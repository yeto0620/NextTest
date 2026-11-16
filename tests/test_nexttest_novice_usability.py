"""Novice-facing UI contract for the four-step historical replay journey."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_written_guide_defines_one_sentence_and_four_step_journey():
    guide = read("docs/NOVICE_USABILITY_GUIDE.md")
    assert "NextTest 用已有实验数据" in guide
    assert "看数据 → 比方案 → 锁预测 → 看结果" in guide
    assert "模型分歧" in guide
    assert "本轮完成" in guide


def test_main_flow_is_visible_without_duplicate_progress_bars():
    app = read("frontend/src/App.jsx")
    home = read("frontend/src/workbench/ResearchCockpit.jsx")
    nav = read("frontend/src/workbench/TopNavigation.jsx")
    assert "<JourneyProgress" not in app
    assert "完成一次回放的步骤" in home
    for label in ("开始", "方案", "回放", "结果"):
        assert f"label: '{label}'" in nav
    assert "查看结果" not in home


def test_first_run_tour_uses_plain_language_and_five_steps():
    tour = read("frontend/src/workbench/NewUserTour.jsx")
    assert tour.count("eyebrow:") == 5
    assert "模型分歧只表示多个模型意见不一致" in tour
    assert "预算表示本轮最多查看几条历史记录" in tour
    assert "没有 DeepSeek Key 时，本地帮助仍可解释流程" in tour
    assert "预测差值异" not in tour


def test_experiment_closes_each_round_and_does_not_claim_saved_before_lock():
    bench = read("frontend/src/workbench/ExperimentBench.jsx")
    prism = read("frontend/src/workbench/EvidencePrism.jsx")
    assert "本轮完成" in bench
    assert "查看本轮总结" in bench
    assert "继续下一轮" in bench
    assert "尚未锁定预测；历史结果保持隐藏" in prism
    assert "预测已保存；等待一次人工确认" not in prism


def test_local_help_entry_is_not_disabled_without_deepseek():
    nav = read("frontend/src/workbench/TopNavigation.jsx")
    app = read("frontend/src/App.jsx")
    assert "本地帮助可用" in nav
    assert "disabled={llmReady === false}" not in nav
    assert "className=\"nt-sidebar-assistant\"" in nav
    assert "onAssistant={() => setAssistantOpen(true)}" in app
    assert "disabled={llmReady === false}" not in app


def test_removed_confusing_typo_from_frontend_source():
    text = "\n".join(path.read_text(encoding="utf-8") for path in FRONTEND.rglob("*.jsx"))
    assert "预测差值异" not in text
