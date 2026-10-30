"""Finite objective grammar and prerequisite joins, independent of fixture identity."""
from __future__ import annotations

import chess

from .contracts import Hypothesis, Proposition, proposal
from .timeline import atom


def common_prefix(first, second):
    return next((i for i, (a, b) in enumerate(zip(first, second)) if a != b), min(len(first), len(second)))


def admit_fact(fact, line, primary, base, stable, reference):
    """Board truth is separate from eligibility for a non-conditional sentence."""
    source = line.get("source_query", {})
    result = {"admitted": False, "proposition_id": fact["id"], "timeline_id": line["id"],
              "search_ids": [line["search_id"]], "source_query": source}
    if source.get("start_ply", 0) > 0 and source.get("root_moves"):
        return {**result, "reason": "forced_opponent_root"}
    if primary is None or line["id"] != primary["id"]:
        return {**result, "reason": "not_the_primary_stability_line"}
    if fact["ply"] == 1:
        return {**result, "admitted": True, "reason": "exact_root_action", "agreement_plies": 1}
    if not base or not stable or not base.lines or not stable.lines:
        return {**result, "reason": "root_stability_unavailable"}
    agreement = common_prefix(base.lines[0]["moves_uci"], stable.lines[0]["moves_uci"])
    result.update(agreement_plies=agreement, search_ids=[base.id, stable.id])
    if fact["ply"] > agreement:
        return {**result, "reason": "beyond_root_stability_agreement"}
    if reference is None or reference.status != "complete_iteration" or not reference.lines:
        return {**result, "reason": "opponent_reference_unavailable"}
    if reference.root_moves or reference.fen != primary["nodes"][1]["fen"]:
        return {**result, "reason": "opponent_reference_is_restricted_or_wrong_node"}
    result["search_ids"].append(reference.id)
    result["reference_depth"] = reference.lines[0].get("depth", 0)
    if result["reference_depth"] < 20:
        return {**result, "reason": "opponent_reference_depth_not_reached"}
    agreement = min(agreement, common_prefix(stable.lines[0]["moves_uci"], [primary["root_uci"], *reference.lines[0]["moves_uci"]]))
    return {**result, "agreement_plies": agreement, "admitted": fact["ply"] <= agreement,
            "reason": "agrees_with_depth20_best_reply" if fact["ply"] <= agreement else "best_reply_does_not_retain_this_event"}


def attach_capture_contrast(h, played, alternative, facts, base_records, stable_records, epsilon):
    """Bind an immediate capture contrast to both original root score gaps.

    No evaluation fraction is attributed to the captured piece. This direct
    decision evidence takes precedence over a conditional coverage witness.
    """
    if (not played or not alternative or played["root_uci"] == h.root_uci
            or h.objective["kind"] not in ("capture", "checking_capture") or h.objective["outcome_ply"] != 1):
        return False
    capture = next(p for p in facts if p.id in h.proposition_ids and p.relation == "captures")
    target = played["nodes"][1]["relations"].get(capture.data["square"])
    if not target or target["piece_id"] != capture.object:
        return False
    from .search import comparison
    pairs = []
    for records in (base_records, stable_records):
        a, p = records[h.root_uci], records[played["root_uci"]]
        if a.status != "complete_iteration" or p.status != "complete_iteration" or not a.lines or not p.lines:
            return False
        best, other = a.lines[0]["score"], p.lines[0]["score"]
        if best["kind"] != "cp" or other["kind"] != "cp" or comparison(best, other, epsilon) != "inferior":
            return False
        pairs.append({"best_search_id": a.id, "played_search_id": p.id,
                      "best_score": dict(best), "played_score": dict(other), "gap_cp": best["value"] - other["value"]})
    root_fact = next(p for p in facts if p.timeline_id == played["id"] and p.relation == "legal_move")
    h.proposition_ids.append(root_fact.id)
    h.objective["root_capture_contrast"] = {"played_timeline_id": played["id"], "alternative_timeline_id": alternative["id"],
        "played_san": played["moves_san"][0], "best_san": alternative["moves_san"][0],
        "played_root_uci": played["root_uci"], "comparisons": pairs, "equivalence_cp": epsilon}
    h.dependencies.append({"kind": "root_capture_contrast", "capture_id": capture.id, "played_root_id": root_fact.id})
    h.search_ids.extend(row[key] for row in pairs for key in ("best_search_id", "played_search_id"))
    return True


def generate(timeline: dict, facts: list[Proposition]) -> tuple[list[Hypothesis], list[Proposition]]:
    root_event = timeline["events"][0]
    root = chess.Board(timeline["nodes"][0]["fen"])
    root_move = chess.Move.from_uci(root_event["move_uci"])
    own = timeline["nodes"][0]["turn"]
    root_id = root_event["moving_piece_id"]
    by_ply = {}
    for fact in facts:
        by_ply.setdefault(fact.ply, []).append(fact)
    generated, extra = [], []
    captures = [p for p in facts if p.relation == "captures" and p.actor == own]
    root_fact = next(p for p in facts if p.relation == "legal_move")
    for capture in captures:
        checking = [p for p in by_ply[capture.ply] if p.relation == "gives_check"]
        dependencies = []
        supporting = [capture, *checking, root_fact]
        earlier = [p for p in facts if p.relation == "captures" and p.ply < capture.ply]
        operation = "TRANSFORM" if capture.ply == 1 else "PREPARE"
        if checking and earlier:
            operation = "SEQUENCE"
            supporting += earlier
            dependencies.append({"kind": "legal_event_order", "before": [p.id for p in earlier], "after": capture.id})
        opened = [p for p in facts if p.relation == "opens_line" and p.subject == capture.subject
                  and p.object == capture.data["square"] and p.ply < capture.ply]
        if opened:
            supporting += opened
            dependencies.append({"kind": "opened_capture_line", "premise_ids": [p.id for p in opened], "outcome_id": capture.id})
            if not checking:
                operation = "ENABLE"
        if capture.subject == root_id and capture.ply > 1:
            dependencies.append({"kind": "same_piece_route", "piece_id": root_id,
                                 "events": [e["ply"] for e in timeline["events"][:capture.ply] if e["moving_piece_id"] == root_id]})
        replies = [p for p in by_ply[capture.ply] if p.relation == "only_legal_reply"]
        supporting += replies
        h = proposal(operation, timeline["root_uci"], {"kind": "checking_capture" if checking else "capture",
                     "target_id": capture.object, "piece_id": capture.subject, "timeline_id": timeline["id"],
                     "outcome_ply": capture.ply, "root_connected": capture.ply == 1 or any(d["kind"] in ("same_piece_route", "opened_capture_line") for d in dependencies)}, supporting, dependencies)
        h.status = "supported_consequence"
        h.search_ids = [timeline["search_id"]]
        h.unresolved = ["material_after_capture_not_proved", "all_defences_not_exhausted"]
        if not h.objective["root_connected"]:
            h.unresolved.append("root_to_outcome_mechanism_incomplete")
        generated.append(h)

    for fact in facts:
        if fact.relation in ("checkmates", "promotes_to") and fact.actor == own:
            h = proposal("ENABLE" if fact.ply == 1 else "PREPARE", timeline["root_uci"],
                         {"kind": fact.relation, "timeline_id": timeline["id"], "outcome_ply": fact.ply,
                          "root_connected": fact.ply == 1}, [fact, root_fact])
            h.status = "supported_mechanism" if fact.relation == "checkmates" and fact.ply == 1 else "supported_consequence"
            h.wording_strength = "exact_immediate_mate" if h.status == "supported_mechanism" else "demonstrated_continuation"
            h.search_ids = [timeline["search_id"]]
            h.unresolved = [] if h.status == "supported_mechanism" else ["all_defences_not_exhausted"]
            generated.append(h)

    # General quiet activity seed: a legal route leads to a newly attacked
    # concrete target. No mobility count is treated as positional benefit.
    for arrival in [p for p in facts if p.relation == "reaches" and p.actor == own and p.ply > 1]:
        pressure = [p for p in by_ply[arrival.ply] if p.relation == "attacks_piece"]
        if not pressure:
            continue
        opened = [p for p in facts if p.relation == "opens_line" and p.subject == arrival.subject and p.object == arrival.object]
        if arrival.subject != root_id and not opened:
            continue
        dependency = {"kind": "opened_entry_line" if opened else "same_piece_route",
                      "premise_ids": [p.id for p in opened] or [root_fact.id], "outcome_id": arrival.id}
        h = proposal("ENABLE" if opened else "PREPARE", timeline["root_uci"],
                     {"kind": "reach", "piece_id": arrival.subject, "square": arrival.object,
                      "timeline_id": timeline["id"], "target_ids": [p.object for p in pressure], "root_connected": True},
                     [root_fact, arrival, *pressure, *opened], [dependency])
        h.status = "supported_consequence"
        h.search_ids = [timeline["search_id"]]
        h.unresolved = ["target_attack_does_not_establish_a_sound_capture", "route_against_other_replies_incomplete",
                        "comparative_cause_not_established"]
        generated.append(h)

    # A quiet compound prerequisite: move a blocker off a still-available castling path.
    king = root.king(root.turn)
    if king is not None and root.piece_type_at(root_move.from_square) != chess.KING:
        for kingside in (True, False):
            rights = root.has_kingside_castling_rights(root.turn) if kingside else root.has_queenside_castling_rights(root.turn)
            destination = chess.square(6 if kingside else 2, chess.square_rank(king))
            rook = chess.square(7 if kingside else 0, chess.square_rank(king))
            path = chess.SquareSet(chess.between(king, rook))
            after = chess.Board(timeline["nodes"][1]["fen"])
            kept = after.has_kingside_castling_rights(root.turn) if kingside else after.has_queenside_castling_rights(root.turn)
            if rights and kept and root_move.from_square in path and root_move.to_square not in path:
                cleared = atom(timeline, 1, root_id, "clears_castling_path", chess.square_name(destination),
                               piece=chess.piece_name(root.piece_type_at(root_move.from_square)), move=root.san(root_move),
                               cleared_square=root_event["origin"])
                extra.append(cleared)
                witnessed = [p for p in facts if p.relation == "castles" and p.actor == own and p.object == cleared.object]
                h = proposal("PREPARE", timeline["root_uci"], {"kind": "castle", "king_id": next(s["piece_id"] for s in timeline["nodes"][0]["relations"].values() if s["piece"] == "king" and s["piece_id"].startswith(own + ":")),
                             "square": cleared.object, "timeline_id": timeline["id"], "root_connected": True}, [cleared, *witnessed, root_fact],
                             [{"kind": "compound_castling_prerequisite", "cleared_square": root_event["origin"],
                               "retained_castling_rights": True, "other_prerequisites": "other blockers, attacked transit squares and intervening replies"}])
                h.status = "supported_consequence" if witnessed else "incomplete_hypothesis"
                h.search_ids = [timeline["search_id"]]
                h.unresolved = ["route_against_opponent_resources", "comparative_cause_not_established"]
                generated.append(h)

    # Exact coverage is retained as premises; no attack count becomes a duty or a forced move.
    after = chess.Board(timeline["nodes"][1]["fen"])
    for square in sorted(set(root.attacks(root_move.from_square)) & set(after.attacks(root_move.to_square))):
        target = root.piece_at(square)
        if target is not None and target.color == root.turn and target.piece_type != chess.KING:
            maintained = atom(timeline, 1, root_id, "coverage_maintained", chess.square_name(square))
            extra.append(maintained)
            h = proposal("PRESERVE", timeline["root_uci"], {"kind": "maintain_coverage", "target_id": timeline["nodes"][0]["relations"][chess.square_name(square)]["piece_id"],
                         "timeline_id": timeline["id"]}, [maintained])
            h.unresolved = ["defensive_responsibility_not_yet_established", "adequate_sacrifice_or_replacement_not_excluded"]
            generated.append(h)
    if root.piece_type_at(root_move.from_square) == chess.PAWN:
        transformed = atom(timeline, 1, root_id, "pawn_transforms", root_event["destination"], move=root.san(root_move))
        extra.append(transformed)
        opened = [p for p in facts if p.relation == "opens_line"]
        h = proposal("TRANSFORM", timeline["root_uci"], {"kind": "pawn_structure", "timeline_id": timeline["id"]}, [transformed, *opened])
        h.unresolved = ["persistent_usable_benefit_not_established", "opponent_pawn_breaks_need_investigation"]
        generated.append(h)
    return generated, extra


def prevention_candidates(played: dict | None, alternative: dict, facts: list[Proposition]) -> list[Hypothesis]:
    if played is None or played["root_uci"] == alternative["root_uci"]:
        return []
    own = played["nodes"][0]["turn"]
    threats = [p for p in facts if p.timeline_id == played["id"] and p.relation == "captures" and p.actor != own]
    result = []
    for threat in threats:
        h = proposal("PREVENT", alternative["root_uci"], {"kind": "opponent_capture", "target_id": threat.object,
                     "observed_timeline_id": played["id"], "contrast_timeline_id": alternative["id"]}, [threat])
        h.unresolved = ["absence_from_alternative_PV_does_not_establish_prevention", "replacement_opponent_resources_not_excluded"]
        result.append(h)
    return result


def challenge(hypothesis: Hypothesis, timelines: list[dict]) -> None:
    """Retain conditional witnesses and exact counterexamples to universal readings."""
    for line in timelines:
        if line["root_uci"] != hypothesis.root_uci:
            continue
        objective = hypothesis.objective
        if objective["kind"] in ("capture", "checking_capture"):
            own = line["nodes"][0]["turn"]
            # If the proposed attacker is actually taken, its later capture in
            # the original ordering cannot be a forced event in this branch.
            lost = [e for e in line["events"] if e["captured_piece_id"] == objective["piece_id"]
                    and line["nodes"][e["ply"] - 1]["turn"] != own]
            captured = any(e["moving_piece_id"] == objective["piece_id"] and e["captured_piece_id"] == objective["target_id"]
                           and (objective["kind"] != "checking_capture" or e["gave_check"]) for e in line["events"])
            if lost and not captured:
                hypothesis.counterexamples.append({"timeline_id": line["id"], "search_id": line["search_id"],
                    "refutes": "unavoidable_event_order", "reason": "proposed attacker is captured on this legal branch"})
        elif objective["kind"] == "castle":
            castles = [e for e in line["events"] if e["moving_piece_id"] == objective["king_id"] and e["destination"] == objective["square"]
                       and chess.Board(e["fen_before"]).is_castling(chess.Move.from_uci(e["move_uci"]))]
            if castles:
                hypothesis.search_ids.append(line["search_id"])
            else:
                final = chess.Board(line["nodes"][-1]["fen"])
                color = objective["king_id"].startswith("white:")
                kingside = chess.square_file(chess.parse_square(objective["square"])) > 4
                rights = final.has_kingside_castling_rights(color) if kingside else final.has_queenside_castling_rights(color)
                if not rights:
                    hypothesis.counterexamples.append({"timeline_id": line["id"], "search_id": line["search_id"],
                        "refutes": "unavoidable_castling_goal", "reason": "the required castling rights are lost on this legal branch"})
                else:
                    hypothesis.unresolved.append("castling_not_witnessed_within_branch:" + line["id"])
    hypothesis.search_ids = sorted(set(hypothesis.search_ids))
