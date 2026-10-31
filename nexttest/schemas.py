"""Frozen, JSON-serializable schemas for the NextTest P1 core.

No model, UI, network, or DiscPilot evidence is imported here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class ColumnRole(str, Enum):
    CONTROL = "control"
    CONTEXT = "context"
    TARGET = "target"
    POSTHOC = "posthoc"
    IGNORED = "ignored"


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DatasetSchema:
    """Roles are exclusive; features are only control + context."""

    roles: Mapping[str, ColumnRole]
    target: str
    name: str = ""

    def __post_init__(self) -> None:
        normalized = {str(k): ColumnRole(v) for k, v in self.roles.items()}
        object.__setattr__(self, "roles", MappingProxyType(normalized))
        if self.target not in normalized or normalized[self.target] is not ColumnRole.TARGET:
            raise ValueError("target must be the unique role=target column")
        if sum(1 for role in normalized.values() if role is ColumnRole.TARGET) != 1:
            raise ValueError("exactly one target column is required")
        if len(self.control_columns) < 2:
            raise ValueError("at least two control columns are required")

    @property
    def control_columns(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.roles.items() if v is ColumnRole.CONTROL)

    @property
    def context_columns(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.roles.items() if v is ColumnRole.CONTEXT)

    @property
    def posthoc_columns(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.roles.items() if v is ColumnRole.POSTHOC)

    @property
    def ignored_columns(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.roles.items() if v is ColumnRole.IGNORED)

    @property
    def feature_columns(self) -> tuple[str, ...]:
        return self.control_columns + self.context_columns

    def to_dict(self) -> dict:
        return {
            "schema_version": "nexttest_p1_dataset_schema_v1",
            "name": self.name,
            "target": self.target,
            "roles": {k: v.value for k, v in self.roles.items()},
            "control_columns": list(self.control_columns),
            "context_columns": list(self.context_columns),
            "posthoc_columns": list(self.posthoc_columns),
            "ignored_columns": list(self.ignored_columns),
            "feature_columns": list(self.feature_columns),
        }

    @property
    def schema_sha256(self) -> str:
        return sha256_text(canonical_json(self.to_dict()))


@dataclass(frozen=True)
class DataAuditResult:
    input_sha256: str
    schema_sha256: str
    row_count: int
    columns: tuple[str, ...]
    missing_counts: Mapping[str, int]
    duplicate_rows: int
    duplicate_feature_rows: int
    constant_columns: tuple[str, ...]
    outlier_counts: Mapping[str, int]
    role_issues: tuple[str, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict:
        return {
            "audit_version": "nexttest_p1_data_audit_v1",
            "input_sha256": self.input_sha256,
            "schema_sha256": self.schema_sha256,
            "row_count": self.row_count,
            "columns": list(self.columns),
            "missing_counts": dict(self.missing_counts),
            "duplicate_rows": self.duplicate_rows,
            "duplicate_feature_rows": self.duplicate_feature_rows,
            "constant_columns": list(self.constant_columns),
            "outlier_counts": dict(self.outlier_counts),
            "role_issues": list(self.role_issues),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "passed": self.passed,
        }


@dataclass(frozen=True)
class SplitManifest:
    seed: int
    input_sha256: str
    schema_sha256: str
    train_row_ids: tuple[str, ...]
    candidate_row_ids: tuple[str, ...]
    test_row_ids: tuple[str, ...]
    group_count: int
    split_sha256: str

    def to_dict(self) -> dict:
        return {
            "split_version": "nexttest_p1_split_v1",
            "seed": self.seed,
            "input_sha256": self.input_sha256,
            "schema_sha256": self.schema_sha256,
            "train_row_ids": list(self.train_row_ids),
            "candidate_row_ids": list(self.candidate_row_ids),
            "test_row_ids": list(self.test_row_ids),
            "counts": {
                "train": len(self.train_row_ids),
                "candidate": len(self.candidate_row_ids),
                "test": len(self.test_row_ids),
            },
            "group_count": self.group_count,
            "split_sha256": self.split_sha256,
        }


@dataclass(frozen=True)
class RegressionMetrics:
    mae: float
    rmse: float
    n_train: int
    n_test: int
    target_mean_test: float

    def __post_init__(self) -> None:
        for name in ("mae", "rmse", "target_mean_test"):
            value = float(getattr(self, name))
            if value != value or value in (float("inf"), float("-inf")):
                raise ValueError(f"{name} must be finite")

    def to_dict(self) -> dict:
        return {
            "metrics_version": "nexttest_p1_regression_metrics_v1",
            "mae": self.mae,
            "rmse": self.rmse,
            "n_train": self.n_train,
            "n_test": self.n_test,
            "target_mean_test": self.target_mean_test,
        }


@dataclass(frozen=True)
class ModelArtifactManifest:
    model_family: str
    model_params: Mapping[str, object]
    seed: int
    feature_names: tuple[str, ...]
    target: str
    train_rows: int
    model_sha256: str
    schema_sha256: str
    input_sha256: str
    metrics: RegressionMetrics
    artifact_path: str
    created_utc: str
    non_real_demo: bool

    def to_dict(self) -> dict:
        return {
            "model_manifest_version": "nexttest_p1_model_manifest_v1",
            "model_family": self.model_family,
            "model_params": dict(self.model_params),
            "seed": self.seed,
            "feature_names": list(self.feature_names),
            "target": self.target,
            "train_rows": self.train_rows,
            "model_sha256": self.model_sha256,
            "schema_sha256": self.schema_sha256,
            "input_sha256": self.input_sha256,
            "metrics": self.metrics.to_dict(),
            "artifact_path": self.artifact_path,
            "created_utc": self.created_utc,
            "non_real_demo": self.non_real_demo,
        }


@dataclass(frozen=True)
class ReleaseRecord:
    row_id: str
    split: str
    target: float
    status: str
    created_utc: str

    def to_dict(self) -> dict:
        return {
            "release_version": "nexttest_p1r_release_v1",
            "row_id": self.row_id,
            "split": self.split,
            "target": self.target,
            "status": self.status,
            "created_utc": self.created_utc,
        }
