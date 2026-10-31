"""Pure P4-A metric tests; no model or UI."""

from __future__ import annotations

from nexttest.comparison_metrics import best_target, iqr, median, oracle_gap, q1, q3, quantile, summarize, threshold_met, METRICS_VERSION


def test_quantiles_and_iqr_are_descriptive_not_ci():
    values = [0, 10, 20, 30, 40]
    assert quantile(values, 0) == 0
    assert quantile(values, 0.5) == 20
    assert quantile(values, 1) == 40
    assert q1(values) == 10 and q3(values) == 30
    assert iqr(values) == 20


def test_direction_normalized_oracle_gap_and_best():
    assert best_target([2, 9, 4], "maximize") == 9
    assert best_target([2, 9, 4], "minimize") == 2
    assert oracle_gap(9, 12, "maximize") == 3
    assert oracle_gap(2, 0, "minimize") == 2
    assert oracle_gap(12, 0, "minimize") == 12
    assert threshold_met(85, 80, "maximize") is True
    assert threshold_met(85, 80, "minimize") is False


def _ledger(direction="maximize", budget=2):
    plan = {"goal": direction, "budget": budget, "seeds": [1, 2, 3], "strategies": ["random", "greedy_prediction", "max_disagreement"], "target": {"name": "target", "display_name": "Target", "unit": "u"}, "threshold": None, "eligible_for_comparison_claim": True, "comparison_mode": "evidence"}
    cells = []
    rounds = []
    for seed in plan["seeds"]:
        for strategy in plan["strategies"]:
            values = [10 + seed % 3, 12 + seed % 3]
            status = "completed"
            cells.append({"seed": seed, "strategy": strategy, "status": status, "stop_reason": "budget_exhausted", "rounds": [{"round": i + 1, "revealed_target": v, "best_revealed_target": max(values[: i + 1]) if direction == "maximize" else min(values[: i + 1]), "oracle_gap": 0, "absolute_error": 1} for i, v in enumerate(values)]})
            for i, value in enumerate(values):
                rounds.append({"seed": seed, "strategy": strategy, "round": i + 1, "oracle_gap": float((12 - max(values[: i + 1])) if direction == "maximize" else (min(values[: i + 1]) - 10)), "best_revealed_target": value, "prediction_error": 1.0})
    return {"plan": plan, "candidate_oracle": 12.0 if direction == "maximize" else 10.0, "cells": cells, "round_metrics": rounds}


def test_summary_denominators_and_no_zero_fill():
    summary = summarize(_ledger())
    assert summary["metrics_version"] == METRICS_VERSION
    assert summary["planned_cells"] == 9
    assert summary["complete"] is True
    random = summary["strategies"]["random"]
    assert random["planned_denominator"] == 3 and random["valid_denominator"] == 3
    assert random["rounds"]["1"]["n"] == 3
    assert random["rounds"]["1"]["gap"]["median"] is not None
    assert random["terminal_oracle_gap"]["median"] is not None
    assert summary["conclusion"]


def test_missing_and_failed_are_not_zero_and_incomplete_suppresses_conclusion():
    ledger = _ledger()
    ledger["cells"][0]["status"] = "failed"
    ledger["cells"][0]["rounds"] = []
    summary = summarize(ledger)
    assert summary["complete"] is False
    random = summary["strategies"]["random"]
    assert random["status_counts"]["failed"] == 1
    assert random["valid_denominator"] == 2
    assert random["terminal_oracle_gap"]["median"] is not None
    assert "不生成策略差异结论" in summary["conclusion"]


def test_threshold_requires_preexisting_threshold():
    ledger = _ledger()
    ledger["plan"]["threshold"] = 11
    summary = summarize(ledger)
    assert summary["strategies"]["random"]["threshold"]["enabled"] is True
    assert summary["strategies"]["random"]["threshold"]["planned_denominator"] == 3
    assert "success_count" in summary["strategies"]["random"]["threshold"]
    ledger2 = _ledger()
    summary2 = summarize(ledger2)
    assert summary2["strategies"]["random"]["threshold"] is None


def test_all_terminal_statuses_are_accounted_without_zero_fill():
    from nexttest.comparison_audit import _state_after_round
    from nexttest.comparison_metrics import summarize_cell
    plan = {"goal": "maximize", "budget": 3, "threshold": 10.0}
    cells = [
        {"seed": 1, "strategy": "random", "status": "stopped_threshold", "rounds": [{"round": 1, "revealed_target": 11.0, "best_revealed_target": 11.0, "oracle_gap": 1.0, "absolute_error": 0.5}], "stop_reason": "threshold_reached"},
        {"seed": 2, "strategy": "random", "status": "candidate_exhausted", "rounds": [{"round": 1, "revealed_target": 8.0, "best_revealed_target": 8.0, "oracle_gap": 4.0, "absolute_error": 1.0}], "stop_reason": "candidate_pool_empty"},
        {"seed": 3, "strategy": "random", "status": "timeout", "rounds": [], "stop_reason": "cell_time_limit"},
        {"seed": 4, "strategy": "random", "status": "failed", "rounds": [], "stop_reason": "exception", "error": "x"},
        {"seed": 5, "strategy": "random", "status": "not_run", "rounds": [], "stop_reason": "overall_time_limit"},
    ]
    ledger = {"plan": {**plan, "seeds": [1, 2, 3, 4, 5], "strategies": ["random"], "target": {"name": "t", "display_name": "T", "unit": "u"}, "eligible_for_comparison_claim": True}, "candidate_oracle": 12.0, "cells": cells, "round_metrics": []}
    result = summarize(ledger)
    counts = result["strategies"]["random"]["status_counts"]
    assert counts == {"completed": 0, "stopped_threshold": 1, "candidate_exhausted": 1, "failed": 1, "timeout": 1, "not_run": 1}
    assert result["strategies"]["random"]["valid_denominator"] == 2
    assert "不生成策略差异结论" in result["conclusion"]
    assert summarize_cell(cells[0], 12.0, "maximize", 10.0)["terminal_oracle_gap"] == 1.0
    assert summarize_cell(cells[1], 12.0, "maximize", 10.0)["valid_for_metrics"] is True
    assert summarize_cell(cells[2], 12.0, "maximize", 10.0)["terminal_oracle_gap"] is None
    assert _state_after_round({"budget": 3}, 1, False, True) == "threshold_reached"
    assert _state_after_round({"budget": 3}, 3, False, False) == "budget_exhausted"
    assert _state_after_round({"budget": 3}, 1, True, False) == "candidate_pool_empty"
