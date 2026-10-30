"""Independent board/search checks; never imports the candidate feature library."""
from __future__ import annotations

import chess

from .objectives import common_prefix
from .search import comparison


def verify_placement(p, timeline):
    node = timeline['nodes'][p.ply]
    board = chess.Board(node['fen'])
    square = chess.parse_square(p.object)
    piece = board.piece_at(square)
    if piece is None or piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return 'placement_piece_absent_or_wrong_type'
    color = 'white' if piece.color == chess.WHITE else 'black'
    if (p.actor != color or p.subject != node['relations'][p.object]['piece_id']
            or p.subject != timeline['events'][p.ply - 1]['moving_piece_id']):
        return 'wrong_placement_actor_or_identity'
    if p.evidence_ids != (timeline['search_id'], node['id']):
        return 'wrong_placement_evidence'
    if board.attackers(not piece.color, square):
        return 'placement_is_currently_attacked'
    defenders = board.attackers(piece.color, square) & board.pieces(chess.PAWN, piece.color)
    if not defenders:
        return 'placement_has_no_pawn_support'
    adjacent, challenges = [], []
    rank, file = chess.square_rank(square), chess.square_file(square)
    for enemy_pawn in board.pieces(chess.PAWN, not piece.color):
        if chess.square_file(enemy_pawn) not in (file - 1, file + 1):
            continue
        adjacent.append(chess.square_name(enemy_pawn))
        # A conservative potential-forward-advance test, not a claim about
        # future file-changing captures or every future legal pawn sequence.
        enemy_rank = chess.square_rank(enemy_pawn)
        if (piece.color == chess.WHITE and enemy_rank > rank) or (piece.color == chess.BLACK and enemy_rank < rank):
            challenges.append(enemy_pawn)
    if challenges:
        return 'adjacent_pawn_can_potentially_advance_to_challenge'
    expected = {'piece': chess.piece_name(piece.piece_type), 'color': color,
                'pawn_defenders': sorted(chess.square_name(s) for s in defenders),
                'enemy_attackers': [], 'adjacent_enemy_pawns': sorted(adjacent),
                'central_square': square in chess.SquareSet(chess.BB_CENTER),
                'pawn_challenge_scope': 'existing_adjacent_files_forward_moves'}
    return None if p.data == expected else 'wrong_placement_support_or_claim_scope'


def _score_for(record, pov):
    raw = record['lines'][0]['score']
    return raw if raw['pov'] == pov else {**raw, 'value': -raw['value'], 'pov': pov}


def _pair_supported(pair, searches, fen, best_roots, other_roots, pov, epsilon, record_pov):
    a, b = searches[pair['best_search_id']], searches[pair['other_search_id']]
    if (a['status'] != 'complete_iteration' or b['status'] != 'complete_iteration'
            or a['fen'] != fen or b['fen'] != fen
            or a['root_moves'] != best_roots or b['root_moves'] != other_roots
            or not a['lines'] or not b['lines']
            or a['requested_nodes'] != b['requested_nodes']
            or a['lines'][0]['score']['pov'] != record_pov or b['lines'][0]['score']['pov'] != record_pov
            or pair['pov'] != pov or pair['best_score'] != _score_for(a, pov)
            or pair['other_score'] != _score_for(b, pov)):
        return False
    for record, roots in ((a, best_roots), (b, other_roots)):
        if roots and record['lines'][0]['moves_uci'][0] not in roots:
            return False
    return comparison(pair['best_score'], pair['other_score'], epsilon) == 'inferior'


def verify_recapture(h, propositions, timelines, searches):
    from .verify import _replay_certificate
    obj = h.objective
    if (h.operation != 'PREPARE' or h.wording_strength != 'demonstrated_preparation_with_verified_replies'
            or len(h.dependencies) != 1 or h.dependencies[0]['kind'] != 'preparation_changes_recapture'
            or searches is None):
        return 'unsupported_recapture_claim_strength'
    p, a = timelines[obj['played_timeline_id']], timelines[obj['alternative_timeline_id']]
    _replay_certificate(p)
    _replay_certificate(a)
    if (p['nodes'][0]['fen'] != a['nodes'][0]['fen'] or a['root_uci'] != h.root_uci
            or p['root_uci'] != obj['contrast_root_uci'] or obj['placement_ply'] != 2):
        return 'wrong_recapture_root_binding'
    if any(propositions[key]['timeline_id'] not in (p['id'], a['id']) for key in h.proposition_ids):
        return 'recapture_receipt_from_unrelated_timeline'
    first, takeback = p['events'][:2]
    prepare, retreat = a['events'][:2]
    later = a['events'][obj['capture_ply'] - 1]
    second = a['events'][obj['recapture_ply'] - 1]
    if (not first['captured_piece_id'] or takeback['captured_piece_id'] != first['moving_piece_id']
            or takeback['destination'] != first['destination']
            or retreat['moving_piece_id'] != takeback['moving_piece_id']
            or later['moving_piece_id'] != first['moving_piece_id']
            or later['captured_piece_id'] != first['captured_piece_id']
            or later['destination'] != first['destination']
            or second['captured_piece_id'] != first['moving_piece_id']
            or second['destination'] != first['destination']
            or second['moving_piece_id'] == takeback['moving_piece_id']
            or second['moving_piece'] == takeback['moving_piece']
            or obj['recapture_ply'] != obj['capture_ply'] + 1
            or obj['demonstration_san'] != a['moves_san'][:obj['recapture_ply']]
            or obj['defender_id'] != takeback['moving_piece_id']
            or obj['target_square'] != takeback['destination']):
        return 'recapture_identity_or_event_join_failed'
    root = chess.Board(p['nodes'][0]['fen'])
    defender = chess.parse_square(takeback['origin'])
    target = chess.parse_square(first['destination'])
    prepared = chess.Board(a['nodes'][1]['fen'])
    if (target not in root.attacks(defender)
            or defender not in prepared.attacks(chess.parse_square(prepare['destination']))):
        return 'preparation_does_not_attack_the_original_defender'
    placement = propositions[obj['placement_proposition_id']]
    if (placement['relation'] != 'secure_piece_placement' or placement['timeline_id'] != p['id']
            or placement['ply'] != 2 or placement['subject'] != takeback['moving_piece_id']
            or placement['object'] != first['destination']
            or h.dependencies[0]['placement_id'] != placement['id']):
        return 'wrong_recapture_placement_link'
    from .contracts import Proposition
    if placement['id'] not in h.proposition_ids or verify_placement(Proposition(**placement), p):
        return 'recapture_placement_failed_independent_check'
    required = [('legal_move', p['id'], 1, first['moving_piece_id'], p['root_uci']),
                ('legal_move', a['id'], 1, prepare['moving_piece_id'], a['root_uci']),
                ('captures', p['id'], 2, takeback['moving_piece_id'], first['moving_piece_id']),
                ('attacks_piece', a['id'], 1, prepare['moving_piece_id'], takeback['moving_piece_id']),
                ('reaches', a['id'], 2, retreat['moving_piece_id'], retreat['destination']),
                ('captures', a['id'], obj['capture_ply'], later['moving_piece_id'], first['captured_piece_id']),
                ('captures', a['id'], obj['recapture_ply'], second['moving_piece_id'], first['moving_piece_id'])]
    required += [('reaches', a['id'], e['ply'], e['moving_piece_id'], e['destination'])
                 for e in a['events'][:obj['recapture_ply']]]
    for relation, timeline_id, ply, subject, target_object in required:
        if not any(propositions[key]['relation'] == relation and propositions[key]['timeline_id'] == timeline_id
                   and propositions[key]['ply'] == ply and propositions[key]['subject'] == subject
                   and propositions[key]['object'] == target_object for key in h.proposition_ids):
            return 'recapture_dependency_fact_receipt_missing'
    # An unfinished investigation is not promoted merely because its geometry
    # is legal. It remains an incomplete hypothesis in the parent pipeline.
    if h.status == 'incomplete_hypothesis':
        return None
    if h.status != 'supported_mechanism' or len(obj['root_comparisons']) != 2:
        return 'recapture_support_incomplete'
    mover = p['nodes'][0]['turn']
    opponent = 'black' if mover == 'white' else 'white'
    epsilon = obj['equivalence_cp']
    for pair in obj['root_comparisons']:
        if not _pair_supported(pair, searches, root.fen(), [a['root_uci']], [p['root_uci']], mover, epsilon, mover):
            return 'recapture_root_score_binding_failed'
        if any(searches[pair[key]]['lines'][0]['score']['pov'] != mover for key in ('best_search_id', 'other_search_id')):
            return 'wrong_recapture_score_perspective'
    for line, needed, key in ((p, 2, 'other_search_id'), (a, obj['recapture_ply'], 'best_search_id')):
        records = [searches[pair[key]] for pair in obj['root_comparisons']]
        if (line['search_id'] != records[1]['id']
                or common_prefix(records[0]['lines'][0]['moves_uci'], records[1]['lines'][0]['moves_uci']) < needed
                or common_prefix(line['moves_uci'], records[1]['lines'][0]['moves_uci']) < needed):
            return 'recapture_beyond_root_stability_agreement'
    if len(obj['reply_references']) != 2:
        return 'recapture_reply_references_missing'
    for binding, line, needed in zip(obj['reply_references'], (p, a), (2, obj['recapture_ply'])):
        record = searches[binding['search_id']]
        if (binding['timeline_id'] != line['id'] or binding['required_ply'] != needed
                or record['fen'] != line['nodes'][1]['fen'] or record['root_moves']
                or record['status'] != 'complete_iteration' or not record['lines']
                or record['lines'][0].get('depth', 0) < 20
                or common_prefix(line['moves_uci'], [line['root_uci'], *record['lines'][0]['moves_uci']]) < needed):
            return 'recapture_not_retained_by_completed_unrestricted_reply_search'
    after = chess.Board(p['nodes'][1]['fen'])
    expected = p['moves_uci'][1]
    other_roots = [m.uci() for m in sorted(after.legal_moves, key=lambda m: m.uci())
                   if after.is_capture(m) and m.to_square == target and m.uci() != expected
                   and after.piece_type_at(m.from_square) != after.piece_type_at(chess.Move.from_uci(expected).from_square)]
    original_recapturer = p['nodes'][1]['relations'].get(second['origin'], {})
    if (a['moves_uci'][obj['recapture_ply'] - 1] not in other_roots
            or original_recapturer.get('piece_id') != second['moving_piece_id']
            or len(obj['recapture_comparisons']) != 2):
        return 'recapture_counterfactual_missing'
    for pair in obj['recapture_comparisons']:
        if (pair['counterfactual_roots'] != other_roots
                or not _pair_supported(pair, searches, after.fen(), [], other_roots, opponent, epsilon, mover)
                or searches[pair['best_search_id']]['lines'][0]['moves_uci'][0] != expected
                or searches[pair['other_search_id']]['lines'][0]['moves_uci'][0] not in other_roots):
            return 'recapture_choice_score_binding_failed'
    bound_ids = {pair[key] for pair in obj['root_comparisons'] + obj['recapture_comparisons']
                 for key in ('best_search_id', 'other_search_id')}
    bound_ids.update(b['search_id'] for b in obj['reply_references'])
    if not bound_ids <= set(h.search_ids):
        return 'recapture_search_receipts_missing'
    return None
