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
import logging

logger = logging.getLogger(__name__)

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
    best_move_uci: str  # UCI format for arrow display
    best_continuation: List[str]
    tactical_themes: List[str]  # ["fork", "pin", "discovered attack"]
    missed_tactic: Optional[str]  # Description of what was missed
    threat_explanation: Optional[str]  # Why the best move was better


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
        
        Compares to Stockfish's recommendations and explains WHY.
        Detects tactical themes (forks, pins, threats) that were missed.
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
        best_move_uci = ""
        if best_move_san:
            try:
                best_chess_move = board_before.parse_san(best_move_san)
                best_move_uci = best_chess_move.uci()
            except:
                best_move_uci = ""
        
        is_best = move_san == best_move_san
        
        # Check if it's a candidate move (top 3)
        candidate_moves = [m["move"] for m in best_moves_before[:3]]
        is_candidate = move_san in candidate_moves
        
        # Classify move quality
        quality = self._classify_move_quality(eval_loss, is_best, is_candidate)
        
        # Detect tactical themes in played move
        tactical_themes = self._detect_tactical_themes(board_before, move_san)
        
        # If not the best move, analyze what was missed
        missed_tactic = None
        threat_explanation = None
        
        if not is_best and best_move_san and eval_loss >= 0.3:
            missed_tactic, threat_explanation = await self._analyze_missed_opportunity(
                board_before, move_san, best_move_san, eval_loss
            )
        
        return MoveAnalysis(
            move_san=move_san,
            quality=quality,
            eval_before=eval_before,
            eval_after=eval_after,
            eval_loss=eval_loss,
            is_best_move=is_best,
            is_candidate=is_candidate,
            best_move_san=best_move_san,
            best_move_uci=best_move_uci,
            best_continuation=[m["move"] for m in best_moves_before],
            tactical_themes=tactical_themes,
            missed_tactic=missed_tactic,
            threat_explanation=threat_explanation
        )
    
    async def _analyze_missed_opportunity(
        self,
        board: chess.Board,
        played_move: str,
        best_move: str,
        eval_loss: float
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Analyze what tactical opportunity was missed.
        
        Returns (missed_tactic, explanation)
        - missed_tactic: "fork", "pin", "skewer", "discovered_attack", "mate_threat", etc.
        - explanation: Human-readable explanation of why best move was better
        """
        try:
            best_chess_move = board.parse_san(best_move)
            board_after_best = board.copy()
            board_after_best.push(best_chess_move)
            
            moving_piece = board.piece_at(best_chess_move.from_square)
            captured_piece = board.piece_at(best_chess_move.to_square)
            
            piece_names = {
                chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
                chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"
            }
            
            moving_piece_name = piece_names.get(moving_piece.piece_type, "piece") if moving_piece else "piece"
            to_square_name = chess.square_name(best_chess_move.to_square)
            
            # Check for check
            if board_after_best.is_check():
                # Check if it's checkmate
                if board_after_best.is_checkmate():
                    return "mate", f"{best_move} was checkmate!"
                
                # Check for fork (attacks multiple pieces while giving check)
                opponent_color = not board.turn
                attacked_pieces = []
                for square in chess.SQUARES:
                    piece = board_after_best.piece_at(square)
                    if piece and piece.color == opponent_color:
                        if board_after_best.is_attacked_by(board.turn, square):
                            if piece.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                                attacked_pieces.append((square, piece))
                
                if len(attacked_pieces) >= 2:
                    targets = [piece_names[p.piece_type] for _, p in attacked_pieces[:2]]
                    return "fork", f"{best_move} forks the {targets[0]} and {targets[1]} with check!"
                
                return "check", f"{best_move} gives check, winning tempo"
            
            # Check for capture of hanging piece
            if captured_piece:
                captured_name = piece_names.get(captured_piece.piece_type, "piece")
                # Was it a free capture?
                if not board.is_attacked_by(not board.turn, best_chess_move.to_square):
                    return "hanging_piece", f"{best_move} wins the {captured_name} which was undefended!"
                
                # Was it a good trade?
                piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, 
                               chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
                captured_val = piece_values.get(captured_piece.piece_type, 0)
                moving_val = piece_values.get(moving_piece.piece_type, 0) if moving_piece else 0
                
                if captured_val > moving_val:
                    return "winning_trade", f"{best_move} wins the {captured_name} for just a {moving_piece_name}"
            
            # Check for fork (knight or other piece attacking multiple targets)
            if moving_piece and moving_piece.piece_type == chess.KNIGHT:
                opponent_color = not board.turn
                high_value_targets = []
                for square in chess.SQUARES:
                    if board_after_best.is_attacked_by(board.turn, square):
                        piece = board_after_best.piece_at(square)
                        if piece and piece.color == opponent_color:
                            if piece.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                                high_value_targets.append((square, piece))
                
                if len(high_value_targets) >= 2:
                    targets = [f"{piece_names[p.piece_type]} on {chess.square_name(sq)}" 
                               for sq, p in high_value_targets[:2]]
                    return "knight_fork", f"{best_move} forks the {targets[0]} and {targets[1]}!"
            
            # Check for pins or skewers
            if moving_piece and moving_piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                # This would require ray tracing - simplified for now
                pass
            
            # Generic "better position" explanation
            if eval_loss >= 2.0:
                return "major_tactic", f"{best_move} was much stronger, gaining significant advantage"
            elif eval_loss >= 1.0:
                return "tactic", f"{best_move} was better, improving your position significantly"
            else:
                return "accuracy", f"{best_move} was more precise in this position"
            
        except Exception as e:
            return None, None
    
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

POSITION CONTEXT (FEN: {position.fen}):
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
- ONLY mention pieces on specific squares if you can VERIFY from the FEN they are there
- DO NOT guess or make up piece positions - stick to what's in the analysis above

Respond with ONLY the JSON, no other text."""

        return prompt
    
    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM to generate feedback using the app's LLM service."""
        try:
            # Use the app's centralized LLM service
            import sys
            sys.path.insert(0, '/app/backend')
            from llm_service import call_llm
            
            response = await call_llm(
                system_message="You are a helpful chess coach providing Socratic feedback.",
                user_message=prompt,
                model="gpt-4o-mini"
            )
            
            return response
            
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



async def get_quick_analysis(
    fen_before: str,
    move_san: str,
    fen_after: str,
    user_color: str,
    move_number: int
) -> Dict[str, Any]:
    """
    Quick analysis without LLM - for trigger evaluation.
    
    Returns position and move analysis without generating feedback.
    """
    coach = CoachCommentary()
    
    # Analyze position and move
    position_analysis = await coach.analyze_position(fen_before)
    move_analysis = await coach.analyze_move(fen_before, move_san, fen_after)
    
    return {
        "eval_before": position_analysis.evaluation,
        "eval_after": move_analysis.eval_after,
        "is_best_move": move_analysis.is_best_move,
        "is_candidate": move_analysis.is_candidate,
        "best_move": move_analysis.best_move_san,
        "best_move_uci": move_analysis.best_move_uci,
        "best_move_eval": position_analysis.evaluation,  # Best move maintains eval
        "move_quality": move_analysis.quality.value,
        "phase": position_analysis.phase,
        "opening_name": position_analysis.opening_name,
        "key_features": position_analysis.key_features
    }


async def generate_coach_chat_message(
    trigger_type: str,
    context: Dict,
    user_rating: int,
    user_color: str
) -> str:
    """
    Generate a natural chat message from the coach.
    
    Based on trigger type, generates appropriate message.
    Uses LLM for complex messages, templates for simple ones.
    """
    import sys
    sys.path.insert(0, '/app/backend')
    from llm_service import call_llm
    
    # Simple encouragement - use templates
    if trigger_type == "encouragement":
        from .coaching_triggers import CoachingTriggers
        triggers = CoachingTriggers(user_rating)
        return triggers.get_encouragement_phrase(
            context.get("message_type", "good_move"),
            context.get("streak", 0)
        )
    
    # Opening guidance - use LLM
    if trigger_type == "opening":
        opening_name = context.get("opening_name", "this opening")
        prompt = f"""You are a chess coach. The student just entered the {opening_name}. 
Give a brief, friendly one-sentence comment about this opening (what it's known for, typical plans).
Keep it under 20 words. Be conversational, not formal."""
        
        try:
            response = await call_llm(
                system_message="You are a friendly chess coach giving brief tips.",
                user_message=prompt,
                model="gpt-4o-mini"
            )
            return response.strip()
        except Exception:
            return f"We're in the {opening_name}. Solid choice!"
    
    # Warning/Teaching - use LLM for explanation with REAL position data
    if trigger_type in ["warning", "teaching", "reflection"]:
        move = context.get("move", "")
        eval_loss = context.get("eval_loss", 0)
        best_move = context.get("best_move", "")
        severity = context.get("severity", "inaccuracy")
        fen = context.get("fen", "")
        pv_after_best = context.get("pv_after_best", [])
        threat = context.get("threat", "")
        
        # Get REAL position-specific insight instead of making LLM guess
        position_insight = ""
        try:
            import sys
            sys.path.insert(0, '/app/backend')
            from services.position_strategy_analyzer import generate_move_specific_insight
            
            if fen and move and best_move:
                cp_loss = int(abs(eval_loss) * 100) if eval_loss else 0
                insight = generate_move_specific_insight(
                    fen_before=fen,
                    user_move=move,
                    best_move=best_move,
                    pv_after_best=pv_after_best,
                    cp_loss=cp_loss,
                    user_color=context.get("user_color", "white"),
                    threat=threat
                )
                if insight and not insight.get("error"):
                    what_missed = insight.get("what_you_missed", "")
                    what_best = insight.get("what_best_move_achieves", "")
                    why_wrong = insight.get("why_your_move_was_wrong", "")
                    
                    parts = []
                    if what_missed:
                        parts.append(f"You missed: {what_missed}")
                    if what_best:
                        parts.append(f"{best_move} would have: {what_best}")
                    if why_wrong:
                        parts.append(f"Problem with {move}: {why_wrong}")
                    position_insight = " ".join(parts)
        except Exception as e:
            pass  # Fall back to generic
        
        # Build prompt with REAL tactical analysis
        if position_insight:
            # We have real analysis - use it!
            if severity == "blunder":
                return f"That's a tough spot. {position_insight}"
            elif severity == "mistake":
                return f"Close, but not quite. {position_insight}"
            else:
                return f"{best_move} was slightly better. {position_insight}"
        
        # Fallback to FACTUAL message only (no LLM guessing)
        if severity == "blunder":
            return f"You played {move}. {best_move} was much stronger here (about {int(abs(eval_loss)*100)} centipawns better)."
        elif severity == "mistake":
            return f"{best_move} was better than {move}. Take your time to find the best move."
        else:
            return f"{best_move} was slightly more accurate than {move}."
    
    return ""


async def generate_response_to_user(
    user_message: str,
    current_fen: str,
    move_history: list,
    user_color: str,
    user_rating: int,
    personal_context: Dict = None,
    position_plan: Dict = None
) -> Dict[str, Any]:
    """
    Generate PERSONALIZED coach response to user's message.
    
    Unlike generic coaches, this one:
    - References the user's past games and mistakes
    - Gives plan-based advice, not just engine evaluations
    - Speaks like a coach who KNOWS you
    
    Returns dict with:
    - response: The personalized text response
    - suggestion_arrow: UCI coords for arrow if suggesting a move
    - move_quality: Quality of analyzed move if applicable
    """
    import sys
    sys.path.insert(0, '/app/backend')
    from llm_service import call_llm
    
    coach = CoachCommentary()
    msg_lower = user_message.lower()
    
    # Result structure
    result = {
        "response": "",
        "suggestion_arrow": None,
        "move_quality": None,
        "best_move": None,
        "missed_tactic": None
    }
    
    # Pre-check: Is this a question about the last move?
    # If so, we need full analysis, not fast path
    asking_about_last_move_fast_check = any(phrase in msg_lower for phrase in [
        "last move", "my move", "was that", "was it", "that move",
        "what i played", "i played", "good move", "bad move", "mistake", "blunder",
        "why did i", "was h", "was my h", "was my move"
    ])
    
    # === FAST PATH: Use pattern matching first (no LLM needed) ===
    # BUT: Skip fast path if asking about a specific move OR asking for plans
    # (plans need actual position analysis)
    asking_for_suggestions = any(phrase in msg_lower for phrase in [
        "what can i", "what should i", "what do i", "suggest", "help",
        "plan", "strategy", "what now", "how do i", "what's the idea",
        "what to do", "out of plans", "any ideas", "stuck", "don't know"
    ])
    
    if not asking_about_last_move_fast_check and not asking_for_suggestions:
        try:
            from coach_engine.question_system import ResponseUnderstanding, generate_response_to_answer
            from coach_engine.opening_plans import get_opening_by_moves
            
            intent, confidence = ResponseUnderstanding.understand(user_message)
            
            # Get opening context
            all_moves = [m.get("move", "") for m in move_history]
            opening = get_opening_by_moves(all_moves)
            
            # For simple intents (NOT plan requests), use pattern-matched response
            if intent in ["confused", "affirmative", "negative"] and confidence >= 0.7:
                response = generate_response_to_answer(
                    user_message=user_message,
                    question=None,  # No pending question in this context
                    opening=opening,
                    board=None
                )
                result["response"] = response
                return result
        except Exception as e:
            # Fall through to LLM-based response
            pass
    
    # Detect question types (already computed above for fast path check)
    asking_about_last_move = asking_about_last_move_fast_check
    
    asking_about_plan = any(phrase in msg_lower for phrase in [
        "what should i", "what do i", "plan", "strategy", "what now",
        "how do i", "what's the idea", "what to do", "suggest", "help",
        "what can i", "out of plans", "stuck", "don't know", "any ideas",
        "give me", "show me", "best move", "recommend"
    ])
    
    # NEW: Detect if asking about COACH's move (not user's move)
    asking_about_coach_move = any(phrase in msg_lower for phrase in [
        "why did you play", "why you play", "your move", "you played",
        "idea behind", "what's the idea behind"
    ])
    
    # Extract specific move being asked about (e.g., "why did you play Qd7?")
    asked_about_move = None
    import re
    move_match = re.search(r'(?:play(?:ed)?|behind)\s+([A-Za-z][a-z]?\d?[x]?[a-z]\d[=]?[QRBN]?[+#]?)', msg_lower)
    if move_match:
        asked_about_move = move_match.group(1)
    
    # Find user's last move
    user_moves = [m for m in move_history if m.get("by") == "player"]
    last_user_move = user_moves[-1] if user_moves else None
    
    # Find coach's last move
    coach_moves = [m for m in move_history if m.get("by") == "coach"]
    last_coach_move = coach_moves[-1] if coach_moves else None
    
    # Build personal context section for prompt
    personal_section = ""
    if personal_context:
        if personal_context.get("similar_mistake"):
            sm = personal_context["similar_mistake"]
            personal_section += f"""
PERSONAL HISTORY (IMPORTANT - Reference this!):
The user made a similar mistake in a game against {sm.get('opponent', 'someone')} {sm.get('when', 'recently')}.
What happened then: {sm.get('what_happened', 'a similar error')}
Lesson from that game: {sm.get('lesson', 'Watch for this pattern')}
>>> REFERENCE THIS IN YOUR RESPONSE! Say something like "Remember your game against {sm.get('opponent', 'X')}..."
"""
        
        if personal_context.get("relevant_tendency"):
            rt = personal_context["relevant_tendency"]
            personal_section += f"""
USER'S TENDENCY (mention this gently):
{rt.get('message', '')}
(This has happened {rt.get('frequency', 'multiple')} times in their games)
"""
        
        if personal_context.get("personal_warning"):
            personal_section += f"""
WARNING FOR THIS USER: {personal_context['personal_warning']}
"""
    
    # Build plan section for prompt
    plan_section = ""
    if position_plan and asking_about_plan:
        plan_section = f"""
STRATEGIC PLAN FOR THIS POSITION:
Main idea: {position_plan.get('main_idea', '')}
Specific goals: {', '.join(position_plan.get('specific_goals', []))}
Things to avoid: {', '.join(position_plan.get('things_to_avoid', []))}
Piece placement tips: {position_plan.get('piece_placement', {})}
>>> USE THIS PLAN in your response - explain it in simple terms!
"""
    
    # Move analysis section
    move_analysis_context = ""
    tactic_explanation = ""
    
    if asking_about_last_move and last_user_move:
        fen_before = last_user_move.get("fen_before", "")
        fen_after = last_user_move.get("fen_after", "")
        move_san = last_user_move.get("move", "")
        
        if fen_before and fen_after and move_san:
            move_analysis = await coach.analyze_move(fen_before, move_san, fen_after)
            
            result["move_quality"] = move_analysis.quality.value
            result["best_move"] = move_analysis.best_move_san
            result["missed_tactic"] = move_analysis.missed_tactic
            
            if not move_analysis.is_best_move and move_analysis.best_move_uci:
                result["suggestion_arrow"] = move_analysis.best_move_uci
            
            quality = move_analysis.quality.value
            eval_before = move_analysis.eval_before
            eval_after = move_analysis.eval_after
            best_move = move_analysis.best_move_san
            was_best = move_analysis.is_best_move
            
            if move_analysis.threat_explanation:
                tactic_explanation = f"\nTACTIC DETAIL: {move_analysis.threat_explanation}"
            
            # Get REAL position-specific insight for better explanations
            position_specific_insight = ""
            try:
                from services.position_strategy_analyzer import generate_move_specific_insight
                
                cp_loss = int(abs(eval_before - eval_after) * 100) if eval_before is not None and eval_after is not None else 0
                insight = generate_move_specific_insight(
                    fen_before=fen_before,
                    user_move=move_san,
                    best_move=best_move,
                    pv_after_best=move_analysis.best_continuation if move_analysis.best_continuation else [],
                    cp_loss=cp_loss,
                    user_color=user_color,
                    threat=move_analysis.threat_explanation
                )
                if insight and not insight.get("error"):
                    parts = []
                    if insight.get("what_you_missed"):
                        parts.append(f"WHAT WAS MISSED: {insight['what_you_missed']}")
                    if insight.get("what_best_move_achieves"):
                        parts.append(f"WHY {best_move} WAS BETTER: {insight['what_best_move_achieves']}")
                    if insight.get("why_your_move_was_wrong"):
                        parts.append(f"PROBLEM WITH {move_san}: {insight['why_your_move_was_wrong']}")
                    if insight.get("the_idea_you_should_learn"):
                        parts.append(f"LESSON: {insight['the_idea_you_should_learn']}")
                    position_specific_insight = "\n".join(parts)
                    logger.info(f"Generated position-specific insight: {position_specific_insight[:200]}")
            except Exception as e:
                logger.warning(f"Failed to generate position-specific insight: {e}")
            
            if was_best:
                move_analysis_context = f"""
MOVE ANALYSIS:
- Move played: {move_san} - EXCELLENT! This was the best move.
- Evaluation: {eval_before:+.2f} → {eval_after:+.2f}"""
            else:
                move_analysis_context = f"""
MOVE ANALYSIS:
- Move played: {move_san}
- Quality: {quality.upper()}
- Evaluation: {eval_before:+.2f} → {eval_after:+.2f}
- Better was: {best_move}{tactic_explanation}
{position_specific_insight}

>>> USE THE POSITION-SPECIFIC INSIGHT ABOVE! Tell the user exactly what they missed, not generic advice."""
    
    # Get position info
    position = await coach.analyze_position(current_fen)
    
    # If user is asking for suggestions, get Stockfish best move
    best_move_suggestion = ""
    if asking_about_plan:
        try:
            import chess
            from stockfish_service import StockfishEngine
            
            board = chess.Board(current_fen)
            engine = StockfishEngine()
            engine.start()
            try:
                best_move_obj, eval_score, _ = engine.get_best_move(board, depth=14)
                best_move_san = board.san(best_move_obj)
                result["best_move"] = best_move_san
                result["suggestion_arrow"] = best_move_obj.uci()
                
                # Add to prompt context
                best_move_suggestion = f"""
STOCKFISH RECOMMENDATION:
Best move: {best_move_san}
>>> Suggest this move and explain WHY it's good in simple terms!
Consider: What does {best_move_san} achieve? Does it attack something? Improve position? Create threats?
"""
            finally:
                engine.stop()
        except Exception as e:
            logger.warning(f"Failed to get best move: {e}")
    
    # NEW: If asking about COACH's move, provide context about it
    coach_move_context = ""
    if asking_about_coach_move:
        # Find the specific move they're asking about, or use last coach move
        target_move = asked_about_move or (last_coach_move.get("move") if last_coach_move else None)
        
        if target_move and last_coach_move:
            fen_before_coach = last_coach_move.get("fen_before", "")
            fen_after_coach = last_coach_move.get("fen_after", "")
            
            coach_move_context = f"""
THE USER IS ASKING ABOUT MY (COACH'S) MOVE: {target_move}
>>> IMPORTANT: The user wants to understand YOUR move, not their move!
>>> Explain WHY you played {target_move}. What was the idea? What does it achieve?

Consider:
- What squares/pieces does this move attack or defend?
- What is the strategic idea behind this move?
- How does it improve my (coach's) position?
- What should the student learn from this move?

DO NOT talk about the student's move or what they should do next.
FOCUS on explaining your reasoning for playing {target_move}.
"""
    
    # Build the full prompt - INCLUDE FEN to prevent hallucinations
    prompt = f"""You are a PERSONALIZED chess coach who KNOWS this player. 
You've analyzed their past games and know their tendencies.

The student ({user_color}, rated {user_rating}) asks:
"{user_message}"

CURRENT POSITION (FEN: {current_fen}):
- Evaluation: {position.evaluation:+.2f}
- Phase: {position.phase}
- Opening: {position.opening_name or 'N/A'}
{coach_move_context}
{best_move_suggestion}
{move_analysis_context}
{personal_section}
{plan_section}

COACHING STYLE - BE SPECIFIC, NOT GENERIC!
1. If there's POSITION-SPECIFIC INSIGHT above, USE IT! Tell the user exactly what they missed.
2. If there's PERSONAL HISTORY, reference it briefly
3. If asking about a plan, use the STRATEGIC PLAN section
4. NO GENERIC ADVICE like "think about piece activity" or "be vigilant for tactics"
5. Keep it to 2-3 sentences, be SPECIFIC about this position!

CRITICAL RULES:
- If the move analysis shows WHAT WAS MISSED, tell them that specific thing
- If it shows WHY their move was bad, explain that specific problem
- NEVER say vague things like "missed tactical potential" - say what the tactic WAS
- Reference their past games only if the specific insight is weak
- ONLY mention pieces on squares if you have VERIFIED they are actually there in the FEN
- DO NOT make up or guess about piece positions - if you're unsure, just say "there was a better move"

EXAMPLES OF GOOD RESPONSES:
- "Bc4 missed the tactic Ne2 which forks your queen and rook. Always check for knight forks before moving your bishop!"
- "Your knight on e4 was actually safe - you should have played Nf3 to threaten their queen."
- "That pawn push weakened your king. Better was to castle first and keep your king safe."

AVOID:
- Generic advice like "think about piece activity" or "be vigilant for tactics"
- Just quoting engine evaluations without explaining WHY
- Saying "tactical potential" without explaining what the tactic IS
- Phrases like "You've got this!" or "Keep an eye out!" - be SPECIFIC
- NEVER mention a piece being on a specific square unless it's VERIFIED in the position analysis above"""
    
    try:
        response = await call_llm(
            system_message="You are a personalized chess coach who knows this player's history. Reference their past games and give plan-based advice.",
            user_message=prompt,
            model="gpt-4o-mini"
        )
        result["response"] = response.strip()
    except Exception:
        if personal_context and personal_context.get("similar_mistake"):
            sm = personal_context["similar_mistake"]
            result["response"] = f"This reminds me of your game against {sm.get('opponent', 'a previous opponent')}. Let's not repeat that mistake!"
        elif position_plan:
            result["response"] = f"Your plan here: {position_plan.get('main_idea', 'develop your pieces and control the center')}."
        else:
            result["response"] = "Let me analyze that for you..."
    
    return result
