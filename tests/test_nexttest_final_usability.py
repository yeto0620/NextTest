"""Final UI closure: concise tables and actionable recovery guidance."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_research_table_defaults_to_three_controls_and_can_expand_all():
    atlas = read("frontend/src/workbench/PossibilityAtlas.jsx")
    assert "const [expanded, setExpanded] = useState(false)" in atlas
    assert "meta.features.slice(0, 3)" in atlas
    assert "mode === 'research' && expanded" in atlas
    assert "全部 ${meta.features.length} 列" in atlas
    assert "aria-expanded={expanded}" in atlas
    assert "controlEntries(controls, includeAge)" in read("frontend/src/workbench/SelectionDetail.jsx")


def test_candidate_status_and_empty_state_use_plain_next_step_language():
    atlas = read("frontend/src/workbench/PossibilityAtlas.jsx")
    assert "暂时没有可比较方案" in atlas
    assert "打开“数据”检查字段与闸门" in atlas
    assert "模型分歧" in atlas
    assert "预测已锁" in atlas
    assert "结果已看" in atlas
    assert "结果未看" in atlas


def test_global_errors_name_a_recovery_action():
    app = read("frontend/src/App.jsx")
    assert "function WorkbenchMessage" in app
    assert "当前步骤没有完成" in app
    assert "只读恢复" in app
    assert "检查数据" in app
    assert "重新读取页面" in app
    assert "nt-action-message" in app


def test_uncertain_update_offers_read_only_refresh_without_retrying():
    bench = read("frontend/src/workbench/ExperimentBench.jsx")
    assert "本轮已停止，记录仍保留" in bench
    assert "系统不会自动重试或补写" in bench
    assert "onClick={onRefresh}" in bench
    assert "只读刷新" in bench


def test_final_usability_styles_keep_secondary_detail_progressive():
    css = read("frontend/src/nocturne.css")
    assert "Final usability pass" in css
    assert ".nt-table-toolbar" in css
    assert ".nt-action-message" in css
    assert ".nt-unavailable-guided" in css
