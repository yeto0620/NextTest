"""One active historical-replay experiment loop for NextTest P2."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .data import CandidatePoolView, HiddenLabelVault, ObservedTrainingSet, PreparedExperiment, DataGateError, prepare_dataset
from .demo import concrete_schema
from .models import TrainedPredictor, train_regression
from .project_store import ProjectStore
from .schemas import canonical_json
from .strategy import Goal, Recommendation, recommend

ROOT = Path(__file__).resolve().parents[1]
# Development/reproduction uses the audited artifacts and data directories.
# The public source bundle ships the same four frozen, hash-checked files under
# nexttest/demo_assets so a fresh clone can run the demo without raw data files.
_P1R_EXTERNAL_OUTPUT = ROOT / "artifacts" / "nexttest_p1_uci_concrete"
_P1R_EXTERNAL_CANONICAL = ROOT / "data" / "nexttest" / "uci_concrete" / "canonical" / "concrete_age28.csv"
_P1R_BUNDLED_OUTPUT = ROOT / "nexttest" / "demo_assets"
_P1R_BUNDLED_CANONICAL = _P1R_BUNDLED_OUTPUT / "concrete_age28.csv"
_P1R_REQUIRED = ("manifest.json", "split.json", "source_manifest.json")
if all((_P1R_EXTERNAL_OUTPUT / name).is_file() for name in _P1R_REQUIRED) and _P1R_EXTERNAL_CANONICAL.is_file():
    P1R_OUTPUT = _P1R_EXTERNAL_OUTPUT
    P1R_CANONICAL = _P1R_EXTERNAL_CANONICAL
elif all((_P1R_BUNDLED_OUTPUT / name).is_file() for name in _P1R_REQUIRED) and _P1R_BUNDLED_CANONICAL.is_file():
    P1R_OUTPUT = _P1R_BUNDLED_OUTPUT
    P1R_CANONICAL = _P1R_BUNDLED_CANONICAL
else:
    P1R_OUTPUT = _P1R_EXTERNAL_OUTPUT
    P1R_CANONICAL = _P1R_EXTERNAL_CANONICAL
PROJECT_ROOT = ROOT / "artifacts" / "nexttest_p2" / "projects"
PROJECT_SCHEMA = "nexttest_p2_project_v1"
EVENT_SCHEMA = "nexttest_p2_event_v1"
HISTORICAL_REPLAY = True


@dataclass(frozen=True)
class ProjectSnapshot:
    project_id: str
    status: str
    goal: str
    threshold: float | None
    budget: int
    remaining_budget: int
    strategy: str
    seed: int
    revealed_count: int
    observed_count: int
    candidate_count: int
    test_count: int
    current_model_sha: str
    initial_model_sha: str
    split_sha256: str
    source_canonical_sha256: str
    observed_row_ids_sha256: str
    test_sha256: str
    historical_replay: bool = True

    def to_dict(self) -> dict:
        return {
            "snapshot_version": "nexttest_p2_snapshot_v1",
            "project_id": self.project_id,
            "status": self.status,
            "goal": self.goal,
            "threshold": self.threshold,
            "budget": self.budget,
            "remaining_budget": self.remaining_budget,
            "strategy": self.strategy,
            "seed": self.seed,
            "revealed_count": self.revealed_count,
            "observed_count": self.observed_count,
            "candidate_count": self.candidate_count,
            "test_count": self.test_count,
            "current_model_sha": self.current_model_sha,
            "initial_model_sha": self.initial_model_sha,
            "split_sha256": self.split_sha256,
            "source_canonical_sha256": self.source_canonical_sha256,
            "observed_row_ids_sha256": self.observed_row_ids_sha256,
            "test_sha256": self.test_sha256,
            "historical_replay": self.historical_replay,
        }


@dataclass(frozen=True)
class RecommendationView:
    project_id: str
    recommendation_id: str
    status: str
    row_id: str
    controls: dict[str, float]
    prediction: float
    disagreement: float | None
    reason: str
    historical_replay: bool = True

    def to_dict(self) -> dict:
        return {
            "recommendation_version": "nexttest_p2_recommendation_v1",
            "project_id": self.project_id,
            "recommendation_id": self.recommendation_id,
            "status": self.status,
            "row_id": self.row_id,
            "controls": dict(self.controls),
            "prediction": self.prediction,
            "disagreement": self.disagreement,
            "reason": self.reason,
            "historical_replay": self.historical_replay,
            "target_hidden": True,
        }


@dataclass(frozen=True)
class FeedbackResult:
    project_id: str
    recommendation_id: str
    row_id: str
    revealed_target: float
    prediction: float
    absolute_error: float
    status: str
    model_sha_before: str
    model_sha_after: str
    remaining_budget: int
    next_available: bool
    historical_replay: bool = True

    def to_dict(self) -> dict:
        return {
            "feedback_version": "nexttest_p2_feedback_v1",
            "project_id": self.project_id,
            "recommendation_id": self.recommendation_id,
            "row_id": self.row_id,
            "revealed_target": self.revealed_target,
            "prediction": self.prediction,
            "absolute_error": self.absolute_error,
            "status": self.status,
            "model_sha_before": self.model_sha_before,
            "model_sha_after": self.model_sha_after,
            "remaining_budget": self.remaining_budget,
            "next_available": self.next_available,
            "historical_replay": self.historical_replay,
            "source": "historical UCI Age=28 replay; not a new physical test",
        }


@dataclass(frozen=True)
class AuditSummary:
    project_id: str
    status: str
    event_count: int
    event_chain_sha256: str
    tree_sha256: str
    project_manifest_sha256: str
    source_canonical_sha256: str
    split_sha256: str
    test_sha256: str
    observed_count: int
    candidate_count: int
    test_count: int
    test_unchanged: bool
    models_present: bool
    historical_replay: bool = True

    def to_dict(self) -> dict:
        return {
            "audit_version": "nexttest_p2_audit_v1",
            "project_id": self.project_id,
            "status": self.status,
            "event_count": self.event_count,
            "event_chain_sha256": self.event_chain_sha256,
            "tree_sha256": self.tree_sha256,
            "project_manifest_sha256": self.project_manifest_sha256,
            "source_canonical_sha256": self.source_canonical_sha256,
            "split_sha256": self.split_sha256,
            "test_sha256": self.test_sha256,
            "observed_count": self.observed_count,
            "candidate_count": self.candidate_count,
            "test_count": self.test_count,
            "test_unchanged": self.test_unchanged,
            "models_present": self.models_present,
            "historical_replay": self.historical_replay,
        }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row_ids_sha(ids: tuple[str, ...]) -> str:
    return hashlib.sha256(canonical_json(list(ids)).encode()).hexdigest()


def _view_sha(view) -> str:
    payload = {
        "row_ids": list(view.row_ids),
        "columns": list(view.feature_columns),
        "rows": view.frame[list(view.feature_columns)].to_dict(orient="records"),
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def load_frozen_base() -> tuple[PreparedExperiment, dict, dict]:
    manifest_path = P1R_OUTPUT / "manifest.json"
    split_path = P1R_OUTPUT / "split.json"
    source_path = P1R_OUTPUT / "source_manifest.json"
    if not all(path.is_file() for path in (manifest_path, split_path, source_path, P1R_CANONICAL)):
        raise DataGateError("P1-R frozen output is incomplete")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    split = json.loads(split_path.read_text(encoding="utf-8"))
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if manifest.get("dataset_mode") != "official" or manifest.get("non_real_demo") is not False:
        raise DataGateError("P1-R output is not the real official run")
    if source.get("license") != "CC BY 4.0" or source.get("http_status") != 200:
        raise DataGateError("P1-R source metadata is invalid")
    if manifest["data_source"]["source_manifest_sha256"] != _sha(source_path):
        raise DataGateError("source manifest SHA mismatch")
    if manifest["data_source"]["age28_csv_sha256"] != _sha(P1R_CANONICAL):
        raise DataGateError("P1-R Age=28 canonical SHA mismatch")
    schema = concrete_schema("uci_concrete_age28")
    prepared = prepare_dataset(P1R_CANONICAL, schema, seed=int(split["seed"]))
    if prepared.split.split_sha256 != split["split_sha256"]:
        raise DataGateError("P1-R split SHA was not reproduced")
    if list(prepared.split.train_row_ids) != split["train_row_ids"] or list(prepared.split.candidate_row_ids) != split["candidate_row_ids"] or list(prepared.split.test_row_ids) != split["test_row_ids"]:
        raise DataGateError("P1-R row IDs were not reproduced")
    return prepared, split, manifest


def _candidate_view(frame: pd.DataFrame, features: tuple[str, ...], row_ids: tuple[str, ...]) -> CandidatePoolView:
    return CandidatePoolView(frame=frame.reset_index(drop=True), feature_columns=features, row_ids=row_ids)


@dataclass
class LoopState:
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
    last_target: float | None = None
    last_prediction: float | None = None
    last_row_id: str | None = None
    failure: str | None = None


def _state_from_store(store: ProjectStore) -> LoopState:
    base, split, p1r_manifest = load_frozen_base()
    manifest = store.manifest()
    if manifest.get("split_sha256") != split["split_sha256"] or manifest.get("source_canonical_sha256") != _sha(P1R_CANONICAL):
        raise DataGateError("project manifest does not match frozen P1-R data")
    if manifest.get("test_sha256") != _view_sha(base.test):
        raise DataGateError("project test view SHA changed")
    observed = base.observed
    candidates = base.candidates
    model_sha = manifest["initial_model_sha"]
    events = store.events()
    pending = None
    status = "ready"
    budget = int(manifest["budget"])
    revealed_count = 0
    last_target = None
    last_prediction = None
    last_row_id = None
    failure = None
    for event in events:
        kind = event["event_type"]
        payload = event["payload"]
        if kind == "recommendation":
            if status != "ready" or pending is not None:
                raise DataGateError("invalid recommendation event sequence")
            if payload["row_id"] not in candidates.row_ids:
                raise DataGateError("recommendation not in candidate pool")
            pending = payload
            status = "awaiting_user_confirmation"
        elif kind == "release_requested":
            if pending is None or payload["recommendation_id"] != pending["recommendation_id"] or payload["row_id"] != pending["row_id"]:
                raise DataGateError("release requested does not match pending recommendation")
            status = "release_requested"
        elif kind == "label_released":
            if pending is None or status != "release_requested" or payload["recommendation_id"] != pending["recommendation_id"] or payload["row_id"] != pending["row_id"]:
                raise DataGateError("label release does not match requested recommendation")
            row_id = payload["row_id"]
            if row_id not in candidates.row_ids:
                raise DataGateError("released row is not a candidate")
            target = float(payload["target"])
            source_row = base.candidates.frame.loc[base.candidates.frame["_row_id"] == row_id].iloc[0]
            new_row = {"_row_id": row_id}
            for column in base.observed.feature_columns:
                new_row[column] = float(source_row[column])
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
            last_target = target
            last_prediction = float(payload["prediction"])
            last_row_id = row_id
            status = "revealed"
        elif kind == "model_updated":
            if status != "revealed" or pending is None:
                raise DataGateError("model update missing released label")
            if int(payload["observed_count"]) != len(observed.frame):
                raise DataGateError("observed count mismatch")
            model_sha = payload["model_sha"]
            if not (store.root / "models" / model_sha).is_dir():
                raise DataGateError("model artifact missing")
            status = payload["state"]
            pending = None
        elif kind == "release_failed":
            status = "release_uncertain"
            failure = payload.get("error")
        elif kind == "update_failed":
            status = "update_failed"
            failure = payload.get("error")
        else:
            raise DataGateError(f"unknown event type: {kind}")
    if status == "awaiting_user_confirmation" and pending is None:
        raise DataGateError("pending recommendation missing")
    if status == "release_requested":
        status = "release_uncertain"
    if status == "revealed":
        status = "update_uncertain"
    model = store.load_model(model_sha)
    return LoopState(
        base=base,
        observed=observed,
        candidates=candidates,
        vault=base.vault,
        current_model_sha=model_sha,
        pending=pending,
        status=status,
        budget=budget,
        revealed_count=revealed_count,
        current_model=model,
        events=events,
        last_target=last_target,
        last_prediction=last_prediction,
        last_row_id=last_row_id,
        failure=failure,
    )


def _snapshot(project_id: str, manifest: dict, state: LoopState) -> ProjectSnapshot:
    return ProjectSnapshot(
        project_id=project_id,
        status=state.status,
        goal=manifest["goal"],
        threshold=manifest.get("threshold"),
        budget=int(manifest["budget"]),
        remaining_budget=state.budget,
        strategy=manifest["strategy"],
        seed=int(manifest["seed"]),
        revealed_count=state.revealed_count,
        observed_count=len(state.observed.frame),
        candidate_count=len(state.candidates.frame),
        test_count=len(state.base.test.frame),
        current_model_sha=state.current_model_sha,
        initial_model_sha=manifest["initial_model_sha"],
        split_sha256=manifest["split_sha256"],
        source_canonical_sha256=manifest["source_canonical_sha256"],
        observed_row_ids_sha256=_row_ids_sha(state.observed.row_ids),
        test_sha256=_view_sha(state.base.test),
    )


def create_experiment(*, goal: str = "maximize", threshold: float | None = None, budget: int = 3, strategy: str = "random", seed: int = 20261026, store_root: str | Path | None = None, project_id: str | None = None) -> ProjectSnapshot:
    if strategy not in {"random", "greedy_prediction", "max_disagreement"}:
        raise ValueError("unknown strategy")
    if not isinstance(budget, int) or isinstance(budget, bool) or not 1 <= budget <= 20:
        raise ValueError("budget must be an integer in [1, 20]")
    goal_obj = Goal(goal, threshold)
    base, split, p1r_manifest = load_frozen_base()
    predictor = train_regression(base, seed=int(seed), evaluate_test=False)
    initial_model_sha = predictor.manifest.model_sha256
    pid = project_id or f"p2_{uuid.uuid4().hex}"
    root = Path(store_root) if store_root is not None else PROJECT_ROOT / pid
    if root.exists():
        raise FileExistsError(f"project already exists: {root}")
    manifest = {
        "schema": PROJECT_SCHEMA,
        "project_id": pid,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "data_source": {
            "path": "data/nexttest/uci_concrete/canonical/concrete_age28.csv",
            "source_manifest_sha256": _sha(P1R_OUTPUT / "source_manifest.json"),
            "source_canonical_sha256": _sha(P1R_CANONICAL),
            "split_sha256": split["split_sha256"],
            "license": "CC BY 4.0",
            "age_mode": "fixed Age=28",
            "historical_replay": True,
        },
        "split_sha256": split["split_sha256"],
        "source_canonical_sha256": _sha(P1R_CANONICAL),
        "seed": int(seed),
        "goal": goal_obj.direction,
        "threshold": goal_obj.threshold,
        "budget": int(budget),
        "strategy": strategy,
        "initial_model_sha": initial_model_sha,
        "initial_observed_count": len(base.observed.frame),
        "initial_candidate_count": len(base.candidates.frame),
        "test_count": len(base.test.frame),
        "test_sha256": _view_sha(base.test),
        "state": "ready",
    }
    store = ProjectStore.create(root, manifest)
    actual = store.write_model(predictor)
    if actual != initial_model_sha:
        raise DataGateError("initial model SHA changed after persistence")
    return _snapshot(pid, manifest, _state_from_store(store))


def _store_for(project_id: str, store_root: str | Path | None = None) -> ProjectStore:
    root = Path(store_root) if store_root is not None else PROJECT_ROOT / project_id
    if not root.is_dir():
        raise FileNotFoundError(f"project not found: {project_id}")
    return ProjectStore(root)


def get_experiment(project_id: str, store_root: str | Path | None = None) -> ProjectSnapshot:
    store = _store_for(project_id, store_root)
    state = _state_from_store(store)
    return _snapshot(project_id, store.manifest(), state)


def recommend_next(project_id: str, store_root: str | Path | None = None) -> RecommendationView:
    store = _store_for(project_id, store_root)
    state = _state_from_store(store)
    if state.status != "ready":
        raise DataGateError(f"recommendation not allowed in state {state.status}")
    if state.budget <= 0:
        raise DataGateError("budget exhausted")
    if state.candidates.frame.empty:
        raise DataGateError("candidate pool is empty")
    manifest = store.manifest()
    recommendation = recommend(manifest["strategy"], state.candidates, state.current_model, goal=Goal(manifest["goal"], manifest.get("threshold")), seed=int(manifest["seed"]), round_index=state.revealed_count)
    rec_id = f"rec-{len(state.events) + 1:06d}"
    store.append_event("recommendation", {
        "recommendation_id": rec_id,
        "strategy": recommendation.strategy,
        "row_id": recommendation.row_id,
        "prediction": recommendation.prediction,
        "disagreement": recommendation.disagreement,
        "reason": recommendation.reason,
        "model_sha": state.current_model_sha,
        "round_index": state.revealed_count,
        "historical_replay": True,
        "target_hidden": True,
    })
    return RecommendationView(
        project_id=project_id,
        recommendation_id=rec_id,
        status="awaiting_user_confirmation",
        row_id=recommendation.row_id,
        controls=recommendation.controls,
        prediction=recommendation.prediction,
        disagreement=recommendation.disagreement,
        reason=recommendation.reason,
    )


def confirm_and_reveal(project_id: str, recommendation_id: str, store_root: str | Path | None = None) -> FeedbackResult:
    store = _store_for(project_id, store_root)
    state = _state_from_store(store)
    if state.status != "awaiting_user_confirmation" or state.pending is None:
        raise DataGateError(f"cannot confirm in state {state.status}")
    if state.pending.get("recommendation_id") != recommendation_id:
        raise DataGateError("recommendation ID does not match pending recommendation")
    row_id = state.pending["row_id"]
    prediction = float(state.pending["prediction"])
    model_before = state.current_model_sha
    store.append_event("release_requested", {"recommendation_id": recommendation_id, "row_id": row_id, "target_hidden": True})
    try:
        released = state.vault.reveal(row_id)
    except Exception as exc:  # noqa: BLE001
        store.append_event("release_failed", {"recommendation_id": recommendation_id, "row_id": row_id, "error": f"{type(exc).__name__}: {exc}"})
        raise DataGateError("label release failed; no retry") from exc
    target = float(released.target)
    abs_error = abs(prediction - target)
    store.append_event("label_released", {
        "recommendation_id": recommendation_id,
        "row_id": row_id,
        "target": target,
        "prediction": prediction,
        "absolute_error": abs_error,
        "historical_replay": True,
    })
    # Append the revealed row to training and remove it from the candidate pool.
    source_row = state.candidates.frame.loc[state.candidates.frame["_row_id"] == row_id].iloc[0]
    new_row = {"_row_id": row_id}
    for column in state.observed.feature_columns:
        new_row[column] = float(source_row[column])
    new_row[state.observed.target_column] = target
    observed = ObservedTrainingSet(
        frame=pd.concat([state.observed.frame, pd.DataFrame([new_row])], ignore_index=True),
        feature_columns=state.observed.feature_columns,
        target_column=state.observed.target_column,
        row_ids=state.observed.row_ids + (row_id,),
    )
    keep = state.candidates.frame["_row_id"] != row_id
    candidates = _candidate_view(state.candidates.frame.loc[keep], state.candidates.feature_columns, tuple(state.candidates.frame.loc[keep, "_row_id"]))
    try:
        experiment = PreparedExperiment(
            observed=observed,
            candidates=candidates,
            test=state.base.test,
            vault=state.vault,
            schema=state.base.schema,
            audit=state.base.audit,
            split=state.base.split,
        )
        predictor = train_regression(experiment, seed=int(store.manifest()["seed"]), evaluate_test=False)
        model_after = store.write_model(predictor)
    except Exception as exc:  # noqa: BLE001
        store.append_event("update_failed", {"recommendation_id": recommendation_id, "row_id": row_id, "error": f"{type(exc).__name__}: {exc}"})
        raise DataGateError("model update failed; no retry") from exc
    remaining = state.budget - 1
    if remaining <= 0:
        next_state = "budget_exhausted"
    elif candidates.frame.empty:
        next_state = "candidate_pool_empty"
    else:
        next_state = "ready"
    store.append_event("model_updated", {
        "recommendation_id": recommendation_id,
        "row_id": row_id,
        "model_sha": model_after,
        "observed_count": len(observed.frame),
        "candidate_count": len(candidates.frame),
        "remaining_budget": remaining,
        "state": next_state,
        "historical_replay": True,
    })
    return FeedbackResult(
        project_id=project_id,
        recommendation_id=recommendation_id,
        row_id=row_id,
        revealed_target=target,
        prediction=prediction,
        absolute_error=abs_error,
        status=next_state,
        model_sha_before=model_before,
        model_sha_after=model_after,
        remaining_budget=remaining,
        next_available=next_state == "ready",
    )


def inspect_experiment(project_id: str, store_root: str | Path | None = None) -> AuditSummary:
    store = _store_for(project_id, store_root)
    state = _state_from_store(store)
    base, split, _ = load_frozen_base()
    test_ids = set(base.test.row_ids)
    if len(set(state.observed.row_ids)) != len(state.observed.row_ids):
        raise DataGateError("duplicate observed rows")
    if test_ids & set(state.observed.row_ids) or test_ids & set(state.candidates.row_ids):
        raise DataGateError("test rows leaked into observed/candidate sets")
    if len(state.base.test.frame) != len(base.test.frame) or state.base.split.split_sha256 != split["split_sha256"]:
        raise DataGateError("test view changed")
    models_present = all((store.root / "models" / event["payload"].get("model_sha", "")).is_dir() for event in state.events if event["event_type"] == "model_updated")
    models_present = models_present and (store.root / "models" / state.current_model_sha).is_dir()
    return AuditSummary(
        project_id=project_id,
        status=state.status,
        event_count=len(state.events),
        event_chain_sha256=store.event_chain_sha(),
        tree_sha256=store.tree_sha(),
        project_manifest_sha256=_sha(store.manifest_path),
        source_canonical_sha256=_sha(P1R_CANONICAL),
        split_sha256=split["split_sha256"],
        test_sha256=_view_sha(base.test),
        observed_count=len(state.observed.frame),
        candidate_count=len(state.candidates.frame),
        test_count=len(base.test.frame),
        test_unchanged=True,
        models_present=models_present,
    )


def preview_candidates(*, strategy: str, goal: str = "maximize", threshold: float | None = None, project_id: str | None = None) -> dict:
    """Read-only candidate projection. Never returns a target or mutates a project."""
    if strategy not in {"random", "greedy_prediction", "max_disagreement"}:
        raise ValueError("unknown strategy")
    goal_obj = Goal(goal, threshold)
    if project_id is None:
        base, split, _ = load_frozen_base()
        view = base.candidates
        predictor = train_regression(base, seed=20261026, evaluate_test=False)
        current_model_sha = predictor.manifest.model_sha256
        project = None
    else:
        store = _store_for(project_id)
        state = _state_from_store(store)
        if state.status != "ready":
            raise DataGateError(f"candidate preview not allowed in state {state.status}")
        view = state.candidates
        predictor = state.current_model
        current_model_sha = state.current_model_sha
        project = project_id
    prediction = predictor.predict(view.frame)
    estimators = getattr(predictor.model, "estimators_", None)
    std = None
    if estimators:
        matrix = np.asarray([tree.predict(view.frame[list(view.feature_columns)].to_numpy(dtype=float)) for tree in estimators], dtype=float)
        std = matrix.std(axis=0)
    rows = []
    for index, row_id in enumerate(view.row_ids):
        controls = {column: float(view.frame.iloc[index][column]) for column in view.feature_columns}
        rows.append({
            "row_id": row_id,
            "controls": controls,
            "prediction": float(prediction[index]),
            "disagreement": None if std is None else float(std[index]),
        })
    rankings = {}
    for candidate_strategy in ("greedy_prediction", "max_disagreement", "random"):
        rec = recommend(candidate_strategy, view, predictor, goal=goal_obj, seed=20261026, round_index=0)
        rankings[candidate_strategy] = {
            "row_id": rec.row_id, "prediction": rec.prediction,
            "disagreement": rec.disagreement, "reason": rec.reason,
        }
    return {
        "scope": "candidate_pool_no_labels",
        "project_id": project,
        "strategy": strategy,
        "model_sha": current_model_sha,
        "candidate_count": len(rows),
        "rows": rows,
        "rankings": rankings,
        "selected": rankings.get(strategy),
        "goal": goal_obj.direction,
        "threshold": goal_obj.threshold,
    }
