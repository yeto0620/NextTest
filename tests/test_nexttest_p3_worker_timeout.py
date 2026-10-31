"""P3 adapter must not retry a timed-out local write."""

from __future__ import annotations

import subprocess

import pytest

from nexttest.app import nexttest_adapter as adapter


def test_worker_timeout_is_uncertain_and_not_retried(monkeypatch):
    calls = []

    def timeout(*args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired(cmd="worker", timeout=1)

    monkeypatch.setattr(adapter.subprocess, "run", timeout)
    with pytest.raises(adapter.NextTestUncertain):
        adapter.intake_create(filename="alloy.csv", content_type="text/csv", content_b64="YQ==", intake_id="intake_" + "a" * 32)
    assert len(calls) == 1
