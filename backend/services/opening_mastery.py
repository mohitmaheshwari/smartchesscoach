"""
Opening Mastery System
======================

A complete opening teaching system that:
1. Identifies openings from current position
2. Offers to teach main lines, traps, plans
3. Remembers what user has learned
4. Tracks if user applies learnings in real games
5. Builds progressive mastery

Philosophy:
- Coach is NOT trying to win, coach is trying to TEACH
- Each opening has: main line, traps, key ideas, common mistakes
- User progresses: Learn → Practice → Apply in real games → Master
- Once mastered, move to next opening

Collections:
- opening_knowledge: Database of openings with teaching content
- user_opening_progress: What each user knows, has practiced, mastered
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime, timezone
import chess
import logging

logger = logging.getLogger(__name__)


class MasteryLevel(str, Enum):
    """User's mastery level for an opening."""
    UNKNOWN = "unknown"          # Never seen this opening
    INTRODUCED = "introduced"    # Coach showed it once
    LEARNING = "learning"        # Currently learning
    PRACTICED = "practiced"      # Practiced in Play with Coach
    APPLIED = "applied"          # Used in a real game
    MASTERED = "mastered"        # Consistently applies correctly


class TeachingMode(str, Enum):
    """What the coach is teaching right now."""
    NONE = "none"
    MAIN_LINE = "main_line"
    TRAP = "trap"
    KEY_IDEAS = "key_ideas"
    QUIZ = "quiz"


@dataclass
class OpeningTrap:
    """A tactical trap within an opening."""
    name: str                    # "Fried Liver Attack"
    moves: List[str]             # ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"]
    trap_move: str               # "Nxf7" - the trap move
    explanation: str             # Why it works
    refutation: Optional[str]    # How to avoid if you're the victim
    fen_before_trap: str         # Position before the trap
    fen_after_trap: str          # Position after the trap lands
    victim_color: str            # "black" - who falls for the trap
    difficulty: str              # "beginner", "intermediate", "advanced"


@dataclass
class OpeningVariation:
    """A variation within an opening."""
    name: str                    # "Giuoco Piano"
    eco: str                     # "C53"
    moves: List[str]             # Main line moves
    key_ideas: List[str]         # Strategic ideas
    plans_for_white: List[str]   # What white wants
    plans_for_black: List[str]   # What black wants
    common_mistakes: List[str]   # What to avoid
    traps: List[OpeningTrap]     # Traps in this variation
    model_games: List[str]       # Famous games to study (optional)


@dataclass
class OpeningFamily:
    """A family of openings (e.g., Italian Game)."""
    name: str                    # "Italian Game"
    eco_range: str               # "C50-C59"
    first_moves: List[str]       # ["e4", "e5", "Nf3", "Nc6", "Bc4"]
    description: str             # Brief description
    character: str               # "open", "closed", "semi-open"
    suitable_for: List[str]      # ["beginners", "tactical players"]
    variations: List[OpeningVariation]
    introduction_message: str    # What coach says when entering this opening
    mastery_criteria: Dict       # What defines mastery


@dataclass
class UserOpeningProgress:
    """Track user's progress in learning an opening."""
    user_id: str
    opening_name: str
    mastery_level: MasteryLevel
    introduced_at: Optional[datetime]
    last_practiced_at: Optional[datetime]
    times_practiced: int
    times_applied_in_games: int
    correct_applications: int    # Times they played it correctly in real games
    traps_learned: List[str]     # Names of traps they've learned
    variations_learned: List[str]  # Variations they know
    quiz_scores: List[Dict]      # History of quiz attempts
    notes: str                   # Coach's notes about this user's progress


# ============================================
# OPENING KNOWLEDGE DATABASE
# ============================================

# This is the teaching content - each opening with its traps and lines
OPENING_DATABASE: Dict[str, OpeningFamily] = {}


def _build_opening_database():
    """Build the opening knowledge database."""
    global OPENING_DATABASE
    
    # ==================== ITALIAN GAME ====================
    italian_traps = [
        OpeningTrap(
            name="Fried Liver Attack",
            moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "d5", "exd5", "Nxd5", "Nxf7"],
            trap_move="Nxf7",
            explanation="White sacrifices the knight to expose Black's king. After Kxf7, Qf3+ is devastating.",
            refutation="Black should play Na5 or d5 earlier to avoid this. After Nxf7, best is Kxf7, but it's very dangerous.",
            fen_before_trap="r1bqkb1r/ppp2ppp/2n2n2/3pp1N1/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
            fen_after_trap="r1bqkb1r/ppp2Npp/2n5/3np3/2B5/8/PPPP1PPP/RNBQK2R b KQkq - 0 6",
            victim_color="black",
            difficulty="beginner"
        ),
        OpeningTrap(
            name="Legal's Mate Trap",
            moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "d6", "Nc3", "Bg4", "h3", "Bh5", "Nxe5"],
            trap_move="Nxe5",
            explanation="White sacrifices the queen! After Bxd1, Bxf7+ Ke7, Nd5# is checkmate.",
            refutation="Black should not take the queen. Instead play Nxe5 or just develop.",
            fen_before_trap="r2qkbnr/ppp2ppp/2np4/4p2b/2B1P3/2N2N1P/PPPP1PP1/R1BQK2R w KQkq - 1 6",
            fen_after_trap="r2qkbnr/ppp2ppp/2np4/4N2b/2B1P3/2N4P/PPPP1PP1/R1BQK2R b KQkq - 0 6",
            victim_color="black",
            difficulty="beginner"
        ),
    ]
    
    italian_variations = [
        OpeningVariation(
            name="Giuoco Piano",
            eco="C53",
            moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"],
            key_ideas=[
                "Control the center with pawns and pieces",
                "Develop bishops actively before knights sometimes",
                "Prepare d4 push to open the center"
            ],
            plans_for_white=[
                "Push d4 to challenge Black's center",
                "Castle kingside for safety",
                "Attack on the kingside with pieces"
            ],
            plans_for_black=[
                "Maintain the e5 pawn",
                "Develop harmoniously",
                "Look for counterplay on the queenside"
            ],
            common_mistakes=[
                "Moving the same piece twice in the opening",
                "Neglecting development for pawn grabbing",
                "Leaving the king in the center too long"
            ],
            traps=italian_traps[:1],  # Fried Liver
            model_games=[]
        ),
        OpeningVariation(
            name="Two Knights Defense",
            eco="C55",
            moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"],
            key_ideas=[
                "Black challenges white's center immediately",
                "More aggressive than Bc5",
                "Leads to sharp tactical play"
            ],
            plans_for_white=[
                "Ng5 is the most aggressive, threatening Nxf7",
                "d3 for a quieter game",
                "Nc3 to develop naturally"
            ],
            plans_for_black=[
                "After Ng5, d5 is the main defense",
                "Be prepared for tactical complications",
                "Castle quickly when possible"
            ],
            common_mistakes=[
                "Not knowing the Fried Liver defense",
                "Panicking after Ng5",
                "Taking the e4 pawn too early"
            ],
            traps=italian_traps,
            model_games=[]
        ),
    ]
    
    OPENING_DATABASE["italian_game"] = OpeningFamily(
        name="Italian Game",
        eco_range="C50-C59",
        first_moves=["e4", "e5", "Nf3", "Nc6", "Bc4"],
        description="One of the oldest openings. White develops the bishop to c4, aiming at f7.",
        character="open",
        suitable_for=["beginners", "tactical players", "attacking players"],
        variations=italian_variations,
        introduction_message="Welcome to the Italian Game! This is one of the oldest and most instructive openings. Your bishop on c4 eyes the weak f7 pawn. Want to learn a deadly trap?",
        mastery_criteria={
            "know_main_line": True,
            "know_at_least_one_trap": True,
            "applied_in_games": 3,
            "correct_applications": 2
        }
    )
    
    # ==================== SICILIAN DEFENSE ====================
    sicilian_traps = [
        OpeningTrap(
            name="Siberian Trap",
            moves=["e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "Bb4", "e5", "Ne4"],
            trap_move="Qa5+",
            explanation="After Qg4, Black plays Qa5+! attacking the knight and threatening Qxg4. White loses material.",
            refutation="White should play Bd3 instead of e5, or be careful with Qg4.",
            fen_before_trap="r1bqk2r/pp1p1ppp/2n1pn2/4P3/1b1N4/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 7",
            fen_after_trap="r1bqk2r/pp1p1ppp/2n1p3/4P3/1b1Nn3/2N5/PPP2PPP/R1BQKB1R w KQkq - 1 8",
            victim_color="white",
            difficulty="intermediate"
        ),
    ]
    
    sicilian_variations = [
        OpeningVariation(
            name="Open Sicilian",
            eco="B20-B99",
            moves=["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4"],
            key_ideas=[
                "Asymmetrical pawn structure creates imbalance",
                "Black fights for the d5 square",
                "White often attacks on the kingside, Black on the queenside"
            ],
            plans_for_white=[
                "Castle and attack the kingside",
                "Control the d5 square",
                "f4-f5 pawn break"
            ],
            plans_for_black=[
                "Pressure the e4 pawn",
                "Queenside pawn majority attack",
                "Control the d5 outpost"
            ],
            common_mistakes=[
                "White: Pushing pawns without piece support",
                "Black: Neglecting king safety",
                "Both: Not understanding typical plans"
            ],
            traps=sicilian_traps,
            model_games=[]
        ),
        OpeningVariation(
            name="Najdorf Variation",
            eco="B90-B99",
            moves=["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"],
            key_ideas=[
                "a6 prepares b5 expansion",
                "Very flexible - Black can choose many setups",
                "Bobby Fischer's favorite"
            ],
            plans_for_white=[
                "Be3 and f3 (English Attack)",
                "Bg5 (classical)",
                "f4 (aggressive)"
            ],
            plans_for_black=[
                "e5 or e6 depending on white's setup",
                "b5 queenside expansion",
                "Piece pressure on e4"
            ],
            common_mistakes=[
                "Playing without a plan",
                "Not knowing the theory",
                "Mixing up move orders"
            ],
            traps=[],
            model_games=[]
        ),
    ]
    
    OPENING_DATABASE["sicilian_defense"] = OpeningFamily(
        name="Sicilian Defense",
        eco_range="B20-B99",
        first_moves=["e4", "c5"],
        description="The most popular response to e4. Creates asymmetrical, fighting chess.",
        character="semi-open",
        suitable_for=["intermediate", "advanced", "tactical players"],
        variations=sicilian_variations,
        introduction_message="The Sicilian Defense! The most popular and complex response to e4. Black immediately fights for the center with c5. Ready to enter the tactical battlefield?",
        mastery_criteria={
            "know_main_line": True,
            "know_at_least_one_variation": True,
            "applied_in_games": 5,
            "correct_applications": 3
        }
    )
    
    # ==================== QUEEN'S GAMBIT ====================
    qg_traps = [
        OpeningTrap(
            name="Elephant Trap",
            moves=["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Nbd7", "cxd5", "exd5", "Nxd5", "Nxd5", "Bxd8"],
            trap_move="Bb4+",
            explanation="After Bxd8, Black plays Bb4+! White must block, and then Kxd8 and Black has won the bishop.",
            refutation="White should not take on d5 with the knight. Play e3 instead.",
            fen_before_trap="r1bqkb1r/pppn1ppp/4pn2/3p2B1/2PP4/2N5/PP2PPPP/R2QKBNR w KQkq - 2 5",
            fen_after_trap="r1bBkb1r/pppn1ppp/8/3n4/2PP4/2N5/PP2PPPP/R2QKbNR b KQkq - 0 7",
            victim_color="white",
            difficulty="beginner"
        ),
    ]
    
    qg_variations = [
        OpeningVariation(
            name="Queen's Gambit Declined",
            eco="D30-D69",
            moves=["d4", "d5", "c4", "e6"],
            key_ideas=[
                "Black solidly defends d5",
                "Develops the dark-squared bishop",
                "Aims for a solid, positional game"
            ],
            plans_for_white=[
                "Build a strong center",
                "Develop pieces harmoniously",
                "Minority attack on the queenside"
            ],
            plans_for_black=[
                "Challenge the center with c5 or e5",
                "Develop the light-squared bishop",
                "Keep a solid structure"
            ],
            common_mistakes=[
                "White: Premature attacks",
                "Black: Passive play without counterplay"
            ],
            traps=qg_traps,
            model_games=[]
        ),
        OpeningVariation(
            name="Queen's Gambit Accepted",
            eco="D20-D29",
            moves=["d4", "d5", "c4", "dxc4"],
            key_ideas=[
                "Black accepts the gambit but should not hold the pawn",
                "Black aims to develop quickly",
                "The center becomes fluid"
            ],
            plans_for_white=[
                "Recapture the pawn with e3 and Bxc4",
                "Build a strong pawn center",
                "Develop rapidly"
            ],
            plans_for_black=[
                "Give back the pawn for development",
                "Challenge the center with e5 or c5",
                "Avoid holding the c4 pawn"
            ],
            common_mistakes=[
                "Black: Trying to hold the c4 pawn",
                "White: Rushing to recapture"
            ],
            traps=[],
            model_games=[]
        ),
    ]
    
    OPENING_DATABASE["queens_gambit"] = OpeningFamily(
        name="Queen's Gambit",
        eco_range="D06-D69",
        first_moves=["d4", "d5", "c4"],
        description="White offers a pawn to gain central control. Not a real gambit - Black rarely keeps the pawn.",
        character="closed",
        suitable_for=["positional players", "beginners", "intermediate"],
        variations=qg_variations,
        introduction_message="The Queen's Gambit! A classic opening where White offers the c4 pawn. Will you accept or decline? There's a famous trap waiting...",
        mastery_criteria={
            "know_main_line": True,
            "know_at_least_one_trap": True,
            "applied_in_games": 3,
            "correct_applications": 2
        }
    )
    
    # ==================== LONDON SYSTEM ====================
    london_variations = [
        OpeningVariation(
            name="London System",
            eco="D00",
            moves=["d4", "d5", "Bf4"],
            key_ideas=[
                "Solid, easy to learn setup",
                "Bishop develops before e3 locks it in",
                "Flexible - works against almost anything"
            ],
            plans_for_white=[
                "Develop: Bf4, e3, Nf3, Bd3, c3",
                "Castle kingside",
                "Push e4 when ready"
            ],
            plans_for_black=[
                "Challenge the bishop with Bd6 or c5",
                "Fight for the center",
                "Don't let White play e4 for free"
            ],
            common_mistakes=[
                "White: Playing e3 before Bf4",
                "White: Pushing pawns without development",
                "Black: Not challenging the center"
            ],
            traps=[],
            model_games=[]
        ),
    ]
    
    OPENING_DATABASE["london_system"] = OpeningFamily(
        name="London System",
        eco_range="D00",
        first_moves=["d4", "Bf4"],
        description="A solid, reliable system. Easy to learn, hard to refute. Perfect for building a repertoire.",
        character="closed",
        suitable_for=["beginners", "solid players", "those who want simple plans"],
        variations=london_variations,
        introduction_message="The London System! A reliable, solid opening. The bishop goes to f4 BEFORE you play e3. Once you know this setup, you can play it against almost anything!",
        mastery_criteria={
            "know_main_line": True,
            "applied_in_games": 3,
            "correct_applications": 2
        }
    )
    
    # ==================== CARO-KANN ====================
    carokann_traps = [
        OpeningTrap(
            name="Caro-Kann Smothered Mate",
            moves=["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Nf6", "Qe2", "Nbd7", "Nd6#"],
            trap_move="Nd6#",
            explanation="Smothered mate! The knight delivers checkmate because the king is blocked by its own pieces.",
            refutation="Black should play Nxe4 on move 5 or not play Nbd7.",
            fen_before_trap="r1bqkb1r/pp1npppp/2p2n2/8/3PN3/8/PPP1QPPP/R1B1KBNR w KQkq - 2 6",
            fen_after_trap="r1bqkb1r/pp1npppp/2pN1n2/8/3P4/8/PPP1QPPP/R1B1KBNR b KQkq - 3 6",
            victim_color="black",
            difficulty="beginner"
        ),
    ]
    
    carokann_variations = [
        OpeningVariation(
            name="Caro-Kann Main Line",
            eco="B12",
            moves=["e4", "c6", "d4", "d5"],
            key_ideas=[
                "Solid pawn structure for Black",
                "The light-squared bishop isn't blocked",
                "Black plays for the long game"
            ],
            plans_for_white=[
                "Advance: push e5 or play Nc3",
                "Attack the kingside",
                "Use space advantage"
            ],
            plans_for_black=[
                "Develop pieces harmoniously",
                "Challenge center with c5 or e6",
                "Trade pieces to reach endgame"
            ],
            common_mistakes=[
                "Black: Playing too passively",
                "White: Overextending"
            ],
            traps=carokann_traps,
            model_games=[]
        ),
    ]
    
    OPENING_DATABASE["caro_kann"] = OpeningFamily(
        name="Caro-Kann Defense",
        eco_range="B10-B19",
        first_moves=["e4", "c6"],
        description="A solid defense where Black prepares d5 while keeping the light-squared bishop active.",
        character="semi-open",
        suitable_for=["solid players", "positional players", "beginners"],
        variations=carokann_variations,
        introduction_message="The Caro-Kann Defense! Black prepares d5 with c6 first. Very solid, but watch out for a deadly smothered mate trap!",
        mastery_criteria={
            "know_main_line": True,
            "know_the_trap": True,
            "applied_in_games": 3,
            "correct_applications": 2
        }
    )


# Initialize the database
_build_opening_database()


# ============================================
# OPENING DETECTION
# ============================================

def detect_opening_from_moves(moves: List[str]) -> Optional[Dict]:
    """
    Detect which opening family we're in based on moves played.
    
    Returns:
        Dict with opening info or None if not recognized
    """
    if not moves:
        return None
    
    moves_str = " ".join(moves[:10]).lower()  # First 10 moves
    
    # Check each opening family
    for key, opening in OPENING_DATABASE.items():
        first_moves_str = " ".join(opening.first_moves).lower()
        
        # Check if the game moves match this opening's first moves
        if moves_str.startswith(first_moves_str) or _moves_match_opening(moves, opening):
            # Find the specific variation
            variation = _find_variation(moves, opening)
            
            return {
                "opening_key": key,
                "opening_name": opening.name,
                "variation": variation.name if variation else None,
                "description": opening.description,
                "character": opening.character,
                "introduction": opening.introduction_message,
                "has_traps": len(opening.variations[0].traps) > 0 if opening.variations else False,
                "trap_names": [t.name for v in opening.variations for t in v.traps]
            }
    
    return None


def _moves_match_opening(game_moves: List[str], opening: OpeningFamily) -> bool:
    """Check if game moves match an opening's characteristic moves."""
    game_moves_lower = [m.lower() for m in game_moves[:len(opening.first_moves)]]
    opening_moves_lower = [m.lower() for m in opening.first_moves]
    
    # Exact match
    if game_moves_lower == opening_moves_lower[:len(game_moves_lower)]:
        return True
    
    # Check variations
    for variation in opening.variations:
        var_moves_lower = [m.lower() for m in variation.moves[:len(game_moves)]]
        if game_moves_lower == var_moves_lower:
            return True
    
    return False


def _find_variation(game_moves: List[str], opening: OpeningFamily) -> Optional[OpeningVariation]:
    """Find the specific variation within an opening family."""
    game_moves_lower = [m.lower() for m in game_moves]
    
    best_match = None
    best_match_length = 0
    
    for variation in opening.variations:
        var_moves_lower = [m.lower() for m in variation.moves]
        match_length = 0
        
        for i, (gm, vm) in enumerate(zip(game_moves_lower, var_moves_lower)):
            if gm == vm:
                match_length = i + 1
            else:
                break
        
        if match_length > best_match_length:
            best_match = variation
            best_match_length = match_length
    
    return best_match


def detect_opening_from_fen(fen: str) -> Optional[Dict]:
    """
    Detect opening from a FEN position.
    
    This is harder - we'd need a position database.
    For now, returns None (use move-based detection).
    """
    # TODO: Implement position-based opening detection
    return None


# ============================================
# TEACHING FLOW
# ============================================

class OpeningTeacher:
    """
    Manages the teaching flow for an opening.
    
    Can:
    - Introduce an opening
    - Teach the main line move by move
    - Show traps interactively
    - Quiz the user
    """
    
    def __init__(self, opening_key: str, user_progress: Optional[UserOpeningProgress] = None):
        self.opening = OPENING_DATABASE.get(opening_key)
        self.user_progress = user_progress
        self.current_mode = TeachingMode.NONE
        self.current_variation = None
        self.current_trap = None
        self.teaching_move_index = 0
    
    def get_introduction(self) -> Dict:
        """Get the introduction message for this opening."""
        if not self.opening:
            return {"error": "Opening not found"}
        
        # Build teaching options
        options = ["Learn the main line"]
        
        if self.opening.variations and self.opening.variations[0].traps:
            trap_names = [t.name for t in self.opening.variations[0].traps]
            options.append(f"See a trap ({trap_names[0]})")
        
        options.append("Just play - I'll figure it out")
        
        return {
            "opening_name": self.opening.name,
            "message": self.opening.introduction_message,
            "options": options,
            "character": self.opening.character,
            "suitable_for": self.opening.suitable_for,
            "has_learned_before": self.user_progress is not None and self.user_progress.mastery_level != MasteryLevel.UNKNOWN
        }
    
    def start_main_line_teaching(self, variation_index: int = 0) -> Dict:
        """Start teaching the main line."""
        if not self.opening or not self.opening.variations:
            return {"error": "No variations available"}
        
        self.current_mode = TeachingMode.MAIN_LINE
        self.current_variation = self.opening.variations[min(variation_index, len(self.opening.variations) - 1)]
        self.teaching_move_index = 0
        
        return {
            "mode": "main_line",
            "variation_name": self.current_variation.name,
            "total_moves": len(self.current_variation.moves),
            "key_ideas": self.current_variation.key_ideas,
            "first_instruction": self._get_next_teaching_move()
        }
    
    def start_trap_teaching(self, trap_index: int = 0) -> Dict:
        """Start teaching a trap."""
        if not self.opening:
            return {"error": "Opening not found"}
        
        # Find traps across all variations
        all_traps = []
        for var in self.opening.variations:
            all_traps.extend(var.traps)
        
        if not all_traps:
            return {"error": "No traps available for this opening"}
        
        self.current_mode = TeachingMode.TRAP
        self.current_trap = all_traps[min(trap_index, len(all_traps) - 1)]
        self.teaching_move_index = 0
        
        return {
            "mode": "trap",
            "trap_name": self.current_trap.name,
            "explanation": self.current_trap.explanation,
            "victim_color": self.current_trap.victim_color,
            "difficulty": self.current_trap.difficulty,
            "setup_fen": self.current_trap.fen_before_trap,
            "total_moves": len(self.current_trap.moves),
            "first_instruction": self._get_next_trap_move()
        }
    
    def _get_next_teaching_move(self) -> Optional[Dict]:
        """Get the next move to teach in main line."""
        if not self.current_variation:
            return None
        
        if self.teaching_move_index >= len(self.current_variation.moves):
            return {
                "complete": True,
                "message": f"Well done! You've learned the main line of the {self.current_variation.name}!",
                "key_ideas": self.current_variation.key_ideas
            }
        
        move = self.current_variation.moves[self.teaching_move_index]
        is_white_move = self.teaching_move_index % 2 == 0
        move_number = (self.teaching_move_index // 2) + 1
        
        instruction = {
            "move": move,
            "move_number": move_number,
            "is_white_move": is_white_move,
            "instruction": f"{'White' if is_white_move else 'Black'} plays {move}",
            "remaining": len(self.current_variation.moves) - self.teaching_move_index - 1
        }
        
        self.teaching_move_index += 1
        return instruction
    
    def _get_next_trap_move(self) -> Optional[Dict]:
        """Get the next move in the trap sequence."""
        if not self.current_trap:
            return None
        
        if self.teaching_move_index >= len(self.current_trap.moves):
            return {
                "complete": True,
                "trap_move": self.current_trap.trap_move,
                "message": f"The trap move is {self.current_trap.trap_move}! {self.current_trap.explanation}",
                "refutation": self.current_trap.refutation
            }
        
        move = self.current_trap.moves[self.teaching_move_index]
        is_trap_move = move == self.current_trap.trap_move
        is_white_move = self.teaching_move_index % 2 == 0
        
        instruction = {
            "move": move,
            "is_white_move": is_white_move,
            "is_trap_move": is_trap_move,
            "instruction": f"Play {move}" if not is_trap_move else f"NOW! {move} - the trap!",
            "remaining": len(self.current_trap.moves) - self.teaching_move_index - 1
        }
        
        self.teaching_move_index += 1
        return instruction
    
    def get_quiz_question(self) -> Dict:
        """Generate a quiz question about this opening."""
        if not self.opening:
            return {"error": "Opening not found"}
        
        self.current_mode = TeachingMode.QUIZ
        
        # Quiz types: main line moves, trap moves, key ideas
        import random
        quiz_type = random.choice(["move", "trap", "idea"])
        
        if quiz_type == "move" and self.opening.variations:
            var = random.choice(self.opening.variations)
            if len(var.moves) >= 3:
                move_idx = random.randint(0, min(4, len(var.moves) - 1))
                return {
                    "type": "move",
                    "question": f"In the {var.name}, what is move {(move_idx // 2) + 1} for {'White' if move_idx % 2 == 0 else 'Black'}?",
                    "answer": var.moves[move_idx],
                    "hint": f"Previous move was {var.moves[move_idx - 1]}" if move_idx > 0 else "First move"
                }
        
        if quiz_type == "trap":
            all_traps = [t for v in self.opening.variations for t in v.traps]
            if all_traps:
                trap = random.choice(all_traps)
                return {
                    "type": "trap",
                    "question": f"What is the key move in the {trap.name}?",
                    "answer": trap.trap_move,
                    "hint": trap.explanation[:50] + "..."
                }
        
        # Default to key idea quiz
        if self.opening.variations:
            var = self.opening.variations[0]
            if var.key_ideas:
                return {
                    "type": "idea",
                    "question": f"Name a key idea in the {self.opening.name}",
                    "answers": var.key_ideas,
                    "hint": f"Think about what {self.opening.character} positions need"
                }
        
        return {"error": "Could not generate quiz question"}


# ============================================
# USER PROGRESS MANAGEMENT
# ============================================

async def get_user_opening_progress(db, user_id: str, opening_name: str) -> Optional[UserOpeningProgress]:
    """Get user's progress for a specific opening."""
    doc = await db.user_opening_progress.find_one({
        "user_id": user_id,
        "opening_name": opening_name
    })
    
    if not doc:
        return None
    
    return UserOpeningProgress(
        user_id=doc["user_id"],
        opening_name=doc["opening_name"],
        mastery_level=MasteryLevel(doc.get("mastery_level", "unknown")),
        introduced_at=doc.get("introduced_at"),
        last_practiced_at=doc.get("last_practiced_at"),
        times_practiced=doc.get("times_practiced", 0),
        times_applied_in_games=doc.get("times_applied_in_games", 0),
        correct_applications=doc.get("correct_applications", 0),
        traps_learned=doc.get("traps_learned", []),
        variations_learned=doc.get("variations_learned", []),
        quiz_scores=doc.get("quiz_scores", []),
        notes=doc.get("notes", "")
    )


async def update_user_opening_progress(db, progress: UserOpeningProgress):
    """Update user's progress for an opening."""
    await db.user_opening_progress.update_one(
        {"user_id": progress.user_id, "opening_name": progress.opening_name},
        {"$set": {
            "mastery_level": progress.mastery_level.value,
            "introduced_at": progress.introduced_at,
            "last_practiced_at": progress.last_practiced_at,
            "times_practiced": progress.times_practiced,
            "times_applied_in_games": progress.times_applied_in_games,
            "correct_applications": progress.correct_applications,
            "traps_learned": progress.traps_learned,
            "variations_learned": progress.variations_learned,
            "quiz_scores": progress.quiz_scores,
            "notes": progress.notes
        }},
        upsert=True
    )


async def get_all_user_openings(db, user_id: str) -> List[Dict]:
    """Get all openings a user has learned or started learning."""
    cursor = db.user_opening_progress.find({"user_id": user_id})
    openings = []
    
    async for doc in cursor:
        opening_key = doc["opening_name"].lower().replace(" ", "_")
        opening_data = OPENING_DATABASE.get(opening_key)
        
        openings.append({
            "opening_name": doc["opening_name"],
            "mastery_level": doc.get("mastery_level", "unknown"),
            "times_practiced": doc.get("times_practiced", 0),
            "times_applied": doc.get("times_applied_in_games", 0),
            "traps_learned": doc.get("traps_learned", []),
            "character": opening_data.character if opening_data else "unknown"
        })
    
    return openings


async def check_opening_in_real_game(db, user_id: str, game_moves: List[str]) -> Optional[Dict]:
    """
    Check if the user applied a learned opening in a real game.
    
    This is called during game analysis to track if the user
    is applying what they learned.
    """
    # Detect what opening was played
    opening_info = detect_opening_from_moves(game_moves)
    if not opening_info:
        return None
    
    # Check if user has learned this opening
    progress = await get_user_opening_progress(db, user_id, opening_info["opening_name"])
    if not progress or progress.mastery_level == MasteryLevel.UNKNOWN:
        return None  # User hasn't learned this opening yet
    
    # User played an opening they've learned!
    # Update their progress
    progress.times_applied_in_games += 1
    progress.last_practiced_at = datetime.now(timezone.utc)
    
    # Check if they played it correctly (simplified check)
    opening_data = OPENING_DATABASE.get(opening_info["opening_key"])
    if opening_data:
        expected_moves = opening_data.first_moves
        played_correct = all(
            gm.lower() == em.lower() 
            for gm, em in zip(game_moves[:len(expected_moves)], expected_moves)
        )
        
        if played_correct:
            progress.correct_applications += 1
            
            # Check if they've mastered it
            criteria = opening_data.mastery_criteria
            if (progress.correct_applications >= criteria.get("correct_applications", 2) and
                progress.times_applied_in_games >= criteria.get("applied_in_games", 3)):
                progress.mastery_level = MasteryLevel.MASTERED
    
    await update_user_opening_progress(db, progress)
    
    return {
        "opening_detected": opening_info["opening_name"],
        "was_learned": True,
        "played_correctly": played_correct,
        "new_mastery_level": progress.mastery_level.value,
        "times_applied": progress.times_applied_in_games,
        "correct_applications": progress.correct_applications
    }


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def get_available_openings() -> List[Dict]:
    """Get list of all available openings to learn."""
    return [
        {
            "key": key,
            "name": opening.name,
            "description": opening.description,
            "character": opening.character,
            "suitable_for": opening.suitable_for,
            "num_traps": sum(len(v.traps) for v in opening.variations),
            "num_variations": len(opening.variations)
        }
        for key, opening in OPENING_DATABASE.items()
    ]


def get_opening_details(opening_key: str) -> Optional[Dict]:
    """Get full details of an opening."""
    opening = OPENING_DATABASE.get(opening_key)
    if not opening:
        return None
    
    return {
        "name": opening.name,
        "eco_range": opening.eco_range,
        "description": opening.description,
        "character": opening.character,
        "suitable_for": opening.suitable_for,
        "first_moves": opening.first_moves,
        "variations": [
            {
                "name": v.name,
                "eco": v.eco,
                "moves": v.moves,
                "key_ideas": v.key_ideas,
                "traps": [{"name": t.name, "difficulty": t.difficulty} for t in v.traps]
            }
            for v in opening.variations
        ],
        "introduction": opening.introduction_message
    }
