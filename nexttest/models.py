"""Lightweight CPU regression adapter for NextTest P1.

Only scikit-learn / pandas / numpy are used. No torch, GPU, network, or UI.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from .data import PreparedExperiment
from .schemas import ModelArtifactManifest, RegressionMetrics, canonical_json


@dataclass
class TrainedPredictor:
    model: RandomForestRegressor
    manifest: ModelArtifactManifest
    feature_columns: tuple[str, ...]

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        missing = [c for c in self.feature_columns if c not in frame.columns]
        if missing:
            raise ValueError(f"missing feature columns: {missing}")
        values = frame[list(self.feature_columns)].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("prediction features must be finite")
        prediction = np.asarray(self.model.predict(values), dtype=float)
        if prediction.ndim != 1 or not np.isfinite(prediction).all():
            raise ValueError("model produced invalid predictions")
        return prediction


def train_regression(prepared: PreparedExperiment, *, seed: int = 20261026, non_real_demo: bool = False, evaluate_test: bool = True) -> TrainedPredictor:
    train = prepared.observed.frame
    x = train[list(prepared.observed.feature_columns)].to_numpy(dtype=float)
    y = train[prepared.observed.target_column].to_numpy(dtype=float)
    if len(x) < 4:
        raise ValueError("at least four training rows are required")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("training data must be finite")
    model = RandomForestRegressor(
        n_estimators=120,
        max_depth=8,
        min_samples_leaf=2,
        random_state=int(seed),
        n_jobs=1,
    )
    model.fit(x, y)
    if evaluate_test:
        metrics = evaluate_regression_model(model, prepared)
    else:
        train_prediction = np.asarray(model.predict(x), dtype=float)
        if not np.isfinite(train_prediction).all():
            raise ValueError("model produced non-finite training predictions")
        metrics = RegressionMetrics(
            mae=float(np.mean(np.abs(train_prediction - y))),
            rmse=float(np.sqrt(np.mean((train_prediction - y) ** 2))),
            n_train=int(len(y)),
            n_test=0,
            target_mean_test=float(np.mean(y)),
        )
    model_bytes = pickle.dumps(model, protocol=5)
    model_sha = hashlib.sha256(model_bytes).hexdigest()
    manifest = ModelArtifactManifest(
        model_family="RandomForestRegressor",
        model_params={
            "n_estimators": 120,
            "max_depth": 8,
            "min_samples_leaf": 2,
            "random_state": int(seed),
            "n_jobs": 1,
        },
        seed=int(seed),
        feature_names=prepared.observed.feature_columns,
        target=prepared.observed.target_column,
        train_rows=int(len(train)),
        model_sha256=model_sha,
        schema_sha256=prepared.schema.schema_sha256,
        input_sha256=prepared.audit.input_sha256,
        metrics=metrics,
        artifact_path="model.pkl",
        created_utc=datetime.now(timezone.utc).isoformat(),
        non_real_demo=bool(non_real_demo),
    )
    return TrainedPredictor(model=model, manifest=manifest, feature_columns=prepared.observed.feature_columns)


def _aligned_test(prepared: PreparedExperiment) -> tuple[pd.DataFrame, np.ndarray]:
    inputs = prepared.test.frame
    labels = prepared.vault.test_labels_for_evaluation()
    if set(inputs["_row_id"]) != set(labels):
        raise ValueError("test labels do not match test view")
    truth = np.asarray([labels[row_id] for row_id in inputs["_row_id"]], dtype=float)
    if not np.isfinite(truth).all():
        raise ValueError("test labels are incomplete")
    return inputs, truth


def evaluate_regression_model(model: RandomForestRegressor, prepared: PreparedExperiment) -> RegressionMetrics:
    inputs, truth = _aligned_test(prepared)
    prediction = np.asarray(model.predict(inputs[list(prepared.observed.feature_columns)].to_numpy(dtype=float)), dtype=float)
    if not np.isfinite(prediction).all():
        raise ValueError("model produced non-finite predictions")
    residual = prediction - truth
    mae = float(np.mean(np.abs(residual)))
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    return RegressionMetrics(
        mae=mae,
        rmse=rmse,
        n_train=int(len(prepared.observed.frame)),
        n_test=int(len(truth)),
        target_mean_test=float(np.mean(truth)),
    )


def evaluate_regression(predictor: TrainedPredictor, prepared: PreparedExperiment) -> RegressionMetrics:
    return evaluate_regression_model(predictor.model, prepared)


def save_predictor(predictor: TrainedPredictor, path: str | Path) -> dict:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    model_path = path / "model.pkl"
    manifest_path = path / "model_manifest.json"
    if model_path.exists() or manifest_path.exists():
        raise FileExistsError("model artifact already exists")
    model_bytes = pickle.dumps(predictor.model, protocol=5)
    fd = os.open(model_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(model_bytes)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    manifest = predictor.manifest.to_dict()
    manifest["model_sha256"] = hashlib.sha256(model_bytes).hexdigest()
    manifest["artifact_path"] = str(model_path.name)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def load_predictor(path: str | Path) -> TrainedPredictor:
    path = Path(path)
    model_path = path / "model.pkl"
    manifest_path = path / "model_manifest.json"
    if not model_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("model artifact is incomplete")
    model_bytes = model_path.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("model_sha256") != hashlib.sha256(model_bytes).hexdigest():
        raise ValueError("model SHA mismatch")
    model = pickle.loads(model_bytes)
    if not isinstance(model, RandomForestRegressor):
        raise ValueError("unsupported model artifact")
    m = manifest["metrics"]
    metrics = RegressionMetrics(mae=float(m["mae"]), rmse=float(m["rmse"]), n_train=int(m["n_train"]), n_test=int(m["n_test"]), target_mean_test=float(m["target_mean_test"]))
    restored_manifest = ModelArtifactManifest(
        model_family=manifest["model_family"],
        model_params=manifest["model_params"],
        seed=manifest["seed"],
        feature_names=tuple(manifest["feature_names"]),
        target=manifest["target"],
        train_rows=manifest["train_rows"],
        model_sha256=manifest["model_sha256"],
        schema_sha256=manifest["schema_sha256"],
        input_sha256=manifest["input_sha256"],
        metrics=metrics,
        artifact_path=manifest["artifact_path"],
        created_utc=manifest["created_utc"],
        non_real_demo=bool(manifest["non_real_demo"]),
    )
    return TrainedPredictor(model=model, manifest=restored_manifest, feature_columns=tuple(manifest["feature_names"]))
