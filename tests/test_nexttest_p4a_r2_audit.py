"""P4-A-R2 completion tests: identity, terminal priority, strict types/schema."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from nexttest import comparison
from nexttest.comparison_audit import audit
from nexttest.comparison_metrics import summarize

QUICK = Path("runs/nexttest_comparisons/cmp_f12f872fb20d4685ac8d1b79f91e4988")
EVIDENCE = Path("runs/nexttest_comparisons/cmp_e6e72be86fb94ddc901fa6e76144bd7a")
DATASET = "dataset_1e5028247271477a868f1aa13a1ac9bd"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(root: Path) -> str:
    return hashlib.sha256(json.dumps(sorted((p.relative_to(root).as_posix(), sha(p)) for p in root.rglob("*") if p.is_file())).encode()).hexdigest()


def copy_source(tmp_path, monkeypatch, source=QUICK):
    target = tmp_path / "comparisons"
    target.mkdir(parents=True)
    shutil.copytree(source, target / source.name)
    monkeypatch.setattr(comparison, "COMPARISON_ROOT", target)
    return target / source.name


def events(cell: Path):
    return [json.loads(line) for line in (cell / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def write_events(cell: Path, items: list[dict]):
    prev = ""
    for event in items:
        event["prev_sha"] = prev
        event["event_sha"] = hashlib.sha256(json.dumps({k: v for k, v in event.items() if k != "event_sha"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        prev = event["event_sha"]
    (cell / "events.jsonl").write_text("\n".join(json.dumps(event, sort_keys=True, ensure_ascii=False) for event in items) + ("\n" if items else ""), encoding="utf-8")
    tp = cell / "terminal.json"
    term = json.loads(tp.read_text(encoding="utf-8"))
    term["event_chain_sha"] = prev
    tp.write_text(json.dumps(term, sort_keys=True), encoding="utf-8")


def rebuild(root: Path):
    plan = json.loads((root / "evaluation_plan.json").read_text(encoding="utf-8"))
    base, _, _ = comparison.load_base(plan["dataset_id"])
    ledger = comparison._ledger(root, plan, base)
    summary = summarize(ledger)
    (root / "comparison_ledger.json").write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")
    (root / "comparison_summary.json").write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    comparison._write_hashes(root)


def assert_fail(root: Path):
    before = tree(root)
    result = audit(root, strict=True, require_complete=True)
    assert result["valid"] is False
    assert tree(root) == before
    value = comparison.inspect_comparison(root.name)
    from nexttest.web import api
    with pytest.raises(Exception):
        api._comparison_result(value)


def first(root: Path):
    return root / "runs" / str(comparison.REHEARSAL_SEEDS[0]) / "random"


def test_release_seed_and_strategy_identity(tmp_path, monkeypatch):
    for field, value in (("seed", 20261027), ("strategy", "max_disagreement")):
        root = copy_source(tmp_path / field, monkeypatch)
        cell = first(root)
        items = events(cell)
        items[2]["payload"][field] = value
        write_events(cell, items)
        rebuild(root)
        assert_fail(root)


@pytest.mark.parametrize("status,reason,error", [("timeout", "cell_time_limit", None), ("failed", "exception", "boom")])
def test_full_budget_completed_cannot_be_downgraded(tmp_path, monkeypatch, status, reason, error):
    root = copy_source(tmp_path / status, monkeypatch)
    cell = first(root)
    tp = cell / "terminal.json"
    terminal = json.loads(tp.read_text(encoding="utf-8"))
    terminal.update({"status": status, "stop_reason": reason, "error": error})
    tp.write_text(json.dumps(terminal), encoding="utf-8")
    rebuild(root)
    assert_fail(root)


def test_bool_is_not_int_for_historical_and_hidden(tmp_path, monkeypatch):
    root = copy_source(tmp_path / "bool", monkeypatch)
    cell = first(root)
    items = events(cell)
    items[0]["payload"]["historical_replay"] = 1
    items[0]["payload"]["target_hidden"] = 1
    items[1]["payload"]["target_hidden"] = 1
    items[3]["payload"]["threshold_reached"] = 0
    write_events(cell, items)
    rebuild(root)
    assert_fail(root)


def test_event_top_level_extra_and_terminal_extra_or_missing(tmp_path, monkeypatch):
    root = copy_source(tmp_path / "top_extra", monkeypatch)
    cell = first(root)
    items = events(cell)
    items[0]["unexpected"] = True
    write_events(cell, items)
    rebuild(root)
    assert_fail(root)
    root = copy_source(tmp_path / "terminal_extra", monkeypatch)
    tp = first(root) / "terminal.json"
    terminal = json.loads(tp.read_text(encoding="utf-8"))
    terminal["unexpected"] = 1
    tp.write_text(json.dumps(terminal), encoding="utf-8")
    rebuild(root)
    assert_fail(root)
    root = copy_source(tmp_path / "terminal_missing", monkeypatch)
    tp = first(root) / "terminal.json"
    terminal = json.loads(tp.read_text(encoding="utf-8"))
    del terminal["error"]
    tp.write_text(json.dumps(terminal), encoding="utf-8")
    rebuild(root)
    assert_fail(root)


def test_threshold_priority_and_forgery(tmp_path, monkeypatch):
    # Build a legitimate threshold-stopped copy from the quick rehearsal.
    root = copy_source(tmp_path / "threshold", monkeypatch)
    plan_path = root / "evaluation_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["threshold"] = 0.0
    plan["plan_sha256"] = hashlib.sha256(json.dumps({k: v for k, v in plan.items() if k != "plan_sha256"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
    manifest_path = root / "comparison_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["plan_sha256"] = plan["plan_sha256"]
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    from nexttest.models import train_regression
    from nexttest.strategy import Goal, recommend
    base, _, _ = comparison.load_base(plan["dataset_id"])
    for seed in plan["seeds"]:
        predictor = train_regression(base, seed=seed, evaluate_test=False)
        for strategy in plan["strategies"]:
            cell = root / "runs" / str(seed) / strategy
            items = events(cell)
            rec = recommend(strategy, base.candidates, predictor, goal=Goal("maximize", 0.0), seed=seed, round_index=0)
            items[0]["payload"]["reason"] = rec.reason
            items[3]["payload"]["threshold_reached"] = True
            items[3]["payload"]["state"] = "threshold_reached"
            write_events(cell, items)
            tp = cell / "terminal.json"
            terminal = json.loads(tp.read_text(encoding="utf-8"))
            terminal.update({"status": "stopped_threshold", "stop_reason": "threshold_reached", "threshold_reached": True})
            tp.write_text(json.dumps(terminal), encoding="utf-8")
    rebuild(root)
    assert audit(root, strict=True, require_complete=True)["valid"] is True
    # A threshold success cannot be downgraded to timeout.
    tp = first(root) / "terminal.json"
    terminal = json.loads(tp.read_text(encoding="utf-8"))
    terminal.update({"status": "timeout", "stop_reason": "cell_time_limit", "error": None})
    tp.write_text(json.dumps(terminal), encoding="utf-8")
    rebuild(root)
    assert_fail(root)


def test_legitimate_timeout_and_failed_with_complete_round(tmp_path, monkeypatch):
    for status, reason, error in (("timeout", "cell_time_limit", None), ("failed", "exception", "boom")):
        root = copy_source(tmp_path / status, monkeypatch, EVIDENCE)
        cell = root / "runs" / str(comparison.EVIDENCE_SEEDS[0]) / "random"
        items = events(cell)[:4]
        write_events(cell, items)
        tp = cell / "terminal.json"
        terminal = json.loads(tp.read_text(encoding="utf-8"))
        terminal.update({"status": status, "stop_reason": reason, "error": error, "rounds_used": 1, "observed_count": 31, "candidate_count": 9, "remaining_budget": 1, "final_model_sha": items[3]["payload"]["model_sha"], "threshold_reached": None})
        tp.write_text(json.dumps(terminal), encoding="utf-8")
        rebuild(root)
        result = audit(root, strict=True, require_complete=False)
        assert result["valid"] is True, result["errors"]


def test_candidate_exhausted_status_is_accounted_by_metrics():
    from nexttest.comparison_metrics import summarize_cell
    cell = {"seed": 1, "strategy": "random", "status": "candidate_exhausted", "stop_reason": "candidate_pool_empty", "rounds": [{"round": 1, "revealed_target": 10.0, "best_revealed_target": 10.0, "oracle_gap": 2.0, "absolute_error": 1.0}], "error": None}
    value = summarize_cell(cell, oracle=12.0, direction="maximize", threshold=None)
    assert value["valid_for_metrics"] is True
    assert value["terminal_oracle_gap"] == 2.0
