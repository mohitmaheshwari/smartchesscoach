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


def verify_piece_pressure(h, propositions, timelines, searches):
    """Check pawn pressure independently of the imported hint and composer."""
    from .contracts import Proposition
    from .timeline import build_timeline
    from .verify import verify
    obj = h.objective
    if (h.operation != 'PREPARE' or h.wording_strength != 'demonstrated_pawn_pressure_with_verified_replies'
            or h.dependencies != [{'kind': 'pawn_attack_changes_reply', 'attack_id': obj['attack_proposition_id']}]
            or obj['reply_agreement'] != 'same_piece_leaves_target_square' or searches is None):
        return 'unsupported_piece_pressure_strength_or_dependency'
    p, a = timelines[obj['played_timeline_id']], timelines[obj['alternative_timeline_id']]
    root = chess.Board(a['nodes'][0]['fen'])
    target = chess.parse_square(obj['target_square'])
    own = a['nodes'][0]['turn']
    opponent = 'black' if own == 'white' else 'white'
    def canonical(line):
        expected = build_timeline(root, line['moves_uci'], line['search_id'], len(line['moves_uci']))
        # The original history contributes to node IDs; a board-only verifier
        # reconstructs geometry/events, retaining the supplied history-bound IDs.
        return (all(line[key] == expected[key] for key in ('events', 'moves_san', 'root_uci'))
                and len(line['nodes']) == len(expected['nodes'])
                and all({k: v for k, v in actual.items() if k != 'id'} ==
                        {k: v for k, v in rebuilt.items() if k != 'id'}
                        for actual, rebuilt in zip(line['nodes'], expected['nodes'])))
    if (not canonical(p) or not canonical(a) or a['root_uci'] != h.root_uci
            or p['root_uci'] != obj['contrast_root_uci'] or p['root_uci'] == a['root_uci']
            or p['nodes'][0]['fen'] != root.fen()):
        return 'wrong_piece_pressure_root_binding'
    after = chess.Board(a['nodes'][1]['fen'])
    played_after = chess.Board(p['nodes'][1]['fen'])
    attack = propositions[obj['attack_proposition_id']]
    event = a['events'][0]
    target_piece = after.piece_at(target)
    if (event['moving_piece'] != 'pawn' or event['moving_piece_id'] != obj['attacker_id']
            or attack['relation'] != 'attacks_piece' or attack['ply'] != 1 or attack['timeline_id'] != a['id']
            or attack['actor'] != own or attack['subject'] != obj['attacker_id'] or attack['object'] != obj['target_id']
            or attack['data']['square'] != obj['target_square'] or target_piece is None
            or target_piece.color == root.turn or target_piece.piece_type in (chess.PAWN, chess.KING)
            or a['nodes'][0]['relations'].get(obj['target_square'], {}).get('piece_id') != obj['target_id']
            or p['nodes'][1]['relations'].get(obj['target_square'], {}).get('piece_id') != obj['target_id']
            or played_after.attackers(root.turn, target) & played_after.pieces(chess.PAWN, root.turn)):
        return 'wrong_piece_pressure_attack_or_target'
    for key in h.proposition_ids:
        fact = propositions[key]
        line = timelines[fact['timeline_id']]
        if verify(Proposition(**{**fact, 'evidence_ids': tuple(fact['evidence_ids'])}), line):
            return 'piece_pressure_fact_failed_independent_check'
    required = [('legal_move', p['id'], 1, p['events'][0]['moving_piece_id'], p['root_uci']),
                ('legal_move', a['id'], 1, obj['attacker_id'], a['root_uci']),
                ('attacks_piece', a['id'], 1, obj['attacker_id'], obj['target_id'])]
    def has_receipts(items):
        return all(any((propositions[key]['relation'], propositions[key]['timeline_id'],
                        propositions[key]['ply'], propositions[key]['subject'], propositions[key]['object']) == item
                       for key in h.proposition_ids) for item in items)
    if obj['attack_proposition_id'] not in h.proposition_ids or not has_receipts(required):
        return 'piece_pressure_root_receipt_missing'
    if h.status == 'incomplete_hypothesis':
        return None
    if h.status != 'supported_mechanism' or len(obj['root_comparisons']) != 2:
        return 'piece_pressure_support_incomplete'
    epsilon = obj['equivalence_cp']
    all_ids = set()
    allocations = []
    # Geometric reply agreement: the same target moves in both root PVs.
    # We deliberately do not claim the varying destination is a stable fact.
    for pair in obj['root_comparisons']:
        if not _pair_supported(pair, searches, root.fen(), [a['root_uci']], [p['root_uci']], own, epsilon, own):
            return 'piece_pressure_root_score_binding_failed'
        rec = searches[pair['best_search_id']]
        moves = rec['lines'][0]['moves_uci']
        if len(moves) < 2 or chess.Move.from_uci(moves[1]).from_square != target:
            return 'piece_pressure_root_reply_identity_not_stable'
        board = root.copy()
        for raw in moves[:2]:
            move = chess.Move.from_uci(raw)
            if move not in board.legal_moves:
                return 'illegal_piece_pressure_root_reply'
            board.push(move)
        allocations.append(rec['requested_nodes'])
        all_ids.update((pair['best_search_id'], pair['other_search_id']))
    if (allocations[0] > allocations[1]
            or a['search_id'] != obj['root_comparisons'][1]['best_search_id']
            or p['search_id'] != obj['root_comparisons'][1]['other_search_id']):
        return 'piece_pressure_root_allocations_or_primary_binding_failed'
    if len(obj['reply_references']) != 2:
        return 'piece_pressure_reply_references_missing'
    ref_records, allowed = [], {p['id'], a['id']}
    for binding, primary in zip(obj['reply_references'], (p, a)):
        rec, line = searches[binding['search_id']], timelines[binding['timeline_id']]
        if (rec['root_moves'] or rec['fen'] != primary['nodes'][1]['fen']
                or rec['status'] != 'complete_iteration' or not rec['lines']
                or rec['requested_depth'] != 20 or rec['lines'][0].get('depth', 0) < 20
                or rec['lines'][0]['score']['pov'] != own or not canonical(line)
                or line['search_id'] != rec['id'] or line['root_uci'] != primary['root_uci']
                or line['moves_uci'] != [primary['root_uci'], *rec['lines'][0]['moves_uci']][:len(line['moves_uci'])]
                or len(line['events']) < 2):
            return 'piece_pressure_reply_not_completed_unrestricted_reference'
        if primary is a:
            if line['events'][1]['moving_piece_id'] != obj['target_id']:
                return 'piece_pressure_best_reply_does_not_move_target'
        elif line['nodes'][2]['relations'].get(obj['target_square'], {}).get('piece_id') != obj['target_id']:
            return 'piece_pressure_played_reply_also_moves_target'
        required.append(('reaches', line['id'], 2, line['events'][1]['moving_piece_id'], line['events'][1]['destination']))
        ref_records.append(rec)
        allowed.add(line['id'])
        all_ids.add(rec['id'])
    pair = obj['reference_comparison']
    if (pair['best_search_id'] != ref_records[1]['id'] or pair['other_search_id'] != ref_records[0]['id']
            or pair['pov'] != own or pair['best_score'] != _score_for(ref_records[1], own)
            or pair['other_score'] != _score_for(ref_records[0], own)
            or ref_records[0]['requested_nodes'] != ref_records[1]['requested_nodes']
            or comparison(pair['best_score'], pair['other_score'], epsilon) != 'inferior'):
        return 'piece_pressure_deeper_root_comparison_failed'
    staying = sorted(m.uci() for m in after.legal_moves if m.from_square != target)
    if not staying or len(obj['pressure_comparisons']) != 2:
        return 'piece_pressure_counterfactual_missing'
    witnesses = []
    for allocation, pair in zip(allocations, obj['pressure_comparisons']):
        if not _pair_supported(pair, searches, after.fen(), [], staying, opponent, epsilon, own):
            return 'piece_pressure_counterfactual_score_binding_failed'
        best, other = searches[pair['best_search_id']], searches[pair['other_search_id']]
        best_move = chess.Move.from_uci(best['lines'][0]['moves_uci'][0])
        if (best['requested_nodes'] != allocation
                or best_move not in after.legal_moves or best_move.from_square != target):
            return 'piece_pressure_counterfactual_reply_or_allocation_changed'
        witnesses.append(other)
        all_ids.update((best['id'], other['id']))
    witness = timelines[obj['witness_timeline_id']]
    if (common_prefix(witnesses[0]['lines'][0]['moves_uci'], witnesses[1]['lines'][0]['moves_uci']) < 3
            or not canonical(witness) or len(witness['events']) < 4
            or witness['search_id'] != witnesses[1]['id'] or witness['root_uci'] != a['root_uci']
            or witness['moves_uci'][:4] != [a['root_uci'], *witnesses[1]['lines'][0]['moves_uci'][:3]]
            or obj['witness_san'] != witness['moves_san'][:4]):
        return 'piece_pressure_witness_beyond_stability_or_wrong_words'
    take, retake = witness['events'][2:4]
    if (take['moving_piece_id'] != obj['attacker_id'] or take['captured_piece_id'] != obj['target_id']
            or retake['captured_piece_id'] != obj['attacker_id']):
        return 'piece_pressure_witness_capture_join_failed'
    required.extend(('reaches', witness['id'], e['ply'], e['moving_piece_id'], e['destination'])
                    for e in witness['events'][:4])
    required.extend([('captures', witness['id'], 3, obj['attacker_id'], obj['target_id']),
                     ('captures', witness['id'], 4, retake['moving_piece_id'], obj['attacker_id'])])
    allowed.add(witness['id'])
    if any(propositions[key]['timeline_id'] not in allowed for key in h.proposition_ids) or not has_receipts(required):
        return 'piece_pressure_dependency_receipt_missing'
    if not all_ids <= set(h.search_ids):
        return 'piece_pressure_search_receipt_missing'
    return None
