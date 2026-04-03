"""
Interactive Routes
==================

Handles interactive analysis, puzzles, Lichess integration, and position evaluation.

Endpoints:
- GET  /training/reflection-impact          - Reflection impact on training
- GET  /training/should-override            - Check if reflection overrides curriculum
- GET  /games/{game_id}/time-analysis       - Time analysis for a game
- GET  /games/{game_id}/move/{move_number}/time-context - Time context for a move
- GET  /games/{game_id}/move/{move_number}/intent-hypotheses - Move intent hypotheses
- POST /games/{game_id}/move/{move_number}/analyze-gap - Cognitive gap analysis
- POST /game/{game_id}/ask                  - Ask about a move (interactive analysis)
- POST /generate-puzzle                     - Generate a puzzle from weakness
- GET  /training/lichess/opening            - Lichess opening explorer data
- GET  /training/lichess/variations         - Lichess opening variations
- GET  /training/lichess/search             - Search Lichess openings by name
- GET  /training/progress                   - Training progress stats
- GET  /eval/position                       - Analyze position with Stockfish
- GET  /eval/best-move                      - Get best move for position
- POST /eval/move                           - Analyze a specific move
- GET  /eval/cache-stats                    - Eval cache statistics
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone
import uuid
import logging

from time_analysis_service import (
    extract_time_data_from_pgn,
    get_time_context_for_move,
    analyze_time_management,
)
from move_intent_service import (
    get_move_intent_summary,
)
from cognitive_gap_service import (
    analyze_cognitive_gap,
    get_coaching_message,
)
from cognitive_gap_intelligence_service import (
    persist_cognitive_gap,
    check_recurrence_alerts,
)
from player_profile_service import categorize_weakness

logger = logging.getLogger(__name__)

# Create router for interactive endpoints
router = APIRouter(tags=["Interactive"])

# Database reference - will be set by server.py
db = None

# LLM function reference - will be set by server.py
call_llm_fn = None


def set_db(database):
    """Set the database reference for interactive routes"""
    global db
    db = database


def set_llm(llm_fn):
    """Set the LLM function reference for interactive routes"""
    global call_llm_fn
    call_llm_fn = llm_fn


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== REFLECTION ROUTES ====================

@router.get("/training/reflection-impact")
async def get_reflection_impact(user: User = Depends(get_current_user)):
    """Get how reflections have impacted training focus."""
    impact = await db.reflection_impacts.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    if not impact:
        return {
            "total_reflections": 0,
            "layer_boosts": {},
            "pattern_counts": {},
            "message": "No reflections yet - your reflections will shape your training!"
        }
    return impact

@router.get("/training/should-override")
async def check_training_override(user: User = Depends(get_current_user)):
    """Check if reflection data suggests overriding the rating-based curriculum."""
    from reflection_training_service import should_override_curriculum
    result = await should_override_curriculum(db, user.user_id)
    return result


# ==================== TIME ANALYSIS ENDPOINTS ====================

@router.get("/games/{game_id}/time-analysis")
async def get_game_time_analysis(game_id: str, user: User = Depends(get_current_user)):
    """
    Get time analysis for a game - time spent on each move, time pressure detection.

    Uses clock data from PGN to provide insights like:
    - "You spent only 3 seconds on move 23 - a rushed decision"
    - "You played 8 moves under time pressure"
    """
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1}
    )

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    pgn = game.get("pgn", "")
    user_color = game.get("user_color", "white")

    # Extract time data from PGN
    time_data = extract_time_data_from_pgn(pgn)

    if not time_data.get("has_time_data"):
        return {"has_time_data": False, "message": "No clock data available for this game"}

    # Add time management analysis
    time_management = analyze_time_management(time_data, user_color)

    return {
        "has_time_data": True,
        "initial_time": time_data.get("initial_time"),
        "increment": time_data.get("increment"),
        "total_moves": time_data.get("total_moves"),
        "user_profile": time_data.get(f"{user_color}_profile"),
        "time_pressure_moves": time_data.get("time_pressure_moves"),
        "rushed_moves": time_data.get("rushed_moves"),
        "time_management": time_management,
        "moves": time_data.get("moves"),  # Full move-by-move time data
    }


@router.get("/games/{game_id}/move/{move_number}/time-context")
async def get_move_time_context(game_id: str, move_number: int, user: User = Depends(get_current_user)):
    """
    Get time context for a specific move.

    Used in reflection to understand if a mistake was due to:
    - Time pressure (< 30s remaining)
    - Rushed decision (< 5s spent)
    - Normal thinking time
    """
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1}
    )

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    pgn = game.get("pgn", "")
    user_color = game.get("user_color", "white")

    # Extract time data
    time_data = extract_time_data_from_pgn(pgn)

    if not time_data.get("has_time_data"):
        return {"has_data": False, "message": "No clock data available"}

    # Get context for specific move
    context = get_time_context_for_move(time_data, move_number, user_color)

    return context


# ==================== MOVE INTENT HYPOTHESES ====================

@router.get("/games/{game_id}/move/{move_number}/intent-hypotheses")
async def get_move_intent_hypotheses(game_id: str, move_number: int, user: User = Depends(get_current_user)):
    """
    Get position-specific hypotheses about why the user played their move.

    This is the crucial layer between Stockfish analysis and user reflection.
    Analyzes the actual position to generate confident hypotheses like:
    - "Were you trying to control the e5 square?"
    - "Were you defending the d4 pawn?"

    Only returns CONFIDENT hypotheses that are actually valid in the position.
    """
    # Get the game analysis to find the move
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )

    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")

    # Find the move evaluation
    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])

    target_eval = None
    for ev in evals:
        if ev.get("move_number") == move_number:
            target_eval = ev
            break

    if not target_eval:
        raise HTTPException(status_code=404, detail="Move not found in analysis")

    fen_before = target_eval.get("fen_before")
    user_move = target_eval.get("move")
    best_move = target_eval.get("best_move")

    if not fen_before or not user_move:
        return {"hypotheses": [], "message": "Insufficient data for analysis"}

    # Get the intent summary with hypotheses
    intent_summary = get_move_intent_summary(fen_before, user_move, best_move)

    # Also get time context if available
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1}
    )

    time_context = None
    if game and game.get("pgn"):
        from time_analysis_service import extract_time_data_from_pgn, get_time_context_for_move
        time_data = extract_time_data_from_pgn(game["pgn"])
        if time_data.get("has_time_data"):
            time_context = get_time_context_for_move(time_data, move_number, game.get("user_color", "white"))

    return {
        "move_number": move_number,
        "user_move": user_move,
        "best_move": best_move,
        "fen_before": fen_before,
        "intent_summary": intent_summary,
        "hypotheses": intent_summary.get("hypotheses", []),
        "primary_intent": intent_summary.get("primary_intent"),
        "time_context": time_context,
    }


# ==================== COGNITIVE GAP ANALYSIS ====================

class CognitiveGapRequest(BaseModel):
    """Request body for cognitive gap analysis."""
    user_stated_plan: Optional[str] = None
    user_hypothesis_category: Optional[str] = None
    user_confidence: Optional[str] = None

@router.post("/games/{game_id}/move/{move_number}/analyze-gap")
async def analyze_move_cognitive_gap(
    game_id: str,
    move_number: int,
    request: CognitiveGapRequest,
    user: User = Depends(get_current_user)
):
    """
    Analyze the cognitive gap for a specific move.

    This is the CRITICAL endpoint that determines WHY the user made a mistake.
    Uses the user's stated plan + position analysis to give precise diagnosis.

    Returns:
        - primary_gap: The main cognitive error type
        - confidence: How sure we are about this diagnosis
        - evidence: Concrete proof from the position
        - explanation: Human-readable explanation
        - coaching_focus: What to work on
    """
    # Get game analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )

    if not analysis:
        raise HTTPException(status_code=404, detail="Game analysis not found")

    # Find the move evaluation
    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])

    target_eval = None
    for ev in evals:
        if ev.get("move_number") == move_number:
            target_eval = ev
            break

    if not target_eval:
        raise HTTPException(status_code=404, detail="Move not found in analysis")

    fen_before = target_eval.get("fen_before")
    user_move = target_eval.get("move")
    best_move = target_eval.get("best_move")
    eval_before = target_eval.get("eval_before", 0)
    eval_after = target_eval.get("eval_after", 0)
    threat = target_eval.get("threat")

    if not fen_before or not user_move or not best_move:
        return {"error": "Insufficient data for analysis"}

    # Get time context
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1}
    )

    time_spent = None
    clock_remaining = None

    if game and game.get("pgn"):
        from time_analysis_service import extract_time_data_from_pgn, get_time_context_for_move
        time_data = extract_time_data_from_pgn(game["pgn"])
        if time_data.get("has_time_data"):
            tc = get_time_context_for_move(time_data, move_number, game.get("user_color", "white"))
            if tc.get("has_data"):
                time_spent = tc.get("time_spent")
                clock_remaining = tc.get("clock_after")

    # Perform cognitive gap analysis
    gap_result = analyze_cognitive_gap(
        fen_before=fen_before,
        user_move_san=user_move,
        best_move_san=best_move,
        eval_before=eval_before,
        eval_after=eval_after,
        threat_description=threat,
        user_stated_plan=request.user_stated_plan,
        user_hypothesis_category=request.user_hypothesis_category,
        time_spent_seconds=time_spent,
        clock_remaining_seconds=clock_remaining,
        user_confidence=request.user_confidence,
    )

    # Add coaching message
    coaching_message = get_coaching_message(gap_result)

    # ENHANCEMENT: For positional misreads and generic gaps, get POSITION-SPECIFIC insights
    if gap_result.get("primary_gap") in ["positional_misread", "calculation_depth", "wrong_plan"]:
        try:
            from services.position_strategy_analyzer import generate_move_specific_insight
            pv_after_best = target_eval.get("pv_after_best", [])
            # cp_loss can be directly from stockfish or calculated
            cp_loss_val = target_eval.get("cp_loss", 0)
            if not cp_loss_val and eval_before is not None and eval_after is not None:
                cp_loss_val = abs(int((eval_before - eval_after) * 100))
            user_color = game.get("user_color", "white") if game else "white"

            logger.info(f"Position-specific insight: threat={threat}, cp_loss={cp_loss_val}, user_move={user_move}, best_move={best_move}")

            specific_insight = generate_move_specific_insight(
                fen_before=fen_before,
                user_move=user_move,
                best_move=best_move,
                pv_after_best=pv_after_best,
                cp_loss=cp_loss_val,
                user_color=user_color,
                threat=threat
            )

            # Override generic explanation with position-specific one
            if specific_insight and not specific_insight.get("error"):
                # Build a better explanation
                what_missed = specific_insight.get("what_you_missed", "")
                what_best_achieves = specific_insight.get("what_best_move_achieves", "")
                why_wrong = specific_insight.get("why_your_move_was_wrong", "")

                # Create concise, specific explanation
                if what_missed and what_best_achieves:
                    gap_result["explanation"] = f"{what_missed}. {best_move} would have {what_best_achieves.lower() if what_best_achieves[0].isupper() else what_best_achieves}."
                elif what_best_achieves:
                    gap_result["explanation"] = f"{best_move} {what_best_achieves.lower() if what_best_achieves[0].isupper() else what_best_achieves}. {why_wrong}"

                # Add position-specific coaching focus
                if specific_insight.get("the_idea_you_should_learn"):
                    gap_result["coaching_focus"] = specific_insight["the_idea_you_should_learn"]

                # Add how to spot this
                if specific_insight.get("how_to_spot_this"):
                    gap_result["how_to_spot"] = specific_insight["how_to_spot_this"]

                logger.info(f"Enhanced positional misread with specific insight: {gap_result['explanation'][:100]}")
        except Exception as e:
            logger.warning(f"Could not enhance with position-specific insight: {e}")

    # PHASE 1: Persist the cognitive gap for tracking
    await persist_cognitive_gap(
        db=db,
        user_id=user.user_id,
        game_id=game_id,
        move_number=move_number,
        gap_analysis=gap_result,
        user_plan=request.user_stated_plan,
        user_confidence=request.user_confidence,
    )

    # PHASE 2: Check for recurrence alerts
    recurrence_alert = await check_recurrence_alerts(db, user.user_id, gap_result.get("primary_gap", "unclear"))

    return {
        "move_number": move_number,
        "user_move": user_move,
        "best_move": best_move,
        "cp_loss": abs(eval_before - eval_after),
        "gap_analysis": gap_result,
        "coaching_message": coaching_message,
        "time_context": {
            "time_spent": time_spent,
            "clock_remaining": clock_remaining,
        } if time_spent else None,
        "recurrence_alert": recurrence_alert,
    }


# ==================== ASK ABOUT MOVE (Interactive Analysis) ====================

class AskAboutMoveRequest(BaseModel):
    """Request for asking questions about a specific position/move"""
    fen: Optional[str] = None  # Position AFTER the move (current board state)
    fen_before: Optional[str] = None  # Position BEFORE the move (for analyzing what user should have played)
    question: str
    played_move: Optional[str] = None  # The move that was played (if any)
    alternative_move: Optional[str] = None  # A "what if" move to analyze
    move_number: Optional[int] = None
    user_color: Optional[str] = "white"
    conversation_history: Optional[List[Dict[str, str]]] = None  # Previous Q&A pairs for context
    context: Optional[str] = None  # Additional context (badge type, threat info, etc.)

@router.post("/game/{game_id}/ask")
async def ask_about_move(game_id: str, req: AskAboutMoveRequest, user: User = Depends(get_current_user)):
    """
    Ask a question about a specific position/move in a game.
    Uses Stockfish for analysis and GPT for explanation.

    Example questions:
    - "What if I played Nf3 instead?"
    - "Why is this move a blunder?"
    - "What was my opponent threatening?"
    - "What should my plan be here?"
    """
    import chess

    try:
        # Use fen_before if fen is not provided (common from badge detail modal)
        position_fen = req.fen or req.fen_before

        if not position_fen:
            raise HTTPException(status_code=400, detail="Either fen or fen_before must be provided")

        # Validate FEN
        try:
            board = chess.Board(position_fen)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid FEN position")

        user_color = req.user_color or "white"
        current_turn = "white" if board.turn else "black"

        # Position BEFORE the move - this is where we analyze what user SHOULD have played
        board_before = None
        if req.fen_before:
            try:
                board_before = chess.Board(req.fen_before)
            except:
                board_before = None
        elif req.fen:
            # If only fen is provided, use it as board_before too
            board_before = board

        # Analyze the position BEFORE the move to find what user should have played
        best_move_for_user = None
        best_line_for_user = []
        eval_before = None

        if board_before and req.played_move:
            # Get cached Stockfish analysis for position BEFORE the move
            from position_analysis_cache_service import PositionAnalysisService
            cache_service = PositionAnalysisService(db)

            before_result = await cache_service.get_position_eval(req.fen_before, depth=18)
            if before_result.get("source") != "error":
                eval_before = before_result.get("eval_cp", 0)
                best_move_for_user = before_result.get("best_move_san", "")
                best_line_for_user = before_result.get("pv_san", [])[:5]

        # Get cached Stockfish analysis for the CURRENT position (after the move)
        from position_analysis_cache_service import PositionAnalysisService
        cache_service = PositionAnalysisService(db)

        current_result = await cache_service.get_position_eval(req.fen, depth=18)
        if current_result.get("source") == "error":
            raise HTTPException(status_code=500, detail="Failed to analyze position")

        # Extract evaluation
        eval_score = current_result.get("eval_cp", 0)
        is_mate = current_result.get("eval_mate") is not None
        current_result.get("eval_mate")

        # Extract best move for CURRENT position (opponent's best response)
        opponent_best_move = current_result.get("best_move_san", "")

        stockfish_data = {
            "evaluation": eval_score,
            "eval_type": "mate" if is_mate else "cp",
            "best_move": opponent_best_move,  # This is opponent's best move (current turn)
            "best_line": current_result.get("pv_san", [])[:5],
            "is_check": board.is_check(),
            "is_checkmate": board.is_checkmate(),
            "turn": current_turn,
            # NEW: Best move for the USER (from position BEFORE their move)
            "user_best_move": best_move_for_user,
            "user_best_line": best_line_for_user,
            "eval_before": eval_before
        }

        # If user asks about an alternative move, analyze it from position BEFORE
        alternative_analysis = None
        if req.alternative_move and board_before:
            try:
                # Parse and validate the alternative move on the board BEFORE
                alt_move = board_before.parse_san(req.alternative_move)
                alt_board = board_before.copy()
                alt_board.push(alt_move)

                # Analyze position after alternative move using cache
                alt_result = await cache_service.get_position_eval(alt_board.fen(), depth=18)
                if alt_result.get("source") != "error":
                    alternative_analysis = {
                        "move": req.alternative_move,
                        "resulting_fen": alt_board.fen(),
                        "evaluation": alt_result.get("eval_cp"),
                        "eval_type": "mate" if alt_result.get("eval_mate") else "cp",
                        "opponent_best_response": alt_result.get("best_move_san"),
                        "continuation": alt_result.get("pv_san", [])[:5]
                    }
            except Exception:
                alternative_analysis = {"error": f"Invalid move: {req.alternative_move}"}

        # Store played move analysis
        played_analysis = None
        if req.played_move:
            played_analysis = {
                "move": req.played_move,
                "evaluation_after": eval_score,
                "opponent_best_response": opponent_best_move,
                "user_should_have_played": best_move_for_user,
                "user_best_line": best_line_for_user
            }

        # Build human-readable position description
        def describe_position(b):
            """Generate a human-readable description of the chess position"""
            piece_names = {
                'K': 'King', 'Q': 'Queen', 'R': 'Rook', 'B': 'Bishop', 'N': 'Knight', 'P': 'Pawn',
                'k': 'King', 'q': 'Queen', 'r': 'Rook', 'b': 'Bishop', 'n': 'Knight', 'p': 'Pawn'
            }

            white_pieces = []
            black_pieces = []

            for square in chess.SQUARES:
                piece = b.piece_at(square)
                if piece:
                    square_name = chess.square_name(square)
                    piece_name = piece_names.get(piece.symbol(), 'Piece')
                    if piece.color == chess.WHITE:
                        white_pieces.append(f"{piece_name} on {square_name}")
                    else:
                        black_pieces.append(f"{piece_name} on {square_name}")

            return f"White: {', '.join(white_pieces)}\nBlack: {', '.join(black_pieces)}"

        # Get legal moves in SAN notation (for current position)
        legal_moves_san = [board.san(m) for m in board.legal_moves]
        legal_moves_str = ', '.join(legal_moves_san[:20])
        if len(legal_moves_san) > 20:
            legal_moves_str += f" (and {len(legal_moves_san) - 20} more)"

        # Determine context for the prompt
        user_color_name = user_color.title()

        # === USE DETERMINISTIC MISTAKE CLASSIFIER ===
        # This is the "truth layer" - no LLM guessing allowed
        mistake_analysis = None
        structured_facts = []

        if req.played_move and req.fen_before and eval_before is not None:
            try:
                from mistake_classifier import (
                    classify_mistake, get_verbalization_template,
                    find_forks, find_pins
                )

                mistake = classify_mistake(
                    fen_before=req.fen_before,
                    fen_after=req.fen or req.fen_before,
                    move_played=req.played_move,
                    best_move=best_move_for_user or "",
                    eval_before=eval_before,
                    eval_after=eval_score,
                    user_color=user_color,
                    move_number=getattr(req, 'move_number', 20),
                    threat=None
                )

                mistake_analysis = {
                    "type": mistake.mistake_type.value,
                    "eval_drop": mistake.eval_drop,
                    "template": get_verbalization_template(mistake),
                    "pattern_details": mistake.pattern_details
                }

                # Build structured facts for LLM
                structured_facts.append(f"MISTAKE_TYPE: {mistake.mistake_type.value}")
                structured_facts.append(f"EVAL_DROP: {mistake.eval_drop:.1f} pawns")
                if mistake.pattern_details.get("reason"):
                    structured_facts.append(f"REASON: {mistake.pattern_details['reason']}")
                structured_facts.append(f"COACHING_TEMPLATE: {get_verbalization_template(mistake)}")

                # Check for tactical patterns in position
                user_chess_color = chess.WHITE if user_color == "white" else chess.BLACK
                forks = find_forks(board_before, not user_chess_color) if board_before else []
                pins = find_pins(board_before, user_chess_color) if board_before else []

                if forks:
                    structured_facts.append(f"THREAT_FORK: Opponent has fork potential with {forks[0]['attacker_piece']}")
                if pins:
                    structured_facts.append(f"YOUR_PINNED_PIECE: {pins[0]['pinned_piece']} on {pins[0]['pinned_square']}")

            except Exception as e:
                logger.warning(f"Mistake classifier error: {e}")
                mistake_analysis = None

        # === BUILD PERSONALITY LAYER PROMPT ===
        # LLM can ONLY verbalize the structured facts - it cannot invent chess analysis

        prompt = f"""You are an encouraging chess coach. Your job is to VERBALIZE the structured analysis below in a friendly, educational way.

IMPORTANT RULES:
1. You CANNOT invent chess analysis. Only explain what is in the STRUCTURED FACTS.
2. You CANNOT claim a move creates a fork/pin/skewer unless it's in the STRUCTURED FACTS.
3. Keep it simple for a ~1300 rated player.
4. Be encouraging - this is a learning moment.
5. 3-4 sentences maximum.

STUDENT'S COLOR: {user_color_name}
STUDENT PLAYED: {req.played_move if req.played_move else 'N/A'}
BEST MOVE WAS: {best_move_for_user if best_move_for_user else 'N/A'}

=== STRUCTURED FACTS (from deterministic analysis) ===
{chr(10).join(structured_facts) if structured_facts else 'No structured analysis available.'}
===

STUDENT'S QUESTION: {req.question}

"""

        if alternative_analysis and "error" not in alternative_analysis:
            prompt += f"""
ALTERNATIVE MOVE ANALYZED: {req.alternative_move}
- Evaluation: {alternative_analysis.get('evaluation')} centipawns
- Opponent's best response: {alternative_analysis.get('opponent_best_response')}
"""

        # Add conversation history for context
        if req.conversation_history and len(req.conversation_history) > 0:
            prompt += "\nPREVIOUS CONVERSATION:\n"
            for exchange in req.conversation_history[-3:]:
                prompt += f"Student: {exchange.get('question', '')}\n"
                prompt += f"Coach: {exchange.get('answer', '')}\n"
            prompt += "\n"

        prompt += """
Respond naturally as a supportive mentor. Use the structured facts to explain what happened.
If the student asks about something not in the facts, say "Let me check..." and stick to what we know from the analysis."""

        # Get GPT response using OpenAI directly
        try:
            answer = await call_llm_fn(
                system_message="You are a chess coach who ONLY verbalizes pre-analyzed facts. You cannot invent chess analysis.",
                user_message=prompt,
                model="gpt-4o-mini"
            )
            answer = answer.strip()
        except Exception as e:
            logger.error(f"GPT error in ask_about_move: {e}")
            # Fallback to the deterministic template (no LLM needed)
            if mistake_analysis:
                answer = mistake_analysis.get("template", f"The best move was {best_move_for_user}.")
            else:
                answer = f"The best move here was {best_move_for_user or stockfish_data['best_move']}."

        # Build response with the deterministic analysis included
        return {
            "answer": answer,
            "stockfish": {
                "evaluation": stockfish_data["evaluation"],
                "eval_type": stockfish_data["eval_type"],
                "best_move": stockfish_data["best_move"],  # Opponent's best move
                "best_line": stockfish_data["best_line"],
                "user_best_move": best_move_for_user,  # What USER should have played
                "user_best_line": best_line_for_user
            },
            "alternative_analysis": alternative_analysis,
            "played_analysis": played_analysis,
            "mistake_analysis": mistake_analysis  # NEW: Include structured analysis
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ask about move error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to analyze position")


# ==================== CHALLENGE/PUZZLE ROUTES ====================

class GeneratePuzzleRequest(BaseModel):
    pattern_id: Optional[str] = None
    category: str = "tactical"
    subcategory: str = "general"

@router.post("/generate-puzzle")
async def generate_puzzle(req: GeneratePuzzleRequest, user: User = Depends(get_current_user)):
    """Generate a puzzle based on user's weakness pattern from PlayerProfile"""
    import json

    # Get player profile for context
    profile = await db.player_profiles.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )

    # Determine which weakness to target
    weakness_context = ""
    target_category = req.category
    target_subcategory = req.subcategory

    if req.pattern_id:
        # Use specified pattern
        pattern = await db.mistake_patterns.find_one(
            {"pattern_id": req.pattern_id, "user_id": user.user_id},
            {"_id": 0}
        )
        if pattern:
            target_category, target_subcategory = categorize_weakness(
                pattern.get("category", "tactical"),
                pattern.get("subcategory", "one_move_blunders")
            )
            weakness_context = f"The player struggles with: {target_subcategory.replace('_', ' ')} ({target_category}). {pattern.get('description', '')}"
    elif profile and profile.get("top_weaknesses"):
        # Use top weakness from profile
        top_weakness = profile["top_weaknesses"][0]
        target_category = top_weakness.get("category", "tactical")
        target_subcategory = top_weakness.get("subcategory", "one_move_blunders")
        weakness_context = f"Player's #1 weakness: {target_subcategory.replace('_', ' ')} ({target_category}). Score: {top_weakness.get('decayed_score', 1)}"
    else:
        weakness_context = f"Focus on {req.subcategory.replace('_', ' ')} in the {req.category} category."

    # Get player level for difficulty calibration
    player_level = "intermediate"
    if profile:
        player_level = profile.get("estimated_level", "intermediate")

    system_prompt = f"""You are a chess puzzle creator. Create a tactical puzzle for training.

Player Level: {player_level.upper()}
Target Weakness: {weakness_context}

Create a puzzle that specifically targets this weakness. The puzzle should:
1. Have a clear winning move or sequence
2. Be instructive for the specific weakness
3. Difficulty appropriate for {player_level} level ({"1 move" if player_level == "beginner" else "1-3 moves"})

Respond in JSON format ONLY:
{{
    "title": "Short descriptive title",
    "description": "Brief description of what to look for",
    "fen": "Valid FEN position string",
    "player_color": "white" or "black",
    "solution_san": "The correct move in SAN notation (e.g., Nxf7)",
    "solution": [{{"from": "e4", "to": "f7"}}],
    "hint": "A subtle hint without giving away the answer",
    "theme": "{target_subcategory}",
    "explanation": {{
        "thinking_error": "What thinking error does this puzzle train against",
        "one_repeatable_rule": "The rule this puzzle teaches"
    }}
}}

Make sure the FEN is valid and the solution is correct for that position."""

    try:
        response = await call_llm_fn(
            system_message=system_prompt,
            user_message=f"Generate a {target_category} puzzle focusing on {target_subcategory.replace('_', ' ')}",
            model="gpt-4o-mini"
        )

        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]

        puzzle = json.loads(response_clean)

        # Store puzzle with target weakness for feedback loop
        puzzle_doc = {
            "puzzle_id": f"puzzle_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "pattern_id": req.pattern_id,
            "target_category": target_category,
            "target_subcategory": target_subcategory,
            "solved": None,  # Will be updated when user submits result
            "solve_time_seconds": None,
            **puzzle,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.puzzles.insert_one(puzzle_doc)
        puzzle_doc.pop('_id', None)

        return puzzle_doc

    except Exception as e:
        logger.error(f"Puzzle generation error: {e}")
        # Return a fallback puzzle with proper tracking fields
        fallback_puzzle = {
            "puzzle_id": f"puzzle_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "target_category": target_category,
            "target_subcategory": target_subcategory,
            "title": "Tactical Training",
            "description": f"Find the best move in this {target_subcategory.replace('_', ' ')} position",
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
            "player_color": "white",
            "solution_san": "Qxf7#",
            "solution": [{"from": "h5", "to": "f7"}],
            "hint": "Look for a forcing move that attacks multiple pieces",
            "theme": target_subcategory,
            "explanation": {
                "thinking_error": "Missing forcing moves that end the game",
                "one_repeatable_rule": "Always check for checkmate threats first"
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.puzzles.insert_one(fallback_puzzle)
        fallback_puzzle.pop('_id', None)
        return fallback_puzzle


# ============================================================================
# LICHESS OPENING EXPLORER INTEGRATION
# ============================================================================

@router.get("/training/lichess/opening")
async def get_lichess_opening_data(
    moves: str = None,  # Comma-separated SAN moves, e.g., "e4,e5,Nf3"
    source: str = "lichess"  # "lichess" or "masters"
):
    """
    Fetch opening data from Lichess Opening Explorer.

    Returns real statistics from millions of games including:
    - Opening name and ECO code
    - Win/draw/loss percentages
    - Most popular continuations with statistics
    """
    from lichess_opening_service import get_opening_info

    move_list = moves.split(",") if moves else []
    data = await get_opening_info(move_list, source=source)

    return data


@router.get("/training/lichess/variations")
async def get_lichess_variations(
    moves: str = None,  # Comma-separated SAN moves
    depth: int = 3
):
    """
    Get popular variations from a position using Lichess data.

    Explores the most common continuations up to the specified depth.
    """
    from lichess_opening_service import get_opening_variations

    move_list = moves.split(",") if moves else []
    variations = await get_opening_variations(move_list, depth=min(depth, 5))

    return {
        "starting_moves": move_list,
        "variations": variations
    }


@router.get("/training/lichess/search")
async def search_lichess_opening(name: str):
    """
    Search for an opening by name and get Lichess statistics.

    Examples: "Italian Game", "Sicilian Najdorf", "Queen's Gambit"
    """
    from lichess_opening_service import search_opening_by_name

    data = await search_opening_by_name(name)

    if not data:
        return {"error": f"Opening '{name}' not found"}

    return data


# /training/progress already in routes/training.py


# =============================================================================
# POSITION ANALYSIS ENDPOINTS (Stockfish + Cache)
# =============================================================================

@router.get("/eval/position")
async def analyze_position_endpoint(
    fen: str,
    depth: int = 18
):
    """
    Analyze a chess position using Stockfish with caching.

    - First request: ~2 seconds (Stockfish runs)
    - Subsequent requests: Instant (from cache)

    Returns evaluation, best move, and principal variation.
    """
    from position_analysis_cache_service import PositionAnalysisService

    service = PositionAnalysisService(db)
    result = await service.get_position_eval(fen, depth=depth)

    return result


@router.get("/eval/best-move")
async def get_best_move_endpoint(fen: str, depth: int = 18):
    """
    Quick endpoint to get just the best move for a position.
    """
    from position_analysis_cache_service import PositionAnalysisService

    service = PositionAnalysisService(db)
    best_move = await service.get_best_move(fen, depth=depth)

    return {
        "fen": fen,
        "best_move": best_move
    }


@router.post("/eval/move")
async def analyze_move_endpoint(
    fen: str,
    move: str,
    depth: int = 18
):
    """
    Analyze a specific move - get evaluation and classification.

    Args:
        fen: Position before the move
        move: The move played (SAN or UCI format)

    Returns:
        Move analysis with cp_loss and classification (blunder/mistake/etc)
    """
    from position_analysis_cache_service import PositionAnalysisService

    service = PositionAnalysisService(db)
    result = await service.analyze_move(fen, move, depth=depth)

    return result


@router.get("/eval/cache-stats")
async def get_eval_cache_stats():
    """Get cache statistics."""
    from position_analysis_cache_service import PositionAnalysisService

    service = PositionAnalysisService(db)
    stats = await service.get_cache_stats()

    return stats
