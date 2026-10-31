"""P1/P1-R demo orchestration: audit → schema → split → model → metrics → report."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from .data import DataGateError, audit_csv, prepare_dataset
from .models import evaluate_regression, save_predictor, train_regression
from .schemas import ColumnRole, DatasetSchema

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_ROOT = ROOT / "data" / "nexttest" / "uci_concrete"
OFFICIAL_SOURCE = OFFICIAL_ROOT / "source"
OFFICIAL_CANONICAL = OFFICIAL_ROOT / "canonical"
OFFICIAL_AGE28 = OFFICIAL_CANONICAL / "concrete_age28.csv"
OFFICIAL_CANONICAL_MANIFEST = OFFICIAL_CANONICAL / "canonical_manifest.json"
OFFICIAL_SOURCE_MANIFEST = OFFICIAL_ROOT / "source_manifest.json"
OFFICIAL_FIELD_MAPPING = OFFICIAL_CANONICAL / "field_mapping.json"

SYNTHETIC_SEED = 20261026
CONTROLS = (
    "Cement",
    "BlastFurnaceSlag",
    "FlyAsh",
    "Water",
    "Superplasticizer",
    "CoarseAggregate",
    "FineAggregate",
)
CONTEXT = ("Age",)
TARGET = "CompressiveStrength"


def concrete_schema(name: str = "synthetic_concrete_fixture") -> DatasetSchema:
    roles = {column: ColumnRole.CONTROL for column in CONTROLS}
    roles.update({column: ColumnRole.CONTEXT for column in CONTEXT})
    roles[TARGET] = ColumnRole.TARGET
    return DatasetSchema(roles=roles, target=TARGET, name=name)


def synthetic_frame(rows: int = 180, seed: int = SYNTHETIC_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = {
        "Cement": rng.uniform(120, 540, rows),
        "BlastFurnaceSlag": rng.uniform(0, 350, rows),
        "FlyAsh": rng.uniform(0, 220, rows),
        "Water": rng.uniform(120, 230, rows),
        "Superplasticizer": rng.uniform(0, 25, rows),
        "CoarseAggregate": rng.uniform(800, 1150, rows),
        "FineAggregate": rng.uniform(590, 990, rows),
        "Age": rng.choice([3, 7, 14, 28, 56, 90], rows),
    }
    strength = (
        12.0
        + 0.055 * data["Cement"]
        + 0.045 * data["BlastFurnaceSlag"]
        + 0.035 * data["FlyAsh"]
        - 0.095 * data["Water"]
        + 0.18 * data["Superplasticizer"]
        + 0.004 * data["CoarseAggregate"]
        + 0.006 * data["FineAggregate"]
        + 0.11 * np.sqrt(data["Age"])
        + rng.normal(0, 3.2, rows)
    )
    data[TARGET] = np.maximum(strength, 2.0)
    return pd.DataFrame(data)


def _write_new(path: Path, data: str | bytes) -> None:
    payload = data.encode("utf-8") if isinstance(data, str) else data
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _environment() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "device": "cpu",
    }


def _official_guard() -> tuple[dict, dict]:
    required = (OFFICIAL_SOURCE_MANIFEST, OFFICIAL_CANONICAL_MANIFEST, OFFICIAL_AGE28, OFFICIAL_FIELD_MAPPING)
    if not all(path.is_file() for path in required):
        raise DataGateError("official UCI data gate is not complete: source/canonical artifacts are missing")
    source = json.loads(OFFICIAL_SOURCE_MANIFEST.read_text(encoding="utf-8"))
    canonical = json.loads(OFFICIAL_CANONICAL_MANIFEST.read_text(encoding="utf-8"))
    if source.get("http_status") != 200:
        raise DataGateError("official source HTTP status is not 200")
    if source.get("license") != "CC BY 4.0":
        raise DataGateError("official license is not the expected CC BY 4.0")
    if canonical.get("source_manifest_sha256") != _sha(OFFICIAL_SOURCE_MANIFEST):
        raise DataGateError("canonical manifest does not bind the source manifest")
    if canonical.get("age28_csv_sha256") != _sha(OFFICIAL_AGE28):
        raise DataGateError("canonical Age=28 SHA mismatch")
    if canonical.get("canonical_csv_sha256") != _sha(OFFICIAL_CANONICAL / "concrete_canonical.csv"):
        raise DataGateError("canonical CSV SHA mismatch")
    if canonical.get("rows") != 1030 or canonical.get("age28_rows") != 425:
        raise DataGateError("official row counts do not match expected 1030/425")
    return source, canonical


def _write_predictions(path: Path, frame: pd.DataFrame, target: str) -> None:
    table = frame[["_row_id", target]].copy()
    table["prediction"] = frame["prediction"]
    table["residual"] = frame["prediction"] - frame[target]
    table.to_csv(path, index=False, float_format="%.8f")



def _duplicate_diagnostics(prepared, canonical_full: Path | None = None) -> dict:
    controls = list(prepared.schema.control_columns)
    train = prepared.observed.frame[controls].to_numpy(dtype=float)
    mean = train.mean(axis=0)
    scale = train.std(axis=0)
    scale[scale == 0] = 1.0
    train_z = (train - mean) / scale
    diagnostics = {
        "diagnostic_version": "nexttest_p1r_duplicate_diagnostic_v1",
        "group_definition": "exact control recipe; Age excluded",
        "exact_recipe_cross_split": 0,
        "candidate_nearest_train_distance": None,
        "test_nearest_train_distance": None,
        "near_duplicate_tolerance": 0.01,
        "near_duplicate_note": "illustrative normalized Euclidean tolerance; not a validated physical threshold",
        "candidate_near_train_count": 0,
        "test_near_train_count": 0,
    }
    for split_name, view in (("candidate", prepared.candidates.frame), ("test", prepared.test.frame)):
        values = view[controls].to_numpy(dtype=float)
        z = (values - mean) / scale
        distances = np.sqrt(((z[:, None, :] - train_z[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
        diagnostics[f"{split_name}_nearest_train_distance"] = {
            "min": float(np.min(distances)),
            "p05": float(np.quantile(distances, 0.05)),
            "median": float(np.median(distances)),
            "max": float(np.max(distances)),
        }
        diagnostics[f"{split_name}_near_train_count"] = int((distances <= 0.01).sum())
    if canonical_full is not None and canonical_full.is_file():
        full = pd.read_csv(canonical_full)
        unique_recipes = full[controls].drop_duplicates().shape[0]
        multi_age = int((full.groupby(controls).size() > 1).sum())
        diagnostics["full_dataset"] = {
            "rows": int(len(full)),
            "exact_duplicate_rows": int(full.duplicated().sum()),
            "unique_control_recipes": int(unique_recipes),
            "recipes_with_multiple_age": multi_age,
            "age_values": {str(k): int(v) for k, v in full["Age"].value_counts().sort_index().items()},
        }
        # Exact recipe groups are checked using the actual split labels.
        frame = prepared.observed.frame.copy()
        split_by_id = {"train": set(prepared.split.train_row_ids), "candidate": set(prepared.split.candidate_row_ids), "test": set(prepared.split.test_row_ids)}
        all_rows = pd.concat([
            prepared.observed.frame[["_row_id", *controls]],
            prepared.candidates.frame[["_row_id", *controls]],
            prepared.test.frame[["_row_id", *controls]],
        ], ignore_index=True)
        groups = all_rows.groupby(controls)["_row_id"].apply(list)
        diagnostics["exact_recipe_cross_split"] = int(sum(
            1 for ids in groups if len({name for name, members in split_by_id.items() if set(ids) & members}) > 1
        ))
    return diagnostics

def run_p1_demo(output_dir: str | Path, *, dataset_mode: str) -> dict:
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f"output directory already exists: {output}")
    if dataset_mode not in {"official", "synthetic"}:
        raise ValueError("dataset_mode must be 'official' or 'synthetic'")

    source_payload = None
    canonical_payload = None
    if dataset_mode == "official":
        source_payload, canonical_payload = _official_guard()
        data_path = OFFICIAL_AGE28
        schema = concrete_schema("uci_concrete_age28")
        non_real_demo = False
        source_info = {
            "kind": "uci_official",
            "dataset": source_payload["dataset"],
            "dataset_page": source_payload["dataset_page"],
            "download_url": source_payload["download_url"],
            "accessed_utc": source_payload["accessed_utc"],
            "license": source_payload["license"],
            "license_url": source_payload["license_url"],
            "attribution": source_payload["attribution"],
            "source_manifest_sha256": _sha(OFFICIAL_SOURCE_MANIFEST),
            "canonical_manifest_sha256": _sha(OFFICIAL_CANONICAL_MANIFEST),
            "canonical_csv_sha256": canonical_payload["canonical_csv_sha256"],
            "age28_csv_sha256": canonical_payload["age28_csv_sha256"],
            "age_mode": "fixed Age=28",
        }
    else:
        data_path = None
        schema = concrete_schema()
        non_real_demo = True
        source_info = {
            "kind": "synthetic_fixture",
            "name": "synthetic concrete-like fixture",
            "license": "not applicable; generated fixture, not UCI data",
            "note": "This is not the official UCI Concrete Compressive Strength dataset.",
        }

    output.mkdir(parents=True, exist_ok=False)
    if dataset_mode == "official":
        assert data_path is not None
        dataset_path = output / "dataset.csv"
        shutil.copyfile(data_path, dataset_path)
        for source_path, name in ((OFFICIAL_SOURCE_MANIFEST, "source_manifest.json"), (OFFICIAL_FIELD_MAPPING, "field_mapping.json"), (OFFICIAL_CANONICAL_MANIFEST, "canonical_manifest.json")):
            shutil.copyfile(source_path, output / name)
    else:
        dataset_path = output / "dataset.csv"
        synthetic_frame().to_csv(dataset_path, index=False, float_format="%.8f")

    started = time.perf_counter()
    audit = audit_csv(dataset_path, schema)
    full_audit = None
    if dataset_mode == "official":
        full_audit = audit_csv(OFFICIAL_CANONICAL / "concrete_canonical.csv", concrete_schema("uci_concrete_full"))
    prepared = prepare_dataset(dataset_path, schema, seed=SYNTHETIC_SEED)
    predictor = train_regression(prepared, seed=SYNTHETIC_SEED, non_real_demo=non_real_demo)
    metrics = evaluate_regression(predictor, prepared)
    diagnostics = _duplicate_diagnostics(prepared, OFFICIAL_CANONICAL / "concrete_canonical.csv" if dataset_mode == "official" else None)
    elapsed = time.perf_counter() - started
    model_manifest = save_predictor(predictor, output / "model")

    test_inputs = prepared.test.frame
    labels = prepared.vault.test_labels_for_evaluation()
    test_frame = test_inputs.copy()
    test_frame[prepared.observed.target_column] = [labels[row_id] for row_id in test_frame["_row_id"]]
    test_frame["prediction"] = predictor.predict(test_inputs)
    _write_predictions(output / "test_predictions.csv", test_frame, prepared.observed.target_column)

    audit_payload = audit.to_dict()
    if full_audit is not None:
        audit_payload["full_dataset_audit"] = full_audit.to_dict()
    split_payload = prepared.split.to_dict()
    split_payload["audit"] = {
        "passed": audit.passed,
        "row_count": audit.row_count,
        "errors": list(audit.errors),
        "warnings": list(audit.warnings),
    }
    metrics_payload = metrics.to_dict()
    _write_new(output / "dataset_audit.json", json.dumps(audit_payload, indent=2, sort_keys=True) + "\n")
    _write_new(output / "split.json", json.dumps(split_payload, indent=2, sort_keys=True) + "\n")
    _write_new(output / "metrics.json", json.dumps(metrics_payload, indent=2, sort_keys=True) + "\n")
    _write_new(output / "duplicate_diagnostics.json", json.dumps(diagnostics, indent=2, sort_keys=True) + "\n")

    manifest = {
        "manifest_version": "nexttest_p1r_demo_manifest_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_mode": dataset_mode,
        "non_real_demo": non_real_demo,
        "data_source": source_info,
        "schema": schema.to_dict(),
        "audit": {"passed": audit.passed, "path": "dataset_audit.json"},
        "split": split_payload,
        "model": model_manifest,
        "metrics": metrics_payload,
        "duplicate_diagnostics": diagnostics,
        "cpu_seconds": elapsed,
        "environment": _environment(),
        "limitations": [
            "Age is fixed at 28 days for this first demo; it is context, not a free control.",
            "Metrics describe this offline model on a held-out group split; no industrial or scientific validity is claimed.",
            "No candidate selection, feedback loop, cost, or UI was implemented in P1 Core/P1-R.",
        ],
        "outputs": {
            "dataset": "dataset.csv",
            "audit": "dataset_audit.json",
            "split": "split.json",
            "metrics": "metrics.json",
            "predictions": "test_predictions.csv",
            "duplicate_diagnostics": "duplicate_diagnostics.json",
            "model_dir": "model",
        },
    }
    _write_new(output / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    report_lines = [
        "# NextTest P1-R Demo",
        "",
        f"- mode: **{dataset_mode}**",
        f"- non_real_demo: **{str(non_real_demo).lower()}**",
        f"- rows: {audit.row_count}",
        f"- controls: {', '.join(schema.control_columns)}",
        f"- context: {', '.join(schema.context_columns)}",
        f"- target: {schema.target}",
        f"- train/candidate/test: {len(split_payload['train_row_ids'])} / {len(split_payload['candidate_row_ids'])} / {len(split_payload['test_row_ids'])}",
        f"- model: {model_manifest['model_family']}",
        f"- MAE: {metrics.mae:.6f}",
        f"- RMSE: {metrics.rmse:.6f}",
        f"- CPU seconds: {elapsed:.3f}",
        "",
        "Limitations: offline demonstration only; no UI, recommendation loop, cost, or industrial claim.",
    ]
    _write_new(output / "README.md", "\n".join(report_lines) + "\n")

    sha_lines = []
    for path in sorted(p for p in output.rglob("*") if p.is_file() and p.name != "sha256.txt"):
        sha_lines.append(f"{_sha(path)}  {path.relative_to(output).as_posix()}")
    _write_new(output / "sha256.txt", "\n".join(sha_lines) + "\n")
    return {
        "output_dir": str(output),
        "dataset_mode": dataset_mode,
        "non_real_demo": non_real_demo,
        "audit": audit_payload,
        "split": split_payload,
        "metrics": metrics_payload,
        "model_manifest": model_manifest,
        "input_sha256": audit.input_sha256,
        "schema_sha256": schema.schema_sha256,
        "cpu_seconds": elapsed,
    }
