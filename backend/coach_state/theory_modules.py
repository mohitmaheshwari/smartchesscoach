"""
THEORY MODULES REGISTRY - Step 10: Pattern Injection Engine

30 High-Leverage Theory Modules organized by category.
Each module is:
- Detectable deterministically
- Enforceable via Focus Lock
- Proven to improve rating fast

Categories:
A - Tactical Awareness (8)
B - Conversion & Advantage (6)
C - Endgame Fundamentals (6)
D - Positional Structure (6)
E - Opening Principles (4)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class ModuleCategory(str, Enum):
    TACTICAL = "tactical"
    CONVERSION = "conversion"
    ENDGAME = "endgame"
    POSITIONAL = "positional"
    OPENING = "opening"


@dataclass
class TheoryModule:
    """A single theory module."""
    key: str
    name: str
    category: ModuleCategory
    trigger_pattern: str  # What triggers this module
    rule: str  # The one rule to follow
    explanation: str  # Short explanation (1-2 sentences)
    detection_keys: List[str]  # lesson_keys that map to this module
    min_rating: int = 0
    max_rating: int = 3000
    
    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "category": self.category,
            "trigger_pattern": self.trigger_pattern,
            "rule": self.rule,
            "explanation": self.explanation,
            "min_rating": self.min_rating,
            "max_rating": self.max_rating,
        }


# =============================================================================
# CATEGORY A — TACTICAL AWARENESS (8 Modules)
# =============================================================================

LPDO = TheoryModule(
    key="LPDO",
    name="Loose Pieces Drop Off",
    category=ModuleCategory.TACTICAL,
    trigger_pattern="Hanging piece blunders",
    rule="Before every move, scan for unprotected pieces.",
    explanation="Loose pieces are magnets for tactics. A piece that isn't defended is a target waiting to be exploited.",
    detection_keys=["HANGING_PIECE", "UNDEFENDED_PIECE", "LPDO"],
    max_rating=1800,
)

FORCING_MOVES_FIRST = TheoryModule(
    key="FORCING_MOVES_FIRST",
    name="Forcing Moves First",
    category=ModuleCategory.TACTICAL,
    trigger_pattern="Missed checks/captures",
    rule="Check forcing moves (checks, captures, threats) before deciding.",
    explanation="Forcing moves limit your opponent's options. Always consider them first before quiet moves.",
    detection_keys=["FORCING_BLIND", "MISSED_TACTIC", "MISSED_CHECK"],
    max_rating=2000,
)

OVERLOADED_DEFENDER = TheoryModule(
    key="OVERLOADED_DEFENDER",
    name="Overloaded Defender",
    category=ModuleCategory.TACTICAL,
    trigger_pattern="Defender protecting two targets",
    rule="Look for pieces defending multiple things.",
    explanation="When one piece guards two targets, attacking either forces a choice. Find the overloaded piece.",
    detection_keys=["OVERLOADED", "DOUBLE_ATTACK"],
    max_rating=1800,
)

BACK_RANK_WEAKNESS = TheoryModule(
    key="BACK_RANK_WEAKNESS",
    name="Back Rank Weakness",
    category=ModuleCategory.TACTICAL,
    trigger_pattern="Back rank mate patterns",
    rule="Always create luft (escape square) before attacking.",
    explanation="A trapped king on the back rank is a death sentence. Give your king air before launching attacks.",
    detection_keys=["BACK_RANK", "KING_SAFETY", "NO_LUFT"],
    max_rating=1600,
)

DISCOVERED_ATTACK = TheoryModule(
    key="DISCOVERED_ATTACK",
    name="Discovered Attack",
    category=ModuleCategory.TACTICAL,
    trigger_pattern="Missed discovered tactic",
    rule="Look for hidden attacks behind your pieces.",
    explanation="Moving one piece can unleash another. Check what lies behind before committing.",
    detection_keys=["DISCOVERED", "HIDDEN_ATTACK"],
    max_rating=1800,
)

ZWISCHENZUG = TheoryModule(
    key="ZWISCHENZUG",
    name="Zwischenzug (In-Between Move)",
    category=ModuleCategory.TACTICAL,
    trigger_pattern="Missed intermediate move",
    rule="Before recapturing, check for a forcing in-between move.",
    explanation="The expected move isn't always best. An intermediate threat can change everything.",
    detection_keys=["ZWISCHENZUG", "INTERMEDIATE", "IN_BETWEEN"],
    max_rating=2000,
)

REMOVE_THE_DEFENDER = TheoryModule(
    key="REMOVE_THE_DEFENDER",
    name="Remove the Defender",
    category=ModuleCategory.TACTICAL,
    trigger_pattern="Tactical collapse due to key defender",
    rule="Identify and eliminate the key defender.",
    explanation="Every position has critical defenders. Remove them and the position collapses.",
    detection_keys=["REMOVE_DEFENDER", "KEY_DEFENDER"],
    max_rating=1800,
)

DEFLECTION = TheoryModule(
    key="DEFLECTION",
    name="Deflection",
    category=ModuleCategory.TACTICAL,
    trigger_pattern="Forced piece off critical square",
    rule="Can a defender be lured away from its duty?",
    explanation="Force a piece to move and leave something unguarded. Deflection exploits commitment.",
    detection_keys=["DEFLECTION", "DECOY"],
    max_rating=1800,
)


# =============================================================================
# CATEGORY B — CONVERSION & ADVANTAGE (6 Modules)
# =============================================================================

SIMPLIFY_WHEN_AHEAD = TheoryModule(
    key="SIMPLIFY_WHEN_AHEAD",
    name="Simplify When Ahead",
    category=ModuleCategory.CONVERSION,
    trigger_pattern="+200+ advantage lost",
    rule="Trade pieces, reduce counterplay.",
    explanation="Complexity helps the defender. When ahead, trade down and reduce chaos.",
    detection_keys=["CONVERTING_ADVANTAGE", "FAILED_CONVERSION", "SIMPLIFY"],
    max_rating=2200,
)

DONT_RUSH_PAWNS = TheoryModule(
    key="DONT_RUSH_PAWNS",
    name="Don't Rush Pawns When Winning",
    category=ModuleCategory.CONVERSION,
    trigger_pattern="Premature pawn push collapse",
    rule="Improve pieces before pushing pawns.",
    explanation="Pawns can't retreat. Improve your position first, then advance with support.",
    detection_keys=["PREMATURE_PAWN", "PAWN_PUSH"],
    max_rating=1800,
)

ACTIVATE_KING_ENDGAME = TheoryModule(
    key="ACTIVATE_KING_ENDGAME",
    name="Activate King in Endgame",
    category=ModuleCategory.CONVERSION,
    trigger_pattern="Passive king in endgame",
    rule="In the endgame, your king becomes a fighting piece.",
    explanation="The king transforms from liability to asset. Bring it forward in endgames.",
    detection_keys=["PASSIVE_KING", "KING_ACTIVITY", "ENDGAME_KING"],
    max_rating=1600,
)

CONVERT_BY_RESTRICTION = TheoryModule(
    key="CONVERT_BY_RESTRICTION",
    name="Convert by Restriction",
    category=ModuleCategory.CONVERSION,
    trigger_pattern="Kept tension instead of limiting opponent",
    rule="Restrict first, then improve.",
    explanation="Limit your opponent's options before improving. A squeezed opponent has fewer tricks.",
    detection_keys=["RESTRICTION", "LIMIT_COUNTERPLAY"],
    max_rating=2000,
)

TRADE_ACTIVE_PIECES = TheoryModule(
    key="TRADE_ACTIVE_PIECES",
    name="Trade Active Pieces",
    category=ModuleCategory.CONVERSION,
    trigger_pattern="Let opponent keep activity",
    rule="Trade your opponent's best piece.",
    explanation="Neutralize their most dangerous piece. Bad pieces don't win games.",
    detection_keys=["ACTIVE_PIECES", "PIECE_ACTIVITY"],
    max_rating=2000,
)

AVOID_COUNTERPLAY = TheoryModule(
    key="AVOID_COUNTERPLAY",
    name="Avoid Counterplay",
    category=ModuleCategory.CONVERSION,
    trigger_pattern="Winning but gave opponent activity",
    rule="Eliminate threats before improving position.",
    explanation="A winning position with counterplay is dangerous. Remove threats first.",
    detection_keys=["COUNTERPLAY", "ALLOWED_COUNTERPLAY"],
    max_rating=2200,
)


# =============================================================================
# CATEGORY C — ENDGAME FUNDAMENTALS (6 Modules)
# =============================================================================

SQUARE_RULE = TheoryModule(
    key="SQUARE_RULE",
    name="Square Rule",
    category=ModuleCategory.ENDGAME,
    trigger_pattern="Pawn race lost",
    rule="If the king enters the square, it catches the pawn.",
    explanation="Draw an imaginary square from pawn to promotion. If the king can enter, it catches the pawn.",
    detection_keys=["SQUARE_RULE", "PAWN_RACE"],
    max_rating=1400,
)

OPPOSITION = TheoryModule(
    key="OPPOSITION",
    name="Opposition",
    category=ModuleCategory.ENDGAME,
    trigger_pattern="King opposition lost",
    rule="In king endgames, control the key squares with opposition.",
    explanation="Kings face off one square apart. The side NOT to move has opposition and wins the key squares.",
    detection_keys=["OPPOSITION", "KING_ENDGAME"],
    max_rating=1600,
)

ROOK_BEHIND_PASSER = TheoryModule(
    key="ROOK_BEHIND_PASSER",
    name="Rook Behind Passed Pawn",
    category=ModuleCategory.ENDGAME,
    trigger_pattern="Passive rook endgame",
    rule="Rooks belong behind passed pawns (yours or opponent's).",
    explanation="Behind the pawn, the rook gains space as the pawn advances. In front, it loses space.",
    detection_keys=["ROOK_ENDGAME", "PASSED_PAWN", "ROOK_PLACEMENT"],
    max_rating=1800,
)

OUTSIDE_PASSED_PAWN = TheoryModule(
    key="OUTSIDE_PASSED_PAWN",
    name="Outside Passed Pawn",
    category=ModuleCategory.ENDGAME,
    trigger_pattern="Missed outside passer creation",
    rule="Create a distant passed pawn to distract the enemy king.",
    explanation="An outside passer draws the king away, letting yours invade. Distance is the weapon.",
    detection_keys=["OUTSIDE_PASSER", "DISTANT_PAWN"],
    max_rating=1800,
)

WRONG_BISHOP_CORNER = TheoryModule(
    key="WRONG_BISHOP_CORNER",
    name="Wrong Bishop Corner",
    category=ModuleCategory.ENDGAME,
    trigger_pattern="Drawn endgame due to wrong bishop",
    rule="Bishop must control the promotion square.",
    explanation="A bishop that can't control the queening square cannot win. Know when the corner is wrong.",
    detection_keys=["WRONG_BISHOP", "BISHOP_ENDGAME"],
    max_rating=1600,
)

PUSH_PASSERS_CAREFULLY = TheoryModule(
    key="PUSH_PASSERS_CAREFULLY",
    name="Push Passed Pawns Carefully",
    category=ModuleCategory.ENDGAME,
    trigger_pattern="Overextended passed pawn",
    rule="Support before advancing.",
    explanation="An unsupported passer becomes a weakness. Ensure support before pushing.",
    detection_keys=["PAWN_ADVANCE", "UNSUPPORTED_PAWN"],
    max_rating=1600,
)


# =============================================================================
# CATEGORY D — POSITIONAL STRUCTURE (6 Modules)
# =============================================================================

GOOD_VS_BAD_BISHOP = TheoryModule(
    key="GOOD_VS_BAD_BISHOP",
    name="Good vs Bad Bishop",
    category=ModuleCategory.POSITIONAL,
    trigger_pattern="Locked bishop behind own pawns",
    rule="Don't block your own bishop with pawns.",
    explanation="Pawns on the same color as your bishop restrict it. Keep pawns on opposite color.",
    detection_keys=["BAD_BISHOP", "BISHOP_PAWNS"],
    max_rating=1800,
)

KNIGHT_OUTPOSTS = TheoryModule(
    key="KNIGHT_OUTPOSTS",
    name="Knight Outposts",
    category=ModuleCategory.POSITIONAL,
    trigger_pattern="Missed outpost opportunity",
    rule="Knights belong on protected squares where pawns can't attack them.",
    explanation="A knight on an outpost is a fortress. Find squares where it can't be challenged by pawns.",
    detection_keys=["OUTPOST", "KNIGHT_PLACEMENT"],
    max_rating=1800,
)

MINOR_PIECE_SUPERIORITY = TheoryModule(
    key="MINOR_PIECE_SUPERIORITY",
    name="Minor Piece Superiority",
    category=ModuleCategory.POSITIONAL,
    trigger_pattern="Bad trade decisions",
    rule="Trade your worse minor piece for their better one.",
    explanation="Not all minors are equal. Trade bad bishops, keep good knights. Quality over quantity.",
    detection_keys=["MINOR_TRADE", "PIECE_TRADE"],
    max_rating=2000,
)

PAWN_BREAK_AWARENESS = TheoryModule(
    key="PAWN_BREAK_AWARENESS",
    name="Pawn Break Awareness",
    category=ModuleCategory.POSITIONAL,
    trigger_pattern="Missed structural break",
    rule="Identify your pawn break plan early.",
    explanation="Every pawn structure has a thematic break. Know yours and time it right.",
    detection_keys=["PAWN_BREAK", "STRUCTURE"],
    max_rating=2000,
)

OPEN_FILE_CONTROL = TheoryModule(
    key="OPEN_FILE_CONTROL",
    name="Open File Control",
    category=ModuleCategory.POSITIONAL,
    trigger_pattern="Ignored open file",
    rule="Put rooks on open files.",
    explanation="Open files are highways for rooks. Control them before your opponent does.",
    detection_keys=["OPEN_FILE", "ROOK_FILE"],
    max_rating=1600,
)

IMPROVE_WORST_PIECE = TheoryModule(
    key="IMPROVE_WORST_PIECE",
    name="Improve Worst Piece",
    category=ModuleCategory.POSITIONAL,
    trigger_pattern="Repeated passive piece",
    rule="Before every move, ask: which piece is worst?",
    explanation="Your position is only as strong as your weakest piece. Find it and improve it.",
    detection_keys=["PASSIVE_PIECE", "PIECE_ACTIVITY", "WORST_PIECE"],
    max_rating=2000,
)


# =============================================================================
# CATEGORY E — OPENING PRINCIPLES (4 Modules)
# =============================================================================

DONT_MOVE_SAME_PIECE_TWICE = TheoryModule(
    key="DONT_MOVE_SAME_PIECE_TWICE",
    name="Don't Move Same Piece Twice",
    category=ModuleCategory.OPENING,
    trigger_pattern="Early tempo loss",
    rule="Develop new pieces first.",
    explanation="Each move should add a new piece to the fight. Moving the same piece twice loses tempo.",
    detection_keys=["TEMPO_LOSS", "PIECE_TWICE", "DEVELOPMENT"],
    max_rating=1400,
)

CASTLE_BEFORE_ATTACKING = TheoryModule(
    key="CASTLE_BEFORE_ATTACKING",
    name="Castle Before Attacking",
    category=ModuleCategory.OPENING,
    trigger_pattern="King caught in center",
    rule="Secure your king before launching operations.",
    explanation="An uncastled king is a liability. Safety first, attack second.",
    detection_keys=["KING_CENTER", "CASTLE_DELAY", "KING_SAFETY"],
    max_rating=1600,
)

FIGHT_FOR_CENTER = TheoryModule(
    key="FIGHT_FOR_CENTER",
    name="Fight for the Center",
    category=ModuleCategory.OPENING,
    trigger_pattern="Passive opening",
    rule="Control e4/d4 (or e5/d5) with pawns or pieces.",
    explanation="The center controls the board. Fight for it from move one.",
    detection_keys=["CENTER_CONTROL", "PASSIVE_OPENING"],
    max_rating=1400,
)

QUEEN_OUT_TOO_EARLY = TheoryModule(
    key="QUEEN_OUT_TOO_EARLY",
    name="Queen Out Too Early",
    category=ModuleCategory.OPENING,
    trigger_pattern="Early queen punished",
    rule="Don't bring the queen out before development is complete.",
    explanation="The queen is a target. Bring it out early and it gets chased while your opponent develops.",
    detection_keys=["EARLY_QUEEN", "QUEEN_PUNISHED"],
    max_rating=1400,
)


# =============================================================================
# MODULE REGISTRY
# =============================================================================

ALL_MODULES: Dict[str, TheoryModule] = {
    # Category A - Tactical
    "LPDO": LPDO,
    "FORCING_MOVES_FIRST": FORCING_MOVES_FIRST,
    "OVERLOADED_DEFENDER": OVERLOADED_DEFENDER,
    "BACK_RANK_WEAKNESS": BACK_RANK_WEAKNESS,
    "DISCOVERED_ATTACK": DISCOVERED_ATTACK,
    "ZWISCHENZUG": ZWISCHENZUG,
    "REMOVE_THE_DEFENDER": REMOVE_THE_DEFENDER,
    "DEFLECTION": DEFLECTION,
    
    # Category B - Conversion
    "SIMPLIFY_WHEN_AHEAD": SIMPLIFY_WHEN_AHEAD,
    "DONT_RUSH_PAWNS": DONT_RUSH_PAWNS,
    "ACTIVATE_KING_ENDGAME": ACTIVATE_KING_ENDGAME,
    "CONVERT_BY_RESTRICTION": CONVERT_BY_RESTRICTION,
    "TRADE_ACTIVE_PIECES": TRADE_ACTIVE_PIECES,
    "AVOID_COUNTERPLAY": AVOID_COUNTERPLAY,
    
    # Category C - Endgame
    "SQUARE_RULE": SQUARE_RULE,
    "OPPOSITION": OPPOSITION,
    "ROOK_BEHIND_PASSER": ROOK_BEHIND_PASSER,
    "OUTSIDE_PASSED_PAWN": OUTSIDE_PASSED_PAWN,
    "WRONG_BISHOP_CORNER": WRONG_BISHOP_CORNER,
    "PUSH_PASSERS_CAREFULLY": PUSH_PASSERS_CAREFULLY,
    
    # Category D - Positional
    "GOOD_VS_BAD_BISHOP": GOOD_VS_BAD_BISHOP,
    "KNIGHT_OUTPOSTS": KNIGHT_OUTPOSTS,
    "MINOR_PIECE_SUPERIORITY": MINOR_PIECE_SUPERIORITY,
    "PAWN_BREAK_AWARENESS": PAWN_BREAK_AWARENESS,
    "OPEN_FILE_CONTROL": OPEN_FILE_CONTROL,
    "IMPROVE_WORST_PIECE": IMPROVE_WORST_PIECE,
    
    # Category E - Opening
    "DONT_MOVE_SAME_PIECE_TWICE": DONT_MOVE_SAME_PIECE_TWICE,
    "CASTLE_BEFORE_ATTACKING": CASTLE_BEFORE_ATTACKING,
    "FIGHT_FOR_CENTER": FIGHT_FOR_CENTER,
    "QUEEN_OUT_TOO_EARLY": QUEEN_OUT_TOO_EARLY,
}

# Mapping from lesson_key to module_key
LESSON_TO_MODULE: Dict[str, str] = {}
for module_key, module in ALL_MODULES.items():
    for detection_key in module.detection_keys:
        LESSON_TO_MODULE[detection_key] = module_key


def get_module(key: str) -> Optional[TheoryModule]:
    """Get a theory module by key."""
    return ALL_MODULES.get(key)


def get_module_for_lesson(lesson_key: str) -> Optional[TheoryModule]:
    """Get the theory module that matches a lesson key."""
    module_key = LESSON_TO_MODULE.get(lesson_key)
    if module_key:
        return ALL_MODULES.get(module_key)
    return None


def get_modules_by_category(category: ModuleCategory) -> List[TheoryModule]:
    """Get all modules in a category."""
    return [m for m in ALL_MODULES.values() if m.category == category]


def get_modules_for_rating(rating: int) -> List[TheoryModule]:
    """Get all modules appropriate for a rating."""
    return [m for m in ALL_MODULES.values() 
            if m.min_rating <= rating <= m.max_rating]
