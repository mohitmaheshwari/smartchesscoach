"""Hybrid boundaries: real geometry, untrusted features, and independent proof checks."""
from copy import deepcopy
from dataclasses import asdict
from importlib import import_module
from types import SimpleNamespace

import chess
import pytest

from services.reasoning.contracts import SearchRecord, fingerprint
from services.reasoning.timeline import build_timeline, event_facts
from services.reasoning.verify import verify, verify_dependencies


FEN = 'r1bq1rk1/ppp5/2n1p2p/3pBpp1/2PPn3/2PB1N2/P1Q2PPP/R3K2R b KQ - 1 12'


def hybrid():
    return import_module('services.reasoning.positional')


def fixture(mirror=False, reference_depth=20, alternative_moves=None):
    board = chess.Board(FEN)
    p = ['c6e5', 'f3e5']
    a = list(alternative_moves or ['g5g4', 'f3d2', 'c6e5', 'd4e5'])
    if mirror:
        board = board.mirror()
        def flip(raw):
            m = chess.Move.from_uci(raw)
            return chess.Move(m.from_square ^ 56, m.to_square ^ 56).uci()
        p, a = [flip(m) for m in p], [flip(m) for m in a]
    pov = 'white' if board.turn else 'black'
    def record(ident, fen, roots, moves, value, nodes, depth=15):
        r = SearchRecord(ident, ident, fen, list(roots), nodes, 1, 'complete_iteration')
        r.lines = [{'root_uci': moves[0], 'moves_uci': moves,
                    'score': {'kind': 'cp', 'value': value, 'pov': pov}, 'depth': depth}]
        return r
    base = {p[0]: record('p_base', board.fen(), [p[0]], p, -32, 30000),
            a[0]: record('a_base', board.fen(), [a[0]], a, 170, 30000)}
    stable = {p[0]: record('p_stable', board.fen(), [p[0]], p, -22, 120000),
              a[0]: record('a_stable', board.fen(), [a[0]], a, 124, 120000)}
    timelines = {}
    def add_line(moves, rec, **kwargs):
        t = build_timeline(board, moves, rec.id, 18)
        t['source_query'] = {'purpose': rec.purpose, 'root_moves': rec.root_moves,
                             'start_ply': 0 if rec.fen == board.fen() else 1}
        timelines[t['id']] = t
        return t
    played = add_line(p, stable[p[0]])
    alternative = add_line(a, stable[a[0]])

    class Session:
        config = SimpleNamespace(nodes=30000, stability_nodes=120000, equivalence_cp=30)
        records = [*base.values(), *stable.values()]
        def can_query(self, nodes=None):
            return True
        def query(self, node, purpose, *, roots=(), width=1, nodes=None, depth=None):
            if node.fen() == played['nodes'][1]['fen']:
                moves = [m.uci() for m in roots] if roots else p[1:]
                value = 121 if roots else -18
            elif node.fen() == alternative['nodes'][1]['fen']:
                moves, value = a[1:], 135
            else:
                raise AssertionError('Unexpected board in recapture investigation')
            r = record(fingerprint([node.fen(), purpose, moves, nodes, depth]), node.fen(),
                       [m.uci() for m in roots], moves, value, nodes or 30000,
                       reference_depth if depth else 15)
            r.purpose, r.requested_depth = purpose, depth
            self.records.append(r)
            return r
    return board, played, alternative, base, stable, Session(), add_line, timelines


def compose(mirror=False, reference_depth=20, alternative_moves=None):
    board, played, alternative, base, stable, session, add_line, timelines = fixture(mirror, reference_depth, alternative_moves)
    report = hybrid().compare_position_features([played, alternative], max_plies=4)
    h, extra = hybrid().recapture_hypothesis(board, played, alternative, report, base,
                                            stable, session, add_line,
                                            verification_nodes=1000000)
    facts = {p.id: p for t in timelines.values() for p in event_facts(t)}
    facts.update({p.id: p for p in extra})
    documents = {key: asdict(value) for key, value in facts.items()}
    searches = {r.id: r.document() for r in session.records}
    return h, facts, documents, searches, timelines


def test_imported_provider_keeps_unpriced_concrete_outpost():
    board = chess.Board(FEN)
    board.push_san('Nxe5')
    board.push_san('Nxe5')
    provider = hybrid().ChessGPTFeatures()
    features = provider.evaluate(board)
    assert any(e['square'] == 'e5' and e['color'] == 'white'
               for e in features['outposts']['evidence'])
    assert features['outposts']['value'] > 0
    assert provider.provenance()['revision'] == 'b7ea991854f926250036105f152894881e7820a2'
    assert len(provider.provenance()['source_sha256']) == 64


def test_feature_snapshots_are_bound_to_our_nodes_and_do_not_claim_cp_causality():
    _, played, alternative, *_ = fixture()
    report = hybrid().compare_position_features([played, alternative], max_plies=4)
    snapshot = next(s for s in report['snapshots'] if s['timeline_id'] == played['id'] and s['ply'] == 2)
    assert snapshot['node_id'] == played['nodes'][2]['id']
    assert snapshot['fen'] == played['nodes'][2]['fen']
    assert snapshot['side_to_move'] == played['nodes'][2]['turn']
    assert report['value_pov'] == 'white'
    assert report['value_units'] == 'upstream_raw_feature_units'
    assert report['authority'] == 'candidate_evidence_only'
    assert all('causal_cp' not in d and 'share_of_gap' not in d for d in report['differences'])


@pytest.mark.parametrize('mirror', [False, True])
def test_recapture_composition_is_generic_and_independently_verified(mirror):
    h, facts, documents, searches, timelines = compose(mirror)
    assert h is not None and h.status == 'supported_mechanism'
    assert h.objective['kind'] == 'comparative_recapture'
    assert all(verify(p, timelines[p.timeline_id]) is None for p in facts.values())
    assert verify_dependencies(h, documents, timelines, searches) is None
    assert 'not_an_exhaustive_forced_reply_proof' in h.unresolved


def test_feature_label_cannot_create_a_safe_square_without_board_support():
    h, facts, documents, searches, timelines = compose()
    p = next(p for p in facts.values() if p.relation == 'secure_piece_placement')
    forged = deepcopy(asdict(p))
    forged['data']['pawn_defenders'] = ['a2']
    from services.reasoning.contracts import Proposition
    assert verify(Proposition(**forged), timelines[p.timeline_id]) is not None


def test_changed_actor_and_piece_identity_are_rejected():
    h, facts, documents, searches, timelines = compose()
    p = next(p for p in facts.values() if p.relation == 'secure_piece_placement')
    from services.reasoning.contracts import Proposition
    for change in [{'actor': 'black'}, {'subject': 'other_knight'}]:
        forged = {**asdict(p), **change}
        assert verify(Proposition(**forged), timelines[p.timeline_id]) is not None


def test_unreached_reference_depth_does_not_make_a_supported_mechanism():
    h, facts, documents, searches, timelines = compose(reference_depth=19)
    assert h is not None and h.status == 'incomplete_hypothesis'
    assert 'opponent_reference_depth_not_reached' in h.unresolved


def test_forged_root_score_or_pov_cannot_license_the_chain():
    h, facts, documents, searches, timelines = compose()
    root = next(r for r in searches.values() if r['purpose'] == 'a_stable')
    root['lines'][0]['score']['pov'] = 'white'
    assert verify_dependencies(h, documents, timelines, searches) is not None


def test_composition_does_not_claim_all_legal_replies_are_forced():
    h, facts, documents, searches, timelines = compose()
    h.wording_strength = 'unavoidable'
    assert verify_dependencies(h, documents, timelines, searches) is not None


def test_restricted_opponent_reference_cannot_support_a_complete_chain():
    h, facts, documents, searches, timelines = compose()
    reference = searches[h.objective['reply_references'][0]['search_id']]
    reference['root_moves'] = [reference['lines'][0]['moves_uci'][0]]
    assert verify_dependencies(h, documents, timelines, searches) is not None


def test_invented_recapture_score_is_rejected():
    h, facts, documents, searches, timelines = compose()
    h.objective['recapture_comparisons'][0]['best_score']['value'] += 50
    assert verify_dependencies(h, documents, timelines, searches) is not None


def test_missing_placement_receipt_is_rejected():
    h, facts, documents, searches, timelines = compose()
    h.proposition_ids.remove(h.objective['placement_proposition_id'])
    assert verify_dependencies(h, documents, timelines, searches) is not None


def test_pawn_advance_challenge_is_not_permitted_by_a_false_feature_label():
    from services.reasoning.contracts import Proposition
    h, facts, documents, searches, timelines = compose()
    p = next(p for p in facts.values() if p.relation == 'secure_piece_placement')
    changed = deepcopy(timelines[p.timeline_id])
    board = chess.Board(changed['nodes'][p.ply]['fen'])
    board.remove_piece_at(chess.F5)
    board.set_piece_at(chess.F7, chess.Piece(chess.PAWN, chess.BLACK))
    changed['nodes'][p.ply]['fen'] = board.fen()
    assert verify(Proposition(**asdict(p)), changed) is not None


def test_controlled_text_explains_the_chain_and_keeps_the_limit():
    from services.reasoning.render import render
    h, facts, documents, searches, timelines = compose()
    result = render(asdict(h), documents, 'inferior', {})
    assert "After Black's Nxe5, White can play Nxe5" in result['text']
    assert 'protected by the pawn on d4' in result['text']
    assert 'g4 instead attacks the defending knight on f3 first' in result['text']
    assert result['text'].endswith('Before an exchange, check which piece would take back.')
    assert 'only legal' not in result['text'] and 'must' not in result['text']
    assert result['scope'] == h.wording_strength


def test_disabled_combination_never_constructs_a_feature_provider(monkeypatch):
    from services.reasoning.engine import explain_fen
    from test_reasoning_boundaries import config
    def forbidden(*args):
        raise AssertionError('Feature provider must remain opt-in')
    monkeypatch.setattr(hybrid().ChessGPTFeatures, '__init__', forbidden)
    result = explain_fen('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1', config=config())
    assert 'feature_evidence' not in result


def test_combination_requires_explicit_experimental_allocations():
    from services.reasoning.engine import explain_fen
    from test_reasoning_boundaries import config
    with pytest.raises(ValueError, match='feature_plies'):
        explain_fen(FEN, 'Nxe5', config=config(), positional_features=True)


def test_longer_demonstrations_preserve_every_intermediate_move_in_text():
    from services.reasoning.render import render
    h, facts, documents, searches, timelines = compose(
        alternative_moves=['g5g4', 'f3d2', 'h6h5', 'c4c5', 'c6e5', 'd4e5'])
    assert h.status == 'supported_mechanism'
    assert verify_dependencies(h, documents, timelines, searches) is None
    assert 'After Nd2 h5 c5 Nxe5 dxe5' in render(asdict(h), documents, 'inferior', {})['text']


def test_a_newly_advanced_pawn_is_not_the_original_recapture_counterfactual():
    h, facts, documents, searches, timelines = compose(
        alternative_moves=['g5g4', 'f3d2', 'h6h5', 'f2f4', 'c6e5', 'f4e5'])
    assert h.status == 'incomplete_hypothesis'
    assert 'alternative_recapture_not_legal_in_played_branch' in h.unresolved
