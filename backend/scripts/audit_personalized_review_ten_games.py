"""Read-only ten-game audit for the Personalized Game Review product.

Reconstructs current deterministic review decisions from stored Stockfish
evidence. It performs no engine runs, LLM calls, or database writes.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping

import chess
import chess.pgn
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_captions_for_why import (
    has_causal_connector,
    has_concrete_consequence,
    has_principle_ending,
)
from services.caption_facts import (
    LegalMaterialLossCause,
    verified_move_purposes,
)
from services.caption_pipeline import CrossMoveState, MoveInputs, build_move_teaching_decision
from services.game_review_planner import build_shadow_game_teaching_plan
from services.game_review_shadow_runtime import (
    adapt_review_event,
    derive_current_review_observations,
)
from services.narrator_claim_verifier import verify_caption
from services.review_reflection_service import build_review_event_reflection_prompt


QUALITY_V2_ENV = {
    "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
    "PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED": "true",
}


ACCOUNT_EMAIL = "bhutramohit@gmail.com"
GAME_IDS = (
    "100897b9-0989-47db-b114-fe7064cecd4d",
    "3a41fb4c-a229-49b4-8801-89a51cbdb24e",
    "e8d32ff3-15b6-4a33-9a08-18017d93500f",
    "6bb265c0-2e48-4415-9ce2-38a263bdb7d4",
    "344d7079-a39c-4ed3-a369-7fd6ae358d93",
    "2d8b0414-b179-403c-8ee9-4fbd561254a4",
    "cd89653f-5fc6-4b2a-a779-786a32b88c79",
    "0aa43a35-9ad0-4e00-aa7d-840c38cd43dc",
    "2127348b-6d81-4ad3-a839-3f7e2db856a6",
    "4890349f-de8e-4976-a27b-ba860196b6ff",
)

MAIN_MOMENT_MOVES = {
    "100897b9-0989-47db-b114-fe7064cecd4d": 13,
    "3a41fb4c-a229-49b4-8801-89a51cbdb24e": 28,
    "e8d32ff3-15b6-4a33-9a08-18017d93500f": 3,
    "6bb265c0-2e48-4415-9ce2-38a263bdb7d4": 26,
    "344d7079-a39c-4ed3-a369-7fd6ae358d93": 13,
    "2d8b0414-b179-403c-8ee9-4fbd561254a4": 19,
    "cd89653f-5fc6-4b2a-a779-786a32b88c79": 30,
    "0aa43a35-9ad0-4e00-aa7d-840c38cd43dc": 17,
    "2127348b-6d81-4ad3-a839-3f7e2db856a6": 31,
    "4890349f-de8e-4976-a27b-ba860196b6ff": 6,
}


def _position_key(fen: str) -> str:
    return " ".join(str(fen or "").split()[:4])


def _best(row: Mapping[str, Any]) -> str:
    return str(row.get("best_move") or row.get("best_move_san") or "")


def _user_outcome(game_doc: Mapping[str, Any]) -> str:
    result = str(game_doc.get("result") or "")
    color = str(game_doc.get("user_color") or "").lower()
    if result == "1/2-1/2":
        return "draw"
    return "win" if (result == "1-0" and color == "white") or (result == "0-1" and color == "black") else "loss"


def _parse_san(board: chess.Board, san: str) -> chess.Move | None:
    try:
        return board.parse_san(str(san or ""))
    except (ValueError, AssertionError):
        return None


def _best_is_check_or_capture(fen: str, best_san: str) -> bool:
    try:
        board = chess.Board(fen)
    except ValueError:
        return False
    move = _parse_san(board, best_san)
    if move is None:
        return False
    capture = board.is_capture(move)
    board.push(move)
    return capture or board.is_check()


def _why_result(caption: str, played: str, best: str) -> dict[str, bool]:
    h1 = has_concrete_consequence(caption, played, best)
    h2 = has_causal_connector(caption)
    h3 = has_principle_ending(caption)
    return {"pass": h1 or h2 or h3, "concrete": h1, "causal": h2, "principle": h3}


def _claim_violations(move: Mapping[str, Any]) -> list[str]:
    caption = str(move.get("caption") or "")
    if not caption:
        return []
    facts = {
        "move_san": move.get("move_san"),
        "fen_before": move.get("fen_before"),
        "fen_after": move.get("fen_after"),
        "is_user_move": True,
        "cp_loss": int(move.get("cp_loss") or 0),
        "best_move_san": move.get("best_move_san"),
        "pv_after_played": list(move.get("pv_after_played") or []),
        "pv_after_best": list(move.get("pv_after_best") or []),
    }
    try:
        return [
            str(item)
            for item in verify_caption(caption, facts, strict_v2=True)
        ]
    except Exception as exc:
        return [f"verifier_error:{type(exc).__name__}"]


def _replay_game(game_doc: Mapping[str, Any], analysis: Mapping[str, Any]) -> dict[str, Any]:
    game_id = str(game_doc["game_id"])
    pgn_text = str(game_doc.get("pgn") or "")
    user_color = str(game_doc.get("user_color") or "white").lower()
    user_is_white = user_color == "white"
    stockfish = analysis.get("stockfish_analysis") or {}
    rows = list(stockfish.get("move_evaluations") or [])
    opp_rows = list(stockfish.get("opponent_move_evaluations") or [])
    observations = derive_current_review_observations(
        game_id=game_id,
        user_id=str(game_doc.get("user_id") or "audit_user"),
        user_color=user_color,
        pgn=pgn_text,
        move_evaluations=rows,
        opponent_move_evaluations=opp_rows,
    )
    by_fen = {_position_key(row.get("fen_before")): row for row in rows if row.get("fen_before")}
    pgn_game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not pgn_game:
        raise ValueError("invalid PGN")

    board = pgn_game.board()
    history: list[str] = []
    state = CrossMoveState()
    shapes_fired: set[str] = set()
    board_window: list[dict[str, Any]] = []
    user_moves = []
    events = []
    prompts = []
    features = {}
    errors = []

    for ply_index, move in enumerate(pgn_game.mainline_moves(), start=1):
        fen_before = board.fen()
        san = board.san(move)
        mover_is_white = board.turn == chess.WHITE
        is_user = mover_is_white == user_is_white
        move_number = board.fullmove_number
        row = by_fen.get(_position_key(fen_before))
        if row is None:
            errors.append(f"missing_eval:ply{ply_index}")
            board.push(move)
            history.append(san)
            continue
        try:
            decision = build_move_teaching_decision(
                MoveInputs(
                    fen_before=fen_before,
                    played_san=san,
                    mover_is_user=is_user,
                    mover_is_white=mover_is_white,
                    user_color=user_color,
                    full_move_number=move_number,
                    move_history_san=list(history),
                    prev_move_san=history[-1] if history else None,
                    best_move_san=_best(row) or None,
                    eval_before_cp=row.get("eval_before"),
                    eval_after_cp=row.get("eval_after"),
                    cp_loss=int(row.get("cp_loss") or 0),
                    pv_after_played=list(row.get("pv_after_played") or []),
                    pv_after_best=list(row.get("pv_after_best") or []),
                    eco_code=game_doc.get("eco"),
                    opening_name=game_doc.get("opening"),
                    user_rating=game_doc.get("user_rating"),
                    allow_fresh_engine_verification=False,
                ),
                state,
                shapes_fired_this_game=shapes_fired,
                bs_recent_window=board_window,
                eval_lookup=by_fen,
                move_evaluations=rows,
            )
        except Exception as exc:
            errors.append(
                f"pipeline:{ply_index}:{type(exc).__name__}:{str(exc)[:200]}"
            )
            board.push(move)
            history.append(san)
            continue

        if is_user:
            explanation = decision.explanation
            caption = str(explanation.board_explanation or decision.text.caption or "").strip()
            meta = decision.teaching_meta
            record = {
                "ply": ply_index,
                "move_number": move_number,
                "move_san": san,
                "fen_before": fen_before,
                "fen_after": decision.debug_facts.get("fen_after"),
                "best_move_san": _best(row),
                "cp_loss": int(row.get("cp_loss") or 0),
                "eval_before": row.get("eval_before"),
                "eval_after": row.get("eval_after"),
                "pv_after_played": list(row.get("pv_after_played") or []),
                "pv_after_best": list(row.get("pv_after_best") or []),
                "severity": meta.severity,
                "severity_canonical": meta.severity_canonical,
                "severity_practical": meta.severity_practical,
                "caption_severity_word": meta.caption_severity_word,
                "stayed_winning": meta.stayed_winning,
                "decisiveness_changed": meta.decisiveness_changed,
                "mover_state_before": meta.mover_state_before,
                "mover_state_after": meta.mover_state_after,
                "mover_winprob_delta": meta.mover_winprob_delta,
                "caption": caption,
                "principle": explanation.transferable_instruction,
                "rule_name": decision.text.rule_name,
                "final_verified": explanation.final_verified,
                "visual": {"arrows": decision.visual.arrows, "highlights": decision.visual.highlight_squares},
                "principle_id": meta.principle_id_used,
                "shape_pattern_id": meta.shape_pattern_id,
                "trap": bool(decision.trap_record),
                "played_purposes": list(
                    verified_move_purposes(
                        fen_before=fen_before,
                        played_san=san,
                    )
                ),
                "observation": observations.get(move_number),
            }
            audited_severity = meta.severity in {"mistake", "blunder"}
            record["why"] = _why_result(caption, san, _best(row)) if audited_severity and caption else None
            record["claim_violations"] = _claim_violations(record)
            issues = []
            if audited_severity and not caption:
                issues.append("silent_mistake_or_blunder")
            if record["why"] and not record["why"]["pass"]:
                issues.append("caption_has_no_why")
            if record["claim_violations"]:
                issues.append("caption_claim_verifier_failure")
            lower = caption.lower()
            forcing_words = "forcing move" in lower or "checks and forcing" in lower
            if forcing_words and not _best_is_check_or_capture(fen_before, _best(row)):
                issues.append("forcing_language_without_best_check_or_capture")
            if meta.stayed_winning and (
                (meta.caption_severity_word or "") == "blunder"
                or any(term in lower for term in ("threw the game", "changed the game", "turning point"))
            ):
                issues.append("harsh_language_while_stayed_winning")
            record["issues"] = issues
            user_moves.append(record)

            observation = observations.get(move_number) or {}
            pair = adapt_review_event(
                decision=decision,
                observation=observation,
                game_id=game_id,
                ply=ply_index,
                move_number=move_number,
                san=san,
                env=QUALITY_V2_ENV,
            )
            if pair is not None:
                event, feature = pair
                if event.player_authorized:
                    events.append(event)
                    features[event.event_id] = feature
                    try:
                        prompt = build_review_event_reflection_prompt(
                            event,
                            fen_before=fen_before,
                            user_move=san,
                            best_move=_best(row),
                            rating=int(game_doc.get("user_rating") or 1200),
                            cp_loss=float(row.get("cp_loss") or 0),
                            move_number=move_number,
                        )
                        prompts.append(prompt)
                    except Exception as exc:
                        errors.append(
                            f"prompt:{ply_index}:{type(exc).__name__}:{str(exc)[:200]}"
                        )

        board.push(move)
        history.append(san)

    plan_result = build_shadow_game_teaching_plan(
        game_id=game_id,
        events=tuple(events),
        features=features,
        generated_at=datetime.now(timezone.utc),
        formula_id="E_transition_then_teaching",
    )
    selected_ids = set(plan_result.selected_event_ids)
    selected_moves = [event.move.number for event in events if event.event_id in selected_ids]
    event_by_move = {event.move.number: event for event in events}
    prompt_by_move = {next((event.move.number for event in events if event.event_id == prompt.event_id), -1): prompt for prompt in prompts}

    significant = [move for move in user_moves if move["severity"] in {"mistake", "blunder"}]
    ranked = sorted(
        significant,
        key=lambda move: (
            int(bool(move["decisiveness_changed"])),
            int(not bool(move["stayed_winning"])),
            max(0.0, -float(move["mover_winprob_delta"] or 0.0)),
            float(move["cp_loss"]),
            -int(move["ply"]),
        ),
        reverse=True,
    )
    top = ranked[0] if ranked else None
    for move in user_moves:
        event = event_by_move.get(move["move_number"])
        prompt = prompt_by_move.get(move["move_number"])
        if event:
            move["v2_caption"] = event.teaching.caption
            move["v2_principle"] = event.teaching.principle
            move["v2_cause"] = (
                event.cause.contract_dict() if event.cause is not None else None
            )
            move["v2_quality_id"] = event.evidence.quality_id
            move["event_visual"] = event.teaching.visual.contract_dict()
            move["reflection_option_ids"] = [option.option_id for option in prompt.options] if prompt else []
            v2_issues = []
            v2_why = _why_result(
                move["v2_caption"],
                move["move_san"],
                move["best_move_san"],
            )
            if not v2_why["pass"]:
                v2_issues.append("caption_has_no_why")
            v2_claim_record = {**move, "caption": move["v2_caption"]}
            v2_claim_violations = _claim_violations(v2_claim_record)
            if v2_claim_violations:
                v2_issues.append("caption_claim_verifier_failure")
            move["v2_claim_violations"] = v2_claim_violations
            attack_possible = bool({"pressures_king_ring", "attacks_opponent_piece"} & set(move["played_purposes"]))
            attack_shown = bool({"chose_attack_over_safety", "attacked_ignored_threat"} & set(move["reflection_option_ids"]))
            if attack_possible and not attack_shown:
                v2_issues.append("reflection_omits_board_possible_attack_intent")
            if isinstance(event.cause, LegalMaterialLossCause):
                cause_tokens = {
                    event.cause.affected.piece,
                    event.cause.affected.square,
                }
                rendered_caption = move["v2_caption"].lower()
                if not all(token.lower() in rendered_caption for token in cause_tokens):
                    v2_issues.append("caption_does_not_name_verified_hang")
            if not event.teaching.visual.arrows:
                v2_issues.append("selected_event_has_no_relationship_arrow")
            if not move["v2_principle"].strip():
                v2_issues.append("missing_transferable_instruction")
            if not move["reflection_option_ids"]:
                v2_issues.append("missing_reflection_options")
            move["v2_issues"] = v2_issues

    actual_plan = (analysis.get("game_teaching_plan") or {}).get("plan")
    actual_selected = (analysis.get("game_teaching_plan") or {}).get("selected_event_ids") or []
    issue_counts = Counter(issue for move in user_moves for issue in move["issues"])
    opening_signals = sum(bool(move.get("principle_id") and str(move["principle_id"]).startswith("OP_")) for move in user_moves)
    endgame_signals = sum(bool(move.get("principle_id") and str(move["principle_id"]).startswith("END_")) for move in user_moves)
    trap_signals = sum(bool(move.get("trap")) for move in user_moves)
    expected_main_move = MAIN_MOMENT_MOVES.get(game_id)
    main_moment = next(
        (
            move
            for move in user_moves
            if expected_main_move is not None
            and move["move_number"] == expected_main_move
        ),
        None,
    )
    significant_events = [
        {
            key: move.get(key)
            for key in (
                "ply",
                "move_number",
                "move_san",
                "fen_before",
                "best_move_san",
                "cp_loss",
                "pv_after_played",
                "pv_after_best",
                "severity",
                "severity_practical",
                "stayed_winning",
                "decisiveness_changed",
                "mover_state_before",
                "mover_state_after",
                "v2_caption",
                "v2_principle",
                "v2_cause",
                "v2_quality_id",
                "event_visual",
                "reflection_option_ids",
                "v2_claim_violations",
                "v2_issues",
                "issues",
            )
        }
        for move in significant
    ]
    return {
        "game_id": game_id,
        "outcome": _user_outcome(game_doc),
        "user_color": user_color,
        "opening": game_doc.get("opening"),
        "stored_v5_version": analysis.get("decryption_v5_version"),
        "actual_v138": analysis.get("decryption_v5_version") == 138,
        "current_reconstructed_event_moves": selected_moves,
        "stored_selected_event_ids": actual_selected,
        "stored_has_plan": bool(actual_plan),
        "significant_move_count": len(significant),
        "current_plan_chapter_count": len(selected_moves),
        "top_practical_move": top["move_number"] if top else None,
        "top_practical_move_selected": bool(top and top["move_number"] in selected_moves),
        "issue_counts": dict(issue_counts),
        "caption_quality": {
            "with_any_why_signal": sum(bool(move.get("why") and move["why"]["pass"]) for move in significant),
            "with_all_three_why_signals": sum(
                bool(move.get("why") and all((move["why"]["concrete"], move["why"]["causal"], move["why"]["principle"])))
                for move in significant
            ),
            "with_concrete_consequence_signal": sum(bool(move.get("why") and move["why"]["concrete"]) for move in significant),
            "with_causal_connector_signal": sum(bool(move.get("why") and move["why"]["causal"]) for move in significant),
            "with_principle_ending_signal": sum(bool(move.get("why") and move["why"]["principle"]) for move in significant),
            "blank_transferable_instruction": sum(not bool(str(move.get("principle") or "").strip()) for move in significant),
            "without_any_arrow": sum(not bool((move.get("visual") or {}).get("arrows")) for move in significant),
            "rule_counts": dict(Counter(str(move.get("rule_name") or "") for move in significant)),
        },
        "content_signals": {"opening": opening_signals, "endgame": endgame_signals, "trap": trap_signals},
        "pipeline_errors": errors,
        "main_moment": (
            {
                key: main_moment.get(key)
                for key in (
                    "ply",
                    "move_number",
                    "move_san",
                    "best_move_san",
                    "severity",
                    "severity_practical",
                    "stayed_winning",
                    "decisiveness_changed",
                    "mover_state_before",
                    "mover_state_after",
                    "mover_winprob_delta",
                    "v2_caption",
                    "v2_principle",
                    "v2_cause",
                    "v2_quality_id",
                    "event_visual",
                    "reflection_option_ids",
                    "v2_claim_violations",
                    "v2_issues",
                    "issues",
                )
            }
            if main_moment is not None
            else None
        ),
        "significant_events": significant_events,
        "selected_moves": [
            {key: move.get(key) for key in (
                "ply", "move_number", "move_san", "fen_before", "best_move_san",
                "cp_loss", "eval_before", "eval_after", "pv_after_played", "pv_after_best",
                "severity_practical", "stayed_winning", "decisiveness_changed",
                "caption", "principle", "rule_name", "visual", "played_purposes",
                "issues", "event_visual", "reflection_option_ids",
                "v2_claim_violations", "v2_issues",
            )}
            for move in user_moves
            if move["move_number"] in selected_moves
        ],
        "top_moves": [
            {key: move.get(key) for key in (
                "ply", "move_number", "move_san", "fen_before", "best_move_san",
                "cp_loss", "eval_before", "eval_after", "pv_after_played", "pv_after_best",
                "severity", "severity_practical", "caption_severity_word", "stayed_winning",
                "decisiveness_changed", "mover_state_before", "mover_state_after",
                "mover_winprob_delta", "caption", "principle", "rule_name", "final_verified",
                "visual", "principle_id", "shape_pattern_id", "played_purposes", "why",
                "claim_violations", "issues", "event_visual",
                "reflection_option_ids", "v2_caption", "v2_principle", "v2_cause",
                "v2_quality_id", "v2_claim_violations", "v2_issues",
            )}
            for move in ranked[:3]
        ],
    }


def main() -> None:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user = db.users.find_one({"email": ACCOUNT_EMAIL}, {"_id": 0, "user_id": 1}) or {}
    user_id = str(user.get("user_id") or "")
    games = {doc["game_id"]: doc for doc in db.games.find({"game_id": {"$in": list(GAME_IDS)}, "user_id": user_id}, {"_id": 0})}
    analyses = {doc["game_id"]: doc for doc in db.game_analyses.find({"game_id": {"$in": list(GAME_IDS)}}, {"_id": 0})}
    results = []
    failures = []
    for game_id in GAME_IDS:
        try:
            results.append(_replay_game(games[game_id], analyses[game_id]))
        except Exception as exc:
            failures.append({"game_id": game_id, "error": f"{type(exc).__name__}:{exc}"})

    aggregate_issues = Counter()
    for result in results:
        aggregate_issues.update(result["issue_counts"])
    output = {
        "schema_version": "personalized_review.ten_game_audit.v1",
        "generated_at": date.today().isoformat(),
        "read_only": True,
        "engine_runs": 0,
        "llm_calls": 0,
        "database_writes": 0,
        "selection": {"games": len(results), "wins": sum(r["outcome"] == "win" for r in results), "losses": sum(r["outcome"] == "loss" for r in results), "draws": sum(r["outcome"] == "draw" for r in results)},
        "aggregate": {
            "games_with_current_plan": sum(r["current_plan_chapter_count"] > 0 for r in results),
            "games_where_top_practical_move_selected": sum(r["top_practical_move_selected"] for r in results),
            "significant_moves": sum(r["significant_move_count"] for r in results),
            "issues": dict(aggregate_issues),
            "caption_quality": {
                "with_any_why_signal": sum(r["caption_quality"]["with_any_why_signal"] for r in results),
                "with_all_three_why_signals": sum(r["caption_quality"]["with_all_three_why_signals"] for r in results),
                "with_concrete_consequence_signal": sum(r["caption_quality"]["with_concrete_consequence_signal"] for r in results),
                "with_causal_connector_signal": sum(r["caption_quality"]["with_causal_connector_signal"] for r in results),
                "with_principle_ending_signal": sum(r["caption_quality"]["with_principle_ending_signal"] for r in results),
                "blank_transferable_instruction": sum(r["caption_quality"]["blank_transferable_instruction"] for r in results),
                "without_any_arrow": sum(r["caption_quality"]["without_any_arrow"] for r in results),
                "rule_counts": dict(sum((Counter(r["caption_quality"]["rule_counts"]) for r in results), Counter())),
            },
            "content_signals": {
                "opening": sum(r["content_signals"]["opening"] for r in results),
                "endgame": sum(r["content_signals"]["endgame"] for r in results),
                "trap": sum(r["content_signals"]["trap"] for r in results),
            },
        },
        "failures": failures,
        "games": results,
    }
    if os.environ.get("AUDIT_COMPACT") == "1":
        output = {
            "selection": output["selection"],
            "aggregate": output["aggregate"],
            "failures": output["failures"],
            "games": [
                {
                    "game_id": game["game_id"],
                    "outcome": game["outcome"],
                    "opening": game["opening"],
                    "stored_v5_version": game["stored_v5_version"],
                    "significant_move_count": game["significant_move_count"],
                    "current_plan_chapter_count": game["current_plan_chapter_count"],
                    "top_practical_move": game["top_practical_move"],
                    "top_practical_move_selected": game["top_practical_move_selected"],
                    "issue_counts": game["issue_counts"],
                    "caption_quality": game["caption_quality"],
                    "content_signals": game["content_signals"],
                    "pipeline_errors": game["pipeline_errors"],
                    "selected_moves": game["selected_moves"],
                    "top_moves": game["top_moves"],
                }
                for game in output["games"]
            ],
        }
    requested_games = {
        game_id.strip()
        for game_id in os.environ.get("AUDIT_GAME_ID", "").split(",")
        if game_id.strip()
    }
    selected_results = results
    if requested_games:
        output["games"] = [game for game in output["games"] if game["game_id"] in requested_games]
        selected_results = [
            game for game in results if game["game_id"] in requested_games
        ]
    if os.environ.get("AUDIT_ERRORS_ONLY") == "1":
        output = {
            "read_only": True,
            "engine_runs": 0,
            "llm_calls": 0,
            "database_writes": 0,
            "games": [
                {
                    "game_id": game["game_id"],
                    "pipeline_errors": game["pipeline_errors"],
                }
                for game in output["games"]
            ],
        }
    if os.environ.get("AUDIT_MAIN_ONLY") == "1":
        output = {
            "schema_version": "personalized_review.ten_game_main_evidence.v1",
            "read_only": True,
            "engine_runs": 0,
            "llm_calls": 0,
            "database_writes": 0,
            "games": [
                {
                    "game_id": game["game_id"],
                    "opening": game["opening"],
                    "main_move_number": MAIN_MOMENT_MOVES[game["game_id"]],
                    "move": next(
                        (
                            move
                            for move in [*game["top_moves"], *game["selected_moves"]]
                            if move.get("move_number") == MAIN_MOMENT_MOVES[game["game_id"]]
                        ),
                        None,
                    ),
                }
                for game in output["games"]
            ],
        }
    if os.environ.get("AUDIT_ACCEPTANCE_ONLY") == "1":
        acceptance_games = []
        for game in selected_results:
            main_moment = game["main_moment"]
            main_move = MAIN_MOMENT_MOVES[game["game_id"]]
            unexpected_errors = [
                error
                for error in game["pipeline_errors"]
                if not error.startswith("missing_eval:")
            ]
            acceptance_games.append(
                {
                    "game_id": game["game_id"],
                    "main_move_number": main_move,
                    "main_moment_selected": main_move
                    in game["current_reconstructed_event_moves"],
                    "significant_move_count": game["significant_move_count"],
                    "current_plan_chapter_count": game[
                        "current_plan_chapter_count"
                    ],
                    "top_practical_move": game["top_practical_move"],
                    "top_practical_move_selected": game[
                        "top_practical_move_selected"
                    ],
                    "unexpected_pipeline_errors": unexpected_errors,
                    "main_moment": main_moment,
                }
            )
        output = {
            "schema_version": "personalized_review.ten_game_acceptance.v1",
            "read_only": True,
            "engine_runs": 0,
            "llm_calls": 0,
            "database_writes": 0,
            "summary": {
                "games": len(acceptance_games),
                "games_with_plan": sum(
                    game["current_plan_chapter_count"] > 0
                    for game in acceptance_games
                ),
                "human_main_moment_selected": sum(
                    game["main_moment_selected"] for game in acceptance_games
                ),
                "top_practical_move_selected": sum(
                    game["top_practical_move_selected"]
                    for game in acceptance_games
                ),
                "games_with_unexpected_pipeline_errors": sum(
                    bool(game["unexpected_pipeline_errors"])
                    for game in acceptance_games
                ),
                "main_moments_with_typed_cause": sum(
                    bool((game["main_moment"] or {}).get("v2_cause"))
                    for game in acceptance_games
                ),
                "main_moments_with_reflection_options": sum(
                    bool(
                        (game["main_moment"] or {}).get(
                            "reflection_option_ids"
                        )
                    )
                    for game in acceptance_games
                ),
                "main_moments_with_v2_issues": sum(
                    bool((game["main_moment"] or {}).get("v2_issues"))
                    for game in acceptance_games
                ),
            },
            "failures": failures,
            "games": acceptance_games,
        }
    if os.environ.get("AUDIT_EVENTS_ONLY") == "1":
        output = {
            "schema_version": "personalized_review.ten_game_events.v1",
            "read_only": True,
            "engine_runs": 0,
            "llm_calls": 0,
            "database_writes": 0,
            "summary": {
                "games": len(selected_results),
                "significant_moves": sum(
                    len(game["significant_events"])
                    for game in selected_results
                ),
                "typed_cause_fires": sum(
                    bool(move.get("v2_cause"))
                    for game in selected_results
                    for move in game["significant_events"]
                ),
                "abstentions": sum(
                    not bool(move.get("v2_cause"))
                    for game in selected_results
                    for move in game["significant_events"]
                ),
                "typed_events_with_v2_issues": sum(
                    bool(move.get("v2_cause"))
                    and bool(move.get("v2_issues"))
                    for game in selected_results
                    for move in game["significant_events"]
                ),
            },
            "games": [
                {
                    "game_id": game["game_id"],
                    "events": game["significant_events"],
                }
                for game in selected_results
            ],
            "failures": failures,
        }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
