"""Read-only project index and pairwise comparability checks.

The library exposes only audited, public summaries. It never ranks projects,
computes win rates or p-values, calls a model, or writes project files.
"""

from __future__ import annotations

import re
from pathlib import Path

LIBRARY_SCHEMA = "nexttest_project_library_v1"
CARD_SCHEMA = "nexttest_project_card_v1"
COMPARABILITY_SCHEMA = "nexttest_project_comparability_v1"
MAX_ITEMS = 100
PROJECT_ID = re.compile(r"^(p2|p3)_[0-9a-f]{32}$")

COMPARABILITY_VALUES = (
    "comparable_same_source_and_split",
    "same_dataset_but_different_split",
    "different_dataset",
    "audit_failed",
)

DESCRIPTIVE_DISCLAIMER = (
    "描述性比较，不构成策略优越、显著性、因果、成本节省、工业有效性或泛化结论。"
)

SHORT_FINGERPRINT_LENGTH = 12
SUMMARY_KEYS = (
    "project_id", "dataset_id", "dataset_display_name", "dataset_short_id",
    "status", "goal", "strategy", "budget", "revealed_count", "observed_count",
    "candidate_count", "historical_replay", "source_sha256_short",
    "split_sha256_short", "test_sha256_short", "model_sha256_short",
    "audit_status", "event_chain_sha256_short",
)
COMPARE_SIDE_KEYS = (
    "project_id", "dataset_id", "dataset_display_name", "dataset_short_id",
    "status", "goal", "strategy", "budget", "revealed_count", "observed_count",
    "candidate_count", "historical_replay", "source_sha256_short",
    "split_sha256_short", "test_sha256_short", "model_sha256_short",
    "event_chain_sha256_short", "audit_status", "mae", "max_error",
)
CARD_KEYS = (
    "schema_version", "project_id", "summary", "dataset_public_metadata",
    "snapshot_public", "audit_public", "defense_brief", "limitations",
    "package_payload_sha256",
)
COMPARE_KEYS = (
    "schema_version", "left", "right", "comparability", "shared_facts",
    "differences", "limitations",
)


class ProjectLibraryError(RuntimeError):
    code = "PROJECT_LIBRARY_INVALID"


def short_sha(value) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value[:SHORT_FINGERPRINT_LENGTH]


def discover_project_ids(p2_root: str | Path | None = None, p3_root: str | Path | None = None) -> list[str]:
    """Return project IDs from the existing read-only project roots."""
    if p2_root is None or p3_root is None:
        from . import experiment, p3_data
        p2_root = experiment.PROJECT_ROOT if p2_root is None else p2_root
        p3_root = p3_data.PROJECT_ROOT if p3_root is None else p3_root
    ids = []
    for root, pattern in ((Path(p2_root), re.compile(r"^p2_[0-9a-f]{32}$")), (Path(p3_root), re.compile(r"^p3_[0-9a-f]{32}$"))):
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if path.is_dir() and pattern.fullmatch(path.name):
                ids.append(path.name)
    return sorted(set(ids))


def _public_dataset(package: dict) -> dict:
    dataset = package.get("dataset_public_metadata")
    return dataset if isinstance(dataset, dict) else {}


def _public_snapshot(package: dict) -> dict:
    snapshot = package.get("snapshot_public")
    return snapshot if isinstance(snapshot, dict) else {}


def _public_audit(package: dict) -> dict:
    audit = package.get("audit_public")
    return audit if isinstance(audit, dict) else {}


def _summary_from_package(package: dict) -> dict:
    dataset = _public_dataset(package)
    snapshot = _public_snapshot(package)
    audit = _public_audit(package)
    return {
        "project_id": package.get("project_id"),
        "dataset_id": dataset.get("dataset_id"),
        "dataset_display_name": dataset.get("display_name"),
        "dataset_short_id": dataset.get("short_id"),
        "status": snapshot.get("status"),
        "goal": snapshot.get("goal"),
        "strategy": snapshot.get("strategy"),
        "budget": snapshot.get("budget"),
        "revealed_count": snapshot.get("revealed_count"),
        "observed_count": snapshot.get("observed_count"),
        "candidate_count": snapshot.get("candidate_count"),
        "historical_replay": snapshot.get("historical_replay"),
        "source_sha256_short": short_sha(snapshot.get("source_canonical_sha256")),
        "split_sha256_short": short_sha(snapshot.get("split_sha256")),
        "test_sha256_short": short_sha(snapshot.get("test_sha256")),
        "model_sha256_short": short_sha(snapshot.get("current_model_sha")),
        "audit_status": "passed" if package.get("schema_version") else "unknown",
        "event_chain_sha256_short": short_sha(audit.get("event_chain_sha256")),
    }


def library_item(package: dict) -> dict:
    """Strict library summary derived from a validated P5-B package."""
    summary = _summary_from_package(package)
    return {key: summary[key] for key in SUMMARY_KEYS}


def library_response(packages: list[dict]) -> dict:
    items = sorted((library_item(package) for package in packages), key=lambda item: str(item["project_id"]))
    items = items[:MAX_ITEMS]
    return {
        "schema_version": LIBRARY_SCHEMA,
        "count": len(items),
        "items": items,
    }


def card_from_package(package: dict) -> dict:
    """Card is a projection of the already-public P5-B package."""
    card = {
        "schema_version": CARD_SCHEMA,
        "project_id": package.get("project_id"),
        "summary": library_item(package),
        "dataset_public_metadata": package.get("dataset_public_metadata"),
        "snapshot_public": package.get("snapshot_public"),
        "audit_public": package.get("audit_public"),
        "defense_brief": package.get("defense_brief"),
        "limitations": package.get("limitations"),
        "package_payload_sha256": package.get("payload_sha256"),
    }
    return {key: card[key] for key in CARD_KEYS}


def _compare_side(package: dict) -> dict:
    summary = _summary_from_package(package)
    defense = package.get("defense_brief") if isinstance(package.get("defense_brief"), dict) else {}
    side = {
        **summary,
        "event_chain_sha256_short": summary["event_chain_sha256_short"],
        "mae": defense.get("mae"),
        "max_error": defense.get("max_absolute_error"),
    }
    return {key: side[key] for key in COMPARE_SIDE_KEYS}


def compare_packages(left_package: dict, right_package: dict) -> dict:
    """Compare two already-audited public packages; never ranks or aggregates."""
    if not isinstance(left_package, dict) or not isinstance(right_package, dict):
        raise ProjectLibraryError("both audited packages are required")
    left = _compare_side(left_package)
    right = _compare_side(right_package)
    left_snapshot = _public_snapshot(left_package)
    right_snapshot = _public_snapshot(right_package)
    left_dataset = _public_dataset(left_package)
    right_dataset = _public_dataset(right_package)
    same_dataset = left_dataset.get("dataset_id") == right_dataset.get("dataset_id")
    same_source = (
        left_snapshot.get("source_canonical_sha256") is not None
        and left_snapshot.get("source_canonical_sha256") == right_snapshot.get("source_canonical_sha256")
    )
    same_split = (
        left_snapshot.get("split_sha256") is not None
        and left_snapshot.get("split_sha256") == right_snapshot.get("split_sha256")
    )
    same_source_and_split = bool(same_source and same_split)
    if same_source_and_split:
        comparability = "comparable_same_source_and_split"
        note = "两侧 source SHA 与 split SHA 均一致；仍只做描述性历史回放比较，不构成策略排名。"
    elif same_dataset:
        comparability = "same_dataset_but_different_split"
        note = "两侧使用同一数据集，但 split SHA 不同，不能直接横向比较。"
    else:
        comparability = "different_dataset"
        note = "两侧数据集不同，不能直接横向比较。"
    shared_facts = {
        "same_dataset": bool(same_dataset),
        "same_source_sha256": bool(same_source),
        "same_split_sha256": bool(same_split),
        "same_source_and_split": bool(same_source_and_split),
        "same_goal": left["goal"] == right["goal"],
        "same_strategy": left["strategy"] == right["strategy"],
        "same_budget": left["budget"] == right["budget"],
        "disclaimer": DESCRIPTIVE_DISCLAIMER,
        "comparison_note": note,
    }
    fields = (
        "dataset_id", "dataset_display_name", "dataset_short_id", "status", "goal",
        "strategy", "budget", "revealed_count", "observed_count", "candidate_count",
        "historical_replay", "source_sha256_short", "split_sha256_short",
        "test_sha256_short", "model_sha256_short", "event_chain_sha256_short",
        "audit_status", "mae", "max_error",
    )
    differences = {
        field: {"left": left[field], "right": right[field]}
        for field in fields
        if left[field] != right[field]
    }
    limitations = [DESCRIPTIVE_DISCLAIMER]
    for item in left_package.get("limitations", []) + right_package.get("limitations", []):
        if isinstance(item, str) and item not in limitations:
            limitations.append(item)
    # A failed audit is never represented as a package comparison; callers get
    # a fail-closed HTTP error. The sentinel remains in the documented enum.
    return {
        "schema_version": COMPARABILITY_SCHEMA,
        "left": left,
        "right": right,
        "comparability": comparability,
        "shared_facts": shared_facts,
        "differences": differences,
        "limitations": limitations,
    }


def audit_failed_error() -> dict:
    return {
        "code": "PROJECT_COMPARISON_AUDIT_FAILED",
        "comparability": "audit_failed",
        "message": "至少一个项目未通过只读审计；不返回部分比较。",
    }
