"""Static P4-A UI contract; behavioral browser checks are in the report."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_observatory_structure_and_fairness_copy():
    text = read("frontend/src/workbench/StrategyObservatory.jsx")
    for fragment in ("STRATEGY INTERFEROMETER", "FAIRNESS RAIL", "RUN FOUNDRY", "BUDGET LENS", "RUN MATRIX", "PAIRED EVIDENCE PLATE", "候选全集事后最优", "IQR", "不是 95% CI", "不生成优胜结论"):
        assert fragment in text, fragment
    assert "seed 输入" not in text
    assert "seed_list" not in text
    assert "产生显著性" not in text


def test_guide_has_no_internal_phase():
    guide = read("frontend/src/workbench/GuideDrawer.jsx")
    assert "V3 P1" not in guide
    assert "V3 / P1" not in guide
    assert "OPERATION MAP" in guide


def test_observatory_entry_is_in_top_navigation_not_a_permanent_mission_card():
    nav = read("frontend/src/workbench/TopNavigation.jsx")
    assert "nt-topnav" in nav
    assert "策略" in nav
    assert "onStrategy" in nav
    app = read("frontend/src/App.jsx")
    assert "StrategyObservatory" in app
    assert "<TopNavigation" in app
    assert "<MissionRail" not in app


def test_seed_interpretation_and_auditor_version_are_visible():
    text = read("frontend/src/workbench/StrategyObservatory.jsx")
    assert "算法随机性" in text
    assert "不是 10 次独立物理实验" in text
    assert "auditor" in text and "semantic_replay" in text
