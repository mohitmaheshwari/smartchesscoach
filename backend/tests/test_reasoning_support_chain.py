"""The played move's lost protection must precede an alternative's virtue."""
from copy import deepcopy
from dataclasses import asdict

import pytest
import chess

from services.reasoning import positional
from services.reasoning.render import render
from services.reasoning.timeline import build_timeline, event_facts
from services.reasoning.verify import verify, verify_dependencies
from test_reasoning_piece_pressure import fixture


def compose(*, mirror=False, depth=20, unstable=False):
    root, p, a, base, stable, session, add_line, lines = fixture(mirror=mirror, depth=depth)
    if unstable:
        base[p['root_uci']].lines[0]['moves_uci'] = p['moves_uci'][:2] + ['d4c5']
    report = positional.compare_position_features([p, a], max_plies=4)
    h, extra = positional.support_chain_hypothesis(root, p, a, report, base, stable,
        session, add_line, verification_nodes=2000000)
    facts = {f.id: f for line in lines.values() for f in event_facts(line)}
    facts.update({f.id: f for f in extra})
    assert all(verify(f, lines[f.timeline_id]) is None for f in facts.values())
    return h, {key: asdict(f) for key, f in facts.items()}, lines, {r.id: r.document() for r in session.records}


@pytest.mark.parametrize('mirror', [False, True])
def test_support_chain_joins_origin_loss_enemy_attack_defender_capture_and_exposure(mirror):
    h, facts, lines, searches = compose(mirror=mirror)
    assert h.status == 'supported_mechanism'
    assert h.objective['kind'] == 'comparative_support_chain'
    assert h.objective['capture_ply'] == 4
    assert verify_dependencies(h, facts, lines, searches) is None
    text = render(asdict(h), facts, 'inferior', {})['text']
    assert ('leaves c6 and stops defending d5' if mirror else 'leaves c3 and stops defending d4') in text
    assert ('knight on e4' if mirror else 'knight on e5') in text
    assert ('queen on f3' if mirror else 'queen on f6') in text
    assert ('pawn on d5 defending e4' if mirror else 'pawn on d4 defending e5') in text
    assert 'pawn for that knight' not in text
    assert text.endswith('Before pushing a pawn, check what it protects and what depends on that protection.')


@pytest.mark.parametrize('options,reason', [({'depth': 19}, 'opponent_reference_depth_not_reached'),
                                         ({'unstable': True}, 'beyond_root_stability_agreement')])
def test_support_loss_is_not_taught_without_stability_and_completed_best_reply(options, reason):
    h, facts, lines, searches = compose(**options)
    assert h.status == 'incomplete_hypothesis'
    assert reason in h.unresolved
    assert verify_dependencies(h, facts, lines, searches) is None


@pytest.mark.parametrize('mutation', ['guard', 'defender', 'key_piece', 'exposure', 'capture_ply',
                                     'reply_roots', 'depth', 'score', 'missing_origin', 'missing_capture',
                                     'words', 'strength', 'receipt'])
def test_independent_support_verifier_rejects_substituted_links(mutation):
    h, facts, lines, searches = deepcopy(compose())
    o = h.objective
    if mutation == 'guard':
        o['guard_id'] = 'white:pawn:a2'
    elif mutation == 'defender':
        o['defender_id'] = 'white:pawn:f2'
    elif mutation == 'key_piece':
        o['key_id'] = 'white:bishop:d3'
    elif mutation == 'exposure':
        o['exposed_to'][0]['square'] = 'a8'
    elif mutation == 'capture_ply':
        o['capture_ply'] = 2
    elif mutation == 'reply_roots':
        rec = searches[o['reply_references'][0]['search_id']]
        rec['root_moves'] = [rec['lines'][0]['moves_uci'][0]]
    elif mutation == 'depth':
        searches[o['reply_references'][0]['search_id']]['lines'][0]['depth'] = 19
    elif mutation == 'score':
        o['root_comparisons'][0]['best_score']['value'] += 100
    elif mutation == 'missing_origin':
        h.proposition_ids.remove(o['abandoned_proposition_id'])
    elif mutation == 'missing_capture':
        h.proposition_ids = [key for key in h.proposition_ids if facts[key]['relation'] != 'captures']
    elif mutation == 'words':
        o['demonstration_san'][1] = 'Qxe5'
    elif mutation == 'strength':
        h.wording_strength = 'unavoidable'
    elif mutation == 'receipt':
        h.search_ids.remove(o['reply_references'][0]['search_id'])
    assert verify_dependencies(h, facts, lines, searches) is not None


def test_support_family_does_not_select_an_unrelated_static_outpost():
    root, p, a, base, stable, session, add_line, _ = fixture()
    report = positional.compare_position_features([p, a], max_plies=4)
    for snap in report['snapshots']:
        snap['features']['outposts']['evidence'] = []
    h, facts = positional.support_chain_hypothesis(root, p, a, report, base, stable,
        session, add_line, verification_nodes=2000000)
    assert h is None and not facts


def test_support_account_abstains_when_the_completed_best_reply_avoids_the_chain():
    root, p, a, base, stable, session, add_line, _ = fixture()
    original = session.query
    def changed_reply(board, purpose, **kwargs):
        rec = original(board, purpose, **kwargs)
        if board.fen() == p['nodes'][1]['fen']:
            rec.lines[0]['moves_uci'] = ['e4f2']
        return rec
    session.query = changed_reply
    report = positional.compare_position_features([p, a], max_plies=4)
    h, _ = positional.support_chain_hypothesis(root, p, a, report, base, stable,
        session, add_line, verification_nodes=2000000)
    assert h.status == 'incomplete_hypothesis'
    assert 'best_reply_does_not_retain_support_loss' in h.unresolved


@pytest.mark.parametrize('extra_support', ['defender', 'key_piece'])
def test_a_remaining_defender_prevents_the_claim_of_a_broken_support_chain(extra_support):
    root, p, a, base, stable, session, add_line, _ = fixture()
    if extra_support == 'defender':
        root.remove_piece_at(chess.D3)
        root.set_piece_at(chess.E3, chess.Piece(chess.BISHOP, chess.WHITE))
        alt_moves = a['moves_uci']
    else:
        root.remove_piece_at(chess.F2)
        root.set_piece_at(chess.F4, chess.Piece(chess.PAWN, chess.WHITE))
        alt_moves = ['e1g1']
    played = build_timeline(root, p['moves_uci'], p['search_id'], 18)
    alternative = build_timeline(root, alt_moves, a['search_id'], 18)
    report = positional.compare_position_features([played, alternative], max_plies=4)
    h, facts = positional.support_chain_hypothesis(root, played, alternative, report, base, stable,
        session, add_line, verification_nodes=2000000)
    assert h is None and not facts
    assert len(session.records) == 4
