"""P3 API and worker contract: raw upload, strict shapes, label boundary, custom loop."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from nexttest.web import api
from scripts import nexttest_ui_worker as worker


RAW = (Path(__file__).resolve().parents[1] / "data" / "nexttest" / "fixtures" / "alloy_tensile_passed.csv").read_bytes()
ROLES = {"temperature_c": "control", "hold_time_min": "control", "cooling_rate_c_s": "control", "alloy_code": "context", "tensile_strength_ksi": "target"}
UNITS = {"temperature_c": "degC", "hold_time_min": "min", "cooling_rate_c_s": "degC/s", "alloy_code": "grade", "tensile_strength_ksi": "ksi"}
DISPLAY = {"temperature_c": "Temperature", "hold_time_min": "Hold time", "cooling_rate_c_s": "Cooling rate", "alloy_code": "Alloy code", "tensile_strength_ksi": "Tensile strength"}


@pytest.fixture(scope="module")
def client():
    return TestClient(api.app, base_url='http://127.0.0.1:8501')


def test_api_raw_upload_gate_freeze_custom_label_boundary(client):
    response = client.post("/api/intakes", content=RAW, headers={"Content-Type": "text/csv", "X-NextTest-Filename": "alloy.csv"})
    assert response.status_code == 200, response.text
    intake_id = response.json()["intake"]["intake_id"]
    assert response.json()["intake"]["rows"] == 50
    assert "preview" in response.json()["intake"]
    schema = client.post(f"/api/intakes/{intake_id}/schema", json={"roles": ROLES, "display_names": DISPLAY, "units": UNITS, "dataset_name": "Alloy"})
    assert schema.status_code == 200, schema.text
    gate = client.post(f"/api/intakes/{intake_id}/gate").json()
    assert gate["status"] == "PASSED"
    frozen = client.post(f"/api/intakes/{intake_id}/freeze")
    assert frozen.status_code == 200, frozen.text
    dataset_id = frozen.json()["dataset"]["dataset_id"]
    assert client.get(f"/api/datasets/{dataset_id}").status_code == 200
    assert client.get("/api/datasets/bad").status_code == 400
    preview = client.post("/api/custom/preview", json={"dataset_id": dataset_id, "goal": "maximize", "strategy": "greedy_prediction", "threshold": None})
    assert preview.status_code == 200, preview.text
    value = preview.json()
    assert value["scope"] == "custom_candidate_pool_no_labels"
    assert value["candidate_count"] == 10
    assert all("target" not in row and "revealed_target" not in row and "tensile_strength_ksi" not in row for row in value["rows"])
    created = client.post("/api/custom/projects", json={"dataset_id": dataset_id, "goal": "maximize", "strategy": "greedy_prediction", "budget": 2, "threshold": None})
    assert created.status_code == 200, created.text
    project = created.json()
    pid = project["snapshot"]["project_id"]
    assert pid.startswith("p3_")
    assert project["dataset"]["target"]["unit"] == "ksi"
    assert project["snapshot"]["test_count"] == 10
    pending = client.post(f"/api/custom/projects/{pid}/recommend")
    assert pending.status_code == 200, pending.text
    assert pending.json()["pending"] is not None
    assert "revealed_target" not in json.dumps(pending.json()["pending"])
    rec_id = pending.json()["pending"]["recommendation_id"]
    revealed = client.post(f"/api/custom/projects/{pid}/reveal", json={"recommendation_id": rec_id})
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["history"][0]["revealed_target"] > 0
    assert revealed.json()["snapshot"]["test_count"] == 10
    assert "target" not in json.dumps(revealed.json()["transition"])


def test_api_rejects_ambiguous_ids_extra_fields_and_non_csv(client):
    assert client.post("/api/intakes", content=b"", headers={"Content-Type": "text/csv", "X-NextTest-Filename": "empty.csv"}).status_code == 413
    assert client.post("/api/intakes", content=RAW, headers={"Content-Type": "text/csv", "X-NextTest-Filename": "../bad.csv"}).status_code == 400
    assert client.post("/api/custom/preview", json={"dataset_id": "dataset_" + "a" * 32, "goal": "maximize", "strategy": "greedy_prediction", "threshold": None, "extra": 1}).status_code == 422
    assert client.post("/api/custom/preview", json={"dataset_id": "../bad", "goal": "maximize", "strategy": "greedy_prediction", "threshold": None}).status_code == 422
    assert client.get("/api/datasets/{bad").status_code == 400
    with pytest.raises(ValidationError):
        api.CustomCreateRequest.model_validate({"dataset_id": "dataset_" + "a" * 32, "goal": "maximize", "strategy": "random", "budget": 2, "threshold": None, "output_dir": "C:/bad"})
    with pytest.raises(ValidationError):
        api.IntakeSchemaRequest.model_validate({"roles": {"a": "control"}, "display_names": {}, "units": {}, "dataset_name": "x", "path": "C:/bad"})


def test_worker_contract_rejects_unknown_fields_and_ids(monkeypatch):
    with pytest.raises(ValueError):
        worker.handle({"operation": "dataset_inspect", "dataset_id": "dataset_" + "a" * 32, "extra": True})
    with pytest.raises(ValueError):
        worker.handle({"operation": "intake_inspect", "intake_id": "../bad"})
    with pytest.raises(Exception):
        worker.handle({"operation": "intake_create", "filename": "../bad.csv", "content_type": "text/csv", "content_b64": base64.b64encode(RAW).decode()})
    with pytest.raises(ValueError):
        worker.handle({"operation": "custom_inspect", "project_id": "p3_" + "z" * 32})

def test_api_warning_gate_requires_all_acknowledgements(client):
    warning = (Path(__file__).resolve().parents[1] / "data" / "nexttest" / "fixtures" / "alloy_tensile_warning_duplicate.csv").read_bytes()
    intake = client.post("/api/intakes", content=warning, headers={"Content-Type": "text/csv", "X-NextTest-Filename": "warning.csv"}).json()["intake"]["intake_id"]
    assert client.post(f"/api/intakes/{intake}/schema", json={"roles": ROLES, "display_names": DISPLAY, "units": UNITS, "dataset_name": "Warning"}).status_code == 200
    gate = client.post(f"/api/intakes/{intake}/gate").json()
    assert gate["status"] == "WARNING"
    blocked = client.post(f"/api/intakes/{intake}/freeze")
    assert blocked.status_code == 400
    ack = client.post(f"/api/intakes/{intake}/acknowledge", json={"warning_ids": [item["id"] for item in gate["warnings"]]})
    assert ack.status_code == 200, ack.text
    frozen = client.post(f"/api/intakes/{intake}/freeze")
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["dataset"]["gate_status"] == "WARNING"
