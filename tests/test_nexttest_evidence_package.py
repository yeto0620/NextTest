"""P5-B deterministic, fail-closed defense evidence packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexttest import evidence_package as package
from nexttest.web import api

P2_ID = "p2_" + "a" * 32
P3_ID = "p3_" + "b" * 32


def _snapshot(project_id=P2_ID, *, revealed_count=1, history=(), status="ready"):
    return {
        "snapshot_version": "nexttest_p2_snapshot_v1",
        "project_id": project_id,
        "status": status,
        "goal": "maximize",
        "threshold": None,
        "budget": 3,
        "remaining_budget": 2,
        "strategy": "greedy_prediction",
        "seed": 20261026,
        "revealed_count": revealed_count,
        "observed_count": 252,
        "candidate_count": 88,
        "test_count": 84,
        "current_model_sha": "c" * 64,
        "initial_model_sha": "d" * 64,
        "split_sha256": "e" * 64,
        "source_canonical_sha256": "f" * 64,
        "observed_row_ids_sha256": "1" * 64,
        "test_sha256": "2" * 64,
        "historical_replay": True,
    }


def _audit(project_id=P2_ID, *, status="ready", test_unchanged=True, models_present=True):
    return {
        "audit_version": "nexttest_p2_audit_v1",
        "project_id": project_id,
        "status": status,
        "event_count": 4,
        "event_chain_sha256": "3" * 64,
        "tree_sha256": "4" * 64,
        "project_manifest_sha256": "5" * 64,
        "source_canonical_sha256": "6" * 64,
        "split_sha256": "7" * 64,
        "test_sha256": "8" * 64,
        "observed_count": 253,
        "candidate_count": 88,
        "test_count": 84,
        "test_unchanged": test_unchanged,
        "models_present": models_present,
        "historical_replay": True,
    }


def _history():
    return [
        {"round": 1, "row_id": "row-000026", "prediction": 62.01822895802379, "revealed_target": 71.29871316, "absolute_error": 9.280484201976215, "strategy": "greedy_prediction"},
        {"round": 2, "row_id": "row-000031", "prediction": 65.5, "revealed_target": 70.0, "absolute_error": 4.5, "strategy": "random"},
    ]


def _view(kind="p2", *, history=None, revealed_count=None, pending=None, extra=None):
    history = _history() if history is None else history
    count = len(history) if revealed_count is None else revealed_count
    snapshot = _snapshot(P3_ID if kind == "p3" else P2_ID, revealed_count=count, history=history)
    if kind == "p3":
        snapshot.update({"dataset_id": "dataset_" + "9" * 32, "dataset_display_name": "Alloy", "dataset_short_id": "alloy", "user_data_replay": True})
    view = {
        "snapshot": snapshot,
        "audit": _audit(P3_ID if kind == "p3" else P2_ID),
        "history": history,
        "pending": pending,
    }
    if kind == "p3":
        view["dataset"] = {
            "dataset_id": "dataset_" + "9" * 32,
            "display_name": "Alloy",
            "short_id": "alloy",
            "target": {"name": "tensile_strength_ksi", "display_name": "Tensile strength", "unit": "ksi"},
            "features": [{"name": "temperature_c", "display_name": "Temperature", "unit": "degC"}],
            "units": {"temperature_c": "degC", "tensile_strength_ksi": "ksi"},
            "unit_not_verified": True,
            "counts": {"train": 30, "candidate": 10, "test": 10, "groups": 50},
            "gate_status": "passed",
            "sha256": {"input": "a" * 64, "schema": "b" * 64},
            "historical_replay": True,
        }
    if extra:
        view.update(extra)
    return view


def test_p2_and_p3_normal_packages_have_exact_schema():
    for kind, project_id in (("p2", P2_ID), ("p3", P3_ID)):
        value = package.build_evidence_package(_view(kind))
        assert list(value) == [
            "schema_version", "project_id", "dataset_public_metadata", "snapshot_public",
            "audit_public", "revealed_history_only", "defense_brief", "limitations",
            "payload_sha256", "markdown",
        ]
        assert value["schema_version"] == package.SCHEMA_VERSION
        assert value["project_id"] == project_id
        assert value["defense_brief"]["revealed_count"] == 2
        assert value["defense_brief"]["evidence_status"] == "available"
        assert value["defense_brief"]["max_absolute_error"] == 9.280484201976215
        assert value["payload_sha256"] == package._hash(package.payload_without_hash(value))
        assert package.verify_payload_hash(value)
        assert "pending" not in value
        assert value["revealed_history_only"][0]["row_id"] == "row-000026"
        assert "test_labels" not in json.dumps(value, ensure_ascii=False)


def test_no_revealed_history_is_insufficient_not_zero_filled():
    value = package.build_evidence_package(_view(history=[], revealed_count=0))
    brief = value["defense_brief"]
    assert brief["revealed_count"] == 0
    assert brief["mae"] is None
    assert brief["max_absolute_error"] is None
    assert brief["evidence_status"] == "insufficient"
    assert "证据不足" in brief["summary"]
    assert "证据不足" in value["markdown"]


def test_pending_hidden_target_and_test_path_key_csv_are_never_serialized():
    pending = {
        "row_id": "row-999999",
        "controls": {"x": 1.0},
        "prediction": 1.0,
        "disagreement": 0.5,
        "target": 999.0,
        "revealed_target": 999.0,
        "test_labels": {"row-test-1": 999.0},
        "raw_csv": "a,b\n1,2\n",
        "path": "C:\\private\\secret.csv",
        "api_key": "sk-should-not-appear",
    }
    extra = {
        "raw_path": "D:\\private\\all.csv",
        "test_rows": ["row-test-1"],
        "NEXTEST_LLM_API_KEY": "sk-should-not-appear",
        "raw_audit": {"path": "C:\\audit.json"},
    }
    value = package.build_evidence_package(_view(pending=pending, extra=extra))
    text = json.dumps(value, ensure_ascii=False)
    for secret in ("999.0", "row-test-1", "C:\\\\private", "sk-should-not-appear", "raw_csv", "test_rows", "raw_audit", "NEXTEST_LLM_API_KEY"):
        assert secret not in text
    assert "row-999999" not in text
    assert "target_hidden" not in text


def test_audit_failure_is_fail_closed_and_never_builds_partial_package():
    view = _view()
    view["audit"]["test_unchanged"] = False
    with pytest.raises(package.EvidencePackageError):
        package.build_evidence_package(view)
    view = _view()
    view["audit"]["status"] = "awaiting"
    with pytest.raises(package.EvidencePackageError):
        package.build_evidence_package(view)


def test_sha_is_stable_and_markdown_numbers_match_json():
    first = package.build_evidence_package(_view())
    second = package.build_evidence_package(_view())
    assert first["payload_sha256"] == second["payload_sha256"]
    assert first["markdown"] == second["markdown"]
    expected = hashlib.sha256(
        json.dumps({key: value for key, value in first.items() if key != "payload_sha256"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert first["payload_sha256"] == expected
    for key in ("mae", "max_absolute_error"):
        number = first["defense_brief"][key]
        assert json.dumps(number, ensure_ascii=False) in first["markdown"]


def test_api_p2_and_p3_schema_and_audit_failure(monkeypatch):
    client = TestClient(api.app, base_url="http://127.0.0.1:8501")
    monkeypatch.setattr(api.bridge, "inspect", lambda pid: _view("p2"))
    monkeypatch.setattr(api.bridge, "custom_inspect", lambda pid: _view("p3"))
    response = client.get(f"/api/projects/{P2_ID}/evidence-package")
    assert response.status_code == 200, response.text
    assert set(response.json()) == {
        "schema_version", "project_id", "dataset_public_metadata", "snapshot_public",
        "audit_public", "revealed_history_only", "defense_brief", "limitations",
        "payload_sha256", "markdown",
    }
    response = client.get(f"/api/custom/projects/{P3_ID}/evidence-package")
    assert response.status_code == 200, response.text
    assert response.json()["project_id"] == P3_ID

    bad = _view("p2")
    bad["audit"]["models_present"] = False
    monkeypatch.setattr(api.bridge, "inspect", lambda pid: bad)
    response = client.get(f"/api/projects/{P2_ID}/evidence-package")
    assert response.status_code == 503
    assert "detail" in response.json()


def test_existing_project_tree_is_unchanged_by_package_route():
    client = TestClient(api.app, base_url="http://127.0.0.1:8501")
    cases = [
        (Path("artifacts/nexttest_p2/projects"), "p2_", "/api/projects/{}/evidence-package", api.bridge.inspect),
        (Path("runs/nexttest_projects"), "p3_", "/api/custom/projects/{}/evidence-package", api.bridge.custom_inspect),
    ]
    checked = 0
    for root, prefix, route, _inspect in cases:
        if not root.is_dir():
            continue
        candidates = sorted(path for path in root.glob(prefix + "*") if path.is_dir())
        if not candidates:
            continue
        project = candidates[0]
        before = package.tree_sha256(project)
        response = client.get(route.format(project.name))
        assert response.status_code == 200, response.text
        after = package.tree_sha256(project)
        assert before == after
        checked += 1
    if checked == 0:
        pytest.skip("no existing read-only projects available")
