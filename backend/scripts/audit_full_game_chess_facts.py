#!/usr/bin/env python3
"""Offline audit of the anonymized 80-game ChessGuru evidence packet.

No Stockfish, MongoDB, network access, or production writes. The script reruns
the current deterministic category and detector code against stored engine
evidence, then applies independent board checks to factual caption claims.
"""

from __future__ import annotations

import inspect
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import chess

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from analysis_interpreter import AnalysisInterpreter
from scripts.audit_captions_for_why import (
    caption_shape,
    has_causal_connector,
    has_concrete_consequence,
    has_principle_ending,
)
from services.concept_detectors.registry import all_detectors
from services.caption_pipeline import (
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
    compute_severity_for_move,
)
from services.decryption_voice.concept_dispatcher import (
    detect_concepts,
    pick_dominant_renderable,
)
from services.opening_lookup import match_opening_for_mover


PACKET = BACKEND / "data/corpus_snapshots/full_game_chess_fact_audit_v1_2026-09-03.json"
SUPPLEMENT = BACKEND / "data/corpus_snapshots/full_game_chess_fact_classifier_inputs_v1_2026-09-03.json"
CALIBRATION = BACKEND / "data/corpus_snapshots/full_game_chess_fact_calibration_gold_v1_2026-09-03.json"
PIECE_VALUE = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
}
PIECE_TYPE = {
    "pawn": chess.PAWN, "knight": chess.KNIGHT, "bishop": chess.BISHOP,
    "rook": chess.ROOK, "queen": chess.QUEEN, "king": chess.KING,
}
EXTRA_KWARGS = (
    "move_number", "opening_name", "move_history_san",
    "best_move_san", "best_move_uci",
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_move(board: chess.Board, token: str) -> chess.Move:
    try:
        move = chess.Move.from_uci(str(token))
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    return board.parse_san(str(token))


def user_eval(value, user_color):
    if value is None:
        return None
    value = float(value)
    return value if user_color == "white" else -value


def material_diff(board: chess.Board, side: chess.Color) -> int:
    own = sum(PIECE_VALUE[p] * len(board.pieces(p, side)) for p in PIECE_VALUE)
    opp = sum(PIECE_VALUE[p] * len(board.pieces(p, not side)) for p in PIECE_VALUE)
    return own - opp


def line_facts(fen: str, first: str, continuation):
    board = chess.Board(fen)
    mover = board.turn
    base = material_diff(board, mover)
    first_move = parse_move(board, first)
    first_capture = board.piece_at(first_move.to_square)
    first_piece = board.piece_at(first_move.from_square)
    first_is_capture = board.is_capture(first_move)
    board.push(first_move)
    facts = {
        "base_material": base,
        "first_piece": first_piece.piece_type if first_piece else None,
        "first_captured": first_capture.piece_type if first_capture else None,
        "first_is_capture": first_is_capture,
        "first_is_check": board.is_check(),
        "mate_by_mover": board.is_checkmate() and board.turn != mover,
        "mate_by_opponent": board.is_checkmate() and board.turn == mover,
        "material_path": [],
        "moves": [],
    }
    for index, token in enumerate((continuation or [])[:4]):
        try:
            move = parse_move(board, token)
        except Exception:
            break
        actor = board.turn
        capture = board.piece_at(move.to_square)
        san = board.san(move)
        board.push(move)
        facts["moves"].append({
            "index": index,
            "actor_is_mover": actor == mover,
            "san": san,
            "capture_type": capture.piece_type if capture else None,
            "to": chess.square_name(move.to_square),
            "mate": board.is_checkmate(),
        })
        facts["material_path"].append(material_diff(board, mover))
        if board.is_checkmate():
            if actor == mover:
                facts["mate_by_mover"] = True
            else:
                facts["mate_by_opponent"] = True
    facts["final_material"] = (
        facts["material_path"][-1] if facts["material_path"] else material_diff(board, mover)
    )
    facts["min_material"] = min([base] + facts["material_path"])
    facts["max_material"] = max([base] + facts["material_path"])
    return facts


def hard_gold_candidate(move, user_color):
    played = line_facts(
        move["fen_before"], move["played_uci"], move.get("pv_after_played")
    )
    best = line_facts(
        move["fen_before"],
        move.get("best_move_uci") or move.get("best_move_san"),
        move.get("pv_after_best"),
    )
    before_eval = user_eval(move.get("eval_before"), user_color)
    after_eval = user_eval(move.get("eval_after"), user_color)
    if best["mate_by_mover"] and not played["mate_by_mover"]:
        return "missed_tactic"
    if (
        played["mate_by_opponent"]
        or (
            after_eval is not None and after_eval <= -9000
            and (before_eval is None or before_eval > -9000)
        )
    ):
        return "king_safety"
    if played["final_material"] <= played["base_material"] - 3:
        # An equal capture-and-recapture is a trade, not a hang.
        equal_trade = (
            played["first_is_capture"]
            and played["first_piece"] is not None
            and played["first_captured"] is not None
            and PIECE_VALUE[played["first_captured"]] >= PIECE_VALUE[played["first_piece"]]
            and played["final_material"] >= played["base_material"]
        )
        if not equal_trade:
            return "piece_safety"
    if (
        best["final_material"] >= played["final_material"] + 3
        or (int(move.get("cp_loss") or 0) >= 150 and (best["first_is_capture"] or best["first_is_check"]))
    ):
        return "missed_tactic"
    if move.get("phase") == "endgame":
        return "endgame_technique"
    if move.get("phase") == "opening":
        return "opening_knowledge"
    return None


def fresh_category(interpreter, move, raw):
    board = chess.Board(move["fen_before"])
    played = parse_move(board, move["played_uci"])
    board.push(played)
    item = {
        "move_number": move.get("move_number"),
        "move": move.get("played_san"),
        "move_san": move.get("played_san"),
        "move_uci": move.get("played_uci"),
        "fen_before": move.get("fen_before"),
        "fen_after": board.fen(),
        "cp_loss": move.get("cp_loss"),
        "eval_before": move.get("eval_before"),
        "eval_after": move.get("eval_after"),
        "eval_swing": raw.get("eval_swing"),
        "is_turning_point": raw.get("is_turning_point"),
        "evaluation": raw.get("evaluation"),
        "best_move": move.get("best_move_san"),
        "best_move_uci": move.get("best_move_uci"),
        "pv_after_best": move.get("pv_after_best") or [],
        "pv_after_played": move.get("pv_after_played") or [],
        "mate_info": move.get("stored_mate_info"),
        "threat": move.get("stored_threat"),
    }
    return interpreter._interpret_single_move(item, future_moves=[]).cognitive_gap


def opening_name(game):
    value = game.get("opening")
    if isinstance(value, dict):
        return value.get("name") or value.get("opening_name")
    return value if isinstance(value, str) else None


def mastery_detector_results(game, move):
    board = chess.Board(move["fen_before"])
    played = parse_move(board, move["played_uci"])
    kwargs_all = {
        "move_number": move.get("move_number"),
        "opening_name": opening_name(game),
        "move_history_san": game["moves_san"][: move["ply"] - 1],
        "best_move_san": move.get("best_move_san"),
        "best_move_uci": move.get("best_move_uci"),
    }
    results = []
    errors = []
    for skill_id, detector in all_detectors().items():
        accepted = inspect.signature(detector).parameters
        kwargs = {key: value for key, value in kwargs_all.items() if key in accepted}
        try:
            verdict = detector(board, played, board.turn, **kwargs)
        except Exception as exc:
            errors.append((skill_id, type(exc).__name__))
            continue
        if verdict == "applied":
            results.append((skill_id, "applied"))
        elif verdict == "missed":
            results.append((skill_id, "wrong"))
    return results, errors


def mate_against_user(move, user_color):
    info = move.get("stored_mate_info") or {}
    after = info.get("after")
    if after is None:
        return None
    if user_color == "white" and after < 0:
        return -after
    if user_color == "black" and after > 0:
        return after
    return None


def verify_pin_claim(caption, move, user_color):
    match = re.search(
        r"Your (pawn|knight|bishop|rook|queen) on ([a-h][1-8]) is pinned "
        r"to your king by the (knight|bishop|rook|queen) on ([a-h][1-8])",
        caption,
        re.I,
    )
    if not match:
        return None
    board = chess.Board(move["fen_before"])
    color = chess.WHITE if user_color == "white" else chess.BLACK
    target = chess.parse_square(match.group(2))
    pinner = chess.parse_square(match.group(4))
    target_piece = board.piece_at(target)
    pinner_piece = board.piece_at(pinner)
    ok = (
        target_piece is not None and target_piece.color == color
        and target_piece.piece_type == PIECE_TYPE[match.group(1).lower()]
        and pinner_piece is not None and pinner_piece.color != color
        and pinner_piece.piece_type == PIECE_TYPE[match.group(3).lower()]
        and board.is_pinned(color, target)
    )
    return None if ok else "unsupported_pin_claim"


def verify_trade_language(caption, move):
    board = chess.Board(move["fen_before"])
    mover = board.turn
    played = parse_move(board, move["played_uci"])
    moved_piece = board.piece_at(played.from_square)
    captured = board.piece_at(played.to_square)
    if re.search(r"hangs your (pawn|knight|bishop|rook|queen)", caption, re.I):
        if (
            captured is not None and moved_piece is not None
            and PIECE_VALUE[captured.piece_type] >= PIECE_VALUE[moved_piece.piece_type]
        ):
            return "equal_or_better_trade_misframed_as_hang"

    win = re.search(
        r"wins your (pawn|knight|bishop|rook|queen) on ([a-h][1-8])",
        caption,
        re.I,
    )
    if not win:
        return None
    wanted_piece = PIECE_TYPE[win.group(1).lower()]
    wanted_square = win.group(2).lower()
    board.push(played)
    line = move.get("pv_after_played") or []
    for index, token in enumerate(line[:4]):
        try:
            reply = parse_move(board, token)
        except Exception:
            break
        actor = board.turn
        captured_piece = board.piece_at(reply.to_square)
        to_square = chess.square_name(reply.to_square)
        board.push(reply)
        if (
            actor != mover and captured_piece is not None
            and captured_piece.color == mover
            and captured_piece.piece_type == wanted_piece
            and to_square == wanted_square
        ):
            if index + 1 < len(line):
                try:
                    recapture = parse_move(board, line[index + 1])
                    if board.turn == mover and board.is_capture(recapture) and recapture.to_square == reply.to_square:
                        return "recapturable_trade_misframed_as_win"
                except Exception:
                    pass
            return None
    return "claimed_capture_not_in_stored_played_line"


def verify_mate_direction(caption, move):
    if not re.search(r"allows mate (?:in \d+|next move)", caption, re.I):
        return None
    played = line_facts(
        move["fen_before"], move["played_uci"], move.get("pv_after_played")
    )
    best = line_facts(
        move["fen_before"],
        move.get("best_move_uci") or move.get("best_move_san"),
        move.get("pv_after_best"),
    )
    if not played["mate_by_opponent"] and best["mate_by_mover"]:
        return "missed_mate_misframed_as_allowed_mate"
    return None


def _rating_for_band(rating_band):
    return {
        "600-899": 750,
        "900-1199": 1050,
        "1200-1499": 1350,
        "1500-1999": 1750,
    }[rating_band]


def _eval_record(move, raw):
    return {
        "move_number": move.get("move_number"),
        "move": move.get("played_san"),
        "move_san": move.get("played_san"),
        "move_uci": move.get("played_uci"),
        "fen_before": move.get("fen_before"),
        "fen_after": move.get("fen_after"),
        "cp_loss": move.get("cp_loss"),
        "eval_before": move.get("eval_before"),
        "eval_after": move.get("eval_after"),
        "evaluation": raw.get("evaluation"),
        "eval_swing": raw.get("eval_swing"),
        "is_turning_point": raw.get("is_turning_point"),
        "is_best": raw.get("is_best"),
        "is_brilliant": raw.get("is_brilliant"),
        "is_sacrifice": raw.get("is_sacrifice"),
        "best_move": move.get("best_move_san"),
        "best_move_san": move.get("best_move_san"),
        "best_move_uci": move.get("best_move_uci"),
        "pv_after_played": move.get("pv_after_played") or [],
        "pv_after_best": move.get("pv_after_best") or [],
        "mate_info": move.get("stored_mate_info"),
        "threat": move.get("stored_threat"),
    }


def render_current_central_pipeline(game, raw_index):
    """Replay the current pure v140 caption door over one complete game.

    Only stored evidence is supplied. Fresh engine verification is explicitly
    disabled, so this audit cannot start Stockfish. Missing below-threshold
    evaluations are represented as quiet moves; every audited meaningful
    decision retains its complete stored engine packet.
    """
    meaningful = {move["ply"]: move for move in game["meaningful_decisions"]}
    eval_by_ply = {}
    for ply, move in meaningful.items():
        raw = raw_index[(game["anonymous_game_key"], ply)]
        eval_by_ply[ply] = _eval_record(move, raw)
    eval_lookup = {
        " ".join(row["fen_before"].split()[:4]): row
        for row in eval_by_ply.values()
    }
    move_evaluations = list(eval_by_ply.values())
    state = CrossMoveState()
    shapes_fired = set()
    board_state_window = []
    history = []
    board = chess.Board(game["initial_fen"])
    previous = None
    rendered = {}
    for ply, uci in enumerate(game["moves_uci"], 1):
        move = chess.Move.from_uci(uci)
        san = board.san(move)
        is_white = board.turn == chess.WHITE
        is_user = is_white == (game["user_color"] == "white")
        evidence = meaningful.get(ply)
        record = eval_by_ply.get(ply, {})
        cp_loss = int(record.get("cp_loss") or 0) if is_user else 0
        eval_before = record.get("eval_before")
        eval_after = record.get("eval_after")
        if is_user and eval_before is not None and eval_after is not None:
            before_user = user_eval(eval_before, game["user_color"])
            after_user = user_eval(eval_after, game["user_color"])
            cp_loss = max(cp_loss, int(max(0, before_user - after_user)))
        post_user = user_eval(eval_after, game["user_color"])
        severity = compute_severity_for_move(
            cp_loss=cp_loss,
            opp_cp_loss=0,
            is_user=is_user,
            is_white=is_white,
            user_color=game["user_color"],
            mate_sentinel_eval_cp=post_user,
            user_eval_before_white_pov=eval_before,
            user_eval_after_white_pov=eval_after,
            opp_eval_before=None,
            opp_eval_after=None,
            board_before=board,
            played_move=move,
            prev_move=previous,
        ).severity_user_facing
        best = record.get("best_move_san")
        if is_user and best and best.rstrip("!?+#") == san.rstrip("!?+#"):
            severity = "good"
        mover_color = "white" if is_white else "black"
        try:
            opening_record = match_opening_for_mover(history + [san], mover_color)
        except Exception:
            opening_record = None
        decision = build_move_teaching_decision(
            MoveInputs(
                fen_before=board.fen(),
                played_san=san,
                mover_is_user=is_user,
                mover_is_white=is_white,
                user_color=game["user_color"],
                full_move_number=board.fullmove_number,
                move_history_san=list(history),
                prev_move_san=history[-1] if history else None,
                best_move_san=best,
                eval_before_cp=eval_before,
                eval_after_cp=eval_after,
                cp_loss=cp_loss,
                pv_after_played=record.get("pv_after_played") or [],
                pv_after_best=record.get("pv_after_best") or [],
                opening_name=opening_name(game),
                user_rating=_rating_for_band(game["rating_band"]),
                prev_move_uci=previous.uci() if previous else None,
                best_move_uci=record.get("best_move_uci"),
                player_context_shadow_only=True,
                allow_fresh_engine_verification=False,
            ),
            state,
            shapes_fired_this_game=shapes_fired,
            bs_recent_window=board_state_window,
            game_trap_fires=game.get("trap_fires") or [],
            eval_lookup=eval_lookup,
            move_evaluations=move_evaluations,
            opening_record=opening_record,
            severity_override=severity,
        )
        mutations = decision.state_mutations
        state.fired_principles.update(mutations.fired_principles_added)
        state.fired_state_keys.update(mutations.fired_state_keys_added)
        if mutations.active_trap_cleared:
            state.active_trap = None
        elif mutations.active_trap_after is not None:
            state.active_trap = mutations.active_trap_after
        state.active_trap_step_cursor = mutations.active_trap_step_cursor_after
        state.active_trap_setup_completed_by_user = (
            mutations.active_trap_setup_completed_by_user_after
        )
        if mutations.prev_user_eval_after is not None:
            state.prev_user_eval_after = mutations.prev_user_eval_after
        state.conductor_threads_pulled.update(
            mutations.conductor_threads_pulled_added
        )
        if evidence is not None:
            rendered[ply] = {
                "caption": decision.text.caption,
                "rule_name": decision.text.rule_name,
                "primary_reason": decision.debug_facts.get("primary_reason"),
                "final_verified": decision.explanation.final_verified,
                "confidence": decision.explanation.confidence,
                "severity": decision.teaching_meta.severity,
                "should_skip": decision.should_skip,
                "skip_reason": decision.skip_reason,
            }
        board.push(move)
        history.append(san)
        previous = move
    return rendered


def audit_caption_record(record, move, game):
    caption = record.get("caption") or ""
    if not caption:
        return {
            "present": False, "why_obligation": False, "why_fail": False,
            "why_shape": None, "claims_tested": 0, "failures": [],
        }
    severity = str(
        record.get("severity") or record.get("severity_canonical") or ""
    ).lower()
    why_obligation = (
        int(move.get("cp_loss") or 0) >= 100
        or severity in {"mistake", "blunder"}
    )
    has_why = (
        has_concrete_consequence(
            caption, move["played_san"], move.get("best_move_san")
        )
        or has_causal_connector(caption)
        or has_principle_ending(caption)
    )
    why_fail = why_obligation and not has_why
    failures = []
    claims_tested = 0
    pin = verify_pin_claim(caption, move, game["user_color"])
    if pin:
        claims_tested += 1
        failures.append(pin)
    elif re.search(r" is pinned to your king by the ", caption, re.I):
        claims_tested += 1
    trade = verify_trade_language(caption, move)
    if trade:
        claims_tested += 1
        failures.append(trade)
    elif re.search(
        r"(hangs your|wins your .* on [a-h][1-8])", caption, re.I
    ):
        claims_tested += 1
    mate = verify_mate_direction(caption, move)
    if mate:
        claims_tested += 1
        failures.append(mate)
    elif re.search(r"allows mate (?:in d+|next move)", caption, re.I):
        claims_tested += 1
    fact_category = (
        (record.get("caption_facts_primary_reason") or {}).get("category")
        or (record.get("primary_reason") or {}).get("category")
    )
    if (
        int(move.get("cp_loss") or 0) >= 150
        and fact_category == "good_move"
    ):
        claims_tested += 1
        failures.append("meaningful_error_praised_as_good_move")
    return {
        "present": True,
        "why_obligation": why_obligation,
        "why_fail": why_fail,
        "why_shape": caption_shape(caption) if why_fail else None,
        "claims_tested": claims_tested,
        "failures": sorted(set(failures)),
    }


def main():
    packet = load(PACKET)
    supplement = load(SUPPLEMENT)
    calibration = load(CALIBRATION)
    raw_index = {
        (game["anonymous_game_key"], row["ply"]): row
        for game in supplement["games"] for row in game["decisions"]
    }
    gold_index = {
        (row["anonymous_game_key"], row["ply"]): row
        for row in calibration["entries"]
    }
    interpreter = AnalysisInterpreter()
    category_distribution = Counter()
    stored_distribution = Counter()
    category_drift = Counter()
    hard_distribution = Counter()
    hard_vs_current = Counter()
    hard_covered = 0
    hard_current_matches = 0
    classifier_errors = Counter()
    mastery_fires = Counter()
    mastery_outcomes = Counter()
    mastery_errors = Counter()
    review_patterns = Counter()
    review_dominant = Counter()
    review_positions_with_any = 0
    caption_total = 0
    why_total = 0
    why_fail = 0
    why_shapes = Counter()
    caption_rules = Counter()
    hard_category_stats = defaultdict(Counter)
    exact_claims_tested = 0
    exact_fail_positions = {}
    current_render_errors = Counter()
    current_caption_total = 0
    current_why_total = 0
    current_why_fail = 0
    current_why_shapes = Counter()
    current_caption_rules = Counter()
    current_exact_claims_tested = 0
    current_exact_fail_positions = {}
    current_without_caption_positions = {}
    stored_vs_current_caption_changed = 0
    fresh_by_key = {}
    hard_by_key = {}

    for game in packet["games"]:
        try:
            current_rendered = render_current_central_pipeline(game, raw_index)
        except Exception as exc:
            current_render_errors[type(exc).__name__] += 1
            current_rendered = {}
        # Mastery detectors are designed to recognize both successful and
        # failed concept applications, so audit every user move rather than
        # only the mistake subset used by Game Review.
        meaningful_by_ply = {
            move["ply"]: move for move in game["meaningful_decisions"]
        }
        board = chess.Board(game["initial_fen"])
        for ply, uci in enumerate(game["moves_uci"], 1):
            played = chess.Move.from_uci(uci)
            if board.turn == (chess.WHITE if game["user_color"] == "white" else chess.BLACK):
                evidence = meaningful_by_ply.get(ply) or {
                    "ply": ply,
                    "move_number": board.fullmove_number,
                    "fen_before": board.fen(),
                    "played_uci": uci,
                    "played_san": board.san(played),
                }
                detections, errors = mastery_detector_results(game, evidence)
                if detections:
                    mastery_fires["positions_with_any"] += 1
                for skill_id, outcome in detections:
                    mastery_fires[skill_id] += 1
                    mastery_outcomes[outcome] += 1
                for skill_id, error in errors:
                    mastery_errors[f"{skill_id}:{error}"] += 1
            board.push(played)

        for move in game["meaningful_decisions"]:
            key = (game["anonymous_game_key"], move["ply"])
            raw = raw_index[key]
            stored = move.get("stored_cognitive_gap") or "NONE"
            stored_distribution[stored] += 1
            try:
                fresh = fresh_category(interpreter, move, raw)
            except Exception as exc:
                classifier_errors[type(exc).__name__] += 1
                fresh = None
            fresh_name = fresh or "NONE"
            fresh_by_key[key] = fresh
            category_distribution[fresh_name] += 1
            if fresh_name != stored:
                category_drift[f"{stored}->{fresh_name}"] += 1
            hard = hard_gold_candidate(move, game["user_color"])
            hard_by_key[key] = hard
            hard_distribution[hard or "NONE"] += 1
            if hard:
                hard_covered += 1
                hard_category_stats[hard]["decisions"] += 1
                hard_category_stats[hard]["fresh_classifier_match"] += int(hard == fresh)
                hard_category_stats[hard]["fresh_classifier_silent"] += int(fresh is None)
                hard_vs_current[f"{hard}->{fresh_name}"] += 1
                hard_current_matches += int(hard == fresh)

            try:
                concepts = detect_concepts(
                    fen_before=move["fen_before"],
                    user_move_san=move["played_san"],
                    best_move_san=move.get("best_move_san"),
                    engine_mate_in_after=mate_against_user(move, game["user_color"]),
                    pv_after_best=move.get("pv_after_best") or [],
                    pv_after_played=move.get("pv_after_played") or [],
                    user_color=game["user_color"],
                )
                if concepts:
                    review_positions_with_any += 1
                    if hard:
                        hard_category_stats[hard]["review_detector_any"] += 1
                for concept in concepts:
                    review_patterns[concept.get("pattern_type") or "UNKNOWN"] += 1
                dominant = pick_dominant_renderable(concepts)
                if dominant:
                    review_dominant[dominant.get("pattern_type") or "UNKNOWN"] += 1
            except Exception as exc:
                review_patterns[f"ERROR:{type(exc).__name__}"] += 1

            current = move.get("current_review") or {}
            caption = current.get("caption") or ""
            if not caption:
                continue
            caption_total += 1
            caption_rules[current.get("rule_name") or "NONE"] += 1
            severity = str(current.get("severity") or current.get("severity_canonical") or "").lower()
            if int(move.get("cp_loss") or 0) >= 100 or severity in {"mistake", "blunder"}:
                why_total += 1
                has_why = (
                    has_concrete_consequence(caption, move["played_san"], move.get("best_move_san"))
                    or has_causal_connector(caption)
                    or has_principle_ending(caption)
                )
                if not has_why:
                    why_fail += 1
                    if hard:
                        hard_category_stats[hard]["caption_why_fail"] += 1
                    why_shapes[caption_shape(caption)] += 1

            failures = []
            pin = verify_pin_claim(caption, move, game["user_color"])
            if pin:
                exact_claims_tested += 1
                failures.append(pin)
            elif re.search(r" is pinned to your king by the ", caption, re.I):
                exact_claims_tested += 1
            trade = verify_trade_language(caption, move)
            if trade:
                exact_claims_tested += 1
                failures.append(trade)
            elif re.search(r"(hangs your|wins your .* on [a-h][1-8])", caption, re.I):
                exact_claims_tested += 1
            mate = verify_mate_direction(caption, move)
            if mate:
                exact_claims_tested += 1
                failures.append(mate)
            elif re.search(r"allows mate (?:in \d+|next move)", caption, re.I):
                exact_claims_tested += 1
            fact_category = ((current.get("caption_facts_primary_reason") or {}).get("category"))
            if (
                int(move.get("cp_loss") or 0) >= 150
                and fact_category == "good_move"
            ):
                exact_claims_tested += 1
                failures.append("meaningful_error_praised_as_good_move")
            if failures:
                if hard:
                    hard_category_stats[hard]["proven_exact_caption_failure"] += 1
                position_key = "{}:p{}".format(
                    game["anonymous_game_key"][:12], move["ply"]
                )
                exact_fail_positions[position_key] = {
                    "reasons": sorted(set(failures)),
                    "played": move["played_san"],
                    "best": move.get("best_move_san"),
                    "cp_loss": move.get("cp_loss"),
                    "caption": caption,
                    "rule_name": current.get("rule_name"),
                }

            current_v140 = current_rendered.get(move["ply"]) or {}
            if (
                (current_v140.get("caption") or "")
                != (current.get("caption") or "")
            ):
                stored_vs_current_caption_changed += 1
            current_check = audit_caption_record(
                current_v140, move, game
            )
            if current_check["present"]:
                current_caption_total += 1
                current_caption_rules[
                    current_v140.get("rule_name") or "NONE"
                ] += 1
            else:
                position_key = "{}:p{}".format(
                    game["anonymous_game_key"][:12], move["ply"]
                )
                current_without_caption_positions[position_key] = {
                    "played": move["played_san"],
                    "best": move.get("best_move_san"),
                    "cp_loss": move.get("cp_loss"),
                    "rule_name": current_v140.get("rule_name"),
                    "final_verified": current_v140.get("final_verified"),
                    "should_skip": current_v140.get("should_skip"),
                    "skip_reason": current_v140.get("skip_reason"),
                }
            if current_check["why_obligation"]:
                current_why_total += 1
            if current_check["why_fail"]:
                current_why_fail += 1
                current_why_shapes[current_check["why_shape"]] += 1
            current_exact_claims_tested += current_check["claims_tested"]
            if current_check["failures"]:
                position_key = "{}:p{}".format(
                    game["anonymous_game_key"][:12], move["ply"]
                )
                current_exact_fail_positions[position_key] = {
                    "reasons": current_check["failures"],
                    "played": move["played_san"],
                    "best": move.get("best_move_san"),
                    "cp_loss": move.get("cp_loss"),
                    "caption": current_v140.get("caption"),
                    "rule_name": current_v140.get("rule_name"),
                    "final_verified": current_v140.get("final_verified"),
                }

    calibration_rows = []
    current_correct = 0
    builder_correct = 0
    for gold in calibration["entries"]:
        key = (gold["anonymous_game_key"], gold["ply"])
        fresh = fresh_by_key.get(key)
        expected_builder = (
            gold["gold_primary_category"]
            if gold["automation_tier"] == "engine_hard" else None
        )
        builder = hard_by_key.get(key)
        current_ok = fresh == gold["gold_primary_category"]
        builder_ok = builder == expected_builder
        current_correct += int(current_ok)
        builder_correct += int(builder_ok)
        calibration_rows.append({
            "sample_key": gold["sample_key"],
            "gold": gold["gold_primary_category"],
            "fresh_current": fresh,
            "hard_builder": builder,
            "expected_builder": expected_builder,
            "current_correct": current_ok,
            "builder_correct": builder_ok,
        })

    total = packet["summary"]["total_meaningful_user_decisions"]
    report = {
        "schema_version": "full_game_chess_fact_audit_report.v1",
        "scope": {
            "games": len(packet["games"]),
            "complete_plies": packet["summary"]["total_complete_plies"],
            "user_moves": packet["summary"]["total_user_moves"],
            "meaningful_decisions": total,
            "stockfish_rerun": False,
        },
        "calibration": {
            "n": len(calibration_rows),
            "fresh_current_exact": current_correct,
            "fresh_current_exact_rate": round(current_correct / len(calibration_rows), 4),
            "hard_builder_exact": builder_correct,
            "hard_builder_exact_rate": round(builder_correct / len(calibration_rows), 4),
            "builder_trusted_for_batch": builder_correct / len(calibration_rows) >= 0.85,
            "rows": calibration_rows,
        },
        "fresh_classifier": {
            "distribution": dict(category_distribution.most_common()),
            "unclassified": category_distribution["NONE"],
            "unclassified_rate": round(category_distribution["NONE"] / total, 4),
            "stored_distribution": dict(stored_distribution.most_common()),
            "stored_vs_fresh_mismatches": sum(category_drift.values()),
            "stored_vs_fresh_mismatch_rate": round(sum(category_drift.values()) / total, 4),
            "top_drift": dict(category_drift.most_common(20)),
            "errors": dict(classifier_errors),
        },
        "validated_hard_gold_batch": {
            "distribution": dict(hard_distribution.most_common()),
            "covered_decisions": hard_covered,
            "coverage_rate": round(hard_covered / total, 4),
            "fresh_current_matches": hard_current_matches,
            "fresh_current_match_rate": round(
                hard_current_matches / hard_covered, 4
            ) if hard_covered else None,
            "confusion": dict(hard_vs_current.most_common()),
            "by_category": {
                category: dict(counts)
                for category, counts in sorted(hard_category_stats.items())
            },
        },
        "mastery_detector_registry": {
            "registered_detectors": len(all_detectors()),
            "user_moves_audited": packet["summary"]["total_user_moves"],
            "moves_with_stored_best_evidence": total,
            "reach_interpretation": (
                "Lower-bound smoke test only: positive-only application "
                "detectors require stored best-move evidence, which this "
                "privacy-safe packet retains only for meaningful decisions. "
                "Use current_detector_fires_2026-09-03.json for corpus reach."
            ),
            "positions_with_any_fire": mastery_fires.pop("positions_with_any", 0),
            "total_fires": sum(mastery_fires.values()),
            "outcomes": dict(mastery_outcomes),
            "fires_by_skill": dict(mastery_fires.most_common()),
            "errors": dict(mastery_errors.most_common()),
        },
        "game_review_detector_dispatcher": {
            "positions_with_any_detection": review_positions_with_any,
            "coverage_rate": round(review_positions_with_any / total, 4),
            "all_patterns": dict(review_patterns.most_common()),
            "dominant_renderable": dict(review_dominant.most_common()),
        },
        "captions": {
            "stored_caption_versions": {
                "135": 72,
                "136": 6,
                "137": 1,
                "140": 1,
                "current_code_version": 140,
            },
            "positions_with_caption": caption_total,
            "caption_coverage_rate": round(caption_total / total, 4),
            "why_obligation_count": why_total,
            "why_fail_count": why_fail,
            "why_fail_rate": round(why_fail / why_total, 4) if why_total else None,
            "top_why_fail_shapes": dict(why_shapes.most_common(10)),
            "caption_rules": dict(caption_rules.most_common(25)),
            "exact_claims_tested": exact_claims_tested,
            "positions_with_proven_exact_failure": len(exact_fail_positions),
            "proven_exact_failure_lower_bound_rate": round(
                len(exact_fail_positions) / caption_total, 4
            ) if caption_total else None,
            "proven_failures": exact_fail_positions,
        },
        "current_v140_central_caption_replay": {
            "method": (
                "Pure central caption pipeline replay with full game state, "
                "stored evidence only, and fresh engine verification disabled."
            ),
            "rating_assumption": (
                "Band midpoint; exact per-account current rating was excluded "
                "from the anonymized packet."
            ),
            "below_threshold_assumption": (
                "Moves absent from the evidence packet are replayed as quiet "
                "moves; all 467 audited decisions retain stored engine facts."
            ),
            "render_errors": dict(current_render_errors),
            "stored_caption_text_changed": stored_vs_current_caption_changed,
            "positions_with_caption": current_caption_total,
            "positions_without_caption": len(current_without_caption_positions),
            "without_caption_positions": current_without_caption_positions,
            "truth_boundary_withheld": sum(
                "FINAL_VERIFY_SILENT" in str(row.get("rule_name") or "")
                for row in current_without_caption_positions.values()
            ),
            "caption_coverage_rate": round(
                current_caption_total / total, 4
            ),
            "why_obligation_count": current_why_total,
            "why_fail_count": current_why_fail,
            "why_fail_rate": round(
                current_why_fail / current_why_total, 4
            ) if current_why_total else None,
            "top_why_fail_shapes": dict(current_why_shapes.most_common(10)),
            "caption_rules": dict(current_caption_rules.most_common(25)),
            "exact_claims_tested": current_exact_claims_tested,
            "positions_with_proven_exact_failure": len(
                current_exact_fail_positions
            ),
            "proven_exact_failure_lower_bound_rate": round(
                len(current_exact_fail_positions) / current_caption_total, 4
            ) if current_caption_total else None,
            "proven_failures": current_exact_fail_positions,
        },
        "limitations": [
            "The exact-claim rate is a lower bound: only machine-falsifiable phrasing families are counted.",
            "The conservative hard builder is scored on 16 manually reasoned positions before any batch category claim.",
            "Positional mechanism quality still requires human/Codex review when the hard builder abstains.",
            "The v140 replay excludes account memory, authored overrides, opponent-only engine rows, and exact per-account rating; it is a pure central-pipeline truth audit, not a byte-for-byte API response.",
            "The 80-game packet cannot estimate positive mastery-detector reach because quiet moves do not carry stored best-move evidence; the separate full-corpus census is authoritative for reach.",
        ],
    }
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
