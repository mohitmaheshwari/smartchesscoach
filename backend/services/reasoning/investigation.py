"""Budgeted alternating legal objective search with three-valued outcomes."""
from __future__ import annotations

import chess
from services.stored_line_verifier import relationship_snapshot, replay_stored_line

from .search import comparison


def actor_score(score: dict, board: chess.Board, pov: chess.Color) -> dict:
    return score if board.turn == pov else {**score, "value": -score["value"], "pov": "white" if board.turn else "black"}


def investigate(root: chess.Board, first: chess.Move, objective: dict, session) -> dict:
    """Witness a plan against searched adequate replies, never an exhaustive proof.

    Own nodes are OR; opponent nodes are AND over explicitly admitted replies.
    An unresolved horizon is unknown. Every edge is legal and every attempted
    own plan is compared with that node's unrestricted engine choice.
    """
    root_color = root.turn
    expanded = 0
    traces, witnesses = [], []
    board = root.copy()
    board.push(first)

    identities = {}

    def lineage(path):
        key = tuple(path)
        if key not in identities:
            states = relationship_snapshot(root)
            replay = replay_stored_line(root, path[0], path, include_events=True)
            for event in replay.events:
                for change in event.relation_changes:
                    states.pop(change.square, None)
                    if change.after is not None:
                        states[change.square] = change.after
            identities[key] = {sq: state.piece_id for sq, state in states.items()}
        return identities[key]

    def goal(before, move, path):
        if before.turn != root_color:
            return False
        if objective["kind"] == "castle":
            return before.is_castling(move) and chess.square_name(move.to_square) == objective["square"]
        if objective["kind"] == "reach":
            return chess.square_name(move.to_square) == objective["square"] and lineage(path).get(chess.square_name(move.from_square)) == objective["piece_id"]
        return False

    def walk(position, path, depth):
        nonlocal expanded
        if depth >= session.config.max_plies or expanded >= session.config.max_expanded_nodes:
            return {"status": "unknown", "reason": "legal_expansion_or_ply_budget"}
        if position.is_game_over(claim_draw=False):
            return {"status": "counterexample", "reason": "terminal_without_objective"}
        if objective["kind"] == "castle":
            kingside = chess.square_file(chess.parse_square(objective["square"])) > 4
            rights = position.has_kingside_castling_rights(root_color) if kingside else position.has_queenside_castling_rights(root_color)
            if not rights:
                return {"status": "counterexample", "reason": "castling_right_lost"}
        if objective["kind"] == "reach" and objective["piece_id"] not in lineage(path).values():
            return {"status": "counterexample", "reason": "route_piece_captured"}
        if not session.can_query():
            return {"status": "unknown", "reason": "search_budget"}
        expanded += 1
        own = position.turn == root_color
        ranking = session.query(position, "objective_own_ranking" if own else "objective_defences",
                                width=1 if own else session.config.reply_width)
        if not ranking.lines:
            return {"status": "unknown", "reason": ranking.stop_reason}
        best_score = actor_score(ranking.lines[0]["score"], position, session.pov)
        ranked = [chess.Move.from_uci(line["root_uci"]) for line in ranking.lines]
        legal = sorted(position.legal_moves, key=lambda m: m.uci())
        if own:
            candidates = [m for m in legal if goal(position, m, path)] + ranked
            if objective["kind"] == "castle":
                king = position.king(root_color)
                target = chess.parse_square(objective["square"])
                rook = chess.square(7 if chess.square_file(target) > 4 else 0, chess.square_rank(king))
                blockers = chess.SquareSet(chess.between(king, rook))
                candidates += [m for m in legal if m.from_square in blockers and m.to_square not in blockers]
            else:
                candidates += [m for m in legal if position.gives_check(m) or position.is_capture(m)]
        else:
            candidates = ranked + [m for m in legal if position.gives_check(m) or position.is_capture(m) or m.promotion]
        candidates = list(dict.fromkeys(candidates))
        children, unknown, admitted = [], False, 0
        for move in candidates:
            if not session.can_query():
                unknown = True
                break
            restricted = session.query(position, "objective_action", roots=[move])
            if not restricted.lines:
                unknown = True
                continue
            quality = comparison(best_score, actor_score(restricted.lines[0]["score"], position, session.pov), session.config.equivalence_cp)
            if quality not in ("equivalent", "same_mate_class", "better"):
                children.append({"move": move.uci(), "status": "excluded_by_search_comparison", "comparison": quality,
                                 "search_id": restricted.id})
                continue
            admitted += 1
            step = {"move": move.uci(), "actor": "white" if position.turn else "black", "search_id": restricted.id}
            if goal(position, move, path):
                witnesses.append({"moves_uci": path + [move.uci()], "search_id": restricted.id})
                child = {**step, "status": "supported_scope", "reason": "goal_witnessed"}
            else:
                after = position.copy()
                after.push(move)
                child = {**step, **walk(after, path + [move.uci()], depth + 1)}
            children.append(child)
            if own and child["status"] == "supported_scope":
                traces.append({"fen": position.fen(), "actor": "own", "search_id": ranking.id,
                               "legal_moves": [m.uci() for m in legal], "searched_moves": [c["move"] for c in children],
                               "omitted_moves": [m.uci() for m in legal if m.uci() not in {c["move"] for c in children}]})
                return {"status": "supported_scope", "choice": move.uci(), "children": children}
            if not own and child["status"] == "counterexample":
                return {"status": "counterexample", "reply": move.uci(), "children": children}
            unknown |= child["status"] == "unknown"
        searched = {c["move"] for c in children}
        omitted = [m.uci() for m in legal if m.uci() not in searched]
        traces.append({"fen": position.fen(), "actor": "own" if own else "opponent", "search_id": ranking.id,
                       "legal_moves": [m.uci() for m in legal], "searched_moves": sorted(searched), "omitted_moves": omitted})
        status = "unknown" if unknown or not admitted or (own and omitted) else ("counterexample" if own else "supported_scope")
        return {"status": status, "children": children, "omitted_legal_moves": omitted}

    tree = walk(board, [first.uci()], 1)
    return {"objective": objective, "root_uci": first.uci(), "status": tree["status"], "policy": tree,
            "witnesses": witnesses, "node_scopes": traces, "expanded_nodes": expanded,
            "strength": "searched_adequate_replies_only", "exhaustive": False}
