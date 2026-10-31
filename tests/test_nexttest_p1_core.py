import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nexttest import data, demo, models
from nexttest.data import CandidatePoolView, HiddenLabelVault, PreparedExperiment
from nexttest.schemas import ColumnRole, DatasetSchema


def _schema():
    return demo.concrete_schema()


def _write(frame, path):
    frame.to_csv(path, index=False)
    return path


def _valid(tmp_path, rows=80):
    path = tmp_path / "data.csv"
    _write(demo.synthetic_frame(rows, seed=7), path)
    return path


def test_normal_csv_audit_prepare_and_typed_views(tmp_path):
    path = _valid(tmp_path)
    audit = data.audit_csv(path, _schema())
    assert audit.passed and audit.row_count == 80
    exp = data.prepare_dataset(path, _schema(), seed=11)
    assert isinstance(exp, PreparedExperiment)
    assert isinstance(exp.candidates, CandidatePoolView)
    assert len(exp.observed.frame) > 0
    assert len(exp.candidates.frame) > 0
    assert len(exp.test.frame) > 0
    assert "CompressiveStrength" not in exp.candidates.frame.columns
    assert "CompressiveStrength" not in exp.test.frame.columns
    assert not hasattr(exp.candidates, "vault")
    assert set(exp.candidates.frame.columns) == {"_row_id", *exp.schema.feature_columns}


def test_roles_are_immutable_and_control_count_enforced():
    schema = _schema()
    with pytest.raises(TypeError):
        schema.roles["Cement"] = ColumnRole.IGNORED
    with pytest.raises(ValueError):
        DatasetSchema(roles={"a": ColumnRole.CONTROL, "y": ColumnRole.TARGET}, target="y")


def test_empty_missing_duplicate_columns_fail(tmp_path):
    empty = tmp_path / "empty.csv"; empty.write_text("")
    with pytest.raises(data.DataGateError):
        data.audit_csv(empty, _schema())
    frame = demo.synthetic_frame(30).drop(columns=["Cement"])
    missing = _write(frame, tmp_path / "missing.csv")
    assert not data.audit_csv(missing, _schema()).passed
    dup = tmp_path / "dup.csv"; dup.write_text("Age,Age,CompressiveStrength\n1,2,3\n")
    with pytest.raises(data.DataGateError):
        data.audit_csv(dup, _schema())


def test_non_numeric_nan_inf_fail(tmp_path):
    frame = demo.synthetic_frame(30); frame["Water"] = frame["Water"].astype(object); frame.loc[0, "Water"] = "bad"
    assert not data.audit_csv(_write(frame, tmp_path / "nonnumeric.csv"), _schema()).passed
    frame = demo.synthetic_frame(30); frame.loc[0, "Water"] = np.nan
    assert not data.audit_csv(_write(frame, tmp_path / "nan.csv"), _schema()).passed
    frame = demo.synthetic_frame(30); frame.loc[0, "Water"] = np.inf
    assert not data.audit_csv(_write(frame, tmp_path / "inf.csv"), _schema()).passed


def test_duplicate_and_constant_warnings(tmp_path):
    frame = demo.synthetic_frame(30)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    frame["Cement"] = 300.0
    audit = data.audit_csv(_write(frame, tmp_path / "dup.csv"), _schema())
    assert audit.passed
    assert audit.duplicate_rows >= 1
    assert "Cement" in audit.constant_columns


def test_caller_row_id_rejected(tmp_path):
    frame = demo.synthetic_frame(20)
    frame.insert(0, "_row_id", ["x"] * len(frame))
    with pytest.raises(data.DataGateError):
        data.audit_csv(_write(frame, tmp_path / "rowid.csv"), _schema())


def test_constant_target_rejected(tmp_path):
    frame = demo.synthetic_frame(30); frame["CompressiveStrength"] = 30.0
    with pytest.raises(data.DataGateError):
        data.prepare_dataset(_write(frame, tmp_path / "constant.csv"), _schema(), seed=1)


def test_split_reproducible_and_grouped(tmp_path):
    path = _valid(tmp_path)
    a = data.prepare_dataset(path, _schema(), seed=9)
    b = data.prepare_dataset(path, _schema(), seed=9)
    c = data.prepare_dataset(path, _schema(), seed=10)
    assert a.split.split_sha256 == b.split.split_sha256
    assert a.split.split_sha256 != c.split.split_sha256
    assert not set(a.split.train_row_ids) & set(a.split.test_row_ids)
    # Same control recipe must remain in one split, even if Age differs.
    ids = list(a.split.train_row_ids) + list(a.split.candidate_row_ids) + list(a.split.test_row_ids)
    frame = pd.concat([a.observed.frame, a.candidates.frame.assign(CompressiveStrength=np.nan), a.test.frame.assign(CompressiveStrength=np.nan)], ignore_index=True)
    assert set(ids) == set(frame["_row_id"])


def test_same_recipe_different_age_same_split(tmp_path):
    frame = demo.synthetic_frame(20)
    base = frame.iloc[0].copy()
    rows = []
    for age in (3, 7, 28, 56, 90):
        row = base.copy(); row["Age"] = age; row["CompressiveStrength"] = float(base["CompressiveStrength"]) + age * 0.1
        rows.append(row)
    frame = pd.concat([frame, pd.DataFrame(rows)], ignore_index=True)
    exp = data.prepare_dataset(_write(frame, tmp_path / "age.csv"), _schema(), seed=12)
    all_frame = pd.concat([
        exp.observed.frame[["_row_id", *exp.schema.control_columns]],
        exp.candidates.frame[["_row_id", *exp.schema.control_columns]],
        exp.test.frame[["_row_id", *exp.schema.control_columns]],
    ], ignore_index=True)
    base_controls = tuple(round(float(v), 9) for v in base[list(exp.schema.control_columns)])
    group = all_frame[all_frame[list(exp.schema.control_columns)].apply(lambda r: tuple(round(float(v), 9) for v in r) == base_controls, axis=1)]
    assert len(group) >= 5
    memberships = {("train" if x in exp.split.train_row_ids else "candidate" if x in exp.split.candidate_row_ids else "test") for x in group["_row_id"]}
    assert len(memberships) == 1


def test_candidate_view_has_no_labels_and_selector_rejects_experiment(tmp_path):
    exp = data.prepare_dataset(_valid(tmp_path), _schema(), seed=2)
    assert "CompressiveStrength" not in exp.candidates.frame.columns
    assert not hasattr(exp.candidates, "label")
    def selector(candidates: CandidatePoolView):
        if not isinstance(candidates, CandidatePoolView):
            raise TypeError("selector only accepts CandidatePoolView")
        return len(candidates.row_ids)
    assert selector(exp.candidates) == len(exp.candidates.row_ids)
    with pytest.raises(TypeError):
        selector(exp)
    with pytest.raises(TypeError):
        selector(exp.vault)


def test_vault_release_once_and_rejects_test_unknown(tmp_path):
    exp = data.prepare_dataset(_valid(tmp_path), _schema(), seed=3)
    candidate = exp.candidates.row_ids[0]
    rec = exp.vault.reveal(candidate)
    assert rec.status == "released"
    assert rec.target == pytest.approx(float(exp.vault.candidate_labels[candidate]))
    with pytest.raises(ValueError):
        exp.vault.reveal(candidate)
    with pytest.raises(PermissionError):
        exp.vault.reveal(exp.test.row_ids[0])
    with pytest.raises(KeyError):
        exp.vault.reveal("row-999999")
    assert [r.status for r in exp.vault.released_records()] == ["requested", "released"]


def test_metrics_finite_defined_and_model_roundtrip(tmp_path):
    exp = data.prepare_dataset(_valid(tmp_path), _schema(), seed=5)
    predictor = models.train_regression(exp, seed=5)
    metrics = models.evaluate_regression(predictor, exp)
    assert np.isfinite([metrics.mae, metrics.rmse]).all()
    pred = predictor.predict(exp.test.frame)
    labels = exp.vault.test_labels_for_evaluation()
    truth = np.asarray([labels[x] for x in exp.test.frame["_row_id"]])
    assert metrics.mae == pytest.approx(float(np.mean(np.abs(pred - truth))))
    assert metrics.rmse == pytest.approx(float(np.sqrt(np.mean((pred - truth) ** 2))))
    models.save_predictor(predictor, tmp_path / "model")
    restored = models.load_predictor(tmp_path / "model")
    assert np.allclose(pred, restored.predict(exp.test.frame))


def test_output_dir_is_exclusive_and_official_real_data_runs(tmp_path):
    out = tmp_path / "out"; out.mkdir()
    with pytest.raises(FileExistsError):
        demo.run_p1_demo(out, dataset_mode="official")
    official = tmp_path / "official"
    result = demo.run_p1_demo(official, dataset_mode="official")
    assert result["non_real_demo"] is False
    assert result["dataset_mode"] == "official"
    assert result["audit"]["row_count"] == 425
    for name in ("source_manifest.json", "dataset_audit.json", "field_mapping.json", "split.json", "metrics.json", "test_predictions.csv", "manifest.json", "README.md", "model/model.pkl", "model/model_manifest.json", "sha256.txt", "duplicate_diagnostics.json"):
        assert (official / name).is_file()
    manifest = json.loads((official / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_mode"] == "official"
    assert manifest["data_source"]["license"] == "CC BY 4.0"
    assert manifest["data_source"]["accessed_utc"]
    assert np.isfinite([manifest["metrics"]["mae"], manifest["metrics"]["rmse"]]).all()


def test_synthetic_demo_is_marked(tmp_path):
    out = tmp_path / "synthetic"
    result = demo.run_p1_demo(out, dataset_mode="synthetic")
    assert result["non_real_demo"] is True
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["non_real_demo"] is True
    assert manifest["data_source"]["kind"] == "synthetic_fixture"


def test_no_torch_or_test_payload_in_nexttest():
    text = "\n".join(p.read_text(encoding="utf-8") for p in Path("nexttest").glob("*.py"))
    assert "import torch" not in text
    assert "datasets/Test" not in text
    assert "runs/live_sessions" not in text


def test_official_source_manifest_and_canonical_hashes():
    source = json.loads(Path("data/nexttest/uci_concrete/source_manifest.json").read_text(encoding="utf-8"))
    canonical = json.loads(Path("data/nexttest/uci_concrete/canonical/canonical_manifest.json").read_text(encoding="utf-8"))
    assert source["instances_expected"] == 1030
    assert source["input_variables_expected"] == 8
    assert source["license"] == "CC BY 4.0"
    import hashlib
    assert hashlib.sha256(Path("data/nexttest/uci_concrete/source/Concrete_Data.xls").read_bytes()).hexdigest() == source["files"]["Concrete_Data.xls"]["sha256"]
    assert hashlib.sha256(Path("data/nexttest/uci_concrete/canonical/concrete_age28.csv").read_bytes()).hexdigest() == canonical["age28_csv_sha256"]


def test_official_xls_to_canonical_is_deterministic(tmp_path):
    import hashlib
    mapping = json.loads(Path("data/nexttest/uci_concrete/canonical/field_mapping.json").read_text(encoding="utf-8"))
    raw = pd.read_excel("data/nexttest/uci_concrete/source/Concrete_Data.xls")
    rename = {item["source"]: item["canonical"] for item in mapping["columns"]}
    order = [item["canonical"] for item in mapping["columns"]]
    regenerated = raw.rename(columns=rename)[order]
    out = tmp_path / "canonical.csv"
    regenerated.to_csv(out, index=False, float_format="%.12g")
    expected = Path("data/nexttest/uci_concrete/canonical/concrete_canonical.csv")
    assert hashlib.sha256(out.read_bytes()).hexdigest() == hashlib.sha256(expected.read_bytes()).hexdigest()
