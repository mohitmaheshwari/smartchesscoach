"""Audit the actual fresh CLI search receipts; no substitute engine call."""
import json
import os
from pathlib import Path

import chess
import pytest

ROOT = os.environ.get('CHESSGURU_TEST_REPLY_DEPENDENCY_DIR')
pytestmark = pytest.mark.skipif(not ROOT, reason='explicit directory of real CLI artifacts required')


def test_real_searches_bind_the_exact_exclusion_and_preserve_actor_pov():
    artifacts = []
    for path in Path(ROOT).rglob('*.json'):
        r = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(r, dict) and r.get('schema_version') == 'reasoning.reply_dependency.v1':
            artifacts.append(r)
    assert artifacts
    for r in artifacts:
        probe = r['probe']
        board = chess.Board(probe['fen'])
        assert probe['actor'] == ('white' if board.turn else 'black')
        records = {s['id']: s for s in r['searches']}
        for m in probe['measurements']:
            a, b = records[m['baseline_search_id']], records[m['without_search_id']]
            assert a['fen'] == b['fen'] == board.fen()
            assert not a['root_moves']
            assert set(b['root_moves']) == {move.uci() for move in board.legal_moves} - {probe['excluded_uci']}
            for record in (a, b):
                walker = board.copy()
                for raw in record['lines'][0]['moves_uci']:
                    move = chess.Move.from_uci(raw)
                    assert move in walker.legal_moves
                    walker.push(move)
            assert a['lines'][0]['depth'] >= m['requested_depth']
            assert b['lines'][0]['depth'] >= m['requested_depth']
            if m['drop_cp'] is not None:
                sign = 1 if a['lines'][0]['score']['pov'] == probe['actor'] else -1
                assert m['drop_cp'] == sign * (a['lines'][0]['score']['value'] - b['lines'][0]['score']['value'])
        assert r['coaching'] is None
        assert probe['mechanism_established'] is False


def test_real_guarded_negative_control_does_not_promote_search_noise():
    path = Path(ROOT) / 'negative_control_guarded/g4_Rf4_control.json'
    r = json.loads(path.read_text(encoding='utf-8'))
    assert r['probe']['status'] == 'measured'
    assert r['probe']['signal'] == 'excluded_move_not_baseline_choice'
    assert all(m['excluded_was_baseline_choice'] is False for m in r['probe']['measurements'])
