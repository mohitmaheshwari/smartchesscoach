"""Composed relation changes are candidates, not certified lessons."""
from copy import deepcopy
from importlib import import_module

import chess
import pytest

from services.reasoning.timeline import build_timeline
from test_reasoning_piece_pressure import fixture


def api():
    return import_module('services.reasoning.chain_builder')


@pytest.mark.parametrize('mirror', [False, True])
def test_composes_lost_support_attack_capture_and_exposure_without_piece_type_rules(mirror):
    root, played, alternative, *_ = fixture(mirror=mirror)
    result = api().build_candidate_chains(root, played, alternative)
    guard = 'black:pawn:c6' if mirror else 'white:pawn:c3'
    middle = 'black:pawn:d5' if mirror else 'white:pawn:d4'
    key = 'black:knight:e4' if mirror else 'white:knight:e5'
    chains = result['candidates']
    assert any(c['facts'][0]['subject'] == guard and c['facts'][0]['object'] == middle
        and any(f['kind'] == 'capture' and f['object'] == middle for f in c['facts'])
        and any(f['kind'] == 'support_lost' and f['subject'] == middle and f['object'] == key for f in c['facts'])
        and any(f['kind'] == 'exposed' and f['subject'] == key for f in c['facts']) for c in chains)
    assert all(c['status'] == 'candidate' and not c['mechanism_verified'] for c in chains)


def test_opponent_attack_without_capture_is_not_invented_as_capture():
    root, played, alternative, *_ = fixture()
    short = build_timeline(root, played['moves_uci'][:2], 'short', 2)
    result = api().build_candidate_chains(root, short, alternative)
    assert all(f['kind'] != 'capture' for c in result['candidates'] for f in c['facts'])


def test_alternative_branch_does_not_create_false_root_support():
    root, played, _, *_ = fixture()
    # Same played line as the alternative cannot restore the removed protection.
    result = api().build_candidate_chains(root, played, played)
    assert all(not c['contrast']['root_relation_preserved'] for c in result['candidates'])


@pytest.mark.parametrize('mutation', ['event', 'node'])
def test_untrusted_replay_cannot_invent_a_link(mutation):
    root, played, alternative, *_ = fixture()
    line = deepcopy(played)
    if mutation == 'event':
        line['events'][1]['moving_piece_id'] = 'black:queen:f6'
    else:
        line['nodes'][1]['relations']['d4']['friendly_defenders'] = ['c3']
    with pytest.raises(ValueError):
        api().build_candidate_chains(root, line, alternative)


def test_no_chess_fact_or_causal_claim_is_generated_from_empty_line():
    root = chess.Board()
    line = build_timeline(root, ['e2e4'], 'test', 1)
    result = api().build_candidate_chains(root, line)
    assert not result['candidates']
    assert result['coaching'] is None
