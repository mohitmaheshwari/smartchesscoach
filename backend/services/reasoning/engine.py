"""Offline FEN -> bounded search -> objectives -> verified controlled explanation."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import time

import chess

from services.stored_line_verifier import parse_legal_move, STORED_LINE_VERIFIER_VERSION
from .contracts import ReasoningConfig, VERSION, fingerprint
from .forcing import sequence_hypothesis, threat_hypothesis
from .investigation import investigate
from .objectives import generate, prevention_candidates, challenge, attach_capture_contrast, admit_fact, common_prefix
from .render import render, add_resource
from .search import SearchSession, score_order, comparison, fingerprint_bytes
from .timeline import build_timeline, event_facts, as_documents
from .verify import verify, verify_dependencies


def input_board(fen: str, history: dict | None):
    try:
        board = chess.Board(fen)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid_fen") from exc
    if not board.is_valid():
        raise ValueError("invalid_board_state")
    if history is None:
        return board, "unavailable"
    if not isinstance(history, dict) or not isinstance(history.get("moves"), list) or not isinstance(history.get("initial_fen"), str):
        raise ValueError("history requires initial_fen and a moves list")
    replay = chess.Board(history["initial_fen"])
    if not replay.is_valid():
        raise ValueError("invalid_history_root")
    for raw in history["moves"]:
        move = parse_legal_move(replay, raw)
        if move is None:
            raise ValueError("illegal_history_move")
        replay.push(move)
    if replay.fen() != board.fen():
        raise ValueError("history_does_not_match_fen")
    return replay, "complete_from_initial_position" if history["initial_fen"] == chess.STARTING_FEN else "provided_segment"


def explain_fen(fen: str, played_move=None, player_level=1200, history=None, *, config: ReasoningConfig) -> dict:
    if isinstance(player_level, bool) or not isinstance(player_level, int) or player_level < 0:
        raise ValueError("player_level must be a nonnegative integer")
    started = time.perf_counter()
    board, history_status = input_board(fen, history)
    played = parse_legal_move(board, played_move) if played_move is not None else None
    if played_move is not None and played is None:
        raise ValueError("illegal_played_move")
    history_id = fingerprint({"status": history_status, "history": history})
    result = {"schema_version": VERSION, "status": "insufficient_evidence", "reason_codes": [],
              "input": {"fen": board.fen(), "played_uci": played.uci() if played else None,
                        "player_level": player_level, "history_status": history_status},
              "context": {"side_to_move": "white" if board.turn else "black", "in_check": board.is_check(),
                          "legal_move_count": board.legal_moves.count(), "repetition_history": history_status},
              "candidates": [], "objectives": [], "hypotheses": {"accepted": [], "rejected": [], "incomplete": []},
              "timelines": [], "propositions": [], "invalid_propositions": [], "investigations": [],
              "searches": [], "selected_teaching_point": None, "coaching": {}, "search_scope": {"exhaustive": False}}
    result.update(sentence_admission=[], teaching_admission=[], resource_admission=[])
    terminal = board.outcome(claim_draw=False)
    if terminal is not None:
        result["context"]["terminal"] = {"termination": terminal.termination.name, "result": terminal.result()}
        result["reason_codes"] = ["terminal_position"]
        result["coaching"] = {"text": "This position is already over.", "sentences": []}
        result["runtime"] = {"wall_ms": round(1000 * (time.perf_counter() - started), 3), "query_count": 0}
        return result
    session = SearchSession(config, board.turn, history_id)
    roots, root_records, base_records = [], {}, {}
    # Mandatory played queries come before ranking/optional resources.
    if played is not None:
        roots.append(played)
        base_records[played.uci()] = session.query(board, "played", roots=[played])
        root_records[played.uci()] = session.query(board, "played_stability", roots=[played], nodes=config.stability_nodes)
    ranking = session.query(board, "root_ranking", width=config.rank_width)
    ranked_moves = [chess.Move.from_uci(line["root_uci"]) for line in ranking.lines]
    natural = [m for m in sorted(board.legal_moves, key=lambda x: x.uci()) if board.is_capture(m) or board.gives_check(m) or m.promotion]
    for move in [*ranked_moves, *natural]:
        if move not in roots and len(roots) < config.root_cap:
            roots.append(move)
    for move in roots:
        key = move.uci()
        if key not in base_records:
            base_records[key] = session.query(board, "alternative", roots=[move])
            root_records[key] = session.query(board, "alternative_stability", roots=[move], nodes=config.stability_nodes)
    complete = {key: r.lines[0] for key, r in root_records.items() if r.status == "complete_iteration" and r.lines}
    best = max(complete, key=lambda k: score_order(complete[k]["score"])) if complete else None
    comparison_status = "not_played"
    if played:
        base_complete = {key: r for key, r in base_records.items() if r.status == "complete_iteration" and r.lines}
        best_base = max(base_complete, key=lambda k: score_order(base_complete[k].lines[0]["score"])) if base_complete else None
        shallow_best = base_complete.get(best_base)
        shallow_played = base_records[played.uci()]
        shallow = comparison(shallow_best.lines[0]["score"] if shallow_best and shallow_best.lines else None,
                             shallow_played.lines[0]["score"] if shallow_played.lines else None, config.equivalence_cp)
        deep = comparison(complete[best]["score"] if best else None,
                          complete.get(played.uci(), {}).get("score"), config.equivalence_cp)
        comparison_status = deep if shallow == deep else "unstable" if "unknown" not in (shallow, deep) else "unknown"
        if comparison_status == "equivalent" and played.uci() == best:
            comparison_status = "played_is_best"
    result["context"]["comparison"] = comparison_status
    result["context"]["assessment"] = complete[best]["score"] if best else None
    result["context"]["best_searched_uci"] = best
    teaching_root = played.uci() if played and comparison_status in ("equivalent", "played_is_best") else best
    result["context"]["teaching_root_uci"] = teaching_root
    if played and best and comparison_status == "inferior":
        best_score = complete[best]["score"]
        played_score = complete.get(played.uci(), {}).get("score")
        if (played_score and best_score["kind"] == played_score["kind"] == "mate"
                and best_score["value"] > 0 and played_score["value"] > 0):
            result["context"]["mate_comparison"] = {
                "kind": "faster_mate", "best_in": best_score["value"], "played_in": played_score["value"],
                "played_san": board.san(played), "best_san": board.san(chess.Move.from_uci(best)),
                "evidence_class": "engine_search", "search_ids": [root_records[best].id, root_records[played.uci()].id]}
    if best and complete[best]["score"]["kind"] == "mate" and complete[best]["score"]["value"] <= 0:
        result["context"]["resistance_context"] = "engine_finds_mate_against_mover_even_after_best_searched_choice"
    facts, hypotheses, timelines = [], [], []
    primary = {}

    def add_line(moves, record, *, retain_hypotheses=True):
        line = build_timeline(board, moves, record.id, config.max_plies)
        line["evidence_origin"] = record.status
        line["source_query"] = {"purpose": record.purpose, "root_moves": record.root_moves,
            "start_ply": next((i for i, node in enumerate(line["nodes"]) if node["fen"] == record.fen), 0)}
        if any(t["id"] == line["id"] for t in timelines):
            return line
        timelines.append(line)
        branch_facts = event_facts(line)
        generated, extra = generate(line, branch_facts)
        facts.extend([*branch_facts, *extra])
        # Generate all objective families but cap retained hypotheses explicitly.
        for h in generated if retain_hypotheses else ():
            if len(hypotheses) < config.max_hypotheses:
                hypotheses.append(h)
        return line

    for move in roots:
        record = root_records[move.uci()]
        chosen = record if record.lines else base_records[move.uci()]
        if chosen.lines:
            primary[move.uci()] = add_line(chosen.lines[0]["moves_uci"], chosen)
        result["candidates"].append({"move_uci": move.uci(), "move_san": board.san(move),
            "role": "played" if move == played else "searched_alternative", "assessment": complete.get(move.uci(), {}).get("score"),
            "base_search_id": base_records[move.uci()].id, "stability_search_id": record.id})
    # A direct root action tied to both root score gaps precedes a local
    # counterfactual coverage witness. Do not call that witness the gap's cause.
    played_line = primary.get(played.uci()) if played else None
    direct_contrast = False
    if best and comparison_status == "inferior":
        for h in hypotheses:
            if h.root_uci == best:
                direct_contrast = attach_capture_contrast(h, played_line, primary.get(best), facts,
                    base_records, root_records, config.equivalence_cp) or direct_contrast
    # Comparative forcing evidence has priority over unrelated quiet routes.
    forcing_mechanism = None
    if not direct_contrast and played_line and best and played.uci() != best and comparison_status == "inferior" and len(played_line["events"]) >= 2:
        setup = played_line["moves_uci"][1]
        for build in (sequence_hypothesis, threat_hypothesis):
            candidate, extra = build(board, played.uci(), best, setup, session, add_line)
            if candidate is not None:
                facts.extend(extra)
                hypotheses.insert(0, candidate)
                hypotheses[:] = hypotheses[:config.max_hypotheses]
                forcing_mechanism = candidate
                break
    # Reserve useful work for quiet objectives before optional resources.
    quiet = next((h for h in hypotheses if h.root_uci == teaching_root and h.objective["kind"] == "castle"), None)
    if quiet is None:
        quiet = next((h for h in hypotheses if h.root_uci == teaching_root and h.objective["kind"] == "reach"), None)
    if quiet and not forcing_mechanism and not direct_contrast and session.can_query():
        investigation = investigate(board, chess.Move.from_uci(teaching_root), quiet.objective, session)
        result["investigations"].append(investigation)
        for witness in investigation["witnesses"]:
            record = next(r for r in session.records if r.id == witness["search_id"])
            witnessed = add_line(witness["moves_uci"], record, retain_hypotheses=False)
            achieved = [p for p in facts if p.timeline_id == witnessed["id"] and
                        ((quiet.objective["kind"] == "castle" and p.relation == "castles") or
                         (quiet.objective["kind"] == "reach" and p.relation == "reaches" and p.subject == quiet.objective["piece_id"] and p.object == quiet.objective["square"]))]
            if achieved:
                quiet.proposition_ids.extend(p.id for p in achieved)
                quiet.status = "supported_consequence"
        if investigation["status"] == "supported_scope":
            quiet.unresolved = ["comparative_cause_not_established", "quiet_policy_covers_searched_adequate_replies_only"]
    # Relevant legal responses are searched even when they do not feature in the main PV.
    resource_scopes = []
    for key in list(dict.fromkeys([teaching_root, best, played.uci() if played else None, *primary])):
        if not key or key not in primary:
            continue
        after = board.copy()
        after.push_uci(key)
        if after.is_game_over(claim_draw=False):
            continue
        replies = session.query(after, "opponent_resources", width=config.reply_width)
        searched = []
        for line in replies.lines:
            add_line([key, *line["moves_uci"]], replies, retain_hypotheses=False)
            searched.append(line["root_uci"])
        forcing = [m for m in sorted(after.legal_moves, key=lambda m: m.uci()) if after.is_capture(m) or after.gives_check(m) or m.promotion]
        for move in forcing:
            if move.uci() in searched or not session.can_query():
                continue
            record = session.query(after, "forcing_counterexample", roots=[move])
            if record.lines:
                add_line([key, *record.lines[0]["moves_uci"]], record, retain_hypotheses=False)
                searched.append(move.uci())
        legal = sorted(m.uci() for m in after.legal_moves)
        resource_scopes.append({"root_uci": key, "legal_replies": legal, "searched_replies": sorted(set(searched)),
                                "omitted_replies": sorted(set(legal) - set(searched))})
    for line in primary.values():
        for h in prevention_candidates(primary.get(played.uci()) if played else None, line, facts):
            if len(hypotheses) < config.max_hypotheses:
                hypotheses.append(h)
    # A later coaching event needs a fresh unrestricted opponent best reply at
    # the review's requested depth. The remaining existing allocation is its
    # hard node cap; an unfinished depth target supplies no permission to speak.
    reference = None
    root_line = primary.get(teaching_root)
    needs_later = any(h.root_uci == teaching_root and h.objective.get("root_connected")
        and h.objective["kind"] in ("capture", "checking_capture", "reach")
        and (h.objective.get("outcome_ply", 2) > 1) for h in hypotheses)
    if root_line and not direct_contrast and not forcing_mechanism and needs_later:
        remaining = config.max_total_nodes - session.requested_nodes
        if remaining > 0 and session.can_query(remaining):
            after = board.copy()
            after.push_uci(teaching_root)
            if not after.is_game_over(claim_draw=False):
                reference = session.query(after, "coaching_best_reply_depth20", nodes=remaining, depth=20)
        result["relevance_reference"] = {"search_id": reference.id if reference else None,
            "requested_depth": 20, "achieved_depth": reference.lines[0].get("depth", 0) if reference and reference.lines else None,
            "status": reference.status if reference else "unavailable_within_existing_budget"}
    line_lookup = {t["id"]: t for t in timelines}
    unique_facts = {p.id: p for p in facts}
    accepted_facts, invalid = {}, []
    for key, fact in sorted(unique_facts.items()):
        problem = verify(fact, line_lookup[fact.timeline_id])
        if problem:
            invalid.append({"proposition": asdict(fact), "reason": problem})
        else:
            accepted_facts[key] = asdict(fact)
    for h in hypotheses:
        challenge(h, timelines)
        missing = sorted(set(h.proposition_ids) - set(accepted_facts))
        dependency_problem = None if missing else verify_dependencies(h, accepted_facts, line_lookup,
            {r.id: r.document() for r in session.records})
        if missing or dependency_problem:
            h.status = "rejected"
            h.unresolved.append("proposition_failed_verification" if missing else dependency_problem)
        # A legal resource in one line is retained; counterexamples forbid a universal reading.
        if h.counterexamples and h.wording_strength != "exact_immediate_mate":
            h.wording_strength = "demonstrated_continuation_with_alternative_branches"
        document = asdict(h)
        bucket = "rejected" if h.status == "rejected" else "incomplete" if h.status == "incomplete_hypothesis" else "accepted"
        result["hypotheses"][bucket].append(document)
        if any(c["refutes"] in ("unavoidable_event_order", "unavoidable_castling_goal") for c in h.counterexamples):
            result["hypotheses"]["rejected"].append({**document, "id": fingerprint([h.id, "universal_reading"]),
                "status": "rejected", "wording_strength": "unavoidable", "unresolved": ["legal_counterexample_to_universal_reading"]})
    result["propositions"] = list(accepted_facts.values())
    result["invalid_propositions"] = invalid
    result["objectives"] = [{"hypothesis_id": h.id, **h.objective} for h in hypotheses]
    def admission(h):
        obj = h["objective"]
        if obj["kind"] in ("comparative_sequence", "comparative_threat"):
            return {"admitted": True, "reason": "verified_conditional_certificate", "search_ids": h["search_ids"]}
        relation = "clears_castling_path" if obj["kind"] == "castle" else "captures" if obj["kind"] in ("capture", "checking_capture") else "reaches" if obj["kind"] == "reach" else obj["kind"]
        choices = [accepted_facts[key] for key in h["proposition_ids"] if accepted_facts[key]["relation"] == relation
                   and accepted_facts[key]["timeline_id"] == obj.get("timeline_id")]
        if obj["kind"] == "reach":
            choices = [p for p in choices if p["subject"] == obj["piece_id"] and p["object"] == obj["square"]]
        if obj.get("outcome_ply"):
            choices = [p for p in choices if p["ply"] == obj["outcome_ply"]]
        if not choices:
            return {"admitted": False, "reason": "no_decisive_fact_link"}
        fact = min(choices, key=lambda p: (p["ply"], p["id"]))
        return admit_fact(fact, line_lookup[fact["timeline_id"]], root_line,
                          base_records.get(teaching_root), root_records.get(teaching_root), reference)

    selectable = []
    for h in result["hypotheses"]["accepted"]:
        if h["root_uci"] == teaching_root and h["objective"].get("root_connected"):
            decision = admission(h)
            result["teaching_admission"].append({"hypothesis_id": h["id"], **decision})
            if decision["admitted"]:
                selectable.append(h)
    # Experimental deterministic shortlist ordering, explicitly not a calibrated shipping rank.
    def teaching_order(h):
        return (h["objective"]["kind"] != "checkmates", not bool(h["objective"].get("root_capture_contrast")), h["status"] != "supported_mechanism",
                h["objective"]["kind"] not in ("comparative_sequence", "comparative_threat"), h["objective"]["kind"] != "checking_capture",
                h["objective"]["kind"] != "castle", not bool(h["dependencies"]), h["id"])
    selected = min(selectable, key=teaching_order) if selectable else None
    result["selected_teaching_point"] = selected
    result["status"] = selected["status"] if selected else "incomplete_hypothesis" if hypotheses else "insufficient_evidence"
    result["coaching"] = render(selected, accepted_facts, comparison_status, result["context"])
    if selected and selected["objective"]["kind"] == "castle":
        resources = [p for p in accepted_facts.values() if p["relation"] == "attacks_piece"
                     and p["actor"] != result["context"]["side_to_move"]
                     and line_lookup[p["timeline_id"]]["root_uci"] == selected["root_uci"]]
        eligible = []
        for p in resources:
            decision = admit_fact(p, line_lookup[p["timeline_id"]], root_line,
                base_records.get(teaching_root), root_records.get(teaching_root), reference)
            result["resource_admission"].append(decision)
            if decision["admitted"]:
                eligible.append(p)
        resource = min(eligible, key=lambda p: (p["ply"], p["id"])) if eligible else None
        result["coaching"] = add_resource(result["coaching"], resource)
    if selected:
        records = {r.id: r for r in session.records}
        for index, sentence in enumerate(result["coaching"].get("sentences", [])):
            conditional = selected["objective"]["kind"] in ("comparative_sequence", "comparative_threat")
            decisions = [] if conditional else [admit_fact(accepted_facts[key], line_lookup[accepted_facts[key]["timeline_id"]], root_line,
                base_records.get(teaching_root), root_records.get(teaching_root), reference) for key in sentence["proposition_ids"]
                if accepted_facts[key]["timeline_id"] == root_line["id"]]
            search_ids = set(sentence.get("search_ids", [])) | {sid for d in decisions for sid in d["search_ids"]}
            if conditional:
                search_ids.update(selected["search_ids"])
            result["sentence_admission"].append({"sentence_index": index, "frame": sentence["frame"],
                "admitted": all(d["admitted"] for d in decisions),
                "reason": "verified_conditional_certificate" if conditional else "root_action_or_depth20_agreement",
                "fact_admission": decisions, "search_ids": sorted(search_ids),
                "sources": [{"search_id": key, "purpose": records[key].purpose, "root_moves": records[key].root_moves,
                             "requested_depth": records[key].requested_depth} for key in sorted(search_ids) if key in records]})
        if result["coaching"].get("comparison_text"):
            result["sentence_admission"].append({"frame": "engine_comparison", "admitted": True,
                "reason": "original_root_search_comparison", "search_ids": sorted(set(selected["search_ids"]) | {r.id for key in (teaching_root, played.uci() if played else None) if key for r in (base_records[key], root_records[key])})})
        if result["coaching"].get("teaching_habit"):
            result["sentence_admission"].append({"frame": "teaching_habit", "admitted": True, "reason": "general_teaching_principle", "search_ids": []})
    result["timelines"] = timelines
    result["searches"] = [r.document() for r in session.records]
    result["search_scope"] = {"exhaustive": False, "resource_scopes": resource_scopes,
        "root_scope": {"legal_moves": sorted(m.uci() for m in board.legal_moves), "searched_moves": [m.uci() for m in roots],
                       "omitted_moves": sorted(set(m.uci() for m in board.legal_moves) - {m.uci() for m in roots})},
        "unresolved": selected["unresolved"] if selected else ["no_supported_teaching_point"],
        "hypotheses_capped": len(hypotheses) >= config.max_hypotheses,
        "stopping_reasons": sorted(set(r.stop_reason for r in session.records)),
        "quiet_investigation": "performed" if result["investigations"] else "not_completed_within_budget"}
    result["reproducibility"] = {**session.document(), "replay_version": STORED_LINE_VERIFIER_VERSION,
        "source_hashes": {p.name: fingerprint_bytes(p) for p in [*sorted(Path(__file__).parent.glob("*.py")), Path(__file__).parents[1] / "stored_line_verifier.py"]},
        "selection_policy": "review_v2_root_gap_then_conditional_then_depth20_agreement", "render_version": VERSION}
    result["runtime"] = {"wall_ms": round(1000 * (time.perf_counter() - started), 3), "query_count": session.executed_queries,
        "query_records": len(session.records),
        "requested_engine_nodes": session.requested_nodes, "actual_engine_nodes": sum(r.actual_nodes for r in session.records),
        "sampled_peak_engine_rss_bytes": max((r.runtime.get("sampled_child_rss_bytes") or 0 for r in session.records), default=0),
        "sampled_peak_parent_rss_bytes": max((r.runtime.get("sampled_parent_rss_bytes") or 0 for r in session.records), default=0),
        "sampled_peak_combined_rss_bytes": max((r.runtime.get("sampled_combined_rss_bytes") or 0 for r in session.records), default=0),
        "sampled_child_cpu_ms": sum(r.runtime.get("sampled_child_cpu_ms") or 0 for r in session.records),
        "reused_queries": "identical queries memoised by full position/history/settings"}
    if any(r.stop_reason == "query_or_node_budget_exhausted" for r in session.records):
        result["reason_codes"].append("budget_exhausted_partial_result")
    if comparison_status in ("unstable", "unknown"):
        result["reason_codes"].append("comparative_decision_unresolved")
    return result
