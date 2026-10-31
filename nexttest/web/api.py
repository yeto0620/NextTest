"""Same-origin desktop API. Scientific state remains in the isolated P2 worker."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import base64
import uuid
from urllib.parse import unquote

from nexttest.app import nexttest_adapter as bridge
from nexttest import llm_copilot as copilot
from nexttest import evidence_package
from nexttest import project_library


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend" / "dist"
PROJECT_ID = re.compile(r"^p2_[0-9a-f]{32}$")
CUSTOM_PROJECT_ID = re.compile(r"^p3_[0-9a-f]{32}$")
COMPARISON_ID = re.compile(r"^cmp_[0-9a-f]{32}$")
REQUEST_ID = re.compile(r"^req_[0-9a-f]{16,64}$")
INTAKE_ID = re.compile(r"^intake_[0-9a-f]{32}$")
DATASET_ID = re.compile(r"^dataset_[0-9a-f]{32}$")
RECOMMENDATION_ID = re.compile(r"^rec-[0-9]{6}$")
app = FastAPI(title="NextTest local API", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


class CreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    goal: str
    strategy: str
    budget: int = Field(ge=1, le=20)
    threshold: float | None = Field(default=None, ge=-1_000_000, le=1_000_000)

    @field_validator("goal")
    @classmethod
    def valid_goal(cls, value: str) -> str:
        if value not in {"maximize", "minimize"}:
            raise ValueError("目标无效")
        return value

    @field_validator("strategy")
    @classmethod
    def valid_strategy(cls, value: str) -> str:
        if value not in bridge.STRATEGIES:
            raise ValueError("推荐方法无效")
        return value


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    goal: str
    strategy: str
    threshold: float | None = Field(default=None, ge=-1_000_000, le=1_000_000)
    project_id: str | None = None

    @field_validator("project_id")
    @classmethod
    def valid_project(cls, value: str | None) -> str | None:
        if value is not None and PROJECT_ID.fullmatch(value) is None:
            raise ValueError("项目编号格式无效")
        return value

    @field_validator("goal")
    @classmethod
    def valid_goal(cls, value: str) -> str:
        if value not in {"maximize", "minimize"}:
            raise ValueError("目标无效")
        return value

    @field_validator("strategy")
    @classmethod
    def valid_strategy(cls, value: str) -> str:
        if value not in bridge.STRATEGIES:
            raise ValueError("推荐方法无效")
        return value






class ComparisonPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    dataset_id: str
    goal: str
    threshold: float | None = Field(default=None, ge=-1_000_000, le=1_000_000)
    budget: int = Field(ge=1, le=10)
    mode: str

    @field_validator("dataset_id")
    @classmethod
    def valid_dataset(cls, value: str) -> str:
        if value != "demo-concrete" and DATASET_ID.fullmatch(value) is None:
            raise ValueError("dataset 编号格式无效")
        return value

    @field_validator("goal")
    @classmethod
    def valid_goal(cls, value: str) -> str:
        if value not in {"maximize", "minimize"}:
            raise ValueError("目标无效")
        return value

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, value: str) -> str:
        if value not in {"evidence", "rehearsal"}:
            raise ValueError("比较模式无效")
        return value


class ComparisonCreateRequest(ComparisonPreviewRequest):
    request_id: str

    @field_validator("request_id")
    @classmethod
    def valid_request(cls, value: str) -> str:
        if REQUEST_ID.fullmatch(value) is None:
            raise ValueError("request ID 格式无效")
        return value


class ComparisonRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str

    @field_validator("request_id")
    @classmethod
    def valid_request(cls, value: str) -> str:
        if REQUEST_ID.fullmatch(value) is None:
            raise ValueError("request ID 格式无效")
        return value




class CopilotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: str
    project_id: str | None = None
    candidate_id: str | None = None
    question: str = Field(default="", max_length=copilot.MAX_QUESTION_CHARS)

    @field_validator("action")
    @classmethod
    def valid_action(cls, value: str) -> str:
        if value not in copilot.ACTIONS:
            raise ValueError("action 无效")
        return value

    @field_validator("project_id")
    @classmethod
    def valid_project(cls, value: str | None) -> str | None:
        if value is not None and copilot.PROJECT_ID.fullmatch(value) is None:
            raise ValueError("项目编号格式无效")
        return value

    @field_validator("candidate_id")
    @classmethod
    def valid_candidate(cls, value: str | None) -> str | None:
        if value is not None and copilot.CANDIDATE_ID.fullmatch(value) is None:
            raise ValueError("候选编号格式无效")
        return value

    @model_validator(mode="after")
    def candidate_only_for_candidate(self):
        if self.candidate_id is not None and self.action != "candidate":
            raise ValueError("candidate_id 只允许用于 candidate action")
        return self


class LibraryCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    left_project_id: str
    right_project_id: str

    @field_validator("left_project_id", "right_project_id")
    @classmethod
    def valid_project(cls, value: str) -> str:
        if project_library.PROJECT_ID.fullmatch(value) is None:
            raise ValueError("项目编号格式无效")
        return value


class IntakeSchemaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    roles: dict[str, str]
    display_names: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    dataset_name: str = ""

    @field_validator("roles")
    @classmethod
    def valid_roles(cls, value: dict[str, str]) -> dict[str, str]:
        if any(role not in {"control", "context", "target", "posthoc", "ignored"} for role in value.values()):
            raise ValueError("字段角色无效")
        return value


class IntakeAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    warning_ids: list[str]


class CustomPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    dataset_id: str
    goal: str
    strategy: str
    threshold: float | None = Field(default=None, ge=-1_000_000, le=1_000_000)
    project_id: str | None = None

    @field_validator("project_id")
    @classmethod
    def valid_project(cls, value: str | None) -> str | None:
        if value is not None and CUSTOM_PROJECT_ID.fullmatch(value) is None:
            raise ValueError("项目编号格式无效")
        return value

    @field_validator("dataset_id")
    @classmethod
    def valid_dataset(cls, value: str) -> str:
        if DATASET_ID.fullmatch(value) is None:
            raise ValueError("dataset 编号格式无效")
        return value

    @field_validator("goal")
    @classmethod
    def valid_goal(cls, value: str) -> str:
        if value not in {"maximize", "minimize"}:
            raise ValueError("目标无效")
        return value

    @field_validator("strategy")
    @classmethod
    def valid_strategy(cls, value: str) -> str:
        if value not in bridge.STRATEGIES:
            raise ValueError("推荐方法无效")
        return value


class CustomCreateRequest(CustomPreviewRequest):
    budget: int = Field(ge=1, le=20)


class RevealRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    recommendation_id: str

    @field_validator("recommendation_id")
    @classmethod
    def valid_recommendation(cls, value: str) -> str:
        if RECOMMENDATION_ID.fullmatch(value) is None:
            raise ValueError("建议编号无效")
        return value


def _project_id(value: str) -> str:
    if PROJECT_ID.fullmatch(value) is None:
        raise HTTPException(400, "项目编号格式无效")
    return value


def _audited(view: dict) -> dict:
    snapshot = view.get("snapshot")
    audit = view.get("audit")
    pending = view.get("pending")
    history = view.get("history")
    if (not isinstance(snapshot, dict) or not isinstance(audit, dict)
            or audit.get("test_unchanged") is not True
            or audit.get("models_present") is not True
            or audit.get("status") != snapshot.get("status")
            or not isinstance(history, list)
            or len(history) != snapshot.get("revealed_count")
            or (snapshot.get("status") == "awaiting_user_confirmation") != isinstance(pending, dict)
            or (isinstance(pending, dict) and ({"target", "revealed_target", "CompressiveStrength"} & set(pending)))):
        raise HTTPException(503, "项目证据校验失败，结果展示已阻断")
    return view


@app.exception_handler(bridge.NextTestUncertain)
async def uncertain_error(_request: Request, _error: bridge.NextTestUncertain) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "操作状态不确定。请使用项目编号只读恢复，不要重复提交。", "uncertain": True})


@app.exception_handler(bridge.NextTestAdapterError)
async def adapter_error(_request: Request, error: bridge.NextTestAdapterError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(error)})


@app.middleware("http")
async def no_store(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "mode": "historical_replay", "production_trial": False}

@app.get("/api/runtime")
def runtime() -> dict:
    """Report capability switches without exposing any credential."""
    try:
        configured = copilot.load_config() is not None
    except Exception:
        configured = False
    return {
        "llm_configured": configured,
        "llm_mode": "deepseek" if configured else "local_rules",
        "historical_replay": True,
    }


@lru_cache(maxsize=1)
def _landscape() -> dict:
    value = bridge.observed_landscape()
    if (value.get("scope") != "observed_training_only" or value.get("count") != 252
            or not isinstance(value.get("rows"), list) or len(value["rows"]) != 252):
        raise HTTPException(503, "已知数据图层校验失败")
    return value


@app.get("/api/landscape")
def landscape() -> dict:
    return _landscape()


@app.post("/api/preview")
def preview(body: PreviewRequest) -> dict:
    value = bridge.preview(goal=body.goal, threshold=body.threshold, strategy=body.strategy, project_id=body.project_id)
    rows = value.get("rows") if isinstance(value, dict) else None
    if (value.get("scope") != "candidate_pool_no_labels" or not isinstance(rows, list)
            or len(rows) != value.get("candidate_count")
            or any(not isinstance(row, dict) or ({"target", "revealed_target", "CompressiveStrength"} & set(row)) for row in rows)
            or not isinstance(value.get("selected"), dict)
            or not isinstance(value.get("rankings"), dict)):
        raise HTTPException(503, "候选投影校验失败")
    return value




def _intake_id(value: str) -> str:
    if INTAKE_ID.fullmatch(value) is None:
        raise HTTPException(400, "intake 编号格式无效")
    return value


def _dataset_id(value: str) -> str:
    if DATASET_ID.fullmatch(value) is None:
        raise HTTPException(400, "dataset 编号格式无效")
    return value


def _custom_id(value: str) -> str:
    if CUSTOM_PROJECT_ID.fullmatch(value) is None:
        raise HTTPException(400, "custom 项目编号格式无效")
    return value




def _comparison_id(value: str) -> str:
    if COMPARISON_ID.fullmatch(value) is None:
        raise HTTPException(400, "comparison 编号格式无效")
    return value


def _comparison_result(value: dict) -> dict:
    audit = value.get("audit")
    if audit is not None and not audit.get("valid"):
        raise HTTPException(503, {"message": "comparison 审计失败，拒绝返回部分成功结果", "errors": audit.get("errors", [])[:8]})
    return value


@app.post("/api/comparisons/preview")
def comparison_preview(body: ComparisonPreviewRequest) -> dict:
    return bridge.comparison_preview(dataset_id=body.dataset_id, goal=body.goal, threshold=body.threshold, budget=body.budget, mode=body.mode)


@app.post("/api/comparisons")
def comparison_create(body: ComparisonCreateRequest) -> dict:
    try:
        return _comparison_result(bridge.comparison_create(dataset_id=body.dataset_id, goal=body.goal, threshold=body.threshold, budget=body.budget, mode=body.mode, request_id=body.request_id))
    except bridge.NextTestUncertain as exc:
        raise HTTPException(409, {"message": str(exc), "request_id": body.request_id, "uncertain": True}) from exc


@app.get("/api/comparisons/{comparison_id}")
def comparison_inspect(comparison_id: str) -> dict:
    return _comparison_result(bridge.comparison_inspect(_comparison_id(comparison_id)))


@app.post("/api/comparisons/{comparison_id}/run")
def comparison_run(comparison_id: str, body: ComparisonRunRequest) -> dict:
    try:
        return _comparison_result(bridge.comparison_run(_comparison_id(comparison_id), body.request_id))
    except bridge.NextTestUncertain as exc:
        raise HTTPException(409, {"message": str(exc), "comparison_id": comparison_id, "request_id": body.request_id, "uncertain": True}) from exc


@app.get("/api/comparisons/{comparison_id}/export")
def comparison_export(comparison_id: str, format: str = "json") -> dict:
    if format not in {"json", "csv"}:
        raise HTTPException(400, "导出格式无效")
    return bridge.comparison_export(_comparison_id(comparison_id), format)


@app.post("/api/intakes")
async def create_intake(request: Request) -> dict:
    filename = unquote(request.headers.get("X-NextTest-Filename", ""))
    content_type = request.headers.get("content-type", "text/csv").split(";", 1)[0].strip()
    length = request.headers.get("content-length")
    if not filename or not filename.lower().endswith(".csv") or "/" in filename or "\\" in filename:
        raise HTTPException(400, "文件名必须是单个 .csv 文件")
    if length is not None:
        try:
            if int(length) > 10 * 1024 * 1024:
                raise HTTPException(413, "CSV 超过 10 MiB")
        except ValueError as exc:
            raise HTTPException(400, "Content-Length 无效") from exc
    body = await request.body()
    if not body or len(body) > 10 * 1024 * 1024:
        raise HTTPException(413, "CSV 为空或超过 10 MiB")
    intake_id = f"intake_{uuid.uuid4().hex}"
    try:
        return bridge.intake_create(filename=filename, content_type=content_type, content_b64=base64.b64encode(body).decode("ascii"), intake_id=intake_id)
    except bridge.NextTestUncertain as exc:
        raise HTTPException(409, {"message": str(exc), "intake_id": intake_id, "uncertain": True}) from exc


@app.get("/api/intakes/{intake_id}")
def inspect_intake(intake_id: str) -> dict:
    return bridge.intake_inspect(_intake_id(intake_id))


@app.post("/api/intakes/{intake_id}/schema")
def assign_intake_schema(intake_id: str, body: IntakeSchemaRequest) -> dict:
    return bridge.intake_schema(_intake_id(intake_id), roles=body.roles, display_names=body.display_names, units=body.units, dataset_name=body.dataset_name)


@app.post("/api/intakes/{intake_id}/gate")
def gate_intake(intake_id: str) -> dict:
    return bridge.intake_gate(_intake_id(intake_id))


@app.post("/api/intakes/{intake_id}/acknowledge")
def acknowledge_intake(intake_id: str, body: IntakeAckRequest) -> dict:
    return bridge.intake_ack(_intake_id(intake_id), body.warning_ids)


@app.post("/api/intakes/{intake_id}/freeze")
def freeze_intake(intake_id: str) -> dict:
    dataset_id = f"dataset_{uuid.uuid4().hex}"
    try:
        return bridge.intake_freeze(_intake_id(intake_id), dataset_id=dataset_id)
    except bridge.NextTestUncertain as exc:
        raise HTTPException(409, {"message": str(exc), "dataset_id": dataset_id, "uncertain": True}) from exc


@app.get("/api/datasets/{dataset_id}")
def inspect_dataset(dataset_id: str) -> dict:
    return bridge.dataset_inspect(_dataset_id(dataset_id))


@app.get("/api/custom/datasets/{dataset_id}/landscape")
def custom_landscape(dataset_id: str) -> dict:
    value = bridge.custom_landscape(_dataset_id(dataset_id))
    if not isinstance(value, dict) or value.get("scope") != "observed_training_only" or not isinstance(value.get("rows"), list) or len(value["rows"]) != value.get("count"):
        raise HTTPException(503, "custom 已知数据图层校验失败")
    return value


@app.post("/api/custom/preview")
def custom_preview(body: CustomPreviewRequest) -> dict:
    value = bridge.custom_preview(dataset_id=body.dataset_id, strategy=body.strategy, goal=body.goal, threshold=body.threshold, project_id=body.project_id)
    rows = value.get("rows") if isinstance(value, dict) else None
    if (not isinstance(value, dict) or value.get("scope") != "custom_candidate_pool_no_labels" or not isinstance(rows, list)
            or len(rows) != value.get("candidate_count")
            or any(not isinstance(row, dict) or ({"target", "revealed_target", "tensile_strength_ksi", "CompressiveStrength"} & set(row)) for row in rows)):
        raise HTTPException(503, "custom 候选投影校验失败")
    return value


@app.post("/api/custom/projects")
def create_custom(body: CustomCreateRequest) -> dict:
    pid = f"p3_{uuid.uuid4().hex}"
    try:
        value = bridge.custom_create(dataset_id=body.dataset_id, project_id=pid, goal=body.goal, threshold=body.threshold, budget=body.budget, strategy=body.strategy)
    except bridge.NextTestUncertain as exc:
        raise HTTPException(409, {"message": str(exc), "project_id": pid, "uncertain": True}) from exc
    return _audited(value)


@app.get("/api/custom/projects/{project_id}")
def inspect_custom(project_id: str) -> dict:
    return _audited(bridge.custom_inspect(_custom_id(project_id)))


@app.post("/api/custom/projects/{project_id}/recommend")
def recommend_custom(project_id: str) -> dict:
    return _audited(bridge.custom_recommend(_custom_id(project_id)))


@app.post("/api/custom/projects/{project_id}/reveal")
def reveal_custom(project_id: str, body: RevealRequest) -> dict:
    return _audited(bridge.custom_reveal(_custom_id(project_id), body.recommendation_id))


@app.post("/api/projects")
def create_project(body: CreateRequest) -> dict:
    project_id = bridge.new_project_id()
    # The generated ID is returned even if the worker times out, so a caller can inspect it.
    try:
        view = bridge.create(goal=body.goal, strategy=body.strategy, budget=body.budget,
                             threshold=body.threshold, project_id=project_id)
    except bridge.NextTestUncertain as exc:
        raise HTTPException(409, {"message": str(exc), "project_id": project_id, "uncertain": True}) from exc
    return _audited(view)


@app.get("/api/projects/{project_id}")
def inspect_project(project_id: str) -> dict:
    return _audited(bridge.inspect(_project_id(project_id)))


@app.post("/api/projects/{project_id}/recommend")
def recommend_project(project_id: str) -> dict:
    return _audited(bridge.recommend(_project_id(project_id)))


@app.post("/api/projects/{project_id}/reveal")
def reveal_project(project_id: str, body: RevealRequest) -> dict:
    return _audited(bridge.reveal(_project_id(project_id), body.recommendation_id))




def _copilot_project_view(project_id: str | None) -> dict | None:
    if project_id is None:
        return None
    if project_id.startswith("p2_"):
        return _audited(bridge.inspect(_project_id(project_id)))
    if project_id.startswith("p3_"):
        return _audited(bridge.custom_inspect(_custom_id(project_id)))
    raise HTTPException(400, "项目编号格式无效")


def _copilot_candidate(view: dict | None, candidate_id: str | None) -> dict | None:
    if not isinstance(view, dict):
        return None
    pending = view.get("pending")
    if isinstance(pending, dict):
        if candidate_id is None or pending.get("row_id") == candidate_id:
            if {"target", "revealed_target"} & set(pending):
                raise HTTPException(503, "候选边界校验失败")
            return pending
    snapshot = view.get("snapshot")
    if not isinstance(snapshot, dict):
        return None
    try:
        if str(snapshot.get("project_id", "")).startswith("p3_"):
            preview = bridge.custom_preview(dataset_id=snapshot.get("dataset_id"), strategy=snapshot.get("strategy"), goal=snapshot.get("goal"), threshold=snapshot.get("threshold"), project_id=snapshot.get("project_id"))
        else:
            preview = bridge.preview(strategy=snapshot.get("strategy"), goal=snapshot.get("goal"), threshold=snapshot.get("threshold"), project_id=snapshot.get("project_id"))
    except Exception:  # noqa: BLE001
        return None
    rows = preview.get("rows") if isinstance(preview, dict) else None
    if not isinstance(rows, list):
        return None
    if candidate_id is not None:
        for row in rows:
            if isinstance(row, dict) and row.get("row_id") == candidate_id:
                return row
        return None
    selected = preview.get("selected")
    if isinstance(selected, dict):
        selected_id = selected.get("row_id")
        for row in rows:
            if isinstance(row, dict) and row.get("row_id") == selected_id:
                return row
    return None


@app.post("/api/copilot/explain")
def copilot_explain(body: CopilotRequest) -> dict:
    # Check configuration before any project lookup or transport call.
    config = copilot.load_config()
    if config is None:
        raise HTTPException(503, detail={"code": "LLM_NOT_CONFIGURED", "message": "证据助手未配置；不发起网络请求。"})
    try:
        view = _copilot_project_view(body.project_id)
        candidate = _copilot_candidate(view, body.candidate_id) if body.action == "candidate" else None
        facts = copilot.build_facts(body.action, view=view, candidate=candidate, candidate_id=body.candidate_id)
        return copilot.explain(body.action, facts, body.question, config=config)
    except copilot.CopilotTimeout as exc:
        raise HTTPException(504, detail={"code": "LLM_TIMEOUT", "message": "证据助手请求超时。"}) from exc
    except copilot.CopilotInvalidResponse as exc:
        raise HTTPException(502, detail={"code": "LLM_INVALID_RESPONSE", "message": "证据助手返回格式无效。"}) from exc
    except copilot.CopilotUpstreamError as exc:
        raise HTTPException(502, detail={"code": "LLM_UPSTREAM_ERROR", "message": "证据助手上游请求失败。"}) from exc


@app.get("/api/copilot/status")
def copilot_status() -> dict:
    """Configuration status only; never sends a model request or returns a secret."""
    return copilot.public_status()


@app.post("/api/agent/brief")
def local_agent_brief(body: CopilotRequest) -> dict:
    """No-network fallback using the same audited public-fact boundary."""
    view = _copilot_project_view(body.project_id)
    candidate = _copilot_candidate(view, body.candidate_id) if body.action == "candidate" else None
    facts = copilot.build_facts(body.action, view=view, candidate=candidate, candidate_id=body.candidate_id)
    return copilot.explain_local(body.action, facts, body.question)


def _evidence_package(view: dict) -> dict:
    try:
        return evidence_package.build_evidence_package(view)
    except evidence_package.EvidencePackageError as exc:
        raise HTTPException(503, detail={"code": "EVIDENCE_PACKAGE_INVALID", "message": "证据包未能通过只读审计或字段校验。"}) from exc


@app.get("/api/projects/{project_id}/evidence-package")
def project_evidence_package(project_id: str) -> dict:
    return _evidence_package(_audited(bridge.inspect(_project_id(project_id))))


@app.get("/api/custom/projects/{project_id}/evidence-package")
def custom_project_evidence_package(project_id: str) -> dict:
    return _evidence_package(_audited(bridge.custom_inspect(_custom_id(project_id))))


def _library_view(project_id: str) -> dict:
    if project_id.startswith("p2_"):
        return _audited(bridge.inspect(_project_id(project_id)))
    if project_id.startswith("p3_"):
        return _audited(bridge.custom_inspect(_custom_id(project_id)))
    raise HTTPException(400, "项目编号格式无效")


def _library_package(project_id: str) -> dict:
    try:
        return evidence_package.build_evidence_package(_library_view(project_id))
    except evidence_package.EvidencePackageError as exc:
        raise HTTPException(503, detail={"code": "EVIDENCE_PACKAGE_INVALID", "message": "项目证据包未能通过只读审计。"}) from exc


@app.get("/api/library")
def project_library_index() -> dict:
    packages = []
    for project_id in project_library.discover_project_ids():
        try:
            packages.append(_library_package(project_id))
        except Exception:  # noqa: BLE001
            # An audited project that fails validation is not partially exposed.
            continue
    return project_library.library_response(packages)


@app.get("/api/library/{project_id}/card")
def project_library_card(project_id: str) -> dict:
    return project_library.card_from_package(_library_package(project_id))


@app.post("/api/library/compare")
def project_library_compare(body: LibraryCompareRequest) -> dict:
    try:
        left = _library_package(body.left_project_id)
        right = _library_package(body.right_project_id)
    except HTTPException as exc:
        raise HTTPException(503, detail=project_library.audit_failed_error()) from exc
    try:
        return project_library.compare_packages(left, right)
    except project_library.ProjectLibraryError as exc:
        raise HTTPException(503, detail={"code": "PROJECT_LIBRARY_INVALID", "message": "比较输入无效。"}) from exc


@app.get("/{path:path}")
def frontend(path: str):
    if not DIST.is_dir():
        raise HTTPException(503, "前端尚未构建，请在 frontend 目录运行 npm install 和 npm run build")
    if path.startswith("api/"):
        raise HTTPException(404, "Not found")
    requested = (DIST / path).resolve()
    if requested.is_file() and requested.is_relative_to(DIST.resolve()):
        return FileResponse(requested)
    return FileResponse(DIST / "index.html")
