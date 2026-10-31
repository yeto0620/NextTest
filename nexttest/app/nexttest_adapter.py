"""UI-only bridge to the fixed local NextTest P2 worker.

The Streamlit environment has no model dependencies. This module never imports
the data vault or the predictor and never accepts caller-supplied paths.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPUTE_PYTHON = Path(os.environ.get("NEXTTEST_COMPUTE_PYTHON") or sys.executable)
WORKER = ROOT / "scripts" / "nexttest_ui_worker.py"
PROJECT_ID = re.compile(r"^p2_[0-9a-f]{32}$")
RECOMMENDATION_ID = re.compile(r"^rec-[0-9]{6}$")
STRATEGIES = {"random", "greedy_prediction", "max_disagreement"}
INTAKE_ID = re.compile(r"^intake_[0-9a-f]{32}$")
DATASET_ID = re.compile(r"^dataset_[0-9a-f]{32}$")
CUSTOM_PROJECT_ID = re.compile(r"^p3_[0-9a-f]{32}$")
COMPARISON_ID = re.compile(r"^cmp_[0-9a-f]{32}$")
REQUEST_ID = re.compile(r"^req_[0-9a-f]{16,64}$")


class NextTestAdapterError(RuntimeError):
    pass


class NextTestUncertain(NextTestAdapterError):
    pass


def new_project_id() -> str:
    return f"p2_{uuid.uuid4().hex}"


def observed_landscape() -> dict:
    """Return only the already observed training rows for the 3D overview."""
    return _invoke({"operation": "landscape"}, timeout=60.0)


def _check_project_id(value: str) -> str:
    if not isinstance(value, str) or PROJECT_ID.fullmatch(value) is None:
        raise NextTestAdapterError("项目编号格式无效")
    return value


def _invoke(payload: dict, *, timeout: float = 180.0) -> dict:
    if not COMPUTE_PYTHON.is_file() or not WORKER.is_file():
        raise NextTestAdapterError("本地计算环境尚未就绪")
    try:
        proc = subprocess.run(
            [str(COMPUTE_PYTHON), str(WORKER)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=str(ROOT),
            timeout=timeout,
            shell=False,
            check=False,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.TimeoutExpired as exc:
        raise NextTestUncertain("计算等待超时。操作可能已写入，请使用项目编号只读恢复；不要重新提交。") from exc
    except OSError as exc:
        raise NextTestAdapterError("无法启动本地计算进程") from exc
    try:
        response = json.loads(proc.stdout)
    except (ValueError, TypeError) as exc:
        raise NextTestAdapterError("计算进程没有返回可核验的结果") from exc
    if not isinstance(response, dict) or response.get("ok") is not True:
        detail = str(response.get("error", "未知错误")) if isinstance(response, dict) else "未知错误"
        raise NextTestAdapterError(detail[:240])
    if proc.returncode != 0 or not isinstance(response.get("data"), dict):
        raise NextTestAdapterError("计算进程未正常完成")
    return response["data"]


def preview(*, goal: str, threshold: float | None, strategy: str, project_id: str | None = None) -> dict:
    if goal not in {"maximize", "minimize"} or strategy not in STRATEGIES:
        raise NextTestAdapterError("目标或推荐方法无效")
    if threshold is not None and (type(threshold) not in {int, float} or not -1e6 <= threshold <= 1e6):
        raise NextTestAdapterError("阈值无效")
    if project_id is not None:
        _check_project_id(project_id)
    return _invoke({"operation": "preview", "goal": goal, "threshold": threshold, "strategy": strategy,
                    "project_id": project_id}, timeout=90.0)


def intake_create(*, filename: str, content_type: str, content_b64: str, intake_id: str) -> dict:
    if not isinstance(filename, str) or not filename or len(filename) > 120 or "/" in filename or "\\" in filename:
        raise NextTestAdapterError("文件名无效")
    if content_type not in {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel"}:
        raise NextTestAdapterError("文件类型无效")
    if not isinstance(content_b64, str) or len(content_b64) > 14 * 1024 * 1024:
        raise NextTestAdapterError("文件过大")
    if not isinstance(intake_id, str) or INTAKE_ID.fullmatch(intake_id) is None:
        raise NextTestAdapterError("intake 编号无效")
    return _invoke({"operation": "intake_create", "filename": filename, "content_type": content_type, "content_b64": content_b64, "intake_id": intake_id}, timeout=180.0)


def intake_inspect(intake_id: str) -> dict:
    if not isinstance(intake_id, str) or INTAKE_ID.fullmatch(intake_id) is None:
        raise NextTestAdapterError("intake 编号无效")
    return _invoke({"operation": "intake_inspect", "intake_id": intake_id}, timeout=60.0)


def intake_schema(intake_id: str, *, roles: dict, display_names: dict, units: dict, dataset_name: str) -> dict:
    if not isinstance(intake_id, str) or INTAKE_ID.fullmatch(intake_id) is None:
        raise NextTestAdapterError("intake 编号无效")
    if not isinstance(roles, dict) or not isinstance(display_names, dict) or not isinstance(units, dict) or not isinstance(dataset_name, str):
        raise NextTestAdapterError("字段角色无效")
    return _invoke({"operation": "intake_schema", "intake_id": intake_id, "roles": roles, "display_names": display_names, "units": units, "dataset_name": dataset_name}, timeout=90.0)


def intake_gate(intake_id: str) -> dict:
    if not isinstance(intake_id, str) or INTAKE_ID.fullmatch(intake_id) is None:
        raise NextTestAdapterError("intake 编号无效")
    return _invoke({"operation": "intake_gate", "intake_id": intake_id}, timeout=90.0)


def intake_ack(intake_id: str, warning_ids: list[str]) -> dict:
    if not isinstance(intake_id, str) or INTAKE_ID.fullmatch(intake_id) is None:
        raise NextTestAdapterError("intake 编号无效")
    if not isinstance(warning_ids, list) or any(not isinstance(item, str) for item in warning_ids):
        raise NextTestAdapterError("warning 编号无效")
    return _invoke({"operation": "intake_ack", "intake_id": intake_id, "warning_ids": warning_ids}, timeout=60.0)


def intake_freeze(intake_id: str, dataset_id: str) -> dict:
    if not isinstance(intake_id, str) or INTAKE_ID.fullmatch(intake_id) is None:
        raise NextTestAdapterError("intake 编号无效")
    if not isinstance(dataset_id, str) or DATASET_ID.fullmatch(dataset_id) is None:
        raise NextTestAdapterError("dataset 编号无效")
    return _invoke({"operation": "intake_freeze", "intake_id": intake_id, "dataset_id": dataset_id}, timeout=180.0)


def dataset_inspect(dataset_id: str) -> dict:
    if not isinstance(dataset_id, str) or DATASET_ID.fullmatch(dataset_id) is None:
        raise NextTestAdapterError("dataset 编号无效")
    return _invoke({"operation": "dataset_inspect", "dataset_id": dataset_id}, timeout=60.0)


def custom_landscape(dataset_id: str) -> dict:
    if not isinstance(dataset_id, str) or DATASET_ID.fullmatch(dataset_id) is None:
        raise NextTestAdapterError("dataset 编号无效")
    return _invoke({"operation": "custom_landscape", "dataset_id": dataset_id}, timeout=60.0)


def custom_preview(*, dataset_id: str, strategy: str, goal: str, threshold: float | None, project_id: str | None = None) -> dict:
    if not isinstance(dataset_id, str) or DATASET_ID.fullmatch(dataset_id) is None:
        raise NextTestAdapterError("dataset 编号无效")
    if project_id is not None and (not isinstance(project_id, str) or CUSTOM_PROJECT_ID.fullmatch(project_id) is None):
        raise NextTestAdapterError("项目编号无效")
    return _invoke({"operation": "custom_preview", "dataset_id": dataset_id, "strategy": strategy, "goal": goal, "threshold": threshold, "project_id": project_id}, timeout=90.0)


def custom_create(*, dataset_id: str, project_id: str, goal: str, threshold: float | None, budget: int, strategy: str) -> dict:
    if not isinstance(dataset_id, str) or DATASET_ID.fullmatch(dataset_id) is None:
        raise NextTestAdapterError("dataset 编号无效")
    if not isinstance(project_id, str) or CUSTOM_PROJECT_ID.fullmatch(project_id) is None:
        raise NextTestAdapterError("项目编号无效")
    return _invoke({"operation": "custom_create", "dataset_id": dataset_id, "project_id": project_id, "goal": goal, "threshold": threshold, "budget": budget, "strategy": strategy}, timeout=180.0)


def custom_inspect(project_id: str) -> dict:
    if not isinstance(project_id, str) or CUSTOM_PROJECT_ID.fullmatch(project_id) is None:
        raise NextTestAdapterError("项目编号无效")
    return _invoke({"operation": "custom_inspect", "project_id": project_id}, timeout=90.0)


def custom_recommend(project_id: str) -> dict:
    if not isinstance(project_id, str) or CUSTOM_PROJECT_ID.fullmatch(project_id) is None:
        raise NextTestAdapterError("项目编号无效")
    return _invoke({"operation": "custom_recommend", "project_id": project_id}, timeout=90.0)


def custom_reveal(project_id: str, recommendation_id: str) -> dict:
    if not isinstance(project_id, str) or CUSTOM_PROJECT_ID.fullmatch(project_id) is None:
        raise NextTestAdapterError("项目编号无效")
    if not isinstance(recommendation_id, str) or RECOMMENDATION_ID.fullmatch(recommendation_id) is None:
        raise NextTestAdapterError("建议编号无效")
    return _invoke({"operation": "custom_reveal", "project_id": project_id, "recommendation_id": recommendation_id}, timeout=180.0)


def comparison_preview(*, dataset_id: str, goal: str, threshold: float | None, budget: int, mode: str) -> dict:
    if not isinstance(dataset_id, str) or (dataset_id != "demo-concrete" and DATASET_ID.fullmatch(dataset_id) is None):
        raise NextTestAdapterError("dataset 编号无效")
    return _invoke({"operation": "comparison_preview", "dataset_id": dataset_id, "goal": goal, "threshold": threshold, "budget": budget, "mode": mode}, timeout=90.0)


def comparison_create(*, dataset_id: str, goal: str, threshold: float | None, budget: int, mode: str, request_id: str) -> dict:
    if not isinstance(request_id, str) or REQUEST_ID.fullmatch(request_id) is None:
        raise NextTestAdapterError("request ID 无效")
    if not isinstance(dataset_id, str) or (dataset_id != "demo-concrete" and DATASET_ID.fullmatch(dataset_id) is None):
        raise NextTestAdapterError("dataset 编号无效")
    return _invoke({"operation": "comparison_create", "dataset_id": dataset_id, "goal": goal, "threshold": threshold, "budget": budget, "mode": mode, "request_id": request_id}, timeout=120.0)


def comparison_inspect(comparison_id: str) -> dict:
    if not isinstance(comparison_id, str) or COMPARISON_ID.fullmatch(comparison_id) is None:
        raise NextTestAdapterError("comparison 编号无效")
    return _invoke({"operation": "comparison_inspect", "comparison_id": comparison_id}, timeout=180.0)


def comparison_run(comparison_id: str, request_id: str) -> dict:
    if not isinstance(comparison_id, str) or COMPARISON_ID.fullmatch(comparison_id) is None:
        raise NextTestAdapterError("comparison 编号无效")
    if not isinstance(request_id, str) or REQUEST_ID.fullmatch(request_id) is None:
        raise NextTestAdapterError("request ID 无效")
    return _invoke({"operation": "comparison_run", "comparison_id": comparison_id, "request_id": request_id}, timeout=900.0)


def comparison_export(comparison_id: str, fmt: str = "json") -> dict:
    if not isinstance(comparison_id, str) or COMPARISON_ID.fullmatch(comparison_id) is None:
        raise NextTestAdapterError("comparison 编号无效")
    return _invoke({"operation": "comparison_export", "comparison_id": comparison_id, "format": fmt}, timeout=120.0)


def create(*, goal: str, threshold: float | None, budget: int, strategy: str, project_id: str) -> dict:
    _check_project_id(project_id)
    if goal not in {"maximize", "minimize"} or strategy not in STRATEGIES:
        raise NextTestAdapterError("目标或推荐方法无效")
    if type(budget) is not int or not 1 <= budget <= 20:
        raise NextTestAdapterError("预算必须为 1 到 20 次")
    if threshold is not None and (type(threshold) not in {int, float} or not -1e6 <= threshold <= 1e6):
        raise NextTestAdapterError("阈值无效")
    return _invoke({"operation": "create", "project_id": project_id, "goal": goal,
                    "threshold": threshold, "budget": budget, "strategy": strategy}, timeout=180.0)


def inspect(project_id: str) -> dict:
    return _invoke({"operation": "inspect", "project_id": _check_project_id(project_id)}, timeout=60.0)


def recommend(project_id: str) -> dict:
    return _invoke({"operation": "recommend", "project_id": _check_project_id(project_id)}, timeout=90.0)


def reveal(project_id: str, recommendation_id: str) -> dict:
    _check_project_id(project_id)
    if not isinstance(recommendation_id, str) or RECOMMENDATION_ID.fullmatch(recommendation_id) is None:
        raise NextTestAdapterError("建议编号无效")
    return _invoke({"operation": "reveal", "project_id": project_id,
                    "recommendation_id": recommendation_id}, timeout=180.0)
