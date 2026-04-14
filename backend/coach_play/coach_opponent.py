"""
Coach Opponent - Engine that plays against the user

Step 1: Simple strongest-move engine using Stockfish.

Later phases will add:
- Pedagogical opponent (creates instructive scenarios)
- Difficulty matching
- Intentional mistake creation for teaching moments

Key principle: Don't overengineer in early iteration.
Interception matters more than fancy opponent weighting.

Skill Level to Rating approximation:
- Skill 0: ~800 Elo
- Skill 5: ~1200 Elo
- Skill 10: ~1600 Elo
- Skill 15: ~2000 Elo
- Skill 20: ~3200+ Elo (full strength)
"""

import chess
import chess.engine
import asyncio
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

STOCKFISH_PATH = "/usr/games/stockfish"

# Thread pool for Stockfish calls (blocking)
_executor = ThreadPoolExecutor(max_workers=2)

# Map user rating to Stockfish skill level (0-20)
def rating_to_skill_level(user_rating: int) -> int:
    """Convert user rating to Stockfish skill level"""
    if user_rating < 800:
        return 0
    elif user_rating < 1000:
        return 3
    elif user_rating < 1200:
        return 5
    elif user_rating < 1400:
        return 8
    elif user_rating < 1600:
        return 10
    elif user_rating < 1800:
        return 12
    elif user_rating < 2000:
        return 15
    elif user_rating < 2200:
        return 17
    else:
        return 20  # Full strength


class CoachOpponent:
    """
    Coach opponent engine.
    
    Plays at a skill level matched to the user's rating.
    Also provides position evaluation for the eval bar.
    """
    
    def __init__(self, user_rating: int = 1200, depth: int = 10, time_limit: float = 0.5):
        """
        Initialize coach opponent.
        
        Args:
            user_rating: User's rating to match difficulty
            depth: Search depth for Stockfish
            time_limit: Time limit per move in seconds
        """
        self.user_rating = user_rating
        self.skill_level = rating_to_skill_level(user_rating)
        self.depth = depth
        self.time_limit = time_limit
    
    async def get_move(self, fen: str) -> Optional[str]:
        """
        Get the coach's move for a given position.
        
        Args:
            fen: Current position in FEN notation
        
        Returns:
            Move in SAN notation, or None if no legal moves
        """
        loop = asyncio.get_event_loop()
        try:
            move = await loop.run_in_executor(
                _executor,
                self._get_move_sync,
                fen
            )
            return move
        except Exception as e:
            print(f"CoachOpponent error: {e}")
            return self._get_fallback_move(fen)
    
    async def get_evaluation(self, fen: str) -> Tuple[float, Optional[int]]:
        """
        Get position evaluation.
        
        Args:
            fen: Position in FEN notation
        
        Returns:
            Tuple of (eval_score, mate_in) where:
            - eval_score: Centipawn score from white's perspective (e.g., 1.5 = +1.5 pawns for white)
            - mate_in: Number of moves to mate (positive = white mates, negative = black mates), or None
        """
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                _executor,
                self._get_eval_sync,
                fen
            )
            return result
        except Exception as e:
            print(f"Evaluation error: {e}")
            return (0.0, None)
    
    def _get_move_sync(self, fen: str) -> Optional[str]:
        """Synchronous Stockfish call with skill level"""
        board = chess.Board(fen)
        
        if board.is_game_over():
            return None
        
        try:
            with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
                # Set skill level to match user's rating
                engine.configure({"Skill Level": self.skill_level})
                
                # Use time limit for speed
                result = engine.play(
                    board,
                    chess.engine.Limit(time=self.time_limit, depth=self.depth)
                )
                
                if result.move:
                    return board.san(result.move)
                return None
                
        except Exception as e:
            print(f"Stockfish error: {e}")
            return self._get_fallback_move(fen)
    
    def _get_eval_sync(self, fen: str) -> Tuple[float, Optional[int]]:
        """Get position evaluation synchronously"""
        board = chess.Board(fen)
        
        try:
            with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
                info = engine.analyse(board, chess.engine.Limit(depth=12, time=0.3))
                score = info.get("score")
                
                if score:
                    pov_score = score.white()  # Always from white's perspective
                    
                    if pov_score.is_mate():
                        mate_in = pov_score.mate()
                        # Cap eval at ±10 for display purposes when mate
                        eval_score = 10.0 if mate_in > 0 else -10.0
                        return (eval_score, mate_in)
                    else:
                        # Convert centipawns to pawns
                        cp = pov_score.score()
                        eval_score = cp / 100.0 if cp else 0.0
                        # Cap at ±10 for display
                        eval_score = max(-10.0, min(10.0, eval_score))
                        return (eval_score, None)
                
                return (0.0, None)
                
        except Exception as e:
            print(f"Eval error: {e}")
            return (0.0, None)
    
    def _get_fallback_move(self, fen: str) -> Optional[str]:
        """Fallback: return first legal move"""
        try:
            board = chess.Board(fen)
            legal_moves = list(board.legal_moves)
            if legal_moves:
                return board.san(legal_moves[0])
        except Exception:
            pass
        return None


class PedagogicalOpponent(CoachOpponent):
    """
    Pedagogical opponent that creates instructive scenarios.
    
    Uses the Teaching Move Selector to choose moves that:
    - Create learning opportunities
    - Match the student's level and weaknesses
    - Teach specific concepts based on game phase
    - Guide games toward known openings for teaching
    - Adapt opening complexity to user rating
    
    The coach plays TO TEACH, not to crush.
    """
    
    # Opening complexity ratings (1-5, where 1=beginner, 5=advanced)
    OPENING_COMPLEXITY = {
        "italian_game": 2,      # Simple, good for beginners
        "london_system": 1,     # Very simple, solid
        "caro_kann": 2,         # Solid, straightforward
        "french_defense": 3,    # Moderate complexity, pawn chains
        "scandinavian_defense": 2,  # Simple but queen out early
        "philidor_defense": 2,  # Solid, passive
        "sicilian_defense": 4,  # Complex, many variations
        "ruy_lopez": 4,         # Deep theory, complex
        "queens_gambit": 3,     # Moderate, positional
    }
    
    # Rating thresholds for opening complexity
    # Below 1000: complexity 1-2 only
    # 1000-1400: complexity 1-3
    # 1400-1800: complexity 1-4
    # Above 1800: all openings
    
    # === COACH PLAYS WHITE (user is Black) ===
    # These are the coach's first moves to guide into openings
    WHITE_OPENING_MOVES = {
        # Beginner-friendly (rating < 1200)
        "beginner": [
            ("e4", ["italian_game", "philidor_defense"]),  # e4 leads to Italian/Philidor
            ("d4", ["london_system", "queens_gambit"]),     # d4 leads to London/QG
        ],
        # Intermediate (1200-1600)
        "intermediate": [
            ("e4", ["italian_game", "french_defense", "caro_kann", "scandinavian_defense"]),
            ("d4", ["queens_gambit", "london_system"]),
            ("Nf3", ["ruy_lopez"]),  # Reti-style into Ruy Lopez
        ],
        # Advanced (1600+)
        "advanced": [
            ("e4", ["sicilian_defense", "french_defense", "caro_kann", "ruy_lopez"]),
            ("d4", ["queens_gambit"]),
        ],
    }
    
    # === COACH PLAYS BLACK (user is White) ===
    # Response moves based on what user plays
    BLACK_RESPONSES = {
        # When user plays e4
        "e4": {
            "beginner": ["e5", "e6"],           # Italian/Philidor path, French
            "intermediate": ["e5", "c6", "e6", "d5"],  # + Caro-Kann, Scandinavian
            "advanced": ["c5", "e6", "c6", "e5"],      # Sicilian priority for advanced
        },
        # When user plays d4
        "d4": {
            "beginner": ["d5"],                 # Simple Queen's Gambit
            "intermediate": ["d5", "Nf6"],      # + Indian setups
            "advanced": ["d5", "Nf6"],
        },
        # When user plays Nf3
        "Nf3": {
            "beginner": ["d5"],
            "intermediate": ["d5", "Nf6"],
            "advanced": ["d5", "c5", "Nf6"],
        },
        # When user plays c4
        "c4": {
            "beginner": ["e5"],
            "intermediate": ["e5", "Nf6"],
            "advanced": ["e5", "c5", "Nf6"],
        },
    }
    
    # Continuation moves to complete opening detection
    OPENING_CONTINUATIONS = {
        # Italian Game / Ruy Lopez path (user White, coach Black)
        ("e4", "e5", "Nf3"): "Nc6",      # Leads to Italian (Bc4) or Ruy Lopez (Bb5)
        ("e4", "e5", "Nf3", "Nc6", "Bc4"): "Bc5",  # Italian Game main line
        ("e4", "e5", "Nf3", "Nc6", "Bb5"): "a6",   # Ruy Lopez Morphy Defense
        
        # Sicilian paths
        ("e4", "c5", "Nf3"): "d6",       # Sicilian Najdorf/Dragon setup
        ("e4", "c5", "d4"): "cxd4",      # Open Sicilian
        ("e4", "c5", "Nc3"): "Nc6",      # Closed Sicilian
        
        # French Defense
        ("e4", "e6", "d4"): "d5",        # French main line
        
        # Caro-Kann
        ("e4", "c6", "d4"): "d5",        # Caro-Kann main line
        
        # Scandinavian
        ("e4", "d5", "exd5"): "Qxd5",    # Scandinavian main line
        
        # Queen's Gambit
        ("d4", "d5", "c4"): "e6",        # QGD
        
        # Philidor
        ("e4", "e5", "Nf3", "d6"): "d4", # Philidor main line (coach as White)
        
        # London System (coach as White)
        ("d4", "d5", "Bf4"): "Nf6",      # London main line
        ("d4", "Nf6", "Bf4"): "e6",      # London vs Indian
    }
    
    def __init__(
        self,
        user_rating: int = 1200,
        teaching_mode: str = "balanced",
        student_weaknesses: list = None,
        teaching_focus: str = None,
        move_history: list = None,
        user_color: str = "white",  # What color is the USER playing
        last_game_violations: list = None,  # Learning loop: previous session's violations
    ):
        """
        Initialize pedagogical opponent.

        Args:
            user_rating: User's estimated rating for difficulty matching
            teaching_mode: "challenging", "balanced", or "supportive"
            student_weaknesses: List of weakness areas to target
            teaching_focus: Specific concept to teach (optional)
            move_history: List of moves played so far (for opening guidance)
            user_color: What color the user is playing ("white" or "black")
            last_game_violations: Fundamental violations from previous game (learning loop)
        """
        super().__init__(user_rating=user_rating)
        self.teaching_mode = teaching_mode
        self.student_weaknesses = student_weaknesses or []
        self.teaching_focus = teaching_focus
        self.last_teaching_context = {}
        self.move_history = move_history or []
        self.user_color = user_color.lower() if user_color else "white"
        self.last_game_violations = last_game_violations or []
        self.skill_tier = self._get_skill_tier(user_rating)
    
    def _get_skill_tier(self, rating: int) -> str:
        """Get skill tier based on rating for opening selection."""
        if rating < 1200:
            return "beginner"
        elif rating < 1600:
            return "intermediate"
        else:
            return "advanced"
    
    def _get_max_complexity(self) -> int:
        """Get maximum opening complexity for this user's rating."""
        if self.skill_tier == "beginner":
            return 2
        elif self.skill_tier == "intermediate":
            return 3
        else:
            return 5
    
    def _filter_openings_by_complexity(self, openings: list) -> list:
        """Filter openings to only include those appropriate for user's level."""
        max_complexity = self._get_max_complexity()
        return [op for op in openings if self.OPENING_COMPLEXITY.get(op, 3) <= max_complexity]
    
    def _get_opening_guided_move(self, fen: str) -> Optional[str]:
        """
        Get a move that guides toward a known opening (for early game).
        
        - Adapts to user's rating (simpler openings for beginners)
        - Works for both colors (coach as White or Black)
        - Only applies in the first 8 moves
        
        Returns None if no guided move is appropriate.
        """
        import random
        
        board = chess.Board(fen)
        move_count = len(self.move_history)
        
        # Only guide in the first 8 moves
        if move_count > 8:
            return None
        
        # Convert move history to tuple for lookup
        history_tuple = tuple(self.move_history)
        
        # Check for specific continuation first
        if history_tuple in self.OPENING_CONTINUATIONS:
            guided_move = self.OPENING_CONTINUATIONS[history_tuple]
            try:
                move = board.parse_san(guided_move)
                if move in board.legal_moves:
                    return guided_move
            except:
                pass
        
        # === COACH PLAYS WHITE (user is Black) ===
        # Coach makes the FIRST move
        if self.user_color == "black" and move_count == 0:
            # Select opening based on user's skill level
            opening_options = self.WHITE_OPENING_MOVES.get(self.skill_tier, [])
            if opening_options:
                random.shuffle(opening_options)
                for first_move, target_openings in opening_options:
                    # Filter by complexity
                    valid_openings = self._filter_openings_by_complexity(target_openings)
                    if valid_openings:
                        try:
                            move = board.parse_san(first_move)
                            if move in board.legal_moves:
                                return first_move
                        except:
                            continue
        
        # === COACH PLAYS BLACK (user is White) ===
        # Respond to user's move
        if self.user_color == "white" and move_count >= 1:
            last_user_move = self.move_history[-1] if self.move_history else None
            
            # Get response options for this user move
            if last_user_move and last_user_move in self.BLACK_RESPONSES:
                options = self.BLACK_RESPONSES[last_user_move].get(self.skill_tier, [])
                if options:
                    # Shuffle for variety
                    shuffled = options.copy()
                    random.shuffle(shuffled)
                    for option in shuffled:
                        try:
                            move = board.parse_san(option)
                            if move in board.legal_moves:
                                return option
                        except:
                            continue
        
        return None
    
    async def get_move(self, fen: str) -> Optional[str]:
        """
        Get pedagogical move using Teaching Move Selector v2.

        Pipeline:
        1. Opening guide (first few moves) — scripted opening lines
        2. V2 selector: intent-driven, position-based scoring
        3. Fallback: raw Stockfish

        Returns:
            Move in SAN notation
        """
        try:
            # OPENING GUIDE: In early game, prefer moves that lead to known openings
            guided_move = self._get_opening_guided_move(fen)
            if guided_move:
                self.last_teaching_context = {
                    "teaching_goal": "opening_guidance",
                    "why_instructive": "Guiding toward a known opening for teaching",
                    "concept_taught": "opening_principles",
                    "student_challenge": "Learn the opening ideas",
                    "is_best_move": True,
                    "move_type": "opening_guide",
                    "v2": False,
                }
                print(f"[CoachOpponent] Using opening guide move: {guided_move} for FEN: {fen[:50]}...")
                return guided_move

            # V2 SELECTOR: position-based, intent-driven
            print(f"[CoachOpponent] Using TeachingMoveSelectorV2 for FEN: {fen[:50]}...")

            from coach_play.teaching.move_selector_v2 import TeachingMoveSelectorV2

            board = chess.Board(fen)
            coach_color = board.turn  # Coach is the side to move

            selector = TeachingMoveSelectorV2(user_rating=self.user_rating)
            result = selector.select_move(
                board=board,
                coach_color=coach_color,
                teaching_focus=self.teaching_focus,
                student_weaknesses=self.student_weaknesses,
                last_game_violations=self.last_game_violations,
            )

            # Store teaching context for later use
            self.last_teaching_context = {
                "teaching_goal": result.intent.value,
                "intent_reason": result.intent_reason,
                "why_instructive": result.score_breakdown.explanation,
                "concept_taught": result.intent.value,
                "student_challenge": f"What is the coach threatening with this move?",
                "is_best_move": result.eval_rank == 1,
                "move_type": result.intent.value,
                "eval_rank": result.eval_rank,
                "v2": True,
                "v2_breakdown": {
                    "raw_score": round(result.score_breakdown.raw_score, 3),
                    "engine_quality": round(result.score_breakdown.engine_quality, 3),
                    "final_score": round(result.score_breakdown.final_score, 3),
                    "sub_scores": {
                        k: round(v, 3) for k, v in result.score_breakdown.sub_scores.items()
                    },
                    "feasibility_fallbacks": result.feasibility_fallbacks,
                },
            }

            print(
                f"[CoachOpponent] V2 selected: {result.selected_san} "
                f"(intent={result.intent.value}, "
                f"score={result.score_breakdown.final_score:.2f}, "
                f"rank={result.eval_rank})"
            )
            return result.selected_san

        except Exception as e:
            print(f"Teaching Move Selector v2 error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to regular Stockfish move
            return await super().get_move(fen)
    
    def get_teaching_context(self) -> dict:
        """Get the teaching context from the last move selection."""
        return self.last_teaching_context
    
    async def get_move_with_teaching(self, fen: str) -> Tuple[Optional[str], dict]:
        """
        Get move along with teaching content.
        
        Returns:
            Tuple of (move_san, teaching_context)
        """
        move = await self.get_move(fen)
        return move, self.last_teaching_context
