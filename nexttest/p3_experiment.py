"""P3 custom-dataset project loop built on the frozen dataset package."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .data import CandidatePoolView, DataGateError, HiddenLabelVault, ObservedTrainingSet, PreparedExperiment
from .models import TrainedPredictor, train_regression
from .p3_data import DATASET_ID, PROJECT_ID, PROJECT_ROOT, load_custom_base
from .project_store import ProjectStore
from .schemas import canonical_json
from .strategy import Goal, recommend

PROJECT_SCHEMA = "nexttest_p3_project_v1"


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _view_sha(view) -> str:
    payload = {
        "row_ids": list(view.row_ids),
        "columns": list(view.feature_columns),
        "rows": view.frame[list(view.feature_columns)].to_dict(orient="records"),
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def _candidate_view(frame: pd.DataFrame, features: tuple[str, ...], row_ids: tuple[str, ...]) -> CandidatePoolView:
    return CandidatePoolView(frame=frame.reset_index(drop=True), feature_columns=features, row_ids=row_ids)


def _dataset_meta(manifest: dict) -> dict:
    return manifest["dataset"]


@dataclass
class CustomState:
    base: PreparedExperiment
    observed: ObservedTrainingSet
    candidates: CandidatePoolView
    vault: HiddenLabelVault
    current_model_sha: str
    pending: dict | None
    status: str
    budget: int
    revealed_count: int
    current_model: TrainedPredictor
    events: list[dict]
    transition: dict | None
    last_target: float | None = None
    last_prediction: float | None = None
    last_row_id: str | None = None
    failure: str | None = None


def _state(store: ProjectStore) -> CustomState:
    manifest = store.manifest()
    dataset_id = manifest["dataset_id"]
    base, package_split, package_manifest = load_custom_base(dataset_id)
    if manifest.get("source_sha256") != package_manifest["dataset"]["sha256"]["input"] or manifest.get("split_sha256") != package_split["split_sha256"]:
        raise DataGateError("custom project manifest does not bind dataset package")
    if manifest.get("test_sha256") != _view_sha(base.test):
        raise DataGateError("custom project test view changed")
    observed = base.observed
    candidates = base.candidates
    model_sha = manifest["initial_model_sha"]
    events = store.events()
    pending = None
    status = "ready"
    budget = int(manifest["budget"])
    revealed_count = 0
    transition = None
    last_target = last_prediction = last_row_id = None
    failure = None
    recommendations = {}
    for event in events:
        kind = event["event_type"]
        item = event["payload"]
        if kind == "recommendation":
            if status != "ready" or pending is not None:
                raise DataGateError("invalid custom recommendation sequence")
            if item["row_id"] not in candidates.row_ids:
                raise DataGateError("custom recommendation outside candidate pool")
            recommendations[item["recommendation_id"]] = item
            pending = item
            status = "awaiting_user_confirmation"
        elif kind == "release_requested":
            if pending is None or item["recommendation_id"] != pending["recommendation_id"] or item["row_id"] != pending["row_id"]:
                raise DataGateError("custom release does not match pending")
            status = "release_requested"
        elif kind == "label_released":
            if pending is None or status != "release_requested" or item["recommendation_id"] != pending["recommendation_id"] or item["row_id"] != pending["row_id"]:
                raise DataGateError("custom label release does not match pending")
            row_id = item["row_id"]
            if row_id not in candidates.row_ids:
                raise DataGateError("custom released row not in candidates")
            target = float(item["target"])
            source = base.candidates.frame.loc[base.candidates.frame["_row_id"] == row_id].iloc[0]
            new_row = {"_row_id": row_id}
            for column in base.observed.feature_columns:
                new_row[column] = float(source[column])
            new_row[base.observed.target_column] = target
            observed = ObservedTrainingSet(
                frame=pd.concat([observed.frame, pd.DataFrame([new_row])], ignore_index=True),
                feature_columns=observed.feature_columns,
                target_column=observed.target_column,
                row_ids=observed.row_ids + (row_id,),
            )
            keep = candidates.frame["_row_id"] != row_id
            candidates = _candidate_view(candidates.frame.loc[keep], candidates.feature_columns, tuple(candidates.frame.loc[keep, "_row_id"]))
            budget -= 1
            revealed_count += 1
            last_target, last_prediction, last_row_id = target, float(item["prediction"]), row_id
            status = "revealed"
        elif kind == "model_updated":
            if status != "revealed" or pending is None:
                raise DataGateError("custom update missing release")
            if int(item["observed_count"]) != len(observed.frame):
                raise DataGateError("custom observed count mismatch")
            model_sha = item["model_sha"]
            if not (store.root / "models" / model_sha).is_dir():
                raise DataGateError("custom model artifact missing")
            transition = {
                "before": {
                    "model_sha": recommendations[item["recommendation_id"]].get("model_sha"),
                    "revealed_count": int(revealed_count) - 1,
                    "remaining_budget": int(item["remaining_budget"]) + 1,
                    "observed_count": int(item["observed_count"]) - 1,
                    "candidate_count": int(item["candidate_count"]) + 1,
                    "pending_row": recommendations[item["recommendation_id"]].get("row_id"),
                },
                "after": {
                    "model_sha": model_sha,
                    "revealed_count": int(revealed_count),
                    "remaining_budget": int(item["remaining_budget"]),
                    "observed_count": int(item["observed_count"]),
                    "candidate_count": int(item["candidate_count"]),
                    "latest_revealed_row": item.get("row_id"),
                },
            }
            status = item["state"]
            pending = None
        elif kind == "release_failed":
            status, failure = "release_uncertain", item.get("error")
        elif kind == "update_failed":
            status, failure = "update_failed", item.get("error")
        else:
            raise DataGateError("unknown custom event type")
    if status == "release_requested":
        status = "release_uncertain"
    if status == "revealed":
        status = "update_uncertain"
    return CustomState(
        base=base, observed=observed, candidates=candidates, vault=base.vault,
        current_model_sha=model_sha, pending=pending, status=status, budget=budget,
        revealed_count=revealed_count, current_model=store.load_model(model_sha),
        events=events, transition=transition, last_target=last_target,
        last_prediction=last_prediction, last_row_id=last_row_id, failure=failure,
    )


def _meta(manifest: dict) -> dict:
    d = manifest["dataset"]
    return {
        "dataset_id": manifest["dataset_id"],
        "display_name": d["display_name"],
        "short_id": manifest["dataset_id"][-8:],
        "target": d["target"],
        "features": d["features"],
        "units": d["units"],
        "unit_not_verified": True,
        "sha256": d["sha256"],
        "counts": d["counts"],
        "gate_status": d["gate_status"],
        "historical_replay": True,
    }


def _view(project_id: str, store: ProjectStore, state: CustomState) -> dict:
    manifest = store.manifest()
    meta = _meta(manifest)
    snapshot = {
        "snapshot_version": "nexttest_p3_snapshot_v1",
        "project_id": project_id,
        "status": state.status,
        "goal": manifest["goal"],
        "threshold": manifest.get("threshold"),
        "budget": int(manifest["budget"]),
        "remaining_budget": state.budget,
        "strategy": manifest["strategy"],
        "seed": int(manifest["seed"]),
        "revealed_count": state.revealed_count,
        "observed_count": len(state.observed.frame),
        "candidate_count": len(state.candidates.frame),
        "test_count": len(state.base.test.frame),
        "current_model_sha": state.current_model_sha,
        "initial_model_sha": manifest["initial_model_sha"],
        "split_sha256": manifest["split_sha256"],
        "source_canonical_sha256": manifest["source_sha256"],
        "observed_row_ids_sha256": hashlib.sha256(canonical_json(list(state.observed.row_ids)).encode()).hexdigest(),
        "test_sha256": _view_sha(state.base.test),
        "dataset_id": manifest["dataset_id"],
        "dataset_display_name": meta["display_name"],
        "dataset_short_id": meta["short_id"],
        "historical_replay": True,
        "user_data_replay": True,
    }
    pending = None
    if state.pending:
        pending = {
            "recommendation_id": state.pending["recommendation_id"],
            "row_id": state.pending["row_id"],
            "controls": {column: float(state.base.candidates.frame.loc[state.base.candidates.frame["_row_id"] == state.pending["row_id"], column].iloc[0]) for column in state.base.observed.feature_columns},
            "prediction": float(state.pending["prediction"]),
            "disagreement": state.pending.get("disagreement"),
            "reason": state.pending.get("reason"),
        }
    history = []
    for event in state.events:
        if event["event_type"] == "label_released":
            item = event["payload"]
            history.append({
                "round": len(history) + 1, "row_id": item["row_id"],
                "prediction": float(item["prediction"]), "revealed_target": float(item["target"]),
                "absolute_error": float(item["absolute_error"]),
                "strategy": next((e["payload"].get("strategy") for e in state.events if e["event_type"] == "recommendation" and e["payload"]["recommendation_id"] == item["recommendation_id"]), manifest["strategy"]),
            })
    models_present = all((store.root / "models" / e["payload"].get("model_sha", "")).is_dir() for e in state.events if e["event_type"] == "model_updated")
    models_present = models_present and (store.root / "models" / state.current_model_sha).is_dir()
    audit = {
        "audit_version": "nexttest_p3_audit_v1", "project_id": project_id, "status": state.status,
        "event_count": len(state.events), "event_chain_sha256": store.event_chain_sha(),
        "tree_sha256": store.tree_sha(), "project_manifest_sha256": _sha_file(store.manifest_path),
        "source_canonical_sha256": manifest["source_sha256"], "split_sha256": manifest["split_sha256"],
        "test_sha256": _view_sha(state.base.test), "observed_count": len(state.observed.frame),
        "candidate_count": len(state.candidates.frame), "test_count": len(state.base.test.frame),
        "test_unchanged": True, "models_present": models_present, "historical_replay": True,
    }
    return {"snapshot": snapshot, "audit": audit, "pending": pending, "history": history, "transition": state.transition, "dataset": {**meta, "target": meta["target"], "features": meta["features"]}}


def create_custom_project(*, dataset_id: str, goal: str = "maximize", threshold: float | None = None, budget: int = 3, strategy: str = "greedy_prediction", seed: int = 20261026, project_id: str | None = None) -> dict:
    if not isinstance(dataset_id, str) or DATASET_ID.fullmatch(dataset_id) is None:
        raise DataGateError("invalid dataset ID")
    if strategy not in {"random", "greedy_prediction", "max_disagreement"}:
        raise ValueError("unknown strategy")
    if not isinstance(budget, int) or isinstance(budget, bool) or not 1 <= budget <= 20:
        raise ValueError("budget must be 1..20")
    goal_obj = Goal(goal, threshold)
    base, split, package = load_custom_base(dataset_id)
    predictor = train_regression(base, seed=int(seed), evaluate_test=False)
    initial_model_sha = predictor.manifest.model_sha256
    pid = project_id or f"p3_{uuid.uuid4().hex}"
    if not PROJECT_ID.fullmatch(pid):
        raise DataGateError("invalid project ID")
    root = PROJECT_ROOT / pid
    if root.exists():
        raise FileExistsError("custom project already exists")
    meta = _meta({"dataset_id": dataset_id, "dataset": package["dataset"]})
    manifest = {
        "schema": PROJECT_SCHEMA, "project_id": pid, "dataset_id": dataset_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": package["dataset"],
        "goal": goal_obj.direction, "threshold": goal_obj.threshold, "budget": int(budget), "strategy": strategy, "seed": int(seed),
        "source_sha256": package["dataset"]["sha256"]["input"], "schema_sha256": package["dataset"]["sha256"].get("schema"),
        "split_sha256": split["split_sha256"], "test_sha256": _view_sha(base.test),
        "initial_model_sha": initial_model_sha, "initial_observed_count": len(base.observed.frame),
        "initial_candidate_count": len(base.candidates.frame), "test_count": len(base.test.frame),
        "state": "ready",
    }
    store = ProjectStore.create(root, manifest)
    actual = store.write_model(predictor)
    if actual != initial_model_sha:
        raise DataGateError("custom initial model SHA changed")
    return _view(pid, store, _state(store))


def _store(project_id: str) -> ProjectStore:
    if not isinstance(project_id, str) or PROJECT_ID.fullmatch(project_id) is None:
        raise DataGateError("invalid custom project ID")
    root = PROJECT_ROOT / project_id
    if not root.is_dir():
        raise FileNotFoundError("custom project not found")
    return ProjectStore(root)


def get_custom_project(project_id: str) -> dict:
    store = _store(project_id)
    return _view(project_id, store, _state(store))


def recommend_custom(project_id: str) -> dict:
    store = _store(project_id)
    state = _state(store)
    if state.status != "ready":
        raise DataGateError("custom recommendation not allowed")
    if state.budget <= 0 or state.candidates.frame.empty:
        raise DataGateError("custom budget exhausted or candidate pool empty")
    manifest = store.manifest()
    rec = recommend(manifest["strategy"], state.candidates, state.current_model, goal=Goal(manifest["goal"], manifest.get("threshold")), seed=int(manifest["seed"]), round_index=state.revealed_count)
    rec_id = f"rec-{len(state.events) + 1:06d}"
    store.append_event("recommendation", {
        "recommendation_id": rec_id, "strategy": rec.strategy, "row_id": rec.row_id,
        "prediction": rec.prediction, "disagreement": rec.disagreement, "reason": rec.reason,
        "model_sha": state.current_model_sha, "round_index": state.revealed_count,
        "historical_replay": True, "target_hidden": True,
    })
    return _view(project_id, store, _state(store))


def reveal_custom(project_id: str, recommendation_id: str) -> dict:
    store = _store(project_id)
    state = _state(store)
    if state.status != "awaiting_user_confirmation" or state.pending is None:
        raise DataGateError("custom reveal not allowed")
    if state.pending["recommendation_id"] != recommendation_id:
        raise DataGateError("custom recommendation ID mismatch")
    row_id = state.pending["row_id"]
    prediction = float(state.pending["prediction"])
    before = state.current_model_sha
    store.append_event("release_requested", {"recommendation_id": recommendation_id, "row_id": row_id, "target_hidden": True})
    try:
        released = state.vault.reveal(row_id)
    except Exception as exc:  # noqa: BLE001
        store.append_event("release_failed", {"recommendation_id": recommendation_id, "row_id": row_id, "error": f"{type(exc).__name__}: {exc}"})
        raise DataGateError("custom label release failed; no retry") from exc
    target = float(released.target)
    store.append_event("label_released", {
        "recommendation_id": recommendation_id, "row_id": row_id, "target": target,
        "prediction": prediction, "absolute_error": abs(prediction - target), "historical_replay": True,
    })
    source = state.candidates.frame.loc[state.candidates.frame["_row_id"] == row_id].iloc[0]
    row = {"_row_id": row_id}
    for column in state.observed.feature_columns:
        row[column] = float(source[column])
    row[state.observed.target_column] = target
    observed = ObservedTrainingSet(frame=pd.concat([state.observed.frame, pd.DataFrame([row])], ignore_index=True), feature_columns=state.observed.feature_columns, target_column=state.observed.target_column, row_ids=state.observed.row_ids + (row_id,))
    keep = state.candidates.frame["_row_id"] != row_id
    candidates = _candidate_view(state.candidates.frame.loc[keep], state.candidates.feature_columns, tuple(state.candidates.frame.loc[keep, "_row_id"]))
    try:
        experiment = PreparedExperiment(observed=observed, candidates=candidates, test=state.base.test, vault=state.vault, schema=state.base.schema, audit=state.base.audit, split=state.base.split)
        predictor = train_regression(experiment, seed=int(store.manifest()["seed"]), evaluate_test=False)
        after = store.write_model(predictor)
    except Exception as exc:  # noqa: BLE001
        store.append_event("update_failed", {"recommendation_id": recommendation_id, "row_id": row_id, "error": f"{type(exc).__name__}: {exc}"})
        raise DataGateError("custom model update failed; no retry") from exc
    remaining = state.budget - 1
    next_state = "budget_exhausted" if remaining <= 0 else "candidate_pool_empty" if candidates.frame.empty else "ready"
    store.append_event("model_updated", {
        "recommendation_id": recommendation_id, "row_id": row_id, "model_sha": after,
        "observed_count": len(observed.frame), "candidate_count": len(candidates.frame),
        "remaining_budget": remaining, "state": next_state, "historical_replay": True,
    })
    return _view(project_id, store, _state(store))


def inspect_custom(project_id: str) -> dict:
    store = _store(project_id)
    state = _state(store)
    test_ids = set(state.base.test.row_ids)
    if test_ids & (set(state.observed.row_ids) | set(state.candidates.row_ids)):
        raise DataGateError("custom test rows leaked")
    return _view(project_id, store, state)


def preview_custom(dataset_id: str, *, strategy: str, goal: str = "maximize", threshold: float | None = None, project_id: str | None = None) -> dict:
    if not isinstance(dataset_id, str) or DATASET_ID.fullmatch(dataset_id) is None:
        raise DataGateError("invalid dataset ID")
    if strategy not in {"random", "greedy_prediction", "max_disagreement"}:
        raise ValueError("unknown strategy")
    goal_obj = Goal(goal, threshold)
    if project_id is not None:
        store = _store(project_id)
        state = _state(store)
        if state.status != "ready":
            raise DataGateError("custom candidate preview not allowed in current state")
        base = state.base
        split = state.base.split.to_dict()
        package = store.manifest()
        predictor = state.current_model
        view = state.candidates
        model_sha = state.current_model_sha
    else:
        base, split, package = load_custom_base(dataset_id)
        predictor = train_regression(base, seed=20261026, evaluate_test=False)
        view = base.candidates
        model_sha = predictor.manifest.model_sha256
    prediction = predictor.predict(view.frame)
    estimators = getattr(predictor.model, "estimators_", None)
    std = None
    if estimators:
        matrix = np.asarray([tree.predict(view.frame[list(view.feature_columns)].to_numpy(dtype=float)) for tree in estimators], dtype=float)
        std = matrix.std(axis=0)
    rows = []
    for index, row_id in enumerate(view.row_ids):
        rows.append({"row_id": row_id, "controls": {col: float(view.frame.iloc[index][col]) for col in view.feature_columns}, "prediction": float(prediction[index]), "disagreement": None if std is None else float(std[index])})
    rankings = {}
    for s in ("greedy_prediction", "max_disagreement", "random"):
        r = recommend(s, view, predictor, goal=goal_obj, seed=20261026, round_index=0)
        rankings[s] = {"row_id": r.row_id, "prediction": r.prediction, "disagreement": r.disagreement, "reason": r.reason}
    dataset_meta = _meta(package) if "dataset" in package and "dataset_id" in package else _meta({"dataset_id": dataset_id, "dataset": package["dataset"]})
    return {"scope": "custom_candidate_pool_no_labels", "dataset_id": dataset_id, "project_id": project_id, "dataset": dataset_meta, "strategy": strategy, "model_sha": model_sha, "candidate_count": len(rows), "rows": rows, "rankings": rankings, "selected": rankings.get(strategy), "goal": goal_obj.direction, "threshold": goal_obj.threshold}


def custom_landscape(dataset_id: str) -> dict:
    if not isinstance(dataset_id, str) or DATASET_ID.fullmatch(dataset_id) is None:
        raise DataGateError("invalid dataset ID")
    base, split, package = load_custom_base(dataset_id)
    columns = ["_row_id", *base.observed.feature_columns, base.observed.target_column]
    rows = base.observed.frame[columns].to_dict(orient="records")
    return {
        "scope": "observed_training_only",
        "dataset_id": dataset_id,
        "dataset": _meta({"dataset_id": dataset_id, "dataset": package["dataset"]}),
        "rows": [{str(k): (float(v) if isinstance(v, (int, float)) else v) for k, v in row.items()} for row in rows],
        "count": len(rows),
        "split_sha256": split["split_sha256"],
    }
