"""P2 UI contract: read-only transition facts, no hidden target, P2 components present."""

from __future__ import annotations

from pathlib import Path

from scripts import nexttest_ui_worker as worker

PID = "p2_" + "d" * 32
ROOT = Path(__file__).resolve().parents[1]


def test_project_view_transition_is_read_only_and_has_no_target(tmp_path, monkeypatch):
    monkeypatch.setattr(worker.exp, "PROJECT_ROOT", tmp_path)
    created = worker.handle({"operation": "create", "project_id": PID, "goal": "maximize",
                             "threshold": None, "budget": 2, "strategy": "greedy_prediction"})["data"]
    assert created["transition"] is None
    pending_view = worker.handle({"operation": "recommend", "project_id": PID})["data"]
    assert pending_view["transition"] is None
    assert "revealed_target" not in pending_view["pending"]
    assert "target" not in pending_view["pending"]
    rec = pending_view["pending"]["recommendation_id"]
    revealed = worker.handle({"operation": "reveal", "project_id": PID, "recommendation_id": rec})["data"]
    transition = revealed["transition"]
    assert transition is not None
    assert {"before", "after"} == set(transition)
    for key in ("model_sha", "revealed_count", "remaining_budget", "observed_count", "candidate_count"):
        assert key in transition["before"] and key in transition["after"]
    assert transition["before"]["model_sha"] != transition["after"]["model_sha"]
    assert transition["after"]["observed_count"] == transition["before"]["observed_count"] + 1
    assert transition["after"]["remaining_budget"] == transition["before"]["remaining_budget"] - 1
    assert "target" not in transition["before"] and "target" not in transition["after"]


def test_p2_components_and_boundary_copy_are_present():
    names = [
        "QuestionRibbon", "StrategyLens", "HypothesisSlip", "EvidencePrism",
        "ReflectionCard", "ResearchLedger", "ScienceScenes",
    ]
    for name in names:
        assert (ROOT / "frontend" / "src" / "workbench" / f"{name}.jsx").is_file()
    hypothesis = (ROOT / "frontend" / "src" / "workbench" / "HypothesisSlip.jsx").read_text(encoding="utf-8")
    prism = (ROOT / "frontend" / "src" / "workbench" / "EvidencePrism.jsx").read_text(encoding="utf-8")
    reflection = (ROOT / "frontend" / "src" / "workbench" / "ReflectionCard.jsx").read_text(encoding="utf-8")
    assert "只存浏览器内存" in hypothesis
    assert "fetch(" not in hypothesis and "CompressiveStrength" not in hypothesis
    assert "尚未公布" in prism
    assert "不证明策略整体更优" in reflection
    assert "概率" in reflection and "置信区间" in reflection
