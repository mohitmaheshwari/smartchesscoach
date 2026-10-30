"""Pawn-pressure hints need identity, reply-class and counterfactual receipts."""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace

import chess
import pytest

from services.reasoning import positional
from services.reasoning.contracts import SearchRecord, fingerprint
from services.reasoning.render import render
from services.reasoning.timeline import build_timeline, event_facts
from services.reasoning.verify import verify, verify_dependencies


FEN = 'r1b2rk1/ppp5/5q1p/3pNpp1/3Pn3/2PB4/P1Q2PPP/R3K2R w KQ - 0 15'


def fixture(*, mirror=False, depth=20, reference_retreats=True, ignore_is_worse=True, history=False, max_plies=18):
    root = chess.Board(FEN)
    if history:
        for san in ('Nf7', 'Re8', 'Ne5', 'Rf8'):
            root.push_san(san)
    played = ['c3c4', 'c7c5', 'c4d5', 'c5d4']
    alternative = ['f2f3', 'e4c5']
    reference = ['e4d6', 'h2h4', 'g5g4']
    witness = ['c7c5', 'f3e4', 'f5e4', 'd3b5']
    def flip(raw):
        m = chess.Move.from_uci(raw)
        return chess.Move(m.from_square ^ 56, m.to_square ^ 56).uci()
    if mirror:
        root = root.mirror()
        played, alternative, reference, witness = [[flip(m) for m in moves]
                                                  for moves in (played, alternative, reference, witness)]
    mover = 'white' if root.turn else 'black'
    def record(name, board, roots, moves, value, nodes, reached=15, requested_depth=None):
        return SearchRecord(fingerprint([name, board.fen(), moves, nodes]), name, board.fen(),
            sorted(m.uci() if isinstance(m, chess.Move) else m for m in roots), nodes, 1,
            'complete_iteration', [{'root_uci': moves[0], 'moves_uci': moves,
                'score': {'kind': 'cp', 'value': value, 'pov': mover}, 'depth': reached}],
            requested_depth=requested_depth)
    base = {played[0]: record('played_base', root, [played[0]], played, -150, 30000),
            alternative[0]: record('alt_base', root, [alternative[0]], alternative, 20, 30000)}
    stable = {played[0]: record('played_stable', root, [played[0]], played, -175, 120000),
              alternative[0]: record('alt_stable', root, [alternative[0]], alternative, 14, 120000)}
    timelines = {}
    def add_line(moves, rec, **kwargs):
        line = build_timeline(root, moves, rec.id, max_plies)
        line['source_query'] = {'purpose': rec.purpose, 'root_moves': rec.root_moves,
            'start_ply': 0 if rec.fen == root.fen() else 1}
        timelines[line['id']] = line
        return line
    p, a = add_line(played, stable[played[0]]), add_line(alternative, stable[alternative[0]])
    class Session:
        config = SimpleNamespace(nodes=30000, stability_nodes=120000, equivalence_cp=30)
        def __init__(self):
            self.records = [*base.values(), *stable.values()]
        def query(self, board, purpose, *, roots=(), nodes=None, depth=None, **kwargs):
            if board.fen() == p['nodes'][1]['fen']:
                moves, value = played[1:], -133
            elif board.fen() == a['nodes'][1]['fen']:
                if roots:
                    moves, value = witness, 86 if ignore_is_worse else 13
                else:
                    moves = reference if reference_retreats or not depth else witness
                    value = -1 if depth else 13
            else:
                raise AssertionError('Unexpected pressure search board')
            rec = record(purpose, board, roots, moves, value, nodes,
                         reached=fixture_depth if depth else 15, requested_depth=depth)
            self.records.append(rec)
            return rec
    fixture_depth = depth
    return root, p, a, base, stable, Session(), add_line, timelines


def compose(**kwargs):
    root, p, a, base, stable, session, add_line, timelines = fixture(**kwargs)
    report = positional.compare_position_features([p, a], max_plies=4)
    h, extra = positional.piece_pressure_hypothesis(root, p, a, report, base, stable,
        session, add_line, verification_nodes=2000000)
    facts = {fact.id: fact for line in timelines.values() for fact in event_facts(line)}
    facts.update({fact.id: fact for fact in extra})
    assert all(verify(fact, timelines[fact.timeline_id]) is None for fact in facts.values())
    return h, {key: asdict(fact) for key, fact in facts.items()}, timelines, {r.id: r.document() for r in session.records}


@pytest.mark.parametrize('mirror', [False, True])
def test_pressure_composes_when_best_replies_move_the_same_piece_to_different_squares(mirror):
    h, facts, lines, searches = compose(mirror=mirror)
    assert h.status == 'supported_mechanism'
    assert h.objective['kind'] == 'comparative_piece_pressure'
    assert h.objective['reply_agreement'] == 'same_piece_leaves_target_square'
    assert verify_dependencies(h, facts, lines, searches) is None
    text = render(asdict(h), facts, 'inferior', {})['text']
    assert ('pawn on f6' if mirror else 'pawn on f3') in text
    assert ('knight on e5' if mirror else 'knight on e4') in text
    assert 'forced' not in text.lower() and 'must move' not in text.lower()
    assert text.endswith('Check whether a pawn can challenge an active enemy piece before starting another plan.')


@pytest.mark.parametrize('settings,reason', [
    ({'depth': 19}, 'opponent_reference_depth_not_reached'),
    ({'reference_retreats': False}, 'best_reply_does_not_move_target_piece'),
    ({'ignore_is_worse': False}, 'leaving_target_not_stably_worse'),
])
def test_incomplete_pressure_never_becomes_a_teaching_certificate(settings, reason):
    h, facts, lines, searches = compose(**settings)
    assert h.status == 'incomplete_hypothesis'
    assert reason in h.unresolved
    assert verify_dependencies(h, facts, lines, searches) is None


@pytest.mark.parametrize('mutation', ['strength', 'target', 'actor', 'root_score', 'reply_roots',
                                     'reply_depth', 'reply_score', 'counterfactual_roots',
                                     'missing_capture', 'witness_words', 'search_receipt', 'pressure_best_move_illegal'])
def test_independent_pressure_verifier_rejects_forged_links(mutation):
    h, facts, lines, searches = compose()
    h, facts, lines, searches = deepcopy((h, facts, lines, searches))
    o = h.objective
    if mutation == 'strength':
        h.wording_strength = 'unavoidable'
    elif mutation == 'target':
        o['target_id'] = 'black:bishop:c8'
    elif mutation == 'actor':
        facts[o['attack_proposition_id']]['actor'] = 'black'
    elif mutation == 'root_score':
        o['root_comparisons'][0]['best_score']['value'] += 100
    elif mutation == 'reply_roots':
        rec = searches[o['reply_references'][1]['search_id']]
        rec['root_moves'] = [rec['lines'][0]['moves_uci'][0]]
    elif mutation == 'reply_depth':
        searches[o['reply_references'][1]['search_id']]['lines'][0]['depth'] = 19
    elif mutation == 'reply_score':
        o['reference_comparison']['best_score']['value'] += 100
    elif mutation == 'counterfactual_roots':
        pair = o['pressure_comparisons'][0]
        searches[pair['other_search_id']]['root_moves'].pop()
    elif mutation == 'missing_capture':
        h.proposition_ids = [key for key in h.proposition_ids
            if not (facts[key]['relation'] == 'captures' and facts[key]['ply'] == 3)]
    elif mutation == 'witness_words':
        o['witness_san'][1] = 'Kh8'
    elif mutation == 'search_receipt':
        h.search_ids.remove(o['reply_references'][1]['search_id'])
    elif mutation == 'pressure_best_move_illegal':
        pair = o['pressure_comparisons'][0]
        searches[pair['best_search_id']]['lines'][0]['moves_uci'][0] = 'e4e8'
    assert verify_dependencies(h, facts, lines, searches) is not None


def test_no_pressure_composition_without_a_matching_chessgpt_hint():
    root, p, a, base, stable, session, add_line, _ = fixture()
    report = positional.compare_position_features([p, a], max_plies=4)
    for snap in report['snapshots']:
        snap['features']['tempo']['evidence'] = []
    h, extra = positional.piece_pressure_hypothesis(root, p, a, report, base, stable,
        session, add_line, verification_nodes=2000000)
    assert h is None and not extra


def test_same_pressure_in_both_roots_is_not_a_contrast():
    root, p, a, base, stable, session, add_line, _ = fixture()
    report = positional.compare_position_features([a], max_plies=4)
    h, _ = positional.piece_pressure_hypothesis(root, a, a, report, base, stable,
        session, add_line, verification_nodes=2000000)
    assert h is None


def test_pressure_verifier_preserves_history_bound_node_ids():
    h, facts, lines, searches = compose(history=True)
    assert h.status == 'supported_mechanism'
    assert verify_dependencies(h, facts, lines, searches) is None


@pytest.mark.parametrize('horizon,reason', [(1, 'reply_projection_horizon_too_short'),
                                         (3, 'exchange_projection_horizon_too_short')])
def test_short_projection_leaves_pressure_incomplete_without_inventing_events(horizon, reason):
    h, facts, lines, searches = compose(max_plies=horizon)
    assert h.status == 'incomplete_hypothesis'
    assert reason in h.unresolved
    assert verify_dependencies(h, facts, lines, searches) is None
