"""CSV auditing, immutable roles, leakage-resistant splits, and label vaults."""

from __future__ import annotations

import csv
import hashlib
import io
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from .schemas import (
    ColumnRole,
    DataAuditResult,
    DatasetSchema,
    ReleaseRecord,
    SplitManifest,
    canonical_json,
    sha256_text,
)


class DataGateError(RuntimeError):
    """Raised when a dataset is not safe to use."""


@dataclass(frozen=True)
class ObservedTrainingSet:
    frame: pd.DataFrame
    feature_columns: tuple[str, ...]
    target_column: str
    row_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.target_column not in self.frame.columns:
            raise ValueError("training target missing")
        if any(c not in self.frame.columns for c in self.feature_columns):
            raise ValueError("training feature missing")
        if "_row_id" not in self.frame.columns:
            raise ValueError("training row IDs missing")


@dataclass(frozen=True)
class CandidatePoolView:
    frame: pd.DataFrame
    feature_columns: tuple[str, ...]
    row_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(c not in self.frame.columns for c in ("_row_id", *self.feature_columns)):
            raise ValueError("candidate view columns invalid")
        if len(self.frame) != len(self.row_ids):
            raise ValueError("candidate row IDs count mismatch")


@dataclass(frozen=True)
class IndependentTestView:
    frame: pd.DataFrame
    feature_columns: tuple[str, ...]
    row_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if "_row_id" not in self.frame.columns:
            raise ValueError("test row IDs missing")
        if len(self.frame) != len(self.row_ids):
            raise ValueError("test row IDs count mismatch")


@dataclass
class HiddenLabelVault:
    """Candidate labels are released once; test labels are evaluation-only."""

    candidate_labels: Mapping[str, float]
    test_labels: Mapping[str, float]
    records: list[ReleaseRecord] = field(default_factory=list)
    _released: set[str] = field(default_factory=set, repr=False)

    def reveal(self, row_id: str) -> ReleaseRecord:
        if not isinstance(row_id, str) or row_id not in self.candidate_labels:
            if row_id in self.test_labels:
                raise PermissionError("test rows are evaluation-only")
            raise KeyError(f"unknown candidate row: {row_id}")
        if row_id in self._released:
            raise ValueError(f"candidate already revealed: {row_id}")
        target = float(self.candidate_labels[row_id])
        self.records.append(ReleaseRecord(row_id=row_id, split="candidate", target=target, status="requested", created_utc=datetime.now(timezone.utc).isoformat()))
        record = ReleaseRecord(row_id=row_id, split="candidate", target=target, status="released", created_utc=datetime.now(timezone.utc).isoformat())
        self._released.add(row_id)
        self.records.append(record)
        return record

    def test_labels_for_evaluation(self) -> dict[str, float]:
        """Only the evaluation module should call this."""
        return dict(self.test_labels)

    def released_records(self) -> tuple[ReleaseRecord, ...]:
        return tuple(self.records)


@dataclass(frozen=True)
class PreparedExperiment:
    observed: ObservedTrainingSet
    candidates: CandidatePoolView
    test: IndependentTestView
    vault: HiddenLabelVault
    schema: DatasetSchema
    audit: DataAuditResult
    split: SplitManifest

    @property
    def train_frame(self) -> pd.DataFrame:
        return self.observed.frame

    @property
    def candidate_inputs(self) -> pd.DataFrame:
        return self.candidates.frame

    @property
    def test_inputs(self) -> pd.DataFrame:
        return self.test.frame


def _read_csv(path: Path) -> tuple[pd.DataFrame, bytes]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataGateError(f"CSV must be UTF-8/UTF-8-SIG: {exc}") from exc
    if not text.strip():
        raise DataGateError("CSV is empty")
    try:
        header = next(csv.reader(io.StringIO(text)))
    except Exception as exc:  # noqa: BLE001
        raise DataGateError(f"CSV header is unreadable: {exc}") from exc
    if len(header) != len(set(header)):
        raise DataGateError("CSV has duplicate column names")
    if "_row_id" in header:
        raise DataGateError("_row_id is reserved and must not be supplied by the caller")
    try:
        frame = pd.read_csv(io.StringIO(text))
    except Exception as exc:  # noqa: BLE001
        raise DataGateError(f"CSV is unreadable: {exc}") from exc
    if frame.empty:
        raise DataGateError("CSV has no data rows")
    return frame, raw


def _schema_role_issues(frame: pd.DataFrame, schema: DatasetSchema) -> list[str]:
    issues = []
    columns = set(map(str, frame.columns))
    for column, role in schema.roles.items():
        if column not in columns:
            issues.append(f"missing required column: {column}")
        if role is ColumnRole.TARGET and column in schema.feature_columns:
            issues.append(f"target leakage: target {column} is a feature")
        if role is ColumnRole.POSTHOC and column in schema.feature_columns:
            issues.append(f"posthoc leakage: posthoc {column} is a feature")
    if len(schema.control_columns) < 2:
        issues.append("at least two control columns are required")
    if schema.target not in schema.roles:
        issues.append("target column is not in schema roles")
    return issues


def _audit_frame(frame: pd.DataFrame, schema: DatasetSchema, input_sha: str) -> DataAuditResult:
    errors: list[str] = []
    warnings: list[str] = []
    role_issues = _schema_role_issues(frame, schema)
    errors.extend(role_issues)
    columns = tuple(map(str, frame.columns))
    missing_counts = {str(k): int(v) for k, v in frame.isna().sum().items()}
    duplicate_rows = int(frame.duplicated().sum())

    numeric_columns = [c for c in schema.roles if c in frame.columns]
    converted = {}
    for column in numeric_columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        bad = int((values.isna() & frame[column].notna()).sum())
        if bad:
            errors.append(f"non-numeric values in {column}: {bad}")
        inf = int(np.isinf(values.to_numpy(dtype=float)).sum())
        if inf:
            errors.append(f"non-finite values in {column}: {inf}")
        converted[column] = values

    for column, count in missing_counts.items():
        if count:
            if column in schema.roles:
                errors.append(f"missing values in {column}: {count}")
            else:
                warnings.append(f"missing values in extra column {column}: {count}")

    control_frame = pd.DataFrame({c: converted[c] for c in schema.control_columns if c in converted})
    duplicate_control_rows = int(control_frame.duplicated().sum()) if not control_frame.empty else 0
    constant_columns = tuple(c for c in schema.feature_columns if c in frame and frame[c].nunique(dropna=False) <= 1)
    if constant_columns:
        warnings.append("constant feature columns: " + ", ".join(constant_columns))

    outlier_counts = {}
    for column in numeric_columns:
        values = converted[column].dropna()
        if len(values) >= 8:
            q1, q3 = values.quantile([0.25, 0.75])
            iqr = float(q3 - q1)
            if iqr > 0:
                count = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum())
                if count:
                    outlier_counts[column] = count

    if duplicate_rows:
        warnings.append(f"exact duplicate rows: {duplicate_rows}")
    if duplicate_control_rows:
        warnings.append(f"duplicate control recipes: {duplicate_control_rows}")
    if schema.target in frame and frame[schema.target].nunique(dropna=False) <= 1:
        errors.append("target has no variation")
    if schema.target in frame and len(frame) < 4:
        errors.append("at least four rows are required for training")

    extra = sorted(set(columns) - set(schema.roles))
    if extra:
        warnings.append("extra columns not in schema: " + ", ".join(extra))

    return DataAuditResult(
        input_sha256=input_sha,
        schema_sha256=schema.schema_sha256,
        row_count=int(len(frame)),
        columns=columns,
        missing_counts=missing_counts,
        duplicate_rows=duplicate_rows,
        duplicate_feature_rows=duplicate_control_rows,
        constant_columns=constant_columns,
        outlier_counts=outlier_counts,
        role_issues=tuple(role_issues),
        errors=tuple(errors),
        warnings=tuple(warnings),
        passed=not errors,
    )


def audit_csv(path: str | Path, schema: DatasetSchema) -> DataAuditResult:
    path = Path(path)
    if not path.is_file():
        raise DataGateError(f"CSV not found: {path}")
    frame, raw = _read_csv(path)
    return _audit_frame(frame, schema, hashlib.sha256(raw).hexdigest())


def _row_ids(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.insert(0, "_row_id", [f"row-{i:06d}" for i in range(len(out))])
    return out


def _group_ids(frame: pd.DataFrame, group_columns: tuple[str, ...]) -> pd.Series:
    signatures = []
    for row in frame[list(group_columns)].itertuples(index=False, name=None):
        signatures.append(sha256_text(canonical_json([float(v) for v in row]))[:20])
    return pd.Series(signatures, index=frame.index, name="_group_id")


def prepare_dataset(path: str | Path, schema: DatasetSchema, *, seed: int = 20261026) -> PreparedExperiment:
    path = Path(path)
    audit = audit_csv(path, schema)
    if not audit.passed:
        raise DataGateError("CSV audit failed: " + "; ".join(audit.errors))
    frame, raw = _read_csv(path)
    frame = _row_ids(frame)
    for column in schema.feature_columns + (schema.target,):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["_group_id"] = _group_ids(frame, schema.control_columns)

    groups = sorted(frame["_group_id"].unique().tolist())
    if len(groups) < 3:
        raise DataGateError("at least three distinct control-recipe groups are required")
    rng = random.Random(int(seed))
    rng.shuffle(groups)
    n = len(groups)
    n_train = max(1, int(round(n * 0.6)))
    n_candidate = max(1, int(round(n * 0.2)))
    if n_train + n_candidate >= n:
        n_train = n - 2
        n_candidate = 1
    train_groups = set(groups[:n_train])
    candidate_groups = set(groups[n_train:n_train + n_candidate])
    test_groups = set(groups[n_train + n_candidate:])
    if not (train_groups and candidate_groups and test_groups):
        raise DataGateError("could not form non-empty train/candidate/test splits")

    train_ids = tuple(frame.loc[frame["_group_id"].isin(train_groups), "_row_id"])
    candidate_ids = tuple(frame.loc[frame["_group_id"].isin(candidate_groups), "_row_id"])
    test_ids = tuple(frame.loc[frame["_group_id"].isin(test_groups), "_row_id"])
    split_payload = {
        "seed": int(seed),
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "schema_sha256": schema.schema_sha256,
        "train": list(train_ids),
        "candidate": list(candidate_ids),
        "test": list(test_ids),
        "groups": len(groups),
    }
    split = SplitManifest(
        seed=int(seed),
        input_sha256=split_payload["input_sha256"],
        schema_sha256=schema.schema_sha256,
        train_row_ids=train_ids,
        candidate_row_ids=candidate_ids,
        test_row_ids=test_ids,
        group_count=len(groups),
        split_sha256=sha256_text(canonical_json(split_payload)),
    )

    feature_columns = schema.feature_columns
    target = schema.target
    observed_frame = frame.loc[frame["_row_id"].isin(train_ids), ["_row_id", *feature_columns, target]].reset_index(drop=True)
    candidate_frame = frame.loc[frame["_row_id"].isin(candidate_ids), ["_row_id", *feature_columns]].reset_index(drop=True)
    test_frame = frame.loc[frame["_row_id"].isin(test_ids), ["_row_id", *feature_columns]].reset_index(drop=True)
    indexed = frame.set_index("_row_id")
    candidate_labels = {row_id: float(indexed.loc[row_id, target]) for row_id in candidate_ids}
    test_labels = {row_id: float(indexed.loc[row_id, target]) for row_id in test_ids}

    observed = ObservedTrainingSet(
        frame=observed_frame,
        feature_columns=feature_columns,
        target_column=target,
        row_ids=train_ids,
    )
    candidates = CandidatePoolView(frame=candidate_frame, feature_columns=feature_columns, row_ids=candidate_ids)
    test = IndependentTestView(frame=test_frame, feature_columns=feature_columns, row_ids=test_ids)
    vault = HiddenLabelVault(candidate_labels=candidate_labels, test_labels=test_labels)
    return PreparedExperiment(
        observed=observed,
        candidates=candidates,
        test=test,
        vault=vault,
        schema=schema,
        audit=audit,
        split=split,
    )
