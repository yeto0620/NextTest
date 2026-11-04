"""P6 research/explore closure contract tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
NAV = (ROOT / "frontend" / "src" / "workbench" / "TopNavigation.jsx").read_text(encoding="utf-8")
BENCH = (ROOT / "frontend" / "src" / "workbench" / "ExperimentBench.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "src" / "nocturne.css").read_text(encoding="utf-8")


def test_initial_mode_is_research_and_default_view_is_table():
    assert "useState('research')" in APP
    assert "useState('table')" in APP
    assert "setViewMode(next === 'research' ? 'table' : 'atlas')" in APP
    assert "localStorage.setItem('nexttest.mode'" not in APP
    assert "localStorage.setItem(\"nexttest.mode\"" not in APP


def test_research_navigation_has_exact_seven_entries():
    for label in ("观测", "方案", "实验", "策略", "证据", "档案", "数据"):
        assert f"label: '{label}'" in NAV
    research = NAV.split("const RESEARCH_ITEMS", 1)[1].split("const EXPLORE_ITEMS", 1)[0]
    assert research.count("label:") == 7
    assert "AI 助手" in NAV
    assert "导出当前项目" in NAV


def test_explore_navigation_is_only_guide_atlas_experience_story():
    explore = NAV.split("const EXPLORE_ITEMS", 1)[1].split("export default", 1)[0]
    assert explore.count("label:") == 4
    for label in ("导览", "航图", "体验", "故事"):
        assert f"label: '{label}'" in explore
    assert "演示模式" in NAV
    assert "使用方法" in NAV


def test_mode_switches_components_not_only_labels():
    assert "mode === 'research' && <ResearchCockpit" in APP
    assert "mode === 'explore' && <MissionDeck" in APP
    assert "mode === 'research' && <ResearchLedger" in APP
    assert "<DataDock" in APP and "mode={mode}" in APP
    assert "<ProjectLibrary" in APP
    assert "<EvidenceAssistant" in APP
    assert "<PresentationStage" in APP
    assert "<GuideDrawer" in APP
    assert "nt-density-${mode}" in APP
    assert ".nt-density-research" in CSS


def test_shared_state_is_passed_to_both_modes():
    for token in ("preview", "selectedCandidate", "selection", "strategy", "view"):
        assert token in APP
    assert "mode={mode}" in BENCH
    assert "viewMode={viewMode}" in APP
    assert "onViewMode={setViewMode}" in APP


def test_research_language_is_compact_in_navigation_and_bench():
    assert "观测" in NAV and "方案" in NAV and "实验" in NAV
    assert "AI 助手" in NAV
    assert "本地工具链负责流程" in (ROOT / "frontend" / "src" / "workbench" / "EvidenceAssistant.jsx").read_text(encoding="utf-8")


def test_explore_has_teaching_and_story_components():
    deck = (ROOT / "frontend" / "src" / "workbench" / "MissionDeck.jsx").read_text(encoding="utf-8")
    guide = (ROOT / "frontend" / "src" / "workbench" / "GuideDrawer.jsx").read_text(encoding="utf-8")
    stage = (ROOT / "frontend" / "src" / "workbench" / "PresentationStage.jsx").read_text(encoding="utf-8")
    assert "下一次" in deck
    assert "使用方法" in guide or "导览" in guide
    assert "演示" in stage or "讲述" in stage


def test_no_desktop_or_mobile_requirement_is_smuggled_into_web_shell():
    package = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    assert "electron" not in package.lower()
    assert "tauri" not in package.lower()
