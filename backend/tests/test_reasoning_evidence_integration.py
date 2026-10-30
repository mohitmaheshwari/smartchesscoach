"""Opt-in live Stockfish check of the generic fifteen-ply evidence runner."""
import json
import os
from pathlib import Path

import pytest

from services.reasoning.evidence import build_position_evidence, model_packet
from test_reasoning_boundaries import config
from test_reasoning_evidence import FEN

ENGINE = os.environ.get('CHESSGURU_TEST_STOCKFISH')
pytestmark = pytest.mark.skipif(not ENGINE, reason='explicit local engine path required')


def test_live_g4_packet_preserves_sources_horizon_identities_and_material(tmp_path):
    result = build_position_evidence(FEN, 'g4', config=config(engine_path=ENGINE, nodes=8000000,
        stability_nodes=8000000, max_total_nodes=40000000, max_queries=5, rank_width=3, hash_mb=64), depth=24)
    (tmp_path / 'evidence.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    assert result['status'] == 'complete'
    assert result['input']['played_uci'] == 'g5g4'
    assert result['runtime']['query_count'] <= 5
    assert result['runtime']['requested_engine_nodes'] <= 40000000
    states = {s['id']: s for s in result['states']}
    assert all(1 <= b['available_plies'] <= 15 for b in result['branches'])
    assert {b['role'] for b in result['branches']} == {'played', 'alternative'}
    for b in result['branches']:
        assert len(b['state_ids']) == b['available_plies'] + 1
        assert b['material_at_end'] == states[b['end_state_id']]['material']
        if b['role'] == 'played':
            after = states[b['state_ids'][1]]
            assert 'f4' not in after['pieces']['black:pawn:g5']['controlled_squares']
    source_ids = {r['id'] for r in result['searches']}
    assert all(source['search_id'] in source_ids for b in result['branches'] for source in b['sources'])
    view = model_packet(result)
    (tmp_path / 'model_input.json').write_text(json.dumps(view, indent=2), encoding='utf-8')
    assert view['schema_version'].endswith('model.v1')
