"""ChessGPT proposes positional evidence; our existing core owns its proof."""
from __future__ import annotations

from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path

import chess

from .contracts import fingerprint, proposal
from .objectives import common_prefix
from .search import comparison, fingerprint_bytes
from .timeline import atom, event_facts


class ChessGPTFeatures:
    def __init__(self):
        from vendor.chessgpt import features
        self.module = features
        self.path = Path(features.__file__)
        self.metadata = json.loads(self.path.with_name('PROVENANCE.json').read_text(encoding='utf-8'))
        if fingerprint_bytes(self.path) != self.metadata['source_sha256']:
            raise ValueError('vendored_feature_source_changed_without_provenance_update')

    def provenance(self):
        return {'provider': 'chessgpt_features', 'revision': self.metadata['revision'],
                'source_sha256': fingerprint_bytes(self.path), 'source_path': self.metadata['source_path'],
                'provenance_sha256': fingerprint_bytes(self.path.with_name('PROVENANCE.json'))}

    def evaluate(self, board):
        return {name: {'value': float(value.value), 'evidence': deepcopy(value.evidence)}
                for name, value in self.module.evaluate(board).items()}


def compare_position_features(timelines, *, max_plies, provider=None):
    if isinstance(max_plies, bool) or not isinstance(max_plies, int) or max_plies < 1:
        raise ValueError('feature horizon must be an explicit positive integer')
    provider = provider or ChessGPTFeatures()
    report = {'authority': 'candidate_evidence_only', 'provider': provider.provenance(),
              'max_plies': max_plies, 'value_pov': 'white', 'value_units': 'upstream_raw_feature_units',
              'snapshots': [], 'differences': []}
    cache, indexed = {}, {}
    for line in timelines:
        for ply, node in enumerate(line['nodes'][:max_plies + 1]):
            if node['fen'] not in cache:
                cache[node['fen']] = provider.evaluate(chess.Board(node['fen']))
            item = {'timeline_id': line['id'], 'node_id': node['id'], 'ply': ply,
                    'fen': node['fen'], 'side_to_move': node['turn'], 'features': cache[node['fen']]}
            item['id'] = fingerprint([report['provider'], line['id'], node['id'], ply, item['features']])
            report['snapshots'].append(item)
            indexed[line['id'], ply] = item
    for first, second in combinations(timelines, 2):
        for ply in range(1, min(max_plies, len(first['events']), len(second['events'])) + 1):
            a, b = indexed[first['id'], ply], indexed[second['id'], ply]
            for name in a['features']:
                diff = a['features'][name]['value'] - b['features'][name]['value']
                if diff:
                    report['differences'].append({'feature': name, 'raw_difference': diff,
                        'first_snapshot_id': a['id'], 'second_snapshot_id': b['id'], 'ply': ply})
    if provider.provenance() != report['provider']:
        raise ValueError('feature_provider_changed_during_extraction')
    return report


def _pattern(played, alternative, report):
    """Join actions and identities, never SAN strings, fixture squares or game labels."""
    if len(played['events']) < 2 or len(alternative['events']) < 4:
        return None
    capture, recapture = played['events'][:2]
    prepare, retreat = alternative['events'][:2]
    if not (capture['captured_piece_id'] and recapture['captured_piece_id'] == capture['moving_piece_id']
            and capture['destination'] == recapture['destination']
            and retreat['moving_piece_id'] == recapture['moving_piece_id']
            and prepare['moving_piece_id'] != capture['moving_piece_id']):
        return None
    root = chess.Board(played['nodes'][0]['fen'])
    defender = chess.parse_square(recapture['origin'])
    target = chess.parse_square(capture['destination'])
    after_prepare = chess.Board(alternative['nodes'][1]['fen'])
    if (target not in root.attacks(defender)
            or defender not in after_prepare.attacks(chess.parse_square(prepare['destination']))):
        return None
    hint = next((snapshot for snapshot in report['snapshots']
                 if snapshot['timeline_id'] == played['id'] and snapshot['ply'] == 2
                 and any(e.get('kind') == 'outpost' and e.get('square') == recapture['destination']
                         for e in snapshot['features'].get('outposts', {}).get('evidence', []))), None)
    if hint is None:
        return None
    for later, reply in zip(alternative['events'][2:], alternative['events'][3:]):
        if (later['moving_piece_id'] == capture['moving_piece_id']
                and later['captured_piece_id'] == capture['captured_piece_id']
                and later['destination'] == capture['destination']
                and reply['captured_piece_id'] == capture['moving_piece_id']
                and reply['destination'] == capture['destination']
                and reply['moving_piece_id'] != recapture['moving_piece_id']
                and reply['moving_piece'] != recapture['moving_piece']):
            return {'capture_ply': later['ply'], 'recapture_ply': reply['ply'],
                    'placement_ply': 2, 'feature_snapshot_id': hint['id'],
                    'demonstration_san': alternative['moves_san'][:reply['ply']],
                    'defender_id': recapture['moving_piece_id'], 'target_square': recapture['destination']}
    return None


def _pair(best, other, pov):
    def score(record):
        raw = record.lines[0]['score']
        return raw if raw['pov'] == pov else {**raw, 'value': -raw['value'], 'pov': pov}
    return {'best_search_id': best.id, 'other_search_id': other.id,
            'best_score': deepcopy(score(best)), 'other_score': deepcopy(score(other)), 'pov': pov}


def _placement_claim(board, square):
    target = chess.parse_square(square)
    piece = board.piece_at(target)
    if piece is None:
        return None
    pawns = sorted(chess.square_name(s) for s in board.attackers(piece.color, target)
                   if board.piece_type_at(s) == chess.PAWN)
    enemies = sorted(chess.square_name(s) for s in board.attackers(not piece.color, target))
    adjacent = sorted(chess.square_name(s) for s in board.pieces(chess.PAWN, not piece.color)
                      if abs(chess.square_file(s) - chess.square_file(target)) == 1)
    potential = [s for s in adjacent if (chess.square_rank(chess.parse_square(s)) > chess.square_rank(target)
                 if piece.color else chess.square_rank(chess.parse_square(s)) < chess.square_rank(target))]
    if not pawns or enemies or potential:
        return None
    return {'piece': chess.piece_name(piece.piece_type), 'color': 'white' if piece.color else 'black',
            'pawn_defenders': pawns, 'enemy_attackers': enemies, 'adjacent_enemy_pawns': adjacent,
            'central_square': bool(chess.BB_SQUARES[target] & chess.BB_CENTER),
            'pawn_challenge_scope': 'existing_adjacent_files_forward_moves'}


def recapture_hypothesis(root, played, alternative, report, base_records, stable_records,
                         session, add_line, *, verification_nodes):
    pattern = _pattern(played, alternative, report)
    if pattern is None:
        return None, []
    data = _placement_claim(chess.Board(played['nodes'][2]['fen']), pattern['target_square'])
    if data is None:
        return None, []
    placement = atom(played, 2, pattern['defender_id'], 'secure_piece_placement',
                     pattern['target_square'], **data)
    facts = [p for p in event_facts(played) if p.ply <= 2]
    facts += [p for p in event_facts(alternative) if p.ply <= pattern['recapture_ply']]
    facts.append(placement)
    obj = {'kind': 'comparative_recapture', 'root_connected': True,
           'played_timeline_id': played['id'], 'alternative_timeline_id': alternative['id'],
           'contrast_root_uci': played['root_uci'], **pattern,
           'placement_proposition_id': placement.id, 'root_comparisons': [],
           'recapture_comparisons': [], 'reply_references': []}
    h = proposal('PREPARE', alternative['root_uci'], obj, facts,
                 [{'kind': 'preparation_changes_recapture', 'played_timeline_id': played['id'],
                   'alternative_timeline_id': alternative['id'], 'placement_id': placement.id}])
    h.wording_strength = 'demonstrated_preparation_with_verified_replies'
    h.unresolved = ['not_an_exhaustive_forced_reply_proof', 'no_exact_causal_cp_allocation']
    after = root.copy()
    after.push_uci(played['root_uci'])
    destination = chess.parse_square(pattern['target_square'])
    expected = played['moves_uci'][1]
    others = [m for m in sorted(after.legal_moves, key=lambda m: m.uci())
              if after.is_capture(m) and m.to_square == destination and m.uci() != expected
              and after.piece_type_at(m.from_square) != after.piece_type_at(chess.Move.from_uci(expected).from_square)]
    if alternative['moves_uci'][pattern['recapture_ply'] - 1] not in [m.uci() for m in others]:
        h.unresolved.append('alternative_recapture_not_legal_in_played_branch')
        return h, facts
    mover = 'white' if root.turn else 'black'
    opponent = 'black' if root.turn else 'white'
    for records in (base_records, stable_records):
        pair = _pair(records[alternative['root_uci']], records[played['root_uci']], mover)
        obj['root_comparisons'].append(pair)
        h.search_ids.extend([pair['best_search_id'], pair['other_search_id']])
        if comparison(pair['best_score'], pair['other_score'], session.config.equivalence_cp) != 'inferior':
            h.unresolved.append('root_comparison_not_stable')
            return h, facts
    obj['equivalence_cp'] = session.config.equivalence_cp
    needed = pattern['recapture_ply']
    for line, ply in ((played, 2), (alternative, needed)):
        a, b = base_records[line['root_uci']], stable_records[line['root_uci']]
        if common_prefix(a.lines[0]['moves_uci'], b.lines[0]['moves_uci']) < ply:
            h.unresolved.append('beyond_root_stability_agreement')
            return h, facts
    # Reserve the two unrestricted relevance checks before optional resources.
    for line, ply in ((played, 2), (alternative, needed)):
        board = root.copy()
        board.push_uci(line['root_uci'])
        reference = session.query(board, 'positional_opponent_best_reply', nodes=verification_nodes, depth=20)
        obj['reply_references'].append({'search_id': reference.id, 'timeline_id': line['id'],
                                         'required_ply': ply})
        h.search_ids.append(reference.id)
        if not reference.lines or reference.status != 'complete_iteration' or reference.lines[0].get('depth', 0) < 20:
            h.unresolved.append('opponent_reference_depth_not_reached')
            return h, facts
        if common_prefix(line['moves_uci'], [line['root_uci'], *reference.lines[0]['moves_uci']]) < ply:
            h.unresolved.append('best_reply_does_not_retain_recapture_chain')
            return h, facts
    for nodes in (session.config.nodes, session.config.stability_nodes):
        best = session.query(after, 'positional_recapture_best', nodes=nodes)
        other = session.query(after, 'positional_recapture_counterfactual', roots=others, nodes=nodes)
        h.search_ids.extend([best.id, other.id])
        if (not best.lines or not other.lines or best.status != 'complete_iteration'
                or other.status != 'complete_iteration' or best.lines[0]['moves_uci'][0] != expected):
            h.unresolved.append('recapture_comparison_unavailable_or_changed')
            return h, facts
        pair = _pair(best, other, opponent)
        pair['counterfactual_roots'] = [m.uci() for m in others]
        obj['recapture_comparisons'].append(pair)
        if comparison(pair['best_score'], pair['other_score'], session.config.equivalence_cp) != 'inferior':
            h.unresolved.append('recapture_value_difference_not_stable')
            return h, facts
    h.search_ids = sorted(set(h.search_ids))
    h.status = 'supported_mechanism'
    return h, facts
