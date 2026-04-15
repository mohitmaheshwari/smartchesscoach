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
    has_opportunity: bool = False,  # student can exploit something
) -> str:
    """
    Build a scenario key for coaching phrase lookup.

    Same key = same coaching situation = same phrase works.
    Examples:
      "hanging_piece_punishment:capture:pawn:knight:undefended:middlegame"
      "fork_opportunity:quiet:knight:queen+rook:fork:middlegame"
      "threat_awareness:quiet:bishop:none:check_threat:opening"
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


async def generate_smart_coach_explanation(
    board_before: chess.Board,
    move: chess.Move,
    user_color: str,
    v2_context: Optional[Dict] = None,
    position_features: Optional[List] = None,
    player_weaknesses: Optional[List[str]] = None,
    user_rating: int = 1200,
    opening_name: Optional[str] = None,
    db=None,
) -> Dict:
    """
    Generate coaching text using LLM as a language layer only.
    All chess facts are computed by our systems and passed to the LLM.

    Caching: Each response is stored in coaching_phrases collection with
    a scenario key. Future identical scenarios serve from cache.
    """
    from llm_service import call_llm
    from services.position_reader import read_position

    move_san = board_before.san(move)
    piece = board_before.piece_at(move.from_square)
    captured = board_before.piece_at(move.to_square)
    coach_color = piece.color if piece else chess.WHITE
    user_chess_color = chess.WHITE if user_color == "white" else chess.BLACK

    board_after = board_before.copy()
    board_after.push(move)
    phase = _get_phase(board_after)

    # ─── GATHER ALL FACTS (from our systems, NOT the LLM) ───

    # Fact 1: What the move does mechanically
    move_facts = []
    if board_before.is_castling(move):
        side = "kingside" if chess.square_file(move.to_square) > 4 else "queenside"
        move_facts.append(f"Castled {side}")
    elif captured:
        move_facts.append(f"Captured {chess.piece_name(captured.piece_type)} on {chess.square_name(move.to_square)}")
    if board_after.is_check():
        move_facts.append("Gives check")
    if piece:
        piece_name = chess.piece_name(piece.piece_type)
        from_sq = chess.square_name(move.from_square)
        to_sq = chess.square_name(move.to_square)
        move_facts.append(f"{piece_name} moved from {from_sq} to {to_sq}")

    # Fact 2: V2 teaching intent
    intent_fact = ""
    if v2_context and v2_context.get("v2"):
        intent = v2_context.get("teaching_goal", "")
        why = v2_context.get("why_instructive", "")
        breakdown = v2_context.get("v2_breakdown", {})
        sub = breakdown.get("sub_scores", {})

        if intent == "hanging_piece_punishment":
            if sub.get("capture_punishment", 0) > 0:
                intent_fact = f"Coach captured an undefended piece (punishing a hanging piece)"
            elif sub.get("undefended", 0) > 0:
                intent_fact = f"Coach's move leaves one of the student's pieces undefended"
            elif sub.get("underdefended", 0) > 0:
                intent_fact = f"Coach's move puts pressure on an underdefended student piece"
        elif intent == "fork_opportunity":
            intent_fact = f"Coach's piece now attacks two student pieces at once ({why})"
        elif intent == "threat_awareness":
            if sub.get("attacks_undefended", 0) > 0:
                intent_fact = "Coach now threatens an undefended student piece"
            elif sub.get("checks", 0) > 0:
                intent_fact = "Coach has a check available next move"
            elif sub.get("safe_captures", 0) > 0:
                intent_fact = "Coach has a safe capture available"
            else:
                intent_fact = "Coach created a threat the student must notice"

    # Fact 3: What the student can exploit (from our detectors)
    opportunities = _scan_opportunities(board_after, user_chess_color)

    # Fact 4: Position features from our reader
    feature_facts = []
    if not position_features:
        try:
            pos_data = read_position(board_after.fen(), user_color, user_rating)
            position_features = pos_data.get("features", [])
        except Exception:
            position_features = []
    for f in (position_features or [])[:3]:
        title = f.title if hasattr(f, 'title') else f.get("title", "") if isinstance(f, dict) else str(f)
        desc = f.description if hasattr(f, 'description') else f.get("description", "") if isinstance(f, dict) else ""
        if title:
            feature_facts.append(f"{title}: {desc}")

    # Fact 5: New threats created by this move
    threat_facts = []
    for sq in chess.SQUARES:
        target = board_after.piece_at(sq)
        if target and target.color == user_chess_color and target.piece_type != chess.KING:
            now_attacked = board_after.is_attacked_by(coach_color, sq)
            was_attacked = board_before.is_attacked_by(coach_color, sq)
            if now_attacked and not was_attacked:
                t_name = chess.piece_name(target.piece_type)
                t_sq = chess.square_name(sq)
                defenders = len(list(board_after.attackers(user_chess_color, sq)))
                threat_facts.append(f"Student's {t_name} on {t_sq} is now attacked (defenders: {defenders})")

    # ─── BUILD SCENARIO KEY ───

    # Determine move type
    if board_before.is_castling(move):
        move_type = "castle"
    elif captured:
        move_type = "capture"
    elif board_after.is_check():
        move_type = "check"
    else:
        move_type = "quiet"

    piece_name = chess.piece_name(piece.piece_type) if piece else "piece"
    target_piece_name = None
    threat_type_key = None

    intent_key = ""
    if v2_context and v2_context.get("v2"):
        intent_key = v2_context.get("teaching_goal", "")
        sub = v2_context.get("v2_breakdown", {}).get("sub_scores", {})
        if sub.get("capture_punishment", 0) > 0:
            threat_type_key = "capture_punishment"
            if captured:
                target_piece_name = chess.piece_name(captured.piece_type)
        elif sub.get("undefended", 0) > 0:
            threat_type_key = "undefended"
        elif sub.get("underdefended", 0) > 0:
            threat_type_key = "underdefended"
        elif intent_key == "fork_opportunity":
            threat_type_key = "fork"
        elif sub.get("checks", 0) > 0:
            threat_type_key = "check_threat"
        elif sub.get("attacks_undefended", 0) > 0:
            threat_type_key = "attacks_undefended"
        elif sub.get("safe_captures", 0) > 0:
            threat_type_key = "safe_capture"

    # Find target piece from threats if not from capture
    if not target_piece_name and threat_facts:
        for tf in threat_facts:
            for pt in ["queen", "rook", "bishop", "knight"]:
                if pt in tf.lower():
                    target_piece_name = pt
                    break
            if target_piece_name:
                break

    scenario_key = build_scenario_key(
        intent=intent_key,
        move_type=move_type,
        piece_moved=piece_name,
        target_piece=target_piece_name,
        threat_type=threat_type_key,
        phase=phase,
        has_opportunity=bool(opportunities),
    )

    # ─── CHECK CACHE ───
    if db is not None:
        try:
            cached = await db.coaching_phrases.find_one(
                {"scenario_key": scenario_key, "type": "coach_move"},
                {"_id": 0, "response": 1}
            )
            if cached and cached.get("response"):
                logger.info(f"[SMART-COACHING] Cache hit: {scenario_key}")
                result = cached["response"]
                result["move_san"] = move_san  # Update move-specific field
                result["from_cache"] = True
                return result
        except Exception:
            pass

    # ─── BUILD FACTS BLOCK (only from our systems) ───

    facts_lines = [f"Move played: {move_san}"]
    facts_lines.append("; ".join(move_facts))

    if intent_fact:
        facts_lines.append(f"Why coach played this: {intent_fact}")

    if threat_facts:
        facts_lines.append(f"Threats created: {'; '.join(threat_facts)}")

    if opportunities:
        facts_lines.append(f"Student can exploit: {opportunities}")

    if feature_facts:
        facts_lines.append(f"Board features: {'; '.join(feature_facts)}")

    facts_lines.append(f"Game phase: {phase}")

    if opening_name:
        facts_lines.append(f"Opening: {opening_name}")

    if player_weaknesses:
        facts_lines.append(f"Student struggles with: {', '.join(player_weaknesses)}")

    facts_block = "FACTS:\n" + "\n".join(f"- {line}" for line in facts_lines)

    system_prompt = f"""You are a chess coach converting analysis into coaching language for a {user_rating}-rated student.

RULES:
- ONLY use the FACTS below. Do NOT analyze chess yourself — you don't know how.
- Speak directly to the student: "I played...", "Notice...", "Can you see..."
- 2-3 sentences max. End with ONE question making them look at the board.
- Do NOT reveal best moves. If they can exploit something, hint — don't name the move.
- No generic principles. Every word must come from the facts.
- Use the PIECE NAMES and SQUARE NAMES from the facts. Be specific.

Respond in JSON only: {{"explanation": "...", "question": "...", "hint": "..."}}"""

    try:
        logger.info(f"[SMART-COACHING] Calling LLM for coach move: {move_san}, key={scenario_key}")
        response = await call_llm(system_prompt, facts_block)
        logger.info(f"[SMART-COACHING] LLM response received: {len(response)} chars")

        import json
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()

        data = json.loads(clean)

        result = {
            "move_san": move_san,
            "explanation": data.get("explanation", f"I played {move_san}."),
            "plan": "",
            "threats": [],
            "teaching_point": "",
            "hint_for_user": data.get("question", ""),
        }
        if data.get("hint"):
            result["opponent_opportunity"] = {
                "type": "smart",
                "message": data["hint"],
            }

        # ─── STORE IN CACHE ───
        if db is not None:
            try:
                await db.coaching_phrases.update_one(
                    {"scenario_key": scenario_key, "type": "coach_move"},
                    {"$set": {
                        "scenario_key": scenario_key,
                        "type": "coach_move",
                        "response": result,
                        "facts": facts_lines,
                        "intent": intent_key,
                        "phase": phase,
                        "piece_moved": piece_name,
                        "target_piece": target_piece_name,
                        "threat_type": threat_type_key,
                        "created_at": __import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
                logger.info(f"[SMART-COACHING] Cached: {scenario_key}")
            except Exception as cache_err:
                logger.debug(f"Cache store failed: {cache_err}")

        return result

    except Exception as e:
        logger.warning(f"[SMART-COACHING] LLM failed, falling back: {e}")
        return None


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
) -> Optional[Dict]:
    """
    Generate Socratic question for mistakes using LLM as language layer.
    All chess facts come from our fundamentals checker and detectors.
    """
    if severity in ("good", "brilliant"):
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

    # ─── CHECK CACHE ───
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

    facts_block = f"""FACTS:
- Student played: {move_san} ({move_desc})
- This was a {severity}
- What went wrong: {'; '.join(problem_facts) if problem_facts else 'unclear'}
- Game phase: {phase}"""

    system_prompt = f"""You convert chess analysis into ONE Socratic question for a {user_rating}-rated student.

RULES:
- ONLY use the FACTS below. Do NOT analyze chess yourself.
- Ask about what they MISSED — never tell them the answer or the best move.
- Reference specific pieces and squares from the facts.
- ONE question, under 20 words. ONE hint sentence.

Respond in JSON only: {{"question": "...", "hint": "..."}}"""

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
    pieces = len(board.piece_map())
    if pieces >= 28:
        return "opening"
    elif pieces >= 14:
        return "middlegame"
    else:
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
