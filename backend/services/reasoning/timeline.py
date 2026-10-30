"""Branch views of canonical legal replay; unchanged relationships stay available."""
from __future__ import annotations

from dataclasses import asdict
import chess

from services.stored_line_verifier import relationship_snapshot, replay_stored_line
from .contracts import Proposition, fingerprint


def snapshot(board: chess.Board, relations: dict, node_id: str) -> dict:
    return {"id": node_id, "fen": board.fen(), "turn": "white" if board.turn else "black",
            "relations": {sq: state.contract_dict() for sq, state in sorted(relations.items())},
            "legal_moves": sorted(m.uci() for m in board.legal_moves),
            "legal_king_moves": sorted(m.uci() for m in board.legal_moves if board.piece_type_at(m.from_square) == chess.KING),
            "in_check": board.is_check()}


def build_timeline(root: chess.Board, moves_uci: list[str], search_id: str, max_plies: int) -> dict:
    if not moves_uci:
        raise ValueError("timeline requires a leading move")
    projected = moves_uci[:max_plies]
    replay = replay_stored_line(root, projected[0], projected, include_events=True)
    if not replay.complete or len(replay.events) != len(projected):
        raise ValueError("timeline has an illegal or post-terminal suffix")
    root_identity = fingerprint([root.fen(), [m.uci() for m in root.move_stack]])
    identity = fingerprint([root_identity, projected, search_id])
    relations = relationship_snapshot(root)
    board = root.copy()
    nodes = [snapshot(board, relations, root_identity)]
    for index, event in enumerate(replay.events):
        board.push_uci(event.move_uci)
        for change in event.relation_changes:
            relations.pop(change.square, None)
            if change.after is not None:
                relations[change.square] = change.after
        nodes.append(snapshot(board, relations, fingerprint([root_identity, projected[:index + 1]])))
    return {"id": identity, "root_uci": projected[0], "search_id": search_id,
            "moves_uci": projected, "moves_san": list(replay.replayed_san),
            "events": [dict(e.contract_dict()) for e in replay.events], "nodes": nodes,
            "net_material_cp": replay.net_material_gain_cp, "legal_replay_complete": True,
            "stop_reason": "projection_horizon" if len(moves_uci) > max_plies else "engine_pv_end",
            "exhaustive": False}


def atom(timeline: dict, ply: int, subject: str, relation: str, obj: str, **data) -> Proposition:
    actor = timeline["nodes"][ply]["turn"] if relation == "only_legal_reply" else timeline["nodes"][ply - 1]["turn"] if ply else timeline["nodes"][0]["turn"]
    fields = [subject, relation, obj, timeline["id"], ply, actor, data]
    return Proposition(fingerprint(fields), subject, relation, obj, timeline["id"], ply, actor,
                       (timeline["search_id"], timeline["nodes"][ply]["id"]), data)


def event_facts(timeline: dict) -> list[Proposition]:
    facts = []
    for event in timeline["events"]:
        ply = event["ply"]
        mover = event["moving_piece_id"]
        facts.append(atom(timeline, ply, mover, "reaches", event["destination"],
                          move=event["move_san"], piece=event["moving_piece"]))
        if ply == 1:
            facts.append(atom(timeline, ply, mover, "legal_move", event["move_uci"],
                              move=event["move_san"], piece=event["moving_piece"], square=event["destination"]))
        if event["captured_piece_id"]:
            facts.append(atom(timeline, ply, mover, "captures", event["captured_piece_id"],
                              square=event["captured_square"], move=event["move_san"], piece=event["moving_piece"],
                              captured_piece=event["captured_piece"]))
        if event["gave_check"]:
            facts.append(atom(timeline, ply, mover, "gives_check", "black" if timeline["nodes"][ply - 1]["turn"] == "white" else "white",
                              move=event["move_san"], piece=event["moving_piece"]))
        if event["checkmate"]:
            facts.append(atom(timeline, ply, mover, "checkmates", timeline["nodes"][ply]["turn"], move=event["move_san"]))
        if event["promotion_piece"]:
            facts.append(atom(timeline, ply, mover, "promotes_to", event["promotion_piece"], square=event["destination"]))
        if event["legal_reply_count"] == 1:
            facts.append(atom(timeline, ply, event["forced_reply_uci"], "only_legal_reply", timeline["nodes"][ply]["id"],
                              move=event["forced_reply_san"]))
        before, after = chess.Board(event["fen_before"]), chess.Board(event["fen_after"])
        origin_square, destination_square = chess.parse_square(event["origin"]), chess.parse_square(event["destination"])
        for square in sorted(set(after.attacks(destination_square)) - set(before.attacks(origin_square))):
            target = after.piece_at(square)
            if target is not None and target.color != before.turn and not event["promotion_piece"]:
                target_state = timeline["nodes"][ply]["relations"][chess.square_name(square)]
                facts.append(atom(timeline, ply, mover, "attacks_piece", target_state["piece_id"],
                                  square=chess.square_name(square), move=event["move_san"],
                                  piece=event["moving_piece"], target_piece=chess.piece_name(target.piece_type)))
        if before.is_castling(chess.Move.from_uci(event["move_uci"])):
            facts.append(atom(timeline, ply, mover, "castles", event["destination"], move=event["move_san"]))
        if ply == 1:
            # Geometric changes are candidates, including empty target squares.
            source, target = chess.parse_square(event["origin"]), chess.parse_square(event["destination"])
            prior, current = set(before.attacks(source)), set(after.attacks(target))
            for relation, squares in (("coverage_gained", current - prior), ("coverage_abandoned", prior - current)):
                for square in sorted(squares):
                    facts.append(atom(timeline, ply, mover, relation, chess.square_name(square)))
            for change in event["line_geometry_changes"]:
                if change["kind"] != "opened":
                    continue
                state = timeline["nodes"][0]["relations"][change["slider_square"]]
                for square in change["changed_squares"]:
                    slider = chess.parse_square(change["slider_square"])
                    target_square = chess.parse_square(square)
                    if target_square in before.attacks(slider) or target_square not in after.attacks(slider):
                        continue  # Newly movable onto a vacated friendly square is not newly gained coverage.
                    facts.append(atom(timeline, ply, state["piece_id"], "opens_line", square,
                                      slider_square=change["slider_square"]))
    return facts


def as_documents(facts):
    return [asdict(p) for p in facts]
