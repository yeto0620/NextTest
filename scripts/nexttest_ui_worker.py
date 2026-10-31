"""Fixed-schema local worker for the NextTest historical replay UI."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nexttest import experiment as exp
from nexttest import p3_data, p3_experiment
from nexttest import comparison
from nexttest.project_store import ProjectStore

PROJECT_ID = re.compile(r"^p2_[0-9a-f]{32}$")
CUSTOM_PROJECT_ID = re.compile(r"^p3_[0-9a-f]{32}$")
INTAKE_ID = re.compile(r"^intake_[0-9a-f]{32}$")
DATASET_ID = re.compile(r"^dataset_[0-9a-f]{32}$")
COMPARISON_ID = re.compile(r"^cmp_[0-9a-f]{32}$")
REQUEST_ID = re.compile(r"^req_[0-9a-f]{16,64}$")
RECOMMENDATION_ID = re.compile(r"^rec-[0-9]{6}$")
ALLOWED = {
    "landscape": {"operation"},
    "preview": {"operation", "strategy", "goal", "threshold", "project_id"},
    "create": {"operation", "project_id", "goal", "threshold", "budget", "strategy"},
    "inspect": {"operation", "project_id"},
    "recommend": {"operation", "project_id"},
    "reveal": {"operation", "project_id", "recommendation_id"},
    "intake_create": {"operation", "filename", "content_type", "content_b64", "intake_id"},
    "intake_inspect": {"operation", "intake_id"},
    "intake_schema": {"operation", "intake_id", "roles", "display_names", "units", "dataset_name"},
    "intake_gate": {"operation", "intake_id"},
    "intake_ack": {"operation", "intake_id", "warning_ids"},
    "intake_freeze": {"operation", "intake_id", "dataset_id"},
    "dataset_inspect": {"operation", "dataset_id"},
    "custom_landscape": {"operation", "dataset_id"},
    "custom_preview": {"operation", "dataset_id", "strategy", "goal", "threshold", "project_id"},
    "custom_create": {"operation", "dataset_id", "goal", "threshold", "budget", "strategy", "project_id"},
    "custom_inspect": {"operation", "project_id"},
    "custom_recommend": {"operation", "project_id"},
    "custom_reveal": {"operation", "project_id", "recommendation_id"},
    "comparison_preview": {"operation", "dataset_id", "goal", "threshold", "budget", "mode"},
    "comparison_create": {"operation", "dataset_id", "goal", "threshold", "budget", "mode", "request_id"},
    "comparison_inspect": {"operation", "comparison_id"},
    "comparison_run": {"operation", "comparison_id", "request_id"},
    "comparison_export": {"operation", "comparison_id", "format"},
}


def _validated(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("请求格式无效")
    operation = payload.get("operation")
    if operation not in ALLOWED or set(payload) != ALLOWED[operation]:
        raise ValueError("请求字段无效")
    if operation == "landscape":
        return payload
    if operation == "intake_create":
        if not isinstance(payload["filename"], str) or not isinstance(payload["content_type"], str) or not isinstance(payload["content_b64"], str) or not isinstance(payload["intake_id"], str) or INTAKE_ID.fullmatch(payload["intake_id"]) is None:
            raise ValueError("请求字段无效")
        return payload
    if operation in {"intake_inspect", "intake_schema", "intake_gate", "intake_ack", "intake_freeze"}:
        if not isinstance(payload["intake_id"], str) or INTAKE_ID.fullmatch(payload["intake_id"]) is None:
            raise ValueError("intake ID 无效")
        if operation == "intake_freeze" and (not isinstance(payload["dataset_id"], str) or DATASET_ID.fullmatch(payload["dataset_id"]) is None):
            raise ValueError("dataset ID 无效")
        if operation == "intake_schema":
            if not isinstance(payload["roles"], dict) or not isinstance(payload["display_names"], dict) or not isinstance(payload["units"], dict) or not isinstance(payload["dataset_name"], str):
                raise ValueError("字段角色请求无效")
        if operation == "intake_ack" and (not isinstance(payload["warning_ids"], list) or any(not isinstance(x, str) for x in payload["warning_ids"])):
            raise ValueError("warning IDs 无效")
        return payload
    if operation in {"dataset_inspect", "custom_landscape"}:
        if not isinstance(payload["dataset_id"], str) or DATASET_ID.fullmatch(payload["dataset_id"]) is None:
            raise ValueError("dataset ID 无效")
        return payload
    if operation in {"custom_preview", "custom_create"}:
        if not isinstance(payload["dataset_id"], str) or DATASET_ID.fullmatch(payload["dataset_id"]) is None:
            raise ValueError("dataset ID 无效")
        if payload["goal"] not in {"maximize", "minimize"} or payload["strategy"] not in {"random", "greedy_prediction", "max_disagreement"}:
            raise ValueError("目标或方法无效")
        threshold = payload["threshold"]
        if threshold is not None and (type(threshold) not in {float, int} or not -1e6 <= threshold <= 1e6):
            raise ValueError("阈值无效")
        if payload.get("project_id") is not None and (not isinstance(payload["project_id"], str) or CUSTOM_PROJECT_ID.fullmatch(payload["project_id"]) is None):
            raise ValueError("项目编号无效")
        if operation == "custom_create":
            if type(payload["budget"]) is not int or not 1 <= payload["budget"] <= 20:
                raise ValueError("预算无效")
            if not isinstance(payload["project_id"], str) or CUSTOM_PROJECT_ID.fullmatch(payload["project_id"]) is None:
                raise ValueError("项目编号无效")
        return payload
    if operation in {"comparison_preview", "comparison_create"}:
        if not isinstance(payload["dataset_id"], str) or (payload["dataset_id"] != "demo-concrete" and DATASET_ID.fullmatch(payload["dataset_id"]) is None):
            raise ValueError("dataset ID 无效")
        if payload["goal"] not in {"maximize", "minimize"} or payload["mode"] not in {"evidence", "rehearsal"}:
            raise ValueError("比较目标或模式无效")
        if type(payload["budget"]) is not int or not 1 <= payload["budget"] <= 10:
            raise ValueError("预算无效")
        if payload["threshold"] is not None and (type(payload["threshold"]) not in {float, int} or not -1e6 <= payload["threshold"] <= 1e6):
            raise ValueError("阈值无效")
        if operation == "comparison_create" and (not isinstance(payload["request_id"], str) or REQUEST_ID.fullmatch(payload["request_id"]) is None):
            raise ValueError("request ID 无效")
        return payload
    if operation in {"comparison_inspect", "comparison_run", "comparison_export"}:
        if not isinstance(payload["comparison_id"], str) or COMPARISON_ID.fullmatch(payload["comparison_id"]) is None:
            raise ValueError("comparison ID 无效")
        if operation == "comparison_run" and (not isinstance(payload["request_id"], str) or REQUEST_ID.fullmatch(payload["request_id"]) is None):
            raise ValueError("request ID 无效")
        if operation == "comparison_export" and payload["format"] not in {"json", "csv"}:
            raise ValueError("导出格式无效")
        return payload
    if operation in {"custom_inspect", "custom_recommend", "custom_reveal"}:
        if not isinstance(payload["project_id"], str) or CUSTOM_PROJECT_ID.fullmatch(payload["project_id"]) is None:
            raise ValueError("custom 项目编号无效")
        if operation == "custom_reveal" and (not isinstance(payload["recommendation_id"], str) or RECOMMENDATION_ID.fullmatch(payload["recommendation_id"]) is None):
            raise ValueError("建议编号无效")
        return payload
    if operation == "preview":
        if payload["strategy"] not in {"random", "greedy_prediction", "max_disagreement"}:
            raise ValueError("目标或方法无效")
        if payload["goal"] not in {"maximize", "minimize"}:
            raise ValueError("目标或方法无效")
        threshold = payload["threshold"]
        if threshold is not None and (type(threshold) not in {float, int} or not -1e6 <= threshold <= 1e6):
            raise ValueError("阈值无效")
        project_id = payload.get("project_id")
        if project_id is not None and (not isinstance(project_id, str) or PROJECT_ID.fullmatch(project_id) is None):
            raise ValueError("项目编号无效")
        return payload
    pid = payload["project_id"]
    if not isinstance(pid, str) or PROJECT_ID.fullmatch(pid) is None:
        raise ValueError("项目编号无效")
    if operation == "create":
        if payload["goal"] not in {"maximize", "minimize"} or payload["strategy"] not in {"random", "greedy_prediction", "max_disagreement"}:
            raise ValueError("目标或方法无效")
        if type(payload["budget"]) is not int or not 1 <= payload["budget"] <= 20:
            raise ValueError("预算无效")
        threshold = payload["threshold"]
        if threshold is not None and (type(threshold) not in {float, int} or not -1e6 <= threshold <= 1e6):
            raise ValueError("阈值无效")
    if operation == "reveal" and (not isinstance(payload["recommendation_id"], str) or RECOMMENDATION_ID.fullmatch(payload["recommendation_id"]) is None):
        raise ValueError("建议编号无效")
    return payload


def _project_view(pid: str) -> dict:
    snapshot = exp.get_experiment(pid).to_dict()
    audit = exp.inspect_experiment(pid).to_dict()
    store = ProjectStore(exp.PROJECT_ROOT / pid)
    events = store.events()
    base, _, _ = exp.load_frozen_base()
    controls = {
        str(row["_row_id"]): {col: float(row[col]) for col in base.candidates.feature_columns}
        for _, row in base.candidates.frame.iterrows()
    }
    pending = None
    history = []
    transition = None
    recommendations = {}
    for event in events:
        kind = event["event_type"]
        item = event["payload"]
        if kind == "recommendation":
            recommendations[item["recommendation_id"]] = item
            pending = {
                "recommendation_id": item["recommendation_id"],
                "row_id": item["row_id"],
                "controls": controls[item["row_id"]],
                "prediction": item["prediction"],
                "disagreement": item["disagreement"],
                "reason": item["reason"],
            }
        elif kind == "label_released":
            original = recommendations[item["recommendation_id"]]
            history.append({
                "round": len(history) + 1,
                "row_id": item["row_id"],
                "prediction": item["prediction"],
                "revealed_target": item["target"],
                "absolute_error": item["absolute_error"],
                "strategy": original["strategy"],
            })
            pending = None
        elif kind == "model_updated":
            original = recommendations[item["recommendation_id"]]
            transition = {
                "before": {
                    "model_sha": original.get("model_sha"),
                    "revealed_count": int(snapshot["revealed_count"]) - 1,
                    "remaining_budget": int(item["remaining_budget"]) + 1,
                    "observed_count": int(item["observed_count"]) - 1,
                    "candidate_count": int(item["candidate_count"]) + 1,
                    "pending_row": original.get("row_id"),
                },
                "after": {
                    "model_sha": item.get("model_sha"),
                    "revealed_count": int(snapshot["revealed_count"]),
                    "remaining_budget": int(item["remaining_budget"]),
                    "observed_count": int(item["observed_count"]),
                    "candidate_count": int(item["candidate_count"]),
                    "latest_revealed_row": item.get("row_id"),
                },
            }
    if snapshot["status"] != "awaiting_user_confirmation":
        pending = None
    return {"snapshot": snapshot, "audit": audit, "pending": pending, "history": history, "transition": transition}


def handle(payload: object) -> dict:
    request = _validated(payload)
    op = request["operation"]
    if op == "preview":
        return {"ok": True, "data": exp.preview_candidates(strategy=request["strategy"], goal=request["goal"], threshold=request["threshold"], project_id=request.get("project_id"))}
    if op == "landscape":
        base, split, _ = exp.load_frozen_base()
        observed = base.observed
        columns = ["_row_id", "Cement", "BlastFurnaceSlag", "FlyAsh", "Water",
                   "Superplasticizer", "CoarseAggregate", "FineAggregate", "CompressiveStrength"]
        rows = observed.frame[columns].to_dict(orient="records")
        return {"ok": True, "data": {"scope": "observed_training_only", "rows": rows,
                                      "count": len(rows), "split_sha256": split["split_sha256"]}}
    if op == "intake_create":
        import base64
        try:
            raw = base64.b64decode(request["content_b64"], validate=True)
        except Exception as exc:
            raise ValueError("CSV 编码无效") from exc
        return {"ok": True, "data": p3_data.intake_create(raw, filename=request["filename"], content_type=request["content_type"], intake_id=request["intake_id"])}
    if op == "intake_inspect":
        return {"ok": True, "data": p3_data.intake_inspect(request["intake_id"])}
    if op == "intake_schema":
        return {"ok": True, "data": p3_data.intake_assign_schema(request["intake_id"], roles=request["roles"], display_names=request["display_names"], units=request["units"], dataset_name=request["dataset_name"])}
    if op == "intake_gate":
        return {"ok": True, "data": p3_data.intake_gate(request["intake_id"])}
    if op == "intake_ack":
        return {"ok": True, "data": p3_data.intake_acknowledge(request["intake_id"], request["warning_ids"])}
    if op == "intake_freeze":
        return {"ok": True, "data": p3_data.intake_freeze(request["intake_id"], dataset_id=request["dataset_id"])}
    if op == "dataset_inspect":
        return {"ok": True, "data": p3_data.dataset_inspect(request["dataset_id"])}
    if op == "custom_landscape":
        return {"ok": True, "data": p3_experiment.custom_landscape(request["dataset_id"])}
    if op == "custom_preview":
        return {"ok": True, "data": p3_experiment.preview_custom(request["dataset_id"], strategy=request["strategy"], goal=request["goal"], threshold=request["threshold"], project_id=request.get("project_id"))}
    if op == "custom_create":
        return {"ok": True, "data": p3_experiment.create_custom_project(dataset_id=request["dataset_id"], goal=request["goal"], threshold=request["threshold"], budget=request["budget"], strategy=request["strategy"], project_id=request["project_id"])}
    if op == "custom_inspect":
        return {"ok": True, "data": p3_experiment.inspect_custom(request["project_id"])}
    if op == "custom_recommend":
        return {"ok": True, "data": p3_experiment.recommend_custom(request["project_id"])}
    if op == "custom_reveal":
        return {"ok": True, "data": p3_experiment.reveal_custom(request["project_id"], request["recommendation_id"])}
    if op == "comparison_preview":
        return {"ok": True, "data": comparison.preview_plan(dataset_id=request["dataset_id"], goal=request["goal"], threshold=request["threshold"], budget=request["budget"], mode=request["mode"])}
    if op == "comparison_create":
        return {"ok": True, "data": comparison.create_comparison(dataset_id=request["dataset_id"], goal=request["goal"], threshold=request["threshold"], budget=request["budget"], mode=request["mode"], request_id=request["request_id"])}
    if op == "comparison_inspect":
        return {"ok": True, "data": comparison.inspect_comparison(request["comparison_id"])}
    if op == "comparison_run":
        return {"ok": True, "data": comparison.run_comparison(request["comparison_id"], request["request_id"])}
    if op == "comparison_export":
        return {"ok": True, "data": comparison.export_comparison(request["comparison_id"], request["format"])}
    pid = request["project_id"]
    if op == "create":
        exp.create_experiment(goal=request["goal"], threshold=request["threshold"],
                              budget=request["budget"], strategy=request["strategy"], project_id=pid)
    elif op == "recommend":
        exp.recommend_next(pid)
    elif op == "reveal":
        exp.confirm_and_reveal(pid, request["recommendation_id"])
    return {"ok": True, "data": _project_view(pid)}


def main() -> int:
    try:
        response = handle(json.loads(sys.stdin.read()))
        print(json.dumps(response, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
