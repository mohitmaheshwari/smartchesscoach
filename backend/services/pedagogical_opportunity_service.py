"""
Pedagogical Opportunity Service
================================

The brain of the "Pedagogical Opponent" feature.

This service transforms the coach from a "perfect engine" into a teaching partner
that intentionally creates learning opportunities based on the user's known weaknesses.

Core Philosophy:
- In openings: Play correct theoretical lines (teach accuracy)
- In middle/endgame: Sometimes play "good but not best" moves to test the user
- Target the user's specific weaknesses from past game analysis
- Use consequence-based learning: hide eval, reveal after user's response

How it works:
1. Query user's weakness profile from past games
2. Analyze current position with multi-PV
3. If conditions are right, find a "pedagogical move" that:
   - Is not a blunder (within acceptable evaluation loss)
   - Creates an opportunity matching user's known weakness
   - Sets up a position where the user can exploit the "mistake"
4. Track whether user found the opportunity for consequence feedback

Usage:
    service = PedagogicalOpportunityService(db, user_id)
    decision = await service.should_create_opportunity(board, game_phase, user_rating)
    if decision["create_opportunity"]:
        move = decision["pedagogical_move"]
        # Play this move, hide eval, track opportunity
"""

import chess
import chess.engine
import random
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

STOCKFISH_PATH = "/usr/games/stockfish"


class OpportunityType(str, Enum):
    """Types of learning opportunities we can create."""
    FORK = "fork"                       # Create a forkable position
    PIN = "pin"                         # Create a pinnable position
    SKEWER = "skewer"                   # Create a skewerable position
    HANGING_PIECE = "hanging_piece"     # Leave a piece tactically vulnerable
    BACK_RANK = "back_rank"             # Create back rank weakness
    PASSED_PAWN = "passed_pawn"         # Allow passed pawn creation
    KING_SAFETY = "king_safety"         # Create king safety exploit
    PIECE_ACTIVITY = "piece_activity"   # Allow better piece placement
    OUTPOST = "outpost"                 # Allow outpost occupation
    PAWN_STRUCTURE = "pawn_structure"   # Create pawn weakness
    ENDGAME_TECHNIQUE = "endgame_technique"  # Test endgame knowledge
    GENERAL = "general"                 # General tactical opportunity


@dataclass
class WeaknessProfile:
    """User's weakness profile from past games."""
    user_id: str
    games_analyzed: int = 0
    
    # Tactical weaknesses (0-100, higher = weaker)
    missed_forks: int = 50
    missed_pins: int = 50
    missed_skewers: int = 50
    hanging_piece_blindness: int = 50
    back_rank_awareness: int = 50
    
    # Positional weaknesses
    pawn_structure_understanding: int = 50
    piece_activity_sense: int = 50
    king_safety_awareness: int = 50
    endgame_technique: int = 50
    
    # Primary weakness areas (sorted by severity)
    primary_weaknesses: List[str] = field(default_factory=list)
    
    # Recent pattern: what user has been missing lately
    recent_misses: List[str] = field(default_factory=list)


@dataclass
class PedagogicalDecision:
    """Decision about whether and how to create a learning opportunity."""
    create_opportunity: bool = False
    
    # If creating opportunity:
    pedagogical_move: Optional[str] = None  # SAN notation
    pedagogical_move_uci: Optional[str] = None
    opportunity_type: Optional[OpportunityType] = None
    eval_sacrifice: float = 0.0  # How much eval we're giving up (pawns)
    
    # What the user should find
    expected_exploit_moves: List[str] = field(default_factory=list)
    target_squares: List[str] = field(default_factory=list)
    
    # Teaching context
    reason: str = ""
    skill_explanation: str = ""  # What concept this tests
    
    # If NOT creating opportunity:
    best_move: Optional[str] = None
    why_not_pedagogical: str = ""


class PedagogicalOpportunityService:
    """
    Service that decides when to create learning opportunities and how.
    """
    
    # Probability of pedagogical move by game phase
    PEDAGOGICAL_PROBABILITY = {
        "opening": 0.0,              # Never in opening - teach theory
        "early_middlegame": 0.20,    # 20% in early middlegame
        "middlegame": 0.25,          # 25% in middlegame
        "late_middlegame": 0.25,     # 25% in late middlegame
        "early_endgame": 0.30,       # 30% in early endgame
        "endgame": 0.30,             # 30% in endgame
        "deep_endgame": 0.25,        # 25% in deep endgame
    }
    
    # Eval sacrifice limits by user rating (in pawns)
    # These are the acceptable ranges for "good but not best" moves
    EVAL_SACRIFICE_BY_RATING = {
        # (min_sacrifice, max_sacrifice)
        "beginner": (0.5, 2.5),      # Rating < 1000: wider range, more obvious
        "intermediate": (0.3, 1.5),  # 1000-1400: moderate
        "club": (0.2, 1.0),          # 1400-1800: subtle
        "advanced": (0.15, 0.8),     # 1800+: very subtle
    }
    
    # Cooldown: minimum moves between pedagogical moves
    MIN_MOVES_BETWEEN_PEDAGOGICAL = 4
    
    def __init__(self, db: AsyncIOMotorDatabase, user_id: str):
        self.db = db
        self.user_id = user_id
        self._engine = None
    
    def _get_rating_tier(self, rating: int) -> str:
        """Get rating tier for calibration."""
        if rating < 1000:
            return "beginner"
        elif rating < 1400:
            return "intermediate"
        elif rating < 1800:
            return "club"
        else:
            return "advanced"
    
    async def get_weakness_profile(self) -> WeaknessProfile:
        """
        Get user's weakness profile from analyzed games.
        This is the key input for targeting opportunities.
        """
        profile = WeaknessProfile(user_id=self.user_id)
        
        try:
            # Get user's analyzed games with habits reports
            games = await self.db.games.find(
                {
                    "user_id": self.user_id,
                    "habits_report": {"$exists": True}
                },
                {"habits_report": 1, "stockfish_analysis": 1}
            ).sort("imported_at", -1).limit(20).to_list(length=20)
            
            if not games:
                return profile
            
            profile.games_analyzed = len(games)
            
            # Aggregate weakness data
            fork_misses = []
            pin_misses = []
            tactical_misses = []
            endgame_scores = []
            
            for game in games:
                habits = game.get("habits_report", {})
                analysis = game.get("stockfish_analysis", {})
                
                # Extract tactical misses from analysis
                if "missed_tactics" in analysis:
                    for tactic in analysis["missed_tactics"]:
                        tactic_type = tactic.get("type", "").lower()
                        if "fork" in tactic_type:
                            fork_misses.append(1)
                        elif "pin" in tactic_type:
                            pin_misses.append(1)
                        else:
                            tactical_misses.append(1)
                
                # Phase performance
                phase_perf = habits.get("phase_performance", {})
                if phase_perf.get("endgame", {}).get("accuracy"):
                    endgame_scores.append(phase_perf["endgame"]["accuracy"])
            
            # Calculate weakness scores (higher = weaker)
            if fork_misses:
                profile.missed_forks = min(100, 30 + len(fork_misses) * 10)
            if pin_misses:
                profile.missed_pins = min(100, 30 + len(pin_misses) * 10)
            if endgame_scores:
                avg_endgame = sum(endgame_scores) / len(endgame_scores)
                profile.endgame_technique = max(0, 100 - avg_endgame)
            
            # Determine primary weaknesses
            weaknesses = [
                ("fork", profile.missed_forks),
                ("pin", profile.missed_pins),
                ("tactics", 50 + len(tactical_misses) * 5),
                ("endgame", profile.endgame_technique),
                ("pawn_structure", profile.pawn_structure_understanding),
            ]
            weaknesses.sort(key=lambda x: x[1], reverse=True)
            profile.primary_weaknesses = [w[0] for w in weaknesses[:3]]
            
        except Exception as e:
            logger.warning(f"Error getting weakness profile: {e}")
        
        return profile
    
    def _get_engine(self) -> chess.engine.SimpleEngine:
        """Get or create Stockfish engine."""
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        return self._engine
    
    def _close_engine(self):
        """Close engine connection."""
        if self._engine:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None
    
    async def should_create_opportunity(
        self,
        board: chess.Board,
        game_phase: str,
        user_rating: int,
        moves_since_last_pedagogical: int,
        coach_eval_advantage: float  # Positive = coach is winning
    ) -> PedagogicalDecision:
        """
        Main decision point: should we create a learning opportunity here?
        
        Args:
            board: Current position (coach to move)
            game_phase: "opening", "middlegame", or "endgame"
            user_rating: User's rating for calibration
            moves_since_last_pedagogical: Cooldown tracking
            coach_eval_advantage: Current eval from coach's perspective
        
        Returns:
            PedagogicalDecision with move and context
        """
        decision = PedagogicalDecision()
        
        # === FILTERS: When NOT to create opportunity ===
        
        # 1. Never in opening (teach theory instead)
        # Check for any "opening" phase label
        if game_phase == "opening":
            decision.why_not_pedagogical = "In opening phase - teaching theory instead"
            return await self._get_best_move_decision(board, decision)
        
        # 2. Cooldown - don't overwhelm the student
        if moves_since_last_pedagogical < self.MIN_MOVES_BETWEEN_PEDAGOGICAL:
            decision.why_not_pedagogical = f"Cooldown: only {moves_since_last_pedagogical} moves since last"
            return await self._get_best_move_decision(board, decision)
        
        # 3. If coach is already losing, don't give more away
        if coach_eval_advantage < -1.0:  # Down more than 1 pawn
            decision.why_not_pedagogical = "Coach is losing - play best move"
            return await self._get_best_move_decision(board, decision)
        
        # 4. Probability check
        probability = self.PEDAGOGICAL_PROBABILITY.get(game_phase, 0.25)
        if random.random() > probability:
            decision.why_not_pedagogical = f"Random check failed ({probability:.0%} chance)"
            return await self._get_best_move_decision(board, decision)
        
        # === OPPORTUNITY CREATION ===
        
        try:
            # Get user's weakness profile
            weakness_profile = await self.get_weakness_profile()
            
            # Get multi-PV analysis
            engine = self._get_engine()
            analysis = engine.analyse(
                board,
                chess.engine.Limit(depth=16),
                multipv=6  # Get top 6 moves
            )
            
            if not analysis:
                return await self._get_best_move_decision(board, decision)
            
            # Get best move eval
            best_info = analysis[0]
            best_score = best_info["score"].relative
            if best_score.is_mate():
                best_eval = 10.0 if best_score.mate() > 0 else -10.0
            else:
                best_eval = best_score.score() / 100.0
            
            # Get acceptable sacrifice range
            rating_tier = self._get_rating_tier(user_rating)
            min_sacrifice, max_sacrifice = self.EVAL_SACRIFICE_BY_RATING.get(
                rating_tier, (0.5, 1.5)
            )
            
            # Look for a pedagogical move among alternatives
            pedagogical_candidate = await self._find_pedagogical_move(
                board=board,
                analysis=analysis,
                best_eval=best_eval,
                min_sacrifice=min_sacrifice,
                max_sacrifice=max_sacrifice,
                weakness_profile=weakness_profile,
                game_phase=game_phase
            )
            
            if pedagogical_candidate:
                decision.create_opportunity = True
                decision.pedagogical_move = pedagogical_candidate["move_san"]
                decision.pedagogical_move_uci = pedagogical_candidate["move_uci"]
                decision.opportunity_type = pedagogical_candidate["opportunity_type"]
                decision.eval_sacrifice = pedagogical_candidate["eval_sacrifice"]
                decision.expected_exploit_moves = pedagogical_candidate.get("exploit_moves", [])
                decision.target_squares = pedagogical_candidate.get("target_squares", [])
                decision.reason = pedagogical_candidate["reason"]
                decision.skill_explanation = pedagogical_candidate["skill_explanation"]
            else:
                decision.why_not_pedagogical = "No suitable pedagogical move found"
                return await self._get_best_move_decision(board, decision)
            
        except Exception as e:
            logger.error(f"Error creating opportunity: {e}")
            return await self._get_best_move_decision(board, decision)
        
        return decision
    
    async def _find_pedagogical_move(
        self,
        board: chess.Board,
        analysis: List,
        best_eval: float,
        min_sacrifice: float,
        max_sacrifice: float,
        weakness_profile: WeaknessProfile,
        game_phase: str
    ) -> Optional[Dict]:
        """
        Find a move that creates a learning opportunity.
        
        Returns dict with move info or None if no suitable move found.
        """
        candidates = []
        
        # Skip the best move (index 0), look at alternatives
        for i, info in enumerate(analysis[1:], start=2):
            if "pv" not in info or not info["pv"]:
                continue
            
            move = info["pv"][0]
            score = info["score"].relative
            
            if score.is_mate():
                eval_score = 10.0 if score.mate() > 0 else -10.0
            else:
                eval_score = score.score() / 100.0
            
            # Calculate sacrifice
            eval_sacrifice = best_eval - eval_score
            
            # Check if within acceptable range
            if eval_sacrifice < min_sacrifice or eval_sacrifice > max_sacrifice:
                continue
            
            # Check what opportunity this creates
            opportunity = self._analyze_opportunity(board, move, weakness_profile)
            
            if opportunity:
                candidates.append({
                    "move": move,
                    "move_san": board.san(move),
                    "move_uci": move.uci(),
                    "eval_sacrifice": eval_sacrifice,
                    "eval_rank": i,
                    **opportunity
                })
        
        if not candidates:
            return None
        
        # Prioritize opportunities matching user's weaknesses
        def score_candidate(c):
            score = 0
            opp_type = c["opportunity_type"]
            
            # Match to primary weaknesses
            if weakness_profile.primary_weaknesses:
                for i, weakness in enumerate(weakness_profile.primary_weaknesses):
                    if weakness in str(opp_type).lower():
                        score += (3 - i) * 10  # First weakness = +30, second = +20, etc.
            
            # Prefer moderate sacrifice (not too obvious, not too subtle)
            if 0.5 <= c["eval_sacrifice"] <= 1.0:
                score += 5
            
            return score
        
        candidates.sort(key=score_candidate, reverse=True)
        return candidates[0]
    
    def _analyze_opportunity(
        self,
        board: chess.Board,
        move: chess.Move,
        weakness_profile: WeaknessProfile
    ) -> Optional[Dict]:
        """
        Analyze what learning opportunity a move creates.
        
        Returns opportunity info or None if no good opportunity found.
        """
        board.push(move)
        
        try:
            opportunity = None
            our_color = not board.turn  # We just moved
            their_color = board.turn
            
            # Check for hanging piece (undefended attacked piece)
            hanging_squares = []
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece and piece.color == our_color:
                    if piece.piece_type != chess.PAWN:  # Ignore pawns
                        attackers = list(board.attackers(their_color, square))
                        defenders = list(board.attackers(our_color, square))
                        if attackers and len(attackers) > len(defenders):
                            hanging_squares.append(chess.square_name(square))
            
            if hanging_squares:
                # Find the attacking moves
                exploit_moves = []
                for target_sq in hanging_squares[:2]:  # Max 2 targets
                    target = chess.parse_square(target_sq)
                    for m in board.legal_moves:
                        if m.to_square == target:
                            exploit_moves.append(board.san(m))
                            break
                
                opportunity = {
                    "opportunity_type": OpportunityType.HANGING_PIECE,
                    "target_squares": hanging_squares,
                    "exploit_moves": exploit_moves,
                    "reason": f"Created opportunity to win material on {', '.join(hanging_squares)}",
                    "skill_explanation": "Piece is undefended or insufficiently defended - a tactical opportunity!"
                }
            
            # Check for fork opportunities
            if not opportunity:
                for m in board.legal_moves:
                    if board.piece_at(m.from_square) and board.piece_at(m.from_square).piece_type == chess.KNIGHT:
                        board.push(m)
                        attacks = list(board.attacks(m.to_square))
                        valuable_attacks = []
                        for sq in attacks:
                            p = board.piece_at(sq)
                            if p and p.color == our_color and p.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                                valuable_attacks.append(chess.square_name(sq))
                        board.pop()
                        
                        if len(valuable_attacks) >= 2:
                            opportunity = {
                                "opportunity_type": OpportunityType.FORK,
                                "target_squares": valuable_attacks,
                                "exploit_moves": [board.san(m)],
                                "reason": f"Knight fork opportunity on {', '.join(valuable_attacks)}",
                                "skill_explanation": "A knight can attack two pieces at once - find the fork!"
                            }
                            break
            
            # Check for pin opportunities
            if not opportunity:
                # Simplified pin detection
                for m in board.legal_moves:
                    piece = board.piece_at(m.from_square)
                    if piece and piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                        move_san = board.san(m)  # Save SAN before pushing
                        # Check if move creates a pin along a line
                        board.push(m)
                        found_pin = False
                        # Check if any enemy piece is now pinned to king
                        enemy_king_sq = board.king(our_color)
                        if enemy_king_sq:
                            for sq in chess.SQUARES:
                                p = board.piece_at(sq)
                                if p and p.color == our_color and p.piece_type != chess.KING:
                                    # Check if piece is on line between attacker and king
                                    if self._is_pinned_by_piece(board, sq, m.to_square, enemy_king_sq):
                                        opportunity = {
                                            "opportunity_type": OpportunityType.PIN,
                                            "target_squares": [chess.square_name(sq)],
                                            "exploit_moves": [move_san],
                                            "reason": f"Pin opportunity on {chess.square_name(sq)}",
                                            "skill_explanation": "A piece is pinned to the king - it cannot move!"
                                        }
                                        found_pin = True
                                        break
                        board.pop()  # Always pop after push
                        if found_pin:
                            break
            
            # General tactical opportunity (fallback)
            if not opportunity:
                # Check if there are any forcing moves (checks, captures)
                forcing_moves = []
                for m in board.legal_moves:
                    if board.is_capture(m):
                        forcing_moves.append(board.san(m))
                    else:
                        move_san = board.san(m)  # Save SAN before pushing
                        board.push(m)
                        if board.is_check():
                            forcing_moves.append(move_san)
                        board.pop()
                
                if forcing_moves:
                    opportunity = {
                        "opportunity_type": OpportunityType.GENERAL,
                        "target_squares": [],
                        "exploit_moves": forcing_moves[:3],
                        "reason": "Created tactical opportunities",
                        "skill_explanation": "Look for checks, captures, and threats!"
                    }
            
            return opportunity
            
        finally:
            board.pop()
    
    def _is_pinned_by_piece(
        self,
        board: chess.Board,
        pinned_sq: int,
        pinner_sq: int,
        king_sq: int
    ) -> bool:
        """Check if a piece is pinned to the king by another piece."""
        # Simplified: check if all three are on same rank/file/diagonal
        pinned_file, pinned_rank = chess.square_file(pinned_sq), chess.square_rank(pinned_sq)
        pinner_file, pinner_rank = chess.square_file(pinner_sq), chess.square_rank(pinner_sq)
        king_file, king_rank = chess.square_file(king_sq), chess.square_rank(king_sq)
        
        # Same file
        if pinned_file == pinner_file == king_file:
            if (pinner_rank < pinned_rank < king_rank) or (king_rank < pinned_rank < pinner_rank):
                return True
        
        # Same rank
        if pinned_rank == pinner_rank == king_rank:
            if (pinner_file < pinned_file < king_file) or (king_file < pinned_file < pinner_file):
                return True
        
        # Same diagonal
        if abs(pinned_file - pinner_file) == abs(pinned_rank - pinner_rank):
            if abs(king_file - pinner_file) == abs(king_rank - pinner_rank):
                if abs(pinned_file - king_file) == abs(pinned_rank - king_rank):
                    return True
        
        return False
    
    async def _get_best_move_decision(
        self,
        board: chess.Board,
        decision: PedagogicalDecision
    ) -> PedagogicalDecision:
        """Get the best move when not creating an opportunity."""
        try:
            engine = self._get_engine()
            result = engine.play(board, chess.engine.Limit(depth=14, time=0.5))
            if result.move:
                decision.best_move = board.san(result.move)
        except Exception as e:
            logger.error(f"Error getting best move: {e}")
            # Fallback to first legal move
            legal = list(board.legal_moves)
            if legal:
                decision.best_move = board.san(legal[0])
        
        return decision
    
    async def evaluate_user_response(
        self,
        board_after_coach: chess.Board,
        user_move: chess.Move,
        opportunity_type: OpportunityType,
        expected_exploit_moves: List[str]
    ) -> Dict:
        """
        Evaluate whether the user found the opportunity.
        
        Returns feedback for consequence-based coaching.
        """
        user_san = board_after_coach.san(user_move)
        
        # Check if user played one of the expected exploits
        found_opportunity = user_san in expected_exploit_moves
        
        # Get eval before and after user's move
        try:
            engine = self._get_engine()
            
            # Eval before user's move
            info_before = engine.analyse(board_after_coach, chess.engine.Limit(depth=14))
            eval_before = info_before["score"].relative.score(mate_score=10000) / 100.0
            
            # Eval after user's move
            board_after_coach.push(user_move)
            info_after = engine.analyse(board_after_coach, chess.engine.Limit(depth=14))
            eval_after = info_after["score"].relative.score(mate_score=10000) / 100.0
            board_after_coach.pop()
            
            # Calculate eval change (positive = user improved position)
            eval_change = eval_after - eval_before
            
        except Exception as e:
            logger.error(f"Error evaluating response: {e}")
            eval_change = 0.0
            eval_before = 0.0
            eval_after = 0.0
        
        # Generate consequence feedback
        if found_opportunity:
            consequence_type = "found"
            if opportunity_type == OpportunityType.FORK:
                message = f"Excellent! You found the fork with {user_san}! This is exactly the tactical pattern to look for."
            elif opportunity_type == OpportunityType.HANGING_PIECE:
                message = f"Great eye! {user_san} wins material. You spotted the undefended piece!"
            elif opportunity_type == OpportunityType.PIN:
                message = f"Well done! {user_san} exploits the pin. The piece couldn't move!"
            else:
                message = f"Nice! {user_san} takes advantage of the opportunity. Your tactical vision is sharp!"
        else:
            consequence_type = "missed"
            if expected_exploit_moves:
                best_exploit = expected_exploit_moves[0]
                if opportunity_type == OpportunityType.FORK:
                    message = f"You missed a fork! {best_exploit} would have attacked two pieces at once. " \
                              f"The eval dropped {abs(eval_change):.1f} pawns."
                elif opportunity_type == OpportunityType.HANGING_PIECE:
                    message = f"There was free material! {best_exploit} wins a piece. " \
                              f"Always check what's undefended before making your move."
                elif opportunity_type == OpportunityType.PIN:
                    message = f"You missed the pin! {best_exploit} would exploit the pinned piece. " \
                              f"Pins are powerful because the piece can't move."
                else:
                    message = f"There was a stronger move: {best_exploit}. " \
                              f"The position changed by {abs(eval_change):.1f} pawns."
            else:
                message = f"Your move was okay, but there might have been a better option. " \
                          f"Eval change: {eval_change:+.1f}"
        
        return {
            "found_opportunity": found_opportunity,
            "consequence_type": consequence_type,
            "eval_before": round(eval_before, 2),
            "eval_after": round(eval_after, 2),
            "eval_change": round(eval_change, 2),
            "message": message,
            "expected_move": expected_exploit_moves[0] if expected_exploit_moves else None,
            "user_move": user_san,
            "opportunity_type": opportunity_type.value if opportunity_type else "general"
        }
    
    def __del__(self):
        """Cleanup engine on destruction."""
        self._close_engine()
