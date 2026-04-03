"""
Analysis Routes
===============

Handles game analysis, position analysis, platform connection, game import,
and thought/reflection endpoints.

Endpoints:
- POST /connect-platform - Connect Chess.com/Lichess account
- POST /import-games - Import games from Chess.com/Lichess
- POST /analyze-game - Full game analysis (Stockfish + AI coaching)
- GET /analysis/{game_id} - Get analysis for a game
- GET /analysis/{game_id}/enriched - Get enriched analysis with human coach layer
- GET /memory/patterns - Get aggregated patterns across all games
- GET /analysis/{game_id}/opening-fundamentals - Opening principle analysis
- POST /analyze-position - Analyze a single position
- POST /best-moves - Get top N best moves for a position
- POST /games/{game_id}/thought - Save user thought for a move
- GET /games/{game_id}/thoughts - Get all user thoughts for a game
- POST /analyze-plan - Analyze user's intended plan
- GET /analysis-queue - Get analysis queue status
- GET /thoughts/all - Get all user thoughts across all games
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging, httpx, uuid, re

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analysis"])
db = None
call_llm_fn = None

def set_db(database):
    global db
    db = database

def set_llm(llm_fn):
    global call_llm_fn
    call_llm_fn = llm_fn

from routes.auth import get_current_user, User
from models.game_models import ImportGamesRequest, AnalyzeGameRequest, ConnectPlatformRequest, Game, GameCreate, MistakePattern, GameAnalysis
from helpers.analysis_helpers import compute_recurring_pattern_context, parse_pgn_games


# ==================== INLINE MODELS ====================

class PositionAnalysisRequest(BaseModel):
    fen: str
    depth: int = 18

class ThoughtSubmission(BaseModel):
    move_number: int
    fen: str = ""
    thought_text: str

class PlanAnalysisRequest(BaseModel):
    fen: str  # Position before user's move
    user_move: str  # The move user played
    plan_moves: List[str]  # User's intended continuation
    plan_reasoning: str = ""  # User's text explanation

class UserThoughtRequest(BaseModel):
    """Request for saving user's thought on a specific move."""
    move_number: int
    fen: str
    thought_text: str
    move_played: Optional[str] = None
    best_move: Optional[str] = None
    evaluation_type: Optional[str] = None  # "blunder", "mistake", "inaccuracy"
    cp_loss: Optional[int] = None


# ==================== SECTION A: PLATFORM CONNECTION + IMPORT ====================

@router.post("/connect-platform", tags=["Platforms"])
async def connect_platform(req: ConnectPlatformRequest, user: User = Depends(get_current_user)):
    """Connect Chess.com or Lichess username to user profile"""
    platform = req.platform.lower()
    username = req.username.strip()

    if platform == "chess.com":
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(f"https://api.chess.com/pub/player/{username}")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Chess.com username not found")

        await db.users.update_one(
            {"user_id": user.user_id},
            {"$set": {"chess_com_username": username}}
        )
    elif platform == "lichess":
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(f"https://lichess.org/api/user/{username}")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Lichess username not found")

        await db.users.update_one(
            {"user_id": user.user_id},
            {"$set": {"lichess_username": username}}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid platform")

    return {"message": f"Connected {platform} account: {username}"}


@router.post("/import-games", tags=["Games"])
async def import_games(req: ImportGamesRequest, user: User = Depends(get_current_user)):
    """Import games from Chess.com or Lichess"""
    platform = req.platform.lower()
    username = req.username.strip()

    # Validate that the username matches user's linked account
    user_doc = await db.users.find_one({"user_id": user.user_id})
    if user_doc:
        linked_chesscom = user_doc.get("chess_com_username") or user_doc.get("chesscom_username")
        linked_lichess = user_doc.get("lichess_username")

        if platform == "chess.com" and linked_chesscom:
            if linked_chesscom.lower() != username.lower():
                raise HTTPException(
                    status_code=400,
                    detail=f"You can only import games from your linked Chess.com account ({linked_chesscom}). Unlink first to change accounts."
                )
        elif platform == "lichess" and linked_lichess:
            if linked_lichess.lower() != username.lower():
                raise HTTPException(
                    status_code=400,
                    detail=f"You can only import games from your linked Lichess account ({linked_lichess}). Unlink first to change accounts."
                )

    games_to_import = []

    if platform == "chess.com":
        async with httpx.AsyncClient(timeout=30.0) as client_http:
            archives_resp = await client_http.get(
                f"https://api.chess.com/pub/player/{username}/games/archives"
            )
            if archives_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Could not fetch Chess.com archives")

            archives = archives_resp.json().get("archives", [])
            recent_archives = archives[-3:] if len(archives) > 3 else archives

            for archive_url in recent_archives:
                try:
                    pgn_url = archive_url + "/pgn"
                    pgn_resp = await client_http.get(pgn_url)
                    if pgn_resp.status_code == 200:
                        parsed = parse_pgn_games(pgn_resp.text, "chess.com", username)
                        games_to_import.extend(parsed[:20])
                except Exception as e:
                    logger.error(f"Error fetching archive: {e}")
                    continue

    elif platform == "lichess":
        async with httpx.AsyncClient(timeout=30.0) as client_http:
            resp = await client_http.get(
                f"https://lichess.org/api/games/user/{username}",
                params={"max": 30, "pgnInJson": False},
                headers={"Accept": "application/x-chess-pgn"}
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Could not fetch Lichess games")

            parsed = parse_pgn_games(resp.text, "lichess", username)
            games_to_import.extend(parsed)

    else:
        raise HTTPException(status_code=400, detail="Invalid platform")

    imported_count = 0
    for game_data in games_to_import[:30]:
        existing = await db.games.find_one({
            "user_id": user.user_id,
            "pgn": game_data['pgn']
        })
        if existing:
            continue

        game = Game(
            user_id=user.user_id,
            **game_data
        )
        doc = game.model_dump()
        doc['imported_at'] = doc['imported_at'].isoformat()
        await db.games.insert_one(doc)
        imported_count += 1

        # Queue for Stockfish analysis
        try:
            await db.analysis_queue.insert_one({
                "game_id": doc["game_id"],
                "user_id": user.user_id,
                "pgn": doc.get("pgn", ""),
                "user_color": doc.get("user_color", "white"),
                "status": "pending",
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "attempts": 0,
            })
        except Exception as q_err:
            logger.error(f"Failed to queue game {doc['game_id']} for analysis: {q_err}")

    # GAMIFICATION: Award XP for importing games
    if imported_count > 0:
        try:
            from gamification_service import add_xp, increment_stat, check_and_award_achievements, update_streak
            for _ in range(imported_count):
                await add_xp(user.user_id, "game_imported")
                await increment_stat(user.user_id, "games_imported")

            # First game achievement
            if imported_count >= 1:
                await check_and_award_achievements(user.user_id, "games_imported", imported_count)

            await update_streak(user.user_id)
        except Exception as gam_err:
            logger.warning(f"Gamification update error (non-critical): {gam_err}")

    return {"imported": imported_count, "total_found": len(games_to_import)}


# ==================== SECTION B: ANALYZE GAME (THE BIG ONE) ====================

@router.post("/analyze-game")
async def analyze_game(req: AnalyzeGameRequest, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Analyze a game with Stockfish engine + AI coaching using PlayerProfile + RAG"""
    import json

    from config import STOCKFISH_DEPTH, STOCKFISH_MAX_RETRIES, DEFAULT_RATING
    from stockfish_service import analyze_game_with_stockfish
    from rag_service import build_rag_context, create_game_embeddings, create_pattern_embedding, create_analysis_embedding
    from player_profile_service import get_or_create_profile, update_profile_after_analysis, validate_explanation, categorize_weakness
    from cqs_service import calculate_cqs, get_stricter_prompt_constraints, log_cqs_result, MAX_REGENERATIONS
    from phase_theory_service import analyze_game_phases, get_rating_bracket
    from mistake_card_service import extract_mistake_cards_from_analysis
    from gamification_service import add_xp, increment_stat, update_streak, update_best_accuracy

    game = await db.games.find_one(
        {"game_id": req.game_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    existing_analysis = await db.game_analyses.find_one(
        {"game_id": req.game_id},
        {"_id": 0}
    )

    # If force re-analysis, delete old analysis first
    if existing_analysis and req.force:
        await db.game_analyses.delete_one({"game_id": req.game_id})
        existing_analysis = None
        logger.info(f"Force re-analysis requested for game {req.game_id}")

    if existing_analysis:
        return existing_analysis

    # ============ STEP 0: STOCKFISH ENGINE ANALYSIS (ACCURATE MOVE EVALUATION) ============
    # Stockfish is the ONLY source of truth for blunders/mistakes/accuracy
    # We retry up to 3 times if it fails
    logger.info(f"Running Stockfish analysis for game {req.game_id}")
    user_color = game.get('user_color', 'white')

    stockfish_result = None
    max_stockfish_retries = STOCKFISH_MAX_RETRIES

    for attempt in range(max_stockfish_retries):
        try:
            stockfish_result = analyze_game_with_stockfish(
                game['pgn'],
                user_color=user_color,
                depth=STOCKFISH_DEPTH  # Good balance of speed and accuracy
            )

            if stockfish_result and stockfish_result.get("success"):
                # Verify we actually got data
                user_stats = stockfish_result.get("user_stats", {})
                if user_stats.get("accuracy", 0) > 0 or len(stockfish_result.get("moves", [])) > 0:
                    logger.info(f"Stockfish analysis succeeded on attempt {attempt + 1}")
                    break
                else:
                    logger.warning(f"Stockfish returned empty data on attempt {attempt + 1}, retrying...")
                    stockfish_result = None
            else:
                logger.warning(f"Stockfish analysis failed on attempt {attempt + 1}: {stockfish_result.get('error') if stockfish_result else 'No result'}")
                stockfish_result = None
        except Exception as e:
            logger.error(f"Stockfish analysis error on attempt {attempt + 1}: {e}")
            stockfish_result = None

        if attempt < max_stockfish_retries - 1:
            import asyncio
            await asyncio.sleep(1)  # Brief pause before retry

    if not stockfish_result or not stockfish_result.get("success"):
        logger.error(f"Stockfish analysis failed after {max_stockfish_retries} attempts for game {req.game_id}")

    # Extract Stockfish evaluations for GPT context
    stockfish_context = ""
    stockfish_move_data = []
    if stockfish_result and stockfish_result.get("success"):
        user_stats = stockfish_result.get("user_stats", {})
        moves = stockfish_result.get("moves", [])

        # Build context for GPT
        stockfish_context = f"""
=== STOCKFISH ENGINE ANALYSIS (DEPTH 18) ===
Player: {user_color}
Accuracy: {user_stats.get('accuracy', 0)}%
Blunders: {user_stats.get('blunders', 0)}
Mistakes: {user_stats.get('mistakes', 0)}
Inaccuracies: {user_stats.get('inaccuracies', 0)}
Best Moves: {user_stats.get('best_moves', 0)}
Excellent Moves: {user_stats.get('excellent_moves', 0)}
Average CP Loss: {user_stats.get('avg_cp_loss', 0)}

=== MOVE-BY-MOVE ENGINE EVALUATION ===
"""
        # Include significant moves (blunders, mistakes, inaccuracies)
        significant_moves = [m for m in moves if m.get('evaluation') in ['blunder', 'mistake', 'inaccuracy']]
        for m in significant_moves[:10]:  # Limit to top 10 bad moves
            eval_type = m.get('evaluation', 'unknown')
            # Handle both string and enum types
            if hasattr(eval_type, 'value'):
                eval_type = eval_type.value

            stockfish_context += f"""
Move {m.get('move_number')}: {m.get('move')} ({eval_type.upper()})
- CP Loss: {m.get('cp_loss', 0)} centipawns
- Best was: {m.get('best_move')}
- Eval before: {m.get('eval_before', 0)/100:.1f} → after: {m.get('eval_after', 0)/100:.1f}"""

            # Add PV lines for mistakes (these explain WHY it's bad)
            if eval_type.lower() in ['inaccuracy', 'mistake', 'blunder']:
                threat = m.get('threat')
                pv_played = m.get('pv_after_played', [])
                pv_best = m.get('pv_after_best', [])

                if threat:
                    stockfish_context += f"\n- OPPONENT'S THREAT: {threat}"
                if pv_played:
                    stockfish_context += f"\n- LINE AFTER YOUR MOVE: {' '.join(pv_played)}"
                if pv_best:
                    stockfish_context += f"\n- LINE AFTER BEST MOVE: {m.get('best_move')} {' '.join(pv_best)}"

            stockfish_context += "\n"
        stockfish_move_data = moves
        logger.info(f"Stockfish: {user_stats.get('blunders', 0)} blunders, {user_stats.get('mistakes', 0)} mistakes, {user_stats.get('accuracy', 0)}% accuracy")

    # Step 1: Get or create PlayerProfile (FIRST-CLASS requirement)
    logger.info(f"Loading PlayerProfile for user {user.user_id}")
    profile = await get_or_create_profile(db, user.user_id, user.name)

    # Step 2: Build RAG context (SUPPORTS memory, doesn't define habits)
    logger.info(f"Building RAG context for game {req.game_id}")
    await build_rag_context(db, user.user_id, game)

    # Step 3: Get user's first name
    first_name = user.name.split()[0] if user.name else "friend"

    # Step 4: Build explicit memory context for coach
    top_weaknesses = profile.get("top_weaknesses", [])[:3]
    improvement_trend = profile.get("improvement_trend", "stuck")
    games_analyzed = profile.get("games_analyzed_count", 0)

    # Build memory call-out strings
    memory_callouts = []
    for w in top_weaknesses:
        subcat = w.get("subcategory", "").replace("_", " ")
        count = w.get("occurrence_count", 0)
        if count >= 3:
            memory_callouts.append(f"- {subcat}: seen {count} times before")
        elif count >= 2:
            memory_callouts.append(f"- {subcat}: this happened before")

    memory_section = ""
    if memory_callouts:
        memory_section = "COACH MEMORY (reference these when relevant):\n" + "\n".join(memory_callouts)

    # Build improvement awareness
    improvement_note = ""
    if improvement_trend == "improving":
        improvement_note = "STATUS: Student is IMPROVING. Acknowledge progress."
    elif improvement_trend == "regressing":
        improvement_note = "STATUS: Student needs support. Be encouraging, focus on basics."
    else:
        improvement_note = "STATUS: Student is steady. Gentle push to improve."

    system_prompt = f"""You are an experienced chess coach with a warm, calm teaching style.

Your approach:
- Patient, principle-driven, supportive
- Focus on thinking habits, not moves
- Simple English, short sentences
- Sound like a mentor, not a commentator
- Use Indian warmth sparingly (max once in summary, e.g., "Well done" not "Beta" repeatedly)

IMPORTANT: I have already analyzed this game with Stockfish (world's best chess engine).
The engine data below is ACCURATE - trust it completely for move evaluations.

=== HOW TO EXPLAIN MISTAKES ===
For INACCURACIES/MISTAKES/BLUNDERS, Stockfish provides:
- OPPONENT'S THREAT: The move that punishes your mistake
- LINE AFTER YOUR MOVE: What happens next (shows the problem)
- LINE AFTER BEST MOVE: What would have happened with the better choice

YOUR JOB: Turn these concrete lines into human coaching:
1. Explain what THREAT you missed (use the exact threat move from data)
2. Show WHY it hurts (use the line to explain consequences)
3. Compare to the better move (what you avoid by playing correctly)

Example transformation:
ENGINE DATA: Move 7: Qxb4 (INACCURACY), THREAT: Bb5+, LINE: Bb5+ Kf7 Ng5+
YOUR EXPLANATION: "You grabbed the pawn with Qxb4, but White has Bb5+ check. After Kf7 forced, Ng5+ comes with another attack. Your king gets stuck in the center - that's the real cost of taking that pawn."

DO NOT make up chess analysis. ONLY use the lines provided.
If no line is provided, give a general principle explanation.

{stockfish_context}

{first_name} played as {game['user_color']} in this game.
Games analyzed together: {games_analyzed}

{memory_section}

{improvement_note}

=== COACHING RULES ===

1. MEMORY REFERENCE (builds trust)
   - If current mistake matches a known weakness, mention it briefly
   - Example: "We've seen this pattern before."
   - Keep it to 1 sentence, non-judgmental

2. HABIT-FIRST EXPLANATIONS
   - Explain "what thinking habit caused this" not "what move was wrong"
   - One thinking error per mistake
   - Advice must apply to future games

3. COACH TONE
   - Warm but professional
   - Use Indian warmth sparingly (max once in summary)
   - Avoid: "Great job!", "Amazing!", "Brilliant!"
   - Prefer: "Good", "Solid", "Well played", "This needs work"

4. CRITICAL: CONSISTENCY RULE
   - If move is "good" or "solid" → NO negative thinking_pattern
   - If move is "good" or "solid" → thinking_pattern must be "solid_thinking" or null
   - Negative patterns ONLY for mistakes/blunders/inaccuracies

5. CONCEPTUAL GUIDANCE (no engine moves)
   - ❌ "Better: Play d5 earlier"
   - ✅ "Consider: Challenge the center with a pawn break"
   - ✅ "Think about: Developing before attacking"
   - Keep suggestions conceptual, applicable to any game

=== OUTPUT FORMAT (STRICT JSON) ===
{{
    "commentary": [
        {{
            "move_number": 5,
            "move": "h6",
            "evaluation": "inaccuracy",
            "intent": "What you were thinking (1 short sentence)",
            "feedback": "Coach feedback using CONCRETE lines from Stockfish data - mention the threat move and what happens (2-3 sentences)",
            "consider": "The better move and WHY it's better (use the PV line to explain)",
            "memory_note": "Brief memory reference if this matches past weakness (null otherwise)",
            "details": {{
                "thinking_pattern": "ONLY for mistakes: rushing, tunnel_vision, hope_chess, etc. For good moves: solid_thinking or null",
                "threat_line": "The EXACT threat from Stockfish (e.g., 'exd5 Qxd5 Nc3')",
                "rule": "A principle for future games"
            }}
        }}
    ],
    "blunders": 0,
    "mistakes": 0,
    "inaccuracies": 0,
    "best_moves": 0,
    "summary_p1": "2 sentences: Overall game assessment - what went well, where discipline showed.",
    "summary_p2": "2 sentences: The one habit to focus on + instruction for next game.",
    "improvement_note": "One sentence about progress trend (null if no data)",
    "identified_weaknesses": [
        {{
            "category": "tactical",
            "subcategory": "pin_blindness",
            "habit_description": "What thinking pattern caused this",
            "practice_tip": "What to practice"
        }}
    ],
    "identified_strengths": [
        {{
            "category": "tactical",
            "subcategory": "good_development",
            "description": "What they did well"
        }}
    ],
    "best_move_suggestions": [
        {{
            "move_number": 15,
            "best_move": "Nf3",
            "reason": "Controls the center and prepares castling"
        }}
    ],
    "focus_this_week": "The ONE habit to work on",
    "voice_script": "30-second calm spoken summary"
}}

=== STRICT RULES ===
1. NO engine language: no "stockfish", no centipawns, no "+0.5"
2. NO flashy commentary: no "Amazing!", "Brilliant!", "What a blunder!"
3. ONE lesson per mistake only
4. "Good/solid" moves NEVER get negative thinking_pattern
5. For MISTAKES: "consider" must reference the BETTER MOVE from Stockfish data and explain WHY using the PV line
6. For GOOD moves: "consider" should be null
7. Keep everything focused - coaches explain using actual moves, not vague principles
8. Memory references are factual, never shaming
9. STRENGTHS must be POSITIVE patterns only (e.g., "good_development", "solid_defense", "active_pieces")
   NEVER list weaknesses as strengths. If no clear strength, leave empty array.
10. For key blunders/mistakes, the "feedback" MUST mention:
    - The THREAT move opponent has (from OPPONENT'S THREAT in data)
    - What happens after (from LINE AFTER YOUR MOVE)
    Example: "After Qxb4, White has Bb5+ check. After Kf7, Ng5+ continues the attack."

Evaluations: "blunder", "mistake", "inaccuracy", "good", "solid", "neutral"
"""

    try:
        # CQS: Track regeneration attempts
        cqs_scores = []
        best_analysis_data = None
        best_cqs_result = None
        has_memory = len(memory_callouts) > 0

        for attempt in range(MAX_REGENERATIONS + 1):
            # Build prompt with stricter constraints on regeneration
            current_prompt = system_prompt
            if attempt > 0:
                stricter_rules = get_stricter_prompt_constraints(attempt)
                current_prompt = system_prompt + "\n" + stricter_rules
                logger.info(f"CQS: Regenerating analysis for {req.game_id}, attempt {attempt + 1}")

            # Use OpenAI directly
            response = await call_llm_fn(
                system_message=current_prompt,
                user_message=f"Please analyze this game:\n\n{game['pgn']}",
                model="gpt-4o-mini"
            )

            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3:]

            try:
                analysis_data = json.loads(response_clean)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error on attempt {attempt + 1}: {e}")
                continue

            # CQS: Evaluate quality
            cqs_result = calculate_cqs(
                analysis_data,
                has_memory=has_memory,
                memory_callouts=memory_callouts
            )
            cqs_scores.append(cqs_result["total_score"])

            # Log the result (internal only)
            log_cqs_result(req.game_id, cqs_result, attempt + 1, not cqs_result["should_regenerate"])

            # Keep track of best result
            if best_analysis_data is None or cqs_result["total_score"] > best_cqs_result["total_score"]:
                best_analysis_data = analysis_data
                best_cqs_result = cqs_result

            # Check if we should accept
            if not cqs_result["should_regenerate"]:
                break

            # If this is the last attempt, we'll use the best one
            if attempt >= MAX_REGENERATIONS:
                break

        # Use the best analysis data
        analysis_data = best_analysis_data
        cqs_result = best_cqs_result

        # Validate explanations against contract
        validated_commentary = []
        for item in analysis_data.get("commentary", []):
            explanation = item.get("explanation", {})
            if explanation:
                is_valid, errors = validate_explanation(explanation)
                if not is_valid:
                    logger.warning(f"Explanation validation failed: {errors}")
                    # Fix common issues
                    if len(explanation.get("thinking_error", "")) < 10:
                        explanation["thinking_error"] = "Move was made without full board awareness"
                    if len(explanation.get("one_repeatable_rule", "")) < 10:
                        explanation["one_repeatable_rule"] = "Always scan the whole board before moving"
            validated_commentary.append(item)

        # Map weaknesses to predefined categories with full details
        categorized_weaknesses = []
        for w in analysis_data.get("identified_weaknesses", []) or analysis_data.get("identified_patterns", []):
            cat, subcat = categorize_weakness(
                w.get("category", "tactical"),
                w.get("subcategory", "one_move_blunders")
            )
            categorized_weaknesses.append({
                "category": cat,
                "subcategory": subcat,
                "description": w.get("description", ""),
                "advice": w.get("advice", ""),
                "display_name": subcat.replace("_", " ").title()
            })

        # STOCKFISH is the ONLY source of truth for move evaluation
        # GPT is ONLY for commentary text, never for blunder/mistake counts
        sf_stats = stockfish_result.get("user_stats", {}) if stockfish_result else {}

        # Check if Stockfish analysis was successful
        stockfish_valid = stockfish_result and stockfish_result.get("success", False)
        stockfish_has_data = sf_stats.get("accuracy", 0) > 0 or len(stockfish_result.get("moves", [])) > 0 if stockfish_result else False

        if not stockfish_valid or not stockfish_has_data:
            # Stockfish failed - log warning and mark analysis as incomplete
            logger.warning(f"Stockfish analysis failed for game {req.game_id}. Analysis will be marked as incomplete.")
            analysis_incomplete = True
        else:
            analysis_incomplete = False

        analysis = GameAnalysis(
            game_id=req.game_id,
            user_id=user.user_id,
            commentary=validated_commentary,
            blunders=sf_stats.get("blunders", 0),
            mistakes=sf_stats.get("mistakes", 0),
            inaccuracies=sf_stats.get("inaccuracies", 0),
            best_moves=sf_stats.get("best_moves", 0),
            overall_summary=analysis_data.get("overall_summary", ""),
            identified_patterns=[]  # Legacy field - will also store full data separately
        )

        # Store voice script and key lesson for future use
        voice_script = analysis_data.get("voice_script", analysis_data.get("voice_script_summary", ""))
        focus_week = analysis_data.get("focus_this_week", analysis_data.get("key_lesson", ""))

        # Update mistake_patterns collection (legacy support for pattern IDs)
        for pattern_data in categorized_weaknesses:
            existing_pattern = await db.mistake_patterns.find_one({
                "user_id": user.user_id,
                "category": pattern_data["category"],
                "subcategory": pattern_data["subcategory"]
            })

            if existing_pattern:
                await db.mistake_patterns.update_one(
                    {"pattern_id": existing_pattern["pattern_id"]},
                    {
                        "$inc": {"occurrences": 1},
                        "$push": {"game_ids": req.game_id},
                        "$set": {"last_seen": datetime.now(timezone.utc).isoformat()}
                    }
                )
                analysis.identified_patterns.append(existing_pattern["pattern_id"])
            else:
                new_pattern = MistakePattern(
                    user_id=user.user_id,
                    category=pattern_data["category"],
                    subcategory=pattern_data["subcategory"],
                    description=pattern_data.get("description", ""),
                    game_ids=[req.game_id]
                )
                pattern_doc = new_pattern.model_dump()
                pattern_doc['first_seen'] = pattern_doc['first_seen'].isoformat()
                pattern_doc['last_seen'] = pattern_doc['last_seen'].isoformat()
                await db.mistake_patterns.insert_one(pattern_doc)
                pattern_doc.pop('_id', None)
                analysis.identified_patterns.append(new_pattern.pattern_id)

        analysis_doc = analysis.model_dump()
        analysis_doc['created_at'] = analysis_doc['created_at'].isoformat()

        # Store full data for frontend display
        analysis_doc['weaknesses'] = categorized_weaknesses
        analysis_doc['identified_weaknesses'] = categorized_weaknesses
        analysis_doc['strengths'] = analysis_data.get("identified_strengths", [])
        analysis_doc['focus_this_week'] = focus_week
        analysis_doc['key_lesson'] = focus_week  # Backward compatibility
        analysis_doc['voice_script_summary'] = voice_script
        analysis_doc['summary_p1'] = analysis_data.get("summary_p1", "")
        analysis_doc['summary_p2'] = analysis_data.get("summary_p2", "")
        analysis_doc['improvement_note'] = analysis_data.get("improvement_note", "")

        # Mark if Stockfish analysis failed - user can retry
        analysis_doc['stockfish_failed'] = analysis_incomplete
        if analysis_incomplete:
            analysis_doc['stockfish_error'] = "Stockfish engine analysis failed. Stats may be inaccurate. Please retry analysis."

        # Use Stockfish best move suggestions (accurate) - merge with GPT's reasoning
        stockfish_best_moves = []
        if stockfish_move_data:
            for m in stockfish_move_data:
                # Get evaluation type safely
                eval_type = m.get('evaluation', 'unknown')
                if hasattr(eval_type, 'value'):
                    eval_type = eval_type.value

                if eval_type in ['blunder', 'mistake'] and m.get('best_move'):
                    stockfish_best_moves.append({
                        "move_number": m.get('move_number'),
                        "played_move": m.get('move'),
                        "best_move": m.get('best_move'),
                        "cp_loss": m.get('cp_loss', 0),
                        "evaluation": eval_type,
                        "reason": f"Engine analysis shows this loses {m.get('cp_loss', 0)/100:.1f} pawns",
                        "pv": m.get('pv_after_best', [])  # Include PV line for playback on board
                    })
        analysis_doc['best_move_suggestions'] = stockfish_best_moves or analysis_data.get("best_move_suggestions", [])

        # Store Stockfish accuracy and detailed move analysis
        if stockfish_result and stockfish_result.get("success"):
            analysis_doc['stockfish_analysis'] = {
                "accuracy": sf_stats.get("accuracy", 0),
                "avg_cp_loss": sf_stats.get("avg_cp_loss", 0),
                "excellent_moves": sf_stats.get("excellent_moves", 0),
                "move_evaluations": stockfish_move_data
            }

        # ============ PHASE-AWARE STRATEGIC COACHING ============
        # Analyze game phases and provide rating-adaptive strategic lessons
        try:
            # Get user's rating for adaptive content
            user_rating = DEFAULT_RATING  # Default

            # Try to get rating from player profile
            player_profile = await db.player_profiles.find_one(
                {"user_id": user.user_id},
                {"_id": 0, "current_rating": 1}
            )
            if player_profile and player_profile.get("current_rating"):
                user_rating = player_profile.get("current_rating", DEFAULT_RATING)

            # Analyze game phases with rating-adaptive content
            phase_analysis = analyze_game_phases(game['pgn'], user_color, user_rating)

            if phase_analysis and not phase_analysis.get("error"):
                analysis_doc['phase_analysis'] = {
                    "phases": phase_analysis.get("phases", []),
                    "final_phase": phase_analysis.get("final_phase", "unknown"),
                    "endgame_info": phase_analysis.get("endgame_info"),
                    "phase_summary": phase_analysis.get("phase_summary", ""),
                    "total_moves": phase_analysis.get("total_moves", 0),
                    "phase_transitions": phase_analysis.get("phase_transitions", [])
                }

                # Strategic lesson - rating-adaptive
                strategic_lesson = phase_analysis.get("strategic_lesson", {})
                analysis_doc['strategic_lesson'] = {
                    "lesson_title": strategic_lesson.get("lesson_title", ""),
                    "what_to_remember": strategic_lesson.get("what_to_remember", []),
                    "theory_to_study": strategic_lesson.get("theory_to_study", []),
                    "one_sentence_takeaway": strategic_lesson.get("one_sentence_takeaway", ""),
                    "next_step": strategic_lesson.get("next_step", ""),
                    "phase_reached": strategic_lesson.get("phase_reached", ""),
                    "rating_bracket": strategic_lesson.get("rating_bracket", "intermediate")
                }

                # Phase-specific theory - rating-adaptive
                theory = phase_analysis.get("theory", {})
                analysis_doc['phase_theory'] = {
                    "phase": theory.get("phase", ""),
                    "key_principles": theory.get("key_principles", []),
                    "key_concept": theory.get("key_concept", ""),
                    "one_thing_to_remember": theory.get("one_thing_to_remember", ""),
                    "specific_advice": theory.get("specific_advice", []),
                    "rating_bracket": theory.get("rating_bracket", "intermediate")
                }

                logger.info(f"Phase analysis complete: {phase_analysis.get('final_phase')} phase, rating bracket: {get_rating_bracket(user_rating)}")
        except Exception as phase_err:
            logger.warning(f"Phase analysis failed (non-critical): {phase_err}")

        # CQS: Store internal metadata (NEVER exposed to users)
        analysis_doc['_cqs_internal'] = {
            "score": cqs_result["total_score"],
            "breakdown": cqs_result["breakdown"],
            "quality_level": cqs_result["quality_level"],
            "regeneration_attempts": len(cqs_scores),
            "all_scores": cqs_scores
        }

        await db.game_analyses.insert_one(analysis_doc)

        # Only mark as analyzed if analysis was complete and valid
        # If Stockfish failed, we have incomplete data
        if not analysis_incomplete:
            await db.games.update_one(
                {"game_id": req.game_id},
                {"$set": {
                    "is_analyzed": True,
                    "analysis_status": "completed"
                }}
            )
        else:
            # Mark as incomplete - needs re-analysis
            await db.games.update_one(
                {"game_id": req.game_id},
                {"$set": {
                    "is_analyzed": False,
                    "analysis_status": "incomplete",
                    "analysis_error": "Stockfish analysis failed or returned invalid data"
                }}
            )
            logger.warning(f"Game {req.game_id} marked as incomplete - Stockfish analysis failed")

        # Remove _id before returning
        analysis_doc.pop('_id', None)

        # IMPORTANT: Remove internal CQS data before returning to user
        analysis_doc.pop('_cqs_internal', None)

        # ============ MISTAKE MASTERY SYSTEM ============
        # Extract mistake cards from this analysis for spaced repetition training
        try:
            cards_created = await extract_mistake_cards_from_analysis(
                db, user.user_id, req.game_id, analysis_doc, game
            )
            if cards_created:
                logger.info(f"Created {len(cards_created)} mistake cards for user {user.user_id}")
        except Exception as card_err:
            logger.warning(f"Mistake card extraction failed (non-critical): {card_err}")

        # ============ COMMUNITY TRAINING POSITIONS ============
        # Auto-extract training-worthy positions for the community pool
        try:
            from services.community_training_service import extract_training_positions
            background_tasks.add_task(
                extract_training_positions, db, req.game_id, user.user_id
            )
        except Exception as extract_err:
            logger.warning(f"Community position extraction failed (non-critical): {extract_err}")

        # Step 5: UPDATE PLAYER PROFILE (CRITICAL - happens after every game)
        logger.info(f"Updating PlayerProfile for user {user.user_id}")
        background_tasks.add_task(
            update_profile_after_analysis,
            db,
            user.user_id,
            req.game_id,
            analysis_data.get("blunders", 0),
            analysis_data.get("mistakes", 0),
            analysis_data.get("best_moves", 0),
            categorized_weaknesses,
            analysis_data.get("identified_strengths", [])
        )

        # Create RAG embeddings in background (RAG supports memory, doesn't define habits)
        background_tasks.add_task(create_game_embeddings, db, game, user.user_id)
        background_tasks.add_task(create_analysis_embedding, db, analysis_doc, game, user.user_id)

        # GAMIFICATION: Award XP for game analysis
        try:
            await add_xp(user.user_id, "game_analyzed")
            await increment_stat(user.user_id, "games_analyzed")

            # Bonus XP for high accuracy
            accuracy = sf_stats.get("accuracy", 0)
            if accuracy >= 90:
                await add_xp(user.user_id, "accuracy_90_plus")
            await update_best_accuracy(user.user_id, accuracy)

            # Award for no blunders
            if sf_stats.get("blunders", 0) == 0:
                await add_xp(user.user_id, "no_blunders")
                await increment_stat(user.user_id, "no_blunders_games")

            # Update streak
            await update_streak(user.user_id)
        except Exception as gam_err:
            logger.warning(f"Gamification update error (non-critical): {gam_err}")

        for pattern_data in categorized_weaknesses:
            pattern = await db.mistake_patterns.find_one({
                "user_id": user.user_id,
                "category": pattern_data["category"],
                "subcategory": pattern_data["subcategory"]
            }, {"_id": 0})
            if pattern:
                background_tasks.add_task(create_pattern_embedding, db, pattern, user.user_id)

        return analysis_doc

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ==================== SECTION C: ANALYSIS RETRIEVAL ====================

@router.get("/analysis/{game_id}", tags=["Analysis"])
async def get_analysis(game_id: str, user: User = Depends(get_current_user)):
    """Get analysis for a specific game"""
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "_cqs_internal": 0}  # Exclude internal CQS data
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Also get the game to extract full move list
    game = await db.games.find_one(
        {"game_id": game_id},
        {"_id": 0, "pgn": 1, "user_color": 1}
    )

    if game and game.get("pgn"):
        # Parse PGN to get all moves
        import chess.pgn
        import io
        try:
            pgn_io = io.StringIO(game["pgn"])
            chess_game = chess.pgn.read_game(pgn_io)
            if chess_game:
                full_moves = []
                board = chess_game.board()
                move_number = 1
                for i, move in enumerate(chess_game.mainline_moves()):
                    fen_before = board.fen()
                    san = board.san(move)
                    is_white = (i % 2 == 0)

                    # Find if this move has commentary (user's move)
                    user_color = game.get("user_color", "white")
                    is_user_move = (is_white and user_color == "white") or (not is_white and user_color == "black")

                    # Look up evaluation from commentary
                    evaluation = "neutral"
                    feedback = None
                    if is_user_move:
                        for c in analysis.get("commentary", []):
                            if c.get("move_number") == (move_number if is_white else move_number) and c.get("move") == san:
                                evaluation = c.get("evaluation", "neutral")
                                feedback = c.get("feedback")
                                break

                    full_moves.append({
                        "ply": i,
                        "move_number": move_number if is_white else move_number,
                        "move": san,
                        "fen": fen_before,
                        "is_white": is_white,
                        "is_user_move": is_user_move,
                        "evaluation": evaluation if is_user_move else "opponent",
                        "feedback": feedback
                    })

                    board.push(move)
                    if not is_white:
                        move_number += 1

                analysis["full_moves"] = full_moves
        except Exception as e:
            logger.warning(f"Failed to parse PGN for full moves: {e}")

    return analysis


@router.get("/analysis/{game_id}/enriched")
async def get_enriched_analysis(game_id: str, user: User = Depends(get_current_user)):
    """
    Get analysis enriched with human coach layer.

    Returns the standard analysis PLUS:
    - Behavioral tags (WHY the mistake happened)
    - Cross-game pattern connections
    - Coach voice summary
    - Specific moment insights
    """
    from services.human_coach_layer import enrich_game_analysis

    # Get base analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "_cqs_internal": 0}
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Enrich with human coach layer
    try:
        enriched = await enrich_game_analysis(db, game_id, user.user_id, analysis)
        return enriched
    except Exception as e:
        logger.warning(f"Failed to enrich analysis: {e}")
        # Return base analysis if enrichment fails
        return analysis


@router.get("/memory/patterns")
async def get_memory_patterns(user: User = Depends(get_current_user)):
    """
    Get aggregated patterns across all games for the Memory tab.

    Returns:
    - Category breakdown (what types of mistakes)
    - Top weaknesses with examples (clickable links to games)
    - Accuracy trend over recent games
    """
    from services.human_coach_layer import get_aggregated_patterns

    try:
        patterns = await get_aggregated_patterns(db, user.user_id)
        return patterns
    except Exception as e:
        logger.error(f"Failed to get memory patterns: {e}")
        return {
            "total_games": 0,
            "category_breakdown": {},
            "top_weaknesses": [],
            "accuracy_trend": [],
            "has_enough_data": False,
            "error": str(e)
        }


@router.get("/analysis/{game_id}/opening-fundamentals")
async def get_opening_fundamentals(game_id: str, user: User = Depends(get_current_user)):
    """
    Analyze a game's opening for fundamental principle violations.

    This teaches players the THINKING PROCESS, not just answers:
    - Did they castle early?
    - Did they develop before attacking?
    - Did they control the center?
    - Did they move the same piece twice?

    Each violation comes with:
    - What the principle is
    - Why it matters
    - What to THINK before each move (the habit to build)
    """
    from services.opening_fundamentals_checker import analyze_opening_fundamentals

    # Get the game
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0, "pgn": 1, "user_color": 1, "result": 1}
    )

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Parse moves from PGN
    try:
        import chess.pgn
        import io
        pgn_io = io.StringIO(game.get("pgn", ""))
        parsed_game = chess.pgn.read_game(pgn_io)

        if parsed_game:
            moves = [move.san() for move in parsed_game.mainline()]
        else:
            moves = []
    except Exception as e:
        logger.warning(f"Failed to parse PGN: {e}")
        moves = []

    if not moves:
        return {
            "error": "Could not parse game moves",
            "violations": [],
            "adherences": [],
            "score": 0
        }

    # Analyze opening fundamentals
    result = analyze_opening_fundamentals(
        moves=moves,
        user_color=game.get("user_color", "white"),
        game_result=game.get("result")
    )

    return result


# ==================== SECTION D: POSITION ANALYSIS ====================

@router.post("/analyze-position")
async def analyze_position(req: PositionAnalysisRequest, user: User = Depends(get_current_user)):
    """
    Analyze a single position using Stockfish with caching.
    Returns evaluation and best moves.
    """
    try:
        from position_analysis_cache_service import PositionAnalysisService

        service = PositionAnalysisService(db)
        result = await service.get_position_eval(req.fen, depth=req.depth)

        if result.get("source") == "error":
            raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))

        # Convert to expected format for backwards compatibility
        return {
            "success": True,
            "evaluation": {
                "centipawns": result.get("eval_cp", 0),
                "mate_in": result.get("eval_mate")
            },
            "best_move": {
                "uci": result.get("best_move"),
                "san": result.get("best_move_san")
            },
            "pv": result.get("pv_san", []),
            "depth": result.get("depth"),
            "source": result.get("source")  # Shows if from cache or fresh
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Position analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/best-moves")
async def get_best_moves(req: PositionAnalysisRequest, num_moves: int = 3, user: User = Depends(get_current_user)):
    """
    Get the top N best moves for a position using Stockfish.
    Useful for showing alternatives.
    """
    try:
        from stockfish_service import get_best_moves_for_position
        result = get_best_moves_for_position(req.fen, num_moves=num_moves, depth=req.depth)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
        return result
    except Exception as e:
        logger.error(f"Best moves analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SECTION E: THOUGHTS ====================

@router.post("/games/{game_id}/thought")
async def save_user_thought(
    game_id: str,
    data: ThoughtSubmission,
    user: User = Depends(get_current_user)
):
    """
    Save user's thought for a specific move ("What were you thinking?").
    This helps build cognitive gap analysis.
    """
    try:
        thought_doc = {
            "game_id": game_id,
            "user_id": user.user_id,
            "move_number": data.move_number,
            "fen": data.fen,
            "thought_text": data.thought_text,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # Upsert - one thought per move per game
        await db.user_thoughts.update_one(
            {"game_id": game_id, "user_id": user.user_id, "move_number": data.move_number},
            {"$set": thought_doc},
            upsert=True
        )

        return {"success": True, "message": "Thought saved"}
    except Exception as e:
        logger.error(f"Failed to save thought: {e}")
        raise HTTPException(status_code=500, detail="Failed to save thought")


@router.get("/games/{game_id}/thoughts")
async def get_user_thoughts(
    game_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get all user thoughts for a game.
    """
    try:
        thoughts = await db.user_thoughts.find(
            {"game_id": game_id, "user_id": user.user_id},
            {"_id": 0}
        ).to_list(100)

        return {"thoughts": thoughts}
    except Exception as e:
        logger.error(f"Failed to get thoughts: {e}")
        return {"thoughts": []}


@router.post("/analyze-plan")
async def analyze_user_plan_endpoint(
    data: PlanAnalysisRequest,
    user: User = Depends(get_current_user)
):
    """
    Analyze user's intended plan to identify where their calculation failed.

    Compares user's planned line with Stockfish's best responses to find
    the exact move where calculation broke down and identify the cognitive gap.
    """
    try:
        from services.plan_analysis_service import analyze_user_plan
        from dataclasses import asdict

        analysis = await analyze_user_plan(
            fen=data.fen,
            user_move=data.user_move,
            user_plan_moves=data.plan_moves,
            user_plan_reasoning=data.plan_reasoning
        )

        return {
            "success": True,
            "analysis": asdict(analysis)
        }

    except Exception as e:
        logger.error(f"Plan analysis failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ==================== SECTION F: ANALYSIS QUEUE + THOUGHTS/ALL ====================

@router.get("/analysis-queue")
async def get_analysis_queue_status(user: User = Depends(get_current_user)):
    """Get all games in the analysis queue for the current user"""
    queue_items = await db.analysis_queue.find(
        {"user_id": user.user_id, "status": {"$in": ["pending", "processing", "failed"]}},
        {"_id": 0}
    ).sort("created_at", 1).to_list(50)

    return {
        "queue": queue_items,
        "count": len(queue_items)
    }


@router.get("/thoughts/all")
async def get_all_user_thoughts(user: User = Depends(get_current_user)):
    """
    Get all thoughts the user has recorded across all games.
    Useful for pattern analysis.
    """
    thoughts = await db.user_thoughts.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    # Group by evaluation type for pattern analysis
    by_type = {}
    for t in thoughts:
        eval_type = t.get("evaluation_type", "unknown")
        if eval_type not in by_type:
            by_type[eval_type] = []
        by_type[eval_type].append(t)

    return {
        "thoughts": thoughts,
        "count": len(thoughts),
        "by_evaluation_type": {k: len(v) for k, v in by_type.items()}
    }
