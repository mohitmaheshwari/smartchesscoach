"""
Structure & Plan Database
=========================

Maps pawn structures to concrete strategic plans with teaching content.
This is the "chess knowledge" that makes coaching human-like.

The database contains:
1. Structure identification patterns
2. Typical plans for both sides
3. Key maneuvers and piece placements
4. Common mistakes to avoid
5. Famous game examples
6. Teaching explanations in plain language

Usage:
    db = StructurePlanDatabase()
    plans = db.get_plans_for_structure("sicilian_scheveningen", "white")
    teaching = db.get_teaching_content("isolated_queen_pawn")
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


@dataclass
class StrategicPlan:
    """A concrete strategic plan for a position type."""
    name: str
    description: str
    key_moves: List[str]  # Typical move sequences
    piece_maneuvers: List[str]  # Key piece repositioning
    pawn_breaks: List[str]  # Important pawn advances
    when_to_use: str  # Conditions for this plan
    what_to_avoid: List[str]  # Common mistakes
    teaching_explanation: str  # Plain language explanation


@dataclass
class StructureTeaching:
    """Complete teaching content for a structure type."""
    structure_name: str
    structure_type: str
    
    # Core understanding
    main_idea: str
    key_characteristics: List[str]
    
    # Plans for both sides
    white_plans: List[StrategicPlan]
    black_plans: List[StrategicPlan]
    
    # Piece placement
    ideal_piece_placement: Dict[str, List[str]]  # {"N": ["d5"], "B": ["g2"]}
    
    # Key squares
    critical_squares: List[str]
    outposts: List[str]
    weak_squares: List[str]
    
    # Teaching content
    teaching_points: List[str]
    common_mistakes: List[str]
    famous_games: List[str]
    
    # Difficulty and prerequisites
    difficulty: str  # "beginner", "intermediate", "advanced"
    prerequisites: List[str]  # Concepts student should know first


class StructurePlanDatabase:
    """
    Database of strategic plans mapped to pawn structures.
    Contains ~20 common structures with detailed teaching content.
    """
    
    def __init__(self):
        """Initialize the database with all structure plans."""
        self.structures = self._build_database()
    
    def get_structure(self, structure_type: str) -> Optional[StructureTeaching]:
        """Get teaching content for a structure type."""
        return self.structures.get(structure_type)
    
    def get_plans_for_structure(
        self, 
        structure_type: str, 
        color: str
    ) -> List[StrategicPlan]:
        """Get strategic plans for a specific color."""
        structure = self.structures.get(structure_type)
        if not structure:
            return []
        
        if color.lower() == "white":
            return structure.white_plans
        else:
            return structure.black_plans
    
    def get_teaching_content(self, structure_type: str) -> Dict:
        """Get teaching content in dictionary format."""
        structure = self.structures.get(structure_type)
        if not structure:
            return {"error": f"Unknown structure: {structure_type}"}
        
        return {
            "name": structure.structure_name,
            "type": structure.structure_type,
            "main_idea": structure.main_idea,
            "key_characteristics": structure.key_characteristics,
            "teaching_points": structure.teaching_points,
            "common_mistakes": structure.common_mistakes,
            "famous_games": structure.famous_games,
            "difficulty": structure.difficulty,
            "white_plans": [
                {
                    "name": p.name,
                    "description": p.description,
                    "key_moves": p.key_moves,
                    "teaching": p.teaching_explanation
                }
                for p in structure.white_plans
            ],
            "black_plans": [
                {
                    "name": p.name,
                    "description": p.description,
                    "key_moves": p.key_moves,
                    "teaching": p.teaching_explanation
                }
                for p in structure.black_plans
            ],
            "critical_squares": structure.critical_squares,
            "piece_placement": structure.ideal_piece_placement
        }
    
    def list_all_structures(self) -> List[str]:
        """List all available structure types."""
        return list(self.structures.keys())
    
    def get_structure_by_difficulty(self, difficulty: str) -> List[str]:
        """Get structures filtered by difficulty level."""
        return [
            name for name, s in self.structures.items()
            if s.difficulty == difficulty
        ]
    
    def _build_database(self) -> Dict[str, StructureTeaching]:
        """Build the complete structure database."""
        return {
            # ============================================
            # ISOLATED QUEEN PAWN (IQP)
            # ============================================
            "isolated_queen_pawn": StructureTeaching(
                structure_name="Isolated Queen Pawn (IQP)",
                structure_type="isolated_queen_pawn",
                main_idea="White has an isolated d4 pawn - a dynamic weakness that provides active piece play",
                key_characteristics=[
                    "White pawn on d4 with no pawns on c or e files",
                    "d5 is a powerful blockade square for Black",
                    "e5 and c5 are strong outposts for White pieces",
                    "In the middlegame, activity compensates for the weakness",
                    "In the endgame, the IQP becomes a serious liability"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Kingside Attack",
                        description="Use active pieces to attack Black's king",
                        key_moves=["Qd3", "Bc2", "Re1", "Ne5"],
                        piece_maneuvers=["Nf3-e5", "Bc2-Qd3 battery", "Rf1-e1"],
                        pawn_breaks=["d4-d5 at the right moment"],
                        when_to_use="When Black's king is castled kingside and pieces are active",
                        what_to_avoid=["Trading pieces unnecessarily", "Pushing d5 too early"],
                        teaching_explanation="The IQP gives you active pieces. Use them to attack before Black can blockade and trade down to an endgame where your d4 pawn is weak."
                    ),
                    StrategicPlan(
                        name="d4-d5 Breakthrough",
                        description="Advance the d-pawn to open lines and create passed pawns",
                        key_moves=["d4-d5", "exd5", "Nxd5"],
                        piece_maneuvers=["Prepare d5 with pieces on active squares"],
                        pawn_breaks=["d4-d5 when it wins material or opens lines"],
                        when_to_use="When d5 wins a piece, opens lines to the king, or creates a passed pawn",
                        what_to_avoid=["Playing d5 when it just loses the pawn"],
                        teaching_explanation="The d4-d5 push is your trump card. Time it right - usually when your pieces are more active than Black's, or when it creates concrete threats."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Blockade Strategy",
                        description="Place a knight on d5 to block the IQP and neutralize White's activity",
                        key_moves=["Nd5", "Bd6", "Re8"],
                        piece_maneuvers=["Nf6-d5 blockade", "Control d5 with bishops"],
                        pawn_breaks=["c6-c5 to challenge the center"],
                        when_to_use="As the default strategy against IQP",
                        what_to_avoid=["Allowing d4-d5", "Trading the blockading knight"],
                        teaching_explanation="The knight on d5 is your hero. It blocks the pawn and can't be chased away by pawns. From d5, it controls key squares and limits White's play."
                    ),
                    StrategicPlan(
                        name="Trade Down to Endgame",
                        description="Exchange pieces to reach an endgame where the IQP is a clear weakness",
                        key_moves=["Trade minor pieces", "Trade queens if possible"],
                        piece_maneuvers=["Simplify while maintaining blockade"],
                        pawn_breaks=[],
                        when_to_use="When you've established the blockade and White's attack has stalled",
                        what_to_avoid=["Trading your blockading piece first"],
                        teaching_explanation="In the endgame, the IQP can't move forward and needs constant defense. Trade pieces, but keep your blockading knight as long as possible."
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["e5", "c3"], "B": ["c2", "g5"], "R": ["e1", "d1"], "Q": ["d3", "h5"]},
                    "black": {"N": ["d5", "f6"], "B": ["e7", "b7"], "R": ["e8", "c8"], "Q": ["c7"]}
                },
                critical_squares=["d4", "d5", "e5", "c5"],
                outposts=["d5 (for Black)", "e5 (for White)", "c5 (for White)"],
                weak_squares=["d4 (the IQP itself)"],
                teaching_points=[
                    "The IQP is like a coin with two sides - strength in middlegame, weakness in endgame",
                    "White should play actively and avoid piece trades",
                    "Black should blockade on d5 and aim for piece trades",
                    "The d4-d5 advance is White's main trump - time it carefully",
                    "The side with more pieces usually prefers this structure"
                ],
                common_mistakes=[
                    "White: Trading into an endgame where d4 is weak",
                    "White: Pushing d5 without preparation",
                    "Black: Allowing d4-d5 breakthrough",
                    "Black: Not establishing a blockade quickly enough"
                ],
                famous_games=[
                    "Kasparov vs Karpov, World Championship 1985",
                    "Botvinnik's IQP masterpieces",
                    "Rubinstein's classic games"
                ],
                difficulty="intermediate",
                prerequisites=["Basic pawn structure understanding", "Piece activity concepts"]
            ),
            
            # ============================================
            # FRENCH ADVANCE
            # ============================================
            "french_advance": StructureTeaching(
                structure_name="French Advance",
                structure_type="french_advance",
                main_idea="White has space with e5 pawn, Black attacks the base of the pawn chain",
                key_characteristics=[
                    "White pawn on e5, Black pawns on d5 and e6",
                    "White has space advantage on the kingside",
                    "Black's light-squared bishop is often restricted",
                    "d4 is the base of White's pawn chain - Black's target",
                    "Black plays ...c5 to attack the chain's base"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Kingside Attack",
                        description="Attack on the kingside where you have more space",
                        key_moves=["f4", "Nf3-h4-f5", "g4-g5"],
                        piece_maneuvers=["Nf3-h4-f5", "Bd3", "Qh5"],
                        pawn_breaks=["f4-f5 to open the f-file"],
                        when_to_use="When Black has castled kingside",
                        what_to_avoid=["Losing the e5 pawn without compensation"],
                        teaching_explanation="You have more space on the kingside - use it! The f4-f5 break opens lines against Black's king. Keep your e5 pawn supported."
                    ),
                    StrategicPlan(
                        name="Central Control",
                        description="Maintain the e5 pawn and restrict Black's pieces",
                        key_moves=["c3", "Nf3", "Be3", "Nd2-f3"],
                        piece_maneuvers=["Support e5 with pieces"],
                        pawn_breaks=[],
                        when_to_use="When Black is trying to break with ...f6",
                        what_to_avoid=["Overextending without piece support"],
                        teaching_explanation="The e5 pawn restricts Black's position. Keep it defended and don't let Black play ...f6 easily. Your pieces have more room to maneuver."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Attack the Chain's Base",
                        description="Play ...c5 to attack d4, the base of White's pawn chain",
                        key_moves=["c5", "cxd4", "Nc6", "Qb6"],
                        piece_maneuvers=["Nc6-a5-c4", "Qb6 pressure on d4"],
                        pawn_breaks=["c5 is the main break"],
                        when_to_use="Standard strategy - start early",
                        what_to_avoid=["Attacking e5 directly instead of d4"],
                        teaching_explanation="Attack the BASE of the chain (d4), not the head (e5). This is Nimzowitsch's rule! If d4 falls, the whole chain collapses."
                    ),
                    StrategicPlan(
                        name="f6 Break",
                        description="Challenge the e5 pawn with ...f6",
                        key_moves=["f6", "exf6", "Nxf6"],
                        piece_maneuvers=["Prepare ...f6 with piece development"],
                        pawn_breaks=["f6 to challenge e5 directly"],
                        when_to_use="When ...c5 isn't working or to open the f-file",
                        what_to_avoid=["Playing ...f6 when White is ready for kingside attack"],
                        teaching_explanation="The ...f6 break challenges e5 directly and activates your pieces. But be careful - it can weaken your king if White is ready to attack."
                    ),
                    StrategicPlan(
                        name="Activate the Bad Bishop",
                        description="Solve the problem of the light-squared bishop",
                        key_moves=["b6", "Ba6", "Bd7-b5"],
                        piece_maneuvers=["Bc8-d7-b5 or Bc8-a6"],
                        pawn_breaks=[],
                        when_to_use="After basic development is done",
                        what_to_avoid=["Leaving the bishop passive on c8"],
                        teaching_explanation="Your bishop on c8 is blocked by your own pawns - it's the 'French bishop problem'. Get it out via a6 or b5 to make it useful."
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["f3", "d2"], "B": ["d3", "e3"], "R": ["f1", "e1"]},
                    "black": {"N": ["c6", "h6", "e7"], "B": ["a6", "e7"], "R": ["c8", "f8"]}
                },
                critical_squares=["d4", "e5", "f5", "c4"],
                outposts=["f5 (for White)", "c4 (for Black)", "e5 (pawn)"],
                weak_squares=["d4 (base of chain)", "light squares around Black's king"],
                teaching_points=[
                    "Always attack the BASE of a pawn chain, not the head",
                    "Black's light-squared bishop is the 'problem piece' - activate it",
                    "White has space but must be careful not to overextend",
                    "The ...c5 break is Black's main idea",
                    "Both sides often castle opposite sides"
                ],
                common_mistakes=[
                    "Black: Attacking e5 instead of d4",
                    "Black: Forgetting to activate the Bc8",
                    "White: Overextending with f4-f5 without preparation",
                    "White: Losing the e5 pawn without compensation"
                ],
                famous_games=[
                    "Nimzowitsch's games explaining pawn chains",
                    "Short vs Timman, Tilburg 1991",
                    "Many Korchnoi games"
                ],
                difficulty="intermediate",
                prerequisites=["Pawn chain concept", "Attack and defense basics"]
            ),
            
            # ============================================
            # SICILIAN SCHEVENINGEN
            # ============================================
            "sicilian_scheveningen": StructureTeaching(
                structure_name="Sicilian Scheveningen",
                structure_type="sicilian_scheveningen",
                main_idea="Black has a small center (e6+d6), White attacks the d5 square and kingside",
                key_characteristics=[
                    "Black pawns on d6 and e6 - solid but slightly passive",
                    "d5 is the key battleground square",
                    "White often plays f4-f5 or g4-g5 attacks",
                    "Black aims for ...d5 or ...e5 central breaks",
                    "Opposite-side castling leads to mutual attacks"
                ],
                white_plans=[
                    StrategicPlan(
                        name="f4-f5 Attack",
                        description="Push f4-f5 to open the f-file against Black's king",
                        key_moves=["f4", "f5", "fxe6"],
                        piece_maneuvers=["Be3", "Qd2", "0-0-0", "Rhf1"],
                        pawn_breaks=["f4-f5 is the main break"],
                        when_to_use="When Black has castled kingside",
                        what_to_avoid=["Playing f5 when Black can capture favorably"],
                        teaching_explanation="The f4-f5 push opens lines against Black's king. After fxe6, Black's pawn structure is weakened and your rook gets the f-file."
                    ),
                    StrategicPlan(
                        name="Nd5 Sacrifice",
                        description="Sacrifice the knight on d5 to destroy Black's pawn structure",
                        key_moves=["Nd5", "exd5", "Qxd5"],
                        piece_maneuvers=["Nc3-d5"],
                        pawn_breaks=[],
                        when_to_use="When the knight sacrifice leads to a strong attack",
                        what_to_avoid=["Sacrificing without clear compensation"],
                        teaching_explanation="The Nd5 sacrifice is a classic Sicilian theme. After exd5, Black's pawns are ruined and your pieces flood in. Calculate carefully!"
                    ),
                    StrategicPlan(
                        name="English Attack (g4-g5)",
                        description="Storm the kingside with g4-g5-g6",
                        key_moves=["g4", "g5", "h4", "g6"],
                        piece_maneuvers=["Be3", "Qd2", "0-0-0", "Rg1"],
                        pawn_breaks=["g4-g5-g6 pawn storm"],
                        when_to_use="When you want a direct kingside attack",
                        what_to_avoid=["Ignoring Black's queenside counterplay"],
                        teaching_explanation="The English Attack is brutal. Push your g and h pawns forward while Black tries to break through on the queenside. It's a race!"
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Queenside Counterplay",
                        description="Attack on the queenside with ...a6, ...b5, ...b4",
                        key_moves=["a6", "b5", "b4"],
                        piece_maneuvers=["Nc6-a5-c4", "Rb8"],
                        pawn_breaks=["b5-b4 to attack White's knight"],
                        when_to_use="Standard counterplay against opposite-side castling",
                        what_to_avoid=["Being too slow - the kingside attack can be deadly"],
                        teaching_explanation="When White castles queenside, you attack there! Push ...a6 and ...b5-b4 to open lines. Speed is critical - you're racing White's kingside attack."
                    ),
                    StrategicPlan(
                        name="Central Break with ...d5",
                        description="Strike in the center with ...d5 to challenge White's control",
                        key_moves=["d5", "exd5", "Nxd5"],
                        piece_maneuvers=["Prepare ...d5 with piece development"],
                        pawn_breaks=["d5 when well prepared"],
                        when_to_use="When you've developed and White's center is loose",
                        what_to_avoid=["Playing ...d5 too early when it loses a pawn"],
                        teaching_explanation="The ...d5 break is your main freeing move. Time it right - you need your pieces developed and White's center vulnerable. It often leads to exchanges."
                    ),
                    StrategicPlan(
                        name="e5 Break",
                        description="Play ...e5 to gain central space",
                        key_moves=["e5", "d5"],
                        piece_maneuvers=["Support ...e5 with pieces"],
                        pawn_breaks=["e5 when d4 is weak"],
                        when_to_use="When you can gain central space safely",
                        what_to_avoid=["Playing ...e5 when it weakens d5 and d6"],
                        teaching_explanation="The ...e5 break gives you more space, but be careful - it can weaken the d5 square. Make sure your pieces can support the center."
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["d5", "f3"], "B": ["e3", "c4"], "R": ["d1", "f1"], "Q": ["d2"]},
                    "black": {"N": ["c6", "f6", "d7"], "B": ["e7", "b7"], "R": ["c8", "d8"], "Q": ["c7"]}
                },
                critical_squares=["d5", "e4", "c4", "f5"],
                outposts=["d5 (key square for both sides)", "c4 (for Black knights)"],
                weak_squares=["d5 (if Black plays ...e5)", "e6 (if weakened)"],
                teaching_points=[
                    "d5 is THE key square - whoever controls it has the advantage",
                    "Opposite-side castling leads to mutual attacks - speed matters",
                    "Black's e6-d6 setup is solid but slightly passive",
                    "The Nd5 sacrifice is a recurring tactical theme",
                    "Both sides need to balance attack and defense"
                ],
                common_mistakes=[
                    "Black: Playing ...e5 too early and weakening d5",
                    "Black: Being too slow with queenside counterplay",
                    "White: Attacking without securing the center",
                    "White: Ignoring Black's ...b5-b4 counterplay"
                ],
                famous_games=[
                    "Kasparov vs Karpov, World Championship matches",
                    "Fischer's Sicilian games",
                    "Tal's attacking masterpieces"
                ],
                difficulty="intermediate",
                prerequisites=["Basic Sicilian understanding", "Opposite-side castling concepts"]
            ),
            
            # ============================================
            # KING'S INDIAN DEFENSE
            # ============================================
            "kings_indian": StructureTeaching(
                structure_name="King's Indian Defense",
                structure_type="kings_indian",
                main_idea="Black fianchettoes and prepares a kingside pawn storm while White expands on queenside",
                key_characteristics=[
                    "Black's bishop on g7 is the key attacking piece",
                    "White has space advantage with d4+c4 (sometimes e4)",
                    "Black aims for ...f5-f4 kingside attack",
                    "White plays c4-c5 for queenside expansion",
                    "Classic case of opposite-side attacks"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Queenside Expansion",
                        description="Push c4-c5 and expand on the queenside",
                        key_moves=["c5", "cxd6", "Nc4", "a4", "b4"],
                        piece_maneuvers=["Nc3-d5", "b4-b5"],
                        pawn_breaks=["c4-c5 is the main break"],
                        when_to_use="Standard strategy for White",
                        what_to_avoid=["Letting Black play ...f4 without counterplay"],
                        teaching_explanation="You have more space on the queenside - use it! Push c5, open lines, and create threats. Meanwhile, watch out for Black's kingside attack."
                    ),
                    StrategicPlan(
                        name="Central Control",
                        description="Keep the center closed and prevent Black's breaks",
                        key_moves=["d5", "Nd3", "f3"],
                        piece_maneuvers=["Block ...f5 with f3", "Nd2-f3 after f2-f3"],
                        pawn_breaks=[],
                        when_to_use="When you want a positional approach",
                        what_to_avoid=["Opening the center when Black's pieces are active"],
                        teaching_explanation="Keep the center closed to limit Black's Bg7. Play f3 to stop ...f5, and slowly improve your position. This is a patient approach."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="f5-f4 Kingside Attack",
                        description="Storm the kingside with the f-pawn",
                        key_moves=["f5", "f4", "g5", "Rf7", "Nf6-h5-f4"],
                        piece_maneuvers=["Nf6-h5-f4", "Rf8-f7-g7", "Qe8-h5"],
                        pawn_breaks=["f5-f4-f3 is the dream"],
                        when_to_use="The main plan in most KID positions",
                        what_to_avoid=["Playing ...f5 when White can play exf5"],
                        teaching_explanation="The ...f5-f4 attack is the heart of the KID. Push your f-pawn, bring your rook to g7, and storm the kingside. Your Bg7 supports everything!"
                    ),
                    StrategicPlan(
                        name="c6-d5 Central Break",
                        description="Strike in the center to challenge White's space",
                        key_moves=["c6", "d5", "cxd5", "cxd5"],
                        piece_maneuvers=["Prepare ...c6 and ...d5"],
                        pawn_breaks=["c6+d5 together"],
                        when_to_use="When kingside attack is not working",
                        what_to_avoid=["Playing ...d5 when it leaves d6 weak"],
                        teaching_explanation="Sometimes the kingside attack is blocked. Then switch to the center! ...c6 and ...d5 challenge White's space advantage and activate your pieces."
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["c3", "f3", "d5"], "B": ["e2", "e3"], "R": ["c1", "b1"], "Q": ["c2"]},
                    "black": {"N": ["d7", "f6", "h5"], "B": ["g7", "e6"], "R": ["f8", "f7"], "Q": ["e8", "h5"]}
                },
                critical_squares=["d5", "e4", "f4", "c5"],
                outposts=["d5 (for White)", "f4 (for Black)", "e5 (contested)"],
                weak_squares=["d6 (potential Black weakness)", "g4-h3 area (if kingside opens)"],
                teaching_points=[
                    "This is a race - whoever attacks faster wins",
                    "Black's Bg7 is the most important piece",
                    "White's queenside vs Black's kingside",
                    "The ...f5-f4 push is Black's main idea",
                    "Timing is everything in the King's Indian"
                ],
                common_mistakes=[
                    "Black: Being too slow with ...f5",
                    "Black: Allowing White to play f3 and block everything",
                    "White: Castling kingside into Black's attack",
                    "White: Not developing queenside counterplay fast enough"
                ],
                famous_games=[
                    "Kasparov vs Karpov, various matches",
                    "Fischer's KID games",
                    "Nakamura's modern KID"
                ],
                difficulty="advanced",
                prerequisites=["Pawn structure basics", "Attack and defense", "Opposite-side attacks"]
            ),
            
            # ============================================
            # CARLSBAD STRUCTURE
            # ============================================
            "carlsbad_structure": StructureTeaching(
                structure_name="Carlsbad Structure",
                structure_type="carlsbad_structure",
                main_idea="Symmetric pawn structure where White plays the minority attack (b4-b5)",
                key_characteristics=[
                    "Symmetric pawns: White c3-d4-e3 vs Black c6-d5-e6",
                    "Arises from QGD Exchange variation",
                    "White's main plan is the minority attack",
                    "Black seeks counterplay on kingside or with ...c5",
                    "Strategic, positional battle"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Minority Attack",
                        description="Push b4-b5 to create a weakness on c6",
                        key_moves=["b4", "b5", "bxc6"],
                        piece_maneuvers=["Rb1", "a4", "b4-b5"],
                        pawn_breaks=["b4-b5 targeting c6"],
                        when_to_use="The standard plan in this structure",
                        what_to_avoid=["Rushing b5 before pieces are ready"],
                        teaching_explanation="The minority attack is a classic plan. Push your b-pawn to force ...cxb5, leaving Black with a weak c6 pawn. Then pile pressure on it."
                    ),
                    StrategicPlan(
                        name="Ne5 Outpost",
                        description="Establish a knight on the e5 outpost",
                        key_moves=["Ne5", "Bf4", "Qb3"],
                        piece_maneuvers=["Nf3-e5"],
                        pawn_breaks=[],
                        when_to_use="In conjunction with minority attack",
                        what_to_avoid=["Trading the e5 knight unnecessarily"],
                        teaching_explanation="The e5 square is a great outpost for your knight. From there it controls key squares and supports both the minority attack and central play."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="c5 Break",
                        description="Play ...c5 before White's minority attack develops",
                        key_moves=["c5", "cxd4", "exd4"],
                        piece_maneuvers=["Prepare ...c5 with piece development"],
                        pawn_breaks=["c5 to counter the minority attack"],
                        when_to_use="Early, before White gets b4-b5 rolling",
                        what_to_avoid=["Playing ...c5 when it creates an IQP for you"],
                        teaching_explanation="If you can play ...c5 in time, you prevent the minority attack and might even get counterplay. But be careful about creating your own IQP!"
                    ),
                    StrategicPlan(
                        name="Kingside Counterplay",
                        description="Attack on the kingside while White expands on queenside",
                        key_moves=["f6", "e5", "Qe8-h5"],
                        piece_maneuvers=["Nf6-e4", "Bd6", "Qe8-h5"],
                        pawn_breaks=["f6 and e5 to open lines"],
                        when_to_use="When minority attack is unstoppable",
                        what_to_avoid=["Overextending without piece support"],
                        teaching_explanation="If you can't stop the minority attack, create your own counterplay! The kingside is your territory. Push ...f6 and ...e5 to open lines."
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["f3", "e5"], "B": ["d3", "f4"], "R": ["b1", "c1"], "Q": ["b3"]},
                    "black": {"N": ["f6", "e4"], "B": ["d6", "e7"], "R": ["c8", "e8"], "Q": ["c7", "e8"]}
                },
                critical_squares=["c6", "e5", "e4", "c5"],
                outposts=["e5 (for White)", "e4 (for Black)"],
                weak_squares=["c6 (after bxc6)", "isolated pawns after ...c5"],
                teaching_points=[
                    "The minority attack is a fundamental strategic plan",
                    "Creating weaknesses is often better than winning material",
                    "Black must choose: prevent the attack or create counterplay",
                    "Piece activity is crucial for both sides",
                    "This structure teaches patient, strategic play"
                ],
                common_mistakes=[
                    "White: Rushing b5 without piece support",
                    "Black: Passively waiting instead of creating counterplay",
                    "Both: Underestimating the power of piece activity"
                ],
                famous_games=[
                    "Capablanca's games in the QGD Exchange",
                    "Carlsen's strategic masterpieces",
                    "Botvinnik vs Petrosian games"
                ],
                difficulty="intermediate",
                prerequisites=["Pawn structure basics", "Strategic planning"]
            ),
            
            # ============================================
            # ROOK ENDGAME BASICS
            # ============================================
            "rook_endgame": StructureTeaching(
                structure_name="Rook Endgame Fundamentals",
                structure_type="rook_endgame",
                main_idea="The most common endgame - activity is more important than material",
                key_characteristics=[
                    "Rooks need open files to be effective",
                    "The 7th rank is paradise for rooks",
                    "Rooks belong BEHIND passed pawns (yours or opponent's)",
                    "King activity becomes critical",
                    "Many rook endgames are drawn with correct technique"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Activate the Rook",
                        description="Place rook on 7th rank or behind passed pawns",
                        key_moves=["Ra7", "Rb7", "Place rook behind passed pawn"],
                        piece_maneuvers=["Rook to 7th rank", "Rook behind passed pawn"],
                        pawn_breaks=["Create a passed pawn to support"],
                        when_to_use="Always prioritize rook activity",
                        what_to_avoid=["Passive rook defending from the side"],
                        teaching_explanation="Your rook on the 7th rank attacks pawns from behind and restricts the enemy king. It's worth more than an extra pawn sometimes!"
                    ),
                    StrategicPlan(
                        name="Cut Off the King",
                        description="Use the rook to prevent enemy king from reaching the action",
                        key_moves=["Rd4 cutting off king", "Re5 keeping king at bay"],
                        piece_maneuvers=["Rook on a rank or file to block king"],
                        pawn_breaks=[],
                        when_to_use="When you have a passed pawn to push",
                        what_to_avoid=["Letting the enemy king get too close"],
                        teaching_explanation="In rook endgames, keep the enemy king away from your passed pawn. The more files you cut it off, the easier your pawn will promote."
                    ),
                    StrategicPlan(
                        name="Lucena Position",
                        description="The winning technique with rook + pawn vs rook",
                        key_moves=["King to 8th rank", "Rook on 4th rank", "Build a bridge"],
                        piece_maneuvers=["Rd1+", "Rd4 (building the bridge)", "Rf4"],
                        pawn_breaks=["Push pawn to 7th"],
                        when_to_use="When you have R+P vs R with pawn on 7th",
                        what_to_avoid=["Not knowing this technique!"],
                        teaching_explanation="The Lucena position is THE most important endgame technique. You must know how to build a bridge to shelter your king from checks. This wins 90% of R+P vs R."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Philidor Defense",
                        description="The drawing technique in R+P vs R",
                        key_moves=["Rook on 6th rank", "Then check from behind"],
                        piece_maneuvers=["Ra6 (on 3rd rank vs pawn)", "Then Ra1 checking"],
                        pawn_breaks=[],
                        when_to_use="When defending R+P vs R",
                        what_to_avoid=["Putting rook in passive position"],
                        teaching_explanation="Philidor's defense: keep your rook on the 6th rank to prevent the enemy king from advancing. Once the pawn moves to the 6th, start checking from behind. This draws!"
                    ),
                    StrategicPlan(
                        name="Active Defense",
                        description="Keep rook active even when defending",
                        key_moves=["Counterattack opponent's pawns", "Create passed pawn"],
                        piece_maneuvers=["Rook behind opponent's passed pawn"],
                        pawn_breaks=["Create your own passed pawn"],
                        when_to_use="When you're down material but can get active",
                        what_to_avoid=["Passive defense with rook stuck"],
                        teaching_explanation="Even when defending, keep your rook active! An active rook can often save a pawn-down endgame. Attack their pawns while they push theirs."
                    )
                ],
                ideal_piece_placement={
                    "white": {"R": ["7th rank", "behind passed pawns"]},
                    "black": {"R": ["6th rank for Philidor", "behind passed pawns"]}
                },
                critical_squares=["7th rank", "queening squares", "key files"],
                outposts=[],
                weak_squares=["base of pawn chains", "isolated pawns"],
                teaching_points=[
                    "Lucena and Philidor positions are MUST-KNOW",
                    "Rook activity is often worth more than a pawn",
                    "Rooks belong BEHIND passed pawns",
                    "Cut off the enemy king with your rook",
                    "The 7th rank is paradise for rooks"
                ],
                common_mistakes=[
                    "Passive rook defending from the side",
                    "Not knowing Lucena/Philidor techniques",
                    "Forgetting to activate the king",
                    "Trading into a lost pawn endgame"
                ],
                famous_games=[
                    "Philidor's original analysis (1777)",
                    "Capablanca's rook endgame technique",
                    "Carlsen's grinding technique"
                ],
                difficulty="beginner",
                prerequisites=["Basic king and pawn endgames", "Understanding of passed pawns"]
            ),
            
            # ============================================
            # KING AND PAWN ENDGAME
            # ============================================
            "king_pawn_endgame": StructureTeaching(
                structure_name="King and Pawn Endgame",
                structure_type="king_pawn_endgame",
                main_idea="The most fundamental endgame - king activity and opposition are key",
                key_characteristics=[
                    "No pieces, only kings and pawns",
                    "The king becomes a fighting piece",
                    "Opposition is the key concept",
                    "Passed pawns are decisive",
                    "One tempo can change the result"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Opposition",
                        description="Gain the opposition to breakthrough with your king",
                        key_moves=["King faces enemy king with one square between"],
                        piece_maneuvers=["King directly facing enemy king"],
                        pawn_breaks=["Shoulder check enemy king away"],
                        when_to_use="When kings are close together",
                        what_to_avoid=["Moving when you have the opposition"],
                        teaching_explanation="Opposition means your king faces their king with one square between. Whoever has to move loses! Use this to push their king away from your pawn."
                    ),
                    StrategicPlan(
                        name="Triangulation",
                        description="Waste a tempo to give the opponent the move",
                        key_moves=["K triangle maneuver"],
                        piece_maneuvers=["Move king in a triangle to lose a tempo"],
                        pawn_breaks=[],
                        when_to_use="When you need to change who has the move",
                        what_to_avoid=["Using when there's a simpler solution"],
                        teaching_explanation="Sometimes you need the opponent to move, but it's your turn. Triangulate - move your king in a triangle to 'waste' a move and give them the turn."
                    ),
                    StrategicPlan(
                        name="Key Squares",
                        description="Control key squares in front of your pawn",
                        key_moves=["King to key squares before pushing pawn"],
                        piece_maneuvers=["King controls squares the pawn needs"],
                        pawn_breaks=["Only push pawn when king controls key squares"],
                        when_to_use="In K+P vs K and similar",
                        what_to_avoid=["Pushing pawn without king support"],
                        teaching_explanation="Key squares are the squares in front of your pawn. If your king controls them, your pawn promotes. King first, pawn second - never push too early!"
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Getting Opposition",
                        description="Get opposition to stop enemy king's advance",
                        key_moves=["Face enemy king directly"],
                        piece_maneuvers=["Mirror enemy king movements"],
                        pawn_breaks=[],
                        when_to_use="When defending against a passed pawn",
                        what_to_avoid=["Losing the opposition at critical moment"],
                        teaching_explanation="As defender, try to get opposition to keep the enemy king at bay. If you have opposition, their king can't advance without giving you room."
                    ),
                    StrategicPlan(
                        name="Rule of the Square",
                        description="Calculate if your king can catch the pawn",
                        key_moves=["Count squares to queening square"],
                        piece_maneuvers=["King moves diagonally to save time"],
                        pawn_breaks=[],
                        when_to_use="When you need to stop a passed pawn",
                        what_to_avoid=["Miscounting the squares"],
                        teaching_explanation="Can your king catch the pawn? Draw a mental square from the pawn to its queening square. If your king is inside that square, you can catch it!"
                    )
                ],
                ideal_piece_placement={
                    "white": {"K": ["in front of pawn", "on key squares"]},
                    "black": {"K": ["opposition", "in the square of the pawn"]}
                },
                critical_squares=["key squares in front of passed pawns"],
                outposts=[],
                weak_squares=[],
                teaching_points=[
                    "The king is a fighting piece in the endgame",
                    "Opposition is the most important concept",
                    "Key squares: control them before pushing the pawn",
                    "One tempo can change win to draw or draw to loss",
                    "Rule of the Square: can the king catch the pawn?"
                ],
                common_mistakes=[
                    "Pushing the pawn too fast without king support",
                    "Not understanding opposition",
                    "Allowing stalemate when winning",
                    "Miscounting squares in pawn races"
                ],
                famous_games=[
                    "Any grandmaster game reaching K+P vs K",
                    "Classic opposition examples"
                ],
                difficulty="beginner",
                prerequisites=["None - this is the starting point"]
            ),
            
            # ============================================
            # OPPOSITE COLOR BISHOPS
            # ============================================
            "opposite_color_bishops": StructureTeaching(
                structure_name="Opposite Color Bishops Endgame",
                structure_type="opposite_color_bishops",
                main_idea="Often drawn even with extra pawns because bishops operate on different colors",
                key_characteristics=[
                    "Each bishop controls only one color",
                    "Bishops can never interact directly",
                    "Defending is much easier than attacking",
                    "Extra pawn doesn't guarantee a win",
                    "Attacker needs pawns on BOTH sides"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Two Weaknesses Principle",
                        description="Create passed pawns on both sides of the board",
                        key_moves=["Create pawns far apart", "Attack both flanks"],
                        piece_maneuvers=["King shuttles between two fronts"],
                        pawn_breaks=["Create passed pawns on both wings"],
                        when_to_use="When you're trying to win with extra pawn(s)",
                        what_to_avoid=["Having all pawns on one side"],
                        teaching_explanation="One bishop can't defend both sides! Create passed pawns far apart, and the defending bishop will be overwhelmed. This is the only way to win."
                    ),
                    StrategicPlan(
                        name="King Infiltration",
                        description="Use your king to attack pawns on the opposite color of your bishop",
                        key_moves=["King attacks pawns bishop can't defend"],
                        piece_maneuvers=["King to squares of enemy bishop's color"],
                        pawn_breaks=[],
                        when_to_use="When you need your king to help win pawns",
                        what_to_avoid=["Letting enemy king become too active"],
                        teaching_explanation="Your bishop can't attack pawns on the wrong color. Use your king! The king can go anywhere, while the bishop is limited."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Fortress Defense",
                        description="Set up an unbreakable blockade on your bishop's color",
                        key_moves=["Place pawns on your bishop's color", "Blockade"],
                        piece_maneuvers=["Bishop protects pawns of its color"],
                        pawn_breaks=[],
                        when_to_use="When defending a worse position",
                        what_to_avoid=["Letting pawns get pushed off defensive squares"],
                        teaching_explanation="Put your pawns on your bishop's color squares. The bishop defends them, and the enemy bishop can never attack them. Fortress!"
                    ),
                    StrategicPlan(
                        name="Active King Defense",
                        description="Use your king actively to support defense",
                        key_moves=["King helps defend weak pawns"],
                        piece_maneuvers=["King covers squares bishop can't"],
                        pawn_breaks=[],
                        when_to_use="When you need to defend on both sides",
                        what_to_avoid=["Letting king get cut off"],
                        teaching_explanation="Your bishop can't be everywhere. Use your king to defend the side your bishop isn't covering. Together, they can hold the fortress."
                    )
                ],
                ideal_piece_placement={
                    "white": {"B": ["active diagonal"], "K": ["attacking weak pawns"]},
                    "black": {"B": ["defensive diagonal"], "K": ["supporting defense"]}
                },
                critical_squares=["squares of each bishop's color"],
                outposts=[],
                weak_squares=["pawns on the wrong color"],
                teaching_points=[
                    "Extra pawn doesn't guarantee a win here",
                    "Attacker needs threats on BOTH sides of the board",
                    "Defender should blockade on their bishop's color",
                    "The fortress setup can save apparently lost positions",
                    "These endgames are often drawn in practice"
                ],
                common_mistakes=[
                    "Attacker: Keeping pawns only on one side",
                    "Attacker: Assuming extra pawn automatically wins",
                    "Defender: Placing pawns on wrong color squares",
                    "Defender: Not setting up a proper blockade"
                ],
                famous_games=[
                    "Many GM draws from 'won' positions",
                    "World Championship games with this endgame"
                ],
                difficulty="intermediate",
                prerequisites=["Basic bishop endgames", "Pawn structure concepts"]
            )
        }
    
    def get_plan_for_situation(
        self,
        structure_type: str,
        color: str,
        game_phase: str,
        student_rating: int
    ) -> Optional[StrategicPlan]:
        """Get the most relevant plan for the current situation."""
        plans = self.get_plans_for_structure(structure_type, color)
        
        if not plans:
            return None
        
        # For beginners, return the simplest plan (first one)
        if student_rating < 1200:
            return plans[0]
        
        # For intermediate, consider all plans
        # In a real system, we'd use position analysis to pick the best
        return plans[0]


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def get_structure_plans(
    structure_type: str,
    color: str = "white"
) -> Dict:
    """
    Get strategic plans for a structure type.
    
    Args:
        structure_type: Type of pawn structure
        color: "white" or "black"
        
    Returns:
        Dict with plans and teaching content
    """
    db = StructurePlanDatabase()
    
    structure = db.get_structure(structure_type)
    if not structure:
        return {
            "error": f"Unknown structure: {structure_type}",
            "available": db.list_all_structures()
        }
    
    plans = db.get_plans_for_structure(structure_type, color)
    
    return {
        "structure_name": structure.structure_name,
        "main_idea": structure.main_idea,
        "for_color": color,
        "plans": [
            {
                "name": p.name,
                "description": p.description,
                "key_moves": p.key_moves,
                "piece_maneuvers": p.piece_maneuvers,
                "pawn_breaks": p.pawn_breaks,
                "when_to_use": p.when_to_use,
                "what_to_avoid": p.what_to_avoid,
                "teaching": p.teaching_explanation
            }
            for p in plans
        ],
        "teaching_points": structure.teaching_points,
        "common_mistakes": structure.common_mistakes,
        "famous_games": structure.famous_games
    }


def get_all_structures() -> List[Dict]:
    """Get a list of all available structures with basic info."""
    db = StructurePlanDatabase()
    
    return [
        {
            "type": name,
            "name": structure.structure_name,
            "main_idea": structure.main_idea,
            "difficulty": structure.difficulty
        }
        for name, structure in db.structures.items()
    ]
