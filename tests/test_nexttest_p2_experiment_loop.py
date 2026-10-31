import json
from pathlib import Path

import pandas as pd
import pytest

from nexttest import experiment as ex
from nexttest import strategy as st
from nexttest.data import CandidatePoolView, PreparedExperiment, HiddenLabelVault
from nexttest.models import train_regression


def _base():
    base, split, manifest = ex.load_frozen_base()
    predictor = train_regression(base, seed=20261026, evaluate_test=False)
    return base, split, manifest, predictor


def _create(tmp_path, strategy="random", budget=2):
    root = tmp_path / f"project_{strategy}_{budget}"
    return ex.create_experiment(strategy=strategy, budget=budget, seed=20261026, store_root=root, project_id="p2_test"), root


def test_selector_only_accepts_candidate_view_and_cannot_get_vault():
    base, _, _, predictor = _base()
    with pytest.raises(TypeError):
        st.recommend("random", base, predictor, goal=st.Goal(), seed=1, round_index=0)
    with pytest.raises(TypeError):
        st.recommend("random", base.vault, predictor, goal=st.Goal(), seed=1, round_index=0)
    with pytest.raises(TypeError):
        st.selector_fixture(base)
    assert st.selector_fixture(base.candidates) == len(base.candidates.row_ids)
    assert not hasattr(base.candidates, "vault")
    assert "CompressiveStrength" not in base.candidates.frame.columns


def test_three_strategies_return_unrevealed_candidates_and_reproducible():
    base, _, _, predictor = _base()
    goal = st.Goal("maximize", 40.0)
    random_a = st.recommend("random", base.candidates, predictor, goal=goal, seed=7, round_index=0)
    random_b = st.recommend("random", base.candidates, predictor, goal=goal, seed=7, round_index=0)
    greedy = st.recommend("greedy_prediction", base.candidates, predictor, goal=goal, seed=7, round_index=0)
    disagreement = st.recommend("max_disagreement", base.candidates, predictor, goal=goal, seed=7, round_index=0)
    assert random_a.row_id == random_b.row_id
    for rec in (random_a, greedy, disagreement):
        assert rec.row_id in base.candidates.row_ids
        assert "target" not in rec.controls
        assert "CompressiveStrength" not in rec.controls
    assert disagreement.disagreement is not None
    assert "模型分歧" in disagreement.reason


def test_recommendation_view_has_no_target_and_no_reveal_before_confirm(tmp_path):
    _, root = _create(tmp_path)
    snap = ex.get_experiment("p2_test", store_root=root)
    assert snap.status == "ready"
    rec = ex.recommend_next("p2_test", store_root=root)
    payload = rec.to_dict()
    assert "target" not in payload and "target_hidden" in payload
    assert payload["historical_replay"] is True
    state = ex.get_experiment("p2_test", store_root=root)
    assert state.status == "awaiting_user_confirmation"
    assert state.candidate_count == snap.candidate_count
    assert state.revealed_count == 0


def test_confirm_releases_once_and_updates_model_without_touching_test(tmp_path):
    _, root = _create(tmp_path)
    before = ex.get_experiment("p2_test", store_root=root)
    rec = ex.recommend_next("p2_test", store_root=root)
    feedback = ex.confirm_and_reveal("p2_test", rec.recommendation_id, store_root=root)
    assert feedback.revealed_target == pytest.approx(feedback.revealed_target)
    assert feedback.model_sha_before != feedback.model_sha_after
    after = ex.get_experiment("p2_test", store_root=root)
    assert after.observed_count == before.observed_count + 1
    assert after.revealed_count == 1
    assert after.test_count == before.test_count
    assert after.test_sha256 == before.test_sha256
    with pytest.raises(ex.DataGateError):
        ex.confirm_and_reveal("p2_test", rec.recommendation_id, store_root=root)


def test_restart_replays_same_state_and_audit_is_read_only(tmp_path):
    _, root = _create(tmp_path)
    rec = ex.recommend_next("p2_test", store_root=root)
    ex.confirm_and_reveal("p2_test", rec.recommendation_id, store_root=root)
    a = ex.get_experiment("p2_test", store_root=root).to_dict()
    b = ex.get_experiment("p2_test", store_root=root).to_dict()
    assert a == b
    audit1 = ex.inspect_experiment("p2_test", store_root=root)
    tree1 = audit1.tree_sha256
    audit2 = ex.inspect_experiment("p2_test", store_root=root)
    assert audit2.tree_sha256 == tree1
    assert audit2.event_count == audit1.event_count
    assert audit2.test_unchanged is True


def test_budget_one_ends_and_blocks_further_recommendation(tmp_path):
    snap, root = _create(tmp_path, budget=1)
    rec = ex.recommend_next("p2_test", store_root=root)
    feedback = ex.confirm_and_reveal("p2_test", rec.recommendation_id, store_root=root)
    assert feedback.status == "budget_exhausted"
    with pytest.raises(ex.DataGateError):
        ex.recommend_next("p2_test", store_root=root)


def test_invalid_recommendation_id_fails_closed(tmp_path):
    _, root = _create(tmp_path)
    ex.recommend_next("p2_test", store_root=root)
    with pytest.raises(ex.DataGateError):
        ex.confirm_and_reveal("p2_test", "rec-999999", store_root=root)


def test_release_failure_leaves_no_fabricated_label(tmp_path, monkeypatch):
    _, root = _create(tmp_path)
    rec = ex.recommend_next("p2_test", store_root=root)
    def boom(self, row_id):
        raise RuntimeError("simulated reveal crash")
    monkeypatch.setattr(HiddenLabelVault, "reveal", boom)
    with pytest.raises(ex.DataGateError):
        ex.confirm_and_reveal("p2_test", rec.recommendation_id, store_root=root)
    state = ex.get_experiment("p2_test", store_root=root)
    assert state.status == "release_uncertain"
    assert state.revealed_count == 0
    with pytest.raises(ex.DataGateError):
        ex.confirm_and_reveal("p2_test", rec.recommendation_id, store_root=root)


def test_empty_candidate_view_rejected():
    frame = pd.DataFrame({"_row_id": [], "Cement": [], "BlastFurnaceSlag": [], "FlyAsh": [], "Water": [], "Superplasticizer": [], "CoarseAggregate": [], "FineAggregate": [], "Age": []})
    with pytest.raises(ValueError):
        st.recommend("random", CandidatePoolView(frame=frame, feature_columns=("Cement",), row_ids=()), None, goal=st.Goal(), seed=1, round_index=0)
