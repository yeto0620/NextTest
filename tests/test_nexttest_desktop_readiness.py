"""P6-A desktop readiness and one-click launcher regression tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nexttest import desktop_readiness
from nexttest import public_release


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "desktop"
    (root / "frontend" / "dist").mkdir(parents=True)
    (root / "frontend" / "dist" / "index.html").write_text("<div></div>\n", encoding="utf-8")
    (root / "frontend" / "package-lock.json").write_text("{}\n", encoding="utf-8")
    return root


def _choice(kind="environment"):
    return desktop_readiness.PythonChoice(kind, ("python",))


def _doctor(root: Path, **overrides):
    values = {
        "root": root,
        "choice": _choice(),
        "version_info": SimpleNamespace(major=3, minor=13, micro=7),
        "imports": {"fastapi": True, "uvicorn": True, "pydantic": True},
        "ports": [8501],
        "release_ready": True,
    }
    values.update(overrides)
    return desktop_readiness.doctor(**values)


def test_python_choice_environment_only_if_file_exists(tmp_path):
    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    assert desktop_readiness.choose_python(root=tmp_path, env={"NEXTEST_COMPUTE_PYTHON": str(python)}).kind == "environment"
    missing = desktop_readiness.choose_python(root=tmp_path, env={"NEXTEST_COMPUTE_PYTHON": str(tmp_path / "absent.exe")}, which=lambda name: None)
    assert missing.kind == "unknown"


def test_python_choice_project_venv_fallback(tmp_path):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    choice = desktop_readiness.choose_python(root=tmp_path, env={}, which=lambda name: None)
    assert choice.kind == "project_venv"


def test_python_choice_py_then_python_then_unknown(tmp_path):
    py = desktop_readiness.choose_python(root=tmp_path, env={}, which=lambda name: "py" if name == "py" else None)
    assert py.kind == "py_launcher"
    assert py.command == ("py", "-3.13")
    python = desktop_readiness.choose_python(root=tmp_path, env={}, which=lambda name: "python" if name == "python" else None)
    assert python.kind == "path_python"
    unknown = desktop_readiness.choose_python(root=tmp_path, env={}, which=lambda name: None)
    assert unknown.kind == "unknown"


def test_doctor_schema_and_ready(tmp_path):
    report = _doctor(_root(tmp_path))
    assert set(report) == {
        "schema_version", "status", "python_executable_kind", "python_version",
        "backend_imports", "frontend_dist", "frontend_package_lock", "release_gate",
        "port_candidates", "errors", "warnings", "ready_to_launch",
    }
    assert report["status"] == "ready"
    assert report["ready_to_launch"] is True
    assert report["python_executable_kind"] == "environment"
    assert report["errors"] == []


def test_doctor_rejects_old_python(tmp_path):
    report = _doctor(_root(tmp_path), version_info=SimpleNamespace(major=3, minor=12, micro=9))
    assert report["ready_to_launch"] is False
    assert any("3.13" in error for error in report["errors"])


def test_doctor_rejects_missing_dist(tmp_path):
    root = _root(tmp_path)
    (root / "frontend" / "dist" / "index.html").unlink()
    report = _doctor(root)
    assert report["ready_to_launch"] is False
    assert report["frontend_dist"] is False


def test_doctor_rejects_missing_package_lock(tmp_path):
    root = _root(tmp_path)
    (root / "frontend" / "package-lock.json").unlink()
    report = _doctor(root)
    assert report["ready_to_launch"] is False
    assert report["frontend_package_lock"] is False


def test_doctor_rejects_release_gate_false(tmp_path):
    report = _doctor(_root(tmp_path), release_ready=False)
    assert report["ready_to_launch"] is False
    assert report["release_gate"]["release_ready"] is False


def test_doctor_rejects_no_ports(tmp_path):
    report = _doctor(_root(tmp_path), ports=[])
    assert report["ready_to_launch"] is False
    assert any("8501" in error for error in report["errors"])


def test_doctor_output_has_no_absolute_path_key_or_env(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setenv("NEXTEST_COMPUTE_PYTHON", "C:\\Users\\alice\\python.exe")
    report = _doctor(root)
    text = json.dumps(report, ensure_ascii=False)
    assert str(root) not in text
    assert "C:\\\\Users" not in text
    assert "sk-" not in text
    assert "NEXTEST_LLM_API_KEY" not in text
    assert "NEXTEST_COMPUTE_PYTHON" not in text


def test_start_cmd_contract():
    text = Path("start_nexttest.cmd").read_text(encoding="utf-8")
    for required in ("%~dp0", "--doctor", "--no-browser", "8501", "8510", "NEXTEST_COMPUTE_PYTHON", ".venv", "py -3.13", "python"):
        assert required in text
    assert "C:\\\\Users" not in text
    assert "AppData\\\\Local\\\\Programs" not in text
    assert "start_nexttest.py" in text


def test_start_cmd_is_crlf():
    raw = Path("start_nexttest.cmd").read_bytes()
    assert b"\r\n" in raw
    assert not raw.startswith(b"\xef\xbb\xbf")


def test_desktop_checks_are_read_only(tmp_path):
    root = _root(tmp_path)
    before = public_release.tree_sha256(root)
    _doctor(root)
    desktop_readiness.doctor_json()
    after = public_release.tree_sha256(root)
    assert before == after


def test_doctor_json_is_compact_and_path_free():
    text = desktop_readiness.doctor_json()
    assert "\n" not in text
    parsed = json.loads(text)
    assert parsed["schema_version"] == desktop_readiness.SCHEMA_VERSION
    assert "C:\\\\Users" not in text
    assert "AppData" not in text
