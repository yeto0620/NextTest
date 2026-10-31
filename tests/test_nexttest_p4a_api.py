"""P4-A API contract: fixed fields, fixed seeds, export, and audit failure closure."""

from __future__ import annotations

from pathlib import Path
import uuid

import pytest
from fastapi.testclient import TestClient

from nexttest.web import api

DATASET = "dataset_1e5028247271477a868f1aa13a1ac9bd"


@pytest.fixture(scope="module")
def client():
    return TestClient(api.app, base_url="http://127.0.0.1:8501")


def test_comparison_preview_create_run_export(client):
    preview = client.post("/api/comparisons/preview", json={"dataset_id": DATASET, "goal": "maximize", "threshold": None, "budget": 1, "mode": "rehearsal"})
    assert preview.status_code == 200, preview.text
    assert preview.json()["calculation_scale"]["seeds"] == 3
    assert [int(x) for x in preview.json()["plan_preview"]["seeds"]] == [20261026, 20261027, 20261028]
    created = client.post("/api/comparisons", json={"dataset_id": DATASET, "goal": "maximize", "threshold": None, "budget": 1, "mode": "rehearsal", "request_id": "req_" + uuid.uuid4().hex[:24]})
    assert created.status_code == 200, created.text
    cid = created.json()["manifest"]["comparison_id"]
    assert created.json()["state"]["status"] == "planned"
    run = client.post(f"/api/comparisons/{cid}/run", json={"request_id": "req_" + "2" * 20})
    assert run.status_code == 200, run.text
    value = run.json()
    assert value["audit"]["valid"] is True
    assert value["summary"]["planned_cells"] == 9
    assert value["plan"]["eligible_for_comparison_claim"] is False
    inspected = client.get(f"/api/comparisons/{cid}")
    assert inspected.status_code == 200, inspected.text
    assert inspected.json()["summary"]["complete"] is True
    export = client.get(f"/api/comparisons/{cid}/export?format=csv")
    assert export.status_code == 200, export.text
    assert "seed,strategy,round" in export.json()["content"]
    assert "revealed_target" in export.json()["content"].splitlines()[0]


def test_comparison_rejects_seed_override_and_extra_fields(client):
    base = {"dataset_id": DATASET, "goal": "maximize", "threshold": None, "budget": 1, "mode": "evidence", "request_id": "req_" + uuid.uuid4().hex[:24]}
    assert client.post("/api/comparisons", json={**base, "seeds": [1, 2, 3]}).status_code == 422
    assert client.post("/api/comparisons", json={**base, "strategies": ["random"]}).status_code == 422
    assert client.post("/api/comparisons", json={**base, "data_path": "C:/bad.csv"}).status_code == 422
    assert client.post("/api/comparisons", json={**base, "dataset_id": "../bad"}).status_code == 422
    assert client.post("/api/comparisons", json={**base, "request_id": "../../bad"}).status_code == 422
    assert client.get("/api/comparisons/not-a-comparison").status_code == 400
    assert client.get("/api/comparisons/cmp_" + "a" * 32 + "/export?format=pdf").status_code == 400
