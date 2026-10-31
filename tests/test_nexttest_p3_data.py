"""P3 Data Dock behavior tests: intake, roles, gate, freeze, labels, custom replay."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from nexttest import p3_data, p3_experiment
from nexttest.data import DataGateError


FIXTURES = Path(__file__).resolve().parents[1] / "data" / "nexttest" / "fixtures"
RAW = (FIXTURES / "alloy_tensile_passed.csv").read_bytes()
ROLES = {
    "temperature_c": "control",
    "hold_time_min": "control",
    "cooling_rate_c_s": "control",
    "alloy_code": "context",
    "tensile_strength_ksi": "target",
}
UNITS = {"temperature_c": "degC", "hold_time_min": "min", "cooling_rate_c_s": "degC/s", "alloy_code": "grade", "tensile_strength_ksi": "ksi"}
DISPLAY = {"temperature_c": "Temperature", "hold_time_min": "Hold time", "cooling_rate_c_s": "Cooling rate", "alloy_code": "Alloy code", "tensile_strength_ksi": "Tensile strength"}


@pytest.fixture(autouse=True)
def isolated_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(p3_data, "INTAKE_ROOT", tmp_path / "intakes")
    monkeypatch.setattr(p3_data, "DATASET_ROOT", tmp_path / "datasets")
    monkeypatch.setattr(p3_data, "PROJECT_ROOT", tmp_path / "projects")
    monkeypatch.setattr(p3_experiment, "PROJECT_ROOT", tmp_path / "projects")


def make_intake(raw: bytes = RAW, filename: str = "alloy.csv", *, schema: bool = True, dataset_name: str = "Alloy fixture"):
    created = p3_data.intake_create(raw, filename=filename)
    intake_id = created["intake"]["intake_id"]
    if schema:
        p3_data.intake_assign_schema(intake_id, roles=ROLES, display_names=DISPLAY, units=UNITS, dataset_name=dataset_name)
    return intake_id


def freeze_valid():
    intake_id = make_intake()
    gate = p3_data.intake_gate(intake_id)
    assert gate["status"] == "PASSED"
    frozen = p3_data.intake_freeze(intake_id)
    return intake_id, frozen["dataset"]["dataset_id"], frozen["tree_sha256"]


def test_valid_non_concrete_flow_full(tmp_path):
    _, dataset_id, tree = freeze_valid()
    inspected = p3_data.dataset_inspect(dataset_id)
    assert inspected["dataset"]["target"]["unit"] == "ksi"
    assert inspected["dataset"]["counts"] == {"train": 30, "candidate": 10, "test": 10, "groups": 50}
    assert inspected["tree_sha256"] == tree
    assert p3_data.dataset_inspect(dataset_id)["tree_sha256"] == tree
    preview = p3_experiment.preview_custom(dataset_id, strategy="greedy_prediction")
    assert preview["scope"] == "custom_candidate_pool_no_labels"
    assert preview["candidate_count"] == 10
    assert all("target" not in row and "revealed_target" not in row and "tensile_strength_ksi" not in row for row in preview["rows"])
    project = p3_experiment.create_custom_project(dataset_id=dataset_id, strategy="greedy_prediction", budget=1)
    pid = project["snapshot"]["project_id"]
    assert project["pending"] is None and project["history"] == []
    assert project["dataset"]["target"]["unit"] == "ksi"
    pending = p3_experiment.recommend_custom(pid)
    assert pending["pending"]["row_id"] in {row["row_id"] for row in preview["rows"]}
    assert "revealed_target" not in json.dumps(pending["pending"])
    revealed = p3_experiment.reveal_custom(pid, pending["pending"]["recommendation_id"])
    assert revealed["history"][0]["revealed_target"] > 0
    assert revealed["snapshot"]["budget"] == 1 and revealed["snapshot"]["remaining_budget"] == 0
    assert revealed["transition"]["before"]["model_sha"] != revealed["transition"]["after"]["model_sha"]
    assert "target" not in json.dumps(revealed["transition"])
    assert revealed["audit"]["test_unchanged"] is True
    assert p3_experiment.inspect_custom(pid)["history"] == revealed["history"]


def test_freeze_is_exclusive_and_does_not_overwrite():
    intake_id, dataset_id, _ = freeze_valid()
    with pytest.raises(DataGateError):
        p3_data.intake_freeze(intake_id)
    with pytest.raises(DataGateError):
        p3_data.intake_assign_schema(intake_id, roles=ROLES, display_names=DISPLAY, units=UNITS, dataset_name="changed")


def test_warning_must_be_individually_acknowledged(tmp_path):
    raw = (FIXTURES / "alloy_tensile_warning_duplicate.csv").read_bytes()
    intake_id = make_intake(raw, "warning.csv")
    gate = p3_data.intake_gate(intake_id)
    assert gate["status"] == "WARNING"
    assert {item["id"] for item in gate["warnings"]} >= {"duplicate_rows", "duplicate_recipes"}
    with pytest.raises(DataGateError):
        p3_data.intake_freeze(intake_id)
    ack = p3_data.intake_acknowledge(intake_id, [item["id"] for item in gate["warnings"]])
    assert set(ack["warning_ids"]) == {item["id"] for item in gate["warnings"]}
    frozen = p3_data.intake_freeze(intake_id)
    assert frozen["dataset"]["gate_status"] == "WARNING"
    assert frozen["dataset"]["warning_count"] == len(gate["warnings"])


def test_blocked_constant_target_and_bad_roles():
    raw = (FIXTURES / "alloy_tensile_blocked_constant.csv").read_bytes()
    intake_id = make_intake(raw, "blocked.csv")
    gate = p3_data.intake_gate(intake_id)
    assert gate["status"] == "BLOCKED"
    assert any(item["code"] == "constant_target" for item in gate["errors"])
    with pytest.raises(DataGateError):
        p3_data.intake_freeze(intake_id)


def test_schema_change_invalidates_gate_and_ack():
    intake_id = make_intake()
    p3_data.intake_gate(intake_id)
    assert (p3_data.INTAKE_ROOT / intake_id / "gate.json").is_file()
    roles = dict(ROLES)
    roles["alloy_code"] = "ignored"
    p3_data.intake_assign_schema(intake_id, roles=roles, display_names=DISPLAY, units=UNITS, dataset_name="changed")
    assert not (p3_data.INTAKE_ROOT / intake_id / "gate.json").exists()
    assert not (p3_data.INTAKE_ROOT / intake_id / "acknowledgements.json").exists()
    with pytest.raises(DataGateError):
        p3_data.intake_freeze(intake_id)


@pytest.mark.parametrize("raw,filename,fragment", [
    (b"a,a\n1,2\n", "duplicate.csv", "duplicate"),
    (b"_row_id,a,b,t\n1,2,3,4\n", "reserved.csv", "_row_id"),
    (b"\xff\xfe\x00a,b\n1,2\n", "binary.csv", "UTF-8"),
    (b"", "empty.csv", "empty"),
    (b'a,b\n"unterminated,2\n', "rows.csv", "unreadable"),
])
def test_upload_rejections(raw, filename, fragment):
    with pytest.raises(DataGateError) as exc:
        p3_data.intake_create(raw, filename=filename)
    assert fragment.lower() in str(exc.value).lower() or fragment in str(exc.value)


def test_upload_limits_and_nonnumeric_roles():
    header = ",".join(f"x{i}" for i in range(65))
    with pytest.raises(DataGateError):
        p3_data.intake_create((header + "\n" + ",".join("1" for _ in range(65)) + "\n").encode(), filename="wide.csv")
    rows = ["x,y,t"] + ["1,2,3"] * 20_001
    with pytest.raises(DataGateError):
        p3_data.intake_create(("\n".join(rows) + "\n").encode(), filename="long.csv")
    raw = b"x,y,t,label\n1,2,3,a\n4,5,6,b\n7,8,9,c\n"
    intake_id = p3_data.intake_create(raw, filename="text.csv")["intake"]["intake_id"]
    with pytest.raises(DataGateError):
        p3_data.intake_assign_schema(intake_id, roles={"x": "control", "y": "control", "t": "target", "label": "control"}, display_names={}, units={}, dataset_name="bad")


def test_nan_and_few_groups_are_blocked():
    raw = b"x,y,t\n1,2,3\n4,NaN,6\n7,8,9\n10,11,12\n"
    intake_id = p3_data.intake_create(raw, filename="nan.csv")["intake"]["intake_id"]
    p3_data.intake_assign_schema(intake_id, roles={"x": "control", "y": "control", "t": "target"}, display_names={}, units={}, dataset_name="nan")
    gate = p3_data.intake_gate(intake_id)
    assert gate["status"] == "BLOCKED"
    assert any(item["code"] == "non_numeric_or_missing" for item in gate["errors"])
    raw2 = b"x,y,t\n1,2,3\n1,2,4\n1,2,5\n1,2,6\n"
    i2 = p3_data.intake_create(raw2, filename="groups.csv")["intake"]["intake_id"]
    p3_data.intake_assign_schema(i2, roles={"x": "control", "y": "control", "t": "target"}, display_names={}, units={}, dataset_name="groups")
    g2 = p3_data.intake_gate(i2)
    assert g2["status"] == "BLOCKED"
    assert any(item["code"] == "split_not_possible" for item in g2["errors"])


def test_heuristic_warnings_are_not_proof():
    rows = [["row_key", "x", "z", "target"]]
    for i in range(40):
        rows.append([i, i + 1, i % 3, i + 1])
    raw = ("\n".join(",".join(map(str, row)) for row in rows) + "\n").encode()
    intake_id = p3_data.intake_create(raw, filename="heuristic.csv")["intake"]["intake_id"]
    p3_data.intake_assign_schema(intake_id, roles={"row_key": "posthoc", "x": "control", "z": "control", "target": "target"}, display_names={}, units={}, dataset_name="heuristic")
    gate = p3_data.intake_gate(intake_id)
    assert gate["status"] == "WARNING"
    text = json.dumps(gate, ensure_ascii=False)
    assert "near_perfect_correlation:x" in text
    assert "id_like:row_key" in text
    assert "不是泄漏证明" in text


def test_constant_and_outlier_are_warnings_not_silent_fixes():
    rows = [["x", "z", "t"]]
    for i in range(40):
        rows.append([1, 1000 if i == 39 else i, i + 2])
    raw = ("\n".join(",".join(map(str, row)) for row in rows) + "\n").encode()
    intake_id = p3_data.intake_create(raw, filename="constant.csv")["intake"]["intake_id"]
    p3_data.intake_assign_schema(intake_id, roles={"x": "control", "z": "control", "t": "target"}, display_names={}, units={}, dataset_name="constant")
    gate = p3_data.intake_gate(intake_id)
    assert gate["status"] == "WARNING"
    ids = {item["id"] for item in gate["warnings"]}
    assert "constant:x" in ids
    assert "outlier:z" in ids


def test_dataset_tamper_and_path_traversal_fail_closed():
    _, dataset_id, _ = freeze_valid()
    root = p3_data.DATASET_ROOT / dataset_id
    schema = json.loads((root / "schema.json").read_text(encoding="utf-8"))
    schema["roles"]["temperature_c"] = "target"
    (root / "schema.json").write_text(json.dumps(schema), encoding="utf-8")
    with pytest.raises(DataGateError):
        p3_data.dataset_inspect(dataset_id)
    with pytest.raises(DataGateError):
        p3_data.dataset_inspect("../" + dataset_id)
    with pytest.raises(DataGateError):
        p3_experiment.create_custom_project(dataset_id="../" + dataset_id)
