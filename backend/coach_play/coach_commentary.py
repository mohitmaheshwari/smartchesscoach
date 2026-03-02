"""
Coach Commentary Service - Live Socratic Coaching

This is the brain of the interactive coaching system.
Instead of just telling users what to do, we:
1. Ask WHY they played a move
2. Compare their reasoning to position reality
3. Provide targeted feedback based on the GAP

The Socratic Method:
- Good move + right thinking → "Exactly! You saw it."
- Good move + wrong reason → "Good move, but it works because..."
- Bad move + reveals blind spot → "You focused on X, but did you see Y?"

Data Sources:
- Stockfish: Position evaluation and best moves
- Lichess Opening Explorer: Opening names and theory
- LLM (GPT-4o-mini): Understanding reasoning and generating feedback
"""

import chess
import chess.engine
import httpx
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import os
import time
import urllib.parse

STOCKFISH_PATH = "/usr/games/stockfish"

# Lichess API endpoints
LICHESS_OPENING_EXPLORER = "https://explorer.lichess.ovh/masters"
LICHESS_CLOUD_EVAL = "https://lichess.org/api/cloud-eval"


class MoveQuality(str, Enum):
    """Classification of move quality"""
    BRILLIANT = "brilliant"      # Much better than expected
    GREAT = "great"              # Found the best move
    GOOD = "good"                # Top 3 move, minimal eval loss
    OKAY = "okay"                # Reasonable, small eval loss
    INACCURACY = "inaccuracy"    # Suboptimal, noticeable eval loss
    MISTAKE = "mistake"          # Bad, significant eval loss
    BLUNDER = "blunder"          # Very bad, major eval loss


@dataclass
class PositionAnalysis:
    """Analysis of a chess position"""
    fen: str
    evaluation: float  # From side-to-move perspective
    mate_in: Optional[int]
    best_moves: List[Dict]  # [{move, eval, is_mate}]
    is_check: bool
    opening_name: Optional[str]
    opening_eco: Optional[str]
    phase: str  # "opening", "middlegame", "endgame"
    key_features: List[str]  # ["white has castled", "open d-file", etc.]


@dataclass 
class MoveAnalysis:
    """Analysis of a specific move"""
    move_san: str
    quality: MoveQuality
    eval_before: float
    eval_after: float
    eval_loss: float  # Centipawns lost (0 = best move)
    is_best_move: bool
    is_candidate: bool  # Top 3 move
    best_move_san: str
    best_continuation: List[str]
    tactical_themes: List[str]  # ["fork", "pin", "discovered attack"]


@dataclass
class CoachFeedback:
    """Coach's response to user's move and reasoning"""
    main_message: str           # Primary feedback
    reasoning_feedback: str     # Response to user's stated reasoning
    position_insight: str       # What's actually happening in the position
    improvement_tip: Optional[str]  # What to look for next time
    opening_comment: Optional[str]  # Opening-specific guidance
    move_quality: MoveQuality
    encouragement: bool         # Should we encourage?


class CoachCommentary:
    """
    The Socratic Chess Coach.
    
    Analyzes positions, evaluates moves, and generates
    targeted feedback based on user's reasoning.
    """
    
    def __init__(self):
        self._opening_cache = {}
        self._last_api_call = 0
        self._api_cooldown = 1.0  # seconds between Lichess API calls
    
    async def analyze_position(self, fen: str) -> PositionAnalysis:
        """
        Analyze a position using Stockfish and Lichess data.
        
        Returns comprehensive position analysis.
        """
        board = chess.Board(fen)
        
        # Get Stockfish analysis
        evaluation, mate_in, best_moves = await self._stockfish_analyze(fen, depth=15, multipv=3)
        
        # Get opening info (with caching and rate limiting)
        opening_name, opening_eco = await self._get_opening_info(fen)
        
        # Determine game phase
        phase = self._determine_phase(board)
        
        # Identify key position features
        key_features = self._identify_key_features(board)
        
        return PositionAnalysis(
            fen=fen,
            evaluation=evaluation,
            mate_in=mate_in,
            best_moves=best_moves,
            is_check=board.is_check(),
            opening_name=opening_name,
            opening_eco=opening_eco,
            phase=phase,
            key_features=key_features
        )
    
    async def analyze_move(
        self,
        fen_before: str,
        move_san: str,
        fen_after: str
    ) -> MoveAnalysis:
        """
        Analyze a specific move - was it good, bad, best?
        
        Compares to Stockfish's recommendations.
        """
        board_before = chess.Board(fen_before)
        
        # Get analysis of position before the move
        eval_before, _, best_moves_before = await self._stockfish_analyze(fen_before, depth=15, multipv=3)
        
        # Get evaluation after the move
        eval_after, mate_after, _ = await self._stockfish_analyze(fen_after, depth=12, multipv=1)
        
        # Flip eval_after to same perspective (it's opponent's turn now)
        eval_after = -eval_after
        
        # Calculate eval loss
        eval_loss = eval_before - eval_after
        if eval_loss < 0:
            eval_loss = 0  # Move was better than expected
        
        # Determine if this was the best move
        best_move_san = best_moves_before[0]["move"] if best_moves_before else None
        is_best = move_san == best_move_san
        
        # Check if it's a candidate move (top 3)
        candidate_moves = [m["move"] for m in best_moves_before[:3]]
        is_candidate = move_san in candidate_moves
        
        # Classify move quality
        quality = self._classify_move_quality(eval_loss, is_best, is_candidate)
        
        # Detect tactical themes
        tactical_themes = self._detect_tactical_themes(board_before, move_san)
        
        return MoveAnalysis(
            move_san=move_san,
            quality=quality,
            eval_before=eval_before,
            eval_after=eval_after,
            eval_loss=eval_loss,
            is_best_move=is_best,
            is_candidate=is_candidate,
            best_move_san=best_move_san,
            best_continuation=[m["move"] for m in best_moves_before],
            tactical_themes=tactical_themes
        )
    
    async def generate_feedback(
        self,
        position_analysis: PositionAnalysis,
        move_analysis: MoveAnalysis,
        user_reasoning: str,
        user_color: str,
        move_number: int
    ) -> CoachFeedback:
        """
        Generate Socratic coaching feedback.
        
        This is the heart of the coaching system - comparing
        user's reasoning to position reality and providing
        targeted, educational feedback.
        """
        # Build context for LLM
        prompt = self._build_feedback_prompt(
            position_analysis,
            move_analysis,
            user_reasoning,
            user_color,
            move_number
        )
        
        # Generate feedback using LLM
        feedback_text = await self._call_llm(prompt)
        
        # Parse LLM response into structured feedback
        feedback = self._parse_llm_feedback(
            feedback_text,
            move_analysis,
            position_analysis
        )
        
        return feedback
    
    def _build_feedback_prompt(
        self,
        position: PositionAnalysis,
        move: MoveAnalysis,
        user_reasoning: str,
        user_color: str,
        move_number: int
    ) -> str:
        """Build the prompt for LLM feedback generation."""
        
        # Determine the coaching context
        if move.is_best_move:
            move_assessment = "EXCELLENT - This was the best move!"
        elif move.is_candidate:
            move_assessment = f"GOOD - This was a strong candidate move (top 3). Best was {move.best_move_san}."
        elif move.quality in [MoveQuality.OKAY, MoveQuality.INACCURACY]:
            move_assessment = f"OKAY - Reasonable but not optimal. Better was {move.best_move_san}."
        elif move.quality == MoveQuality.MISTAKE:
            move_assessment = f"MISTAKE - This loses advantage. Much better was {move.best_move_san}."
        else:
            move_assessment = f"BLUNDER - This is a serious error. {move.best_move_san} was needed."
        
        opening_context = ""
        if position.opening_name:
            opening_context = f"\nOpening: {position.opening_name}"
        
        prompt = f"""You are a friendly chess coach having a real-time training session. 
The student just played a move and explained their reasoning. Give targeted Socratic feedback.

POSITION CONTEXT:
- Game phase: {position.phase}{opening_context}
- Position evaluation before move: {position.evaluation:+.2f} (positive = {user_color} is better)
- Key features: {', '.join(position.key_features[:3]) if position.key_features else 'standard position'}
- Move number: {move_number}

MOVE ANALYSIS:
- Student played: {move.move_san}
- Move quality: {move_assessment}
- Eval change: {position.evaluation:+.2f} → {move.eval_after:+.2f}
- Best moves were: {', '.join(move.best_continuation[:3])}

STUDENT'S REASONING:
"{user_reasoning}"

YOUR TASK:
Generate coaching feedback in this JSON format:
{{
  "main_message": "Your primary feedback (1-2 sentences, conversational)",
  "reasoning_feedback": "Response to their stated reasoning - was their thinking on track? (1-2 sentences)",
  "position_insight": "What was actually important in this position? (1 sentence)",
  "improvement_tip": "What should they look for next time? (1 sentence, optional - null if move was great)",
  "encouragement": true/false (true if move was good or reasoning showed understanding)
}}

COACHING STYLE:
- Be warm and encouraging, like a supportive coach
- If they found a great move, celebrate it!
- If their reasoning was wrong but move was good, gently correct the thinking
- If move was bad, focus on what they missed, not criticism
- Use "you" not "the student"
- Keep it conversational, not formal
- Reference their specific reasoning in your response

Respond with ONLY the JSON, no other text."""

        return prompt
    
    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM to generate feedback."""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            emergent_api_key = os.environ.get("EMERGENT_LLM_KEY", "")
            
            llm = LlmChat(
                api_key=emergent_api_key,
                model="openai/gpt-4o-mini"
            )
            
            response = await llm.chat([
                UserMessage(content=prompt)
            ])
            
            return response.content
            
        except Exception as e:
            print(f"LLM call failed: {e}")
            # Fallback to deterministic response
            return self._generate_fallback_feedback()
    
    def _generate_fallback_feedback(self) -> str:
        """Generate fallback feedback if LLM fails."""
        return '''{
  "main_message": "Interesting move! Let me think about your reasoning.",
  "reasoning_feedback": "I see what you were thinking.",
  "position_insight": "There are several factors to consider here.",
  "improvement_tip": "Always check for checks, captures, and threats.",
  "encouragement": true
}'''
    
    def _parse_llm_feedback(
        self,
        llm_response: str,
        move: MoveAnalysis,
        position: PositionAnalysis
    ) -> CoachFeedback:
        """Parse LLM response into structured feedback."""
        import json
        
        try:
            # Clean up response (remove markdown if present)
            response = llm_response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()
            
            data = json.loads(response)
            
            return CoachFeedback(
                main_message=data.get("main_message", "Good effort!"),
                reasoning_feedback=data.get("reasoning_feedback", ""),
                position_insight=data.get("position_insight", ""),
                improvement_tip=data.get("improvement_tip"),
                opening_comment=None,  # Set separately if in opening
                move_quality=move.quality,
                encouragement=data.get("encouragement", True)
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to parse LLM response: {e}")
            # Return basic feedback
            return CoachFeedback(
                main_message=self._get_quality_message(move.quality),
                reasoning_feedback="I understand your thinking.",
                position_insight="Consider all the tactical possibilities.",
                improvement_tip="Check for forcing moves first." if move.quality.value in ["mistake", "blunder"] else None,
                opening_comment=f"We're in the {position.opening_name}." if position.opening_name else None,
                move_quality=move.quality,
                encouragement=move.quality.value in ["brilliant", "great", "good", "okay"]
            )
    
    def _get_quality_message(self, quality: MoveQuality) -> str:
        """Get a basic message for move quality."""
        messages = {
            MoveQuality.BRILLIANT: "Brilliant! That was an exceptional move!",
            MoveQuality.GREAT: "Excellent! You found the best move!",
            MoveQuality.GOOD: "Good move! That's one of the best options.",
            MoveQuality.OKAY: "Reasonable move. There were slightly better options.",
            MoveQuality.INACCURACY: "That's a small inaccuracy. Let's see what was better.",
            MoveQuality.MISTAKE: "That's a mistake. Let me show you what was missed.",
            MoveQuality.BLUNDER: "That's a blunder. Something important was missed here."
        }
        return messages.get(quality, "Interesting move.")
    
    async def _stockfish_analyze(
        self,
        fen: str,
        depth: int = 15,
        multipv: int = 3
    ) -> Tuple[float, Optional[int], List[Dict]]:
        """
        Analyze position with Stockfish.
        
        Returns: (evaluation, mate_in, best_moves)
        """
        board = chess.Board(fen)
        
        if board.is_game_over():
            return 0.0, None, []
        
        try:
            transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
            
            # Get multi-PV analysis
            result = await engine.analyse(
                board,
                chess.engine.Limit(depth=depth),
                multipv=multipv
            )
            
            await engine.quit()
            
            best_moves = []
            evaluation = 0.0
            mate_in = None
            
            for i, info in enumerate(result):
                score = info.get("score")
                pv = info.get("pv", [])
                
                if score:
                    pov_score = score.relative  # From side-to-move perspective
                    
                    if i == 0:  # First line is the best
                        if pov_score.is_mate():
                            mate_in = pov_score.mate()
                            evaluation = 100.0 if mate_in > 0 else -100.0
                        else:
                            evaluation = pov_score.score() / 100.0 if pov_score.score() else 0.0
                    
                    if pv:
                        move_eval = pov_score.score() / 100.0 if pov_score.score() and not pov_score.is_mate() else (100.0 if pov_score.is_mate() and pov_score.mate() > 0 else -100.0)
                        best_moves.append({
                            "move": board.san(pv[0]),
                            "eval": move_eval,
                            "is_mate": pov_score.is_mate()
                        })
            
            return evaluation, mate_in, best_moves
            
        except Exception as e:
            print(f"Stockfish analysis error: {e}")
            return 0.0, None, []
    
    async def _get_opening_info(self, fen: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get opening name from Lichess Explorer API.
        
        Uses caching and rate limiting.
        """
        # Check cache first
        if fen in self._opening_cache:
            return self._opening_cache[fen]
        
        # Only query for opening positions (first ~15 moves)
        board = chess.Board(fen)
        if board.fullmove_number > 15:
            return None, None
        
        # Rate limiting
        now = time.time()
        if now - self._last_api_call < self._api_cooldown:
            await asyncio.sleep(self._api_cooldown - (now - self._last_api_call))
        
        try:
            # URL encode the FEN
            encoded_fen = urllib.parse.quote(fen)
            url = f"{LICHESS_OPENING_EXPLORER}?fen={encoded_fen}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"Accept": "application/json"},
                    timeout=5.0
                )
                
                self._last_api_call = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    opening = data.get("opening", {})
                    name = opening.get("name")
                    eco = opening.get("eco")
                    
                    # Cache the result
                    self._opening_cache[fen] = (name, eco)
                    return name, eco
                    
        except Exception as e:
            print(f"Opening API error: {e}")
        
        return None, None
    
    def _determine_phase(self, board: chess.Board) -> str:
        """Determine the game phase."""
        # Count material
        queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
        rooks = len(board.pieces(chess.ROOK, chess.WHITE)) + len(board.pieces(chess.ROOK, chess.BLACK))
        minors = (len(board.pieces(chess.KNIGHT, chess.WHITE)) + len(board.pieces(chess.KNIGHT, chess.BLACK)) +
                  len(board.pieces(chess.BISHOP, chess.WHITE)) + len(board.pieces(chess.BISHOP, chess.BLACK)))
        
        total_minors_and_major = queens * 2 + rooks + minors
        
        if board.fullmove_number <= 10:
            return "opening"
        elif total_minors_and_major <= 4:
            return "endgame"
        else:
            return "middlegame"
    
    def _identify_key_features(self, board: chess.Board) -> List[str]:
        """Identify key positional features."""
        features = []
        
        # Check castling status
        if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
            features.append("white can still castle")
        if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
            features.append("black can still castle")
        
        # Check for open files
        for file_idx in range(8):
            white_pawns = False
            black_pawns = False
            for rank_idx in range(8):
                piece = board.piece_at(chess.square(file_idx, rank_idx))
                if piece and piece.piece_type == chess.PAWN:
                    if piece.color == chess.WHITE:
                        white_pawns = True
                    else:
                        black_pawns = True
            
            if not white_pawns and not black_pawns:
                features.append(f"open {chess.FILE_NAMES[file_idx]}-file")
                break  # Only mention first open file
        
        # Check for piece activity
        if board.is_check():
            features.append("check!")
        
        # Count center control
        center_squares = [chess.E4, chess.D4, chess.E5, chess.D5]
        white_center = sum(1 for sq in center_squares if board.is_attacked_by(chess.WHITE, sq))
        black_center = sum(1 for sq in center_squares if board.is_attacked_by(chess.BLACK, sq))
        
        if white_center > black_center + 1:
            features.append("white controls the center")
        elif black_center > white_center + 1:
            features.append("black controls the center")
        
        return features[:5]  # Limit to 5 features
    
    def _classify_move_quality(
        self,
        eval_loss: float,
        is_best: bool,
        is_candidate: bool
    ) -> MoveQuality:
        """Classify move quality based on eval loss."""
        if is_best:
            return MoveQuality.GREAT
        elif is_candidate and eval_loss < 0.3:
            return MoveQuality.GOOD
        elif eval_loss < 0.1:
            return MoveQuality.GREAT  # Found an equally good move
        elif eval_loss < 0.3:
            return MoveQuality.GOOD
        elif eval_loss < 0.5:
            return MoveQuality.OKAY
        elif eval_loss < 1.0:
            return MoveQuality.INACCURACY
        elif eval_loss < 2.0:
            return MoveQuality.MISTAKE
        else:
            return MoveQuality.BLUNDER
    
    def _detect_tactical_themes(self, board: chess.Board, move_san: str) -> List[str]:
        """Detect tactical themes in a move."""
        themes = []
        
        try:
            move = board.parse_san(move_san)
            
            # Check if it's a capture
            if board.is_capture(move):
                themes.append("capture")
            
            # Check if it gives check
            board_after = board.copy()
            board_after.push(move)
            if board_after.is_check():
                themes.append("check")
            
            # Check if it's castling
            if board.is_castling(move):
                themes.append("castling")
            
        except Exception:
            pass
        
        return themes


# Convenience function for API use
async def get_coach_feedback(
    fen_before: str,
    move_san: str,
    fen_after: str,
    user_reasoning: str,
    user_color: str,
    move_number: int
) -> Dict[str, Any]:
    """
    Main entry point for getting coach feedback.
    
    Args:
        fen_before: Position before the move
        move_san: The move played (SAN notation)
        fen_after: Position after the move
        user_reasoning: User's stated reasoning for the move
        user_color: "white" or "black"
        move_number: Current move number
    
    Returns:
        Dict with coach feedback
    """
    coach = CoachCommentary()
    
    # Analyze position and move
    position_analysis = await coach.analyze_position(fen_before)
    move_analysis = await coach.analyze_move(fen_before, move_san, fen_after)
    
    # Generate Socratic feedback
    feedback = await coach.generate_feedback(
        position_analysis,
        move_analysis,
        user_reasoning,
        user_color,
        move_number
    )
    
    return {
        "main_message": feedback.main_message,
        "reasoning_feedback": feedback.reasoning_feedback,
        "position_insight": feedback.position_insight,
        "improvement_tip": feedback.improvement_tip,
        "opening_comment": feedback.opening_comment,
        "move_quality": feedback.move_quality.value,
        "encouragement": feedback.encouragement,
        "opening_name": position_analysis.opening_name,
        "phase": position_analysis.phase,
        "best_move": move_analysis.best_move_san,
        "was_best_move": move_analysis.is_best_move,
        "was_candidate": move_analysis.is_candidate,
        "eval_before": position_analysis.evaluation,
        "eval_after": move_analysis.eval_after
    }
