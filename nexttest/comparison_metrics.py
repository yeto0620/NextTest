"""Pure P4-A metrics: no I/O, model, or UI imports."""

from __future__ import annotations

from statistics import median
from typing import Iterable

METRICS_VERSION = "nexttest_p4a_metrics_v1"
VALID_TERMINAL = {"completed", "stopped_threshold", "candidate_exhausted"}


def quantile(values: Iterable[float], q: float) -> float | None:
    ordered = sorted(float(v) for v in values if v is not None)
    if not ordered:
        return None
    if not 0 <= q <= 1:
        raise ValueError("quantile must be in [0,1]")
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def q1(values: Iterable[float]) -> float | None:
    return quantile(values, 0.25)


def q3(values: Iterable[float]) -> float | None:
    return quantile(values, 0.75)


def iqr(values: Iterable[float]) -> float | None:
    a, b = q1(values), q3(values)
    return None if a is None or b is None else b - a


def best_target(values: Iterable[float], direction: str) -> float | None:
    vals = [float(v) for v in values]
    if not vals:
        return None
    return max(vals) if direction == "maximize" else min(vals)


def oracle_gap(best: float | None, oracle: float | None, direction: str) -> float | None:
    """Direction-normalized: always >=0 and lower is better."""
    if best is None or oracle is None:
        return None
    if direction == "maximize":
        return max(0.0, float(oracle) - float(best))
    if direction == "minimize":
        return max(0.0, float(best) - float(oracle))
    raise ValueError("direction must be maximize or minimize")


def threshold_met(value: float, threshold: float | None, direction: str) -> bool | None:
    if threshold is None:
        return None
    return float(value) >= float(threshold) if direction == "maximize" else float(value) <= float(threshold)


def summarize_cell(cell: dict, oracle: float, direction: str, threshold: float | None) -> dict:
    rounds = cell.get("rounds") or []
    status = cell.get("status", "not_run")
    valid = status in VALID_TERMINAL and bool(rounds)
    targets = [row["revealed_target"] for row in rounds if row.get("revealed_target") is not None]
    best = best_target(targets, direction) if targets else None
    first_threshold = None
    if threshold is not None:
        for row in rounds:
            if threshold_met(row["revealed_target"], threshold, direction):
                first_threshold = int(row["round"])
                break
    return {
        "seed": int(cell["seed"]), "strategy": cell["strategy"], "status": status,
        "valid_for_metrics": valid, "rounds_used": len(rounds),
        "terminal_best_target": best,
        "terminal_oracle_gap": oracle_gap(best, oracle, direction) if valid else None,
        "threshold_reached": (first_threshold is not None) if threshold is not None else None,
        "first_threshold_round": first_threshold,
        "stop_reason": cell.get("stop_reason"),
        "error": cell.get("error"),
    }


def summarize(ledger: dict) -> dict:
    plan = ledger["plan"]
    direction = plan["goal"]
    threshold = plan.get("threshold")
    oracle = ledger["candidate_oracle"]
    strategies = plan["strategies"]
    cells = ledger["cells"]
    by_strategy = {s: [] for s in strategies}
    for cell in cells:
        by_strategy.setdefault(cell["strategy"], []).append(cell)
    strategy_summary = {}
    for strategy in strategies:
        scells = sorted(by_strategy.get(strategy, []), key=lambda c: c["seed"])
        summarized = [summarize_cell(c, oracle, direction, threshold) for c in scells]
        valid = [item for item in summarized if item["valid_for_metrics"]]
        gaps = [item["terminal_oracle_gap"] for item in valid if item["terminal_oracle_gap"] is not None]
        bests = [item["terminal_best_target"] for item in valid if item["terminal_best_target"] is not None]
        status_counts = {status: sum(1 for item in summarized if item["status"] == status) for status in (
            "completed", "stopped_threshold", "candidate_exhausted", "failed", "timeout", "not_run"
        )}
        rounds = {}
        for r in range(1, int(plan["budget"]) + 1):
            rows_r = [row for row in ledger["round_metrics"] if row["strategy"] == strategy and row["round"] == r]
            gap_values = [row["oracle_gap"] for row in rows_r if row["oracle_gap"] is not None]
            best_values = [row["best_revealed_target"] for row in rows_r if row["best_revealed_target"] is not None]
            error_values = [row["prediction_error"] for row in rows_r if row["prediction_error"] is not None]
            rounds[str(r)] = {
                "n": len(gap_values), "planned": len(scells),
                "gap": {"median": median(gap_values) if gap_values else None, "q1": q1(gap_values), "q3": q3(gap_values), "iqr": iqr(gap_values)},
                "best_target": {"median": median(best_values) if best_values else None, "q1": q1(best_values), "q3": q3(best_values), "iqr": iqr(best_values)},
                "prediction_error": {"median": median(error_values) if error_values else None, "q1": q1(error_values), "q3": q3(error_values), "iqr": iqr(error_values)},
            }
        threshold_summary = None
        if threshold is not None:
            threshold_summary = {
                "enabled": True, "success_count": sum(1 for item in summarized if item["threshold_reached"] is True),
                "valid_denominator": len(valid), "planned_denominator": len(scells),
                "first_round_by_seed": {str(item["seed"]): item["first_threshold_round"] for item in summarized if item["threshold_reached"]},
            }
        strategy_summary[strategy] = {
            "planned_denominator": len(scells), "valid_denominator": len(valid),
            "status_counts": status_counts,
            "terminal_best_target": {"median": median(bests) if bests else None, "min": min(bests) if bests else None, "max": max(bests) if bests else None, "q1": q1(bests), "q3": q3(bests), "iqr": iqr(bests)},
            "terminal_oracle_gap": {"median": median(gaps) if gaps else None, "min": min(gaps) if gaps else None, "max": max(gaps) if gaps else None, "q1": q1(gaps), "q3": q3(gaps), "iqr": iqr(gaps)},
            "rounds": rounds, "threshold": threshold_summary,
            "cells": summarized,
        }
    paired = {}
    random_by_seed = {item["seed"]: item for item in strategy_summary.get("random", {}).get("cells", [])}
    for strategy in strategies:
        if strategy == "random":
            continue
        rows = []
        for cell in strategy_summary[strategy]["cells"]:
            ref = random_by_seed.get(cell["seed"])
            if ref and cell["valid_for_metrics"] and ref["valid_for_metrics"] and cell["terminal_oracle_gap"] is not None and ref["terminal_oracle_gap"] is not None:
                rows.append({"seed": cell["seed"], "strategy": strategy, "comparator_gap": cell["terminal_oracle_gap"], "random_gap": ref["terminal_oracle_gap"], "difference": cell["terminal_oracle_gap"] - ref["terminal_oracle_gap"]})
        diffs = [row["difference"] for row in rows]
        paired[strategy] = {"n": len(rows), "planned": len(strategy_summary[strategy]["cells"]), "median_difference": median(diffs) if diffs else None, "min": min(diffs) if diffs else None, "max": max(diffs) if diffs else None, "rows": rows}
    complete = all(cell.get("status") in VALID_TERMINAL for cell in cells) and len(cells) == len(strategies) * len(plan["seeds"])
    labels = {"random": "随机对照", "greedy_prediction": "预测优先", "max_disagreement": "最大分歧"}
    if not complete or not plan.get("eligible_for_comparison_claim", False):
        conclusion = "计划未完整执行，或这是不可用于比较结论的 Quick Rehearsal；当前只展示运行状态，不生成策略差异结论。"
    else:
        medians = {s: strategy_summary[s]["terminal_oracle_gap"]["median"] for s in strategies}
        if any(value is None for value in medians.values()):
            conclusion = "有效分母不足，当前不生成策略差异结论。"
        else:
            ordered = sorted(strategies, key=lambda s: (medians[s], s))
            lead = ordered[0]
            gap_span = max(medians.values()) - min(medians.values())
            if gap_span <= 1e-12:
                conclusion = f"在当前冻结数据包、{len(plan['seeds'])} 个固定种子、每个最多 {plan['budget']} 次历史揭示下，三种策略的终轮候选差距中位数没有可区分差异；这只描述当前数据包的历史回放。"
            else:
                lead_label = labels.get(lead, lead)
                reversals = 0
                if lead != "random":
                    reversals = sum(1 for row in paired.get(lead, {}).get("rows", []) if row["difference"] > 0)
                conclusion = f"在当前冻结数据包、{len(plan['seeds'])} 个固定种子、每个最多 {plan['budget']} 次历史揭示下，{lead_label}的终轮候选差距中位数较低；仍有 {reversals} 个种子与随机对照的方向相反。该结果只适用于当前冻结数据包与历史回放协议，不表示显著优于、更智能或可跨数据集泛化。"
    return {
        "metrics_version": METRICS_VERSION,
        "direction": direction, "target": plan["target"], "threshold": threshold,
        "planned_cells": len(strategies) * len(plan["seeds"]), "observed_cells": len(cells),
        "complete": complete, "eligible_for_comparison_claim": bool(plan.get("eligible_for_comparison_claim", False)),
        "strategies": strategy_summary, "paired": paired,
        "candidate_oracle": oracle, "conclusion": conclusion,
        "conclusion_version": "nexttest_p4a_conclusion_v1",
    }
