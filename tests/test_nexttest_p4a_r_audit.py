"""P4-A-R synchronized tamper tests: semantic replay, not stale SHA trust."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from nexttest import comparison
from nexttest.comparison_audit import audit
from nexttest.comparison_metrics import summarize


SOURCE = Path("runs/nexttest_comparisons/cmp_f12f872fb20d4685ac8d1b79f91e4988")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree(root: Path) -> str:
    return hashlib.sha256(json.dumps(sorted((p.relative_to(root).as_posix(), _sha(p)) for p in root.rglob("*") if p.is_file())).encode()).hexdigest()


def _copy(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    target = tmp_path / "comparisons"
    target.mkdir()
    shutil.copytree(SOURCE, target / SOURCE.name)
    monkeypatch.setattr(comparison, "COMPARISON_ROOT", target)
    return target / SOURCE.name, target


def _events(cell: Path):
    return [json.loads(line) for line in (cell / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_events(cell: Path, events: list[dict]) -> None:
    prev = ""
    for event in events:
        event["prev_sha"] = prev
        event["event_sha"] = hashlib.sha256(json.dumps({k: v for k, v in event.items() if k != "event_sha"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        prev = event["event_sha"]
    (cell / "events.jsonl").write_text("\n".join(json.dumps(event, sort_keys=True, ensure_ascii=False) for event in events) + ("\n" if events else ""), encoding="utf-8")
    terminal_path = cell / "terminal.json"
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    terminal["event_chain_sha"] = prev
    terminal_path.write_text(json.dumps(terminal, sort_keys=True), encoding="utf-8")


def _rebuild(root: Path) -> None:
    plan = json.loads((root / "evaluation_plan.json").read_text(encoding="utf-8"))
    base, _, _ = comparison.load_base(plan["dataset_id"])
    ledger = comparison._ledger(root, plan, base)
    summary = summarize(ledger)
    (root / "comparison_ledger.json").write_text(json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8")
    (root / "comparison_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    comparison._write_hashes(root)


def _first_cell(root: Path) -> Path:
    return root / "runs" / str(comparison.REHEARSAL_SEEDS[0]) / "random"


def _assert_semantic_failure(root: Path, monkeypatch) -> None:
    before = _tree(root)
    result = audit(root, strict=True, require_complete=True)
    assert result["valid"] is False
    assert _tree(root) == before
    # The inspect surface must not return a partial success conclusion.
    comparison.inspect_comparison(root.name)
    # API gate applies the same fail-closed rule.
    from nexttest.web import api
    value = comparison.inspect_comparison(root.name)
    with pytest.raises(Exception):
        api._comparison_result(value)


@pytest.mark.parametrize("case", [
    "release_row", "label_row", "target", "prediction", "absolute_error",
    "disagreement", "reason", "counts_budget_hidden", "missing_event", "duplicate_event",
    "swap_events", "model_update", "timeout_forged_completed", "test_row",
])
def test_synchronized_event_tamper_is_semantically_rejected(tmp_path, monkeypatch, case):
    root, _ = _copy(tmp_path, monkeypatch)
    cell = _first_cell(root)
    events = _events(cell)
    base, _, _ = comparison.load_base("dataset_1e5028247271477a868f1aa13a1ac9bd")
    if case == "release_row":
        events[1]["payload"]["row_id"] = "row-000001"
    elif case == "label_row":
        events[2]["payload"]["row_id"] = "row-000001"
    elif case == "target":
        events[2]["payload"]["target"] = float(events[2]["payload"]["target"]) + 1.0
    elif case == "prediction":
        events[2]["payload"]["prediction"] = float(events[2]["payload"]["prediction"]) + 1.0
    elif case == "absolute_error":
        events[2]["payload"]["absolute_error"] = float(events[2]["payload"]["absolute_error"]) + 1.0
    elif case == "disagreement":
        events[0]["payload"]["disagreement"] = 1.0
    elif case == "reason":
        events[0]["payload"]["reason"] = "tampered reason"
    elif case == "counts_budget_hidden":
        events[0]["payload"]["candidate_count"] = 999
        events[0]["payload"]["budget"] = 99
        events[0]["payload"]["target_hidden"] = False
    elif case == "missing_event":
        events.pop(0)
    elif case == "duplicate_event":
        events.insert(1, dict(events[0]))
    elif case == "swap_events":
        events[0], events[1] = events[1], events[0]
    elif case == "model_update":
        events[3]["payload"]["remaining_budget"] = 99
        events[3]["payload"]["state"] = "ready"
    elif case == "timeout_forged_completed":
        events = []
        terminal_path = cell / "terminal.json"
        terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
        terminal.update({"status": "completed", "stop_reason": "budget_exhausted", "rounds_used": 1})
        terminal_path.write_text(json.dumps(terminal), encoding="utf-8")
    elif case == "test_row":
        test_id = base.test.row_ids[0]
        events[0]["payload"]["row_id"] = test_id
        events[1]["payload"]["row_id"] = test_id
        events[2]["payload"]["row_id"] = test_id
    _write_events(cell, events)
    _rebuild(root)
    _assert_semantic_failure(root, monkeypatch)


@pytest.mark.parametrize("case", ["bom", "duplicate_path", "malformed", "extra_file", "escape_path"])
def test_synchronized_manifest_tamper_is_rejected(tmp_path, monkeypatch, case):
    root, _ = _copy(tmp_path, monkeypatch)
    path = root / "sha256.txt"
    if case == "bom":
        path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    elif case == "duplicate_path":
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines + [lines[0]]) + "\n", encoding="utf-8")
    elif case == "malformed":
        path.write_text("not-a-sha  file\n", encoding="utf-8")
    elif case == "extra_file":
        (root / "unregistered.bin").write_bytes(b"unregistered")
    elif case == "escape_path":
        path.write_text("0" * 64 + "  ../escape.txt\n", encoding="utf-8")
    before = _tree(root)
    result = audit(root, strict=True, require_complete=True)
    assert result["valid"] is False
    assert _tree(root) == before


@pytest.mark.parametrize("status,reason,error", [("not_run", "overall_time_limit", None)])
def test_legitimate_stopped_terminal_is_accepted_semantically(tmp_path, monkeypatch, status, reason, error):
    root, _ = _copy(tmp_path, monkeypatch)
    cell = _first_cell(root)
    _write_events(cell, [])
    terminal_path = cell / "terminal.json"
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    base, _, _ = comparison.load_base("dataset_1e5028247271477a868f1aa13a1ac9bd")
    from nexttest.models import train_regression
    initial = train_regression(base, seed=comparison.REHEARSAL_SEEDS[0], evaluate_test=False).manifest.model_sha256
    terminal.update({"status": status, "stop_reason": reason, "rounds_used": 0, "error": error, "event_chain_sha": "", "observed_count": 30, "candidate_count": 10, "remaining_budget": 1, "final_model_sha": None if status == "not_run" else initial, "threshold_reached": None})
    terminal_path.write_text(json.dumps(terminal), encoding="utf-8")
    _rebuild(root)
    result = audit(root, strict=True, require_complete=False)
    assert result["valid"] is True, result["errors"]


@pytest.mark.parametrize("status,reason,error", [("timeout", "cell_time_limit", None), ("failed", "exception", "boom")])
def test_no_event_timeout_or_failed_is_rejected_without_a_started_round(tmp_path, monkeypatch, status, reason, error):
    root, _ = _copy(tmp_path, monkeypatch)
    cell = _first_cell(root)
    _write_events(cell, [])
    terminal_path = cell / "terminal.json"
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    base, _, _ = comparison.load_base("dataset_1e5028247271477a868f1aa13a1ac9bd")
    from nexttest.models import train_regression
    initial = train_regression(base, seed=comparison.REHEARSAL_SEEDS[0], evaluate_test=False).manifest.model_sha256
    terminal.update({"status": status, "stop_reason": reason, "rounds_used": 0, "error": error, "event_chain_sha": "", "observed_count": 30, "candidate_count": 10, "remaining_budget": 1, "final_model_sha": initial, "threshold_reached": None})
    terminal_path.write_text(json.dumps(terminal), encoding="utf-8")
    _rebuild(root)
    result = audit(root, strict=True, require_complete=False)
    assert result["valid"] is False
