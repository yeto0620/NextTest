"""Web API contract against a temporary P2 project store."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from nexttest.web import api
from scripts import nexttest_ui_worker as worker


PID = "p2_" + "c" * 32


def test_historical_replay_api_preserves_label_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(worker.exp, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(api.bridge, "new_project_id", lambda: PID)
    monkeypatch.setattr(api.bridge, "observed_landscape", lambda: worker.handle({"operation": "landscape"})["data"])
    monkeypatch.setattr(api.bridge, "preview", lambda **kw: worker.handle({"operation": "preview", **kw})["data"])
    monkeypatch.setattr(api.bridge, "create", lambda **kw: worker.handle({"operation": "create", **kw})["data"])
    monkeypatch.setattr(api.bridge, "inspect", lambda pid: worker.handle({"operation": "inspect", "project_id": pid})["data"])
    monkeypatch.setattr(api.bridge, "recommend", lambda pid: worker.handle({"operation": "recommend", "project_id": pid})["data"])
    monkeypatch.setattr(api.bridge, "reveal", lambda pid, rid: worker.handle({"operation": "reveal", "project_id": pid, "recommendation_id": rid})["data"])
    api._landscape.cache_clear()
    assert api.health()["production_trial"] is False
    landscape = api.landscape()
    assert landscape["scope"] == "observed_training_only"
    assert len(landscape["rows"]) == 252
    preview = api.preview(api.PreviewRequest(goal="maximize", strategy="greedy_prediction"))
    assert preview["scope"] == "candidate_pool_no_labels"
    assert preview["candidate_count"] == 89
    assert len(preview["rows"]) == 89
    assert all("target" not in row and "CompressiveStrength" not in row for row in preview["rows"])
    assert preview["selected"]["row_id"] in {row["row_id"] for row in preview["rows"]}
    with pytest.raises(ValidationError):
        api.CreateRequest.model_validate({"goal": "maximize", "strategy": "greedy_prediction", "budget": 1,
                                          "threshold": None, "data_path": "C:/bad.csv"})
    created = api.create_project(api.CreateRequest(goal="maximize", strategy="greedy_prediction", budget=1))
    assert created["snapshot"]["project_id"] == PID
    assert created["history"] == [] and created["pending"] is None
    pending = api.recommend_project(PID)
    assert pending["snapshot"]["status"] == "awaiting_user_confirmation"
    assert "revealed_target" not in pending["pending"]
    assert pending["history"] == []
    assert api.inspect_project(PID)["pending"] == pending["pending"]
    rec_id = pending["pending"]["recommendation_id"]
    revealed = api.reveal_project(PID, api.RevealRequest(recommendation_id=rec_id))
    assert revealed["snapshot"]["status"] == "budget_exhausted"
    assert revealed["history"][0]["revealed_target"] > 0
    assert api.inspect_project(PID)["history"] == revealed["history"]
    with pytest.raises(HTTPException):
        api.inspect_project("../bad")
    with pytest.raises(ValidationError):
        api.RevealRequest(recommendation_id="../../bad")


def test_api_rejects_failed_evidence(monkeypatch):
    monkeypatch.setattr(api.bridge, "inspect", lambda _pid: {
        "snapshot": {"status": "ready"}, "audit": {"status": "ready", "test_unchanged": False, "models_present": True},
    })
    with pytest.raises(HTTPException) as exc:
        api.inspect_project(PID)
    assert exc.value.status_code == 503
    assert "证据校验失败" in exc.value.detail
