"""P4-A fair comparison domain: frozen plan, serial replay, ledger, recovery."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from . import experiment as exp
from .data import CandidatePoolView, DataGateError, HiddenLabelVault, ObservedTrainingSet, PreparedExperiment
from .models import train_regression
from .p3_data import DATASET_ID, DataGateError as P3DataGateError, load_custom_base
from .strategy import Goal, STRATEGIES, recommend

ROOT = Path(__file__).resolve().parents[1]
COMPARISON_ROOT = ROOT / "runs" / "nexttest_comparisons"
EVIDENCE_SEEDS = (20261026, 20261027, 20261028, 20261029, 20261030, 20261031, 20261032, 20261033, 20261034, 20261035)
REHEARSAL_SEEDS = EVIDENCE_SEEDS[:3]
COMPARISON_ID = __import__("re").compile(r"^cmp_[0-9a-f]{32}$")
REQUEST_ID = __import__("re").compile(r"^req_[0-9a-f]{16,64}$")
COMPARISON_SCHEMA = "nexttest_p4a_comparison_v1"
PLAN_SCHEMA = "nexttest_p4a_plan_v1"
LEDGER_SCHEMA = "nexttest_p4a_ledger_v1"
SUMMARY_SCHEMA = "nexttest_p4a_summary_v1"
AUDIT_SCHEMA = "nexttest_p4a_audit_v1"
METRICS_VERSION = "nexttest_p4a_metrics_v1"
DEFAULT_BUDGET = 3
MAX_BUDGET = 10
CELL_TIME_LIMIT = 120.0
TOTAL_TIME_LIMIT = 900.0
STRATEGY_ORDER = ("random", "greedy_prediction", "max_disagreement")
DEMO_DATASET_ID = "demo-concrete"


class ComparisonError(RuntimeError):
    pass


class ComparisonUncertain(ComparisonError):
    pass


def _sha(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode()
    return hashlib.sha256(value).hexdigest()


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def _write_json(path: Path, value) -> None:
    _write_new(path, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode())


def _replace_json(path: Path, value) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def _hashes(root: Path) -> list[dict]:
    return [{"path": p.relative_to(root).as_posix(), "sha256": _sha(p.read_bytes())} for p in sorted(root.rglob("*")) if p.is_file() and p.name != "sha256.txt"]


def _write_hashes(root: Path) -> None:
    rows = _hashes(root)
    text = "\n".join(f"{row['sha256']}  {row['path']}" for row in rows) + "\n"
    (root / "sha256.txt").write_text(text, encoding="utf-8")


def _validate_comparison_id(value: str) -> str:
    if not isinstance(value, str) or COMPARISON_ID.fullmatch(value) is None:
        raise ComparisonError("invalid comparison ID")
    return value


def _validate_request_id(value: str) -> str:
    if not isinstance(value, str) or REQUEST_ID.fullmatch(value) is None:
        raise ComparisonError("invalid request ID")
    return value


def _validate_dataset(dataset_id: str) -> str:
    if dataset_id == DEMO_DATASET_ID:
        return dataset_id
    if not isinstance(dataset_id, str) or DATASET_ID.fullmatch(dataset_id) is None:
        raise ComparisonError("invalid dataset ID")
    return dataset_id


def load_base(dataset_id: str):
    if dataset_id == DEMO_DATASET_ID:
        base, split, package = exp.load_frozen_base()
        target_name = base.observed.target_column
        target_display = {"CompressiveStrength": "抗压强度"}.get(target_name, target_name)
        features = [
            {"name": c, "role": "control", "display_name": {"Cement": "水泥", "Water": "水", "Age": "龄期"}.get(c, c), "unit": "day" if c == "Age" else "kg/m³"}
            for c in base.observed.feature_columns
        ]
        passport = {
            "dataset_version": "nexttest_p4a_demo_ref_v1", "dataset_id": DEMO_DATASET_ID,
            "display_name": "UCI Concrete", "short_id": "DEMO",
            "target": {"name": target_name, "display_name": target_display, "unit": "MPa"},
            "features": features, "units": {f["name"]: f["unit"] for f in features},
            "counts": {"train": len(base.observed.frame), "candidate": len(base.candidates.frame), "test": len(base.test.frame), "groups": split.get("group_count")},
            "sha256": {"input": base.audit.input_sha256, "schema": base.schema.schema_sha256, "split": split["split_sha256"]},
            "unit_not_verified": False, "historical_replay": True,
        }
        return base, split, passport
    base, split, package = load_custom_base(dataset_id)
    passport = {
        "dataset_version": "nexttest_p4a_dataset_ref_v1", "dataset_id": dataset_id,
        "display_name": package["dataset"]["display_name"], "short_id": dataset_id[-8:],
        "target": package["dataset"]["target"], "features": package["dataset"]["features"],
        "units": package["dataset"]["units"],
        "counts": package["dataset"]["counts"], "sha256": package["dataset"]["sha256"],
        "gate_status": package["dataset"]["gate_status"], "unit_not_verified": True,
        "historical_replay": True,
    }
    return base, split, passport


def _plan(dataset_id: str, *, goal: str, threshold: float | None, budget: int, mode: str) -> dict:
    if goal not in {"maximize", "minimize"}:
        raise ComparisonError("invalid goal")
    if threshold is not None and (type(threshold) not in {int, float} or not -1_000_000 <= threshold <= 1_000_000):
        raise ComparisonError("invalid threshold")
    if type(budget) is not int or not 1 <= budget <= MAX_BUDGET:
        raise ComparisonError("budget must be 1..10")
    if mode not in {"evidence", "rehearsal"}:
        raise ComparisonError("invalid comparison mode")
    base, split, passport = load_base(dataset_id)
    if budget > len(base.candidates.frame):
        raise ComparisonError("budget exceeds candidate pool")
    seeds = list(EVIDENCE_SEEDS if mode == "evidence" else REHEARSAL_SEEDS)
    plan = {
        "plan_schema": f"nexttest_p4a_plan_{mode}_v1", "plan_version": 1,
        "comparison_mode": mode,
        "dataset_id": dataset_id,
        "dataset_display_name": passport["display_name"],
        "dataset_short_id": passport["short_id"],
        "dataset_passport_ref": {
            "dataset_id": dataset_id, "display_name": passport["display_name"],
            "target": passport["target"], "counts": passport["counts"],
            "sha256": passport["sha256"], "unit_not_verified": passport.get("unit_not_verified", False),
        },
        "goal": goal, "threshold": threshold, "target": passport["target"],
        "strategies": list(STRATEGY_ORDER),
        "seeds": seeds, "seed_count": len(seeds), "budget": budget,
        "model": {"family": "RandomForestRegressor", "params": {"n_estimators": 120, "max_depth": 8, "min_samples_leaf": 2, "n_jobs": 1, "random_state": "seed"}},
        "tie_break": "row_id_ascending_for_model_strategies; fixed_random_for_random",
        "metrics_version": METRICS_VERSION,
        "time_limit_seconds": TOTAL_TIME_LIMIT, "cell_time_limit_seconds": CELL_TIME_LIMIT,
        "historical_replay": True, "confirmatory": False,
        "exploratory_preview": mode == "rehearsal",
        "eligible_for_comparison_claim": mode == "evidence",
        "unit_not_verified": passport.get("unit_not_verified", False),
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    plan["plan_sha256"] = _sha(_canonical(plan))
    return plan, passport, base, split


def preview_plan(*, dataset_id: str, goal: str, threshold: float | None, budget: int, mode: str) -> dict:
    dataset_id = _validate_dataset(dataset_id)
    plan, passport, base, split = _plan(dataset_id, goal=goal, threshold=threshold, budget=budget, mode=mode)
    return {
        "plan_preview": plan, "dataset": passport,
        "calculation_scale": {"strategies": 3, "seeds": len(plan["seeds"]), "budget": budget, "max_reveals": 3 * len(plan["seeds"]) * budget, "max_model_updates": 3 * len(plan["seeds"]) * budget},
        "candidate_count": len(base.candidates.frame), "initial_observed_count": len(base.observed.frame), "split_sha256": split["split_sha256"],
    }


def _find_by_request(request_id: str) -> Path | None:
    if not COMPARISON_ROOT.is_dir():
        return None
    for root in COMPARISON_ROOT.glob("cmp_*"):
        manifest = root / "comparison_manifest.json"
        if manifest.is_file():
            try:
                value = json.loads(manifest.read_text(encoding="utf-8"))
                if value.get("request_id") == request_id:
                    return root
            except Exception:
                continue
    return None


def create_comparison(*, dataset_id: str, goal: str, threshold: float | None, budget: int, mode: str, request_id: str) -> dict:
    request_id = _validate_request_id(request_id)
    dataset_id = _validate_dataset(dataset_id)
    existing = _find_by_request(request_id)
    if existing is not None:
        return inspect_comparison(existing.name)
    plan, passport, base, split = _plan(dataset_id, goal=goal, threshold=threshold, budget=budget, mode=mode)
    if plan["comparison_mode"] == "rehearsal":
        plan["eligible_for_comparison_claim"] = False
    comparison_id = f"cmp_{uuid.uuid4().hex}"
    root = COMPARISON_ROOT / comparison_id
    root.mkdir(parents=True, exist_ok=False)
    manifest = {
        "manifest_schema": f"nexttest_p4a_comparison_{mode}_v1", "comparison_id": comparison_id,
        "request_id": request_id, "created_utc": datetime.now(timezone.utc).isoformat(),
        "comparison_mode": mode, "dataset_id": dataset_id, "plan_sha256": plan["plan_sha256"],
        "historical_replay": True, "confirmatory": False,
    }
    _write_json(root / "comparison_manifest.json", manifest)
    _write_json(root / "evaluation_plan.json", plan)
    _write_json(root / "dataset_passport_ref.json", passport)
    _write_json(root / "comparison_state.json", {"status": "planned", "run_request_ids": [], "created_utc": manifest["created_utc"]})
    _write_hashes(root)
    return inspect_comparison(comparison_id)


def _load(root: Path) -> tuple[dict, dict, dict, dict]:
    if not root.is_dir():
        raise ComparisonError("comparison not found")
    manifest = json.loads((root / "comparison_manifest.json").read_text(encoding="utf-8"))
    plan = json.loads((root / "evaluation_plan.json").read_text(encoding="utf-8"))
    passport = json.loads((root / "dataset_passport_ref.json").read_text(encoding="utf-8"))
    state = json.loads((root / "comparison_state.json").read_text(encoding="utf-8")) if (root / "comparison_state.json").is_file() else {"status": "planned"}
    if manifest.get("plan_sha256") != plan.get("plan_sha256") or plan.get("plan_sha256") != _sha(_canonical({k: v for k, v in plan.items() if k != "plan_sha256"})):
        raise ComparisonError("evaluation plan hash mismatch")
    if manifest.get("comparison_id") != root.name:
        raise ComparisonError("comparison manifest ID mismatch")
    if plan.get("seeds") != list(EVIDENCE_SEEDS if plan.get("comparison_mode") == "evidence" else REHEARSAL_SEEDS):
        raise ComparisonError("comparison seed plan mismatch")
    if plan.get("strategies") != list(STRATEGY_ORDER):
        raise ComparisonError("comparison strategy plan mismatch")
    return manifest, plan, passport, state


def _cell_root(root: Path, seed: int, strategy: str) -> Path:
    return root / "runs" / str(seed) / strategy


def _event(event_type: str, payload: dict, prev_sha: str) -> dict:
    body = {"event_type": event_type, "payload": payload, "prev_sha": prev_sha}
    return {**body, "event_sha": _sha(_canonical(body))}


def _append_event(path: Path, event_type: str, payload: dict, prev_sha: str) -> tuple[dict, str]:
    event = _event(event_type, payload, prev_sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event, event["event_sha"]


def _read_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fresh_base(base: PreparedExperiment) -> PreparedExperiment:
    vault = HiddenLabelVault(candidate_labels=dict(base.vault.candidate_labels), test_labels=dict(base.vault.test_labels))
    return PreparedExperiment(observed=base.observed, candidates=base.candidates, test=base.test, vault=vault, schema=base.schema, audit=base.audit, split=base.split)


def _run_cell(root: Path, plan: dict, base: PreparedExperiment, seed: int, strategy: str) -> dict:
    cell = _cell_root(root, seed, strategy)
    terminal_path = cell / "terminal.json"
    if terminal_path.is_file():
        return json.loads(terminal_path.read_text(encoding="utf-8"))
    events_path = cell / "events.jsonl"
    cell.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    prev_sha = ""
    observed = base.observed
    candidates = base.candidates
    vault = HiddenLabelVault(candidate_labels=dict(base.vault.candidate_labels), test_labels=dict(base.vault.test_labels))
    predictor = train_regression(PreparedExperiment(observed=observed, candidates=candidates, test=base.test, vault=vault, schema=base.schema, audit=base.audit, split=base.split), seed=seed, evaluate_test=False)
    status = "completed"
    stop_reason = "budget_exhausted"
    error = None
    round_no = 0
    threshold_reached = False
    try:
        while round_no < int(plan["budget"]):
            if time.monotonic() - start > float(plan.get("cell_time_limit_seconds", CELL_TIME_LIMIT)):
                status, stop_reason = "timeout", "cell_time_limit"
                break
            if candidates.frame.empty:
                status, stop_reason = "candidate_exhausted", "candidate_pool_empty"
                break
            round_no += 1
            rec = recommend(strategy, candidates, predictor, goal=Goal(plan["goal"], plan.get("threshold")), seed=seed, round_index=round_no - 1)
            payload = {
                "seed": seed, "strategy": strategy, "round": round_no, "row_id": rec.row_id,
                "prediction": rec.prediction, "disagreement": rec.disagreement, "reason": rec.reason,
                "model_sha": predictor.manifest.model_sha256, "observed_count": len(observed.frame),
                "candidate_count": len(candidates.frame), "budget": plan["budget"],
                "historical_replay": True, "target_hidden": True,
            }
            _, prev_sha = _append_event(events_path, "recommendation", payload, prev_sha)
            _, prev_sha = _append_event(events_path, "release_requested", {"seed": seed, "strategy": strategy, "round": round_no, "row_id": rec.row_id, "target_hidden": True}, prev_sha)
            released = vault.reveal(rec.row_id)
            target = float(released.target)
            _, prev_sha = _append_event(events_path, "label_released", {"seed": seed, "strategy": strategy, "round": round_no, "row_id": rec.row_id, "target": target, "prediction": rec.prediction, "absolute_error": abs(target - rec.prediction)}, prev_sha)
            row = {"_row_id": rec.row_id}
            for column in observed.feature_columns:
                row[column] = float(candidates.frame.loc[candidates.frame["_row_id"] == rec.row_id, column].iloc[0])
            row[observed.target_column] = target
            observed = ObservedTrainingSet(frame=pd.concat([observed.frame, pd.DataFrame([row])], ignore_index=True), feature_columns=observed.feature_columns, target_column=observed.target_column, row_ids=observed.row_ids + (rec.row_id,))
            keep = candidates.frame["_row_id"] != rec.row_id
            candidates = CandidatePoolView(frame=candidates.frame.loc[keep].reset_index(drop=True), feature_columns=candidates.feature_columns, row_ids=tuple(candidates.frame.loc[keep, "_row_id"]))
            threshold_reached = bool(plan.get("threshold") is not None and ((target >= plan["threshold"]) if plan["goal"] == "maximize" else (target <= plan["threshold"])))
            experiment = PreparedExperiment(observed=observed, candidates=candidates, test=base.test, vault=vault, schema=base.schema, audit=base.audit, split=base.split)
            predictor = train_regression(experiment, seed=seed, evaluate_test=False)
            _, prev_sha = _append_event(events_path, "model_updated", {
                "seed": seed, "strategy": strategy, "round": round_no, "model_sha": predictor.manifest.model_sha256,
                "observed_count": len(observed.frame), "candidate_count": len(candidates.frame),
                "remaining_budget": int(plan["budget"]) - round_no, "threshold_reached": threshold_reached,
                "state": "threshold_reached" if threshold_reached else ("budget_exhausted" if round_no >= int(plan["budget"]) else ("candidate_pool_empty" if candidates.frame.empty else "ready")),
            }, prev_sha)
            if threshold_reached:
                status, stop_reason = "stopped_threshold", "threshold_reached"
                break
            if candidates.frame.empty:
                status, stop_reason = "candidate_exhausted", "candidate_pool_empty"
                break
        if round_no >= int(plan["budget"]) and status == "completed":
            status, stop_reason = "completed", "budget_exhausted"
    except Exception as exc:  # noqa: BLE001
        status, stop_reason, error = "failed", "exception", f"{type(exc).__name__}: {exc}"
    terminal = {
        "seed": seed, "strategy": strategy, "status": status, "stop_reason": stop_reason,
        "rounds_used": round_no, "error": error, "event_chain_sha": prev_sha,
        "observed_count": len(observed.frame), "candidate_count": len(candidates.frame),
        "remaining_budget": max(0, int(plan["budget"]) - round_no),
        "final_model_sha": predictor.manifest.model_sha256,
        "threshold_reached": bool(threshold_reached) if plan.get("threshold") is not None else None,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(terminal_path, terminal)
    return terminal


def _oracle(base: PreparedExperiment, direction: str) -> float:
    values = list(base.vault.candidate_labels.values())
    if not values:
        raise ComparisonError("candidate oracle unavailable")
    return max(values) if direction == "maximize" else min(values)


def _ledger(root: Path, plan: dict, base: PreparedExperiment) -> dict:
    oracle = _oracle(base, plan["goal"])
    cells = []
    round_metrics = []
    for seed in plan["seeds"]:
        for strategy in plan["strategies"]:
            cell_root = _cell_root(root, seed, strategy)
            terminal_path = cell_root / "terminal.json"
            events = _read_events(cell_root / "events.jsonl")
            terminal = json.loads(terminal_path.read_text(encoding="utf-8")) if terminal_path.is_file() else {"seed": seed, "strategy": strategy, "status": "not_run", "stop_reason": "not_run", "rounds_used": 0, "error": None}
            rounds = []
            revealed = []
            threshold_first = None
            for event in events:
                if event["event_type"] == "label_released":
                    payload = event["payload"]
                    revealed.append(float(payload["target"]))
                    best = max(revealed) if plan["goal"] == "maximize" else min(revealed)
                    gap = (oracle - best) if plan["goal"] == "maximize" else (best - oracle)
                    if plan.get("threshold") is not None and threshold_first is None:
                        if (plan["goal"] == "maximize" and payload["target"] >= plan["threshold"]) or (plan["goal"] == "minimize" and payload["target"] <= plan["threshold"]):
                            threshold_first = int(payload["round"])
                    rounds.append({
                        "round": int(payload["round"]), "row_id": payload["row_id"],
                        "prediction": float(payload["prediction"]), "revealed_target": float(payload["target"]),
                        "absolute_error": float(payload["absolute_error"]), "best_revealed_target": best,
                        "oracle_gap": max(0.0, gap), "threshold_reached": threshold_first is not None,
                        "reveals_used": int(payload["round"]),
                    })
                    round_metrics.append({"seed": seed, "strategy": strategy, "round": int(payload["round"]), "oracle_gap": max(0.0, gap), "best_revealed_target": best, "prediction_error": float(payload["absolute_error"])})
            cells.append({
                "seed": seed, "strategy": strategy, "status": terminal["status"], "stop_reason": terminal.get("stop_reason"),
                "rounds": rounds, "rounds_used": len(rounds), "threshold_first_round": threshold_first,
                "final_model_sha": terminal.get("final_model_sha"), "error": terminal.get("error"),
            })
    return {
        "ledger_schema": LEDGER_SCHEMA, "ledger_version": 1,
        "comparison_id": root.name, "mode": plan["comparison_mode"],
        "plan": plan, "candidate_oracle": oracle,
        "cells": cells, "round_metrics": round_metrics,
    }


def _state(root: Path, value: dict) -> None:
    _replace_json(root / "comparison_state.json", value)


def run_comparison(comparison_id: str, request_id: str) -> dict:
    comparison_id = _validate_comparison_id(comparison_id)
    request_id = _validate_request_id(request_id)
    root = COMPARISON_ROOT / comparison_id
    manifest, plan, passport, state = _load(root)
    if state.get("status") in {"complete", "incomplete"} and (root / "comparison_ledger.json").is_file():
        return inspect_comparison(comparison_id)
    lock = root / "run.lock"
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    except FileExistsError as exc:
        raise ComparisonUncertain("comparison run already in progress or interrupted; inspect only") from exc
    started = datetime.now(timezone.utc).isoformat()
    cpu_start = time.process_time()
    try:
        state.update({"status": "running", "started_utc": started, "run_request_ids": sorted(set(state.get("run_request_ids", []) + [request_id]))})
        _state(root, state)
        loaded = load_base(plan["dataset_id"])
        base, split, current_passport = loaded
        # The plan's dataset reference must still match the immutable package.
        if plan["dataset_passport_ref"]["sha256"] != current_passport["sha256"]:
            raise ComparisonError("dataset package changed after plan freeze")
        overall_start = time.monotonic()
        for seed in plan["seeds"]:
            for strategy in plan["strategies"]:
                terminal_path = _cell_root(root, seed, strategy) / "terminal.json"
                if terminal_path.is_file():
                    continue
                if time.monotonic() - overall_start > float(plan["time_limit_seconds"]):
                    _write_json(terminal_path, {
                        "seed": seed, "strategy": strategy, "status": "not_run", "stop_reason": "overall_time_limit",
                        "rounds_used": 0, "error": None, "event_chain_sha": "",
                        "observed_count": len(base.observed.frame), "candidate_count": len(base.candidates.frame),
                        "remaining_budget": int(plan["budget"]), "final_model_sha": None,
                        "threshold_reached": None, "finished_utc": datetime.now(timezone.utc).isoformat(),
                    })
                    continue
                try:
                    _run_cell(root, plan, base, seed, strategy)
                except Exception as exc:  # noqa: BLE001
                    _write_json(terminal_path, {"seed": seed, "strategy": strategy, "status": "failed", "stop_reason": "exception", "rounds_used": 0, "error": f"{type(exc).__name__}: {exc}", "event_chain_sha": "", "finished_utc": datetime.now(timezone.utc).isoformat()})
        ledger = _ledger(root, plan, base)
        from .comparison_metrics import summarize
        summary = summarize(ledger)
        _write_json(root / "comparison_ledger.json", ledger)
        _write_json(root / "comparison_summary.json", summary)
        audit = audit_comparison(root, write=False, strict=False, require_complete=False)
        _write_json(root / "audit.json", audit)
        status = "complete" if summary["complete"] and audit.get("valid") else "incomplete"
        state.update({"status": status, "finished_utc": datetime.now(timezone.utc).isoformat(), "cpu_seconds": round(time.process_time() - cpu_start, 3), "wall_seconds": round(time.monotonic() - overall_start, 3), "audit_valid": bool(audit.get("valid"))})
        _state(root, state)
        try:
            lock.unlink()
        except OSError:
            pass
        _write_hashes(root)
        return inspect_comparison(comparison_id)
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def _verify_hashes(root: Path) -> list[str]:
    errors = []
    hashes = root / "sha256.txt"
    if not hashes.is_file():
        return ["sha256.txt missing"]
    for line in hashes.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        try:
            digest, rel = line.split("  ", 1)
        except ValueError:
            errors.append("malformed sha256 line"); continue
        path = root / rel
        if not path.is_file() or _sha(path.read_bytes()) != digest:
            errors.append(f"hash mismatch: {rel}")
    return errors


def audit_comparison(root: Path, *, write: bool = False, strict: bool = True, require_complete: bool = True) -> dict:
    from .comparison_audit import audit
    return audit(root, write=write, strict=strict, require_complete=require_complete)


def inspect_comparison(comparison_id: str) -> dict:
    comparison_id = _validate_comparison_id(comparison_id)
    root = COMPARISON_ROOT / comparison_id
    tree_before = _tree_sha(root) if root.is_dir() else ""
    manifest, plan, passport, state = _load(root)
    ledger = json.loads((root / "comparison_ledger.json").read_text(encoding="utf-8")) if (root / "comparison_ledger.json").is_file() else None
    summary = json.loads((root / "comparison_summary.json").read_text(encoding="utf-8")) if (root / "comparison_summary.json").is_file() else None
    audit = audit_comparison(root, write=False) if ledger is not None else None
    tree_after = _tree_sha(root)
    if tree_before != tree_after:
        audit = {"valid": False, "errors": ["inspect modified comparison tree"], "audit_schema": AUDIT_SCHEMA}
    return {"manifest": manifest, "plan": plan, "dataset": passport, "state": state, "ledger": ledger, "summary": summary, "audit": audit, "tree_sha256": tree_after, "seed_interpretation": "10 个种子用于观察算法随机性，不是 10 次独立物理实验。"}


def export_comparison(comparison_id: str, fmt: str = "json") -> dict:
    value = inspect_comparison(comparison_id)
    if not value["ledger"] or not value["audit"] or not value["audit"].get("valid"):
        raise ComparisonError("comparison is not audit-valid")
    if fmt == "json":
        return {"format": "json", "ledger": value["ledger"], "summary": value["summary"], "audit": value["audit"], "seed_interpretation": value["seed_interpretation"]}
    if fmt == "csv":
        rows = ["seed,strategy,round,row_id,prediction,revealed_target,absolute_error,best_revealed_target,oracle_gap"]
        for cell in value["ledger"]["cells"]:
            for row in cell["rounds"]:
                rows.append(",".join(map(str, [cell["seed"], cell["strategy"], row["round"], row["row_id"], row["prediction"], row["revealed_target"], row["absolute_error"], row["best_revealed_target"], row["oracle_gap"]])))
        return {"format": "csv", "content": "\n".join(rows) + "\n"}
    raise ComparisonError("unsupported export format")
