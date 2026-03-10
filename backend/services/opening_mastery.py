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
        OpeningTrap(
            name="Blackburne Shilling Gambit",
            moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4", "Nxe5"],
            trap_move="Nxe5",
            explanation="After Nxe5?, Black plays Qg5! attacking g2 and e5. If Nxf7, Qxg2 threatens mate!",
            refutation="Don't take on e5! Play Nxd4 or c3 to kick the knight away.",
            fen_before_trap="r1bqkbnr/pppp1ppp/8/4p3/2BnP3/5N2/PPPP1PPP/RNBQK2R w KQkq - 3 4",
            fen_after_trap="r1bqkbnr/pppp1ppp/8/4N3/2BnP3/8/PPPP1PPP/RNBQK2R b KQkq - 0 4",
            victim_color="white",
            difficulty="beginner"
        ),
        OpeningTrap(
            name="Traxler Counterattack",
            moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "Bc5", "Nxf7", "Bxf2+"],
            trap_move="Bxf2+",
            explanation="Black ignores the rook! After Kf1 (or Kxf2), Qe7 and Black's attack is ferocious despite being down material.",
            refutation="White should not take on f7. Play d4 or d3 instead for a safe advantage.",
            fen_before_trap="r1bqk2r/pppp1ppp/2n2n2/2b1p1N1/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 4 5",
            fen_after_trap="r1bqk2r/pppp1Npp/2n2n2/2b1p3/2B1P3/8/PPPP1bPP/RNBQK2R w KQkq - 0 6",
            victim_color="white",
            difficulty="advanced"
        ),
        OpeningTrap(
            name="Jerome Gambit",
            moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "Bxf7+", "Kxf7", "Nxe5+"],
            trap_move="Nxe5+",
            explanation="White sacrifices BOTH minor pieces! The king is exposed and Qh5+ creates chaos.",
            refutation="After Nxe5+, play Ke8! (not Nxe5). Black is winning but must defend carefully.",
            fen_before_trap="r1bqk1nr/pppp1Bpp/2n5/2b1p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 4",
            fen_after_trap="r1bqk1nr/pppp2pp/2n5/2b1N3/4P3/8/PPPP1PPP/RNBQK2R b KQkq - 0 5",
            victim_color="black",
            difficulty="advanced"
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
            traps=italian_traps[:2],  # Fried Liver, Legal's Mate for Giuoco Piano
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
            traps=italian_traps[2:],  # Blackburne Shilling, Traxler, Jerome for Two Knights
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
        OpeningTrap(
            name="Magnus Smith Trap",
            moves=["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "g6", "Bc4", "Bg7", "Nxc6"],
            trap_move="bxc6",
            explanation="After bxc6, White plays Bxf7+! Kxf7 e5! opens devastating lines against Black's king.",
            refutation="Black should play Nbd7 before developing the bishop to g7.",
            fen_before_trap="rn1qk2r/pp2ppbp/3p1np1/2N5/2B1P3/2N5/PPP2PPP/R1BQK2R b KQkq - 0 8",
            fen_after_trap="rn1qk2r/pp2ppbp/2pp1np1/8/2B1P3/2N5/PPP2PPP/R1BQK2R w KQkq - 0 9",
            victim_color="black",
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
    london_traps = [
        OpeningTrap(
            name="London System Trap",
            moves=["d4", "d5", "Bf4", "c5", "e3", "Nc6", "c3", "Qb6", "Qb3", "c4", "Qc2"],
            trap_move="Qc2",
            explanation="White threatens Qxh7! The h7 pawn is undefended because the bishop on f4 covers it.",
            refutation="Black should play g6 early or develop the kingside faster.",
            fen_before_trap="r1b1kbnr/pp2pppp/1qn5/3p4/2pP1B2/2P1P3/PP3PPP/RN1QKBNR w KQkq - 0 7",
            fen_after_trap="r1b1kbnr/pp2pppp/1qn5/3p4/2pP1B2/2P1P3/PPQ2PPP/RN2KBNR b KQkq - 1 7",
            victim_color="black",
            difficulty="beginner"
        ),
        OpeningTrap(
            name="London System Greek Gift",
            moves=["d4", "d5", "Bf4", "Nf6", "e3", "e6", "Nf3", "Bd6", "Bg3", "O-O", "Bd3", "Nc6", "Nbd2", "Nb4"],
            trap_move="Bxh7+",
            explanation="The classic Greek Gift sacrifice! Bxh7+ Kxh7 Ng5+ leads to a winning attack.",
            refutation="Black should not castle into the attack. Play h6 first or develop differently.",
            fen_before_trap="r1bq1rk1/ppp2ppp/3bpn2/3p4/3P4/3BPN2/PPP2PPP/RN1QK2R w KQ - 5 8",
            fen_after_trap="r1bq1rk1/ppp2pBp/3bpn2/3p4/3P4/4PN2/PPP2PPP/RN1QK2R b KQ - 0 8",
            victim_color="black",
            difficulty="intermediate"
        ),
    ]
    
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
            traps=london_traps,
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
        OpeningTrap(
            name="Caro-Kann Fantasy Trap",
            moves=["e4", "c6", "d4", "d5", "f3", "dxe4", "fxe4", "e5", "Nf3", "exd4", "Bc4"],
            trap_move="Bc4",
            explanation="After Bc4, White threatens Bxf7+ and has a powerful attack. Black's center collapses.",
            refutation="Black should not play e5 in the Fantasy Variation - it opens too many lines.",
            fen_before_trap="rnbqkbnr/pp3ppp/2p5/8/2BpP3/5N2/PPP3PP/RNBQK2R b KQkq - 1 6",
            fen_after_trap="rnbqkbnr/pp3ppp/2p5/8/2BpP3/5N2/PPP3PP/RNBQK2R b KQkq - 1 6",
            victim_color="black",
            difficulty="intermediate"
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
    
    # ==================== FRENCH DEFENSE ====================
    french_traps = [
        OpeningTrap(
            name="French Defense Winawer Poisoned Pawn",
            moves=["e4", "e6", "d4", "d5", "Nc3", "Bb4", "e5", "c5", "a3", "Bxc3+", "bxc3", "Ne7", "Qg4", "Qc7", "Qxg7", "Rg8", "Qxh7", "cxd4"],
            trap_move="Qxg7",
            explanation="White grabs the g7 pawn, but Black gets tremendous counterplay with cxd4, opening lines against White's weakened center.",
            refutation="White should avoid being too greedy. Play Nf3 for safer development.",
            fen_before_trap="r1b1k1nr/ppq1ppbp/4p3/2ppP3/3P2Q1/P1P5/2P2PPP/R1B1KBNR w KQkq - 0 9",
            fen_after_trap="r1b1k1nr/ppq1pp1p/4p3/2ppP1Q1/3P4/P1P5/2P2PPP/R1B1KBNR b KQkq - 0 9",
            victim_color="white",
            difficulty="advanced"
        ),
    ]
    
    french_variations = [
        OpeningVariation(
            name="French Defense Classical",
            eco="C11",
            moves=["e4", "e6", "d4", "d5"],
            key_ideas=[
                "Black creates a solid pawn chain",
                "The light-squared bishop is blocked (French bishop problem)",
                "Black counterattacks White's center with c5"
            ],
            plans_for_white=[
                "Push e5 to gain space",
                "Attack the kingside with f4-f5",
                "Target the weak d6 square"
            ],
            plans_for_black=[
                "Play c5 to challenge the center",
                "Develop the knight to c6, then e7-f5",
                "Solve the bishop problem with Bd7-e8-g6 or b6-Ba6"
            ],
            common_mistakes=[
                "Black: Leaving the bad bishop passive",
                "White: Overextending the e-pawn"
            ],
            traps=french_traps,
            model_games=[]
        ),
    ]
    
    OPENING_DATABASE["french_defense"] = OpeningFamily(
        name="French Defense",
        eco_range="C00-C19",
        first_moves=["e4", "e6"],
        description="A solid, counterattacking defense where Black builds a strong pawn chain but must solve the 'French bishop' problem.",
        character="semi-open",
        suitable_for=["strategic players", "counterattackers", "intermediate players"],
        variations=french_variations,
        introduction_message="The French Defense! Solid like a fortress. You'll build a strong center with d5 and counterattack with c5. Just remember - your light-squared bishop needs a plan!",
        mastery_criteria={
            "know_main_line": True,
            "know_c5_break": True,
            "applied_in_games": 3,
            "correct_applications": 2
        }
    )
    
    # ==================== SCANDINAVIAN DEFENSE ====================
    scandinavian_traps = [
        OpeningTrap(
            name="Scandinavian Queen Trap",
            moves=["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "e5", "dxe5"],
            trap_move="dxe5",
            explanation="After dxe5, Black's queen is exposed. White develops with tempo and Black struggles to find safe squares.",
            refutation="Black should not play e5 - play Nf6 or c6 for solid development.",
            fen_before_trap="rnb1kbnr/ppp2ppp/8/q3P3/8/2N5/PPP2PPP/R1BQKBNR b KQkq - 0 5",
            fen_after_trap="rnb1kbnr/ppp2ppp/8/q3P3/8/2N5/PPP2PPP/R1BQKBNR b KQkq - 0 5",
            victim_color="black",
            difficulty="beginner"
        ),
    ]
    
    scandinavian_variations = [
        OpeningVariation(
            name="Scandinavian Main Line",
            eco="B01",
            moves=["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5"],
            key_ideas=[
                "Black immediately challenges White's center",
                "The queen comes out early (unusual but playable)",
                "Black develops quickly: Nf6, c6, Bf5"
            ],
            plans_for_white=[
                "Develop with tempo against the queen",
                "Control the center with d4",
                "Castle and attack"
            ],
            plans_for_black=[
                "Keep the queen safe while developing",
                "Play c6, Bf5, e6 for solid setup",
                "Don't let the queen get trapped!"
            ],
            common_mistakes=[
                "Black: Moving queen too much",
                "Black: Playing e5 which weakens d5",
                "White: Overchasing the queen"
            ],
            traps=scandinavian_traps,
            model_games=[]
        ),
    ]
    
    OPENING_DATABASE["scandinavian_defense"] = OpeningFamily(
        name="Scandinavian Defense",
        eco_range="B01",
        first_moves=["e4", "d5"],
        description="A provocative defense where Black immediately challenges White's e-pawn, bringing the queen out early.",
        character="open",
        suitable_for=["aggressive players", "surprise weapon", "beginners"],
        variations=scandinavian_variations,
        introduction_message="The Scandinavian Defense! Bold choice - you're bringing your queen out early. Keep her safe while you develop!",
        mastery_criteria={
            "know_main_line": True,
            "know_queen_safety": True,
            "applied_in_games": 3,
            "correct_applications": 2
        }
    )
    
    # ==================== RUY LOPEZ ====================
    ruylopez_traps = [
        OpeningTrap(
            name="Noah's Ark Trap",
            moves=["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "d6", "d4", "b5", "Bb3", "Nxd4", "Nxd4", "exd4", "Qxd4", "c5", "Qd5", "Be6", "Qc6+", "Bd7", "Qd5", "c4"],
            trap_move="c4",
            explanation="The bishop on b3 is trapped! After c4, the bishop retreats to a4, then b4 and c3 close the cage.",
            refutation="White should avoid Qxd4 - play c3 instead to maintain the center.",
            fen_before_trap="r2qkbnr/3b1ppp/p2p4/1p1Q4/2p1P3/1B6/PPP2PPP/RNB1K2R w KQkq - 0 12",
            fen_after_trap="r2qkbnr/3b1ppp/p2p4/1p1Q4/2p1P3/1B6/PPP2PPP/RNB1K2R w KQkq - 0 12",
            victim_color="white",
            difficulty="intermediate"
        ),
        OpeningTrap(
            name="Fishing Pole Trap",
            moves=["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6", "O-O", "Ng4", "h3", "h5", "hxg4", "hxg4"],
            trap_move="hxg4",
            explanation="After hxg4 hxg4, Black's h-file is open! Qh4 threatens mate. The attack is devastating.",
            refutation="Don't take the knight with the h-pawn - play d3 or Be2 instead.",
            fen_before_trap="r1bqkb1r/pppp1pp1/2n5/1B2p3/4P1p1/5N2/PPPP1PP1/RNBQ1RK1 w kq - 0 7",
            fen_after_trap="r1bqkb1r/pppp1pp1/2n5/1B2p3/4P1p1/5N2/PPPP1PP1/RNBQ1RK1 w kq - 0 7",
            victim_color="white",
            difficulty="intermediate"
        ),
        OpeningTrap(
            name="Mortimer Trap",
            moves=["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6", "d3", "Ne7", "Bxc6", "dxc6", "Nxe5"],
            trap_move="dxc6",
            explanation="After Bxc6?? dxc6, White thinks they're winning a piece with Nxe5, but Nxe4! wins material since dxe4 allows Qxd1+!",
            refutation="White should not take on c6. Play Nc3 or O-O instead - Ne7 is a signal of the trap.",
            fen_before_trap="r1bqkb1r/ppppnppp/2B2n2/4p3/4P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 0 6",
            fen_after_trap="r1bqkb1r/ppp1nppp/2p2n2/4p3/4P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 0 7",
            victim_color="white",
            difficulty="intermediate"
        ),
    ]
    
    ruylopez_variations = [
        OpeningVariation(
            name="Ruy Lopez Morphy Defense",
            eco="C65",
            moves=["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4"],
            key_ideas=[
                "White puts pressure on Black's center via the c6 knight",
                "The bishop retreat to a4 maintains tension",
                "Black must decide how to defend the e5 pawn"
            ],
            plans_for_white=[
                "Castle and play d4 to open the center",
                "Build up with c3, Re1, and Nbd2",
                "Launch a kingside attack in the middlegame"
            ],
            plans_for_black=[
                "Play d6 or Nf6 to solidify the center",
                "Counter with b5 to push the bishop back",
                "Consider the Marshall Attack for aggressive play"
            ],
            common_mistakes=[
                "Black: Playing Nxe4 too early (trappy!)",
                "White: Being too greedy with pawns"
            ],
            traps=ruylopez_traps,
            model_games=[]
        ),
    ]
    
    OPENING_DATABASE["ruy_lopez"] = OpeningFamily(
        name="Ruy Lopez",
        eco_range="C60-C99",
        first_moves=["e4", "e5", "Nf3", "Nc6", "Bb5"],
        description="The 'Spanish Game' - one of the oldest and most respected openings. Rich in strategy and theory.",
        character="open",
        suitable_for=["strategic players", "serious improvers", "intermediate to advanced"],
        variations=ruylopez_variations,
        introduction_message="The Ruy Lopez! A classic opening played by world champions for centuries. Let's explore its rich strategies and sneaky traps!",
        mastery_criteria={
            "know_main_line": True,
            "know_morphy_defense": True,
            "applied_in_games": 5,
            "correct_applications": 3
        }
    )
    
    # ==================== PHILIDOR DEFENSE ====================
    philidor_traps = [
        OpeningTrap(
            name="Philidor Defense Trap",
            moves=["e4", "e5", "Nf3", "d6", "d4", "Nd7", "Bc4", "Be7", "dxe5", "dxe5", "Qd5"],
            trap_move="Qd5",
            explanation="Qd5! attacks f7 and e5 simultaneously. Black cannot defend both.",
            refutation="Black should play Nxe5 instead of dxe5, or develop Nf6 instead of Nd7.",
            fen_before_trap="r1bqk1nr/pppnbppp/8/4p3/2B1P3/5N2/PPP2PPP/RNBQK2R w KQkq - 0 6",
            fen_after_trap="r1bqk1nr/pppnbppp/8/3Qp3/2B1P3/5N2/PPP2PPP/RNB1K2R b KQkq - 1 6",
            victim_color="black",
            difficulty="beginner"
        ),
        OpeningTrap(
            name="Legal's Mate",
            moves=["e4", "e5", "Nf3", "d6", "Bc4", "Bg4", "Nc3", "g6", "Nxe5", "Bxd1", "Bxf7+", "Ke7", "Nd5#"],
            trap_move="Nxe5",
            explanation="White sacrifices the queen! After Bxd1, Bxf7+ Ke7, Nd5# is checkmate.",
            refutation="Black should not capture the queen - play dxe5 instead.",
            fen_before_trap="rn1qkbnr/ppp2p1p/3p2p1/4p3/2B1P1b1/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 5",
            fen_after_trap="rn1qkbnr/ppp2p1p/3p2p1/4N3/2B1P1b1/2N5/PPPP1PPP/R1BQK2R b KQkq - 0 5",
            victim_color="black",
            difficulty="intermediate"
        ),
    ]
    
    philidor_variations = [
        OpeningVariation(
            name="Philidor Defense",
            eco="C41",
            moves=["e4", "e5", "Nf3", "d6"],
            key_ideas=[
                "Black solidly defends e5 with d6",
                "More passive than Nc6 but very solid",
                "Black aims for slow, strategic play"
            ],
            plans_for_white=[
                "Play d4 to challenge the center",
                "Develop Bc4 targeting f7",
                "Castle and build pressure"
            ],
            plans_for_black=[
                "Develop Nf6 and Be7",
                "Castle kingside quickly",
                "Look for c6 and d5 break later"
            ],
            common_mistakes=[
                "Black: Playing Nd7 blocking the bishop",
                "Black: Capturing dxe5 allowing Qd5 fork"
            ],
            traps=philidor_traps,
            model_games=[]
        ),
    ]
    
    OPENING_DATABASE["philidor_defense"] = OpeningFamily(
        name="Philidor Defense",
        eco_range="C41",
        first_moves=["e4", "e5", "Nf3", "d6"],
        description="A solid but passive defense. Named after the legendary François-André Danican Philidor.",
        character="semi-open",
        suitable_for=["solid players", "defensive players", "beginners"],
        variations=philidor_variations,
        introduction_message="The Philidor Defense! Solid and reliable, but watch out for the deadly Legal's Mate trap!",
        mastery_criteria={
            "know_main_line": True,
            "know_legals_mate": True,
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
    
    IMPORTANT: Only detects when we have enough characteristic moves.
    
    Detection requirements:
    - Italian Game: e4 e5 Nf3 Nc6 Bc4 (5 moves)
    - Queen's Gambit: d4 d5 c4 (3 moves)
    - London System: d4 [any] Bf4 (3 moves, White's 2nd must be Bf4)
    - Sicilian: e4 c5 (2 moves)
    - Caro-Kann: e4 c6 (2 moves)
    
    Returns:
        Dict with opening info or None if not recognized yet
    """
    if not moves:
        return None
    
    # Minimum moves to start detection
    if len(moves) < 2:
        return None
    
    moves_lower = [m.lower() for m in moves]
    
    # Manual priority-based detection for accuracy
    # Check most specific openings first
    
    # Italian Game: e4 e5 Nf3 Nc6 Bc4
    if len(moves_lower) >= 5:
        if moves_lower[:5] == ["e4", "e5", "nf3", "nc6", "bc4"]:
            return _build_opening_result("italian_game", moves)
        # Two Knights: e4 e5 Nf3 Nc6 Bc4 Nf6
        if len(moves_lower) >= 6 and moves_lower[:6] == ["e4", "e5", "nf3", "nc6", "bc4", "nf6"]:
            return _build_opening_result("italian_game", moves, "Two Knights Defense")
    
    # Queen's Gambit: d4 d5 c4
    if len(moves_lower) >= 3:
        if moves_lower[:3] == ["d4", "d5", "c4"]:
            return _build_opening_result("queens_gambit", moves)
    
    # London System: d4 [any] Bf4 (White's 2nd move must be Bf4)
    if len(moves_lower) >= 3:
        if moves_lower[0] == "d4" and moves_lower[2].lower() == "bf4":
            return _build_opening_result("london_system", moves)
    
    # Sicilian Defense: e4 c5
    if len(moves_lower) >= 2:
        if moves_lower[:2] == ["e4", "c5"]:
            return _build_opening_result("sicilian_defense", moves)
    
    # Caro-Kann: e4 c6
    if len(moves_lower) >= 2:
        if moves_lower[:2] == ["e4", "c6"]:
            return _build_opening_result("caro_kann", moves)
    
    # French Defense: e4 e6
    if len(moves_lower) >= 2:
        if moves_lower[:2] == ["e4", "e6"]:
            return _build_opening_result("french_defense", moves)
    
    # Scandinavian Defense: e4 d5
    if len(moves_lower) >= 2:
        if moves_lower[:2] == ["e4", "d5"]:
            return _build_opening_result("scandinavian_defense", moves)
    
    # Ruy Lopez: e4 e5 Nf3 Nc6 Bb5 (5 moves)
    if len(moves_lower) >= 5:
        if moves_lower[:5] == ["e4", "e5", "nf3", "nc6", "bb5"]:
            return _build_opening_result("ruy_lopez", moves)
    
    # Philidor Defense: e4 e5 Nf3 d6 (4 moves)
    if len(moves_lower) >= 4:
        if moves_lower[:4] == ["e4", "e5", "nf3", "d6"]:
            return _build_opening_result("philidor_defense", moves)
    
    return None


def _build_opening_result(opening_key: str, moves: List[str], override_variation: str = None) -> Optional[Dict]:
    """Build the opening detection result dict."""
    opening = OPENING_DATABASE.get(opening_key)
    if not opening:
        return None
    
    variation = _find_variation(moves, opening) if not override_variation else None
    variation_name = override_variation or (variation.name if variation else None)
    
    return {
        "opening_key": opening_key,
        "opening_name": opening.name,
        "variation": variation_name,
        "description": opening.description,
        "character": opening.character,
        "introduction": opening.introduction_message,
        "has_traps": any(len(v.traps) > 0 for v in opening.variations),
        "trap_names": list(set(t.name for v in opening.variations for t in v.traps))
    }


def _moves_match_opening(game_moves: List[str], opening: OpeningFamily) -> bool:
    """
    Check if game moves match an opening's characteristic moves.
    
    IMPORTANT: Only returns True if we have ALL the defining moves.
    We don't want to say "Queen's Gambit" after just d4.
    """
    if not game_moves:
        return False
    
    game_moves_lower = [m.lower() for m in game_moves]
    opening_moves_lower = [m.lower() for m in opening.first_moves]
    
    # We need AT LEAST all the opening's first moves to be played
    # to confidently identify the opening
    min_required_moves = len(opening_moves_lower)
    
    if len(game_moves_lower) < min_required_moves:
        # Not enough moves yet to identify this opening
        return False
    
    # Check if the game moves contain all the opening's characteristic moves
    # in the correct order
    game_prefix = game_moves_lower[:min_required_moves]
    if game_prefix == opening_moves_lower:
        return True
    
    # Also check variations - they might have different move orders
    for variation in opening.variations:
        var_moves_lower = [m.lower() for m in variation.moves]
        var_min_moves = min(len(var_moves_lower), min_required_moves)
        
        if len(game_moves_lower) >= var_min_moves:
            if game_moves_lower[:var_min_moves] == var_moves_lower[:var_min_moves]:
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



async def suggest_opening_for_session(db, user_id: str, user_color: str, user_rating: int) -> Dict:
    """
    Suggest an opening for this game session and set up teaching.
    
    ALWAYS suggests an opening with traps - proactive teaching at every game start.
    
    Returns:
        - opening_key: Key of the suggested opening
        - opening_name: Display name
        - why: Why this opening was chosen
        - first_moves: The moves to guide the player through
        - teaching_message: What to tell the player
        - traps: List of available traps in this opening
        - suggested_trap: The trap we recommend learning (if any)
    """
    # Get user's opening progress
    progress_list = await db.user_opening_progress.find({"user_id": user_id}).to_list(20)
    progress_by_name = {p["opening_name"]: p for p in progress_list}
    
    # Get user's trap progress
    trap_progress_list = await db.user_trap_stats.find({"user_id": user_id}).to_list(50)
    learned_traps = {t["trap_name"]: t for t in trap_progress_list if t.get("success_rate", 0) >= 0.5}
    
    # Find openings suitable for this color and rating
    suitable_openings = []
    for key, opening in OPENING_DATABASE.items():
        # Determine opening color from first move
        # White openings start with moves like e4, d4, c4, Nf3
        # The database typically has openings for White (e4/d4 based)
        first_move = opening.first_moves[0] if opening.first_moves else ""
        opening_for_white = first_move in ["e4", "d4", "c4", "Nf3", "g3", "b3"]
        
        # Check if opening matches the color the user is playing
        if (user_color == "white" and not opening_for_white) or (user_color == "black" and opening_for_white):
            continue
        
        # Check rating suitability - parse from suitable_for field
        # suitable_for is a list like ["beginners", "tactical players"]
        suitable = opening.suitable_for
        rating_ok = True
        if user_rating < 1000 and "advanced" in str(suitable).lower():
            rating_ok = False
        if user_rating > 1800 and "beginner" in str(suitable).lower() and "intermediate" not in str(suitable).lower():
            rating_ok = False
        
        if not rating_ok:
            continue
        
        # Get user's mastery level
        progress = progress_by_name.get(opening.name)
        mastery = progress.get("mastery_level", "unknown") if progress else "unknown"
        games_played = progress.get("games_played", 0) if progress else 0
        
        # Count unlearned traps
        all_traps = []
        for var in opening.variations:
            all_traps.extend(var.traps)
        unlearned_traps = [t for t in all_traps if t.name not in learned_traps]
        
        suitable_openings.append({
            "key": key,
            "opening": opening,
            "mastery": mastery,
            "games_played": games_played,
            "all_traps": all_traps,
            "unlearned_traps": unlearned_traps
        })
    
    if not suitable_openings:
        # Fallback to any opening
        for key, opening in OPENING_DATABASE.items():
            all_traps = []
            for var in opening.variations:
                all_traps.extend(var.traps)
            suitable_openings.append({
                "key": key,
                "opening": opening,
                "mastery": "unknown",
                "games_played": 0,
                "all_traps": all_traps,
                "unlearned_traps": all_traps
            })
            break
    
    if not suitable_openings:
        return None
    
    # Priority: unknown > introduced > learning > practiced (review) > mastered (skip)
    # Also prioritize openings with unlearned traps
    priority_order = ["unknown", "introduced", "learning", "practiced"]
    
    selected = None
    for priority in priority_order:
        candidates = [o for o in suitable_openings if o["mastery"] == priority]
        if candidates:
            # Prioritize openings with unlearned traps
            with_traps = [c for c in candidates if len(c["unlearned_traps"]) > 0]
            if with_traps:
                selected = min(with_traps, key=lambda x: x["games_played"])
            else:
                selected = min(candidates, key=lambda x: x["games_played"])
            break
    
    if not selected:
        # All mastered, pick one to review (preferably with traps)
        with_traps = [o for o in suitable_openings if len(o.get("unlearned_traps", [])) > 0]
        selected = with_traps[0] if with_traps else suitable_openings[0]
    
    opening = selected["opening"]
    mastery = selected["mastery"]
    all_traps = selected.get("all_traps", [])
    unlearned_traps = selected.get("unlearned_traps", [])
    
    # Select a trap to suggest (prioritize by difficulty)
    suggested_trap = None
    if unlearned_traps:
        # Sort by difficulty: beginner < intermediate < advanced
        difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        sorted_traps = sorted(unlearned_traps, key=lambda t: difficulty_order.get(t.difficulty, 1))
        suggested_trap = sorted_traps[0]
    
    # Build teaching message based on mastery level
    if mastery == "unknown":
        why = "I noticed you haven't tried this opening yet"
        teaching_message = (
            f"Today let's learn the {opening.name}! "
            f"{opening.introduction_message}"
        )
    elif mastery == "introduced":
        why = "We started learning this but need more practice"
        teaching_message = (
            f"Let's continue learning the {opening.name}. "
            f"Follow my guidance for each move."
        )
    elif mastery == "learning":
        why = "You're learning this opening"
        teaching_message = (
            f"Good! Let's practice the {opening.name} again. "
            f"Try to remember the main moves."
        )
    elif mastery == "practiced":
        why = "Time to reinforce what you've learned"
        teaching_message = (
            f"Let's review the {opening.name}. "
            f"Show me what you remember!"
        )
    else:
        why = "Keeping your skills sharp"
        teaching_message = f"Let's play the {opening.name} - you know this one well!"
    
    # Add trap information to the message
    if suggested_trap:
        teaching_message += (
            f"\n\nThere's a famous trap here: the **{suggested_trap.name}**. "
            f"Want to learn it?"
        )
    
    # Get first moves for this opening
    first_moves = opening.first_moves
    
    # Get the first variation's moves for full teaching
    if opening.variations:
        main_variation = opening.variations[0]
        full_moves = main_variation.moves
        key_ideas = main_variation.key_ideas[:3] if main_variation.key_ideas else []
    else:
        full_moves = first_moves
        key_ideas = []
    
    # Build trap info for response
    trap_list = []
    for trap in all_traps:
        trap_list.append({
            "name": trap.name,
            "difficulty": trap.difficulty,
            "moves": trap.moves,
            "trap_move": trap.trap_move,
            "explanation": trap.explanation,
            "refutation": trap.refutation,
            "victim_color": trap.victim_color,
            "learned": trap.name in learned_traps,
            "fen_before": trap.fen_before_trap,
            "fen_after": trap.fen_after_trap
        })
    
    return {
        "opening_key": selected["key"],
        "opening_name": opening.name,
        "why": why,
        "first_moves": first_moves,
        "full_moves": full_moves,
        "teaching_message": teaching_message,
        "key_ideas": key_ideas,
        "mastery_level": mastery,
        "traps": trap_list,
        "suggested_trap": {
            "name": suggested_trap.name,
            "difficulty": suggested_trap.difficulty,
            "moves": suggested_trap.moves,
            "trap_move": suggested_trap.trap_move,
            "explanation": suggested_trap.explanation,
            "refutation": suggested_trap.refutation,
            "victim_color": suggested_trap.victim_color
        } if suggested_trap else None
    }


def get_move_guidance(opening_key: str, move_index: int, user_color: str) -> Optional[Dict]:
    """
    Get guidance for what move the user should play next in the opening.
    
    Returns instruction for the user's next move in the opening sequence.
    """
    opening = OPENING_DATABASE.get(opening_key)
    if not opening or not opening.variations:
        return None
    
    # Get main variation
    main_var = opening.variations[0]
    moves = main_var.moves
    
    if move_index >= len(moves):
        return {
            "complete": True,
            "message": f"Excellent! You've completed the main line of the {opening.name}. Now let's play!"
        }
    
    move = moves[move_index]
    is_white_move = (move_index % 2 == 0)
    
    # Check if this is the user's move
    is_user_move = (is_white_move and user_color == "white") or (not is_white_move and user_color == "black")
    
    move_number = (move_index // 2) + 1
    
    if is_user_move:
        # User should play this move - give guidance
        explanation = ""
        if move_index == 0 and main_var.key_ideas:
            explanation = main_var.key_ideas[0]
        elif move_index < len(main_var.key_ideas or []):
            explanation = main_var.key_ideas[move_index] if main_var.key_ideas else ""
        
        return {
            "complete": False,
            "your_turn": True,
            "suggested_move": move,
            "move_number": move_number,
            "message": f"Play {move}. {explanation}".strip(),
            "hint": f"The main line continues with {move}"
        }
    else:
        # This is the coach's move
        return {
            "complete": False,
            "your_turn": False,
            "coach_move": move,
            "move_number": move_number,
            "message": f"I'll play {move}."
        }
