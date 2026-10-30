"""Opt-in end-to-end checks of the combined offline core, using a local engine."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from services.reasoning import explain_fen
from test_reasoning_boundaries import NA4, QF8, config
from test_reasoning_combined import FEN
from test_reasoning_review_regressions import QUIET
from test_reasoning_relevance import ROOK
from test_reasoning_piece_pressure import FEN as PRESSURE_FEN


ENGINE = os.environ.get('CHESSGURU_TEST_STOCKFISH')
pytestmark = pytest.mark.skipif(not ENGINE, reason='explicit local Stockfish path required')


@pytest.fixture(scope='module')
def outputs(tmp_path_factory):
    assert Path(ENGINE).is_file()
    destination = tmp_path_factory.mktemp('combined_engine')
    rows = {}
    cases = [('nxe5_baseline_same_cap', FEN, 'Nxe5', False, 6000000),
             ('nxe5', FEN, 'Nxe5', True, 6000000),
             ('na4', NA4, 'Na4', True, 2000000),
             ('qf8', QF8, 'Qf8', True, 2000000),
             ('nf3', QUIET, 'Nf3', True, 2000000),
             ('qa2', '7k/6pp/8/8/3b4/8/8/QK2R3 w - - 0 1', 'Qa2', True, 2000000),
             ('rook_contrast', ROOK, 'Re1', True, 2000000),
             ('qc2', 'rnbq1rk1/pppp1p2/4p2p/6p1/2PPn3/2P3B1/P4PPP/R2QKBNR w KQ - 0 9', 'Qc2', True, 2000000),
             ('nxe5_repeat', FEN, 'Nxe5', True, 6000000),
             ('c4', PRESSURE_FEN, 'c4', True, 6000000),
             ('c4_repeat', PRESSURE_FEN, 'c4', True, 6000000),
             ('c4_limited', PRESSURE_FEN, 'c4', True, 2000000)]
    for name, fen, played, combined, budget in cases:
        settings = config(engine_path=ENGINE, nodes=30000, stability_nodes=120000,
                          max_queries=32, max_total_nodes=budget, rank_width=4, hash_mb=64)
        options = {'positional_features': True, 'feature_plies': 4,
                   'verification_nodes': 2000000} if combined else {}
        result = explain_fen(fen, played, config=settings, **options)
        (destination / (name + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({'case': name, 'status': result['status'], 'text': result['coaching']['text'],
                          'runtime': result['runtime'], 'artifact': str(destination / (name + '.json'))}), flush=True)
        rows[name] = result
    return rows


def test_combination_adds_a_verified_mechanism_beyond_the_same_cap_baseline(outputs):
    assert outputs['nxe5_baseline_same_cap']['selected_teaching_point'] is None
    result = outputs['nxe5']
    assert result['selected_teaching_point']['objective']['kind'] == 'comparative_recapture'
    assert result['status'] == 'supported_mechanism'
    assert 'placing the knight in the centre on e5' in result['coaching']['text']
    assert 'protected by the pawn on d4' in result['coaching']['text']
    assert 'g4 instead attacks the defending knight on f3 first' in result['coaching']['text']
    assert 'White has a pawn on e5 instead' in result['coaching']['text']


def test_original_forcing_and_material_lessons_survive_with_the_provider_enabled(outputs):
    assert outputs['na4']['selected_teaching_point']['objective']['kind'] == 'comparative_sequence'
    assert outputs['qf8']['selected_teaching_point']['objective']['kind'] == 'comparative_threat'
    assert 'Qf8 adds no cover on f5' in outputs['qf8']['coaching']['text']
    assert 'avoids this immediate mating line' not in outputs['qf8']['coaching']['text']
    assert outputs['rook_contrast']['coaching']['text'].startswith("Rxc2 takes Black's rook on c2")


def test_original_subject_and_mate_distance_fixes_survive(outputs):
    assert outputs['nf3']['selected_teaching_point']['root_uci'] == 'g1f3'
    assert 'Black plays e4' not in outputs['nf3']['coaching']['text']
    assert outputs['qa2']['context']['mate_comparison']['best_in'] == 1
    assert outputs['qa2']['context']['comparison'] == 'inferior'


def test_all_claims_have_receipts_and_searches_stay_inside_their_explicit_caps(outputs):
    for name, result in outputs.items():
        assert not result['invalid_propositions']
        assert all(row['admitted'] for row in result['sentence_admission'])
        budget = 6000000 if name.startswith('nxe5') or name in ('c4', 'c4_repeat') else 2000000
        assert result['runtime']['requested_engine_nodes'] <= budget
        assert result['runtime']['query_count'] <= 32
        if name != 'nxe5_baseline_same_cap':
            assert result['feature_evidence']['authority'] == 'candidate_evidence_only'
            assert result['reproducibility']['positional_provider']['revision'] == 'b7ea991854f926250036105f152894881e7820a2'


def test_combined_output_is_repeatable_outside_runtime(outputs):
    def stable(value):
        if isinstance(value, dict):
            return {key: stable(item) for key, item in value.items()
                    if key != 'runtime' and not key.endswith('_ms')}
        if isinstance(value, list):
            return [stable(item) for item in value]
        return value
    assert stable(deepcopy(outputs['nxe5'])) == stable(deepcopy(outputs['nxe5_repeat']))
    assert stable(deepcopy(outputs['c4'])) == stable(deepcopy(outputs['c4_repeat']))


def test_played_support_loss_precedes_an_unrelated_alternative_feature(outputs):
    result = outputs['c4']
    assert result['status'] == 'supported_mechanism'
    point = result['selected_teaching_point']
    assert point['objective']['kind'] == 'comparative_support_chain'
    assert point['objective']['guard_id'] == 'white:pawn:c3'
    assert point['objective']['defender_id'] == 'white:pawn:d4'
    assert point['objective']['key_id'] == 'white:knight:e5'
    assert point['objective']['capture_ply'] == 4
    assert 'leaves c3 and stops defending d4' in result['coaching']['text']
    assert "White's knight on e5" in result['coaching']['text']
    assert 'c4 c5 cxd5 cxd4' in result['coaching']['text']
    assert "Black's queen on f6" in result['coaching']['text']
    assert 'f3 c5 fxe4 fxe4' not in result['coaching']['text']
    assert 'must move' not in result['coaching']['text']


def test_pressure_budget_exhaustion_does_not_relax_the_depth_gate(outputs):
    result = outputs['c4_limited']
    assert result['selected_teaching_point'] is None
    pressure = [h for h in result['hypotheses']['incomplete']
                if h['objective']['kind'] == 'comparative_support_chain']
    assert len(pressure) == 1
    assert 'opponent_reference_depth_not_reached' in pressure[0]['unresolved']
