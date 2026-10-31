"""Read-only desktop launch readiness checks.

No network, model, data, project, or environment contents are read. The only
filesystem checks are fixed paths needed to start the local web workbench.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "nexttest_desktop_readiness_v1"
PORT_MIN = 8501
PORT_MAX = 8510
MIN_PYTHON = (3, 13)


@dataclass(frozen=True)
class PythonChoice:
    kind: str
    command: tuple[str, ...]


def _exists(path: str | Path) -> bool:
    try:
        return Path(path).is_file()
    except OSError:
        return False


def choose_python(
    *,
    root: Path | None = None,
    env: dict[str, str] | None = None,
    which=shutil.which,
) -> PythonChoice:
    """Choose the fixed order without executing anything."""
    base = ROOT if root is None else Path(root)
    values = os.environ if env is None else env
    env_python = values.get("NEXTEST_COMPUTE_PYTHON", "")
    if env_python and _exists(env_python):
        return PythonChoice("environment", (str(Path(env_python)),))
    venv_python = base / ".venv" / "Scripts" / "python.exe"
    if _exists(venv_python):
        return PythonChoice("project_venv", (str(venv_python),))
    if which("py"):
        return PythonChoice("py_launcher", ("py", "-3.13"))
    if which("python"):
        return PythonChoice("path_python", ("python",))
    return PythonChoice("unknown", ())


def python_version_string(info=None) -> str:
    value = sys.version_info if info is None else info
    return f"{value.major}.{value.minor}.{value.micro}"


def backend_imports() -> dict[str, bool]:
    return {
        name: importlib.util.find_spec(name) is not None
        for name in ("fastapi", "uvicorn", "pydantic")
    }


def port_available(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", int(port)))
        return True
    except (OSError, ValueError):
        return False


def available_ports() -> list[int]:
    return [port for port in range(PORT_MIN, PORT_MAX + 1) if port_available(port)]


def choose_port(requested: int | None = None) -> tuple[int, bool]:
    """Return (port, used_fallback); never kills an existing process."""
    if requested is not None:
        if port_available(requested):
            return requested, False
        ports = available_ports()
        if not ports:
            raise RuntimeError("8501–8510 端口均被占用，请关闭旧服务后重试。")
        return ports[0], True
    ports = available_ports()
    if not ports:
        raise RuntimeError("8501–8510 端口均被占用，请关闭旧服务后重试。")
    return ports[0], False


def _current_kind(root: Path) -> str:
    choice = choose_python(root=root)
    return choice.kind


def doctor(
    *,
    root: Path | None = None,
    choice: PythonChoice | None = None,
    version_info=None,
    imports: dict[str, bool] | None = None,
    ports: list[int] | None = None,
    release_ready: bool | None = None,
) -> dict:
    """Fixed-root readiness report; all output fields are path-free."""
    base = ROOT if root is None else Path(root)
    errors: list[str] = []
    warnings: list[str] = []
    selected = choice or choose_python(root=base)
    version = python_version_string(version_info)
    if selected.kind == "unknown":
        errors.append("未找到可用的 Python 3.13。请安装 Python 3.13，或设置 NEXTEST_COMPUTE_PYTHON。")
    try:
        parts = tuple(int(part) for part in version.split(".")[:2])
    except ValueError:
        parts = (0, 0)
        errors.append("无法识别当前 Python 版本。")
    if parts < MIN_PYTHON:
        errors.append("Python 版本低于 3.13。请安装 Python 3.13，或在 NEXTEST_COMPUTE_PYTHON 中指定可用的 3.13。")
    imported = backend_imports() if imports is None else dict(imports)
    for name, ok in imported.items():
        if not ok:
            errors.append(f"缺少后端依赖：{name}。请安装 requirements-web.txt。")
    dist = (base / "frontend" / "dist" / "index.html").is_file()
    if not dist:
        errors.append("前端尚未构建：缺少 frontend/dist/index.html。请在 frontend 目录运行 npm ci 和 npm run build。")
    lock = (base / "frontend" / "package-lock.json").is_file()
    if not lock:
        errors.append("缺少 frontend/package-lock.json，无法复现前端依赖。")
    if release_ready is None:
        try:
            from nexttest import public_release
            release = public_release.verify_release()
            ready = release.get("release_ready") is True
        except Exception:  # noqa: BLE001
            ready = False
            errors.append("公开发布门禁无法完成。请运行 python scripts/verify_public_release.py --check。")
    else:
        ready = bool(release_ready)
    if not ready:
        errors.append("公开发布门禁未通过。请运行 python scripts/verify_public_release.py --check 查看原因。")
    port_list = available_ports() if ports is None else sorted(set(int(p) for p in ports))
    if not port_list:
        errors.append("8501–8510 端口均被占用。请关闭占用端口的旧服务后重试。")
    if selected.kind == "unknown":
        warnings.append("未确定启动解释器；将使用脚本调用者。")
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if not errors else "blocked",
        "python_executable_kind": selected.kind,
        "python_version": version,
        "backend_imports": imported,
        "frontend_dist": dist,
        "frontend_package_lock": lock,
        "release_gate": {"release_ready": ready},
        "port_candidates": port_list,
        "errors": errors,
        "warnings": warnings,
        "ready_to_launch": not errors,
    }
    return result


def doctor_json() -> str:
    return json.dumps(doctor(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
