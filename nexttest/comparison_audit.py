"""Strict P4-A-R auditor.

The auditor is deliberately independent of the stored ledger/summary. It
replays each event round from the frozen candidate vault and only then compares
the derived ledger and summary. A synchronized rewrite of events, ledger,
summary and sha256.txt must still fail on a semantic mismatch.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from .data import CandidatePoolView, ObservedTrainingSet, PreparedExperiment
from .models import train_regression
from .strategy import Goal, recommend

AUDIT_SCHEMA = "nexttest_p4a_r2_audit_v1"
AUDITOR_VERSION = "p4a-r.2"
SEED_INTERPRETATION = "10 个种子用于观察算法随机性，不是 10 次独立物理实验。"
ROUND_TYPES = ("recommendation", "release_requested", "label_released", "model_updated")
STATUS_VALUES = {"completed", "stopped_threshold", "candidate_exhausted", "timeout", "failed", "not_run"}
VALID_TERMINAL = {"completed", "stopped_threshold", "candidate_exhausted"}
SHA_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")
REC_KEYS = {"seed", "strategy", "round", "row_id", "prediction", "disagreement", "reason", "model_sha", "observed_count", "candidate_count", "budget", "historical_replay", "target_hidden"}
REQ_KEYS = {"seed", "strategy", "round", "row_id", "target_hidden"}
REL_KEYS = {"seed", "strategy", "round", "row_id", "target", "prediction", "absolute_error"}
UPD_KEYS = {"seed", "strategy", "round", "model_sha", "observed_count", "candidate_count", "remaining_budget", "threshold_reached", "state"}
EVENT_KEYS = {"event_type", "payload", "prev_sha", "event_sha"}
TERMINAL_KEYS = {"seed", "strategy", "status", "stop_reason", "rounds_used", "error", "event_chain_sha", "observed_count", "candidate_count", "remaining_budget", "final_model_sha", "threshold_reached", "finished_utc"}


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode()
    return hashlib.sha256(value).hexdigest()


def _close(a, b, tol=1e-7) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def _same(a, b, tol=1e-7) -> bool:
    # bool is a subclass of int in Python; true/false must never equal 1/0.
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return _close(a, b, tol)
    return a == b


def _event_hash(event: dict) -> str:
    return _sha(_canonical({k: v for k, v in event.items() if k != "event_sha"}))


def _load_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _hash_files(root: Path) -> list[str]:
    """Strict manifest validation: no BOM, duplicate, malformed, extra, or escaping paths."""
    errors: list[str] = []
    sha_path = root / "sha256.txt"
    if not sha_path.is_file():
        return ["sha256.txt missing"]
    raw = sha_path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return ["sha256.txt contains a UTF-8 BOM"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["sha256.txt is not UTF-8"]
    listed: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line:
            errors.append(f"sha256 line {number}: blank line")
            continue
        match = SHA_LINE.fullmatch(line)
        if not match:
            errors.append(f"sha256 line {number}: malformed")
            continue
        digest, rel = match.groups()
        if rel in listed:
            errors.append(f"sha256 duplicate path: {rel}")
            continue
        if rel.startswith("/") or rel.startswith("\\") or re.match(r"^[A-Za-z]:", rel) or ".." in Path(rel).parts or "\\" in rel:
            errors.append(f"sha256 unsafe path: {rel}")
            continue
        path = root / rel
        try:
            resolved = path.resolve()
            if root.resolve() not in resolved.parents and resolved != root.resolve():
                errors.append(f"sha256 escapes package: {rel}")
                continue
        except Exception:
            errors.append(f"sha256 unresolved path: {rel}")
            continue
        if not path.is_file():
            errors.append(f"sha256 missing file: {rel}")
            continue
        listed[rel] = digest
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "sha256.txt"}
    for rel in actual - set(listed):
        errors.append(f"unregistered file: {rel}")
    for rel, digest in listed.items():
        path = root / rel
        if path.is_file() and _sha(path.read_bytes()) != digest:
            errors.append(f"hash mismatch: {rel}")
    return errors


def _terminal_shape_errors(terminal: dict, label: str) -> list[str]:
    errors = []
    if set(terminal) != TERMINAL_KEYS:
        errors.append(f"{label}: terminal field set mismatch")
        return errors
    if not isinstance(terminal["seed"], int) or isinstance(terminal["seed"], bool):
        errors.append(f"{label}: terminal seed type invalid")
    if not isinstance(terminal["strategy"], str) or terminal["strategy"] not in {"random", "greedy_prediction", "max_disagreement"}:
        errors.append(f"{label}: terminal strategy type/value invalid")
    if not isinstance(terminal["status"], str) or terminal["status"] not in STATUS_VALUES:
        errors.append(f"{label}: terminal status type/value invalid")
    if not isinstance(terminal["stop_reason"], str):
        errors.append(f"{label}: terminal stop_reason type invalid")
    if not isinstance(terminal["rounds_used"], int) or isinstance(terminal["rounds_used"], bool) or terminal["rounds_used"] < 0:
        errors.append(f"{label}: terminal rounds_used type/value invalid")
    if terminal["error"] is not None and not isinstance(terminal["error"], str):
        errors.append(f"{label}: terminal error type invalid")
    if not isinstance(terminal["event_chain_sha"], str):
        errors.append(f"{label}: terminal event_chain_sha type invalid")
    for key in ("observed_count", "candidate_count", "remaining_budget"):
        if not isinstance(terminal[key], int) or isinstance(terminal[key], bool) or terminal[key] < 0:
            errors.append(f"{label}: terminal {key} type/value invalid")
    if terminal["final_model_sha"] is not None and not isinstance(terminal["final_model_sha"], str):
        errors.append(f"{label}: terminal final_model_sha type invalid")
    if terminal["threshold_reached"] is not None and not isinstance(terminal["threshold_reached"], bool):
        errors.append(f"{label}: terminal threshold_reached type invalid")
    if not isinstance(terminal["finished_utc"], str):
        errors.append(f"{label}: terminal finished_utc type invalid")
    else:
        try:
            from datetime import datetime
            datetime.fromisoformat(terminal["finished_utc"].replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"{label}: terminal finished_utc format invalid")
    if terminal["event_chain_sha"] and (len(terminal["event_chain_sha"]) != 64 or any(ch not in "0123456789abcdef" for ch in terminal["event_chain_sha"])):
        errors.append(f"{label}: terminal event_chain_sha format invalid")
    return errors


def _event_field_errors(event: dict, expected: dict, label: str) -> list[str]:
    errors = []
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return [f"{label}: payload is not an object"]
    for key, value in expected.items():
        if not _same(payload.get(key), value):
            errors.append(f"{label}: {key} mismatch")
    return errors


def _state_after_round(plan: dict, round_no: int, candidates_empty: bool, threshold_hit: bool) -> str:
    if threshold_hit:
        return "threshold_reached"
    if round_no >= int(plan["budget"]):
        return "budget_exhausted"
    if candidates_empty:
        return "candidate_pool_empty"
    return "ready"


def _replay_cell(root: Path, base: PreparedExperiment, plan: dict, seed: int, strategy: str) -> tuple[dict, dict, list[str]]:
    errors: list[str] = []
    cell = root / "runs" / str(seed) / strategy
    events_path = cell / "events.jsonl"
    terminal_path = cell / "terminal.json"
    if not terminal_path.is_file():
        raise ValueError(f"{seed}/{strategy}: terminal missing")
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    errors.extend(_terminal_shape_errors(terminal, f"{seed}/{strategy}"))
    try:
        events = _load_events(events_path)
    except Exception as exc:  # noqa: BLE001
        return {}, terminal, [f"{seed}/{strategy}: malformed events: {exc}"]
    if len(events) % 4 != 0:
        errors.append(f"{seed}/{strategy}: incomplete event quartet")
    observed = base.observed
    candidates = base.candidates
    predictor = train_regression(base, seed=seed, evaluate_test=False)
    last_sha = ""
    rounds: list[dict] = []
    released: set[str] = set()
    test_labels = base.vault.test_labels
    candidate_labels = base.vault.candidate_labels
    threshold = plan.get("threshold")
    threshold_hit_any = False
    for offset in range(0, len(events), 4):
        quartet = events[offset:offset + 4]
        round_no = offset // 4 + 1
        if [event.get("event_type") for event in quartet] != list(ROUND_TYPES):
            errors.append(f"{seed}/{strategy}: round {round_no} event order/type invalid")
            continue
        for event in quartet:
            if set(event) != EVENT_KEYS:
                errors.append(f"{seed}/{strategy}: round {round_no} event top-level fields invalid")
            if event.get("prev_sha") != last_sha:
                errors.append(f"{seed}/{strategy}: round {round_no} prev_sha mismatch")
            if event.get("event_sha") != _event_hash(event):
                errors.append(f"{seed}/{strategy}: round {round_no} event SHA mismatch")
            last_sha = event.get("event_sha", last_sha)
        rec_event, request_event, release_event, update_event = quartet
        for event, allowed, label in ((rec_event, REC_KEYS, "recommendation"), (request_event, REQ_KEYS, "release_requested"), (release_event, REL_KEYS, "label_released"), (update_event, UPD_KEYS, "model_updated")):
            if set(event.get("payload", {})) != allowed:
                errors.append(f"{seed}/{strategy}: round {round_no} {label} payload keys invalid")
        rec_payload = rec_event.get("payload", {})
        if int(rec_payload.get("round", -1)) != round_no:
            errors.append(f"{seed}/{strategy}: round {round_no} recommendation round mismatch")
        if rec_payload.get("seed") != seed or rec_payload.get("strategy") != strategy:
            errors.append(f"{seed}/{strategy}: round {round_no} recommendation identity mismatch")
        try:
            rec = recommend(strategy, candidates, predictor, goal=Goal(plan["goal"], threshold), seed=seed, round_index=round_no - 1)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{seed}/{strategy}: round {round_no} recommendation cannot replay: {exc}")
            break
        expected_rec = {
            "seed": seed, "strategy": strategy, "round": round_no,
            "row_id": rec.row_id, "prediction": rec.prediction,
            "disagreement": rec.disagreement, "reason": rec.reason,
            "model_sha": predictor.manifest.model_sha256,
            "observed_count": len(observed.frame), "candidate_count": len(candidates.frame),
            "budget": int(plan["budget"]), "historical_replay": True, "target_hidden": True,
        }
        errors.extend(_event_field_errors(rec_event, expected_rec, f"{seed}/{strategy} round {round_no} recommendation"))
        if rec.row_id not in candidates.row_ids:
            errors.append(f"{seed}/{strategy}: recommended row absent from candidate view")
            break
        errors.extend(_event_field_errors(request_event, {
            "seed": seed, "strategy": strategy, "round": round_no,
            "row_id": rec.row_id, "target_hidden": True,
        }, f"{seed}/{strategy} round {round_no} release_requested"))
        errors.extend(_event_field_errors(release_event, {
            "seed": seed, "strategy": strategy, "round": round_no,
            "row_id": rec.row_id,
        }, f"{seed}/{strategy} round {round_no} label_released identity"))
        if release_event.get("payload", {}).get("row_id") != rec.row_id:
            errors.append(f"{seed}/{strategy}: label release row mismatch")
        if release_event.get("payload", {}).get("round") != round_no:
            errors.append(f"{seed}/{strategy}: label release round mismatch")
        if rec.row_id in test_labels and rec.row_id not in candidate_labels:
            errors.append(f"{seed}/{strategy}: TEST row released")
            break
        if rec.row_id not in candidate_labels:
            errors.append(f"{seed}/{strategy}: release row not in frozen candidate vault")
            break
        if rec.row_id in released:
            errors.append(f"{seed}/{strategy}: candidate released twice")
            break
        vault_target = float(candidate_labels[rec.row_id])
        released.add(rec.row_id)
        errors.extend(_event_field_errors(release_event, {
            "row_id": rec.row_id, "round": round_no, "prediction": rec.prediction,
            "target": vault_target, "absolute_error": abs(vault_target - rec.prediction),
        }, f"{seed}/{strategy} round {round_no} label_released"))
        if not _close(release_event.get("payload", {}).get("target"), vault_target):
            errors.append(f"{seed}/{strategy}: release target does not match frozen vault")
        if not _close(release_event.get("payload", {}).get("prediction"), rec.prediction):
            errors.append(f"{seed}/{strategy}: release prediction does not match recommendation")
        if not _close(release_event.get("payload", {}).get("absolute_error"), abs(vault_target - rec.prediction)):
            errors.append(f"{seed}/{strategy}: release absolute error does not recompute")
        row = {"_row_id": rec.row_id}
        for column in observed.feature_columns:
            row[column] = float(candidates.frame.loc[candidates.frame["_row_id"] == rec.row_id, column].iloc[0])
        row[observed.target_column] = vault_target
        observed = ObservedTrainingSet(
            frame=pd.concat([observed.frame, pd.DataFrame([row])], ignore_index=True),
            feature_columns=observed.feature_columns, target_column=observed.target_column,
            row_ids=observed.row_ids + (rec.row_id,),
        )
        keep = candidates.frame["_row_id"] != rec.row_id
        candidates = CandidatePoolView(
            frame=candidates.frame.loc[keep].reset_index(drop=True),
            feature_columns=candidates.feature_columns,
            row_ids=tuple(candidates.frame.loc[keep, "_row_id"]),
        )
        try:
            predictor = train_regression(PreparedExperiment(observed=observed, candidates=candidates, test=base.test, vault=base.vault, schema=base.schema, audit=base.audit, split=base.split), seed=seed, evaluate_test=False)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{seed}/{strategy}: model retraining failed: {exc}")
            break
        threshold_hit = threshold is not None and (vault_target >= float(threshold) if plan["goal"] == "maximize" else vault_target <= float(threshold))
        threshold_hit_any = threshold_hit_any or threshold_hit
        expected_update = {
            "seed": seed, "strategy": strategy, "round": round_no,
            "model_sha": predictor.manifest.model_sha256,
            "observed_count": len(observed.frame), "candidate_count": len(candidates.frame),
            "remaining_budget": int(plan["budget"]) - round_no,
            "threshold_reached": threshold_hit if threshold is not None else False,
            "state": _state_after_round(plan, round_no, candidates.frame.empty, threshold_hit),
        }
        errors.extend(_event_field_errors(update_event, expected_update, f"{seed}/{strategy} round {round_no} model_updated"))
        rounds.append({
            "round": round_no, "row_id": rec.row_id, "prediction": float(rec.prediction),
            "revealed_target": vault_target, "absolute_error": abs(vault_target - rec.prediction),
            "model_sha": predictor.manifest.model_sha256,
        })
    if len(rounds) * 4 != len(events):
        errors.append(f"{seed}/{strategy}: event count is not complete rounds")
    # Terminal is derived in priority order from what the events prove.
    # A terminal cannot downgrade a proven success/natural stop to timeout/failed,
    # and no-events cells can only be not_run.
    expected_status = None
    expected_reason = None
    if threshold is not None and threshold_hit_any:
        expected_status, expected_reason = "stopped_threshold", "threshold_reached"
    elif len(rounds) >= int(plan["budget"]):
        expected_status, expected_reason = "completed", "budget_exhausted"
    elif candidates.frame.empty:
        expected_status, expected_reason = "candidate_exhausted", "candidate_pool_empty"
    elif not events:
        expected_status, expected_reason = "not_run", "overall_time_limit"
    elif terminal.get("status") == "timeout":
        expected_status, expected_reason = "timeout", "cell_time_limit"
    elif terminal.get("status") == "failed":
        expected_status, expected_reason = "failed", "exception"
    else:
        # A partial replay that is neither a natural stop nor a declared
        # timeout/failed is not a legal successful terminal.
        expected_status, expected_reason = "failed", "exception"
    if terminal.get("status") not in STATUS_VALUES:
        errors.append(f"{seed}/{strategy}: invalid terminal status")
    if terminal.get("status") != expected_status:
        errors.append(f"{seed}/{strategy}: terminal status mismatch (expected {expected_status})")
    if terminal.get("stop_reason") != expected_reason:
        errors.append(f"{seed}/{strategy}: terminal stop_reason mismatch (expected {expected_reason})")
    expected_threshold = None if threshold is None else bool(threshold_hit_any)
    t_expected = {
        "seed": seed, "strategy": strategy, "rounds_used": len(rounds),
        "event_chain_sha": last_sha, "observed_count": len(observed.frame),
        "candidate_count": len(candidates.frame),
        "remaining_budget": max(0, int(plan["budget"]) - len(rounds)),
        "threshold_reached": expected_threshold,
    }
    for key, value in t_expected.items():
        if not _same(terminal.get(key), value):
            errors.append(f"{seed}/{strategy}: terminal {key} mismatch")
    if terminal.get("status") == "failed" and not terminal.get("error"):
        errors.append(f"{seed}/{strategy}: failed terminal lacks error")
    if terminal.get("status") != "failed" and terminal.get("error") not in {None, ""}:
        errors.append(f"{seed}/{strategy}: non-failed terminal has error")
    if terminal.get("status") != "not_run" and terminal.get("final_model_sha") != predictor.manifest.model_sha256:
        errors.append(f"{seed}/{strategy}: terminal final_model_sha mismatch")
    canonical = {
        "seed": seed, "strategy": strategy, "status": terminal.get("status"),
        "stop_reason": terminal.get("stop_reason"), "rounds": rounds,
        "rounds_used": len(rounds),
        "threshold_first_round": next((r["round"] for r in rounds if threshold is not None and (r["revealed_target"] >= float(threshold) if plan["goal"] == "maximize" else r["revealed_target"] <= float(threshold))), None),
        "final_model_sha": terminal.get("final_model_sha"), "error": terminal.get("error"),
    }
    return canonical, terminal, errors


def _canonical_ledger(root: Path, plan: dict, base: PreparedExperiment, cells: list[dict]) -> dict:
    values = list(base.vault.candidate_labels.values())
    oracle = max(values) if plan["goal"] == "maximize" else min(values)
    round_metrics = []
    out_cells = []
    for cell in cells:
        rounds = []
        threshold_first = None
        revealed = []
        for row in cell["rounds"]:
            target = float(row["revealed_target"])
            revealed.append(target)
            best = max(revealed) if plan["goal"] == "maximize" else min(revealed)
            gap = (oracle - best) if plan["goal"] == "maximize" else (best - oracle)
            if plan.get("threshold") is not None and threshold_first is None and ((plan["goal"] == "maximize" and target >= plan["threshold"]) or (plan["goal"] == "minimize" and target <= plan["threshold"])):
                threshold_first = row["round"]
            rounds.append({
                "round": row["round"], "row_id": row["row_id"], "prediction": row["prediction"],
                "revealed_target": target, "absolute_error": row["absolute_error"],
                "best_revealed_target": best, "oracle_gap": max(0.0, gap),
                "threshold_reached": threshold_first is not None, "reveals_used": row["round"],
            })
            round_metrics.append({"seed": cell["seed"], "strategy": cell["strategy"], "round": row["round"], "oracle_gap": max(0.0, gap), "best_revealed_target": best, "prediction_error": row["absolute_error"]})
        out_cells.append({
            "seed": cell["seed"], "strategy": cell["strategy"], "status": cell["status"],
            "stop_reason": cell["stop_reason"], "rounds": rounds, "rounds_used": len(rounds),
            "threshold_first_round": threshold_first, "final_model_sha": cell["final_model_sha"],
            "error": cell["error"],
        })
    return {"ledger_schema": "nexttest_p4a_ledger_v1", "ledger_version": 1, "comparison_id": root.name, "mode": plan["comparison_mode"], "plan": plan, "candidate_oracle": oracle, "cells": out_cells, "round_metrics": round_metrics}


def audit(root: Path, *, write: bool = False, strict: bool = True, require_complete: bool = True) -> dict:
    from .comparison import EVIDENCE_SEEDS, REHEARSAL_SEEDS, load_base
    from .comparison_metrics import METRICS_VERSION, summarize

    errors: list[str] = []
    try:
        manifest = json.loads((root / "comparison_manifest.json").read_text(encoding="utf-8"))
        plan = json.loads((root / "evaluation_plan.json").read_text(encoding="utf-8"))
        passport_ref = json.loads((root / "dataset_passport_ref.json").read_text(encoding="utf-8"))
        state = json.loads((root / "comparison_state.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"audit_schema": AUDIT_SCHEMA, "auditor_version": AUDITOR_VERSION, "semantic_replay": True, "valid": False, "errors": [f"required file unreadable: {exc}"], "metrics_version": METRICS_VERSION, "seed_interpretation": SEED_INTERPRETATION}
    for name in ("comparison_manifest.json", "evaluation_plan.json", "dataset_passport_ref.json", "comparison_state.json", "sha256.txt", "comparison_ledger.json", "comparison_summary.json"):
        if not (root / name).is_file():
            errors.append(f"missing {name}")
    if plan.get("plan_sha256") != _sha(_canonical({k: v for k, v in plan.items() if k != "plan_sha256"})):
        errors.append("plan SHA mismatch")
    if manifest.get("plan_sha256") != plan.get("plan_sha256"):
        errors.append("manifest plan SHA mismatch")
    if plan.get("metrics_version") != METRICS_VERSION:
        errors.append("metrics version mismatch")
    expected_seeds = EVIDENCE_SEEDS if plan.get("comparison_mode") == "evidence" else REHEARSAL_SEEDS
    if plan.get("seeds") != list(expected_seeds):
        errors.append("seed plan mismatch")
    if plan.get("strategies") != ["random", "greedy_prediction", "max_disagreement"]:
        errors.append("strategy plan mismatch")
    if require_complete and state.get("status") not in {"complete", "incomplete"}:
        errors.append("comparison not finished")
    if strict:
        errors.extend(_hash_files(root))
    try:
        ledger = json.loads((root / "comparison_ledger.json").read_text(encoding="utf-8"))
        summary = json.loads((root / "comparison_summary.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"audit_schema": AUDIT_SCHEMA, "auditor_version": AUDITOR_VERSION, "semantic_replay": True, "valid": False, "errors": errors + [f"ledger/summary unreadable: {exc}"], "metrics_version": METRICS_VERSION, "seed_interpretation": SEED_INTERPRETATION}
    try:
        base, split, current_passport = load_base(plan["dataset_id"])
        if current_passport["sha256"] != passport_ref.get("sha256") or current_passport["sha256"] != plan["dataset_passport_ref"].get("sha256"):
            errors.append("dataset passport changed")
        if len(base.candidates.frame) < int(plan["budget"]):
            errors.append("candidate pool smaller than budget")
        canonical_cells = []
        for seed in plan["seeds"]:
            for strategy in plan["strategies"]:
                cell, terminal, cell_errors = _replay_cell(root, base, plan, int(seed), strategy)
                errors.extend(cell_errors)
                canonical_cells.append(cell)
        canonical_ledger = _canonical_ledger(root, plan, base, canonical_cells)
        canonical_summary = summarize(canonical_ledger)
        if _canonical(ledger) != _canonical(canonical_ledger):
            errors.append("ledger does not derive from semantically validated events")
        if _canonical(summary) != _canonical(canonical_summary):
            errors.append("summary does not derive from validated ledger")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"semantic replay failed: {type(exc).__name__}: {exc}")
    result = {
        "audit_schema": AUDIT_SCHEMA, "auditor_version": AUDITOR_VERSION,
        "semantic_replay": True, "metrics_version": METRICS_VERSION,
        "seed_interpretation": SEED_INTERPRETATION,
        "valid": not errors, "errors": errors,
        "planned_cells": 3 * len(plan.get("seeds", [])),
        "observed_cells": len(ledger.get("cells", [])),
        "historical_replay": True, "confirmatory": False,
        "tree_sha256": _sha(_canonical(sorted(({"path": p.relative_to(root).as_posix(), "sha256": _sha(p.read_bytes())} for p in root.rglob("*") if p.is_file()), key=lambda item: item["path"]))),
    }
    if write:
        (root / "audit.json").write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return result
