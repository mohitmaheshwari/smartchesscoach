"""
Pawn Structure Classifier
=========================

Identifies pawn structures and maps them to strategic plans.
This is critical for teaching - the pawn structure determines the plan!

Features:
1. Classify pawn structure type (Sicilian, French, Caro-Kann, etc.)
2. Identify structural features (isolated, doubled, backward, passed pawns)
3. Map structure → typical plans for both sides
4. Identify key squares and outposts
5. Suggest piece placement based on structure

Usage:
    classifier = PawnStructureClassifier()
    analysis = classifier.analyze(board)
    # Returns: structure type, plans, features, teaching content
"""

import chess
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class StructureType(str, Enum):
    """Major pawn structure categories."""
    # Open Games (1.e4 e5)
    OPEN_GAME = "open_game"
    ITALIAN_STRUCTURE = "italian_structure"
    SPANISH_STRUCTURE = "spanish_structure"
    SCOTCH_STRUCTURE = "scotch_structure"
    
    # Sicilian Structures
    SICILIAN_SCHEVENINGEN = "sicilian_scheveningen"
    SICILIAN_NAJDORF = "sicilian_najdorf"
    SICILIAN_DRAGON = "sicilian_dragon"
    SICILIAN_MAROCZY_BIND = "sicilian_maroczy_bind"
    SICILIAN_HEDGEHOG = "sicilian_hedgehog"
    SICILIAN_CLOSED = "sicilian_closed"
    
    # French Structures
    FRENCH_ADVANCE = "french_advance"
    FRENCH_EXCHANGE = "french_exchange"
    FRENCH_TARRASCH = "french_tarrasch"
    
    # Caro-Kann Structures
    CARO_KANN_CLASSICAL = "caro_kann_classical"
    CARO_KANN_ADVANCE = "caro_kann_advance"
    CARO_KANN_EXCHANGE = "caro_kann_exchange"
    
    # Queen's Pawn Structures
    QUEENS_GAMBIT_ACCEPTED = "queens_gambit_accepted"
    QUEENS_GAMBIT_DECLINED = "queens_gambit_declined"
    SLAV_STRUCTURE = "slav_structure"
    CATALAN_STRUCTURE = "catalan_structure"
    
    # Indian Structures
    KINGS_INDIAN = "kings_indian"
    NIMZO_INDIAN = "nimzo_indian"
    QUEENS_INDIAN = "queens_indian"
    GRUNFELD_STRUCTURE = "grunfeld_structure"
    BENONI_STRUCTURE = "benoni_structure"
    BENKO_STRUCTURE = "benko_structure"
    
    # English/Flank Structures
    ENGLISH_STRUCTURE = "english_structure"
    REVERSED_SICILIAN = "reversed_sicilian"
    
    # Isolated Pawn Structures
    ISOLATED_QUEEN_PAWN = "isolated_queen_pawn"
    HANGING_PAWNS = "hanging_pawns"
    
    # Symmetric Structures
    SYMMETRIC_STRUCTURE = "symmetric_structure"
    CARLSBAD_STRUCTURE = "carlsbad_structure"
    
    # Other
    CLOSED_CENTER = "closed_center"
    OPEN_CENTER = "open_center"
    UNKNOWN = "unknown"


@dataclass
class PawnFeature:
    """A specific pawn feature (weakness or strength)."""
    type: str  # "isolated", "doubled", "backward", "passed", etc.
    square: str  # e.g., "d4"
    color: str  # "white" or "black"
    description: str
    is_weakness: bool
    teaching_note: str


@dataclass
class StructureAnalysis:
    """Complete pawn structure analysis."""
    structure_type: StructureType
    structure_name: str
    confidence: float  # 0.0-1.0
    
    # Pawn positions
    white_pawns: List[str]
    black_pawns: List[str]
    
    # Features
    features: List[PawnFeature]
    isolated_pawns: List[str]
    doubled_pawns: List[str]
    backward_pawns: List[str]
    passed_pawns: List[str]
    pawn_chains: List[Dict]
    
    # Key squares
    outposts: List[str]  # Strong squares for pieces
    weak_squares: List[str]  # Holes in pawn structure
    
    # Strategic guidance
    white_plans: List[str]
    black_plans: List[str]
    piece_placement: Dict[str, List[str]]  # {"N": ["d5", "e4"], "B": ["g2"]}
    
    # Teaching content
    key_concepts: List[str]
    common_mistakes: List[str]
    famous_examples: List[str]


# ============================================
# STRUCTURE DEFINITIONS AND PLANS
# ============================================

STRUCTURE_DATABASE = {
    
    StructureType.SICILIAN_SCHEVENINGEN: {
        "name": "Sicilian Scheveningen",
        "pattern": {
            "white_center": ["e4", "d4"],  # or d4 captured
            "black_center": ["e6", "d6"],
        },
        "description": "Black has pawns on e6 and d6, creating a small center",
        "white_plans": [
            "f4-f5 pawn break to open the f-file",
            "Nd5 sacrifice to destroy Black's structure",
            "g4-g5 to attack the kingside",
            "Be3-Qd2-0-0-0 for opposite side castling attack"
        ],
        "black_plans": [
            "...d5 or ...e5 central break when ready",
            "...b5-b4 queenside counterplay",
            "...a6 + ...b5 with Nc4 outpost",
            "Piece pressure on e4 pawn"
        ],
        "key_squares": {
            "outposts_white": ["d5"],
            "outposts_black": ["d5", "e5"],
            "weak_squares_white": [],
            "weak_squares_black": ["d5"]
        },
        "piece_placement": {
            "white": {"N": ["d5", "f3"], "B": ["e3", "c4"], "R": ["d1", "f1"]},
            "black": {"N": ["c6", "f6", "d7"], "B": ["e7", "b7"], "R": ["c8", "d8"]}
        },
        "key_concepts": [
            "The d5 square is the key battleground",
            "Black's e6-d6 structure is solid but slightly passive",
            "White often sacrifices on d5 to open lines",
            "Opposite side castling leads to mutual attacks"
        ],
        "common_mistakes": [
            "Black playing ...e5 too early (weakens d5)",
            "White pushing f5 without preparation",
            "Neglecting development for pawn pushes"
        ],
        "famous_examples": ["Kasparov vs Karpov, many games", "Fischer's Sicilian games"]
    },
    
    StructureType.FRENCH_ADVANCE: {
        "name": "French Advance",
        "pattern": {
            "white_center": ["e5", "d4"],
            "black_center": ["e6", "d5"],
        },
        "description": "White's e5 pawn creates a space advantage but is also a target",
        "white_plans": [
            "Kingside attack with f4-f5",
            "Support the e5 pawn and restrict Black",
            "Nf3-h4-f5 maneuver",
            "Open the kingside with g4-g5 if Black castles short"
        ],
        "black_plans": [
            "...c5 to attack the d4 base of White's pawn chain",
            "...f6 to challenge the e5 pawn",
            "...Nh6-f7 or ...Nh6-f5 to pressure e5",
            "Queenside play with ...Qb6, ...Nc6-a5"
        ],
        "key_squares": {
            "outposts_white": ["d4", "f4"],
            "outposts_black": ["e5", "f5"],
            "weak_squares_white": ["d3", "f3"],
            "weak_squares_black": ["e5 (if taken)", "light squares"]
        },
        "piece_placement": {
            "white": {"N": ["f3", "d2"], "B": ["d3", "e3"], "R": ["f1"]},
            "black": {"N": ["c6", "h6", "e7"], "B": ["c8 (problem piece)", "e7"], "R": ["c8"]}
        },
        "key_concepts": [
            "Attack the BASE of pawn chain (d4), not the head (e5)",
            "Black's light-squared bishop is the 'problem piece'",
            "White has space, Black has counterplay",
            "The f6 break is key for Black"
        ],
        "common_mistakes": [
            "Black attacking e5 directly instead of d4",
            "White overextending without piece support",
            "Black forgetting to develop the Bc8"
        ],
        "famous_examples": ["Nimzowitsch's games", "Short vs many opponents"]
    },
    
    StructureType.ISOLATED_QUEEN_PAWN: {
        "name": "Isolated Queen Pawn (IQP)",
        "pattern": {
            "white_center": ["d4"],  # Isolated, no pawns on c or e file
            "black_center": ["d5 or none"],
        },
        "description": "White has an isolated d4 pawn - dynamic piece play vs static weakness",
        "white_plans": [
            "Use the d4 pawn to support pieces on e5 and c5",
            "Attack on the kingside with pieces",
            "d4-d5 advance at the right moment",
            "Nc3-d5 or Ne5 outpost play"
        ],
        "black_plans": [
            "Blockade the d4 pawn (Nd5 is ideal)",
            "Trade pieces to reach an endgame where d4 is weak",
            "Target the d4 pawn with pieces",
            "Control the d5 square"
        ],
        "key_squares": {
            "outposts_white": ["e5", "c5"],
            "outposts_black": ["d5"],
            "weak_squares_white": ["d4 (the IQP)"],
            "weak_squares_black": []
        },
        "piece_placement": {
            "white": {"N": ["e5", "c3"], "B": ["d3", "c1-g5"], "R": ["d1", "c1"]},
            "black": {"N": ["d5", "f6"], "B": ["e7", "b7"], "R": ["d8", "c8"]}
        },
        "key_concepts": [
            "IQP gives active piece play in the middlegame",
            "IQP is a weakness in the endgame",
            "Blockade is the key defensive concept",
            "The side with IQP should avoid piece trades"
        ],
        "common_mistakes": [
            "White trading pieces into a lost endgame",
            "Black allowing d4-d5 advance",
            "Forgetting to blockade with a knight"
        ],
        "famous_examples": ["Botvinnik's IQP games", "Kasparov vs Karpov 1985"]
    },
    
    StructureType.KINGS_INDIAN: {
        "name": "King's Indian Structure",
        "pattern": {
            "white_center": ["d4", "e4 or c4"],
            "black_center": ["d6", "e5 (often closed)"],
        },
        "description": "Black fianchettoes and plays for ...f5 or ...c5 breaks",
        "white_plans": [
            "c4-c5 queenside expansion",
            "Control d5 with pieces",
            "Queenside attack with a4-a5, b4",
            "Keep center closed, expand on queenside"
        ],
        "black_plans": [
            "...f5-f4 kingside attack",
            "...g5-g4 pawn storm after ...f5",
            "...Nh5-f4 piece maneuver",
            "...c6 + ...d5 central break"
        ],
        "key_squares": {
            "outposts_white": ["d5"],
            "outposts_black": ["f4", "e5"],
            "weak_squares_white": [],
            "weak_squares_black": ["d6"]
        },
        "piece_placement": {
            "white": {"N": ["c3", "f3", "d5"], "B": ["e2", "e3"], "R": ["c1", "b1"]},
            "black": {"N": ["d7", "f6", "h5"], "B": ["g7", "e6"], "R": ["f8", "f7"]}
        },
        "key_concepts": [
            "Opposite side attacks - whoever is faster wins",
            "Black's kingside attack can be very dangerous",
            "White should not allow ...f4 without a fight",
            "The Bg7 is Black's key attacking piece"
        ],
        "common_mistakes": [
            "White castling kingside into Black's attack",
            "Black playing ...f5 without preparation",
            "Forgetting about the other side of the board"
        ],
        "famous_examples": ["Kasparov vs Karpov", "Fischer's KID games", "Nakamura's KID"]
    },
    
    StructureType.CARLSBAD_STRUCTURE: {
        "name": "Carlsbad Structure",
        "pattern": {
            "white_center": ["c3", "d4", "e3"],
            "black_center": ["c6", "d5", "e6"],
        },
        "description": "Symmetric structure with minority attack potential for White",
        "white_plans": [
            "Minority attack: b4-b5 to create a weakness on c6",
            "Put pressure on the c-file after ...cxb5",
            "Ne5 outpost",
            "Kingside attack as alternative"
        ],
        "black_plans": [
            "...c5 break before White's b4-b5",
            "Kingside counterplay with ...f6 and ...e5",
            "...Ne4 outpost",
            "Trade pieces if White gets the minority attack going"
        ],
        "key_squares": {
            "outposts_white": ["e5"],
            "outposts_black": ["e4"],
            "weak_squares_white": ["c3 (after b4-b5)"],
            "weak_squares_black": ["c6 (after b4-b5 cxb5)"]
        },
        "piece_placement": {
            "white": {"N": ["f3", "e5"], "B": ["d3", "f4"], "R": ["c1", "b1"]},
            "black": {"N": ["f6", "e4"], "B": ["d6", "e7"], "R": ["c8", "e8"]}
        },
        "key_concepts": [
            "Minority attack creates a permanent weakness",
            "The side being attacked should seek counterplay",
            "Piece activity is crucial",
            "This structure arises from QGD Exchange"
        ],
        "common_mistakes": [
            "Black passively waiting for the minority attack",
            "White rushing b4-b5 without piece support",
            "Ignoring the center while focusing on flanks"
        ],
        "famous_examples": ["Capablanca's QGD games", "Carlsen's technique"]
    },
    
    StructureType.BENONI_STRUCTURE: {
        "name": "Benoni Structure",
        "pattern": {
            "white_center": ["c4", "d5"],
            "black_center": ["c5", "d6", "e6"],
        },
        "description": "White has space with d5, Black has queenside majority and ...e6-e5 break",
        "white_plans": [
            "e4-e5 break to cramp Black further",
            "Kingside attack after e5",
            "Control the e4 square",
            "Nc4-Ne3-d5 piece maneuver"
        ],
        "black_plans": [
            "...b5 queenside counterplay",
            "...e6-e5 central break (key!)",
            "...f5 after ...e5 is blocked",
            "Piece pressure on e4"
        ],
        "key_squares": {
            "outposts_white": ["e4", "d5"],
            "outposts_black": ["e5", "d3"],
            "weak_squares_white": [],
            "weak_squares_black": ["d6", "e6"]
        },
        "piece_placement": {
            "white": {"N": ["c4", "f3"], "B": ["e2", "d2"], "R": ["e1", "b1"]},
            "black": {"N": ["a6", "e8-c7", "f6"], "B": ["g7", "a6"], "R": ["b8", "e8"]}
        },
        "key_concepts": [
            "The ...e5 break is Black's main idea",
            "If White stops ...e5, Black is in trouble",
            "Black's Bg7 is the key piece",
            "Timing is everything in the Benoni"
        ],
        "common_mistakes": [
            "Black playing ...e5 at the wrong time",
            "White ignoring Black's queenside play",
            "Forgetting that the d6 pawn can be weak"
        ],
        "famous_examples": ["Tal's Benoni attacks", "Topalov's Benoni"]
    },
    
    StructureType.GRUNFELD_STRUCTURE: {
        "name": "Grünfeld Structure",
        "pattern": {
            "white_center": ["c4", "d4", "e4 (big center)"],
            "black_center": ["(none or minimal)"],
        },
        "description": "White has a big center, Black attacks it with pieces",
        "white_plans": [
            "Support and advance the center (e4-e5, d4-d5)",
            "Use space advantage for kingside attack",
            "Don't let Black destroy the center",
            "Qd2-Bh6 to trade Black's key bishop"
        ],
        "black_plans": [
            "...c5 to attack d4",
            "Pressure the center with Nc6, Bg7, Qa5",
            "...e6 + ...cxd4 to create IQP",
            "Trade the dark-squared bishops if possible"
        ],
        "key_squares": {
            "outposts_white": ["d5", "e5"],
            "outposts_black": ["c3", "d4 (if center collapses)"],
            "weak_squares_white": ["d4 (under pressure)"],
            "weak_squares_black": []
        },
        "piece_placement": {
            "white": {"N": ["c3", "f3", "e2"], "B": ["e3", "e2"], "R": ["d1", "c1"]},
            "black": {"N": ["c6", "d7"], "B": ["g7", "g4"], "R": ["c8", "d8"]}
        },
        "key_concepts": [
            "Black allows the big center to attack it",
            "If the center holds, White is better",
            "If the center collapses, Black is better",
            "Very sharp, concrete play required"
        ],
        "common_mistakes": [
            "White overextending the center",
            "Black not generating enough pressure",
            "Underestimating the power of the Bg7"
        ],
        "famous_examples": ["Kasparov's Grünfeld victories", "Carlsen vs many"]
    },
    
    StructureType.HANGING_PAWNS: {
        "name": "Hanging Pawns",
        "pattern": {
            "white_center": ["c4", "d4"],  # Both on half-open files
            "black_center": [],
        },
        "description": "Two adjacent pawns on c4 and d4, both potentially weak",
        "white_plans": [
            "Advance d4-d5 or c4-c5 to break through",
            "Use pawns to support piece activity",
            "Attack on the kingside while pawns hold center",
            "Avoid piece trades that expose the pawns"
        ],
        "black_plans": [
            "Pressure the hanging pawns with pieces",
            "Force one pawn to advance, then target the other",
            "Trade pieces to leave the pawns weak",
            "Blockade on c5 and d5"
        ],
        "key_squares": {
            "outposts_white": [],
            "outposts_black": ["c5", "d5"],
            "weak_squares_white": ["c4", "d4"],
            "weak_squares_black": []
        },
        "piece_placement": {
            "white": {"N": ["c3", "f3"], "B": ["d3", "b2"], "R": ["c1", "d1"]},
            "black": {"N": ["c6", "f6"], "B": ["b7", "e7"], "R": ["c8", "d8"]}
        },
        "key_concepts": [
            "Hanging pawns are dynamic - they can advance or be targeted",
            "In middlegame, they support active piece play",
            "In endgame, they become serious weaknesses",
            "The side with hanging pawns should keep pieces on"
        ],
        "common_mistakes": [
            "White trading into an endgame",
            "Black allowing d4-d5 or c4-c5 advance",
            "Not coordinating pieces against the pawns"
        ],
        "famous_examples": ["Rubinstein's games", "Many QGD games"]
    }
}

# Default for unknown structures
DEFAULT_STRUCTURE = {
    "name": "Complex Structure",
    "description": "Position doesn't match a standard structure pattern",
    "white_plans": [
        "Improve your worst-placed piece",
        "Look for pawn breaks to open the position",
        "Create targets in opponent's position",
        "Coordinate your pieces"
    ],
    "black_plans": [
        "Improve your worst-placed piece",
        "Look for pawn breaks to open the position",
        "Create counterplay",
        "Coordinate your pieces"
    ],
    "key_concepts": [
        "Study the pawn structure to find plans",
        "Pawns determine where pieces belong",
        "Attack weaknesses, defend your own"
    ],
    "common_mistakes": [
        "Moving without a plan",
        "Creating unnecessary pawn weaknesses",
        "Ignoring opponent's threats"
    ]
}


class PawnStructureClassifier:
    """
    Analyzes pawn structures and provides strategic guidance.
    """
    
    def analyze(self, board: chess.Board) -> StructureAnalysis:
        """
        Perform complete pawn structure analysis.
        
        Args:
            board: chess.Board object
            
        Returns:
            StructureAnalysis with structure type, plans, features, etc.
        """
        # Get pawn positions
        white_pawns = self._get_pawn_squares(board, chess.WHITE)
        black_pawns = self._get_pawn_squares(board, chess.BLACK)
        
        # Classify the structure
        structure_type, confidence = self._classify_structure(board, white_pawns, black_pawns)
        
        # Get structure data
        structure_data = STRUCTURE_DATABASE.get(structure_type, DEFAULT_STRUCTURE)
        
        # Find structural features
        features = []
        isolated = self._find_isolated_pawns(board, white_pawns, black_pawns)
        doubled = self._find_doubled_pawns(board, white_pawns, black_pawns)
        backward = self._find_backward_pawns(board, white_pawns, black_pawns)
        passed = self._find_passed_pawns(board, white_pawns, black_pawns)
        chains = self._find_pawn_chains(board, white_pawns, black_pawns)
        
        # Convert to PawnFeature objects
        for sq, color in isolated:
            features.append(PawnFeature(
                type="isolated",
                square=sq,
                color=color,
                description=f"Isolated pawn on {sq} - no friendly pawns on adjacent files",
                is_weakness=True,
                teaching_note="Isolated pawns can't be defended by other pawns. Target them!"
            ))
        
        for sq, color in doubled:
            features.append(PawnFeature(
                type="doubled",
                square=sq,
                color=color,
                description=f"Doubled pawn on {sq}",
                is_weakness=True,
                teaching_note="Doubled pawns are slow and can't defend each other."
            ))
        
        for sq, color in backward:
            features.append(PawnFeature(
                type="backward",
                square=sq,
                color=color,
                description=f"Backward pawn on {sq} - can't be supported by other pawns",
                is_weakness=True,
                teaching_note="Backward pawns can become targets. The square in front is weak."
            ))
        
        for sq, color in passed:
            features.append(PawnFeature(
                type="passed",
                square=sq,
                color=color,
                description=f"Passed pawn on {sq} - no enemy pawns can stop it",
                is_weakness=False,
                teaching_note="Passed pawns must be pushed! They're very dangerous in endgames."
            ))
        
        # Find key squares
        outposts = self._find_outposts(board, white_pawns, black_pawns)
        weak_squares = self._find_weak_squares(board, white_pawns, black_pawns)
        
        return StructureAnalysis(
            structure_type=structure_type,
            structure_name=structure_data.get("name", "Unknown"),
            confidence=confidence,
            white_pawns=[chess.square_name(sq) for sq in white_pawns],
            black_pawns=[chess.square_name(sq) for sq in black_pawns],
            features=features,
            isolated_pawns=[sq for sq, _ in isolated],
            doubled_pawns=[sq for sq, _ in doubled],
            backward_pawns=[sq for sq, _ in backward],
            passed_pawns=[sq for sq, _ in passed],
            pawn_chains=chains,
            outposts=outposts,
            weak_squares=weak_squares,
            white_plans=structure_data.get("white_plans", DEFAULT_STRUCTURE["white_plans"]),
            black_plans=structure_data.get("black_plans", DEFAULT_STRUCTURE["black_plans"]),
            piece_placement=structure_data.get("piece_placement", {}),
            key_concepts=structure_data.get("key_concepts", DEFAULT_STRUCTURE["key_concepts"]),
            common_mistakes=structure_data.get("common_mistakes", DEFAULT_STRUCTURE["common_mistakes"]),
            famous_examples=structure_data.get("famous_examples", [])
        )
    
    def _get_pawn_squares(self, board: chess.Board, color: chess.Color) -> List[int]:
        """Get all pawn squares for a color."""
        pawns = []
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                pawns.append(square)
        return pawns
    
    def _classify_structure(
        self, 
        board: chess.Board,
        white_pawns: List[int],
        black_pawns: List[int]
    ) -> Tuple[StructureType, float]:
        """
        Classify the pawn structure type.
        Returns (structure_type, confidence).
        """
        white_pawn_squares = {chess.square_name(sq) for sq in white_pawns}
        black_pawn_squares = {chess.square_name(sq) for sq in black_pawns}
        
        # Check for specific structures based on pawn patterns
        
        # Sicilian Scheveningen: Black has e6+d6, White has/had e4
        if "e6" in black_pawn_squares and "d6" in black_pawn_squares:
            if "e4" in white_pawn_squares or self._had_pawn_on(board, "e4", chess.WHITE):
                return StructureType.SICILIAN_SCHEVENINGEN, 0.85
        
        # French Advance: White e5, Black e6+d5
        if "e5" in white_pawn_squares and "e6" in black_pawn_squares and "d5" in black_pawn_squares:
            return StructureType.FRENCH_ADVANCE, 0.90
        
        # French Exchange: No e-pawns, symmetric-ish
        if "d4" in white_pawn_squares and "d5" in black_pawn_squares:
            if "e4" not in white_pawn_squares and "e5" not in black_pawn_squares:
                return StructureType.FRENCH_EXCHANGE, 0.60
        
        # King's Indian: Black g6+d6, White d4+c4
        if "g6" in black_pawn_squares and "d6" in black_pawn_squares:
            if "d4" in white_pawn_squares and "c4" in white_pawn_squares:
                return StructureType.KINGS_INDIAN, 0.80
        
        # Benoni: White d5, Black c5+d6+e6
        if "d5" in white_pawn_squares and "c5" in black_pawn_squares:
            if "d6" in black_pawn_squares:
                return StructureType.BENONI_STRUCTURE, 0.85
        
        # Grünfeld: White has big center (c4+d4+e4)
        if "c4" in white_pawn_squares and "d4" in white_pawn_squares and "e4" in white_pawn_squares:
            return StructureType.GRUNFELD_STRUCTURE, 0.70
        
        # Carlsbad: Symmetric c3/c6, d4/d5, e3/e6
        if "c3" in white_pawn_squares and "c6" in black_pawn_squares:
            if "d4" in white_pawn_squares and "d5" in black_pawn_squares:
                return StructureType.CARLSBAD_STRUCTURE, 0.75
        
        # Isolated Queen Pawn (White has d4 isolated)
        if "d4" in white_pawn_squares:
            c_file_pawns = [sq for sq in white_pawns if chess.square_file(sq) == 2]  # c-file
            e_file_pawns = [sq for sq in white_pawns if chess.square_file(sq) == 4]  # e-file
            if len(c_file_pawns) == 0 and len(e_file_pawns) == 0:
                return StructureType.ISOLATED_QUEEN_PAWN, 0.90
        
        # Isolated Queen Pawn (Black has d5 isolated)
        if "d5" in black_pawn_squares:
            c_file_pawns = [sq for sq in black_pawns if chess.square_file(sq) == 2]
            e_file_pawns = [sq for sq in black_pawns if chess.square_file(sq) == 4]
            if len(c_file_pawns) == 0 and len(e_file_pawns) == 0:
                return StructureType.ISOLATED_QUEEN_PAWN, 0.90
        
        # Hanging Pawns
        if "c4" in white_pawn_squares and "d4" in white_pawn_squares:
            if "b3" not in white_pawn_squares and "e3" not in white_pawn_squares:
                return StructureType.HANGING_PAWNS, 0.80
        
        # Open Game (1.e4 e5)
        if "e4" in white_pawn_squares and "e5" in black_pawn_squares:
            return StructureType.OPEN_GAME, 0.70
        
        # Symmetric
        if white_pawn_squares == {chess.square_name(chess.square(chess.square_file(sq), 7-chess.square_rank(sq))) for sq in black_pawns}:
            return StructureType.SYMMETRIC_STRUCTURE, 0.60
        
        return StructureType.UNKNOWN, 0.30
    
    def _had_pawn_on(self, board: chess.Board, square_name: str, color: chess.Color) -> bool:
        """Check if a pawn was likely on this square earlier (heuristic)."""
        # This is a simplification - in real analysis, we'd check move history
        return False
    
    def _find_isolated_pawns(
        self, 
        board: chess.Board,
        white_pawns: List[int],
        black_pawns: List[int]
    ) -> List[Tuple[str, str]]:
        """Find isolated pawns (no friendly pawns on adjacent files)."""
        isolated = []
        
        for sq in white_pawns:
            file = chess.square_file(sq)
            adjacent_files = []
            if file > 0:
                adjacent_files.append(file - 1)
            if file < 7:
                adjacent_files.append(file + 1)
            
            has_support = False
            for adj_file in adjacent_files:
                for rank in range(8):
                    adj_sq = chess.square(adj_file, rank)
                    if adj_sq in white_pawns:
                        has_support = True
                        break
            
            if not has_support:
                isolated.append((chess.square_name(sq), "white"))
        
        for sq in black_pawns:
            file = chess.square_file(sq)
            adjacent_files = []
            if file > 0:
                adjacent_files.append(file - 1)
            if file < 7:
                adjacent_files.append(file + 1)
            
            has_support = False
            for adj_file in adjacent_files:
                for rank in range(8):
                    adj_sq = chess.square(adj_file, rank)
                    if adj_sq in black_pawns:
                        has_support = True
                        break
            
            if not has_support:
                isolated.append((chess.square_name(sq), "black"))
        
        return isolated
    
    def _find_doubled_pawns(
        self,
        board: chess.Board,
        white_pawns: List[int],
        black_pawns: List[int]
    ) -> List[Tuple[str, str]]:
        """Find doubled pawns (two pawns on same file)."""
        doubled = []
        
        # White doubled pawns
        files = {}
        for sq in white_pawns:
            f = chess.square_file(sq)
            if f not in files:
                files[f] = []
            files[f].append(sq)
        
        for f, squares in files.items():
            if len(squares) > 1:
                for sq in squares:
                    doubled.append((chess.square_name(sq), "white"))
        
        # Black doubled pawns
        files = {}
        for sq in black_pawns:
            f = chess.square_file(sq)
            if f not in files:
                files[f] = []
            files[f].append(sq)
        
        for f, squares in files.items():
            if len(squares) > 1:
                for sq in squares:
                    doubled.append((chess.square_name(sq), "black"))
        
        return doubled
    
    def _find_backward_pawns(
        self,
        board: chess.Board,
        white_pawns: List[int],
        black_pawns: List[int]
    ) -> List[Tuple[str, str]]:
        """Find backward pawns (behind adjacent pawns and can't advance safely)."""
        backward = []
        
        # Simplified: a pawn is backward if pawns on adjacent files are more advanced
        for sq in white_pawns:
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            
            adjacent_files = []
            if file > 0:
                adjacent_files.append(file - 1)
            if file < 7:
                adjacent_files.append(file + 1)
            
            is_backward = False
            for adj_file in adjacent_files:
                for adj_sq in white_pawns:
                    if chess.square_file(adj_sq) == adj_file:
                        if chess.square_rank(adj_sq) > rank + 1:  # Significantly more advanced
                            is_backward = True
            
            if is_backward and rank < 5:  # Not too advanced to be backward
                backward.append((chess.square_name(sq), "white"))
        
        for sq in black_pawns:
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            
            adjacent_files = []
            if file > 0:
                adjacent_files.append(file - 1)
            if file < 7:
                adjacent_files.append(file + 1)
            
            is_backward = False
            for adj_file in adjacent_files:
                for adj_sq in black_pawns:
                    if chess.square_file(adj_sq) == adj_file:
                        if chess.square_rank(adj_sq) < rank - 1:
                            is_backward = True
            
            if is_backward and rank > 2:
                backward.append((chess.square_name(sq), "black"))
        
        return backward
    
    def _find_passed_pawns(
        self,
        board: chess.Board,
        white_pawns: List[int],
        black_pawns: List[int]
    ) -> List[Tuple[str, str]]:
        """Find passed pawns (no enemy pawns can stop them)."""
        passed = []
        
        for sq in white_pawns:
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            
            is_passed = True
            # Check if any black pawn can stop it
            for black_sq in black_pawns:
                black_file = chess.square_file(black_sq)
                black_rank = chess.square_rank(black_sq)
                
                # Black pawn blocks if on same or adjacent file AND ahead
                if abs(black_file - file) <= 1 and black_rank > rank:
                    is_passed = False
                    break
            
            if is_passed and rank >= 3:  # Must be somewhat advanced
                passed.append((chess.square_name(sq), "white"))
        
        for sq in black_pawns:
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            
            is_passed = True
            for white_sq in white_pawns:
                white_file = chess.square_file(white_sq)
                white_rank = chess.square_rank(white_sq)
                
                if abs(white_file - file) <= 1 and white_rank < rank:
                    is_passed = False
                    break
            
            if is_passed and rank <= 4:
                passed.append((chess.square_name(sq), "black"))
        
        return passed
    
    def _find_pawn_chains(
        self,
        board: chess.Board,
        white_pawns: List[int],
        black_pawns: List[int]
    ) -> List[Dict]:
        """Find pawn chains (diagonal pawn connections)."""
        chains = []
        
        # Find white chains
        white_chain = []
        for sq in sorted(white_pawns, key=lambda s: chess.square_rank(s)):
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            
            # Check if this pawn is supported by a pawn diagonally behind
            for supporter in white_pawns:
                sup_file = chess.square_file(supporter)
                sup_rank = chess.square_rank(supporter)
                if abs(sup_file - file) == 1 and sup_rank == rank - 1:
                    white_chain.append(chess.square_name(sq))
                    break
        
        if len(white_chain) >= 2:
            chains.append({
                "color": "white",
                "pawns": white_chain,
                "base": white_chain[0],
                "teaching": "Attack the BASE of the chain, not the head!"
            })
        
        # Find black chains
        black_chain = []
        for sq in sorted(black_pawns, key=lambda s: -chess.square_rank(s)):
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            
            for supporter in black_pawns:
                sup_file = chess.square_file(supporter)
                sup_rank = chess.square_rank(supporter)
                if abs(sup_file - file) == 1 and sup_rank == rank + 1:
                    black_chain.append(chess.square_name(sq))
                    break
        
        if len(black_chain) >= 2:
            chains.append({
                "color": "black",
                "pawns": black_chain,
                "base": black_chain[0],
                "teaching": "Attack the BASE of the chain, not the head!"
            })
        
        return chains
    
    def _find_outposts(
        self,
        board: chess.Board,
        white_pawns: List[int],
        black_pawns: List[int]
    ) -> List[str]:
        """Find outpost squares (squares that can't be attacked by enemy pawns)."""
        outposts = []
        
        # Good outpost squares for White (can't be attacked by Black pawns)
        for file in range(8):
            for rank in range(3, 6):  # Central ranks
                sq = chess.square(file, rank)
                
                # Check if any black pawn can attack this square
                can_be_attacked = False
                for black_sq in black_pawns:
                    black_file = chess.square_file(black_sq)
                    black_rank = chess.square_rank(black_sq)
                    
                    # Black pawn could attack if on adjacent file and behind
                    if abs(black_file - file) == 1 and black_rank > rank:
                        can_be_attacked = True
                        break
                
                if not can_be_attacked:
                    # It's an outpost if it's also protected by our pawns
                    for white_sq in white_pawns:
                        white_file = chess.square_file(white_sq)
                        white_rank = chess.square_rank(white_sq)
                        if abs(white_file - file) == 1 and white_rank == rank - 1:
                            outposts.append(chess.square_name(sq) + " (for White)")
                            break
        
        return outposts[:4]  # Limit to most relevant
    
    def _find_weak_squares(
        self,
        board: chess.Board,
        white_pawns: List[int],
        black_pawns: List[int]
    ) -> List[str]:
        """Find weak squares (holes in pawn structure)."""
        weak = []
        
        # Weak squares are typically in front of backward/missing pawns
        # For now, identify squares that can't be defended by pawns
        
        # Check d5, e5, d4, e4 (key central squares)
        key_squares = [chess.D5, chess.E5, chess.D4, chess.E4, chess.C5, chess.C4]
        
        for sq in key_squares:
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            
            # Check if White can defend with pawns
            white_can_defend = False
            for white_sq in white_pawns:
                w_file = chess.square_file(white_sq)
                w_rank = chess.square_rank(white_sq)
                if abs(w_file - file) == 1 and w_rank == rank - 1:
                    white_can_defend = True
            
            # Check if Black can defend with pawns
            black_can_defend = False
            for black_sq in black_pawns:
                b_file = chess.square_file(black_sq)
                b_rank = chess.square_rank(black_sq)
                if abs(b_file - file) == 1 and b_rank == rank + 1:
                    black_can_defend = True
            
            if not white_can_defend and rank >= 4:
                weak.append(chess.square_name(sq) + " (weak for White)")
            if not black_can_defend and rank <= 3:
                weak.append(chess.square_name(sq) + " (weak for Black)")
        
        return weak[:4]


def get_structure_teaching(analysis: StructureAnalysis, for_color: str = "white") -> Dict:
    """
    Get teaching content for the current structure.
    
    Args:
        analysis: StructureAnalysis from classifier
        for_color: "white" or "black"
        
    Returns:
        Teaching content dictionary
    """
    plans = analysis.white_plans if for_color == "white" else analysis.black_plans
    
    return {
        "structure_name": analysis.structure_name,
        "your_plans": plans,
        "opponent_plans": analysis.black_plans if for_color == "white" else analysis.white_plans,
        "key_concepts": analysis.key_concepts,
        "piece_placement": analysis.piece_placement.get(for_color, {}),
        "outposts": [o for o in analysis.outposts if for_color in o.lower()],
        "weaknesses_to_target": [f.square for f in analysis.features if f.color != for_color and f.is_weakness],
        "your_weaknesses": [f.square for f in analysis.features if f.color == for_color and f.is_weakness],
        "common_mistakes": analysis.common_mistakes,
        "famous_examples": analysis.famous_examples
    }
