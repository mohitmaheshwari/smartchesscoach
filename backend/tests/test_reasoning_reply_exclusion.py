"""Reply deletion measures a search dependency; it never certifies a motif."""
from importlib import import_module
from types import SimpleNamespace

import chess
import pytest

from services.reasoning.contracts import SearchRecord
from test_reasoning_boundaries import config


def api():
    return import_module('services.reasoning.counterfactual')


class Session:
    def __init__(self, pov=chess.WHITE, *, depth=20, unavailable=False, reversal=False, mate=False):
        self.pov = pov
        self.config = config()
        self.records = []
        self.achieved = depth
        self.unavailable = unavailable
        self.reversal = reversal
        self.mate = mate

    def query(self, board, purpose, *, roots=(), width=1, nodes=None, depth=None):
        allowed = sorted(roots or board.legal_moves, key=lambda m: m.uci())
        value = (90 if self.reversal else 50) if roots else 80
        if board.turn != self.pov:
            value = -value
        score = {'kind': 'mate' if self.mate else 'cp', 'value': value,
                 'pov': 'white' if self.pov else 'black'}
        r = SearchRecord(str(len(self.records)), purpose, board.fen(), [m.uci() for m in roots],
            nodes or 100, width, 'unavailable' if roots and self.unavailable else 'complete_iteration',
            [] if roots and self.unavailable else [{'root_uci': allowed[0].uci(), 'moves_uci': [allowed[0].uci()],
                'score': score, 'depth': self.achieved}], requested_depth=depth)
        self.records.append(r)
        return r


@pytest.mark.parametrize('turn,pov', [(True, True), (True, False), (False, True), (False, False)])
def test_drop_is_from_the_actor_pov_and_only_one_legal_move_is_removed(turn, pov):
    board = chess.Board()
    if not turn:
        board.push_san('e4')
    session = Session(pov)
    result = api().probe_reply_dependency(board, session, depth=20)
    assert result['status'] == 'measured'
    assert result['scope'] == 'searched_move_dependency_not_a_chess_mechanism'
    assert all(m['drop_cp'] == 30 for m in result['measurements'])
    excluded = result['excluded_uci']
    for r in session.records:
        if r.root_moves:
            assert set(r.root_moves) == {m.uci() for m in board.legal_moves} - {excluded}
    assert result['actor'] == ('white' if turn else 'black')


def test_nominated_move_can_have_no_measured_value_without_being_a_reason():
    session = Session()
    board = chess.Board()
    # The fixture returns an improved score in the restricted search.
    session.reversal = True
    result = api().probe_reply_dependency(board, session, depth=20, exclude_move='e4')
    assert result['excluded_uci'] == 'e2e4'
    assert all(m['drop_cp'] == -10 for m in result['measurements'])
    assert result['signal'] == 'search_reversal'
    assert result['mechanism_established'] is False


@pytest.mark.parametrize('settings', [{'depth': 19}, {'unavailable': True}])
def test_incomplete_search_does_not_supply_a_measured_effect(settings):
    result = api().probe_reply_dependency(chess.Board(), Session(**settings), depth=20)
    assert result['status'] == 'partial'
    assert all(m['drop_cp'] is None for m in result['measurements'])


def test_mates_keep_their_typed_scores_without_synthetic_centipawn_subtraction():
    result = api().probe_reply_dependency(chess.Board(), Session(mate=True), depth=20)
    assert result['status'] == 'measured'
    assert all(m['drop_cp'] is None for m in result['measurements'])
    assert all(m['baseline_score']['kind'] == 'mate' for m in result['measurements'])


def test_only_legal_reply_never_turns_an_empty_restricted_set_into_unrestricted_search():
    board = chess.Board('7k/6Q1/8/8/8/8/8/K7 b - - 0 1')
    assert board.legal_moves.count() == 1
    session = Session()
    result = api().probe_reply_dependency(board, session, depth=20)
    assert result['status'] == 'only_legal_reply'
    assert not session.records
    assert result['mechanism_established'] is False


def test_terminal_node_and_invalid_nominated_move_do_not_search():
    session = Session()
    assert api().probe_reply_dependency(chess.Board('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1'),
        session, depth=20)['status'] == 'terminal'
    with pytest.raises(ValueError):
        api().probe_reply_dependency(chess.Board(), session, depth=20, exclude_move='e5')
    assert not session.records


def test_wrong_root_binding_is_rejected_instead_of_used_as_a_counterfactual():
    session = Session()
    query = session.query
    def wrong(*args, **kwargs):
        r = query(*args, **kwargs)
        if r.root_moves:
            r.root_moves = r.root_moves[:1]
        return r
    session.query = wrong
    result = api().probe_reply_dependency(chess.Board(), session, depth=20)
    assert result['status'] == 'partial'
    assert all(m['drop_cp'] is None for m in result['measurements'])


def test_equal_node_allocations_are_not_repeated():
    session = Session()
    session.config = config(nodes=100, stability_nodes=100)
    result = api().probe_reply_dependency(chess.Board(), session, depth=20)
    assert len(result['measurements']) == 1
    assert len(session.records) == 2


def test_wrapper_validates_the_actual_prefix_before_creating_a_session():
    def forbidden(*args):
        raise AssertionError('illegal prefix reached engine')
    with pytest.raises(ValueError):
        api().locate_reply_dependency(chess.STARTING_FEN, 'e4', continuation=['e4'],
            config=config(), depth=20, session_factory=forbidden)
