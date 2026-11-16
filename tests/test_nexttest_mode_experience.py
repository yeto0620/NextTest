"""Research and popular-science modes must be different experiences over one fact source."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_home_has_one_plain_language_path():
    cockpit = read("frontend/src/workbench/ResearchCockpit.jsx")
    for label in ("选方法", "锁预测", "看答案"):
        assert label in cockpit
    assert 'className="nt-replay-cta nt-head-action"' in cockpit
    assert "先看预测" in cockpit and "再看答案" in cockpit


def test_app_removes_duplicate_journey_and_does_not_force_tour():
    app = read("frontend/src/App.jsx")
    assert "<JourneyProgress" not in app
    assert "const [tourOpen, setTourOpen] = useState(false)" in app


def test_research_cockpit_exposes_details_only_on_request():
    cockpit = read("frontend/src/workbench/ResearchCockpit.jsx")
    assert '<details className="nt-replay-explore">' in cockpit
    assert '<details className="nt-cockpit-more nt-replay-more">' in cockpit
    assert cockpit.index('nt-replay-cta') < cockpit.index('nt-replay-explore')
    assert cockpit.index('nt-replay-explore') < cockpit.index('nt-replay-more')


def test_research_home_shows_prediction_without_pretending_it_is_measured():
    cockpit = read("frontend/src/workbench/ResearchCockpit.jsx")
    assert "模型预测" in cockpit and "历史实测" in cockpit
    assert "锁定后揭晓" in cockpit
    assert "仅预览 · 尚未锁定" in cockpit
    assert "view?.pending?.prediction" in cockpit
    assert "revealed_target" not in cockpit
    assert "pending ? '本条尚未揭晓'" in cockpit
    assert "ended ? '查看本次结果'" in cockpit


def test_mode_switch_explains_and_exposes_selection_state():
    nav = read("frontend/src/workbench/TopNavigation.jsx")
    assert "研究：精简操作、完整字段" in nav
    assert "科普：逐步解释、图形引导" in nav
    assert "aria-pressed={mode === 'research'}" in nav
    assert "aria-pressed={mode === 'explore'}" in nav


def test_modes_share_facts_but_render_different_structures():
    app = read("frontend/src/App.jsx")
    bench = read("frontend/src/workbench/ExperimentBench.jsx")
    trail = read("frontend/src/workbench/EvidenceTrail.jsx")
    assert "mode === 'research' && <ResearchCockpit" in app
    assert "mode === 'explore' && <MissionDeck" in app
    assert "!research &&" in bench and "<HypothesisSlip" in bench and "<ReflectionCard" in bench
    assert "mode === 'research' && <ResearchLedger" in app
    assert "!research && <ScienceScenes" in trail
