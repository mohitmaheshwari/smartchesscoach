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
    if p.relation == "secure_piece_placement":
        from .positional_verify import verify_placement
        return verify_placement(p, timeline)
    if p.relation in ("checking_capture_available", "checking_capture_unavailable", "retained_coverage"):
        node = timeline["nodes"][p.ply]
        if p.evidence_ids != (timeline["search_id"], node["id"]):
            return "wrong_evidence_reference"
        board = chess.Board(node["fen"])
        state = next((s for s in node["relations"].values() if s["piece_id"] == p.subject), None)
        if state is None or p.actor != p.subject.split(":", 1)[0]:
            return "wrong_snapshot_actor_or_identity"
        source = chess.parse_square(state["square"])
        if p.relation == "retained_coverage":
            square = chess.parse_square(p.object)
            if p.data["piece"] != chess.piece_name(board.piece_type_at(source)) or p.data["square"] != state["square"]:
                return "wrong_retained_piece"
            since = p.data["retained_since_ply"]
            if isinstance(since, bool) or not isinstance(since, int) or not 0 <= since <= p.ply:
                return "invalid_retained_scope"
            for snapshot in timeline["nodes"][since:p.ply + 1]:
                piece = next((s for s in snapshot["relations"].values() if s["piece_id"] == p.subject), None)
                if piece is None or square not in chess.Board(snapshot["fen"]).attacks(chess.parse_square(piece["square"])):
                    return "coverage_not_retained"
            return None
        target = node["relations"].get(p.data["target_square"])
        move = chess.Move.from_uci(p.data["move_uci"])
        if (target is None or target["piece_id"] != p.object or move.from_square != source
                or move.to_square != chess.parse_square(p.data["target_square"])
                or board.piece_at(source).color != board.turn):
            return "wrong_checking_capture_entities"
        available = move in board.legal_moves and board.is_capture(move) and board.gives_check(move)
        if p.relation == "checking_capture_available":
            return None if available and board.san(move) == p.data["move_san"] else "checking_capture_unavailable"
        return None if not available else "checking_capture_actually_available"
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
    elif p.relation in ("coverage_gained", "coverage_abandoned", "coverage_maintained", "coverage_not_gained"):
        square = chess.parse_square(p.object)
        prior, current = square in before.attacks(move.from_square), square in after.attacks(move.to_square)
        ok = {"coverage_gained": not prior and current, "coverage_abandoned": prior and not current,
              "coverage_maintained": prior and current, "coverage_not_gained": not prior and not current}[p.relation]
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


def verify_dependencies(hypothesis, propositions: dict, timelines: dict, searches=None) -> str | None:
    """Check composed links as relations over the accepted facts and legal events.

    This validates a demonstrated dependency, not necessity or attribution of
    an engine evaluation. Those stronger readings remain unresolved.
    """
    try:
        facts = [propositions[key] for key in hypothesis.proposition_ids]
        if hypothesis.objective["kind"] == "comparative_recapture":
            from .positional_verify import verify_recapture
            return verify_recapture(hypothesis, propositions, timelines, searches)
        allowed_roots = {hypothesis.root_uci}
        if hypothesis.objective.get("root_capture_contrast"):
            allowed_roots.add(hypothesis.objective["root_capture_contrast"]["played_root_uci"])
        if hypothesis.objective["kind"] in ("comparative_sequence", "comparative_threat"):
            sequence = hypothesis.objective["kind"] == "comparative_sequence"
            permitted = "conditional_on_setup_and_demonstrated_exchange" if sequence else "conditional_threat_with_searched_defences"
            if (hypothesis.wording_strength not in (permitted, "demonstrated_continuation_with_alternative_branches")
                    or len(hypothesis.dependencies) != 1
                    or hypothesis.dependencies[0]["kind"] != ("checking_capture_changes_exchange" if sequence else "added_cover_answers_prepared_check")
                    or hypothesis.operation != ("SEQUENCE" if sequence else "PREVENT")):
                return "unsupported_comparative_strength_or_dependency"
            allowed_roots.add(hypothesis.objective["contrast_root_uci"])
        if any(timelines[p["timeline_id"]]["root_uci"] not in allowed_roots for p in facts if p["relation"] != "captures" or hypothesis.operation != "PREVENT"):
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
            elif edge["kind"] == "root_capture_contrast":
                obj = hypothesis.objective["root_capture_contrast"]
                capture, played_root = propositions[edge["capture_id"]], propositions[edge["played_root_id"]]
                p, a = timelines[obj["played_timeline_id"]], timelines[obj["alternative_timeline_id"]]
                target = p["nodes"][1]["relations"].get(capture["data"]["square"], {})
                if (capture["relation"] != "captures" or capture["ply"] != 1 or capture["timeline_id"] != a["id"]
                        or played_root["relation"] != "legal_move" or played_root["timeline_id"] != p["id"]
                        or p["nodes"][0]["fen"] != a["nodes"][0]["fen"] or a["root_uci"] != hypothesis.root_uci
                        or p["root_uci"] != obj["played_root_uci"] or obj["played_san"] != p["moves_san"][0]
                        or obj["best_san"] != a["moves_san"][0] or target.get("piece_id") != capture["object"]
                        or len(obj["comparisons"]) != 2 or searches is None):
                    return "wrong_root_capture_contrast"
                from .search import comparison
                for pair in obj["comparisons"]:
                    best, other = searches[pair["best_search_id"]], searches[pair["played_search_id"]]
                    if (best["status"] != "complete_iteration" or other["status"] != "complete_iteration"
                            or best["fen"] != a["nodes"][0]["fen"] or other["fen"] != p["nodes"][0]["fen"]
                            or best["root_moves"] != [a["root_uci"]] or other["root_moves"] != [p["root_uci"]]
                            or best["lines"][0]["score"] != pair["best_score"] or other["lines"][0]["score"] != pair["played_score"]
                            or pair["best_score"]["kind"] != "cp" or pair["played_score"]["kind"] != "cp"
                            or pair["best_score"]["pov"] != a["nodes"][0]["turn"] or pair["played_score"]["pov"] != a["nodes"][0]["turn"]
                            or pair["gap_cp"] != pair["best_score"]["value"] - pair["played_score"]["value"]
                            or comparison(pair["best_score"], pair["played_score"], obj["equivalence_cp"]) != "inferior"):
                        return "root_gap_not_supported_by_both_searches"
            elif edge["kind"] in ("checking_capture_changes_exchange", "added_cover_answers_prepared_check"):
                problem = verify_comparative(hypothesis, edge, propositions, timelines, searches)
                if problem:
                    return problem
            else:
                return "unknown_dependency_operation"
    except (ValueError, KeyError, IndexError, TypeError):
        return "malformed_dependency"
    return None


def _replay_certificate(line):
    board = chess.Board(line["nodes"][0]["fen"])
    for ply, raw in enumerate(line["moves_uci"], 1):
        move = chess.Move.from_uci(raw)
        if move not in board.legal_moves:
            raise ValueError("illegal_certificate")
        if board.san(move) != line["moves_san"][ply - 1]:
            raise ValueError("wrong_certificate_move_name")
        board.push(move)
        if board.fen() != line["nodes"][ply]["fen"]:
            raise ValueError("wrong_certificate_position")
    return board


def verify_comparative(h, edge, propositions, timelines, searches):
    p, a = timelines[edge["played_timeline_id"]], timelines[edge["alternative_timeline_id"]]
    p_final, a_final = _replay_certificate(p), _replay_certificate(a)
    obj = h.objective
    if (p["nodes"][0]["fen"] != a["nodes"][0]["fen"] or p["moves_uci"][1] != a["moves_uci"][1]
            or obj["contrast_root_uci"] != p["root_uci"] or h.root_uci != a["root_uci"]
            or obj["played_san"] != p["moves_san"][0] or obj["alternative_san"] != a["moves_san"][0]
            or obj["setup_san"] != p["moves_san"][1]
            or obj["played_timeline_id"] != p["id"] or obj["alternative_timeline_id"] != a["id"]):
        return "wrong_comparative_roots_or_setup"
    if edge["kind"] == "checking_capture_changes_exchange":
        available, unavailable = propositions[edge["available_id"]], propositions[edge["unavailable_id"]]
        if (available["relation"] != "checking_capture_available" or unavailable["relation"] != "checking_capture_unavailable"
                or available["subject"] != unavailable["subject"] or available["object"] != unavailable["object"]
                or available["timeline_id"] != a["id"] or unavailable["timeline_id"] != p["id"]
                or available["ply"] != 2 or unavailable["ply"] != 2
                or a["events"][2]["captured_piece_id"] != available["object"] or not a["events"][2]["gave_check"]
                or obj["resource_san"] != available["data"]["move_san"]
                or obj["target_square"] != available["data"]["target_square"]
                or obj["exchange_san"] != p["moves_san"][2:] or a["moves_uci"][4:] != p["moves_uci"][2:]):
            return "checking_capture_link_not_established"
        queen_sets = [{e["captured_piece_id"] for e in line["events"] if e["captured_piece"] == "queen"} for line in (p, a)]
        if len(queen_sets[0]) != 2 or queen_sets[0] != queen_sets[1]:
            return "both_queens_not_exchanged"
        certificate = obj["certificate"]
        after_check = chess.Board(a["nodes"][3]["fen"])
        if (certificate["played_line"] != p["moves_uci"] or certificate["alternative_line"] != a["moves_uci"]
                or certificate["setup_uci"] != p["moves_uci"][1] or certificate["checking_capture"] != a["moves_uci"][2]
                or certificate["legal_check_evasions"] != sorted(m.uci() for m in after_check.legal_moves)
                or certificate["target_square"] != obj["target_square"] or certificate["victim_piece"] != obj["extra_piece"]
                or certificate["scope"] != "conditional_on_setup_and_demonstrated_exchange"):
            return "wrong_serialized_sequence_certificate"
        victim_type = chess.Board(a["nodes"][2]["fen"]).piece_type_at(chess.parse_square(available["data"]["target_square"]))
        if obj["extra_piece"] != chess.piece_name(victim_type):
            return "wrong_extra_piece"
        own = chess.Board(p["nodes"][0]["fen"]).turn
        for piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            gain = (len(a_final.pieces(piece_type, own)) - len(a_final.pieces(piece_type, not own))) - (len(p_final.pieces(piece_type, own)) - len(p_final.pieces(piece_type, not own)))
            if gain != (1 if piece_type == victim_type else 0):
                return "comparative_material_not_the_named_piece"
        return None
    missing, gained = propositions[edge["missing_id"]], propositions[edge["gained_id"]]
    if (missing["subject"] != gained["subject"] or missing["object"] != gained["object"]
            or missing["object"] != obj["target_square"] or missing["timeline_id"] != p["id"] or gained["timeline_id"] != a["id"]
            or missing["relation"] not in ("coverage_not_gained", "coverage_abandoned")
            or gained["relation"] not in ("coverage_gained", "coverage_maintained")
            or p["moves_uci"][2:4] != a["moves_uci"][2:4] or not p["events"][3]["gave_check"]
            or a["events"][4]["moving_piece_id"] != gained["subject"]
            or a["events"][4]["captured_piece_id"] != a["events"][3]["moving_piece_id"]
            or a["events"][4]["captured_square"] != gained["object"]
            or obj["check_san"] != p["moves_san"][3] or obj["capture_san"] != a["moves_san"][4]
            or obj["wait_san"] != p["moves_san"][2] or obj["mate_line_san"] != p["moves_san"][3:]
            or obj["answer_line_san"] != a["moves_san"][4:6]
            or missing["ply"] != 1 or gained["ply"] != 1
            or bool(obj["origin_covered"]) != (missing["relation"] == "coverage_abandoned")):
        return "added_cover_does_not_answer_the_resource"
    exchange = (len(a["events"]) > 5 and a["events"][3]["moving_piece"] == "queen"
                and a["events"][4]["moving_piece"] == "queen"
                and a["events"][5]["captured_piece_id"] == a["events"][4]["moving_piece_id"])
    if obj["queen_exchange"] != exchange:
        return "queen_exchange_not_established"
    if not p_final.is_checkmate():
        return "demonstration_does_not_end_in_mate"
    for key in h.proposition_ids:
        fact = propositions[key]
        if fact["relation"] == "retained_coverage" and (fact["timeline_id"] != p["id"]
                or fact["ply"] != len(p["events"]) or fact["data"]["retained_since_ply"] != 0
                or fact["object"] != p["events"][-1]["destination"]
                or fact["actor"] != p["nodes"][-2]["turn"]):
            return "retained_support_not_linked_to_mating_piece"
    # Independently close the claimed mate-in-two tree after the legal waiting
    # move. It is not a claim about other earlier defender choices.
    before = chess.Board(p["nodes"][3]["fen"])
    check = chess.Move.from_uci(p["moves_uci"][3])
    if not _verified_mate_two(before, check):
        return "conditional_mate_tree_has_a_defence"
    certificate = obj["certificate"]
    if (certificate["played_prefix"] != p["moves_uci"][:3] or certificate["alternative_prefix"] != a["moves_uci"][:4]
            or certificate["played_uci"] != p["moves_uci"][0] or certificate["alternative_uci"] != a["moves_uci"][0]
            or certificate["setup_uci"] != p["moves_uci"][1] or certificate["wait_uci"] != p["moves_uci"][2]
            or certificate["check_uci"] != check.uci() or certificate["capture_answer_uci"] != a["moves_uci"][4]
            or certificate["target_square"] != obj["target_square"] or certificate["origin_covered"] != obj["origin_covered"]
            or certificate["status"] != "legal_conditional_witness"):
        return "wrong_serialized_threat_certificate"
    after_check = before.copy()
    after_check.push(check)
    tree = certificate["mate_tree"]
    evasions = sorted(m.uci() for m in after_check.legal_moves)
    if (tree["all_evasions"] != evasions or tree["depth"] != (1 if after_check.is_checkmate() else 2)
            or (evasions and sorted(branch[1] for branch in tree["lines"]) != evasions)
            or not tree["lines"] or tree["lines"][0] != p["moves_uci"][3:]):
        return "wrong_serialized_mate_tree"
    for branch in tree["lines"]:
        node = before.copy()
        if branch[0] != check.uci() or len(branch) != (1 if after_check.is_checkmate() else 3):
            return "wrong_serialized_mate_tree"
        for raw in branch:
            action = chess.Move.from_uci(raw)
            if action not in node.legal_moves:
                return "illegal_serialized_mate_branch"
            node.push(action)
        if not node.is_checkmate():
            return "serialized_branch_is_not_mate"
    if searches is None:
        return "missing_comparative_search_evidence"
    if len(obj["score_pairs"]) != 2:
        return "missing_comparative_search_evidence"
    from .search import comparison
    pov = p["nodes"][0]["turn"]
    for got_id, covered_id in obj["score_pairs"]:
        got, covered = searches[got_id], searches[covered_id]
        if (got["status"] != "complete_iteration" or covered["status"] != "complete_iteration"
                or not got["lines"] or not covered["lines"]
                or got["fen"] != p["nodes"][3]["fen"] or covered["fen"] != a["nodes"][4]["fen"]
                or got["root_moves"] != [p["moves_uci"][3]] or covered["root_moves"] != [a["moves_uci"][4]]
                or got["lines"][0]["root_uci"] != p["moves_uci"][3] or covered["lines"][0]["root_uci"] != a["moves_uci"][4]
                or got["lines"][0]["score"]["pov"] != pov or covered["lines"][0]["score"]["pov"] != pov
                or comparison(covered["lines"][0]["score"], got["lines"][0]["score"], obj["equivalence_cp"]) != "inferior"):
            return "comparative_resource_not_supported_by_search"
    defence = obj["defence_scope"]
    if defence.get("refutes_ignoring_reply_mate_tree"):
        record = searches[defence["search_id"]]
        node = chess.Board(p["nodes"][2]["fen"])
        reply = chess.Move.from_uci(record["lines"][0]["root_uci"])
        if record["status"] != "complete_iteration" or record["fen"] != node.fen() or reply not in node.legal_moves or node.san(reply) != defence["first_reply_san"]:
            return "invalid_earlier_defence_evidence"
        if defence["first_reply_score"] != record["lines"][0]["score"] or defence["first_reply_score"]["pov"] != pov:
            return "wrong_earlier_defence_score"
        node.push(reply)
        if _verified_mate_two(node, check):
            return "earlier_defence_does_not_refute_mate_tree"
    return None


def _verified_mate_two(board, check):
    """Independent finite rule validation, separate from candidate generation."""
    if check not in board.legal_moves or not board.gives_check(check):
        return False
    after = board.copy()
    after.push(check)
    if after.is_checkmate():
        return True
    replies = list(after.legal_moves)
    for response in replies:
        node = after.copy()
        node.push(response)
        finishes = []
        for move in list(node.legal_moves):
            child = node.copy()
            child.push(move)
            if child.is_checkmate():
                finishes.append(move)
        if not finishes:
            return False
    return bool(replies)
