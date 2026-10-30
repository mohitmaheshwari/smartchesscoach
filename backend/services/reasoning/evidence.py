"""General offline evidence: every piece, every available ply, no chosen reason."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import re
import time

import chess

from services.caption_facts import PIECE_VALUE_CP
from services.stored_line_verifier import parse_legal_move, STORED_LINE_VERIFIER_VERSION
from .contracts import ReasoningConfig, fingerprint
from .engine import input_board
from .positional import compare_position_features
from .search import SearchSession, score_order, fingerprint_bytes
from .timeline import build_timeline

VERSION = 'reasoning.position_evidence.v1'
MAX_PLIES = 15  # User-requested maximum, not a shipping search policy.


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(name + ' must be a positive integer')


def _horizon(value):
    _positive(value, 'max_plies')
    if value > MAX_PLIES:
        raise ValueError('this evidence contract allows at most 15 plies')


def scan_node(node: dict, features: dict) -> dict:
    """Derive neutral support/pressure facts; positional labels remain candidates."""
    board = chess.Board(node['fen'])
    relations = node['relations']
    pieces = {}
    for square, state in sorted(relations.items()):
        identity = state['piece_id']
        color = board.color_at(chess.parse_square(square))
        defenders = [relations[s]['piece_id'] for s in state['friendly_defenders']]
        attackers = [relations[s]['piece_id'] for s in state['enemy_attackers']]
        friends, enemies = [], []
        for target in state['attack_squares']:
            if target in relations:
                (friends if board.color_at(chess.parse_square(target)) == color else enemies).append(relations[target]['piece_id'])
        strengths, weaknesses = [], []
        pawn_support = [relations[s]['piece_id'] for s in state['friendly_defenders']
                        if board.piece_type_at(chess.parse_square(s)) == chess.PAWN]
        if pawn_support:
            strengths.append({'kind': 'pawn_supported', 'piece_ids': pawn_support, 'scope': 'geometric'})
        if friends:
            strengths.append({'kind': 'protects_friendly_pieces', 'piece_ids': friends, 'scope': 'geometric'})
        if attackers:
            weaknesses.append({'kind': 'attacked', 'piece_ids': attackers, 'scope': 'geometric_not_proven_lost'})
        if not defenders and state['piece'] != 'king':
            weaknesses.append({'kind': 'undefended', 'scope': 'not_necessarily_capturable'})
        if state['pinned_to_king']:
            weaknesses.append({'kind': 'pinned_to_king'})
        pieces[identity] = {'piece': state['piece'], 'color': 'white' if color else 'black', 'square': square,
            'defended_by': defenders, 'attacked_by': attackers, 'protects': friends, 'attacks': enemies,
            'controlled_squares': list(state['attack_squares']),
            'geometric_reachable_squares': list(state['reachable_squares']),
            'pinned_to_king': state['pinned_to_king'], 'strengths': strengths, 'weaknesses': weaknesses,
            'positional_evidence': []}
    # Bind only unambiguous owner/square or owner/piece descriptions. All
    # evidence, including ambiguous target roles, is also retained board-wide.
    for name, feature in sorted(features.items()):
        for evidence in feature.get('evidence', []):
            owner, square = evidence.get('color'), evidence.get('square')
            if not square:
                description = evidence.get('piece', evidence.get('bishop', ''))
                match = re.fullmatch(r'(pawn|knight|bishop|rook|queen|king) on ([a-h][1-8])', str(description))
                square = match.group(2) if match else None
            state = relations.get(square)
            if state and owner in ('white', 'black'):
                piece = pieces[state['piece_id']]
                if piece['color'] == owner:
                    piece['positional_evidence'].append({'feature': name, 'evidence': deepcopy(evidence),
                                                        'authority': 'candidate_evidence_only'})
    counts = {label: {chess.piece_name(t): len(board.pieces(t, color)) for t in chess.PIECE_TYPES}
              for label, color in [('white', chess.WHITE), ('black', chess.BLACK)]}
    balance = sum((len(board.pieces(t, chess.WHITE)) - len(board.pieces(t, chess.BLACK))) * PIECE_VALUE_CP.get(t, 0)
                  for t in chess.PIECE_TYPES)
    return {'fen': node['fen'], 'side_to_move': node['turn'], 'in_check': node['in_check'],
            'pieces': pieces, 'material': {**counts, 'balance_cp_white': balance}, 'features': deepcopy(features)}


def packet_from_timelines(root, specifications, searches, *, depth, max_plies=MAX_PLIES, provider=None):
    _horizon(max_plies)
    _positive(depth, 'depth')
    records = {r['id']: r for r in searches}
    lines, sources = [], []
    for spec in specifications:
        record = records[spec['search_id']]
        index = spec.get('source_line_index', 0)
        raw = record['lines'][index]['moves_uci']
        moves = spec['moves_uci']
        if spec['role'] not in ('played', 'alternative') or spec['origin'] not in ('root', 'reply'):
            raise ValueError('unknown evidence branch role/origin')
        if not moves:
            raise ValueError('empty evidence continuation')
        after = root.copy()
        try:
            after.push_uci(moves[0])
        except (ValueError, AssertionError) as exc:
            raise ValueError('illegal leading move') from exc
        if spec['origin'] == 'root':
            if record['fen'] != root.fen() or moves != raw or (record['root_moves'] and moves[0] not in record['root_moves']):
                raise ValueError('wrong root search binding')
        elif record['fen'] != after.fen() or record['root_moves'] or moves[1:] != raw:
            raise ValueError('reply must be an unrestricted search at the correct node')
        line = build_timeline(root, moves, record['id'], max_plies)
        lines.append(line)
        sources.append({**spec, 'source_line_index': index, 'original_plies': len(moves)})
    if not lines:
        raise ValueError('no available searched line to replay')
    report = compare_position_features(lines, max_plies=max_plies, provider=provider)
    feature_index = {(s['timeline_id'], s['ply']): s['features'] for s in report['snapshots']}
    states, by_node, branches, by_moves = [], {}, [], {}
    for line, source in zip(lines, sources):
        sequence = tuple(line['moves_uci'])
        source_ref = {'search_id': line['search_id'], 'origin': source['origin'],
                      'source_line_index': source['source_line_index']}
        if sequence in by_moves:
            branch = by_moves[sequence]
            if branch['role'] != source['role']:
                raise ValueError('identical moves assigned incompatible roles')
            branch['sources'].append(source_ref)
            continue
        ids = []
        for ply, node in enumerate(line['nodes']):
            if node['id'] not in by_node:
                state = scan_node(node, feature_index[line['id'], ply])
                state['id'] = 'N' + str(len(states))
                # Canonical board IDs bind position/history in the full saved
                # artifact; compact aliases are sufficient for model citations.
                state['canonical_node_id'] = node['id']
                states.append(state); by_node[node['id']] = state
            ids.append(by_node[node['id']]['id'])
        events = [{**e, 'actor_color': line['nodes'][e['ply'] - 1]['turn']} for e in line['events']]
        end = chess.Board(line['nodes'][-1]['fen'])
        stop = 'terminal' if end.is_game_over(claim_draw=False) else 'projection_horizon' if source['original_plies'] > max_plies else 'pv_end'
        branch = {'id': 'B' + str(len(branches) + 1), 'role': source['role'], 'sources': [source_ref],
                  'moves_uci': line['moves_uci'], 'moves_san': line['moves_san'], 'state_ids': ids,
                  'end_state_id': ids[-1], 'material_at_end': deepcopy(by_node[line['nodes'][-1]['id']]['material']),
                  'events': events, 'available_plies': len(events), 'stop_reason': stop, 'exhaustive': False}
        branches.append(branch); by_moves[sequence] = branch
    incomplete = [r['id'] for r in searches if r['status'] != 'complete_iteration' or not r['lines']
                  or min(l.get('depth', 0) for l in r['lines']) < depth]
    package = Path(__file__).parent
    source_files = [*sorted(package.glob('*.py')), package.parent / 'stored_line_verifier.py']
    return {'schema_version': VERSION, 'status': 'partial' if incomplete else 'complete',
            'input': {'fen_before': root.fen()}, 'settings': {'max_plies': max_plies, 'requested_depth': depth},
            'initial_state_id': states[0]['id'], 'states': states, 'branches': branches, 'searches': deepcopy(searches),
            'search_quality': {'incomplete_search_ids': incomplete, 'all_moves_forced': False,
                               'comparison_scope': 'best_searched_alternative_not_exhaustive'},
            'provider': report['provider'], 'feature_authority': report['authority'],
            'feature_value_pov': report['value_pov'], 'feature_value_units': report['value_units'],
            'reproducibility': {'replay_version': STORED_LINE_VERIFIER_VERSION,
                'source_hashes': {p.name: fingerprint_bytes(p) for p in source_files}},
            'review': {'prose_factuality': 'not_reviewed', 'explanatory_relevance': 'not_reviewed'}}


def build_position_evidence(fen_before, played_move=None, *, fen_after=None, history=None,
                            config: ReasoningConfig, depth, max_plies=MAX_PLIES, provider=None,
                            session_factory=None):
    started = time.perf_counter()
    _horizon(max_plies); _positive(depth, 'depth')
    root, history_status = input_board(fen_before, history)
    normalized_after = None
    if fen_after is not None:
        final, _ = input_board(fen_after, None)
        normalized_after = final.fen()
    if played_move is None:
        if normalized_after is None:
            raise ValueError('a played move or fen_after is required')
        candidates = []
        for move in root.legal_moves:
            board = root.copy(); board.push(move)
            if board.fen() == normalized_after:
                candidates.append(move)
        if len(candidates) != 1:
            raise ValueError('FEN pair does not identify one legal move')
        played = candidates[0]
    else:
        played = parse_legal_move(root, played_move)
        if played is None:
            raise ValueError('illegal played move')
    after = root.copy(); after.push(played)
    if normalized_after is not None and after.fen() != normalized_after:
        raise ValueError('played move does not match fen_after')
    session = (session_factory or SearchSession)(config, root.turn,
        fingerprint([root.root().fen(), [m.uci() for m in root.move_stack]]))
    played_record = session.query(root, 'evidence_played_root', roots=[played], nodes=config.stability_nodes, depth=depth)
    ranking = session.query(root, 'evidence_root_ranking', width=config.rank_width, depth=depth)
    specs = []
    if played_record.lines:
        specs.append({'role': 'played', 'origin': 'root', 'search_id': played_record.id,
                      'moves_uci': played_record.lines[0]['moves_uci']})
    ranked = [(l, i) for i, l in enumerate(ranking.lines)]
    best_pair = max(ranked, key=lambda item: score_order(item[0]['score'])) if ranked else None
    alternative = None
    if best_pair and best_pair[0]['root_uci'] != played.uci():
        if not played_record.lines or score_order(best_pair[0]['score']) > score_order(played_record.lines[0]['score']):
            alternative = chess.Move.from_uci(best_pair[0]['root_uci'])
            record = session.query(root, 'evidence_alternative_root', roots=[alternative], nodes=config.stability_nodes, depth=depth)
            if record.lines:
                specs.append({'role': 'alternative', 'origin': 'root', 'search_id': record.id,
                              'moves_uci': record.lines[0]['moves_uci']})
            else:
                specs.append({'role': 'alternative', 'origin': 'root', 'search_id': ranking.id,
                              'source_line_index': best_pair[1], 'moves_uci': best_pair[0]['moves_uci']})
    for role, move in [('played', played), ('alternative', alternative)]:
        if move is None:
            continue
        board = root.copy(); board.push(move)
        if board.is_game_over(claim_draw=False):
            continue
        record = session.query(board, 'evidence_' + role + '_reply', nodes=config.stability_nodes, depth=depth)
        if record.lines:
            specs.append({'role': role, 'origin': 'reply', 'search_id': record.id,
                          'moves_uci': [move.uci(), *record.lines[0]['moves_uci']]})
    if not specs:
        raise ValueError('search budget produced no legal continuation')
    packet = packet_from_timelines(root, specs, [r.document() for r in session.records],
                                   depth=depth, max_plies=min(max_plies, config.max_plies), provider=provider)
    packet['input'].update(played_uci=played.uci(), played_san=root.san(played), fen_after=after.fen(),
                           history_status=history_status)
    packet['settings']['search_config'] = asdict(config)
    packet['reproducibility']['search'] = session.document()
    packet['runtime'] = {'wall_ms': round(1000 * (time.perf_counter() - started), 3),
                         'query_count': session.executed_queries, 'requested_engine_nodes': session.requested_nodes,
                         'actual_engine_nodes': sum(r.actual_nodes for r in session.records)}
    return packet


def model_packet(packet):
    """Lossless state deltas. No salience filter or explanation is supplied."""
    states = {s['id']: s for s in packet['states']}
    first = packet['initial_state_id']
    parents = {}
    for branch in packet['branches']:
        for parent, child in zip(branch['state_ids'], branch['state_ids'][1:]):
            parents.setdefault(child, parent)
    changes = []
    for state in packet['states']:
        if state['id'] == first:
            continue
        before = states[parents[state['id']]]
        piece_changes, relations = {}, {}
        for key in sorted(before['pieces'].keys() | state['pieces'].keys()):
            old, new = before['pieces'].get(key), state['pieces'].get(key)
            if old == new:
                continue
            piece_changes[key] = None if new is None else {k: deepcopy(v) for k, v in new.items() if old is None or old.get(k) != v}
            if old is not None and new is not None:
                relations[key] = {'removed_controls': sorted(set(old['controlled_squares']) - set(new['controlled_squares'])),
                                  'added_controls': sorted(set(new['controlled_squares']) - set(old['controlled_squares']))}
        changes.append({'parent_id': before['id'], 'fields': {k: deepcopy(v) for k, v in state.items()
                         if k not in ('pieces', 'features') and before.get(k) != v},
                        'piece_changes': piece_changes, 'relationship_changes': relations,
                        'feature_changes': {k: deepcopy(v) for k, v in state['features'].items() if before['features'].get(k) != v}})
    coverage = {}
    for branch in packet['branches']:
        for source in branch['sources']:
            offset = 0 if source['origin'] == 'root' else 1
            coverage[source['search_id'], source['source_line_index']] = branch['moves_san'][offset:]
    searches = []
    for record in packet['searches']:
        lines = []
        for index, line in enumerate(record['lines']):
            san = coverage.get((record['id'], index))
            if san is None:
                board = chess.Board(record['fen'])
                leading = chess.Move.from_uci(line['moves_uci'][0])
                san = [board.san(leading)] if leading in board.legal_moves else []
            lines.append({'depth': line.get('depth'), 'score': deepcopy(line['score']),
                          'root_uci': line['moves_uci'][0], 'moves_san': list(san)})
        searches.append({**{k: deepcopy(record[k]) for k in ('id', 'purpose', 'fen', 'root_moves', 'requested_depth', 'status')},
                         'lines': lines})
    # No local engine path, credentials, code, previous captions or selected
    # mechanism objects enter this model-facing view.
    return {'schema_version': VERSION + '.model.v1', 'input': deepcopy(packet['input']),
            'settings': {k: v for k, v in packet['settings'].items() if k != 'search_config'},
            'initial': deepcopy(states[first]), 'state_changes': changes,
            'branches': [{**{k: deepcopy(b[k]) for k in ('id', 'role', 'sources', 'state_ids', 'moves_san',
                         'end_state_id', 'material_at_end', 'available_plies', 'stop_reason', 'exhaustive')},
                         'events': [{k: deepcopy(e[k]) for k in ('ply', 'move_san', 'actor_color', 'moving_piece_id',
                            'captured_piece_id', 'captured_square', 'gave_check', 'checkmate', 'legal_reply_count',
                            'promotion_piece')} for e in b['events']]} for b in packet['branches']],
            'searches': searches,
            'search_quality': deepcopy(packet['search_quality']),
            'semantics': {'relations': 'geometric; an attacked or undefended piece is not automatically lost',
                          'features': 'untrusted positional candidates; raw values are White POV, not causal centipawns',
                          'lines': 'separate searched examples; later moves are not necessarily forced',
                          'state_changes': 'apply changed piece fields and feature values to parent state; null removes a captured piece',
                          'material': 'exact piece counts at each state; balance_cp_white uses shared piece values, not engine evaluation'}}
