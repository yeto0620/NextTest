"""P5-D public-release gate tests. All fixtures are temporary."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from nexttest import public_release


def _write(root: Path, relative: str, text: str):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "release"
    root.mkdir()
    _write(root, ".gitignore", "\n".join([
        ".env", ".env.*", "!.env.example", ".venv/", ".venv-ui/", "__pycache__/",
        "*.pyc", ".pytest_cache/", "node_modules/", "frontend/node_modules/",
        "frontend/dist/", "artifacts/", "runs/", "deliverables/", "data/",
        ".dsh-*/", "*.log",
    ]) + "\n")
    _write(root, ".env.example", "\n".join([
        "NEXTEST_LLM_PROVIDER=deepseek",
        "NEXTEST_LLM_BASE_URL=https://api.deepseek.com",
        "NEXTEST_LLM_MODEL=deepseek-chat",
        "NEXTEST_LLM_API_KEY=",
    ]) + "\n")
    _write(root, "README.md", "# Fixture\n\n历史回放；NEXTEST_LLM_API_KEY 名称可以出现在说明里，但不要提交真实 key。\n")
    _write(root, "app.py", "print('fixture')\n")
    _write(root, "requirements-web.txt", "fastapi\n")
    _write(root, "requirements-compute.txt", "numpy\n")
    _write(root, "requirements-app.txt", "streamlit\n")
    _write(root, "start_nexttest.cmd", "python scripts\\start_nexttest.py\n")
    _write(root, "configure_nexttest_llm.cmd", "@echo off\n")
    _write(root, "start_nexttest_with_llm.cmd", "@echo off\n")
    _write(root, "nexttest/__init__.py", "")
    _write(root, "nexttest/source.py", "def public():\n    return True\n")
    _write(root, "scripts/start_nexttest.py", "print('fixture')\n")
    _write(root, "tests/placeholder.py", "def test_ok():\n    assert True\n")
    _write(root, "frontend/index.html", "<div id='root'></div>\n")
    _write(root, "frontend/package.json", json.dumps({"scripts": {"build": "vite build"}}))
    _write(root, "frontend/package-lock.json", "{}\n")
    _write(root, "frontend/vite.config.js", "export default {}\n")
    _write(root, "frontend/.gitignore", "node_modules/\n")
    _write(root, "frontend/src/main.js", "console.log('fixture')\n")
    _write(root, "docs/GITHUB_RELEASE_CHECKLIST.md", "# Checklist\n\nNo secrets.\n")
    _write(root, "docs/EVIDENCE_PACKAGE_CONTRACT.md", "# Evidence package\n\n公开字段。\n")
    _write(root, "docs/PROJECT_LIBRARY_CONTRACT.md", "# Library\n\n只读索引，不是排行榜。\n")
    _write(root, "docs/PUBLIC_RELEASE_RUNBOOK.md", "# Runbook\n\n历史回放不是新实验。\n")
    _write(root, ".github/workflows/public-check.yml", """name: public-check
on:
  push:
  pull_request:
  workflow_dispatch:
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: python scripts/verify_public_release.py --check
      - run: npm ci
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
""")
    return root


@pytest.fixture()
def fixture(tmp_path, monkeypatch):
    root = _fixture(tmp_path)
    monkeypatch.setattr(public_release, "ROOT", root)
    return root


def test_current_repository_passes():
    result = public_release.audit_public_release()
    assert result["release_ready"] is True, result["errors"]
    assert result["status"] == "ready"
    assert result["schema_version"] == public_release.SCHEMA_VERSION
    assert result["public_source_files"]
    assert result["excluded_sensitive_paths"]
    assert result["required_docs"]
    assert result["ci_workflows"]


def test_missing_runs_ignore_rule_is_rejected(fixture):
    path = fixture / ".gitignore"
    path.write_text(path.read_text(encoding="utf-8").replace("runs/\n", ""), encoding="utf-8")
    result = public_release.audit_public_release()
    assert result["release_ready"] is False
    assert any("runs/" in error for error in result["errors"])


def test_fake_key_in_env_example_is_rejected(fixture):
    fake_key = "sk-" + "test-live-key-" + "1234567890"
    (fixture / ".env.example").write_text("NEXTEST_LLM_API_KEY=" + fake_key + "\n", encoding="utf-8")
    result = public_release.audit_public_release()
    assert result["release_ready"] is False
    assert any("NEXTEST_LLM_API_KEY" in error for error in result["errors"])


def test_windows_private_path_in_allowlisted_source_is_rejected(fixture):
    (fixture / "nexttest" / "leak.py").write_text("PATH = r'C:\\\\Users\\\\alice\\\\secret.csv'\n", encoding="utf-8")
    result = public_release.audit_public_release()
    assert result["release_ready"] is False
    assert any("Windows absolute path" in error for error in result["errors"])


def test_documentation_key_name_without_assignment_is_allowed(fixture):
    (fixture / "README.md").write_text("# Fixture\n\nNEXTEST_LLM_API_KEY 只是变量名称，不能提交真实 key。\n", encoding="utf-8")
    result = public_release.audit_public_release()
    assert result["release_ready"] is True, result["errors"]


def test_missing_workflow_is_rejected(fixture):
    (fixture / ".github" / "workflows" / "public-check.yml").unlink()
    result = public_release.audit_public_release()
    assert result["release_ready"] is False
    assert any("CI workflow" in error for error in result["errors"])


def test_verify_script_exit_codes_and_compact_json(fixture, capsys):
    spec = importlib.util.spec_from_file_location("verify_public_release", Path("scripts/verify_public_release.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.main(["--check"]) == 0
    ready = capsys.readouterr().out.strip()
    parsed = json.loads(ready)
    assert parsed["release_ready"] is True
    assert "\n" not in ready

    (fixture / ".env.example").write_text("NEXTEST_LLM_API_KEY=" + "real-secret" + "\n", encoding="utf-8")
    assert module.main(["--check"]) == 1
    blocked = json.loads(capsys.readouterr().out.strip())
    assert blocked["release_ready"] is False
    with pytest.raises(SystemExit):
        module.main(["--check", "--json-out", "out.json"])


def test_audit_is_read_only(fixture):
    before = public_release.tree_sha256(fixture)
    public_release.audit_public_release()
    assert public_release.tree_sha256(fixture) == before


def test_restricted_directories_are_not_scanned(fixture):
    (fixture / "data").mkdir()
    (fixture / "data" / "secret.csv").write_text("target\n999\n", encoding="utf-8")
    (fixture / "artifacts").mkdir()
    (fixture / "artifacts" / "secret.log").write_text("sk-" + "x" * 30, encoding="utf-8")
    result = public_release.audit_public_release()
    assert result["release_ready"] is True, result["errors"]
    assert all(not path.startswith("data/") for path in result["public_source_files"])
