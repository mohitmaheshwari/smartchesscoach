"""
Smart Coaching — LLM converts structured chess data into natural coaching language.

Architecture:
  1. Our detectors produce FACTS (intent, threats, hanging pieces, phase)
  2. Facts form a SCENARIO KEY (intent + piece types + threat type + phase)
  3. Check coaching_phrases DB for cached response matching this scenario
  4. If cache miss → call LLM → store response with scenario key
  5. Over time, the DB fills up → LLM calls drop to zero

The scenario key is NOT position-specific (not FEN-based). It captures the
COACHING SITUATION: "hanging_piece_punishment + undefended_knight + middlegame"
so the same phrase works for any position with that pattern.
"""

import chess
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


def build_scenario_key(
    intent: str,
    move_type: str,  # "capture", "check", "quiet", "castle"
    piece_moved: str,  # "knight", "bishop", etc.
    target_piece: Optional[str] = None,  # piece being threatened/captured
    threat_type: Optional[str] = None,  # "undefended", "underdefended", "fork", "check_threat"
    phase: str = "middlegame",
    has_opportunity: bool = False,
    opening_key: Optional[str] = None,  # opening name for opening-phase coaching
) -> str:
    """
    Build a scenario key for coaching phrase lookup.

    Same key = same coaching situation = same phrase works.
    Opening-phase coaching includes the opening name so different
    openings don't share cached phrases.
    """
    parts = [
        intent or "unknown",
        move_type or "quiet",
        piece_moved or "piece",
        target_piece or "none",
        threat_type or "none",
        phase,
        "opp" if has_opportunity else "no_opp",
    ]
    if opening_key:
        parts.append(opening_key)
    return ":".join(parts)


def build_user_scenario_key(
    severity: str,
    fundamental: Optional[str],
    hanging_piece: Optional[str] = None,  # "knight", "bishop", etc.
    hanging_square: Optional[str] = None,
    coach_intent: Optional[str] = None,
    phase: str = "middlegame",
) -> str:
    """Scenario key for user move feedback (Socratic questions)."""
    parts = [
        severity,
        fundamental or "unknown",
        hanging_piece or "none",
        coach_intent or "none",
        phase,
    ]
    return ":".join(parts)


# generate_smart_coach_explanation REMOVED 2026-05-26 (PR-5 of central-
# layer migration). The PWC coach-narration surface now flows through
# caption_pipeline.build_move_teaching_decision via live_v5_teaching.
# coach_move_narration_for_live_move. Per [[one-source-of-truth-for-
# coaching]] — every PWC coach move produces narration deterministically
# from R17_coach_move.json templates, no LLM fallback.
#
# generate_smart_user_feedback (below) still uses the LLM path; PR-6
# will migrate that surface using the same approach.


async def generate_smart_user_feedback(
    board_before: chess.Board,
    user_move: chess.Move,
    best_move_san: Optional[str],
    cp_loss: int,
    severity: str,
    fundamental_violated: Optional[str],
    coach_intent: Optional[str],
    user_rating: int = 1200,
    phase: str = "middlegame",
    db=None,
    pv_after_played: Optional[List[str]] = None,
    move_history_san: Optional[List[str]] = None,
) -> Optional[Dict]:
    """
    Generate Socratic question for mistakes using LLM as language layer.
    All chess facts come from our fundamentals checker and detectors.
    """
    if severity in ("good", "brilliant"):
        return None

    # ─── PRE-ROUTING GATES ────────────────────────────────────────
    # Several Parth bugs (fb_3c558315d3c7, fb_3f8c02a989c9,
    # fb_9b519ba4edb2, fb_0cbacdf54340, fb_631576d2f1ab,
    # fb_274dfae7eb44) had the "X was the stronger move here"
    # template fire on moves that weren't actually mistakes:
    #   - User addressing an immediate forcing threat (Qe7 saves
    #     Bc5, Kf8 stops Bh6 mate-in-1)
    #   - Known opening lines (b4 = Evans Gambit)
    #   - Both moves leading to mate (Rfe1+ vs Bxf7+)
    #   - Borderline cp_loss that stockfish flagged "mistake"
    #
    # Apply confidence-philosophy gates: if any gate fires,
    # downgrade severity so the mistake_calculation template
    # ("stronger move") doesn't fire. The move is left for the
    # human coach to address in the review tab if needed.
    suppress_mistake_framing = False
    suppress_reason = None

    # Gate A: cp_loss too small for "stronger move" framing
    if cp_loss is not None and cp_loss < 80:
        suppress_mistake_framing = True
        suppress_reason = f"cp_loss={cp_loss} below 'stronger move' threshold"

    # Gate B: user's move addresses an immediate forcing threat
    if not suppress_mistake_framing:
        try:
            from services.tactical_safety import user_move_addresses_threat
            if user_move_addresses_threat(board_before, user_move):
                suppress_mistake_framing = True
                suppress_reason = "user move addresses an attacked own piece"
        except Exception as gate_err:
            logger.debug(f"[SMART-COACHING] threat-gate failed: {gate_err}")

    # Gate C: position is in known opening theory
    if not suppress_mistake_framing and move_history_san is not None:
        try:
            from services.decryption_voice.opening_book import (
                recognize_opening_from_history,
            )
            move_san_check = board_before.san(user_move)
            full_history = list(move_history_san) + [move_san_check]
            if recognize_opening_from_history(full_history):
                suppress_mistake_framing = True
                suppress_reason = "move is part of known opening theory"
        except Exception as gate_err:
            logger.debug(f"[SMART-COACHING] opening-theory gate failed: {gate_err}")

    if suppress_mistake_framing:
        logger.info(
            f"[SMART-COACHING] suppressing mistake framing "
            f"(severity={severity}, cp_loss={cp_loss}): {suppress_reason}"
        )
        # Return None — the move shows uncaptioned and the human
        # coach can address it in the review tab. This is the same
        # pattern as engine_review_needed in per_move_caption.py.
        return None

    from llm_service import call_llm

    move_san = board_before.san(user_move)
    piece = board_before.piece_at(user_move.from_square)
    captured = board_before.piece_at(user_move.to_square)
    board_after = board_before.copy()
    board_after.push(user_move)

    # ─── GATHER FACTS ───

    move_desc = _describe_move(board_before, user_move, piece, captured)

    # What went wrong (from our fundamentals checker)
    problem_facts = []
    hanging_piece_name = None
    hanging_square_name = None

    if fundamental_violated == "check_opponents_move":
        problem_facts.append("Student did not respond to the opponent's threat from the previous move")
    elif fundamental_violated == "hanging_pieces":
        user_color_bool = chess.WHITE if board_before.turn == chess.WHITE else chess.BLACK
        for sq in chess.SQUARES:
            p = board_after.piece_at(sq)
            if p and p.color == user_color_bool and p.piece_type not in (chess.KING, chess.PAWN):
                attackers = list(board_after.attackers(not user_color_bool, sq))
                defenders = list(board_after.attackers(user_color_bool, sq))
                if attackers and not defenders:
                    hanging_piece_name = chess.piece_name(p.piece_type)
                    hanging_square_name = chess.square_name(sq)
                    problem_facts.append(f"Student's {hanging_piece_name} on {hanging_square_name} is now undefended and attacked")
                    break
        if not problem_facts:
            problem_facts.append("Student left a piece undefended")
    elif fundamental_violated == "calculate":
        problem_facts.append("Student didn't calculate the opponent's response")
    elif fundamental_violated == "king_safety":
        problem_facts.append("Student's king is in danger")
    elif fundamental_violated == "development":
        problem_facts.append("Student moved an already-developed piece instead of developing a new one")
    elif fundamental_violated == "center_control":
        problem_facts.append("Student lost control of the center")
    elif fundamental_violated == "have_a_plan":
        problem_facts.append("Student's move doesn't serve a clear purpose")

    if coach_intent:
        intent_map = {
            "hanging_piece_punishment": "The coach created a position to test piece safety awareness",
            "fork_opportunity": "The coach set up a double attack the student needed to handle",
            "threat_awareness": "The coach created a threat the student needed to notice",
        }
        if coach_intent in intent_map:
            problem_facts.append(intent_map[coach_intent])

    # Recovery plan from Stockfish PV — adapted to student's rating
    # Lower rated: general direction ("keep your pieces safe")
    # Higher rated: more specific ("think about the move order to recover")
    recovery_facts = []
    if pv_after_played and len(pv_after_played) >= 2:
        sim = board_after.copy()
        user_color_bool = chess.WHITE if board_before.turn == chess.WHITE else chess.BLACK

        # Analyze what the PV involves (without telling exact moves)
        pv_themes = {"castle": False, "capture": False, "develop": False, "defend": False}
        capture_target = None

        for pv_move_san in pv_after_played[:4]:
            try:
                pv_move = sim.parse_san(pv_move_san)
                piece = sim.piece_at(pv_move.from_square)
                is_user_move = (sim.turn == user_color_bool)

                if is_user_move and piece:
                    if sim.is_castling(pv_move):
                        pv_themes["castle"] = True
                    elif sim.is_capture(pv_move):
                        pv_themes["capture"] = True
                        captured = sim.piece_at(pv_move.to_square)
                        if captured:
                            capture_target = chess.piece_name(captured.piece_type)
                    elif piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                        back_rank = 0 if piece.color == chess.WHITE else 7
                        if chess.square_rank(pv_move.from_square) == back_rank:
                            pv_themes["develop"] = True

                sim.push(pv_move)
            except Exception:
                break

        # Build plan based on rating level
        if user_rating < 1000:
            # Beginners: just the habit, one thing at a time
            if pv_themes["capture"]:
                recovery_facts.append("Look for pieces you can take safely")
            elif pv_themes["castle"]:
                recovery_facts.append("Your king needs to be safe first")
            elif pv_themes["develop"]:
                recovery_facts.append("Bring your pieces into the game")
            else:
                recovery_facts.append("Take a breath and look at the whole board")
        elif user_rating < 1400:
            # Improving: two priorities, no specific squares
            if pv_themes["capture"] and capture_target:
                recovery_facts.append(f"There's a {capture_target} you can win back")
            if pv_themes["castle"]:
                recovery_facts.append("Get your king safe")
            if pv_themes["develop"]:
                recovery_facts.append("Finish developing your pieces")
            if not recovery_facts:
                recovery_facts.append("Think about what your pieces need right now")
        else:
            # Club+: push them to calculate
            if pv_themes["capture"]:
                recovery_facts.append("Can you find a way to win material back?")
            if pv_themes["castle"]:
                recovery_facts.append("Think about king safety")
            if not recovery_facts:
                recovery_facts.append("Calculate the next 2-3 moves carefully")

    # Fallback: basic position checks if PV is empty
    if not recovery_facts:
        user_color_bool = chess.WHITE if board_before.turn == chess.WHITE else chess.BLACK
        king_sq = board_after.king(user_color_bool)
        if king_sq is not None:
            king_file = chess.square_file(king_sq)
            king_rank = chess.square_rank(king_sq)
            back_rank = 0 if user_color_bool == chess.WHITE else 7
            if king_rank == back_rank and king_file == 4:
                recovery_facts.append("Get your king safe — castle")
            undeveloped = 0
            for sq in chess.SQUARES:
                p = board_after.piece_at(sq)
                if p and p.color == user_color_bool and p.piece_type in (chess.KNIGHT, chess.BISHOP):
                    if chess.square_rank(sq) == back_rank:
                        undeveloped += 1
            if undeveloped >= 2:
                recovery_facts.append(f"Develop your {undeveloped} pieces still on the back row")

    # ─── DETECT OPPONENT THREATS (for blunders) ───
    opponent_threat_type = None
    opponent_threat_text = ""
    threat_piece = ""
    threat_square = ""
    if severity == "blunder":
        try:
            from services.move_comparison import _find_opponent_threats
            # Pass the engine singleton so 'free capture' threats are
            # verified at depth before being added — Category 4 fix
            # (fb_159fc121ec61 class). Singleton returns None outside
            # production containers, in which case verification is
            # skipped (existing behavior).
            from services.threat_verifier import _get_singleton_engine
            verify_engine = _get_singleton_engine()
            threats = _find_opponent_threats(
                board_after,
                not (chess.WHITE if board_before.turn == chess.WHITE else chess.BLACK),
                engine=verify_engine,
            )
            if threats:
                opponent_threat_text = threats[0]
                if "fork" in threats[0].lower():
                    opponent_threat_type = "fork"
                    # Extract piece and square from threat text
                    import re
                    fork_match = re.search(r'(\w+)\s+forks', threats[0], re.IGNORECASE)
                    if not fork_match:
                        fork_match = re.search(r'(\w+[+#]?)\s+forks', threats[0])
                elif "checkmate" in threats[0].lower() or "mate" in threats[0].lower():
                    opponent_threat_type = "mate"
                elif "taken for free" in threats[0].lower() or "can be taken" in threats[0].lower():
                    opponent_threat_type = "capture"
        except Exception:
            pass

    # ─── TRY COACHING LIBRARY FIRST ───
    try:
        from services.coaching_library import match_user_scenario, get_user_feedback_text

        lib_key = match_user_scenario(
            severity=severity,
            fundamental=fundamental_violated,
            opponent_threat=opponent_threat_type,
        )
        if lib_key:
            lib_text = get_user_feedback_text(
                lib_key,
                piece=hanging_piece_name or "piece",
                square=hanging_square_name or "?",
                move=move_san,
                best_move=best_move_san or "the engine's choice",
                threat=opponent_threat_text,
                threat_piece=threat_piece or "piece",
                threat_square=threat_square or "?",
            )
            if lib_text:
                if recovery_facts:
                    lib_text["plan"] = lib_text.get("plan", "") or "; ".join(recovery_facts[:2])
                logger.info(f"[SMART-COACHING] User library hit: {lib_key} (threat={opponent_threat_type})")
                return lib_text
    except Exception as lib_err:
        logger.debug(f"[SMART-COACHING] User library miss: {lib_err}")

    # ─── CHECK DB CACHE ───
    user_scenario_key = build_user_scenario_key(
        severity=severity,
        fundamental=fundamental_violated,
        hanging_piece=hanging_piece_name,
        coach_intent=coach_intent,
        phase=phase,
    )

    if db is not None:
        try:
            cached = await db.coaching_phrases.find_one(
                {"scenario_key": user_scenario_key, "type": "user_feedback"},
                {"_id": 0, "response": 1}
            )
            if cached and cached.get("response"):
                logger.info(f"[SMART-COACHING] User cache hit: {user_scenario_key}")
                return cached["response"]
        except Exception:
            pass

    # ─── LLM CALL ───

    recovery_block = ""
    if recovery_facts:
        recovery_block = "\n- What to focus on now: " + "; ".join(recovery_facts[:3])

    facts_block = f"""FACTS:
- Student played: {move_san} ({move_desc})
- This was a {severity}
- What went wrong: {'; '.join(problem_facts) if problem_facts else 'unclear'}
- Game phase: {phase}{recovery_block}"""

    system_prompt = f"""Rewrite these facts as a coach talking to a {user_rating}-rated student who made a {severity}.

BANNED:
- ANY chess knowledge not in the FACTS
- Suggesting specific moves
- Fancy words like "consolidate", "establish", "vulnerable"

VOICE:
- Blunder: "Wait — your queen is sitting on c4 with no protection!"
- Mistake: "Good idea, but you missed something..."
- Always connect to a habit: "Before moving, always check..."
- If recovery plan in facts, mention it simply

1-2 sentences for what went wrong. 1 sentence plan. 1 question. 1 hint.

RESPOND with:
- narrative: 2 sentences max. What happened + what habit to build. Sound human.
- question: ONE Socratic question, under 20 words
- hint: ONE sentence if they can't answer

ONLY use the FACTS below. Do NOT analyze chess yourself.

Respond in JSON only: {{"narrative": "what went wrong (1-2 sentences)", "plan": "what to focus on for next 2-3 moves (from facts only)", "question": "one question about what they missed", "hint": "one hint if they can't answer"}}"""

    try:
        response = await call_llm(system_prompt, facts_block)
        import json
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
        result = json.loads(clean)

        # ─── STORE IN CACHE ───
        if db is not None:
            try:
                await db.coaching_phrases.update_one(
                    {"scenario_key": user_scenario_key, "type": "user_feedback"},
                    {"$set": {
                        "scenario_key": user_scenario_key,
                        "type": "user_feedback",
                        "response": result,
                        "facts": problem_facts,
                        "severity": severity,
                        "fundamental": fundamental_violated,
                        "phase": phase,
                        "created_at": __import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
                logger.info(f"[SMART-COACHING] User cached: {user_scenario_key}")
            except Exception:
                pass

        return result
    except Exception as e:
        logger.warning(f"[SMART-COACHING] User feedback LLM failed: {e}")
        return None


def _describe_move(board, move, piece, captured):
    """Describe what a move does in plain English."""
    parts = []
    if board.is_castling(move):
        side = "kingside" if chess.square_file(move.to_square) > 4 else "queenside"
        return f"{side} castling"
    if captured:
        parts.append(f"captures {chess.piece_name(captured.piece_type)} on {chess.square_name(move.to_square)}")
    if piece:
        parts.append(f"{chess.piece_name(piece.piece_type)} from {chess.square_name(move.from_square)} to {chess.square_name(move.to_square)}")

    board_after = board.copy()
    board_after.push(move)
    if board_after.is_check():
        parts.append("gives check")

    return "; ".join(parts) if parts else "quiet move"


def _get_phase(board):
    """Phase by piece count + move number.

    Tester reported "we're in the King's Pawn Opening — solid start"
    fired on Qe2 at move 6 (fb_f054972fee92), and "we're both still
    setting up" on Qe3 at move 4 (fb_307b44a3ebb9). Piece-count
    alone called both positions "opening" because all pieces were
    still on the board, and the templates assume early-opening
    framing. Add a move-number gate so anything past move 6 falls
    through to middlegame templates.
    """
    pieces = len(board.piece_map())
    fullmove = board.fullmove_number or 1
    # Opening templates assume "still setting up / solid start"
    # framing — only valid in the first few moves before pieces
    # become active. Past fullmove 4, even with all pieces on the
    # board, we're in early middlegame.
    if pieces >= 28 and fullmove <= 4:
        return "opening"
    if pieces >= 14:
        return "middlegame"
    return "endgame"


def _scan_opportunities(board, student_color):
    """Quick scan for what the student can exploit in this position."""
    try:
        from coach_play.teaching.pattern_detectors import find_hanging_pieces, find_fork_opportunities
        coach_color = not student_color

        hanging, underdefended = find_hanging_pieces(board, victim_color=coach_color)
        forks = find_fork_opportunities(board, forker_color=student_color)

        parts = []
        if hanging:
            names = [f"{chess.piece_name(h.piece_type)} on {chess.square_name(h.square)}" for h in hanging]
            parts.append(f"Coach has undefended: {', '.join(names)}")
        if forks:
            parts.append(f"Student can fork {len(forks)} targets")
        if underdefended:
            names = [f"{chess.piece_name(h.piece_type)} on {chess.square_name(h.square)}" for h in underdefended]
            parts.append(f"Under pressure: {', '.join(names)}")
        return "; ".join(parts) if parts else ""
    except Exception:
        return ""
