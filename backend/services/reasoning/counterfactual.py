"""Generic move deletion: locate search dependencies without naming a motif."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import time

import chess

from services.stored_line_verifier import parse_legal_move
from .contracts import fingerprint
from .engine import input_board
from .search import SearchSession, fingerprint_bytes
from .timeline import build_timeline, event_facts


def _score_for(score, color):
    return {'kind': score['kind'], 'value': score['value'] if score['pov'] == ('white' if color else 'black')
            else -score['value'], 'pov': 'white' if color else 'black'}


def _usable(record, board, roots, depth):
    if (record.status != 'complete_iteration' or record.fen != board.fen()
            or set(record.root_moves) != {m.uci() for m in roots} or not record.lines):
        return False
    line = record.lines[0]
    if line.get('depth', 0) < depth or line['score'].get('pov') not in ('white', 'black'):
        return False
    moves = line.get('moves_uci', [])
    if not moves or line.get('root_uci') != moves[0] or (roots and moves[0] not in record.root_moves):
        return False
    walker = board.copy()
    for raw in moves:
        move = parse_legal_move(walker, raw)
        if move is None:
            return False
        walker.push(move)
    return True


def probe_reply_dependency(board, session, *, depth, exclude_move=None):
    """Compare the same legal node with/without one move at explicit budgets.

    Positive CP drop is a measured dependency for the actor at this node.
    Mate scores stay typed. A PV, a score drop or an attack is not a mechanism.
    """
    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 1:
        raise ValueError('depth must be a positive integer')
    legal = sorted(board.legal_moves, key=lambda m: m.uci())
    nominated = parse_legal_move(board, exclude_move) if exclude_move is not None else None
    if exclude_move is not None and nominated is None:
        raise ValueError('excluded move must be legal at the investigated node')
    result = {'status': 'not_searched', 'fen': board.fen(), 'actor': 'white' if board.turn else 'black',
              'legal_moves': [m.uci() for m in legal], 'excluded_uci': None, 'excluded_san': None,
              'measurements': [], 'signal': 'unknown', 'mechanism_established': False,
              'scope': 'searched_move_dependency_not_a_chess_mechanism', 'exhaustive': False}
    if board.is_game_over(claim_draw=False):
        result['status'] = 'terminal'
        return result
    if len(legal) == 1:
        result.update(status='only_legal_reply', excluded_uci=legal[0].uci(), excluded_san=board.san(legal[0]))
        return result
    allocations = list(dict.fromkeys([session.config.nodes, session.config.stability_nodes]))
    baseline = [session.query(board, 'reply_dependency_unrestricted', nodes=n, depth=depth) for n in allocations]
    chosen = next((r for r in reversed(baseline) if _usable(r, board, [], depth)), None)
    if nominated is None and chosen is None:
        result.update(status='partial', baseline_search_ids=[r.id for r in baseline])
        return result
    nominated = nominated or chess.Move.from_uci(chosen.lines[0]['root_uci'])
    allowed = [m for m in legal if m != nominated]
    result.update(excluded_uci=nominated.uci(), excluded_san=board.san(nominated),
                  selection='nominated_legal_move' if exclude_move is not None else 'deepest_usable_unrestricted_choice')
    for allocation, unrestricted in zip(allocations, baseline):
        without = session.query(board, 'reply_dependency_without_move', roots=allowed, nodes=allocation, depth=depth)
        usable = _usable(unrestricted, board, [], depth) and _usable(without, board, allowed, depth)
        a = _score_for(unrestricted.lines[0]['score'], board.turn) if usable else None
        b = _score_for(without.lines[0]['score'], board.turn) if usable else None
        result['measurements'].append({'nodes_per_query': allocation, 'requested_depth': depth,
            'status': 'measured' if usable else 'partial',
            'baseline_search_id': unrestricted.id, 'without_search_id': without.id,
            'baseline_score': a, 'without_score': b,
            'excluded_was_baseline_choice': unrestricted.lines[0]['root_uci'] == nominated.uci() if usable else None,
            'drop_cp': a['value'] - b['value'] if usable and a['kind'] == b['kind'] == 'cp' else None,
            'replacement_uci': without.lines[0]['root_uci'] if usable else None})
    result['status'] = 'measured' if all(m['status'] == 'measured' for m in result['measurements']) else 'partial'
    if result['status'] == 'measured':
        drops = [m['drop_cp'] for m in result['measurements']]
        result['signal'] = ('typed_scores_only' if None in drops else
            'search_reversal' if any(d < 0 for d in drops) else
            'excluded_move_not_baseline_choice' if not all(m['excluded_was_baseline_choice'] for m in result['measurements']) else
            'positive_at_all_allocations' if all(d > 0 for d in drops) else 'no_consistent_positive_drop')
    return result


def locate_reply_dependency(fen, played_move, *, config, depth, continuation=None,
                            exclude_move=None, history=None, session_factory=None):
    """Investigate the immediate reply or an explicitly supplied legal later node."""
    started = time.perf_counter()
    root, history_status = input_board(fen, history)
    path = [played_move, *(continuation or [])]
    board = root.copy()
    moves = []
    for raw in path:
        move = parse_legal_move(board, raw)
        if move is None:
            raise ValueError('illegal move in investigated prefix')
        moves.append(move.uci())
        board.push(move)
    if len(moves) >= config.max_plies:
        raise ValueError('prefix leaves no room for a reply within the recorded horizon')
    session = (session_factory or SearchSession)(config, root.turn,
        fingerprint([root.root().fen(), [m.uci() for m in root.move_stack]]))
    probe = probe_reply_dependency(board, session, depth=depth, exclude_move=exclude_move)
    timelines, seen = [], set()
    for record in session.records:
        if not record.lines or record.id in seen:
            continue
        seen.add(record.id)
        line = build_timeline(root, [*moves, *record.lines[0]['moves_uci']], record.id, config.max_plies)
        line['scope'] = 'counterfactual_root_restriction' if record.root_moves else 'unrestricted_at_investigated_node'
        line['source_query'] = {'start_ply': len(moves), 'root_moves': record.root_moves}
        line['facts'] = [asdict(p) for p in event_facts(line)]
        timelines.append(line)
    return {'schema_version': 'reasoning.reply_dependency.v1', 'input': {'fen': root.fen(),
                'played_uci': moves[0], 'continuation_uci': moves[1:], 'history_status': history_status},
            'probe': probe, 'timelines': timelines, 'searches': [r.document() for r in session.records],
            'reproducibility': {**session.document(), 'locator_source_sha256': fingerprint_bytes(Path(__file__))},
            'runtime': {'wall_ms': round(1000 * (time.perf_counter() - started), 3),
                        'query_count': session.executed_queries, 'requested_nodes': session.requested_nodes,
                        'actual_nodes': sum(r.actual_nodes for r in session.records)},
            'coaching': None, 'review': 'dependency_only_requires_board_mechanism_and_relevance_review'}
