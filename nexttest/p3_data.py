"""P3 Data Dock: local CSV intake, roles, safety gate, and immutable dataset packages."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .data import (
    CandidatePoolView,
    DataGateError,
    HiddenLabelVault,
    IndependentTestView,
    ObservedTrainingSet,
    PreparedExperiment,
)
from .schemas import ColumnRole, DataAuditResult, DatasetSchema, SplitManifest, canonical_json, sha256_text

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
INTAKE_ROOT = RUNS / "nexttest_intakes"
DATASET_ROOT = RUNS / "nexttest_datasets"
PROJECT_ROOT = RUNS / "nexttest_projects"
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 20_000
MAX_COLUMNS = 64
FIXED_SEED = 20261026
INTAKE_ID = re.compile(r"^intake_[0-9a-f]{32}$")
DATASET_ID = re.compile(r"^dataset_[0-9a-f]{32}$")
PROJECT_ID = re.compile(r"^p3_[0-9a-f]{32}$")
ROLE_NAMES = {role.value for role in ColumnRole}
ID_LIKE = re.compile(r"(^|_)(id|uuid|key|index|row|record)(_|$)", re.IGNORECASE)
RESULT_WORDS = re.compile(r"(result|outcome|after|final|post)", re.IGNORECASE)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


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


def _canonical_file(path: Path, value: dict) -> None:
    _write_new(path, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))


def _replace_file(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _validate_id(value: str, pattern: re.Pattern, label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise DataGateError(f"invalid {label} ID")
    return value


def _tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _parse_csv(raw: bytes, filename: str, content_type: str = "text/csv") -> pd.DataFrame:
    if not isinstance(filename, str) or not filename or Path(filename).name != filename or len(filename) > 120 or not filename.lower().endswith(".csv"):
        raise DataGateError("filename must be a single .csv filename")
    if content_type not in {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel"}:
        raise DataGateError("unsupported content type")
    if not raw:
        raise DataGateError("CSV is empty")
    if len(raw) > MAX_BYTES:
        raise DataGateError("CSV exceeds 10 MiB limit")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataGateError("CSV must be UTF-8 or UTF-8-SIG") from exc
    if not text.strip():
        raise DataGateError("CSV is empty")
    try:
        reader = csv.reader(io.StringIO(text))
        header = next(reader)
    except Exception as exc:  # noqa: BLE001
        raise DataGateError("CSV header is unreadable") from exc
    if not header or any(not str(c).strip() for c in header):
        raise DataGateError("CSV columns must be non-empty")
    if len(header) != len(set(header)):
        raise DataGateError("CSV has duplicate column names")
    if "_row_id" in header:
        raise DataGateError("_row_id is reserved")
    if len(header) > MAX_COLUMNS:
        raise DataGateError(f"CSV has more than {MAX_COLUMNS} columns")
    try:
        frame = pd.read_csv(io.StringIO(text))
    except Exception as exc:  # noqa: BLE001
        raise DataGateError("CSV is unreadable") from exc
    if frame.empty:
        raise DataGateError("CSV has no data rows")
    if len(frame) > MAX_ROWS:
        raise DataGateError(f"CSV has more than {MAX_ROWS} rows")
    return frame


def _safe_value(value):
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
        return value if np.isfinite(value) else None
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return str(value)


def _columns_meta(frame: pd.DataFrame) -> list[dict]:
    out = []
    for column in frame.columns:
        series = frame[column]
        numeric = pd.to_numeric(series, errors="coerce")
        valid_numeric = int(numeric.notna().sum())
        non_missing = int(series.notna().sum())
        out.append({
            "name": str(column),
            "missing": int(series.isna().sum()),
            "unique": int(series.nunique(dropna=True)),
            "numeric": bool(non_missing > 0 and valid_numeric == non_missing),
        })
    return out


def _preview(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for record in frame.head(8).to_dict(orient="records"):
        rows.append({str(k): _safe_value(v) for k, v in record.items()})
    return rows


def _intake_path(intake_id: str) -> Path:
    _validate_id(intake_id, INTAKE_ID, "intake")
    return INTAKE_ROOT / intake_id


def intake_create(raw: bytes, *, filename: str, content_type: str = "text/csv", intake_id: str | None = None) -> dict:
    frame = _parse_csv(raw, filename, content_type)
    intake_id = intake_id or f"intake_{uuid.uuid4().hex}"
    _validate_id(intake_id, INTAKE_ID, "intake")
    root = _intake_path(intake_id)
    root.mkdir(parents=True, exist_ok=False)
    _write_new(root / "raw.csv", raw)
    manifest = {
        "schema": "nexttest_p3_intake_v1",
        "intake_id": intake_id,
        "filename": filename,
        "content_type": content_type,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "encoding": "UTF-8",
        "input_sha256": _sha(raw),
        "bytes": len(raw),
        "rows": len(frame),
        "columns": list(map(str, frame.columns)),
        "column_meta": _columns_meta(frame),
        "preview": _preview(frame),
        "schema_assigned": False,
        "gate": None,
        "acknowledged": False,
    }
    _canonical_file(root / "intake_manifest.json", manifest)
    return {"intake": manifest, "raw_sha256": manifest["input_sha256"]}


def _load_intake(intake_id: str) -> tuple[Path, dict, pd.DataFrame]:
    root = _intake_path(intake_id)
    if not root.is_dir():
        raise DataGateError("intake not found")
    manifest = json.loads((root / "intake_manifest.json").read_text(encoding="utf-8"))
    raw = (root / "raw.csv").read_bytes()
    if manifest.get("input_sha256") != _sha(raw):
        raise DataGateError("intake raw SHA mismatch")
    frame = _parse_csv(raw, manifest["filename"], manifest["content_type"])
    if len(frame) != manifest["rows"] or list(map(str, frame.columns)) != manifest["columns"]:
        raise DataGateError("intake shape mismatch")
    return root, manifest, frame


def intake_inspect(intake_id: str) -> dict:
    root, manifest, _ = _load_intake(intake_id)
    schema = None
    if (root / "schema.json").is_file() or list(root.glob("schema_*.json")):
        schema = _current_schema(root, manifest)
    gate = None
    if (root / "gate.json").is_file():
        gate = json.loads((root / "gate.json").read_text(encoding="utf-8"))
    ack = None
    if (root / "acknowledgements.json").is_file():
        ack = json.loads((root / "acknowledgements.json").read_text(encoding="utf-8"))
    return {"intake": manifest, "schema": schema, "gate": gate, "acknowledgements": ack, "tree_sha256": _tree_sha(root)}


def _schema_payload(root: Path, manifest: dict, roles: dict[str, str], display_names: dict[str, str], units: dict[str, str], dataset_name: str) -> dict:
    columns = set(manifest["columns"])
    if set(roles) != columns:
        raise DataGateError("every CSV column must have exactly one role")
    if any(role not in ROLE_NAMES for role in roles.values()):
        raise DataGateError("unknown role")
    if sum(1 for role in roles.values() if role == "target") != 1:
        raise DataGateError("exactly one target is required")
    if sum(1 for role in roles.values() if role == "control") < 2:
        raise DataGateError("at least two controls are required")
    meta = {item["name"]: item for item in manifest["column_meta"]}
    for column, role in roles.items():
        if role in {"control", "context", "target"} and not meta[column]["numeric"]:
            raise DataGateError(f"{column} must be numeric for role {role}")
    display = {column: str(display_names.get(column, column))[:80] or column for column in columns}
    unit = {column: str(units.get(column, ""))[:40] for column in columns}
    name = str(dataset_name or Path(manifest["filename"]).stem)[:100]
    payload = {
        "schema_version": "nexttest_p3_dataset_schema_v1",
        "dataset_name": name,
        "target": next(column for column, role in roles.items() if role == "target"),
        "roles": {column: roles[column] for column in manifest["columns"]},
        "display_names": display,
        "units": unit,
        "unit_not_verified": True,
    }
    payload["schema_sha256"] = sha256_text(canonical_json(payload))
    return payload


def intake_assign_schema(intake_id: str, *, roles: dict[str, str], display_names: dict[str, str], units: dict[str, str], dataset_name: str) -> dict:
    root, manifest, _ = _load_intake(intake_id)
    if (root / "frozen.json").is_file():
        raise DataGateError("intake is frozen; create a new intake to change roles")
    payload = _schema_payload(root, manifest, roles, display_names, units, dataset_name)
    _write_new(root / f"schema_{payload['schema_sha256']}.json", (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    _replace_file(root / "schema.json", payload)
    # A schema change invalidates any previous gate and acknowledgement.
    for name in ("gate.json", "acknowledgements.json"):
        path = root / name
        if path.is_file():
            path.unlink()
    return {"schema": payload, "tree_sha256": _tree_sha(root)}


def _current_schema(root: Path, manifest: dict) -> dict:
    current = root / "schema.json"
    files = [current] if current.is_file() else sorted(root.glob("schema_*.json"))
    if not files:
        raise DataGateError("schema has not been assigned")
    payload = json.loads(files[-1].read_text(encoding="utf-8"))
    if payload.get("schema_sha256") != sha256_text(canonical_json({k: v for k, v in payload.items() if k != "schema_sha256"})):
        raise DataGateError("schema SHA mismatch")
    if set(payload["roles"]) != set(manifest["columns"]):
        raise DataGateError("schema columns changed")
    return payload


def _schema_object(payload: dict) -> DatasetSchema:
    return DatasetSchema(
        roles={column: ColumnRole(role) for column, role in payload["roles"].items()},
        target=payload["target"],
        name=payload["dataset_name"],
    )


def _split_frame(frame: pd.DataFrame, schema: DatasetSchema, input_sha: str, seed: int = FIXED_SEED):
    work = frame.copy()
    work.insert(0, "_row_id", [f"row-{i:06d}" for i in range(len(work))])
    for column in schema.feature_columns + (schema.target,):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work["_group_id"] = [sha256_text(canonical_json([float(v) for v in row]))[:20] for row in work[list(schema.control_columns)].itertuples(index=False, name=None)]
    groups = sorted(work["_group_id"].unique().tolist())
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
    train_ids = tuple(work.loc[work["_group_id"].isin(train_groups), "_row_id"])
    candidate_ids = tuple(work.loc[work["_group_id"].isin(candidate_groups), "_row_id"])
    test_ids = tuple(work.loc[work["_group_id"].isin(test_groups), "_row_id"])
    split_payload = {
        "seed": int(seed), "input_sha256": input_sha, "schema_sha256": schema.schema_sha256,
        "train": list(train_ids), "candidate": list(candidate_ids), "test": list(test_ids),
        "groups": len(groups),
    }
    split = SplitManifest(
        seed=int(seed), input_sha256=input_sha, schema_sha256=schema.schema_sha256,
        train_row_ids=train_ids, candidate_row_ids=candidate_ids, test_row_ids=test_ids,
        group_count=len(groups), split_sha256=sha256_text(canonical_json(split_payload)),
    )
    return work, split


def _gate_payload(root: Path, manifest: dict, schema_payload: dict, frame: pd.DataFrame) -> dict:
    schema = _schema_object(schema_payload)
    errors: list[dict] = []
    warnings: list[dict] = []
    facts: list[str] = []
    missing = {str(k): int(v) for k, v in frame.isna().sum().items()}
    columns_meta = {item["name"]: item for item in manifest["column_meta"]}
    for column in (*schema.feature_columns, schema.target):
        if column not in frame.columns:
            errors.append({"code": "missing_column", "column": column, "message": f"缺少列 {column}"})
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        bad = int((values.isna() & frame[column].notna()).sum())
        if bad or missing.get(column, 0) or int(np.isinf(values.to_numpy(dtype=float)).sum()):
            errors.append({"code": "non_numeric_or_missing", "column": column, "message": f"{column} 必须全部为有限数值（非数值/缺失/Inf 不允许）。"})
    target_values = pd.to_numeric(frame[schema.target], errors="coerce") if schema.target in frame else pd.Series(dtype=float)
    if target_values.nunique(dropna=True) <= 1:
        errors.append({"code": "constant_target", "column": schema.target, "message": "target 没有变化，无法回归。"})
    if len(frame) < 4:
        errors.append({"code": "too_few_rows", "message": "至少需要 4 行数据。"})
    if len(schema.control_columns) < 2:
        errors.append({"code": "too_few_controls", "message": "至少需要 2 个 control 列。"})
    if schema.target in schema.feature_columns:
        errors.append({"code": "target_in_features", "column": schema.target, "message": "target 不能作为 feature。"})
    if set(schema.posthoc_columns) & set(schema.feature_columns):
        errors.append({"code": "posthoc_in_features", "message": "post-hoc 列不能进入 feature。"})
    groups = None
    try:
        _, split = _split_frame(frame, schema, manifest["input_sha256"])
        groups = split.group_count
        facts.append(f"恰好一个 target：{schema.target}")
        facts.append(f"feature 全部为有限数值：{len(schema.feature_columns)} 列")
        facts.append("post-hoc 未进入 feature")
        facts.append(f"control recipe 分组：{groups} 组，可形成三段非空切分")
        facts.append(f"拟议切分：{len(split.train_row_ids)} / {len(split.candidate_row_ids)} / {len(split.test_row_ids)}")
        facts.append(f"input SHA：{manifest['input_sha256']}")
        facts.append(f"schema SHA：{schema_payload['schema_sha256']}")
    except DataGateError as exc:
        errors.append({"code": "split_not_possible", "message": str(exc)})
        split = None
    # Heuristics are warnings, never proof of leakage.
    duplicate_rows = int(frame.duplicated().sum())
    if duplicate_rows:
        warnings.append({"id": "duplicate_rows", "title": "存在完全重复行", "message": f"检测到 {duplicate_rows} 行完全重复；需要人工判断是否重复记录。", "columns": []})
    control_frame = frame[list(schema.control_columns)] if all(c in frame for c in schema.control_columns) else pd.DataFrame()
    duplicate_recipes = int(control_frame.duplicated().sum()) if not control_frame.empty else 0
    if duplicate_recipes:
        warnings.append({"id": "duplicate_recipes", "title": "存在重复 control 配方", "message": f"检测到 {duplicate_recipes} 行重复 control 配方；它们会被固定分到同一组。", "columns": list(schema.control_columns)})
    for column in schema.feature_columns:
        if column in frame and frame[column].nunique(dropna=False) <= 1:
            warnings.append({"id": f"constant:{column}", "title": f"{column} 是常量", "message": f"{column} 只有一个取值，作为 feature 可能没有信息。", "columns": [column]})
    for column in schema.feature_columns:
        if column not in frame: continue
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if len(values) >= 8:
            q1, q3 = values.quantile([0.25, 0.75]); iqr = float(q3 - q1)
            if iqr > 0:
                count = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum())
                if count:
                    warnings.append({"id": f"outlier:{column}", "title": f"{column} 有 IQR 异常值", "message": f"检测到 {count} 个 IQR 异常值；异常不等于错误。", "columns": [column]})
    if len(frame) < 30:
        warnings.append({"id": "low_rows", "title": "行数较少", "message": f"只有 {len(frame)} 行；模型和评估会不稳定。", "columns": []})
    if groups is not None and groups < 10:
        warnings.append({"id": "low_groups", "title": "分组较少", "message": f"只有 {groups} 个 control recipe 组；切分和评估会不稳定。", "columns": []})
    for column in schema.feature_columns:
        if column not in frame or not target_values.notna().any(): continue
        values = pd.to_numeric(frame[column], errors="coerce")
        try:
            corr = float(values.corr(target_values))
        except Exception:
            corr = float("nan")
        if np.isfinite(corr) and abs(corr) >= 0.98:
            warnings.append({"id": f"near_perfect_correlation:{column}", "title": f"{column} 与 target 相关性接近 1", "message": f"Pearson |r|={abs(corr):.3f}，接近 1；这是启发式提示，不是泄漏证明。", "columns": [column]})
    for column in schema.feature_columns + schema.posthoc_columns:
        if column not in frame: continue
        valid = int(pd.to_numeric(frame[column], errors="coerce").notna().sum())
        ratio = valid / max(len(frame), 1)
        if ratio >= 0.98 and ID_LIKE.search(column):
            warnings.append({"id": f"id_like:{column}", "title": f"{column} 看起来像 ID", "message": "名称和唯一率提示它可能是标识列；本工具不自动判定泄漏。", "columns": [column]})
        if RESULT_WORDS.search(column):
            warnings.append({"id": f"result_word:{column}", "title": f"{column} 名称含结果词", "message": "列名像结果/事后信息；请确认它不会进入 feature。", "columns": [column]})
    status = "BLOCKED" if errors else "WARNING" if warnings else "PASSED"
    payload = {
        "gate_version": "nexttest_p3_gate_v1", "status": status,
        "input_sha256": manifest["input_sha256"], "schema_sha256": schema_payload["schema_sha256"],
        "errors": errors, "warnings": warnings, "facts": facts,
        "split_counts": {"train": len(split.train_row_ids), "candidate": len(split.candidate_row_ids), "test": len(split.test_row_ids)} if split else None,
        "gate_sha256": sha256_text(canonical_json({"input": manifest["input_sha256"], "schema": schema_payload["schema_sha256"], "status": status, "errors": errors, "warnings": warnings, "facts": facts})),
    }
    return payload


def intake_gate(intake_id: str) -> dict:
    root, manifest, frame = _load_intake(intake_id)
    schema_payload = _current_schema(root, manifest)
    payload = _gate_payload(root, manifest, schema_payload, frame)
    gate_path = root / "gate.json"
    if gate_path.exists():
        gate_path.unlink()
    _write_new(gate_path, (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    return dict(payload)


def intake_acknowledge(intake_id: str, warning_ids: list[str]) -> dict:
    root, manifest, _ = _load_intake(intake_id)
    gate = json.loads((root / "gate.json").read_text(encoding="utf-8"))
    if gate["status"] == "BLOCKED":
        raise DataGateError("blocked gate cannot be acknowledged")
    valid = {item["id"] for item in gate["warnings"]}
    requested = set(warning_ids)
    if not requested <= valid or len(requested) != len(warning_ids):
        raise DataGateError("unknown or duplicate warning ID")
    ack = {"gate_sha256": gate["gate_sha256"], "warning_ids": sorted(requested), "acknowledged_at": datetime.now(timezone.utc).isoformat(), "meaning": "user saw warning; risk not scientifically eliminated"}
    ack_path = root / "acknowledgements.json"
    if ack_path.exists():
        ack_path.unlink()
    _write_new(ack_path, (json.dumps(ack, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return ack


def _passport(dataset_id: str, root: Path, manifest: dict) -> dict:
    meta = manifest["dataset"]
    return {
        "dataset_id": dataset_id,
        "display_name": meta["display_name"],
        "short_id": dataset_id[-8:],
        "filename": meta["filename"],
        "rows": meta["rows"],
        "columns": meta["columns"],
        "target": meta["target"],
        "features": meta["features"],
        "units": meta["units"],
        "unit_not_verified": True,
        "sha256": meta["sha256"],
        "counts": meta["counts"],
        "gate_status": meta["gate_status"],
        "warning_count": meta["warning_count"],
        "historical_replay": True,
    }


def intake_freeze(intake_id: str, *, dataset_id: str | None = None) -> dict:
    root, intake_manifest, frame = _load_intake(intake_id)
    if (root / "frozen.json").is_file():
        raise DataGateError("intake is already frozen; create a new intake to change roles")
    schema_payload = _current_schema(root, intake_manifest)
    if not (root / "gate.json").is_file():
        raise DataGateError("gate has not been run")
    gate = json.loads((root / "gate.json").read_text(encoding="utf-8"))
    if gate["status"] == "BLOCKED":
        raise DataGateError("blocked gate cannot be frozen")
    if gate["input_sha256"] != intake_manifest["input_sha256"] or gate["schema_sha256"] != schema_payload["schema_sha256"]:
        raise DataGateError("gate is stale; rerun gate")
    ack = json.loads((root / "acknowledgements.json").read_text(encoding="utf-8")) if (root / "acknowledgements.json").is_file() else None
    warning_ids = {item["id"] for item in gate["warnings"]}
    if warning_ids:
        if not ack or ack.get("gate_sha256") != gate["gate_sha256"] or not warning_ids <= set(ack.get("warning_ids", [])):
            raise DataGateError("all warnings must be acknowledged before freeze")
    schema = _schema_object(schema_payload)
    work, split = _split_frame(frame, schema, intake_manifest["input_sha256"])
    dataset_id = dataset_id or f"dataset_{uuid.uuid4().hex}"
    _validate_id(dataset_id, DATASET_ID, "dataset")
    out = DATASET_ROOT / dataset_id
    out.mkdir(parents=True, exist_ok=False)
    raw = (root / "raw.csv").read_bytes()
    _write_new(out / "raw.csv", raw)
    _write_new(out / "schema.json", (json.dumps(schema_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    _write_new(out / "units.json", (json.dumps({"units": schema_payload["units"], "unit_not_verified": True}, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    _write_new(out / "audit.json", (json.dumps(gate, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    _write_new(out / "split.json", (json.dumps(split.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8"))
    _write_new(out / "warning_acknowledgements.json", (json.dumps(ack or {"gate_sha256": gate["gate_sha256"], "warning_ids": []}, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    target = schema.target
    features = [
        {"name": c, "role": schema_payload["roles"][c], "display_name": schema_payload["display_names"].get(c, c), "unit": schema_payload["units"].get(c, "")}
        for c in frame.columns if schema_payload["roles"].get(str(c)) in {"control", "context"}
    ]
    manifest = {
        "dataset_version": "nexttest_p3_dataset_v1",
        "dataset_id": dataset_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "display_name": schema_payload["dataset_name"],
            "filename": intake_manifest["filename"],
            "rows": len(frame),
            "columns": len(frame.columns),
            "target": {"name": target, "display_name": schema_payload["display_names"].get(target, target), "unit": schema_payload["units"].get(target, "")},
            "features": features,
            "units": schema_payload["units"],
            "sha256": {"input": intake_manifest["input_sha256"], "schema": schema_payload["schema_sha256"], "split": split.split_sha256},
            "counts": {"train": len(split.train_row_ids), "candidate": len(split.candidate_row_ids), "test": len(split.test_row_ids), "groups": split.group_count},
            "gate_status": gate["status"], "warning_count": len(gate["warnings"]),
            "historical_replay": True, "unit_not_verified": True,
        },
    }
    _write_new(out / "dataset_manifest.json", (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    lines = []
    for path in sorted(p for p in out.rglob("*") if p.is_file() and p.name != "sha256.txt"):
        lines.append(f"{_file_sha(path)}  {path.relative_to(out).as_posix()}")
    _write_new(out / "sha256.txt", ("\n".join(lines) + "\n").encode("utf-8"))
    _canonical_file(root / "frozen.json", {"dataset_id": dataset_id, "tree_sha256": _tree_sha(out)})
    return {"dataset": _passport(dataset_id, out, manifest), "tree_sha256": _tree_sha(out)}


def _verify_dataset(dataset_id: str) -> tuple[Path, dict]:
    _validate_id(dataset_id, DATASET_ID, "dataset")
    root = DATASET_ROOT / dataset_id
    required = ["dataset_manifest.json", "raw.csv", "schema.json", "audit.json", "split.json", "units.json", "warning_acknowledgements.json", "sha256.txt"]
    if not root.is_dir() or not all((root / n).is_file() for n in required):
        raise DataGateError("dataset package incomplete")
    manifest = json.loads((root / "dataset_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("dataset_id") != dataset_id:
        raise DataGateError("dataset manifest ID mismatch")
    for line in (root / "sha256.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        digest, rel = line.split("  ", 1)
        path = root / rel
        if not path.is_file() or _file_sha(path) != digest:
            raise DataGateError(f"dataset file SHA mismatch: {rel}")
    raw = (root / "raw.csv").read_bytes()
    schema = json.loads((root / "schema.json").read_text(encoding="utf-8"))
    split = json.loads((root / "split.json").read_text(encoding="utf-8"))
    if manifest["dataset"]["sha256"]["input"] != _sha(raw):
        raise DataGateError("dataset raw SHA mismatch")
    if manifest["dataset"]["sha256"]["schema"] != schema["schema_sha256"] or schema["schema_sha256"] != sha256_text(canonical_json({k: v for k, v in schema.items() if k != "schema_sha256"})):
        raise DataGateError("dataset schema SHA mismatch")
    if manifest["dataset"]["sha256"]["split"] != split["split_sha256"]:
        raise DataGateError("dataset split SHA mismatch")
    return root, manifest


def dataset_inspect(dataset_id: str) -> dict:
    root, manifest = _verify_dataset(dataset_id)
    return {"dataset": _passport(dataset_id, root, manifest), "tree_sha256": _tree_sha(root)}


def load_custom_base(dataset_id: str) -> tuple[PreparedExperiment, dict, dict]:
    root, manifest = _verify_dataset(dataset_id)
    frame = _parse_csv((root / "raw.csv").read_bytes(), manifest["dataset"]["filename"], "text/csv")
    schema_payload = json.loads((root / "schema.json").read_text(encoding="utf-8"))
    schema = _schema_object(schema_payload)
    work, split = _split_frame(frame, schema, manifest["dataset"]["sha256"]["input"])
    package_split = json.loads((root / "split.json").read_text(encoding="utf-8"))
    if split.split_sha256 != package_split["split_sha256"] or list(split.train_row_ids) != package_split["train_row_ids"] or list(split.candidate_row_ids) != package_split["candidate_row_ids"] or list(split.test_row_ids) != package_split["test_row_ids"]:
        raise DataGateError("dataset split cannot be reproduced")
    target = schema.target
    observed_frame = work.loc[work["_row_id"].isin(split.train_row_ids), ["_row_id", *schema.feature_columns, target]].reset_index(drop=True)
    candidate_frame = work.loc[work["_row_id"].isin(split.candidate_row_ids), ["_row_id", *schema.feature_columns]].reset_index(drop=True)
    test_frame = work.loc[work["_row_id"].isin(split.test_row_ids), ["_row_id", *schema.feature_columns]].reset_index(drop=True)
    indexed = work.set_index("_row_id")
    vault = HiddenLabelVault(
        candidate_labels={row_id: float(indexed.loc[row_id, target]) for row_id in split.candidate_row_ids},
        test_labels={row_id: float(indexed.loc[row_id, target]) for row_id in split.test_row_ids},
    )
    audit_payload = json.loads((root / "audit.json").read_text(encoding="utf-8"))
    audit = DataAuditResult(
        input_sha256=manifest["dataset"]["sha256"]["input"], schema_sha256=schema.schema_sha256,
        row_count=len(frame), columns=tuple(map(str, frame.columns)),
        missing_counts={str(k): int(v) for k, v in frame.isna().sum().items()},
        duplicate_rows=int(frame.duplicated().sum()), duplicate_feature_rows=0,
        constant_columns=tuple(column for column in schema.feature_columns if frame[column].nunique(dropna=False) <= 1),
        outlier_counts={}, role_issues=(), errors=tuple(item["message"] for item in audit_payload.get("errors", [])),
        warnings=tuple(item["message"] for item in audit_payload.get("warnings", [])), passed=audit_payload.get("status") != "BLOCKED",
    )
    prepared = PreparedExperiment(
        observed=ObservedTrainingSet(frame=observed_frame, feature_columns=schema.feature_columns, target_column=target, row_ids=split.train_row_ids),
        candidates=CandidatePoolView(frame=candidate_frame, feature_columns=schema.feature_columns, row_ids=split.candidate_row_ids),
        test=IndependentTestView(frame=test_frame, feature_columns=schema.feature_columns, row_ids=split.test_row_ids),
        vault=vault, schema=schema, audit=audit, split=split,
    )
    return prepared, package_split, manifest
