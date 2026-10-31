"""P4-A comparison execution, fairness, resumption, audit, and tamper tests."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

from nexttest import comparison
from nexttest.comparison_audit import audit


DATASET = "dataset_1e5028247271477a868f1aa13a1ac9bd"


def rid(_char: str = "") -> str:
    return "req_" + uuid.uuid4().hex[:24]


def create(mode="rehearsal", budget=1, request_id=None):
    return comparison.create_comparison(dataset_id=DATASET, goal="maximize", threshold=None, budget=budget, mode=mode, request_id=request_id or rid())


def test_plan_is_frozen_before_any_reveal_and_fixed_seeds():
    value = create("rehearsal", 1)
    cid = value["manifest"]["comparison_id"]
    root = comparison.COMPARISON_ROOT / cid
    assert (root / "evaluation_plan.json").is_file()
    assert not (root / "runs").exists()
    plan = value["plan"]
    assert plan["seeds"] == list(comparison.REHEARSAL_SEEDS)
    assert plan["strategies"] == ["random", "greedy_prediction", "max_disagreement"]
    assert plan["exploratory_preview"] is True and plan["eligible_for_comparison_claim"] is False
    plan_file_before = (root / "evaluation_plan.json").read_bytes()
    # A second create with the same idempotency key returns the same frozen plan.
    same = comparison.create_comparison(dataset_id=DATASET, goal="maximize", threshold=None, budget=1, mode="rehearsal", request_id=value["manifest"]["request_id"])
    assert same["manifest"]["comparison_id"] == cid
    assert (root / "evaluation_plan.json").read_bytes() == plan_file_before
    preview = comparison.preview_plan(dataset_id=DATASET, goal="maximize", threshold=None, budget=1, mode="evidence")
    assert preview["plan_preview"]["seeds"] == list(comparison.EVIDENCE_SEEDS)
    assert preview["calculation_scale"]["max_reveals"] == 30


def test_rehearsal_run_ledger_audit_and_label_boundary():
    value = create("rehearsal", 1)
    cid = value["manifest"]["comparison_id"]
    assert value["state"]["status"] == "planned" and value["ledger"] is None
    finished = comparison.run_comparison(cid, rid("b"))
    assert finished["state"]["status"] == "complete"
    assert finished["audit"]["valid"] is True
    assert finished["summary"]["complete"] is True
    assert finished["summary"]["eligible_for_comparison_claim"] is False
    assert len(finished["ledger"]["cells"]) == 9
    assert all(cell["status"] in {"completed", "stopped_threshold", "candidate_exhausted"} for cell in finished["ledger"]["cells"])
    all_events = list((comparison.COMPARISON_ROOT / cid / "runs").rglob("events.jsonl"))
    assert len(all_events) == 9
    for path in all_events:
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        recs = [e for e in events if e["event_type"] == "recommendation"]
        releases = [e for e in events if e["event_type"] == "label_released"]
        assert all("target" not in e["payload"] and "revealed_target" not in e["payload"] for e in recs)
        assert len(releases) == len(recs)
    text = json.dumps(finished["ledger"], ensure_ascii=False)
    base, split, passport = comparison.load_base(DATASET)
    assert all(test_id not in text for test_id in base.test.row_ids)
    first_model_by_seed = {}
    for seed in comparison.REHEARSAL_SEEDS:
        shas = set()
        for strategy in comparison.STRATEGY_ORDER:
            root = comparison.COMPARISON_ROOT / cid / "runs" / str(seed) / strategy
            events = [json.loads(line) for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            rec = next(e for e in events if e["event_type"] == "recommendation")
            shas.add(rec["payload"]["model_sha"])
            assert rec["payload"]["observed_count"] == len(base.observed.frame)
        assert len(shas) == 1
        first_model_by_seed[seed] = next(iter(shas))
    # Resume is read-only for a completed comparison and does not add events.
    count_before = sum(1 for _ in (comparison.COMPARISON_ROOT / cid / "runs").rglob("events.jsonl"))
    again = comparison.run_comparison(cid, rid("c"))
    assert again["audit"]["valid"] is True
    assert sum(1 for _ in (comparison.COMPARISON_ROOT / cid / "runs").rglob("events.jsonl")) == count_before


def test_audit_fails_on_ledger_or_plan_tamper(tmp_path, monkeypatch):
    value = create("rehearsal", 1)
    cid = value["manifest"]["comparison_id"]
    comparison.run_comparison(cid, rid("d"))
    source = comparison.COMPARISON_ROOT / cid
    target_root = tmp_path / "comparisons"
    target_root.mkdir()
    shutil.copytree(source, target_root / cid)
    monkeypatch.setattr(comparison, "COMPARISON_ROOT", target_root)
    ledger_path = target_root / cid / "comparison_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["cells"][0]["status"] = "completed"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    result = audit(target_root / cid, strict=True, require_complete=True)
    assert result["valid"] is False
    assert any("hash mismatch" in error or "ledger" in error.lower() for error in result["errors"])
    plan_path = target_root / cid / "evaluation_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["seeds"] = [20261026]
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(Exception):
        comparison.inspect_comparison(cid)


def test_dataset_and_seed_validation():
    with pytest.raises(Exception):
        comparison.create_comparison(dataset_id="../bad", goal="maximize", threshold=None, budget=1, mode="rehearsal", request_id=rid("e"))
    with pytest.raises(Exception):
        comparison.create_comparison(dataset_id=DATASET, goal="maximize", threshold=None, budget=99, mode="rehearsal", request_id=rid("f"))
    with pytest.raises(Exception):
        comparison.preview_plan(dataset_id=DATASET, goal="maximize", threshold=None, budget=1, mode="arbitrary")

def test_timeout_terminal_is_accounted_not_zero_filled():
    value = create("rehearsal", 1)
    cid = value["manifest"]["comparison_id"]
    root = comparison.COMPARISON_ROOT / cid
    cell = root / "runs" / str(comparison.REHEARSAL_SEEDS[0]) / "random"
    cell.mkdir(parents=True, exist_ok=True)
    (cell / "terminal.json").write_text(json.dumps({"seed": comparison.REHEARSAL_SEEDS[0], "strategy": "random", "status": "timeout", "stop_reason": "cell_time_limit", "rounds_used": 0, "error": None, "event_chain_sha": "", "finished_utc": "2026-10-30T00:00:00Z"}), encoding="utf-8")
    finished = comparison.run_comparison(cid, rid())
    random_cell = next(c for c in finished["ledger"]["cells"] if c["seed"] == comparison.REHEARSAL_SEEDS[0] and c["strategy"] == "random")
    assert random_cell["status"] == "timeout" and random_cell["rounds"] == []
    assert finished["summary"]["complete"] is False
    assert finished["summary"]["strategies"]["random"]["status_counts"]["timeout"] == 1
    assert finished["summary"]["strategies"]["random"]["valid_denominator"] == 2
    assert "不生成策略差异结论" in finished["summary"]["conclusion"]
