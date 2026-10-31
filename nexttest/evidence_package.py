"""Deterministic, read-only defense evidence package for P2/P3 projects.

The package is built only after the caller has passed the existing API audit.
This module never writes project files, trains a model, calls an LLM, or reads
raw CSV/test rows.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA_VERSION = "nexttest_evidence_package_v1"
TEMPLATE_VERSION = "p5b-defense-v1"
PAYLOAD_HASH_FIELD = "payload_sha256"
LIMITATIONS = (
    "历史回放不是新实验，也不是新的物理测量。",
    "模型预测不是实测值；候选在揭示前没有真实 target。",
    "模型分歧不是概率、置信度或统计不确定性保证；IQR 不是 95% CI。",
    "本包不证明策略优越、因果、成本节省、工业有效性或跨数据集泛化。",
    "独立 test 标签、原始 CSV 和任意本机路径不进入本包。",
    "单位来自公开或用户声明 metadata，未做独立物理单位验证。",
)

P2_DATASET = {
    "dataset_id": "uci_concrete_compressive_strength",
    "display_name": "UCI Concrete Compressive Strength",
    "short_id": "uci-concrete",
    "target": {
        "name": "CompressiveStrength",
        "display_name": "Compressive strength",
        "unit": "MPa",
    },
    "units": {"CompressiveStrength": "MPa"},
    "unit_not_verified": True,
    "source": "UCI Machine Learning Repository (CC BY 4.0)",
    "historical_replay": True,
}

SNAPSHOT_KEYS = (
    "snapshot_version", "project_id", "status", "goal", "threshold", "budget",
    "remaining_budget", "strategy", "seed", "revealed_count", "observed_count",
    "candidate_count", "test_count", "current_model_sha", "initial_model_sha",
    "split_sha256", "source_canonical_sha256", "observed_row_ids_sha256",
    "test_sha256", "historical_replay", "dataset_id", "dataset_display_name",
    "dataset_short_id", "user_data_replay",
)
DATASET_KEYS = (
    "dataset_id", "display_name", "short_id", "target", "features", "units",
    "unit_not_verified", "counts", "gate_status", "sha256", "historical_replay",
)
AUDIT_KEYS = (
    "audit_version", "project_id", "status", "event_count", "event_chain_sha256",
    "tree_sha256", "project_manifest_sha256", "source_canonical_sha256",
    "split_sha256", "test_sha256", "observed_count", "candidate_count",
    "test_count", "test_unchanged", "models_present", "historical_replay",
    "valid", "auditor_schema", "auditor_version", "semantic_replay",
)
HISTORY_KEYS = ("round", "row_id", "prediction", "revealed_target", "absolute_error", "strategy")
FORBIDDEN_KEYS = {
    "pending", "test_labels", "test_rows", "raw_csv", "raw_data", "path",
    "file_path", "api_key", "authorization", "env", "environment", "events",
    "raw_audit", "candidate_target", "target_value", "revealed_target_before",
}


class EvidencePackageError(RuntimeError):
    code = "EVIDENCE_PACKAGE_INVALID"


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _public_snapshot(snapshot: dict) -> dict:
    return {key: snapshot[key] for key in SNAPSHOT_KEYS if key in snapshot}


def _public_audit(audit: dict) -> dict:
    return {key: audit[key] for key in AUDIT_KEYS if key in audit}


def _public_dataset(view: dict, snapshot: dict) -> dict:
    source = view.get("dataset")
    if isinstance(source, dict):
        result = {key: source[key] for key in DATASET_KEYS if key in source}
        if "counts" not in result:
            result["counts"] = {
                "observed": snapshot.get("observed_count"),
                "candidates": snapshot.get("candidate_count"),
                "test": snapshot.get("test_count"),
            }
        return result
    # P2 has a fixed public UCI dataset passport; counts come from this project.
    result = dict(P2_DATASET)
    result["counts"] = {
        "observed": snapshot.get("observed_count"),
        "candidates": snapshot.get("candidate_count"),
        "test": snapshot.get("test_count"),
    }
    return result


def _public_history(history: list) -> list[dict]:
    rows = []
    for item in history:
        if not isinstance(item, dict):
            continue
        rows.append({key: item[key] for key in HISTORY_KEYS if key in item})
    rows.sort(key=lambda row: (row.get("round", 0), str(row.get("row_id", ""))))
    return rows


def _defense_brief(history: list[dict]) -> dict:
    values = []
    for item in history:
        value = item.get("absolute_error")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    if not values:
        return {
            "template_version": TEMPLATE_VERSION,
            "revealed_count": 0,
            "mae": None,
            "max_absolute_error": None,
            "evidence_status": "insufficient",
            "summary": "尚未揭示任何历史结果，证据不足，不能计算预测误差。",
            "boundaries": list(LIMITATIONS),
        }
    mae = sum(values) / len(values)
    maximum = max(values)
    return {
        "template_version": TEMPLATE_VERSION,
        "revealed_count": len(values),
        "mae": mae,
        "max_absolute_error": maximum,
        "evidence_status": "available",
        "summary": (
            f"已揭示 {len(values)} 条历史结果；平均绝对误差为 {_number(mae)}；"
            f"最大绝对误差为 {_number(maximum)}。这是历史回放的描述性统计，不是新实验证据。"
        ),
        "boundaries": list(LIMITATIONS),
    }


def _number(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _markdown(package: dict) -> str:
    project = package["project_id"]
    dataset = package["dataset_public_metadata"]
    snapshot = package["snapshot_public"]
    audit = package["audit_public"]
    defense = package["defense_brief"]
    lines = [
        "# NextTest 答辩证据包",
        "",
        f"- 项目编号：`{project}`",
        f"- 数据：{dataset.get('display_name', dataset.get('dataset_id', '—'))}",
        f"- 状态：`{snapshot.get('status', '—')}`",
        f"- 目标：`{snapshot.get('goal', '—')}`；预算：`{snapshot.get('budget', '—')}`；剩余：`{snapshot.get('remaining_budget', '—')}`",
        f"- 已揭示：`{snapshot.get('revealed_count', 0)}`；已观测：`{snapshot.get('observed_count', 0)}`；候选：`{snapshot.get('candidate_count', 0)}`；独立检验：`{snapshot.get('test_count', 0)}`",
        f"- 来源 SHA-256：`{audit.get('source_canonical_sha256', '—')}`",
        f"- 数据切分 SHA-256：`{audit.get('split_sha256', '—')}`",
        f"- 独立检验 SHA-256：`{audit.get('test_sha256', '—')}`",
        "",
        "## 已揭示历史（仅公开记录）",
        "",
    ]
    if package["revealed_history_only"]:
        lines += ["| 轮次 | 候选 | 预测 | 历史实测 | 绝对误差 | 策略 |", "|---:|---|---:|---:|---:|---|"]
        for item in package["revealed_history_only"]:
            lines.append(
                "| {round} | `{row}` | {prediction} | {target} | {error} | `{strategy}` |".format(
                    round=item.get("round", "—"),
                    row=item.get("row_id", "—"),
                    prediction=_number(item.get("prediction")) if item.get("prediction") is not None else "—",
                    target=_number(item.get("revealed_target")) if item.get("revealed_target") is not None else "—",
                    error=_number(item.get("absolute_error")) if item.get("absolute_error") is not None else "—",
                    strategy=item.get("strategy", "—"),
                )
            )
    else:
        lines.append("暂无已揭示历史记录。")
    lines += [
        "",
        "## 确定性答辩摘要",
        "",
        f"- 已揭示记录数：`{defense['revealed_count']}`",
        f"- 平均绝对误差（MAE）：{_number(defense['mae']) if defense['mae'] is not None else '证据不足'}",
        f"- 最大绝对误差：{_number(defense['max_absolute_error']) if defense['max_absolute_error'] is not None else '证据不足'}",
        f"- 状态：`{defense['evidence_status']}`",
        f"- {defense['summary']}",
        "",
        "## 科学边界",
        "",
    ]
    lines += [f"- {item}" for item in package["limitations"]]
    lines += [
        "",
        "## 公开审计摘要",
        "",
        f"- 审计状态：`{audit.get('status', '—')}`",
        f"- 事件数：`{audit.get('event_count', '—')}`",
        f"- 包 schema：`{package['schema_version']}`",
        "",
        "> 本文件只包含已公开的项目事实、已揭示历史和确定性统计；不包含 pending target、test 标签、原始 CSV、路径、环境变量或 API Key。",
    ]
    return "\n".join(lines) + "\n"


def build_evidence_package(view: dict) -> dict:
    """Return a strict package or raise; never writes files."""
    if not isinstance(view, dict):
        raise EvidencePackageError("view is not an object")
    snapshot = view.get("snapshot")
    audit = view.get("audit")
    history = view.get("history")
    if not isinstance(snapshot, dict) or not isinstance(audit, dict):
        raise EvidencePackageError("missing snapshot/audit")
    if not isinstance(history, list):
        raise EvidencePackageError("history is not a list")
    # The caller's existing audit remains authoritative; these are fail-closed
    # consistency checks, not a replacement audit.
    if audit.get("test_unchanged") is not True or audit.get("models_present") is not True:
        raise EvidencePackageError("audit flags failed")
    if audit.get("status") != snapshot.get("status"):
        raise EvidencePackageError("audit/snapshot status mismatch")
    if snapshot.get("historical_replay") is not True:
        raise EvidencePackageError("project is not a historical replay")
    if not isinstance(snapshot.get("project_id"), str):
        raise EvidencePackageError("missing project id")
    # Do not inspect or serialize pending. Hidden target/test/path values must
    # never become package input, even if an upstream object accidentally has them.
    public_history = _public_history(history)
    package = {
        "schema_version": SCHEMA_VERSION,
        "project_id": snapshot["project_id"],
        "dataset_public_metadata": _public_dataset(view, snapshot),
        "snapshot_public": _public_snapshot(snapshot),
        "audit_public": _public_audit(audit),
        "revealed_history_only": public_history,
        "defense_brief": _defense_brief(public_history),
        "limitations": list(LIMITATIONS),
    }
    package["markdown"] = _markdown(package)
    digest = _hash(package)
    package[PAYLOAD_HASH_FIELD] = digest
    # Keep key order deterministic in the returned JSON object.
    return {
        "schema_version": package["schema_version"],
        "project_id": package["project_id"],
        "dataset_public_metadata": package["dataset_public_metadata"],
        "snapshot_public": package["snapshot_public"],
        "audit_public": package["audit_public"],
        "revealed_history_only": package["revealed_history_only"],
        "defense_brief": package["defense_brief"],
        "limitations": package["limitations"],
        "payload_sha256": package["payload_sha256"],
        "markdown": package["markdown"],
    }


def payload_without_hash(package: dict) -> dict:
    return {key: value for key, value in package.items() if key != PAYLOAD_HASH_FIELD}


def verify_payload_hash(package: dict) -> bool:
    return package.get(PAYLOAD_HASH_FIELD) == _hash(payload_without_hash(package))


def tree_sha256(root: str | Path) -> str:
    root = Path(root)
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            entries.append((path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
    return _hash(entries)
