"""The UI worker exposes only revealed historical labels."""

from __future__ import annotations

import pytest

from scripts import nexttest_ui_worker as worker


PID = "p2_" + "b" * 32


def test_landscape_exposes_only_observed_training_rows():
    base, split, _ = worker.exp.load_frozen_base()
    result = worker.handle({"operation": "landscape"})["data"]
    assert result["scope"] == "observed_training_only"
    assert result["count"] == 252
    assert result["split_sha256"] == split["split_sha256"]
    observed_ids = set(base.observed.row_ids)
    candidate_ids = set(base.candidates.row_ids)
    test_ids = set(base.test.row_ids)
    assert {row["_row_id"] for row in result["rows"]} == observed_ids
    assert observed_ids.isdisjoint(candidate_ids | test_ids)
    assert all("CompressiveStrength" in row for row in result["rows"])
    with pytest.raises(ValueError):
        worker.handle({"operation": "landscape", "include_hidden": True})
    preview = worker.handle({"operation": "preview", "strategy": "greedy_prediction", "goal": "maximize",
                             "threshold": None, "project_id": None})["data"]
    assert preview["scope"] == "candidate_pool_no_labels"
    assert preview["candidate_count"] == 89
    assert all("target" not in row and "CompressiveStrength" not in row for row in preview["rows"])
    assert preview["selected"]["row_id"] in {row["row_id"] for row in preview["rows"]}


def test_worker_replay_progress_and_label_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(worker.exp, "PROJECT_ROOT", tmp_path)
    created = worker.handle({"operation": "create", "project_id": PID, "goal": "maximize",
                             "threshold": None, "budget": 1, "strategy": "greedy_prediction"})["data"]
    assert created["snapshot"]["status"] == "ready"
    assert created["history"] == [] and created["pending"] is None
    pending = worker.handle({"operation": "recommend", "project_id": PID})["data"]
    assert pending["snapshot"]["status"] == "awaiting_user_confirmation"
    assert "revealed_target" not in pending["pending"]
    assert pending["history"] == []
    same = worker.handle({"operation": "inspect", "project_id": PID})["data"]
    assert same["pending"] == pending["pending"]
    done = worker.handle({"operation": "reveal", "project_id": PID,
                          "recommendation_id": pending["pending"]["recommendation_id"]})["data"]
    assert done["snapshot"]["status"] == "budget_exhausted"
    assert len(done["history"]) == 1
    assert done["history"][0]["revealed_target"] > 0
    with pytest.raises(ValueError):
        worker.handle({"operation": "inspect", "project_id": "../outside"})
    with pytest.raises(ValueError):
        worker.handle({"operation": "reveal", "project_id": PID, "recommendation_id": "../bad"})
