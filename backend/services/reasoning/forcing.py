"""Comparative legal certificates for checking captures and prepared checks.

No position lookup: enumerate action orderings, changed coverage and legal
opponent resources. Null moves suggest checks only; accepted evidence always
uses actual legal continuations and separately recorded engine queries.
"""
from __future__ import annotations

import chess

from .contracts import Proposition, SearchRecord, fingerprint, proposal
from .search import comparison
from .timeline import atom, event_facts


def walk(root, moves):
    board = root.copy()
    for raw in moves:
        move = chess.Move.from_uci(raw)
        if move not in board.legal_moves:
            raise ValueError("illegal_certificate_line")
        board.push(move)
    return board


def exchange_routes(board):
    """Legal queen takes / other queen takes / capturer is taken orderings."""
    if any(len(board.pieces(chess.QUEEN, color)) != 1 for color in chess.COLORS):
        return
    for first in sorted(board.legal_moves, key=lambda m: m.uci()):
        if not board.is_capture(first) or board.piece_type_at(first.to_square) != chess.QUEEN:
            continue
        after = board.copy()
        after.push(first)
        for second in sorted(after.legal_moves, key=lambda m: m.uci()):
            if not after.is_capture(second) or after.piece_type_at(second.to_square) != chess.QUEEN:
                continue
            final = after.copy()
            final.push(second)
            for third in sorted(final.legal_moves, key=lambda m: m.uci()):
                if final.is_capture(third) and third.to_square == second.to_square:
                    yield [first.uci(), second.uci(), third.uci()]


def sequence_certificate(root, played_uci, alternative_uci, setup_uci):
    """Find an extra checking capture while the same queen exchange is available."""
    played, alternative = chess.Move.from_uci(played_uci), chess.Move.from_uci(alternative_uci)
    if played.from_square != alternative.from_square:
        return None
    try:
        before_played = walk(root, [played_uci, setup_uci])
        before_alternative = walk(root, [alternative_uci, setup_uci])
    except ValueError:
        return None
    if before_played.turn != root.turn or before_alternative.turn != root.turn:
        return None
    for exchange in exchange_routes(before_played):
        for check in sorted(before_alternative.legal_moves, key=lambda m: m.uci()):
            if (check.from_square != alternative.to_square or not before_alternative.is_capture(check)
                    or not before_alternative.gives_check(check)):
                continue
            counterpart = chess.Move(played.to_square, check.to_square, promotion=check.promotion)
            if counterpart in before_played.legal_moves and before_played.gives_check(counterpart):
                continue
            victim = before_alternative.piece_at(check.to_square)
            if victim is None or victim.piece_type == chess.QUEEN:
                continue
            after_check = before_alternative.copy()
            after_check.push(check)
            legal_evasions = sorted(after_check.legal_moves, key=lambda m: m.uci())
            for reply in legal_evasions:
                preferred_line = [alternative_uci, setup_uci, check.uci(), reply.uci(), *exchange]
                try:
                    walk(root, preferred_line)
                except ValueError:
                    continue
                return {"played_line": [played_uci, setup_uci, *exchange], "alternative_line": preferred_line,
                        "setup_uci": setup_uci, "checking_capture": check.uci(), "target_square": chess.square_name(check.to_square),
                        "victim_piece": chess.piece_name(victim.piece_type),
                        "legal_check_evasions": [m.uci() for m in legal_evasions],
                        "scope": "conditional_on_setup_and_demonstrated_exchange"}
    return None


def checking_threat_seeds(root, played_uci, alternative_uci, setup_uci):
    """Diagnostic pass proposes a future check, never a legal-line certificate."""
    played, alternative = chess.Move.from_uci(played_uci), chess.Move.from_uci(alternative_uci)
    if played.from_square != alternative.from_square:
        return []
    try:
        a, b = walk(root, [played_uci, setup_uci]), walk(root, [alternative_uci, setup_uci])
    except ValueError:
        return []
    setup = chess.Move.from_uci(setup_uci)
    before_setup = walk(root, [played_uci])
    if before_setup.is_capture(setup) or before_setup.gives_check(setup) or a.is_check():
        return []
    diagnostic = a.copy()
    diagnostic.push(chess.Move.null())
    result = []
    for action in sorted(diagnostic.legal_moves, key=lambda m: m.uci()):
        if action.from_square != setup.to_square or not diagnostic.gives_check(action):
            continue
        target = action.to_square
        if target in b.attacks(alternative.to_square) and target not in a.attacks(played.to_square):
            result.append({"played_uci": played_uci, "alternative_uci": alternative_uci, "setup_uci": setup_uci,
                           "check_uci": action.uci(), "target_square": chess.square_name(target),
                           "origin_covered": target in root.attacks(played.from_square),
                           "status": "diagnostic_seed_only"})
    return result


def mate_two_witness(board, check):
    """Exact two-move mate certificate at this node; no engine score surrogate."""
    if check not in board.legal_moves or not board.gives_check(check):
        return None
    after = board.copy()
    after.push(check)
    if after.is_checkmate():
        return {"lines": [[check.uci()]], "all_evasions": [], "depth": 1}
    branches = []
    replies = sorted(after.legal_moves, key=lambda m: m.uci())
    for reply in replies:
        following = after.copy()
        following.push(reply)
        finish = next((m for m in sorted(following.legal_moves, key=lambda m: m.uci())
                       if following.gives_check(m) and is_mating(following, m)), None)
        if finish is None:
            return None
        branches.append([check.uci(), reply.uci(), finish.uci()])
    return {"lines": branches, "all_evasions": [m.uci() for m in replies], "depth": 2} if branches else None


def is_mating(board, move):
    after = board.copy()
    after.push(move)
    return after.is_checkmate()


def legal_threat_witness(root, seed, limit):
    """Replace diagnostic pass with a legal quiet move and close the mate tree."""
    played = walk(root, [seed["played_uci"], seed["setup_uci"]])
    alternate = walk(root, [seed["alternative_uci"], seed["setup_uci"]])
    coverer = chess.Move.from_uci(seed["alternative_uci"]).to_square
    moved_played = chess.Move.from_uci(seed["played_uci"]).to_square
    common = set(played.legal_moves) & set(alternate.legal_moves)
    visited = 0
    for wait in sorted(common, key=lambda m: m.uci()):
        if (wait.from_square in (coverer, moved_played) or played.piece_type_at(wait.from_square) == chess.KING
                or played.is_capture(wait) or alternate.is_capture(wait) or wait.promotion
                or played.gives_check(wait) or alternate.gives_check(wait)):
            continue
        if visited >= limit:
            break
        visited += 1
        a, b = played.copy(), alternate.copy()
        a.push(wait)
        b.push(wait)
        check = chess.Move.from_uci(seed["check_uci"])
        if check not in b.legal_moves or not b.gives_check(check):
            continue
        certificate = mate_two_witness(a, check)
        if certificate is None:
            continue
        b.push(check)
        answer = chess.Move(coverer, check.to_square)
        if answer not in b.legal_moves or not b.is_capture(answer):
            continue
        return {**seed, "wait_uci": wait.uci(), "mate_tree": certificate,
                "played_prefix": [seed["played_uci"], seed["setup_uci"], wait.uci()],
                "alternative_prefix": [seed["alternative_uci"], seed["setup_uci"], wait.uci(), check.uci()],
                "capture_answer_uci": answer.uci(), "status": "legal_conditional_witness"}
    return None


def rule_record(session, root, moves):
    record = SearchRecord(fingerprint(["legal_rule_probe", root.fen(), moves]), "legal_rule_probe", root.fen(),
                          [moves[0]], 0, 1, "legal_rule_probe", stop_reason="legal_replay_only")
    session.records.append(record)
    return record


def snapshot_atom(line, ply, subject, relation, obj, **data):
    actor = subject.split(":", 1)[0]
    return Proposition(fingerprint([subject, relation, obj, line["id"], ply, data]), subject, relation, obj,
                       line["id"], ply, actor, (line["search_id"], line["nodes"][ply]["id"]), data)


def sequence_hypothesis(root, played_uci, alternative_uci, setup_uci, session, add_line):
    certificate = sequence_certificate(root, played_uci, alternative_uci, setup_uci)
    if certificate is None:
        return None, []
    p_moves, a_moves = certificate["played_line"], certificate["alternative_line"]
    if max(len(p_moves), len(a_moves)) > session.config.max_plies:
        return None, []
    p_line = add_line(p_moves, rule_record(session, root, p_moves), retain_hypotheses=False)
    a_line = add_line(a_moves, rule_record(session, root, a_moves), retain_hypotheses=False)
    target = certificate["target_square"]
    subject = p_line["events"][0]["moving_piece_id"]
    victim = a_line["nodes"][2]["relations"][target]["piece_id"]
    available = snapshot_atom(a_line, 2, subject, "checking_capture_available", victim,
                             target_square=target, move_uci=certificate["checking_capture"],
                             move_san=chess.Board(a_line["nodes"][2]["fen"]).san(chess.Move.from_uci(certificate["checking_capture"])))
    unavailable = snapshot_atom(p_line, 2, subject, "checking_capture_unavailable", victim,
                               target_square=target, move_uci=chess.Move(chess.Move.from_uci(played_uci).to_square, chess.parse_square(target)).uci())
    objective = {"kind": "comparative_sequence", "root_connected": True, "contrast_root_uci": played_uci,
                 "played_timeline_id": p_line["id"], "alternative_timeline_id": a_line["id"],
                 "setup_san": p_line["moves_san"][1], "played_san": p_line["moves_san"][0],
                 "alternative_san": a_line["moves_san"][0], "resource_san": available.data["move_san"],
                 "target_square": target, "exchange_san": p_line["moves_san"][2:],
                 "extra_piece": certificate["victim_piece"], "certificate": certificate}
    evidence = [available, unavailable, *event_facts(p_line), *event_facts(a_line)]
    h = proposal("SEQUENCE", alternative_uci, objective, evidence,
                 [{"kind": "checking_capture_changes_exchange", "played_timeline_id": p_line["id"],
                   "alternative_timeline_id": a_line["id"], "available_id": available.id, "unavailable_id": unavailable.id}])
    h.status, h.wording_strength = "supported_mechanism", certificate["scope"]
    h.search_ids = [p_line["search_id"], a_line["search_id"]]
    h.unresolved = ["setup_reply_not_forced", "exchange_is_a_legal_variation_not_an_exhaustive_minimax_result"]
    return h, evidence


def threat_hypothesis(root, played_uci, alternative_uci, setup_uci, session, add_line):
    for seed in checking_threat_seeds(root, played_uci, alternative_uci, setup_uci):
        witness = legal_threat_witness(root, seed, session.config.max_expanded_nodes)
        if witness is None:
            continue
        if len(witness["played_prefix"]) + len(witness["mate_tree"]["lines"][0]) > session.config.max_plies or session.config.max_plies < 6:
            continue
        a = walk(root, witness["played_prefix"])
        b = walk(root, witness["alternative_prefix"])
        check = chess.Move.from_uci(seed["check_uci"])
        capture = chess.Move.from_uci(witness["capture_answer_uci"])
        pairs = []
        for nodes in (session.config.nodes, session.config.stability_nodes):
            if not session.can_query(nodes):
                break
            got = session.query(a, "uncovered_check_resource", roots=[check], nodes=nodes)
            if not session.can_query(nodes):
                break
            covered = session.query(b, "added_cover_capture_response", roots=[capture], nodes=nodes)
            if not got.lines or not covered.lines or comparison(covered.lines[0]["score"], got.lines[0]["score"], session.config.equivalence_cp) != "inferior":
                break
            pairs.append((got, covered))
        if len(pairs) != 2:
            continue
        uncovered, covered = pairs[-1]
        mate_branch = witness["played_prefix"] + witness["mate_tree"]["lines"][0]
        p_line = add_line(mate_branch, rule_record(session, root, mate_branch), retain_hypotheses=False)
        a_line = add_line(witness["alternative_prefix"] + covered.lines[0]["moves_uci"], covered, retain_hypotheses=False)
        subject = p_line["events"][0]["moving_piece_id"]
        relation = "coverage_abandoned" if seed["origin_covered"] else "coverage_not_gained"
        missing = atom(p_line, 1, subject, relation, seed["target_square"])
        gained = atom(a_line, 1, subject, "coverage_maintained" if seed["origin_covered"] else "coverage_gained", seed["target_square"])
        supports = []
        final = p_line["nodes"][-1]
        last = p_line["events"][-1]
        if last["checkmate"]:
            landing = last["destination"]
            for state in final["relations"].values():
                initial = next((s for s in p_line["nodes"][0]["relations"].values() if s["piece_id"] == state["piece_id"]), None)
                if state["piece_id"] != last["moving_piece_id"] and state["piece_id"].split(":")[0] == final["relations"][landing]["piece_id"].split(":")[0] and landing in state["attack_squares"] and initial and landing in initial["attack_squares"]:
                    supports.append(snapshot_atom(p_line, len(p_line["events"]), state["piece_id"], "retained_coverage", landing,
                                                  retained_since_ply=0, piece=state["piece"], square=state["square"]))
        defence_scope = {"status": "not_searched", "all_defences_exhausted": False}
        after_setup = walk(root, [played_uci, setup_uci])
        if session.can_query(session.config.stability_nodes):
            defences = session.query(after_setup, "defences_to_prepared_check", width=session.config.reply_width,
                                     nodes=session.config.stability_nodes)
            defence_scope = {"search_id": defences.id, "status": defences.status,
                             "replies": [r["root_uci"] for r in defences.lines], "all_defences_exhausted": False}
            for response in defences.lines[:1]:
                candidate = walk(root, [played_uci, setup_uci, response["root_uci"]])
                if check in candidate.legal_moves:
                    defence_scope["refutes_ignoring_reply_mate_tree"] = mate_two_witness(candidate, check) is None
                    defence_scope["first_reply_san"] = after_setup.san(chess.Move.from_uci(response["root_uci"]))
        exchange = (len(a_line["events"]) > 5 and a_line["events"][3]["moving_piece"] == "queen"
                    and a_line["events"][4]["moving_piece"] == "queen"
                    and a_line["events"][5]["captured_piece_id"] == a_line["events"][4]["moving_piece_id"])
        objective = {"kind": "comparative_threat", "root_connected": True, "contrast_root_uci": played_uci,
                     "played_timeline_id": p_line["id"], "alternative_timeline_id": a_line["id"],
                     "played_san": p_line["moves_san"][0], "alternative_san": a_line["moves_san"][0],
                     "setup_san": p_line["moves_san"][1], "check_san": p_line["moves_san"][3],
                     "capture_san": a_line["moves_san"][4], "target_square": seed["target_square"],
                     "wait_san": p_line["moves_san"][2], "mate_line_san": p_line["moves_san"][3:],
                     "queen_exchange": exchange, "answer_line_san": a_line["moves_san"][4:6],
                     "origin_covered": seed["origin_covered"], "certificate": witness,
                     "score_pairs": [[x.id, y.id] for x, y in pairs], "equivalence_cp": session.config.equivalence_cp,
                     "defence_scope": defence_scope}
        evidence = [missing, gained, *supports, *event_facts(p_line), *event_facts(a_line)]
        h = proposal("PREVENT", alternative_uci, objective, evidence,
                     [{"kind": "added_cover_answers_prepared_check", "played_timeline_id": p_line["id"],
                       "alternative_timeline_id": a_line["id"], "missing_id": missing.id, "gained_id": gained.id}])
        h.status, h.wording_strength = "supported_mechanism", "conditional_threat_with_searched_defences"
        h.search_ids = [p_line["search_id"], a_line["search_id"], *[r.id for pair in pairs for r in pair]]
        h.unresolved = ["waiting_move_is_a_witness_not_best_defence", "no_claim_of_forced_mate_against_all_defences"]
        return h, evidence
    return None, []
