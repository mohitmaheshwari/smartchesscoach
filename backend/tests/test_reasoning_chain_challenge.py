"""Search receipts constrain candidates; agreement cannot certify relevance."""
from copy import deepcopy
from importlib import import_module

from services.reasoning.chain_builder import build_candidate_chains
from services.reasoning.timeline import build_timeline
from test_reasoning_piece_pressure import fixture


def sample():
    root, played, alternative, _, stable, session, *_ = fixture()
    after = root.copy(); after.push_uci(played['root_uci'])
    reply = session.query(after, 'reference', depth=20, nodes=2000000).document()
    played = build_timeline(root, [played['root_uci'], *reply['lines'][0]['moves_uci']], reply['id'], 15)
    base = stable[played['root_uci']].document()
    base['lines'][0]['depth'] = 20
    ranking = stable[alternative['root_uci']].document()
    ranking['root_moves'] = []
    ranking['lines'][0]['depth'] = 20
    candidates = build_candidate_chains(root, played, alternative)['candidates']
    return root, played, alternative, candidates, base, reply, ranking


def check(*args):
    return import_module('services.reasoning.chain_challenge').challenge_candidates(*args, depth=20)


def test_agreeing_searched_lines_are_still_candidates_not_certified_lessons():
    root, line, alt, candidates, base, reply, ranking = sample()
    result = check(root, line, alt, candidates, base, reply, ranking)
    assert result[0]['checks']['played_line_agreement_plies'] == 4
    assert result[0]['checks']['facts_within_agreement']
    assert result[0]['checks']['root_relation_preserved']
    assert result[0]['status'] == 'candidate_needs_review'
    assert result[0]['mechanism_verified'] is False


def test_late_or_divergent_consequence_is_not_promoted():
    root, line, alt, candidates, base, reply, ranking = sample()
    base['lines'][0]['moves_uci'] = ['c3c4', 'c7c5', 'd4c5']
    result = check(root, line, alt, candidates, base, reply, ranking)
    assert result[0]['checks']['played_line_agreement_plies'] == 2
    assert not result[0]['checks']['facts_within_agreement']
    assert result[0]['status'] == 'incomplete'


def test_forced_root_or_unreached_depth_is_not_treated_as_a_best_reply():
    root, line, alt, candidates, base, reply, ranking = sample()
    reply['root_moves'] = [reply['lines'][0]['root_uci']]
    ranking['lines'][0]['depth'] = 19
    result = check(root, line, alt, candidates, base, reply, ranking)
    assert not result[0]['checks']['unrestricted_reply_binding']
    assert not result[0]['checks']['ranking_at_requested_depth']
    assert result[0]['status'] == 'incomplete'


def test_forged_candidate_is_rejected():
    root, line, alt, candidates, base, reply, ranking = sample()
    forged = deepcopy(candidates)
    forged[0]['facts'][0]['subject'] = 'white:pawn:a2'
    result = check(root, line, alt, forged, base, reply, ranking)
    assert not result[0]['checks']['canonical_candidate']
    assert result[0]['status'] == 'incomplete'
