"""
Teaching Move Selector
======================

The heart of the "Play to Teach" vision.

This service selects moves that CREATE LEARNING OPPORTUNITIES for the student,
NOT the objectively strongest moves. The coach plays to teach, not to win.

Philosophy:
- A good teacher doesn't crush the student
- A good teacher creates positions that illustrate concepts
- A good teacher adjusts to the student's level
- A good teacher makes the student THINK, not just react

Move Selection Criteria:
1. Instructive Value - Does this move teach something?
2. Appropriate Challenge - Is it right for this student's level?
3. Concept Alignment - Does it match what we're trying to teach?
4. Game Flow - Does it keep the game interesting and educational?

The selector considers:
- Student's rating and weaknesses
- Current game phase (opening/middlegame/endgame)
- Position type (tactical/positional/endgame technique)
- Teaching goals for this session
- Previous moves in the game (avoid repetition)

Usage:
    selector = TeachingMoveSelector()
    move = selector.select_move(
        board=board,
        student_rating=1200,
        student_weaknesses=["tactics", "endgame"],
        teaching_focus="piece_activity"
    )
"""

import chess
import chess.engine
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
import random

logger = logging.getLogger(__name__)


class TeachingGoal(str, Enum):
    """What we're trying to teach with this move."""
    TACTICS = "tactics"                     # Create tactical opportunities
    PIECE_ACTIVITY = "piece_activity"       # Show the value of active pieces
    PAWN_STRUCTURE = "pawn_structure"       # Teach structural concepts
    KING_SAFETY = "king_safety"             # Demonstrate king safety principles
    DEVELOPMENT = "development"             # Teach opening principles
    ENDGAME_TECHNIQUE = "endgame_technique" # Show endgame concepts
    PROPHYLAXIS = "prophylaxis"             # Teach defensive thinking
    ATTACK = "attack"                       # Demonstrate attacking ideas
    DEFENSE = "defense"                     # Show defensive resources
    SPACE = "space"                         # Teach space advantage
    INITIATIVE = "initiative"               # Show how to keep/gain initiative
    NATURAL_PLAY = "natural_play"           # Just play reasonable moves


class MoveType(str, Enum):
    """Classification of a move's character."""
    FORCING = "forcing"         # Check, capture, or strong threat
    TACTICAL = "tactical"       # Creates tactical complications
    POSITIONAL = "positional"   # Improves position quietly
    PROPHYLACTIC = "prophylactic"  # Prevents opponent's plan
    DEVELOPING = "developing"   # Brings piece into play
    QUIET = "quiet"            # Subtle, hard to understand
    AGGRESSIVE = "aggressive"   # Attacking move
    DEFENSIVE = "defensive"     # Addresses a threat
    INSTRUCTIVE = "instructive" # Perfect for teaching


@dataclass
class MoveCandidate:
    """A candidate move with teaching evaluation."""
    move: chess.Move
    san: str
    
    # Engine evaluation
    eval_score: float           # Centipawns (+ is good for side to move)
    eval_rank: int              # 1 = best move, 2 = second best, etc.
    
    # Teaching metrics
    teaching_value: float       # 0.0-1.0, how instructive is this move?
    teaching_goal: TeachingGoal # What concept does this teach?
    move_type: MoveType         # Type of move
    
    # Explanation
    why_instructive: str        # Why this move is good for teaching
    concept_taught: str         # The chess concept illustrated
    student_challenge: str      # What the student should think about
    
    # Penalties/Bonuses
    too_strong: bool = False    # Is this move too crushing?
    too_weak: bool = False      # Is this move too passive/bad?
    creates_tactics: bool = False  # Does it create tactical opportunities?
    simplifies: bool = False    # Does it trade pieces?
    
    # Final score
    final_score: float = 0.0    # Combined score for selection


@dataclass
class TeachingContext:
    """Context for move selection."""
    student_rating: int = 1200
    student_weaknesses: List[str] = field(default_factory=list)
    teaching_focus: Optional[TeachingGoal] = None
    game_phase: str = "middlegame"
    moves_played: int = 0
    coach_is_winning: bool = False
    position_is_sharp: bool = False
    concepts_covered: Set[str] = field(default_factory=set)


class TeachingMoveSelector:
    """
    Selects moves that teach rather than crush.
    """
    
    # Rating bands for appropriate challenge
    RATING_BANDS = {
        "beginner": (0, 1000),
        "intermediate": (1000, 1400),
        "club": (1400, 1800),
        "advanced": (1800, 2200),
        "expert": (2200, 3000)
    }
    
    # How much worse than best move is acceptable (centipawns)
    ACCEPTABLE_LOSS = {
        "beginner": 200,      # Can play moves up to 2 pawns worse
        "intermediate": 150,  # Up to 1.5 pawns worse
        "club": 100,          # Up to 1 pawn worse
        "advanced": 75,       # Up to 0.75 pawns worse
        "expert": 50          # Up to 0.5 pawns worse
    }
    
    # Teaching priorities by game phase
    PHASE_TEACHING = {
        "opening": [
            TeachingGoal.DEVELOPMENT,
            TeachingGoal.PIECE_ACTIVITY,
            TeachingGoal.KING_SAFETY
        ],
        "early_middlegame": [
            TeachingGoal.PIECE_ACTIVITY,
            TeachingGoal.TACTICS,
            TeachingGoal.PAWN_STRUCTURE
        ],
        "middlegame": [
            TeachingGoal.TACTICS,
            TeachingGoal.ATTACK,
            TeachingGoal.PIECE_ACTIVITY
        ],
        "late_middlegame": [
            TeachingGoal.ENDGAME_TECHNIQUE,
            TeachingGoal.PAWN_STRUCTURE,
            TeachingGoal.TACTICS
        ],
        "endgame": [
            TeachingGoal.ENDGAME_TECHNIQUE,
            TeachingGoal.KING_SAFETY,  # King activity
            TeachingGoal.PAWN_STRUCTURE
        ],
        "deep_endgame": [
            TeachingGoal.ENDGAME_TECHNIQUE,
            TeachingGoal.PROPHYLAXIS,
            TeachingGoal.NATURAL_PLAY
        ]
    }
    
    def __init__(self, stockfish_path: str = "/usr/games/stockfish"):
        """Initialize with Stockfish engine."""
        self.stockfish_path = stockfish_path
        self.engine = None
    
    def _get_engine(self) -> chess.engine.SimpleEngine:
        """Get or create engine instance."""
        if self.engine is None:
            try:
                self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
                # Limit strength for teaching
                self.engine.configure({"Skill Level": 15})  # Not maximum strength
            except Exception as e:
                logger.error(f"Failed to start Stockfish: {e}")
                raise
        return self.engine
    
    def _close_engine(self):
        """Close engine connection."""
        if self.engine:
            self.engine.quit()
            self.engine = None
    
    def get_student_band(self, rating: int) -> str:
        """Get the rating band for a student."""
        for band, (low, high) in self.RATING_BANDS.items():
            if low <= rating < high:
                return band
        return "intermediate"
    
    def select_move(
        self,
        board: chess.Board,
        student_rating: int = 1200,
        student_weaknesses: List[str] = None,
        teaching_focus: TeachingGoal = None,
        game_phase: str = "middlegame",
        avoid_crushing: bool = True
    ) -> Dict:
        """
        Select the most instructive move for the current position.
        
        Args:
            board: Current position
            student_rating: Student's rating for calibration
            student_weaknesses: List of weakness areas to target
            teaching_focus: Specific concept to teach (optional)
            game_phase: Current game phase
            avoid_crushing: If True, avoid moves that win immediately
            
        Returns:
            Dict with selected move and teaching explanation
        """
        if student_weaknesses is None:
            student_weaknesses = []
        
        context = TeachingContext(
            student_rating=student_rating,
            student_weaknesses=student_weaknesses,
            teaching_focus=teaching_focus,
            game_phase=game_phase,
            moves_played=len(board.move_stack)
        )
        
        try:
            engine = self._get_engine()
            
            # Get multiple candidate moves from engine
            candidates = self._get_candidate_moves(board, engine, context)
            
            if not candidates:
                return {"error": "No legal moves available"}
            
            # Evaluate each candidate for teaching value
            evaluated = self._evaluate_candidates(board, candidates, context)
            
            # Select the best teaching move
            selected = self._select_best_teaching_move(evaluated, context, avoid_crushing)
            
            # Generate teaching content
            teaching = self._generate_teaching_content(board, selected, context)
            
            return {
                "selected_move": selected.san,
                "move_uci": selected.move.uci(),
                "teaching_goal": selected.teaching_goal.value,
                "move_type": selected.move_type.value,
                "eval_rank": selected.eval_rank,
                "why_instructive": selected.why_instructive,
                "concept_taught": selected.concept_taught,
                "student_challenge": selected.student_challenge,
                "teaching_content": teaching,
                "is_best_move": selected.eval_rank == 1,
                "eval_score_cp": int(selected.eval_score),
                "alternatives_considered": len(evaluated)
            }
            
        except Exception as e:
            logger.error(f"Move selection error: {e}")
            return {"error": str(e)}
    
    def _get_candidate_moves(
        self,
        board: chess.Board,
        engine: chess.engine.SimpleEngine,
        context: TeachingContext
    ) -> List[MoveCandidate]:
        """Get candidate moves from engine with evaluations."""
        candidates = []
        
        # Get top N moves from engine
        num_candidates = 8  # Consider top 8 moves
        
        try:
            result = engine.analyse(
                board,
                chess.engine.Limit(depth=15),
                multipv=num_candidates
            )
        except Exception as e:
            logger.error(f"Engine analysis failed: {e}")
            # Fallback: just get legal moves
            for i, move in enumerate(list(board.legal_moves)[:5]):
                candidates.append(MoveCandidate(
                    move=move,
                    san=board.san(move),
                    eval_score=0,
                    eval_rank=i + 1,
                    teaching_value=0.5,
                    teaching_goal=TeachingGoal.NATURAL_PLAY,
                    move_type=MoveType.QUIET,
                    why_instructive="",
                    concept_taught="",
                    student_challenge=""
                ))
            return candidates
        
        # Process each PV line
        for i, info in enumerate(result):
            if "pv" not in info or not info["pv"]:
                continue
            
            move = info["pv"][0]
            
            # Get evaluation
            score = info.get("score", chess.engine.Cp(0))
            if score.is_mate():
                eval_cp = 10000 if score.mate() > 0 else -10000
            else:
                eval_cp = score.relative.score(mate_score=10000)
            
            candidates.append(MoveCandidate(
                move=move,
                san=board.san(move),
                eval_score=eval_cp,
                eval_rank=i + 1,
                teaching_value=0,  # Will be calculated
                teaching_goal=TeachingGoal.NATURAL_PLAY,
                move_type=MoveType.QUIET,
                why_instructive="",
                concept_taught="",
                student_challenge=""
            ))
        
        return candidates
    
    def _evaluate_candidates(
        self,
        board: chess.Board,
        candidates: List[MoveCandidate],
        context: TeachingContext
    ) -> List[MoveCandidate]:
        """Evaluate each candidate for teaching value."""
        
        best_eval = candidates[0].eval_score if candidates else 0
        student_band = self.get_student_band(context.student_rating)
        acceptable_loss = self.ACCEPTABLE_LOSS.get(student_band, 100)
        
        # Get phase-appropriate teaching goals
        phase_goals = self.PHASE_TEACHING.get(
            context.game_phase, 
            [TeachingGoal.NATURAL_PLAY]
        )
        
        for candidate in candidates:
            # Classify the move type
            candidate.move_type = self._classify_move_type(board, candidate.move)
            
            # Determine teaching goal this move serves
            candidate.teaching_goal = self._determine_teaching_goal(
                board, candidate.move, phase_goals, context
            )
            
            # Check if move is too strong (crushing)
            if candidate.eval_score > 500:  # More than 5 pawns up
                candidate.too_strong = True
            
            # Check if move is too weak
            loss = best_eval - candidate.eval_score
            if loss > acceptable_loss:
                candidate.too_weak = True
            
            # CRITICAL: Check if move hangs a piece - NEVER allow this
            if self._hangs_piece(board, candidate.move):
                candidate.too_weak = True
                candidate.teaching_value = 0  # Zero teaching value for blunders
            
            # Check if creates tactics
            candidate.creates_tactics = self._creates_tactical_opportunity(
                board, candidate.move
            )
            
            # Check if simplifies
            captured = board.piece_at(candidate.move.to_square)
            if captured:
                candidate.simplifies = True
            
            # Calculate teaching value
            teaching_value = self._calculate_teaching_value(
                candidate, context, phase_goals
            )
            candidate.teaching_value = teaching_value
            
            # Generate explanations
            self._generate_move_explanation(board, candidate, context)
            
            # Calculate final score
            candidate.final_score = self._calculate_final_score(
                candidate, context
            )
        
        # Sort by final score
        candidates.sort(key=lambda c: c.final_score, reverse=True)
        
        return candidates
    
    def _classify_move_type(self, board: chess.Board, move: chess.Move) -> MoveType:
        """Classify the type of move."""
        # Check if it's a capture
        is_capture = board.is_capture(move)
        
        # Check if it gives check
        board.push(move)
        is_check = board.is_check()
        board.pop()
        
        if is_check:
            return MoveType.FORCING
        
        if is_capture:
            return MoveType.TACTICAL
        
        # Check if it's a developing move (in opening)
        piece = board.piece_at(move.from_square)
        if piece:
            from_rank = chess.square_rank(move.from_square)
            
            # Knight or Bishop from back rank
            if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                if (piece.color == chess.WHITE and from_rank <= 1) or \
                   (piece.color == chess.BLACK and from_rank >= 6):
                    return MoveType.DEVELOPING
            
            # Castling
            if board.is_castling(move):
                return MoveType.DEVELOPING
        
        # Default to positional
        return MoveType.POSITIONAL
    
    def _determine_teaching_goal(
        self,
        board: chess.Board,
        move: chess.Move,
        phase_goals: List[TeachingGoal],
        context: TeachingContext
    ) -> TeachingGoal:
        """Determine what concept this move teaches."""
        
        piece = board.piece_at(move.from_square)
        if not piece:
            return TeachingGoal.NATURAL_PLAY
        
        # Check for tactical opportunities
        board.push(move)
        
        # Count threats created
        threats = self._count_threats(board)
        
        # Check for check or mate threat
        if board.is_check():
            board.pop()
            return TeachingGoal.TACTICS
        
        board.pop()
        
        if threats >= 2:
            return TeachingGoal.TACTICS
        
        # Development moves
        if self._is_developing_move(board, move, piece):
            return TeachingGoal.DEVELOPMENT
        
        # Piece activity improvement
        if self._improves_piece_activity(board, move, piece):
            return TeachingGoal.PIECE_ACTIVITY
        
        # Pawn structure moves
        if piece.piece_type == chess.PAWN:
            return TeachingGoal.PAWN_STRUCTURE
        
        # King safety (castling or king moves)
        if piece.piece_type == chess.KING or board.is_castling(move):
            return TeachingGoal.KING_SAFETY
        
        # Match to student weakness if possible
        if "tactics" in context.student_weaknesses and threats > 0:
            return TeachingGoal.TACTICS
        
        if "endgame" in context.student_weaknesses and context.game_phase in ["endgame", "deep_endgame"]:
            return TeachingGoal.ENDGAME_TECHNIQUE
        
        # Default to first phase goal
        return phase_goals[0] if phase_goals else TeachingGoal.NATURAL_PLAY
    
    def _count_threats(self, board: chess.Board) -> int:
        """Count number of threats in position."""
        threats = 0
        side = not board.turn  # We just moved, so count our threats
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == side:
                # Count attacks on opponent pieces
                attacks = board.attacks(square)
                for target in attacks:
                    target_piece = board.piece_at(target)
                    if target_piece and target_piece.color != side:
                        if target_piece.piece_type in [chess.QUEEN, chess.ROOK]:
                            threats += 1
                        elif target_piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                            threats += 0.5
        
        return int(threats)
    
    def _is_developing_move(
        self, 
        board: chess.Board, 
        move: chess.Move, 
        piece: chess.Piece
    ) -> bool:
        """Check if this is a developing move."""
        if board.is_castling(move):
            return True
        
        from_rank = chess.square_rank(move.from_square)
        
        # Knights and bishops from back rank
        if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
            if piece.color == chess.WHITE and from_rank == 0:
                return True
            if piece.color == chess.BLACK and from_rank == 7:
                return True
        
        return False
    
    def _improves_piece_activity(
        self,
        board: chess.Board,
        move: chess.Move,
        piece: chess.Piece
    ) -> bool:
        """Check if move improves piece activity."""
        old_attacks = len(board.attacks(move.from_square))
        
        board.push(move)
        new_attacks = len(board.attacks(move.to_square))
        board.pop()
        
        return new_attacks > old_attacks
    
    def _creates_tactical_opportunity(
        self,
        board: chess.Board,
        move: chess.Move
    ) -> bool:
        """Check if move creates tactical opportunities for the student."""
        board.push(move)
        
        # Check if there are tactical responses for opponent
        has_tactics = False
        
        for response in list(board.legal_moves)[:10]:
            # Check if response is a capture or check
            if board.is_capture(response):
                has_tactics = True
                break
            
            board.push(response)
            if board.is_check():
                has_tactics = True
            board.pop()
            
            if has_tactics:
                break
        
        board.pop()
        return has_tactics
    
    def _hangs_piece(self, board: chess.Board, move: chess.Move) -> bool:
        """
        Check if the move hangs a piece (leaves it undefended and attackable).
        This is CRITICAL - we should NEVER play moves that hang pieces.
        """
        # Make the move
        board.push(move)
        our_color = not board.turn  # We just moved
        
        # Check all our pieces for hanging
        hangs_material = False
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == our_color:
                # Skip pawns for simplicity
                if piece.piece_type == chess.PAWN:
                    continue
                
                # Is this piece attacked?
                if board.is_attacked_by(board.turn, square):
                    # Is it defended?
                    defenders = len([s for s in board.attackers(our_color, square)])
                    attackers = len([s for s in board.attackers(board.turn, square)])
                    
                    if attackers > defenders:
                        # Piece is hanging!
                        # More attackers than defenders = piece is lost
                        hangs_material = True
                        break
                    elif attackers > 0 and defenders == 0:
                        # Undefended and attacked = hanging
                        hangs_material = True
                        break
        
        board.pop()
        return hangs_material
    
    def _calculate_teaching_value(
        self,
        candidate: MoveCandidate,
        context: TeachingContext,
        phase_goals: List[TeachingGoal]
    ) -> float:
        """Calculate the teaching value of a move (0.0 - 1.0)."""
        value = 0.5  # Base value
        
        # Bonus for matching phase goals
        if candidate.teaching_goal in phase_goals:
            goal_index = phase_goals.index(candidate.teaching_goal)
            value += 0.2 * (1 - goal_index / len(phase_goals))
        
        # Bonus for matching student weaknesses
        weakness_goals = {
            "tactics": TeachingGoal.TACTICS,
            "piece_activity": TeachingGoal.PIECE_ACTIVITY,
            "pawn_structure": TeachingGoal.PAWN_STRUCTURE,
            "king_safety": TeachingGoal.KING_SAFETY,
            "development": TeachingGoal.DEVELOPMENT,
            "endgame": TeachingGoal.ENDGAME_TECHNIQUE
        }
        
        for weakness in context.student_weaknesses:
            if weakness in weakness_goals:
                if candidate.teaching_goal == weakness_goals[weakness]:
                    value += 0.15
        
        # Bonus for matching explicit teaching focus
        if context.teaching_focus and candidate.teaching_goal == context.teaching_focus:
            value += 0.2
        
        # Bonus for creating tactical opportunities
        if candidate.creates_tactics:
            value += 0.1
        
        # Penalty for too strong (crushing) moves
        if candidate.too_strong:
            value -= 0.3
        
        # Penalty for too weak moves
        if candidate.too_weak:
            value -= 0.4
        
        # Slight penalty for simplification (reduces teaching material)
        if candidate.simplifies:
            value -= 0.05
        
        # Bonus for instructive move types
        if candidate.move_type in [MoveType.DEVELOPING, MoveType.POSITIONAL]:
            value += 0.05
        
        return max(0.0, min(1.0, value))
    
    def _generate_move_explanation(
        self,
        board: chess.Board,
        candidate: MoveCandidate,
        context: TeachingContext
    ) -> None:
        """Generate teaching explanations for the move."""
        
        piece = board.piece_at(candidate.move.from_square)
        piece_name = self._piece_name(piece) if piece else "piece"
        to_sq = chess.square_name(candidate.move.to_square)
        
        # Generate based on teaching goal
        explanations = {
            TeachingGoal.TACTICS: {
                "why": f"This {piece_name} move creates tactical pressure",
                "concept": "Creating threats forces your opponent to react",
                "challenge": "What threats does this move create? How would you defend?"
            },
            TeachingGoal.PIECE_ACTIVITY: {
                "why": f"Moving the {piece_name} to {to_sq} increases its activity",
                "concept": "Active pieces control more squares and create more options",
                "challenge": "Notice how many more squares this piece now influences"
            },
            TeachingGoal.DEVELOPMENT: {
                "why": f"This develops the {piece_name} toward the center",
                "concept": "Piece development is crucial in the opening - get all pieces into play",
                "challenge": "Which of your pieces is still undeveloped?"
            },
            TeachingGoal.PAWN_STRUCTURE: {
                "why": "This pawn move shapes the structure of the game",
                "concept": "Pawn structure determines where pieces belong and what plans to follow",
                "challenge": "How does this pawn move affect the position long-term?"
            },
            TeachingGoal.KING_SAFETY: {
                "why": "This move prioritizes king safety",
                "concept": "A safe king allows you to play aggressively with other pieces",
                "challenge": "Is your king safe? What would happen if it wasn't?"
            },
            TeachingGoal.ENDGAME_TECHNIQUE: {
                "why": "This is a key endgame technique",
                "concept": "In endgames, precise technique is more important than material",
                "challenge": "What's the plan to convert this position?"
            },
            TeachingGoal.PROPHYLAXIS: {
                "why": "This move prevents your plan before you execute it",
                "concept": "Good players always ask: 'What does my opponent want to do?'",
                "challenge": "What was I preventing with this move?"
            },
            TeachingGoal.ATTACK: {
                "why": "This move increases pressure on your position",
                "concept": "Coordinated attacks on weaknesses win games",
                "challenge": "How will you defend against this pressure?"
            },
            TeachingGoal.NATURAL_PLAY: {
                "why": "This is a natural developing/improving move",
                "concept": "Good chess is often about making sensible, solid moves",
                "challenge": "What would be a good response to this?"
            }
        }
        
        explanation = explanations.get(candidate.teaching_goal, explanations[TeachingGoal.NATURAL_PLAY])
        
        candidate.why_instructive = explanation["why"]
        candidate.concept_taught = explanation["concept"]
        candidate.student_challenge = explanation["challenge"]
    
    def _calculate_final_score(
        self,
        candidate: MoveCandidate,
        context: TeachingContext
    ) -> float:
        """Calculate final selection score combining teaching and quality."""
        
        # Teaching value is most important
        score = candidate.teaching_value * 0.6
        
        # Evaluation rank matters but less so
        rank_score = max(0, 1 - (candidate.eval_rank - 1) * 0.15)
        score += rank_score * 0.25
        
        # Randomness for variety (avoid predictable play)
        score += random.uniform(0, 0.15)
        
        # Penalty for too strong/weak
        if candidate.too_strong:
            score *= 0.5
        if candidate.too_weak:
            score *= 0.3
        
        return score
    
    def _select_best_teaching_move(
        self,
        candidates: List[MoveCandidate],
        context: TeachingContext,
        avoid_crushing: bool
    ) -> MoveCandidate:
        """Select the best move for teaching from evaluated candidates."""
        
        # CRITICAL: Sort by evaluation first to ensure we never play blunders
        # Even for teaching, we should not lose material needlessly
        sorted_by_eval = sorted(candidates, key=lambda c: c.eval_score, reverse=True)
        
        # Filter out unacceptable moves (moves that are too weak)
        acceptable = [c for c in sorted_by_eval if not c.too_weak]
        
        if avoid_crushing:
            # Also filter out crushing moves unless all are crushing
            non_crushing = [c for c in acceptable if not c.too_strong]
            if non_crushing:
                acceptable = non_crushing
        
        if not acceptable:
            # If all moves are too weak or too strong, 
            # at least pick the best evaluated move (don't blunder!)
            acceptable = sorted_by_eval
        
        # Sort acceptable moves by teaching value
        acceptable.sort(key=lambda c: c.teaching_value, reverse=True)
        
        # Return the highest teaching value among acceptable moves
        # But ensure it's in the top 3 evaluated moves to avoid blunders
        for candidate in acceptable:
            if candidate.eval_rank <= 3:  # Top 3 engine moves only
                return candidate
        
        # Fallback: just return the best evaluated move
        return sorted_by_eval[0] if sorted_by_eval else candidates[0]
    
    def _generate_teaching_content(
        self,
        board: chess.Board,
        selected: MoveCandidate,
        context: TeachingContext
    ) -> Dict:
        """Generate comprehensive teaching content for the selected move."""
        
        return {
            "before_move": self._generate_before_move_teaching(board, selected, context),
            "after_move": self._generate_after_move_teaching(board, selected, context),
            "thinking_prompt": selected.student_challenge,
            "concept_explanation": selected.concept_taught,
            "related_concepts": self._get_related_concepts(selected.teaching_goal),
            "difficulty_appropriate": self._is_difficulty_appropriate(selected, context)
        }
    
    def _generate_before_move_teaching(
        self,
        board: chess.Board,
        selected: MoveCandidate,
        context: TeachingContext
    ) -> str:
        """Teaching message before showing the move."""
        
        prompts = {
            TeachingGoal.TACTICS: "Let me show you how to create threats...",
            TeachingGoal.PIECE_ACTIVITY: "Watch how I improve my piece's position...",
            TeachingGoal.DEVELOPMENT: "Here's how to get pieces into play efficiently...",
            TeachingGoal.PAWN_STRUCTURE: "This pawn move will shape our plans...",
            TeachingGoal.KING_SAFETY: "Let's make sure our king is safe first...",
            TeachingGoal.ENDGAME_TECHNIQUE: "In endgames, technique is everything...",
            TeachingGoal.PROPHYLAXIS: "Before attacking, let me prevent your idea...",
            TeachingGoal.ATTACK: "Now let's increase the pressure...",
            TeachingGoal.NATURAL_PLAY: "Here's a solid move..."
        }
        
        return prompts.get(selected.teaching_goal, "Let me make a move...")
    
    def _generate_after_move_teaching(
        self,
        board: chess.Board,
        selected: MoveCandidate,
        context: TeachingContext
    ) -> str:
        """Teaching explanation after the move."""
        
        return f"I played {selected.san}. {selected.why_instructive}. " \
               f"{selected.concept_taught}. Now, {selected.student_challenge}"
    
    def _get_related_concepts(self, goal: TeachingGoal) -> List[str]:
        """Get related chess concepts for deeper learning."""
        
        related = {
            TeachingGoal.TACTICS: ["combinations", "calculation", "pattern recognition"],
            TeachingGoal.PIECE_ACTIVITY: ["centralization", "coordination", "outposts"],
            TeachingGoal.DEVELOPMENT: ["opening principles", "time in chess", "tempi"],
            TeachingGoal.PAWN_STRUCTURE: ["pawn chains", "weak squares", "passed pawns"],
            TeachingGoal.KING_SAFETY: ["castling", "pawn shelter", "king attacks"],
            TeachingGoal.ENDGAME_TECHNIQUE: ["king activity", "zugzwang", "opposition"],
            TeachingGoal.PROPHYLAXIS: ["defense", "preventing threats", "Nimzowitsch"],
            TeachingGoal.ATTACK: ["attacking the king", "creating weaknesses", "initiative"]
        }
        
        return related.get(goal, ["general chess principles"])
    
    def _is_difficulty_appropriate(
        self,
        selected: MoveCandidate,
        context: TeachingContext
    ) -> bool:
        """Check if the move's difficulty matches student level."""
        
        band = self.get_student_band(context.student_rating)
        
        # Very quiet moves might be too subtle for beginners
        if band == "beginner" and selected.move_type == MoveType.QUIET:
            return False
        
        # Very forcing moves might be too easy for experts
        if band == "expert" and selected.move_type == MoveType.FORCING:
            if selected.eval_rank == 1:  # Only move
                return True  # It's fine
        
        return True
    
    def _piece_name(self, piece: chess.Piece) -> str:
        """Get piece name."""
        names = {
            chess.KING: "King",
            chess.QUEEN: "Queen",
            chess.ROOK: "Rook",
            chess.BISHOP: "Bishop",
            chess.KNIGHT: "Knight",
            chess.PAWN: "pawn"
        }
        return names.get(piece.piece_type, "piece")
    
    def __del__(self):
        """Cleanup engine on destruction."""
        self._close_engine()


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def select_teaching_move(
    fen: str,
    student_rating: int = 1200,
    student_weaknesses: List[str] = None,
    teaching_focus: str = None,
    game_phase: str = "middlegame"
) -> Dict:
    """
    Convenience function to select a teaching move.
    
    Args:
        fen: Position in FEN format
        student_rating: Student's rating
        student_weaknesses: List of weakness areas
        teaching_focus: Specific concept to teach
        game_phase: Current game phase
        
    Returns:
        Dict with selected move and teaching content
    """
    try:
        board = chess.Board(fen)
    except Exception as e:
        return {"error": f"Invalid FEN: {e}"}
    
    # Convert teaching_focus string to enum
    focus = None
    if teaching_focus:
        try:
            focus = TeachingGoal(teaching_focus)
        except ValueError:
            pass
    
    selector = TeachingMoveSelector()
    result = selector.select_move(
        board=board,
        student_rating=student_rating,
        student_weaknesses=student_weaknesses or [],
        teaching_focus=focus,
        game_phase=game_phase
    )
    
    return result
