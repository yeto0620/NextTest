"""Fail-closed, read-only public-release audit.

The audit runs against the repository containing this module. It deliberately
does not walk data/, artifacts/, runs/, deliverables/, environments, or build
output; those locations are reported as excluded categories, not inspected.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "nexttest_public_release_v1"

ROOT_FILES = (
    ".gitignore",
    ".env.example",
    "README.md",
    "app.py",
    "requirements-web.txt",
    "requirements-compute.txt",
    "requirements-app.txt",
    "start_nexttest.cmd",
    "configure_nexttest_llm.cmd",
    "start_nexttest_with_llm.cmd",
)
REQUIRED_DOCS = (
    "README.md",
    "docs/GITHUB_RELEASE_CHECKLIST.md",
    "docs/EVIDENCE_PACKAGE_CONTRACT.md",
    "docs/PROJECT_LIBRARY_CONTRACT.md",
    "docs/PUBLIC_RELEASE_RUNBOOK.md",
)
PUBLIC_DOCS = (
    "README.md",
    "docs/GITHUB_RELEASE_CHECKLIST.md",
    "docs/EVIDENCE_PACKAGE_CONTRACT.md",
    "docs/PROJECT_LIBRARY_CONTRACT.md",
    "docs/PUBLIC_RELEASE_RUNBOOK.md",
    "docs/WINDOWS_QUICKSTART.md",
    "docs/WINDOWS_DESKTOP_APP.md",
    "docs/contest_fit_2026.md",
)
REQUIRED_REQUIREMENTS = (
    "requirements-web.txt",
    "requirements-compute.txt",
    "requirements-app.txt",
)
FRONTEND_FILES = (
    "frontend/index.html",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vite.config.js",
    "frontend/.gitignore",
)
PUBLIC_DIRS = (
    "nexttest",
    "scripts",
    "tests",
    "frontend/src",
)
OPTIONAL_PUBLIC_DIRS = ("desktop", "src-tauri")
OPTIONAL_ROOT_FILES = ("package.json",)
SKIP_PUBLIC_PREFIXES = ("desktop/dist/", "desktop/build/", "src-tauri/target/", "src-tauri/gen/")
WORKFLOW = ".github/workflows/public-check.yml"
REQUIRED_IGNORE_RULES = (
    "data/",
    "artifacts/",
    "runs/",
    "deliverables/",
    ".venv/",
    ".venv-ui/",
    "node_modules/",
    "frontend/node_modules/",
    "frontend/dist/",
    ".env",
    "*.log",
    "*.pyc",
)
EXCLUDED_CATEGORIES = (
    ("local_data", ("data/",)),
    ("local_artifacts", ("artifacts/",)),
    ("local_runs", ("runs/",)),
    ("local_deliverables", ("deliverables/",)),
    ("python_environment", (".venv/", ".venv-ui/", "__pycache__/", "*.pyc", ".pytest_cache/")),
    ("node_environment", ("node_modules/", "frontend/node_modules/", "frontend/dist/")),
    ("secrets", (".env", ".env.*", "*.log")),
    ("internal_docs", ("docs/V3_*.md", "docs/web_workbench_contract.md", "docs/visual_identity.md", "docs/product_roadmap.md")),
    ("local_helper_scripts", ("scripts/fill_zzu_agent_contest_form.py", "scripts/revise_v3_proposal.py")),
)
LOCAL_HELPERS = {
    "scripts/fill_zzu_agent_contest_form.py",
    "scripts/revise_v3_proposal.py",
}
TEXT_SUFFIXES = {".py", ".md", ".js", ".jsx", ".json", ".yml", ".yaml", ".cmd", ".txt", ".example", ".gitignore", ".rs", ".toml", ".ps1"}
KEY_ASSIGN = re.compile(r"NEXTEST_LLM_API_KEY[ \t]*=[ \t]*([^\s#`]+)")
SECRET_PREFIX = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
WINDOWS_PRIVATE = re.compile(r"[A-Za-z]:[\\/](?:Users|OneDrive|Documents|Desktop|AppData)[\\/]", re.IGNORECASE)
WINDOWS_ABSOLUTE = re.compile(r"[A-Za-z]:\\[^\s\"'`]+", re.IGNORECASE)
RAW_CSV_PATH = re.compile(r"(?:^|[\s\"'`(])data/[^\s\"'`]+\.csv", re.IGNORECASE)
PRIVATE_PROJECT_PATH = re.compile(r"(?:^|[\s\"'`(])(?:runs|artifacts)/nexttest[^\s\"'`]*", re.IGNORECASE)
RAW_CSV_ALLOWLIST = ("data/nexttest/uci_concrete/canonical/concrete_age28.csv",)
SELF_PATH = "nexttest/public_release.py"


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _read_utf8(path: Path, errors: list[str]) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        errors.append(f"cannot read {_rel(path)}")
        return None
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append(f"BOM in {_rel(path)}")
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"non-UTF-8 {_rel(path)}")
        return None


def _walk_public_files(errors: list[str]) -> list[str]:
    files = []
    for rel in ROOT_FILES + FRONTEND_FILES:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"required public file missing: {rel}")
        else:
            files.append(rel)
    for rel in PUBLIC_DOCS:
        path = ROOT / rel
        if path.is_file():
            files.append(rel)
    for rel in OPTIONAL_ROOT_FILES:
        if (ROOT / rel).is_file():
            files.append(rel)
    for directory in PUBLIC_DIRS + OPTIONAL_PUBLIC_DIRS:
        root = ROOT / directory
        if not root.is_dir():
            if directory in PUBLIC_DIRS:
                errors.append(f"public directory missing: {directory}")
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative in LOCAL_HELPERS or any(relative.startswith(prefix) for prefix in SKIP_PUBLIC_PREFIXES):
                continue
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".log"}:
                continue
            if path.is_symlink():
                errors.append(f"public symlink rejected: {relative}")
                continue
            try:
                path.resolve().relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"public path escapes root: {relative}")
                continue
            files.append(relative)
    if (ROOT / WORKFLOW).is_file():
        files.append(WORKFLOW)
    else:
        errors.append(f"required public file missing: {WORKFLOW}")
    return sorted(set(files))


def _ignore_audit(errors: list[str]) -> list[dict]:
    path = ROOT / ".gitignore"
    if not path.is_file():
        errors.append(".gitignore missing")
        return []
    text = _read_utf8(path, errors)
    if text is None:
        return []
    rules = []
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    for required in REQUIRED_IGNORE_RULES:
        match = next((line for line in lines if line == required), None)
        if required == "frontend/node_modules/":
            match = match or next((line for line in lines if line == "node_modules/"), None)
        if required == "frontend/dist/":
            match = match or next((line for line in lines if line == "dist/"), None)
        covered = match is not None
        rules.append({"pattern": required, "covered": covered, "matched_rule": match})
        if not covered:
            errors.append(f".gitignore missing rule: {required}")
    return rules


def _env_example_audit(errors: list[str]) -> dict:
    path = ROOT / ".env.example"
    if not path.is_file():
        errors.append(".env.example missing")
        return {"exists": False, "key_blank": False, "keys": [], "format_ok": False}
    text = _read_utf8(path, errors)
    if text is None:
        return {"exists": True, "key_blank": False, "keys": [], "format_ok": False}
    keys = []
    key_blank = False
    format_ok = True
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            errors.append(f".env.example line {number} is not KEY=VALUE")
            format_ok = False
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            errors.append(f".env.example line {number} has invalid key name")
            format_ok = False
        keys.append(name)
        if name == "NEXTEST_LLM_API_KEY":
            if value:
                errors.append(".env.example contains a non-empty NEXTEST_LLM_API_KEY")
                format_ok = False
            else:
                key_blank = True
    required = {"NEXTEST_LLM_PROVIDER", "NEXTEST_LLM_BASE_URL", "NEXTEST_LLM_MODEL", "NEXTEST_LLM_API_KEY"}
    if set(keys) != required:
        errors.append(".env.example key set is incomplete or has extra keys")
        format_ok = False
    if not key_blank:
        errors.append(".env.example must contain a blank NEXTEST_LLM_API_KEY")
    return {"exists": True, "key_blank": key_blank, "keys": keys, "format_ok": format_ok}


def _required_docs_audit(errors: list[str]) -> list[dict]:
    docs = []
    for rel in REQUIRED_DOCS:
        path = ROOT / rel
        exists = path.is_file()
        if not exists:
            errors.append(f"required documentation missing: {rel}")
            docs.append({"path": rel, "exists": False, "utf8": False, "nonempty": False})
            continue
        text = _read_utf8(path, errors)
        nonempty = bool(text and text.strip())
        if not nonempty:
            errors.append(f"required documentation empty: {rel}")
        docs.append({"path": rel, "exists": True, "utf8": text is not None, "nonempty": nonempty})
    return docs


def _requirements_audit(errors: list[str]) -> list[dict]:
    files = []
    for rel in REQUIRED_REQUIREMENTS:
        path = ROOT / rel
        exists = path.is_file()
        if not exists:
            errors.append(f"requirements file missing: {rel}")
            files.append({"path": rel, "exists": False, "utf8": False})
            continue
        text = _read_utf8(path, errors)
        files.append({"path": rel, "exists": True, "utf8": text is not None})
    return files


def _frontend_audit(errors: list[str]) -> dict:
    package_path = ROOT / "frontend" / "package.json"
    result = {
        "package_json": {"exists": package_path.is_file(), "parsed": False, "build_script": False},
        "lockfile": (ROOT / "frontend" / "package-lock.json").is_file(),
        "vite_config": (ROOT / "frontend" / "vite.config.js").is_file(),
        "src_dir": (ROOT / "frontend" / "src").is_dir(),
        "node_modules_excluded": any(line == "frontend/node_modules/" for line in _ignore_lines(errors)),
        "dist_excluded": any(line == "frontend/dist/" for line in _ignore_lines(errors)),
    }
    if not package_path.is_file():
        errors.append("frontend/package.json missing")
        return result
    text = _read_utf8(package_path, errors)
    if text is None:
        return result
    try:
        package = json.loads(text)
    except json.JSONDecodeError:
        errors.append("frontend/package.json is malformed")
        return result
    result["package_json"]["parsed"] = True
    result["package_json"]["build_script"] = isinstance(package.get("scripts"), dict) and isinstance(package["scripts"].get("build"), str)
    if not result["package_json"]["build_script"]:
        errors.append("frontend package.json lacks scripts.build")
    if not result["lockfile"]:
        errors.append("frontend/package-lock.json missing")
    if not result["vite_config"]:
        errors.append("frontend/vite.config.js missing")
    if not result["src_dir"]:
        errors.append("frontend/src missing")
    return result


def _ignore_lines(errors: list[str]) -> list[str]:
    path = ROOT / ".gitignore"
    if not path.is_file():
        return []
    text = _read_utf8(path, errors)
    if text is None:
        return []
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def _workflow_audit(errors: list[str]) -> list[dict]:
    path = ROOT / WORKFLOW
    if not path.is_file():
        errors.append(f"CI workflow missing: {WORKFLOW}")
        return []
    text = _read_utf8(path, errors)
    if text is None:
        return []
    checks = {
        "push": "push" in text,
        "pull_request": "pull_request" in text,
        "workflow_dispatch": "workflow_dispatch" in text,
        "python313": bool(re.search(r"python-version:\s*['\"]?3\.13['\"]?", text)),
        "verify_command": "python scripts/verify_public_release.py --check" in text,
        "npm_ci": "npm ci" in text,
        "npm_build": "npm run build" in text,
        "no_secret_reference": "secrets." not in text and "NEXTEST_LLM_API_KEY" not in text,
    }
    for key, ok in checks.items():
        if not ok:
            errors.append(f"CI workflow check failed: {key}")
    return [{"path": WORKFLOW, "exists": True, "checks": checks}]


def _scan(errors: list[str], files: list[str]) -> dict:
    findings = []
    scanned = 0
    for rel in files:
        path = ROOT / rel
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".gitignore", ".env.example"}:
            continue
        text = _read_utf8(path, errors)
        if text is None:
            continue
        scanned += 1
        for match in KEY_ASSIGN.finditer(text):
            value = match.group(1).strip().strip("\"'")
            if value.startswith(("<", "${", "{", "$", "your", "YOUR", "\"", "'", ",", "+")) or value in {"", ",", "REDACTED", "PLACEHOLDER"}:
                continue
            findings.append({"path": rel, "kind": "api_key_assignment"})
            errors.append(f"API key assignment in public file: {rel}")
        for _match in SECRET_PREFIX.finditer(text):
            findings.append({"path": rel, "kind": "sk_prefix"})
            errors.append(f"secret-like sk- value in public file: {rel}")
        if rel.startswith("tests/"):
            continue
        if rel == SELF_PATH:
            continue
        path_text = text
        for allowed in RAW_CSV_ALLOWLIST:
            path_text = path_text.replace(allowed, "")
        if WINDOWS_PRIVATE.search(path_text) or WINDOWS_ABSOLUTE.search(path_text):
            findings.append({"path": rel, "kind": "windows_absolute_path"})
            errors.append(f"Windows absolute path in public source: {rel}")
        if RAW_CSV_PATH.search(path_text):
            findings.append({"path": rel, "kind": "raw_csv_path"})
            errors.append(f"raw CSV path in public source: {rel}")
        if PRIVATE_PROJECT_PATH.search(path_text):
            findings.append({"path": rel, "kind": "private_project_path"})
            errors.append(f"private project/runs path in public source: {rel}")
    return {"files_scanned": scanned, "findings": findings, "patterns": ["api_key_assignment", "sk_prefix", "windows_absolute_path", "raw_csv_path", "private_project_path"]}


def _extra_candidates(errors: list[str]) -> list[str]:
    candidates = []
    for path in sorted(ROOT.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if name == ".env.example":
            continue
        if name == ".env" or name.startswith(".env.") or path.suffix.lower() in {".log", ".pyc", ".csv"}:
            candidates.append(name)
    for rel in _walk_public_files([]):
        name = Path(rel).name
        if name == ".env.example":
            continue
        if name == ".env" or name.startswith(".env.") or Path(rel).suffix.lower() in {".log", ".pyc", ".csv"}:
            candidates.append(rel)
    for candidate in sorted(set(candidates)):
        errors.append(f"sensitive public candidate: {candidate}")
    return sorted(set(candidates))


def tree_sha256(root: str | Path) -> str:
    """Read-only helper used by tests and release checks."""
    root = Path(root)
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            entries.append([path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()])
    return hashlib.sha256(json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def audit_public_release() -> dict:
    """Run the fixed-root release audit; returns strict JSON-ready facts only."""
    errors: list[str] = []
    warnings: list[str] = []
    files = _walk_public_files(errors)
    ignore_rules = _ignore_audit(errors)
    env_example = _env_example_audit(errors)
    required_docs = _required_docs_audit(errors)
    requirements = _requirements_audit(errors)
    frontend = _frontend_audit(errors)
    workflows = _workflow_audit(errors)
    scan = _scan(errors, files)
    extra = _extra_candidates(errors)
    excluded = [{"category": category, "patterns": list(patterns), "excluded": True} for category, patterns in EXCLUDED_CATEGORIES]
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if not errors else "blocked",
        "public_source_files": files,
        "excluded_sensitive_paths": excluded,
        "ignore_rules_checked": ignore_rules,
        "secret_scan": scan,
        "required_docs": required_docs,
        "requirements_files": requirements,
        "frontend_contract": frontend,
        "ci_workflows": workflows,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "release_ready": not errors,
    }
    if extra:
        warnings.append(f"extra sensitive public candidates: {len(extra)}")
    result["warnings"] = sorted(set(warnings))
    return result


def verify_release() -> dict:
    """Compatibility entry point for the desktop doctor."""
    return audit_public_release()
