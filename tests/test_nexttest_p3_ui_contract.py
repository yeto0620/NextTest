"""Static P3 UI contract checks; behavioral browser checks live in the report."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_data_dock_steps_and_gate_language():
    dock = read("frontend/src/workbench/DataDock.jsx")
    for fragment in ("D1", "D2", "D3", "D4", "BLOCKED", "WARNING", "PASSED", "unit_not_verified", "unit not supplied", "文件只在本机处理"):
        assert fragment in dock
    assert "自动填补" not in dock or "不做自动" in dock
    assert "自动编码" not in dock or "不做自动" in dock
    assert "自动换算" not in dock or "不做自动" in dock


def test_dynamic_dataset_context_replaces_concrete_hardcodes():
    app = read("frontend/src/App.jsx")
    assert "DatasetMetaProvider" in app and "CUSTOM_DATASET_KEY" in app
    for path in ("frontend/src/workbench/ObservationPlate.jsx", "frontend/src/workbench/PossibilityAtlas.jsx", "frontend/src/workbench/SelectionDetail.jsx", "frontend/src/workbench/ExperimentBench.jsx", "frontend/src/workbench/EvidencePrism.jsx", "frontend/src/workbench/ReflectionCard.jsx", "frontend/src/workbench/ScienceScenes.jsx", "frontend/src/workbench/ResearchLedger.jsx", "frontend/src/Landscape.jsx"):
        assert "useDataset" in read(path), path


def test_dataset_passport_is_read_only_copy():
    passport = read("frontend/src/workbench/DatasetPassport.jsx")
    assert "只读样本护照" in passport
    assert "冻结后不可原地修改" in passport
    assert "unit_not_verified" in passport
    assert "onChange" not in passport
