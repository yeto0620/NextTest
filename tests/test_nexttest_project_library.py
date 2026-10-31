"""P5-C read-only project library and pairwise comparability checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexttest import evidence_package
from nexttest import project_library
from nexttest.web import api

P2_A = "p2_" + "1" * 32
P2_B = "p2_" + "2" * 32
P3_A = "p3_" + "3" * 32
P3_B = "p3_" + "4" * 32
DATASET_A = "dataset_" + "a" * 32
DATASET_B = "dataset_" + "b" * 32


def _history():
    return [
        {"round": 1, "row_id": "row-000026", "prediction": 62.0, "revealed_target": 71.0, "absolute_error": 9.0, "strategy": "greedy_prediction"},
        {"round": 2, "row_id": "row-000031", "prediction": 65.0, "revealed_target": 70.0, "absolute_error": 5.0, "strategy": "random"},
    ]


def _view(kind="p2", project_id=P2_A, *, dataset_id=None, source="a" * 64, split="b" * 64, history=None, pending=None, extra=None):
    history = _history() if history is None else history
    dataset_id = dataset_id or (DATASET_A if kind == "p3" else "uci_concrete_compressive_strength")
    snapshot = {
        "snapshot_version": "nexttest_p3_snapshot_v1" if kind == "p3" else "nexttest_p2_snapshot_v1",
        "project_id": project_id, "status": "ready", "goal": "maximize", "threshold": None,
        "budget": 3, "remaining_budget": 1, "strategy": "greedy_prediction", "seed": 20261026,
        "revealed_count": len(history), "observed_count": 30, "candidate_count": 9, "test_count": 10,
        "current_model_sha": "c" * 64, "initial_model_sha": "d" * 64,
        "split_sha256": split, "source_canonical_sha256": source,
        "observed_row_ids_sha256": "e" * 64, "test_sha256": "f" * 64,
        "historical_replay": True,
    }
    if kind == "p3":
        snapshot.update({"dataset_id": dataset_id, "dataset_display_name": "Alloy", "dataset_short_id": "alloy", "user_data_replay": True})
    view = {
        "snapshot": snapshot,
        "audit": {
            "audit_version": "nexttest_p3_audit_v1" if kind == "p3" else "nexttest_p2_audit_v1",
            "project_id": project_id, "status": "ready", "event_count": 4,
            "event_chain_sha256": "9" * 64, "tree_sha256": "8" * 64,
            "project_manifest_sha256": "7" * 64, "source_canonical_sha256": source,
            "split_sha256": split, "test_sha256": "f" * 64,
            "observed_count": 30, "candidate_count": 9, "test_count": 10,
            "test_unchanged": True, "models_present": True,
            "historical_replay": True,
        },
        "history": history,
        "pending": pending,
    }
    if kind == "p3":
        view["dataset"] = {
            "dataset_id": dataset_id, "display_name": "Alloy", "short_id": "alloy",
            "target": {"name": "tensile_strength_ksi", "display_name": "Tensile strength", "unit": "ksi"},
            "features": [{"name": "temperature_c", "display_name": "Temperature", "unit": "degC"}],
            "units": {"temperature_c": "degC", "tensile_strength_ksi": "ksi"},
            "unit_not_verified": True, "counts": {"train": 30, "candidate": 10, "test": 10, "groups": 50},
            "gate_status": "passed", "sha256": {"input": "a" * 64, "schema": "b" * 64},
            "historical_replay": True,
        }
    if extra:
        view.update(extra)
    return view


def _client():
    return TestClient(api.app, base_url="http://127.0.0.1:8501")


def _bind(monkeypatch, views: dict):
    monkeypatch.setattr(project_library, "discover_project_ids", lambda: sorted(views))
    monkeypatch.setattr(api.bridge, "inspect", lambda pid: views[pid])
    monkeypatch.setattr(api.bridge, "custom_inspect", lambda pid: views[pid])


def test_library_is_stable_whitelisted_and_has_count(monkeypatch):
    views = {P3_B: _view("p3", P3_B), P2_A: _view("p2", P2_A), P2_B: _view("p2", P2_B, source="d" * 64, split="c" * 64)}
    _bind(monkeypatch, views)
    response = _client().get("/api/library")
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["schema_version"] == project_library.LIBRARY_SCHEMA
    assert value["count"] == 3
    assert [item["project_id"] for item in value["items"]] == [P2_A, P2_B, P3_B]
    for item in value["items"]:
        assert set(item) == set(project_library.SUMMARY_KEYS)
        text = json.dumps(item, ensure_ascii=False)
        for secret in ("pending", "target", "path", "api_key", "raw_csv", "test_label", "event_chain_sha256\""):
            assert secret not in text
        assert len(item["source_sha256_short"]) == 12
        assert item["audit_status"] == "passed"


def test_library_limit_is_100(monkeypatch):
    views = {}
    for index in range(105):
        pid = f"p2_{index:032x}"
        views[pid] = _view("p2", pid)
    _bind(monkeypatch, views)
    response = _client().get("/api/library")
    assert response.status_code == 200
    value = response.json()
    assert value["count"] == 100
    assert len(value["items"]) == 100
    assert [item["project_id"] for item in value["items"]] == sorted(views)[:100]


def test_audit_failure_is_excluded_and_card_compare_close(monkeypatch):
    good = _view("p2", P2_A)
    views = {P2_A: good, P2_B: good}
    _bind(monkeypatch, views)

    def fail(pid):
        if pid == P2_B:
            from fastapi import HTTPException
            raise HTTPException(503, "audit failed")
        return views[pid]
    monkeypatch.setattr(api.bridge, "inspect", fail)
    library = _client().get("/api/library")
    assert library.status_code == 200
    assert [item["project_id"] for item in library.json()["items"]] == [P2_A]
    assert _client().get(f"/api/library/{P2_B}/card").status_code == 503
    compared = _client().post("/api/library/compare", json={"left_project_id": P2_A, "right_project_id": P2_B})
    assert compared.status_code == 503
    assert compared.json()["detail"]["comparability"] == "audit_failed"
    assert "left" not in compared.json()


def test_card_uses_package_public_facts(monkeypatch):
    _bind(monkeypatch, {P2_A: _view("p2", P2_A)})
    response = _client().get(f"/api/library/{P2_A}/card")
    assert response.status_code == 200, response.text
    card = response.json()
    assert set(card) == set(project_library.CARD_KEYS)
    assert card["schema_version"] == project_library.CARD_SCHEMA
    assert card["summary"]["project_id"] == P2_A
    assert card["defense_brief"]["revealed_count"] == 2
    assert "markdown" not in card
    assert "revealed_history_only" not in card


def test_pending_test_path_key_and_raw_csv_are_never_serialized():
    pending = {"row_id": "row-999999", "target": 999.0, "test_labels": {"row-test": 1}, "path": "C:\\private\\data.csv", "raw_csv": "x,y"}
    extra = {"raw_path": "D:\\secret.csv", "api_key": "sk-secret", "raw_audit": {"path": "C:\\audit.json"}}
    value = evidence_package.build_evidence_package(_view("p2", P2_A, pending=pending, extra=extra))
    text = json.dumps(value, ensure_ascii=False)
    for secret in ("999.0", "row-test", "C:\\\\private", "D:\\\\secret", "sk-secret", "raw_csv", "raw_audit", "raw_path"):
        assert secret not in text
    assert "row-999999" not in text
    assert "pending" not in value


def test_compare_same_source_and_split(monkeypatch):
    left = _view("p3", P3_A, dataset_id=DATASET_A, source="1" * 64, split="2" * 64)
    right = _view("p3", P3_B, dataset_id=DATASET_A, source="1" * 64, split="2" * 64)
    _bind(monkeypatch, {P3_A: left, P3_B: right})
    response = _client().post("/api/library/compare", json={"left_project_id": P3_A, "right_project_id": P3_B})
    assert response.status_code == 200, response.text
    value = response.json()
    assert set(value) == set(project_library.COMPARE_KEYS)
    assert value["schema_version"] == project_library.COMPARABILITY_SCHEMA
    assert value["comparability"] == "comparable_same_source_and_split"
    assert value["shared_facts"]["same_source_and_split"] is True
    assert value["left"]["revealed_count"] == 2
    assert value["left"]["mae"] == 7.0
    assert value["left"]["max_error"] == 9.0
    assert value["shared_facts"]["disclaimer"] == project_library.DESCRIPTIVE_DISCLAIMER
    assert "策略优越" in value["shared_facts"]["disclaimer"]


def test_compare_same_dataset_different_split(monkeypatch):
    left = _view("p3", P3_A, dataset_id=DATASET_A, split="2" * 64)
    right = _view("p3", P3_B, dataset_id=DATASET_A, split="3" * 64)
    _bind(monkeypatch, {P3_A: left, P3_B: right})
    value = _client().post("/api/library/compare", json={"left_project_id": P3_A, "right_project_id": P3_B}).json()
    assert value["comparability"] == "same_dataset_but_different_split"
    assert value["shared_facts"]["same_dataset"] is True
    assert value["shared_facts"]["same_split_sha256"] is False


def test_compare_different_dataset(monkeypatch):
    left = _view("p3", P3_A, dataset_id=DATASET_A, source="1" * 64, split="2" * 64)
    right = _view("p3", P3_B, dataset_id=DATASET_B, source="3" * 64, split="4" * 64)
    _bind(monkeypatch, {P3_A: left, P3_B: right})
    value = _client().post("/api/library/compare", json={"left_project_id": P3_A, "right_project_id": P3_B}).json()
    assert value["comparability"] == "different_dataset"
    assert value["shared_facts"]["same_dataset"] is False


def test_no_reveal_is_null_not_zero(monkeypatch):
    view = _view("p2", P2_A, history=[])
    _bind(monkeypatch, {P2_A: view})
    card = _client().get(f"/api/library/{P2_A}/card").json()
    assert card["defense_brief"]["mae"] is None
    assert card["defense_brief"]["max_absolute_error"] is None
    assert card["defense_brief"]["evidence_status"] == "insufficient"


def test_compare_request_forbids_extra_and_bad_ids(monkeypatch):
    _bind(monkeypatch, {P2_A: _view("p2", P2_A)})
    assert _client().post("/api/library/compare", json={"left_project_id": P2_A, "right_project_id": P2_A, "extra": 1}).status_code == 422
    assert _client().post("/api/library/compare", json={"left_project_id": "../bad", "right_project_id": P2_A}).status_code == 422


def test_library_routes_leave_existing_project_trees_unchanged():
    roots = [Path("artifacts/nexttest_p2/projects"), Path("runs/nexttest_projects")]
    projects = []
    for root in roots:
        if root.is_dir():
            children = sorted(path for path in root.iterdir() if path.is_dir() and path.name.startswith(("p2_", "p3_")))
            if children:
                projects.append(children[0])
    if not projects:
        pytest.skip("no existing read-only projects available")
    before = {str(path): evidence_package.tree_sha256(path) for path in projects}
    client = _client()
    for project in projects:
        response = client.get(f"/api/library/{project.name}/card")
        assert response.status_code == 200, response.text
    after = {str(path): evidence_package.tree_sha256(path) for path in projects}
    assert before == after
