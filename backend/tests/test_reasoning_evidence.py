"""Contracts for the user's general 15-ply evidence pipeline, not a motif."""
from copy import deepcopy
from importlib import import_module

import chess
import pytest

from services.reasoning.contracts import SearchRecord, fingerprint
from services.reasoning.timeline import build_timeline
from test_reasoning_boundaries import config

FEN = 'r1b2rk1/pp3n2/2p2q1p/2PpNpp1/3P1P2/3B4/P1Q3PP/R4RK1 b - - 0 18'
PLAYED = ['g5g4', 'a1e1', 'f7e5', 'f4e5', 'f6g6', 'f1f4', 'c8e6', 'g2g3',
          'h6h5', 'e1f1', 'g8g7', 'a2a4', 'f8f7', 'c2f2', 'a8f8']
BEST = ['f7e5', 'f4e5', 'f6f7', 'g2g3', 'f5f4', 'g3f4', 'g5f4', 'g1h1',
        'g8h8', 'f1g1', 'c8f5', 'd3f5', 'f7f5', 'c2f5', 'f8f5']


def api():
    return import_module('services.reasoning.evidence')


def sample(max_plies=15):
    root = chess.Board(FEN)
    searches, specs = [], []
    for role, moves, value in [('played', PLAYED, -45), ('alternative', BEST, -9)]:
        r = SearchRecord(role, 'root', root.fen(), [moves[0]], 200, 1, 'complete_iteration',
            [{'root_uci': moves[0], 'moves_uci': moves,
              'score': {'kind': 'cp', 'value': value, 'pov': 'black'}, 'depth': 20}], requested_depth=20)
        searches.append(r.document())
        specs.append({'role': role, 'origin': 'root', 'search_id': r.id, 'moves_uci': moves})
    return api().packet_from_timelines(root, specs, searches, depth=20, max_plies=max_plies)


def test_initial_scan_has_every_piece_support_threat_and_positional_attributes():
    p = sample()
    initial = next(s for s in p['states'] if s['id'] == p['initial_state_id'])
    assert len(initial['pieces']) == len(chess.Board(FEN).piece_map())
    knight = initial['pieces']['white:knight:e5']
    assert set(knight['defended_by']) == {'white:pawn:d4', 'white:pawn:f4'}
    assert set(knight['attacked_by']) == {'black:queen:f6', 'black:knight:f7'}
    assert any(e['evidence']['kind'] == 'outpost' for e in knight['positional_evidence'])
    assert initial['material']['white']['pawn'] == 6
    assert initial['material']['black']['pawn'] == 7


def test_every_ply_is_scanned_including_unmoved_pieces_and_new_piece_types_on_a_square():
    p = sample()
    branch = next(b for b in p['branches'] if b['role'] == 'played')
    states = {s['id']: s for s in p['states']}
    after = states[branch['state_ids'][1]]
    assert after['pieces']['white:pawn:f4']['attacked_by'] == []
    assert 'f4' not in after['pieces']['black:pawn:g5']['controlled_squares']
    end_exchange = states[branch['state_ids'][4]]
    assert 'white:knight:e5' not in end_exchange['pieces']
    assert end_exchange['pieces']['white:pawn:f4']['square'] == 'e5'
    assert any(e['evidence']['kind'] == 'passed_pawn'
               for e in end_exchange['pieces']['white:pawn:f4']['positional_evidence'])
    assert branch['available_plies'] == 15


def test_model_projection_can_reconstruct_every_saved_state_without_dropping_unchanged_links():
    p = sample()
    view = api().model_packet(p)
    restored = {view['initial']['id']: deepcopy(view['initial'])}
    for delta in view['state_changes']:
        state = deepcopy(restored[delta['parent_id']])
        state.update({k: deepcopy(v) for k, v in delta['fields'].items()})
        for key, changes in delta['piece_changes'].items():
            if changes is None:
                state['pieces'].pop(key)
            else:
                state['pieces'].setdefault(key, {}).update(deepcopy(changes))
        for key, value in delta['feature_changes'].items():
            state['features'][key] = deepcopy(value)
        restored[state['id']] = state
    assert restored == {s['id']: s for s in p['states']}
    assert any('f4' in changes.get('removed_controls', [])
               for delta in view['state_changes'] for changes in delta['relationship_changes'].values())


def test_duplicate_variations_share_states_and_sources_without_mixing_branches():
    p = sample()
    assert p['branches'][0]['state_ids'][0] == p['branches'][1]['state_ids'][0]
    assert len({s['id'] for s in p['states']}) == len(p['states'])
    assert p['branches'][0]['state_ids'][1] != p['branches'][1]['state_ids'][1]


def test_short_pv_is_not_padded_or_called_forced():
    p = sample(max_plies=3)
    assert all(b['available_plies'] == 3 for b in p['branches'])
    assert all(b['stop_reason'] == 'projection_horizon' for b in p['branches'])
    root = chess.Board(FEN)
    rec = SearchRecord('short', 'short', root.fen(), [PLAYED[0]], 200, 1,
        'complete_iteration', [{'moves_uci': PLAYED[:1], 'score': {'kind': 'cp', 'value': 0, 'pov': 'black'}, 'depth': 20}], requested_depth=20)
    short = api().packet_from_timelines(root, [{'role': 'played', 'origin': 'root',
        'search_id': 'short', 'moves_uci': PLAYED[:1]}], [rec.document()], depth=20)
    assert short['branches'][0]['available_plies'] == 1
    assert short['branches'][0]['stop_reason'] == 'pv_end'


@pytest.mark.parametrize('limit', [0, 16, True])
def test_horizon_is_a_positive_limit_of_at_most_fifteen(limit):
    with pytest.raises(ValueError):
        sample(max_plies=limit)


@pytest.mark.parametrize('fen,moves,expected', [
    (chess.STARTING_FEN, ['e1g1'], 'illegal'),
    ('4k3/8/8/8/8/8/P7/4K3 w - - 0 1', ['a2a8'], 'illegal'),
])
def test_illegal_lines_are_rejected(fen, moves, expected):
    root = chess.Board(fen)
    r = SearchRecord('bad', 'bad', fen, [], 100, 1, 'complete_iteration',
                    [{'moves_uci': moves, 'score': {'kind': 'cp', 'value': 0, 'pov': 'white'}, 'depth': 20}])
    with pytest.raises(ValueError):
        api().packet_from_timelines(root, [{'role': 'played', 'origin': 'root',
            'search_id': 'bad', 'moves_uci': moves}], [r.document()], depth=20)


@pytest.mark.parametrize('fen,moves,piece_id,square,piece', [
    ('4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1', ['e1g1'], 'white:rook:h1', 'f1', 'rook'),
    ('4k3/P7/8/8/8/8/8/4K3 w - - 0 1', ['a7a8q'], 'white:pawn:a7', 'a8', 'queen'),
    ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', ['e5d6'], 'white:pawn:e5', 'd6', 'pawn'),
])
def test_special_moves_keep_the_physical_piece_identity(fen, moves, piece_id, square, piece):
    t = build_timeline(chess.Board(fen), moves, 'special', 15)
    s = api().scan_node(t['nodes'][1], {})
    assert s['pieces'][piece_id]['square'] == square
    assert s['pieces'][piece_id]['piece'] == piece
    if moves == ['e5d6']:
        assert 'black:pawn:d5' not in s['pieces']


class FakeSession:
    def __init__(self, settings, pov, history_id):
        self.config, self.records = settings, []
        self.requested_nodes, self.executed_queries = 0, 0
    def query(self, board, purpose, *, roots=(), width=1, nodes=None, depth=None):
        allocation = nodes or self.config.nodes
        limited = self.executed_queries >= self.config.max_queries or self.requested_nodes + allocation > self.config.max_total_nodes
        start = chess.Board(FEN)
        if board.fen() == start.fen():
            moves = PLAYED if roots and roots[0].uci() == PLAYED[0] else BEST
            lines = [moves] if roots else [BEST, PLAYED]
        else:
            p = start.copy(); p.push_uci(PLAYED[0])
            lines = [PLAYED[1:] if board.fen() == p.fen() else BEST[1:]]
        r = SearchRecord(fingerprint([purpose, board.fen(), [m.uci() for m in roots]]), purpose,
            board.fen(), [m.uci() for m in roots], allocation, width,
            'unavailable' if limited else 'complete_iteration', requested_depth=depth)
        if not limited:
            r.lines = [{'root_uci': l[0], 'moves_uci': l,
                'score': {'kind': 'cp', 'value': -45 if l[0] in (PLAYED[0], PLAYED[1]) else -9, 'pov': 'black'},
                'depth': depth} for l in lines]
            self.executed_queries += 1; self.requested_nodes += allocation
        else:
            r.stop_reason = 'query_or_node_budget_exhausted'
        self.records.append(r)
        return r
    def document(self):
        return {'test_session': True}


def test_full_collector_infers_and_checks_the_fen_pair_and_runs_both_sides():
    after = chess.Board(FEN); after.push_uci(PLAYED[0])
    p = api().build_position_evidence(FEN, fen_after=after.fen(), config=config(), depth=20,
                                      session_factory=FakeSession)
    assert p['input']['played_uci'] == PLAYED[0]
    assert p['status'] == 'complete'
    assert {b['role'] for b in p['branches']} == {'played', 'alternative'}
    assert any(not r['root_moves'] and r['fen'] == after.fen() for r in p['searches'])


def test_wrong_fen_after_is_rejected_before_search():
    with pytest.raises(ValueError):
        api().build_position_evidence(FEN, 'g4', fen_after=FEN, config=config(), depth=20,
                                      session_factory=FakeSession)


def test_budget_failure_is_partial_evidence_and_never_invents_an_alternative():
    p = api().build_position_evidence(FEN, 'g4', config=config(max_queries=1), depth=20,
                                      session_factory=FakeSession)
    assert p['status'] == 'partial'
    assert p['search_quality']['incomplete_search_ids']
    assert all(b['role'] == 'played' for b in p['branches'])


def test_reply_source_is_unrestricted_and_at_the_actual_post_move_position():
    root = chess.Board(FEN); after = root.copy(); after.push_uci(PLAYED[0])
    r = SearchRecord('reply', 'reply', after.fen(), [PLAYED[1]], 100, 1, 'complete_iteration',
        [{'moves_uci': PLAYED[1:], 'score': {'kind': 'cp', 'value': -40, 'pov': 'black'}, 'depth': 20}], requested_depth=20)
    with pytest.raises(ValueError):
        api().packet_from_timelines(root, [{'role': 'played', 'origin': 'reply',
            'search_id': 'reply', 'moves_uci': PLAYED}], [r.document()], depth=20)
    r.root_moves = []; r.fen = root.fen()
    with pytest.raises(ValueError):
        api().packet_from_timelines(root, [{'role': 'played', 'origin': 'reply',
            'search_id': 'reply', 'moves_uci': PLAYED}], [r.document()], depth=20)


def test_unreached_requested_depth_is_visible_in_packet():
    root = chess.Board(FEN)
    r = SearchRecord('low', 'low', root.fen(), [PLAYED[0]], 100, 1, 'complete_iteration',
        [{'moves_uci': PLAYED[:2], 'score': {'kind': 'cp', 'value': -40, 'pov': 'black'}, 'depth': 19}], requested_depth=20)
    p = api().packet_from_timelines(root, [{'role': 'played', 'origin': 'root',
        'search_id': 'low', 'moves_uci': PLAYED[:2]}], [r.document()], depth=20)
    assert p['status'] == 'partial' and p['search_quality']['incomplete_search_ids'] == ['low']


def test_terminal_line_stops_at_mate_without_padding():
    root = chess.Board('7k/6pp/8/8/3b4/8/8/QK2R3 w - - 0 1')
    r = SearchRecord('mate', 'mate', root.fen(), ['a1a8'], 100, 1, 'complete_iteration',
        [{'moves_uci': ['a1a8'], 'score': {'kind': 'mate', 'value': 1, 'pov': 'white'}, 'depth': 20}], requested_depth=20)
    p = api().packet_from_timelines(root, [{'role': 'played', 'origin': 'root',
        'search_id': 'mate', 'moves_uci': ['a1a8']}], [r.document()], depth=20)
    assert p['branches'][0]['available_plies'] == 1
    assert p['branches'][0]['stop_reason'] == 'terminal'


def test_model_view_has_no_local_engine_path_or_unscanned_search_tail():
    p = sample(max_plies=3)
    p['settings']['search_config'] = {'engine_path': 'private-machine-path'}
    view = api().model_packet(p)
    import json
    assert 'private-machine-path' not in json.dumps(view)
    for r in view['searches']:
        assert all(len(l['moves_san']) <= 3 for l in r['lines'])
