"""Compose candidate chains from replayed relations; no coaching authority."""
from __future__ import annotations

import chess

from .contracts import fingerprint
from .timeline import build_timeline


def _canonical(root, line):
    rebuilt = build_timeline(root, line['moves_uci'], line['search_id'], len(line['moves_uci']))
    if any(line[k] != rebuilt[k] for k in ('nodes', 'events', 'moves_uci', 'moves_san')):
        raise ValueError('timeline does not match legal identity-aware replay')


def _ids(node):
    return {v['piece_id']: v for v in node['relations'].values()}


def _related(node, state, field):
    return {node['relations'][sq]['piece_id'] for sq in state[field]}


def _facts(line):
    facts = []
    for event, before, after in zip(line['events'], line['nodes'], line['nodes'][1:]):
        old, new = _ids(before), _ids(after)
        ply = event['ply']
        common = {'ply': ply, 'move': event['move_san'], 'timeline_id': line['id']}
        if event['captured_piece_id']:
            facts.append({**common, 'kind': 'capture', 'subject': event['moving_piece_id'],
                'object': event['captured_piece_id'], 'square': event['captured_square']})
        for target in sorted(old.keys() & new.keys()):
            previous, current = old[target], new[target]
            old_def = _related(before, previous, 'friendly_defenders')
            new_def = _related(after, current, 'friendly_defenders')
            for defender in sorted(old_def - new_def):
                facts.append({**common, 'kind': 'support_lost', 'subject': defender, 'object': target,
                    'subject_square_before': old[defender]['square'], 'square': current['square'],
                    'remaining_defenders': sorted(new_def)})
            old_atk = _related(before, previous, 'enemy_attackers')
            new_atk = _related(after, current, 'enemy_attackers')
            for attacker in sorted(new_atk - old_atk):
                facts.append({**common, 'kind': 'attack_gained', 'subject': attacker, 'object': target,
                    'square': current['square'], 'remaining_defenders': sorted(new_def)})
            if old_def - new_def and not new_def:
                for attacker in sorted(new_atk):
                    facts.append({**common, 'kind': 'exposed', 'subject': target, 'object': attacker,
                        'square': current['square'], 'attacker_square': new[attacker]['square']})
    for item in facts:
        item['id'] = fingerprint(item)
    return facts


def _linked(a, b):
    if b['ply'] < a['ply']:
        return False
    pair = a['kind'], b['kind']
    if pair == ('support_lost', 'attack_gained'):
        return a['object'] == b['object'] and b['ply'] >= a['ply']
    if pair == ('attack_gained', 'capture'):
        return a['subject'] == b['subject'] and a['object'] == b['object'] and b['ply'] > a['ply']
    if pair == ('capture', 'support_lost'):
        return a['object'] == b['subject'] and b['ply'] == a['ply']
    if pair == ('support_lost', 'exposed'):
        return a['object'] == b['subject'] and b['ply'] == a['ply']
    return False


def build_candidate_chains(root: chess.Board, played: dict, alternative: dict | None = None):
    _canonical(root, played)
    if alternative is not None:
        _canonical(root, alternative)
    facts = _facts(played)
    roots = [f for f in facts if f['kind'] == 'support_lost' and f['ply'] == 1]
    alt = _ids(alternative['nodes'][1]) if alternative else {}
    candidates = []
    def walk(path):
        next_facts = [f for f in facts if f['id'] not in {x['id'] for x in path} and _linked(path[-1], f)]
        if not next_facts:
            if len(path) < 2:
                return
            first = path[0]
            target = alt.get(first['object'])
            preserved = bool(target and first['subject'] in _related(alternative['nodes'][1], target, 'friendly_defenders'))
            candidates.append({'id': fingerprint([f['id'] for f in path]), 'status': 'candidate',
                'mechanism_verified': False, 'facts': path,
                'contrast': {'root_relation_preserved': preserved, 'timeline_id': alternative['id'] if alternative else None},
                'unresolved': ['opponent_best_reply_and_defences', 'root_comparison_and_compensation',
                               'causal_relevance', 'independent_fact_review']})
            return
        for fact in next_facts:
            walk([*path, fact])
    for fact in roots:
        walk([fact])
    return {'schema_version': 'reasoning.candidate_chains.v1', 'played_timeline_id': played['id'],
            'candidates': candidates, 'fact_count': len(facts), 'coaching': None,
            'scope': 'legal_line_candidates_no_claim_of_forcedness_or_causal_verification'}
