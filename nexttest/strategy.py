"""Three label-blind recommendation baselines for NextTest P2."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

import numpy as np

from .data import CandidatePoolView
from .models import TrainedPredictor

GoalDirection = Literal["maximize", "minimize"]
STRATEGIES = ("random", "greedy_prediction", "max_disagreement")


@dataclass(frozen=True)
class Goal:
    direction: GoalDirection = "maximize"
    threshold: float | None = None

    def __post_init__(self) -> None:
        if self.direction not in ("maximize", "minimize"):
            raise ValueError("direction must be maximize or minimize")
        if self.threshold is not None and not np.isfinite(float(self.threshold)):
            raise ValueError("threshold must be finite")


@dataclass(frozen=True)
class Recommendation:
    row_id: str
    strategy: str
    controls: dict[str, float]
    prediction: float
    disagreement: float | None
    reason: str


def _assert_view(candidates) -> CandidatePoolView:
    if not isinstance(candidates, CandidatePoolView):
        raise TypeError("selector only accepts CandidatePoolView")
    if candidates.frame.empty:
        raise ValueError("candidate pool is empty")
    return candidates


def _assert_predictor(predictor) -> TrainedPredictor:
    if not isinstance(predictor, TrainedPredictor):
        raise TypeError("selector only accepts TrainedPredictor")
    return predictor


def _row_features(view: CandidatePoolView, index: int) -> dict[str, float]:
    row = view.frame.iloc[index]
    return {column: float(row[column]) for column in view.feature_columns}


def _threshold_reason(goal: Goal, prediction: float) -> str:
    if goal.threshold is None:
        return "未设置阈值"
    if goal.direction == "maximize":
        return "达到阈值" if prediction >= goal.threshold else "低于阈值"
    return "低于阈值" if prediction <= goal.threshold else "高于阈值"


def recommend(strategy: str, candidates: CandidatePoolView, predictor: TrainedPredictor, *, goal: Goal, seed: int, round_index: int) -> Recommendation:
    view = _assert_view(candidates)
    model = _assert_predictor(predictor)
    if strategy not in STRATEGIES:
        raise ValueError("unknown strategy")
    ids = list(view.row_ids)
    if len(ids) != len(view.frame):
        raise ValueError("candidate view is inconsistent")
    prediction = model.predict(view.frame)
    if len(prediction) != len(ids):
        raise ValueError("prediction count mismatch")

    if strategy == "random":
        rng = random.Random(int(seed) + int(round_index) * 1000003)
        index = rng.randrange(len(ids))
        reason = "固定种子的均匀随机历史候选"
        disagreement = None
    elif strategy == "greedy_prediction":
        order = sorted(range(len(ids)), key=lambda i: ((-prediction[i] if goal.direction == "maximize" else prediction[i]), ids[i]))
        index = order[0]
        reason = f"贪心预测（{goal.direction}）；{_threshold_reason(goal, float(prediction[index]))}"
        disagreement = None
    else:
        estimators = getattr(model.model, "estimators_", None)
        if not estimators:
            raise ValueError("max_disagreement requires a tree ensemble")
        matrix = np.asarray([tree.predict(view.frame[list(view.feature_columns)].to_numpy(dtype=float)) for tree in estimators], dtype=float)
        if not np.isfinite(matrix).all():
            raise ValueError("tree predictions are non-finite")
        std = matrix.std(axis=0)
        index = sorted(range(len(ids)), key=lambda i: (-std[i], ids[i]))[0]
        disagreement = float(std[index])
        reason = "RandomForest 树间预测标准差；这是模型分歧指标，不是校准概率或置信区间"

    return Recommendation(
        row_id=ids[index],
        strategy=strategy,
        controls=_row_features(view, index),
        prediction=float(prediction[index]),
        disagreement=disagreement,
        reason=reason,
    )


def selector_fixture(candidates: CandidatePoolView) -> int:
    """Minimal type guard used by tests; no labels, vault, or full table."""
    if not isinstance(candidates, CandidatePoolView):
        raise TypeError("selector only accepts CandidatePoolView")
    return len(candidates.row_ids)
