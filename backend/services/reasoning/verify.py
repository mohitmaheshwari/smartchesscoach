"""Independent board/rule checks for structured propositions, never word matching."""
from __future__ import annotations

import chess
from .contracts import Proposition


def verify(p: Proposition, timeline: dict) -> str | None:
    try:
        return _verify(p, timeline)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return "malformed_claim_or_evidence"


def _verify(p: Proposition, timeline: dict) -> str | None:
    if p.evidence_class != "exact_board_fact" or p.quantifier != "at_this_node" or not p.polarity:
        return "unsupported_strength_or_polarity"
    if p.timeline_id != timeline["id"] or not 0 < p.ply <= len(timeline["events"]):
        return "wrong_timeline_or_ply"
    event = timeline["events"][p.ply - 1]
    before = chess.Board(timeline["nodes"][p.ply - 1]["fen"])
    move = chess.Move.from_uci(event["move_uci"])
    if move not in before.legal_moves:
        return "illegal_move"
    expected_turn = not before.turn if p.relation == "only_legal_reply" else before.turn
    actor = "white" if expected_turn else "black"
    if p.actor != actor:
        return "wrong_actor"
    identities = timeline["nodes"][p.ply - 1]["relations"]
    source = identities.get(chess.square_name(move.from_square), {})
    after = before.copy()
    after.push(move)
    if after.fen() != timeline["nodes"][p.ply]["fen"]:
        return "wrong_after_position"
    if p.evidence_ids != (timeline["search_id"], timeline["nodes"][p.ply]["id"]):
        return "wrong_evidence_reference"
    if p.relation == "only_legal_reply":
        replies = list(after.legal_moves)
        return None if len(replies) == 1 and replies[0].uci() == p.subject and p.object == timeline["nodes"][p.ply]["id"] and after.san(replies[0]) == p.data.get("move") else "not_the_only_legal_reply"
    if p.relation == "opens_line":
        square = chess.parse_square(p.data["slider_square"])
        state = identities.get(p.data["slider_square"], {})
        target = chess.parse_square(p.object)
        ok = (p.ply == 1 and state.get("piece_id") == p.subject and before.piece_at(square) == after.piece_at(square)
              and target in after.attacks(square) and target not in before.attacks(square))
        return None if ok else "line_not_opened"
    if p.subject != source.get("piece_id"):
        return "wrong_piece_identity"
    if p.relation == "legal_move":
        ok = p.ply == 1 and p.object == move.uci() and p.data.get("square") == chess.square_name(move.to_square)
    elif p.relation == "reaches":
        ok = p.object == chess.square_name(move.to_square)
    elif p.relation == "captures":
        square = move.to_square + (-8 if before.turn else 8) if before.is_en_passant(move) else move.to_square
        victim = identities.get(chess.square_name(square), {})
        ok = (before.is_capture(move) and victim.get("piece_id") == p.object
              and p.data.get("square") == chess.square_name(square)
              and p.data.get("captured_piece") == chess.piece_name(before.piece_type_at(square)))
    elif p.relation == "gives_check":
        ok = before.gives_check(move) and p.object == ("white" if after.turn else "black")
    elif p.relation == "attacks_piece":
        square = chess.parse_square(p.data["square"])
        victim = after.piece_at(square)
        state = timeline["nodes"][p.ply]["relations"].get(p.data["square"], {})
        ok = (victim is not None and victim.color != before.turn and state.get("piece_id") == p.object
              and square in after.attacks(move.to_square) and square not in before.attacks(move.from_square)
              and p.data.get("target_piece") == chess.piece_name(victim.piece_type))
    elif p.relation == "checkmates":
        ok = after.is_checkmate() and p.object == ("white" if after.turn else "black")
    elif p.relation == "promotes_to":
        ok = move.promotion is not None and chess.piece_name(move.promotion) == p.object and p.data.get("square") == chess.square_name(move.to_square)
    elif p.relation == "castles":
        ok = before.is_castling(move) and p.object == chess.square_name(move.to_square)
    elif p.relation in ("coverage_gained", "coverage_abandoned", "coverage_maintained"):
        square = chess.parse_square(p.object)
        prior, current = square in before.attacks(move.from_square), square in after.attacks(move.to_square)
        ok = {"coverage_gained": not prior and current, "coverage_abandoned": prior and not current,
              "coverage_maintained": prior and current}[p.relation]
    elif p.relation == "clears_castling_path":
        king = before.king(before.turn)
        target = chess.parse_square(p.object)
        kingside = chess.square_file(target) > chess.square_file(king)
        rights = before.has_kingside_castling_rights(before.turn) if kingside else before.has_queenside_castling_rights(before.turn)
        rook = chess.square(7 if kingside else 0, chess.square_rank(king))
        path = chess.SquareSet(chess.between(king, rook))
        ok = (p.ply == 1 and rights and move.from_square in path
              and move.to_square not in path
              and p.data.get("cleared_square") == chess.square_name(move.from_square)
              and (after.has_kingside_castling_rights(before.turn) if kingside else after.has_queenside_castling_rights(before.turn)))
    elif p.relation == "pawn_transforms":
        ok = before.piece_type_at(move.from_square) == chess.PAWN and p.object == chess.square_name(move.to_square)
    else:
        return "unknown_relation"
    if p.data.get("move") is not None and p.data["move"] != before.san(move):
        return "wrong_move_or_timing"
    if p.data.get("piece") is not None and p.data["piece"] != chess.piece_name(before.piece_type_at(move.from_square)):
        return "wrong_piece_type"
    return None if ok else "relationship_not_true_at_this_event"


def verify_dependencies(hypothesis, propositions: dict, timelines: dict) -> str | None:
    """Check composed links as relations over the accepted facts and legal events.

    This validates a demonstrated dependency, not necessity or attribution of
    an engine evaluation. Those stronger readings remain unresolved.
    """
    try:
        facts = [propositions[key] for key in hypothesis.proposition_ids]
        if any(timelines[p["timeline_id"]]["root_uci"] != hypothesis.root_uci for p in facts if p["relation"] != "captures" or hypothesis.operation != "PREVENT"):
            return "incompatible_root_branches"
        for edge in hypothesis.dependencies:
            if edge["kind"] in ("opened_capture_line", "opened_entry_line"):
                outcome = propositions[edge["outcome_id"]]
                for key in edge["premise_ids"]:
                    premise = propositions[key]
                    target = outcome["data"]["square"] if outcome["relation"] == "captures" else outcome["object"]
                    if not (premise["relation"] == "opens_line" and premise["subject"] == outcome["subject"]
                            and premise["object"] == target and premise["ply"] < outcome["ply"]
                            and premise["timeline_id"] == outcome["timeline_id"]):
                        return "incompatible_open_line_link"
            elif edge["kind"] == "legal_event_order":
                outcome = propositions[edge["after"]]
                if any(propositions[key]["ply"] >= outcome["ply"] or propositions[key]["timeline_id"] != outcome["timeline_id"] for key in edge["before"]):
                    return "wrong_sequence_timing"
            elif edge["kind"] == "same_piece_route":
                line = timelines[hypothesis.objective["timeline_id"]]
                piece_id = edge.get("piece_id", hypothesis.objective.get("piece_id"))
                route = [e for e in line["events"] if e["moving_piece_id"] == piece_id]
                if not route or route[0]["ply"] != 1:
                    return "unconnected_piece_route"
                if "events" in edge and any(line["events"][ply - 1]["moving_piece_id"] != piece_id for ply in edge["events"]):
                    return "route_identity_mismatch"
            elif edge["kind"] == "compound_castling_prerequisite":
                if not any(p["relation"] == "clears_castling_path" for p in facts):
                    return "missing_castling_prerequisite"
            else:
                return "unknown_dependency_operation"
    except (ValueError, KeyError, IndexError, TypeError):
        return "malformed_dependency"
    return None
