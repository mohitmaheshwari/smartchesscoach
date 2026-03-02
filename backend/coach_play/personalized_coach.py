"""
Personalized Coach - The Secret Sauce

This is what makes us different from chess.com.
The coach KNOWS the user:
- Their past mistakes and patterns
- Similar positions from their games
- Their tendencies (rushing, forgetting king safety, etc.)
- What they struggle with

Instead of "Stockfish says +0.3", we say:
"Remember your game against PlayerX? You made the same mistake.
Your plan here should be: develop pieces, control center, castle."

This module:
1. Fetches user's historical patterns from analyzed games
2. Finds similar positions/mistakes from their history
3. Generates plan-based, human coaching (not engine moves)
4. Connects current moments to personal history
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import chess
import re


@dataclass
class PersonalPattern:
    """A pattern from user's game history"""
    pattern_type: str  # "tactical_miss", "positional_error", "time_trouble", etc.
    description: str
    frequency: int  # How often this happens
    example_game: Optional[str]  # Game ID where this happened
    opponent: Optional[str]  # Who they played against
    when: Optional[datetime]


@dataclass
class PositionPlan:
    """A human-understandable plan for a position"""
    phase: str  # opening, middlegame, endgame
    main_idea: str  # "Control the center and develop"
    specific_goals: List[str]  # ["Castle kingside", "Put rook on open file"]
    things_to_avoid: List[str]  # ["Don't move the same piece twice", "Watch the f7 pawn"]
    piece_placement: Dict[str, str]  # {"knight": "aim for d5 or f5", "bishop": "keep the long diagonal"}


class PersonalizedCoach:
    """
    A coach that knows YOU.
    
    Unlike generic chess engines, this coach:
    - Remembers your past games and mistakes
    - Recognizes when you're about to repeat a pattern
    - Gives plan-based advice, not engine moves
    - Speaks like a human coach who's been watching your games
    """
    
    def __init__(self, db, user_id: str):
        self.db = db
        self.user_id = user_id
        self._user_patterns = None
        self._recent_games = None
    
    async def load_user_history(self):
        """Load user's patterns and recent games"""
        # Get user's behavioral patterns
        patterns_doc = await self.db.behavioral_patterns.find_one({"user_id": self.user_id})
        self._user_patterns = patterns_doc or {}
        
        # Get recent analyzed games (last 20)
        cursor = self.db.game_analyses.find(
            {"user_id": self.user_id}
        ).sort("analyzed_at", -1).limit(20)
        
        self._recent_games = []
        async for game in cursor:
            self._recent_games.append(game)
    
    async def get_personal_context(self, current_fen: str, last_move: str, phase: str) -> Dict[str, Any]:
        """
        Get personalized context for coaching.
        
        Returns info about:
        - Similar positions/mistakes from user's history
        - User's tendencies relevant to this position
        - Personalized warnings based on their patterns
        """
        if self._user_patterns is None:
            await self.load_user_history()
        
        context = {
            "similar_mistake": None,
            "relevant_tendency": None,
            "personal_warning": None,
            "past_game_reference": None
        }
        
        # Check for similar mistakes in history
        similar = await self._find_similar_pattern(current_fen, last_move, phase)
        if similar:
            context["similar_mistake"] = similar
        
        # Get relevant tendency for this phase
        tendency = self._get_phase_tendency(phase)
        if tendency:
            context["relevant_tendency"] = tendency
        
        # Generate personal warning if applicable
        warning = self._generate_personal_warning(current_fen, phase)
        if warning:
            context["personal_warning"] = warning
        
        return context
    
    async def _find_similar_pattern(
        self, 
        current_fen: str, 
        last_move: str,
        phase: str
    ) -> Optional[Dict]:
        """
        Find if user made a similar mistake before.
        
        Looks at:
        - Similar piece movements
        - Similar position types
        - Same opening/structure mistakes
        """
        if not self._recent_games:
            return None
        
        board = chess.Board(current_fen)
        
        # Get the piece that was just moved
        try:
            # Parse move to get piece type
            if last_move[0].isupper():
                piece_moved = last_move[0]  # N, B, R, Q, K
            else:
                piece_moved = "P"  # Pawn
        except:
            piece_moved = "?"
        
        # Search through recent games for similar situations
        for game in self._recent_games:
            learning_moments = game.get("learning_moments", [])
            
            for moment in learning_moments:
                # Check if similar piece/phase mistake
                moment_move = moment.get("move", "")
                moment_phase = moment.get("phase", "")
                
                # Same piece type in same phase
                if moment_phase == phase:
                    moment_piece = moment_move[0] if moment_move and moment_move[0].isupper() else "P"
                    
                    if moment_piece == piece_moved:
                        # Found a similar pattern!
                        opponent = game.get("opponent", "unknown")
                        game_date = game.get("analyzed_at", datetime.now())
                        
                        # Format the date nicely
                        if isinstance(game_date, str):
                            try:
                                game_date = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
                            except:
                                game_date = datetime.now()
                        
                        days_ago = (datetime.now(timezone.utc) - game_date.replace(tzinfo=timezone.utc)).days
                        
                        if days_ago == 0:
                            time_str = "earlier today"
                        elif days_ago == 1:
                            time_str = "yesterday"
                        elif days_ago < 7:
                            time_str = f"{days_ago} days ago"
                        else:
                            time_str = f"on {game_date.strftime('%b %d')}"
                        
                        return {
                            "found": True,
                            "opponent": opponent,
                            "when": time_str,
                            "similar_move": moment_move,
                            "what_happened": moment.get("explanation", "a similar mistake"),
                            "lesson": moment.get("lesson", "Watch out for this pattern")
                        }
        
        return None
    
    def _get_phase_tendency(self, phase: str) -> Optional[Dict]:
        """Get user's typical issues in this game phase"""
        if not self._user_patterns:
            return None
        
        tendencies = self._user_patterns.get("tendencies", {})
        phase_issues = self._user_patterns.get("phase_issues", {})
        
        # Common patterns we track
        if phase == "opening":
            if tendencies.get("early_queen_moves", 0) > 2:
                return {
                    "type": "early_queen",
                    "message": "You sometimes bring out your queen too early. Focus on developing knights and bishops first.",
                    "frequency": tendencies.get("early_queen_moves", 0)
                }
            if tendencies.get("pawn_pushes_before_development", 0) > 3:
                return {
                    "type": "pawn_pushing",
                    "message": "You tend to push pawns before developing pieces. Remember: knights and bishops first!",
                    "frequency": tendencies.get("pawn_pushes_before_development", 0)
                }
        
        elif phase == "middlegame":
            if tendencies.get("forgotten_castling", 0) > 2:
                return {
                    "type": "king_safety",
                    "message": "You sometimes forget to castle. King safety is crucial!",
                    "frequency": tendencies.get("forgotten_castling", 0)
                }
            if tendencies.get("piece_hanging", 0) > 3:
                return {
                    "type": "hanging_pieces",
                    "message": "Watch your pieces - you've left pieces hanging in several games.",
                    "frequency": tendencies.get("piece_hanging", 0)
                }
        
        elif phase == "endgame":
            if tendencies.get("passive_king", 0) > 2:
                return {
                    "type": "passive_king",
                    "message": "In endgames, activate your king! It's a fighting piece now.",
                    "frequency": tendencies.get("passive_king", 0)
                }
        
        return None
    
    def _generate_personal_warning(self, fen: str, phase: str) -> Optional[str]:
        """Generate a personalized warning based on position and history"""
        if not self._user_patterns:
            return None
        
        board = chess.Board(fen)
        warnings = []
        
        # Check castling status
        if phase in ["opening", "middlegame"]:
            white_turn = board.turn == chess.WHITE
            if white_turn:
                if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
                    if self._user_patterns.get("tendencies", {}).get("forgotten_castling", 0) > 1:
                        warnings.append("Don't forget to castle - you've missed this before!")
        
        # Check for loose pieces
        # (simplified - real implementation would be more thorough)
        
        return warnings[0] if warnings else None
    
    def get_position_plan(self, fen: str, phase: str, user_color: str) -> PositionPlan:
        """
        Generate a human-understandable plan for the position.
        
        NOT engine analysis - actual strategic guidance!
        """
        board = chess.Board(fen)
        is_white = user_color == "white"
        
        if phase == "opening":
            return self._get_opening_plan(board, is_white)
        elif phase == "middlegame":
            return self._get_middlegame_plan(board, is_white)
        else:
            return self._get_endgame_plan(board, is_white)
    
    def _get_opening_plan(self, board: chess.Board, is_white: bool) -> PositionPlan:
        """Opening plans - focus on development"""
        goals = []
        avoid = []
        pieces = {}
        
        color = chess.WHITE if is_white else chess.BLACK
        
        # Check what's developed
        knights_developed = 0
        bishops_developed = 0
        castled = False
        
        # Count developed pieces
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == color:
                rank = chess.square_rank(square)
                home_rank = 0 if is_white else 7
                
                if piece.piece_type == chess.KNIGHT and rank != home_rank:
                    knights_developed += 1
                if piece.piece_type == chess.BISHOP and rank != home_rank:
                    bishops_developed += 1
        
        # Check castling
        king_square = board.king(color)
        if king_square:
            king_file = chess.square_file(king_square)
            if king_file in [6, 2]:  # g or c file = likely castled
                castled = True
        
        # Generate goals
        if knights_developed < 2:
            goals.append("Develop your knights to active squares (f3/c3 for white, f6/c6 for black)")
            pieces["knights"] = "Aim for f3 and c3 - they control the center"
        
        if bishops_developed < 2:
            goals.append("Develop your bishops - look for long diagonals")
            pieces["bishops"] = "Consider fianchetto (g3+Bg2) or Italian style (Bc4)"
        
        if not castled:
            if board.has_kingside_castling_rights(color) or board.has_queenside_castling_rights(color):
                goals.append("Castle to safety - don't leave your king in the center!")
        
        # Things to avoid in opening
        avoid.append("Don't move the same piece twice unless necessary")
        avoid.append("Don't bring your queen out too early")
        avoid.append("Don't push too many pawns - develop pieces first")
        
        return PositionPlan(
            phase="opening",
            main_idea="Develop all your pieces and castle to safety",
            specific_goals=goals[:3],
            things_to_avoid=avoid[:2],
            piece_placement=pieces
        )
    
    def _get_middlegame_plan(self, board: chess.Board, is_white: bool) -> PositionPlan:
        """Middlegame plans - attack and defense"""
        goals = []
        avoid = []
        pieces = {}
        
        color = chess.WHITE if is_white else chess.BLACK
        
        # Check pawn structure for plan ideas
        center_control = 0
        for sq in [chess.E4, chess.D4, chess.E5, chess.D5]:
            if board.is_attacked_by(color, sq):
                center_control += 1
        
        # Check for open files
        open_files = []
        for file_idx in range(8):
            has_pawns = False
            for rank_idx in range(8):
                piece = board.piece_at(chess.square(file_idx, rank_idx))
                if piece and piece.piece_type == chess.PAWN:
                    has_pawns = True
                    break
            if not has_pawns:
                open_files.append(chess.FILE_NAMES[file_idx])
        
        # Generate goals
        if center_control < 3:
            goals.append("Fight for the center - it's the key to the middlegame")
        
        if open_files:
            goals.append(f"Put your rooks on the open {open_files[0]}-file")
            pieces["rooks"] = f"The {open_files[0]}-file is open - control it!"
        
        goals.append("Look for tactical opportunities - checks, captures, threats")
        goals.append("Coordinate your pieces - they should work together")
        
        # Things to avoid
        avoid.append("Don't leave pieces undefended")
        avoid.append("Don't open the position if your king is exposed")
        avoid.append("Don't trade pieces without a reason")
        
        pieces["queen"] = "Keep it active but safe - don't trade it for less"
        
        return PositionPlan(
            phase="middlegame",
            main_idea="Create threats while keeping your pieces safe",
            specific_goals=goals[:3],
            things_to_avoid=avoid[:2],
            piece_placement=pieces
        )
    
    def _get_endgame_plan(self, board: chess.Board, is_white: bool) -> PositionPlan:
        """Endgame plans - king activity and pawn promotion"""
        goals = []
        avoid = []
        pieces = {}
        
        color = chess.WHITE if is_white else chess.BLACK
        
        # Check passed pawns
        # (simplified - real implementation would check for actual passed pawns)
        
        goals.append("Activate your king - in endgames, the king is a fighting piece!")
        goals.append("Push your passed pawns or create one")
        goals.append("Trade pieces if you're ahead in material")
        
        avoid.append("Don't let your king stay passive")
        avoid.append("Don't allow opponent's pawns to advance")
        
        pieces["king"] = "Bring it to the center - it should be active"
        pieces["pawns"] = "Advance them with king support"
        
        return PositionPlan(
            phase="endgame",
            main_idea="Activate your king and push passed pawns",
            specific_goals=goals[:3],
            things_to_avoid=avoid[:2],
            piece_placement=pieces
        )


async def get_personalized_coaching(
    db,
    user_id: str,
    current_fen: str,
    last_move: str,
    phase: str,
    user_color: str
) -> Dict[str, Any]:
    """
    Main entry point for personalized coaching.
    
    Returns:
    - personal_context: Similar past mistakes, tendencies, warnings
    - position_plan: Human-understandable strategic plan
    """
    coach = PersonalizedCoach(db, user_id)
    
    # Get personal context (past mistakes, tendencies)
    personal_context = await coach.get_personal_context(current_fen, last_move, phase)
    
    # Get position plan (human strategic guidance)
    position_plan = coach.get_position_plan(current_fen, phase, user_color)
    
    return {
        "personal_context": personal_context,
        "position_plan": {
            "main_idea": position_plan.main_idea,
            "specific_goals": position_plan.specific_goals,
            "things_to_avoid": position_plan.things_to_avoid,
            "piece_placement": position_plan.piece_placement
        }
    }
