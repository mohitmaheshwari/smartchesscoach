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
            ),
            
            # ============================================
            # QUEEN'S GAMBIT DECLINED
            # ============================================
            "queens_gambit_declined": StructureTeaching(
                structure_name="Queen's Gambit Declined",
                structure_type="queens_gambit_declined",
                main_idea="Black maintains solid central pawn structure with d5-e6, White has space advantage",
                key_characteristics=[
                    "Black pawns on d5 and e6 - solid but slightly cramped",
                    "White controls more space with d4-c4",
                    "The c8 bishop is often Black's problem piece",
                    "White often develops with Bg5, pinning the knight",
                    "Both sides often castle kingside"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Minority Attack",
                        description="Push b4-b5 to create weaknesses on Black's queenside",
                        key_moves=["b4", "b5", "bxc6"],
                        piece_maneuvers=["Rb1", "a4-b4-b5"],
                        pawn_breaks=["b4-b5 targeting c6"],
                        when_to_use="After exchanging on d5 (Carlsbad structure)",
                        what_to_avoid=["Rushing b5 without preparation"],
                        teaching_explanation="The minority attack creates a weakness on c6. You attack with fewer pawns to create an isolated pawn or backward pawn for Black."
                    ),
                    StrategicPlan(
                        name="Central Pressure",
                        description="Maintain tension and pressure Black's center",
                        key_moves=["Rc1", "Qc2", "e4 break"],
                        piece_maneuvers=["Nf3-e5", "Bd3"],
                        pawn_breaks=["e3-e4 to challenge d5"],
                        when_to_use="When Black hasn't equalized",
                        what_to_avoid=["Releasing tension too early"],
                        teaching_explanation="Keep the tension in the center. Black is slightly cramped, so don't let them free their position with easy exchanges."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Freeing Break with ...c5",
                        description="Play ...c5 to challenge White's center and free the position",
                        key_moves=["c5", "cxd4", "exd4"],
                        piece_maneuvers=["Nc6-b4", "Bb7"],
                        pawn_breaks=["c5 is the main freeing break"],
                        when_to_use="Standard freeing plan",
                        what_to_avoid=["Playing ...c5 when it loses a pawn"],
                        teaching_explanation="The ...c5 break is your key to equality. It challenges White's center and frees your pieces. Time it right!"
                    ),
                    StrategicPlan(
                        name="Develop the Bad Bishop",
                        description="Activate the light-squared bishop which is blocked by e6",
                        key_moves=["b6", "Bb7", "Bd7-b5"],
                        piece_maneuvers=["Bc8-d7-b5 or Bc8-a6"],
                        pawn_breaks=[],
                        when_to_use="After basic development",
                        what_to_avoid=["Leaving the bishop passive on c8"],
                        teaching_explanation="Your c8 bishop is blocked by your own pawns. Get it out via b7 or a6 to make it active."
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["f3", "d2"], "B": ["d3", "g5"], "R": ["c1", "e1"]},
                    "black": {"N": ["f6", "d7"], "B": ["e7", "b7"], "R": ["c8", "e8"]}
                },
                critical_squares=["d5", "e4", "c5"],
                outposts=["e5 (for White)", "e4 (for Black after ...c5)"],
                weak_squares=["c6 (after minority attack)", "e6"],
                teaching_points=[
                    "Black's position is solid but slightly cramped",
                    "The c8 bishop is the 'problem piece' - activate it",
                    "...c5 is Black's main freeing break",
                    "White often plays for the minority attack",
                    "Don't release central tension without a good reason"
                ],
                common_mistakes=[
                    "Black: Leaving the c8 bishop passive",
                    "Black: Playing ...c5 too early or too late",
                    "White: Exchanging pieces when you have more space",
                    "White: Not exploiting Black's cramped position"
                ],
                famous_games=[
                    "Capablanca's games in the QGD",
                    "Karpov vs Kasparov World Championship matches",
                    "Carlsen's QGD games"
                ],
                difficulty="intermediate",
                prerequisites=["Basic opening principles", "Pawn structure concepts"]
            ),
            
            # ============================================
            # CARO-KANN DEFENSE
            # ============================================
            "caro_kann": StructureTeaching(
                structure_name="Caro-Kann Defense",
                structure_type="caro_kann",
                main_idea="Black gets a solid position with good light-squared bishop, but less central control",
                key_characteristics=[
                    "Black plays ...c6 to support ...d5",
                    "Unlike the French, Black's light-squared bishop is NOT blocked",
                    "White often gets more space but Black is solid",
                    "The c6 pawn can become a target",
                    "Black often plays ...Bf5 early to develop actively"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Advance Variation Attack",
                        description="Push e5 and attack on the kingside",
                        key_moves=["e5", "f4", "Nf3", "Be3"],
                        piece_maneuvers=["Nd2-f3", "Be2", "0-0"],
                        pawn_breaks=["f4-f5 to open lines"],
                        when_to_use="In the Advance variation",
                        what_to_avoid=["Overextending without piece support"],
                        teaching_explanation="With e5, you gain space. Use it to attack on the kingside. But watch out for Black's counterplay against d4."
                    ),
                    StrategicPlan(
                        name="Classical Development",
                        description="Develop naturally and maintain central control",
                        key_moves=["Nc3", "Nf3", "Bd3", "0-0"],
                        piece_maneuvers=["Natural development"],
                        pawn_breaks=["c3 to support d4"],
                        when_to_use="In the Classical variation",
                        what_to_avoid=["Allowing Black to equalize easily"],
                        teaching_explanation="Develop your pieces to good squares and castle. Your space advantage is small but real. Don't let Black equalize easily."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Solid Development with ...Bf5",
                        description="Develop the bishop actively before playing ...e6",
                        key_moves=["Bf5", "e6", "Nf6", "Be7"],
                        piece_maneuvers=["Bc8-f5 BEFORE ...e6"],
                        pawn_breaks=["c5 break when appropriate"],
                        when_to_use="Standard Caro-Kann development",
                        what_to_avoid=["Blocking the bishop with ...e6 too early"],
                        teaching_explanation="The beauty of the Caro-Kann: develop your bishop to f5 BEFORE playing ...e6. This is why it's better than the French for the light-squared bishop."
                    ),
                    StrategicPlan(
                        name="Counterattack on d4",
                        description="Target White's d4 pawn with ...c5",
                        key_moves=["c5", "Nc6", "Qb6"],
                        piece_maneuvers=["Nc6 attacking d4", "Qb6 pressure"],
                        pawn_breaks=["c5 challenging the center"],
                        when_to_use="When you want active counterplay",
                        what_to_avoid=["Playing ...c5 when it loses a pawn"],
                        teaching_explanation="Like in the French, attack the base of White's pawn chain. The ...c5 break challenges d4 and gives you counterplay."
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["c3", "f3"], "B": ["d3", "c4"], "R": ["e1", "d1"]},
                    "black": {"N": ["d7", "f6"], "B": ["f5", "e7"], "R": ["c8", "e8"]}
                },
                critical_squares=["d4", "e5", "c5", "f5"],
                outposts=["d3 (for White B)", "f5 (for Black B)", "d5 (contested)"],
                weak_squares=["c6 (can become weak)", "d5 (contested)"],
                teaching_points=[
                    "Develop the light-squared bishop BEFORE playing ...e6",
                    "The Caro-Kann is solid but can be passive",
                    "...c5 is the key counterattacking break",
                    "White gets more space but Black is hard to break down",
                    "This opening is great for players who like solid positions"
                ],
                common_mistakes=[
                    "Black: Playing ...e6 before ...Bf5",
                    "Black: Being too passive - you need counterplay",
                    "White: Underestimating Black's solidity",
                    "White: Overextending and getting counterattacked"
                ],
                famous_games=[
                    "Karpov's Caro-Kann games",
                    "Petrosian's defensive masterpieces",
                    "Many top GM games with the Caro"
                ],
                difficulty="intermediate",
                prerequisites=["Basic opening principles", "Understanding of space"]
            ),
            
            # ============================================
            # NIMZO-INDIAN DEFENSE
            # ============================================
            "nimzo_indian": StructureTeaching(
                structure_name="Nimzo-Indian Defense",
                structure_type="nimzo_indian",
                main_idea="Black pins the knight and is willing to trade bishop for knight to damage White's pawns",
                key_characteristics=[
                    "Black's bishop on b4 pins White's knight",
                    "The main strategic idea is ...Bxc3 doubling White's pawns",
                    "White often gets the bishop pair as compensation",
                    "Black aims for solid center and good piece play",
                    "Very popular at the highest levels"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Accept Doubled Pawns for Bishop Pair",
                        description="Allow ...Bxc3 and use the two bishops",
                        key_moves=["Qc2", "a3", "Bxc3"],
                        piece_maneuvers=["Develop bishops actively"],
                        pawn_breaks=["e4 to open the position for bishops"],
                        when_to_use="When you want to play with two bishops",
                        what_to_avoid=["Keeping the position too closed"],
                        teaching_explanation="If Black takes on c3, you get doubled pawns but TWO BISHOPS. Open the position to make them powerful. The pawns can be a strength too!"
                    ),
                    StrategicPlan(
                        name="Avoid the Trade with a3",
                        description="Play a3 to force the bishop to decide",
                        key_moves=["a3", "Bd6/Be7", "e4"],
                        piece_maneuvers=["Gain space after bishop retreats"],
                        pawn_breaks=["e4 for central control"],
                        when_to_use="When you don't want doubled pawns",
                        what_to_avoid=["Wasting time if Black won't take anyway"],
                        teaching_explanation="If you don't want doubled pawns, play a3 to ask the bishop what it wants. But you use a tempo, so make sure it's worth it."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Double the Pawns",
                        description="Play ...Bxc3 to damage White's pawn structure",
                        key_moves=["Bxc3", "bxc3", "d5", "c5"],
                        piece_maneuvers=["Attack the doubled pawns"],
                        pawn_breaks=["c5 and d5 for central control"],
                        when_to_use="When you want structural advantage",
                        what_to_avoid=["Opening the position for White's bishops"],
                        teaching_explanation="Take on c3 to double White's pawns. But keep the position CLOSED - you don't want White's two bishops to become strong."
                    ),
                    StrategicPlan(
                        name="Keep the Bishop",
                        description="Retreat and keep the bishop for later",
                        key_moves=["Be7", "d5", "c5"],
                        piece_maneuvers=["Bishop stays active"],
                        pawn_breaks=["d5 for central presence"],
                        when_to_use="When you don't want to give up the bishop",
                        what_to_avoid=["Losing too much time retreating"],
                        teaching_explanation="Sometimes it's better to keep your bishop. Retreat to e7 and play a solid game. You still have good piece play."
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["e2", "f3"], "B": ["d3", "b2"], "R": ["c1", "e1"]},
                    "black": {"N": ["c6", "f6"], "B": ["b4", "b7"], "R": ["c8", "e8"]}
                },
                critical_squares=["c3", "d4", "e4", "c5"],
                outposts=["d3 (for White)", "d5 (for Black)", "c4"],
                weak_squares=["c3/c4 (after doubling)", "d4 (can be weak)"],
                teaching_points=[
                    "The ...Bxc3 trade is the heart of the Nimzo",
                    "White gets two bishops but damaged pawns",
                    "Black should keep the position CLOSED after doubling",
                    "This is one of the most strategic openings",
                    "Both sides have real chances - very balanced"
                ],
                common_mistakes=[
                    "Black: Opening the position after ...Bxc3",
                    "Black: Trading too early or too late",
                    "White: Not using the bishop pair effectively",
                    "White: Letting the doubled pawns become weak"
                ],
                famous_games=[
                    "Nimzowitsch's original games",
                    "Kasparov's Nimzo-Indian battles",
                    "Modern GM practice"
                ],
                difficulty="advanced",
                prerequisites=["Pawn structure understanding", "Strategic planning"]
            ),
            
            # ============================================
            # SICILIAN NAJDORF
            # ============================================
            "sicilian_najdorf": StructureTeaching(
                structure_name="Sicilian Najdorf",
                structure_type="sicilian_najdorf",
                main_idea="Black plays ...a6 to control b5 and prepare ...e5 or ...b5 counterplay",
                key_characteristics=[
                    "The ...a6 move is multi-purpose: stops Bb5, prepares ...b5 or ...e5",
                    "Very sharp and tactical opening",
                    "White often attacks the kingside, Black the queenside",
                    "One of the most analyzed openings in chess",
                    "Requires precise knowledge from both sides"
                ],
                white_plans=[
                    StrategicPlan(
                        name="English Attack (Be3/f3/g4)",
                        description="Kingside pawn storm with Be3, f3, Qd2, g4, 0-0-0",
                        key_moves=["Be3", "f3", "Qd2", "g4", "0-0-0"],
                        piece_maneuvers=["Be3", "Qd2", "0-0-0", "Rg1"],
                        pawn_breaks=["g4-g5-g6 pawn storm"],
                        when_to_use="Standard attacking setup",
                        what_to_avoid=["Being too slow - Black will attack first"],
                        teaching_explanation="The English Attack is direct: castle queenside and storm the kingside with g4-g5. It's a race - whoever attacks faster wins!"
                    ),
                    StrategicPlan(
                        name="Positional with Be2",
                        description="Solid development with Be2 and 0-0",
                        key_moves=["Be2", "0-0", "f4", "Kh1"],
                        piece_maneuvers=["Be2", "0-0", "Qe1-g3"],
                        pawn_breaks=["f4-f5 or e5"],
                        when_to_use="When you want a slower game",
                        what_to_avoid=["Being too passive against Black's counterplay"],
                        teaching_explanation="The Be2 systems are quieter but still have bite. You can attack later with f4-f5 while keeping a solid position."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Queenside Counterattack",
                        description="Push ...b5-b4 and attack on the queenside",
                        key_moves=["b5", "b4", "Rb8", "Qa5"],
                        piece_maneuvers=["Nc6-a5-c4", "Rb8"],
                        pawn_breaks=["b5-b4 is the main break"],
                        when_to_use="Against Be3/f3 setups",
                        what_to_avoid=["Being too slow - the kingside attack is deadly"],
                        teaching_explanation="In the Najdorf, you MUST counterattack. Push ...b5-b4 to open lines on the queenside while White attacks your king. Speed is everything!"
                    ),
                    StrategicPlan(
                        name="...e5 Central Break",
                        description="Play ...e5 to challenge the center",
                        key_moves=["e5", "Be7", "0-0"],
                        piece_maneuvers=["Prepare ...e5 carefully"],
                        pawn_breaks=["e5 gaining central space"],
                        when_to_use="When you want a more stable center",
                        what_to_avoid=["Playing ...e5 when it weakens d5 too much"],
                        teaching_explanation="The ...e5 break gives you more space but weakens d5. Make sure you can control d5 before playing it!"
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["c3", "f3"], "B": ["e3", "c4/e2"], "R": ["d1", "g1"]},
                    "black": {"N": ["c6", "f6", "d7"], "B": ["e7", "b7"], "R": ["c8", "b8"]}
                },
                critical_squares=["d5", "e5", "b5", "g6"],
                outposts=["d5 (critical for White)", "c4 (for Black knight)"],
                weak_squares=["d5 (if Black plays ...e5)", "g7 (kingside attack target)"],
                teaching_points=[
                    "This is one of the sharpest openings - study it well!",
                    "Speed is critical for both sides",
                    "...a6 is multi-purpose: controls b5, prepares counterplay",
                    "White attacks kingside, Black attacks queenside",
                    "Precise move order knowledge is essential"
                ],
                common_mistakes=[
                    "Black: Being too slow with counterplay",
                    "Black: Not knowing the theory - it's deadly",
                    "White: Attacking without preparation",
                    "White: Letting Black get ...b5-b4 rolling first"
                ],
                famous_games=[
                    "Fischer's Najdorf games",
                    "Kasparov's legendary Najdorf battles",
                    "Modern super-GM games"
                ],
                difficulty="advanced",
                prerequisites=["Tactical skill", "Opening theory knowledge", "Sharp play"]
            ),
            
            # ============================================
            # LONDON SYSTEM
            # ============================================
            "london_system": StructureTeaching(
                structure_name="London System",
                structure_type="london_system",
                main_idea="White develops Bf4 early and creates a solid pyramid structure",
                key_characteristics=[
                    "White plays d4, Bf4, e3, c3, Nf3, Bd3 - the 'London setup'",
                    "Very solid and hard to break down",
                    "White's dark-squared bishop is outside the pawn chain",
                    "Can be played against almost anything",
                    "Popular at club level for its simplicity"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Standard London Setup",
                        description="Complete the pyramid: d4, Bf4, e3, c3, Nf3, Bd3",
                        key_moves=["d4", "Bf4", "e3", "c3", "Nf3", "Bd3"],
                        piece_maneuvers=["Bf4 BEFORE e3", "Nbd2-f3 if needed"],
                        pawn_breaks=["e4 or c4 later"],
                        when_to_use="Default setup",
                        what_to_avoid=["Playing e3 before Bf4 (blocks the bishop)"],
                        teaching_explanation="The London is simple: get your bishop out with Bf4, then build the e3/c3/d4 pyramid. It's solid and you always know what to do."
                    ),
                    StrategicPlan(
                        name="Kingside Attack",
                        description="Attack the kingside after solid development",
                        key_moves=["h3", "Qe2", "Ne5", "g4"],
                        piece_maneuvers=["Nf3-e5", "Qe2-g4"],
                        pawn_breaks=["e4 to open the center"],
                        when_to_use="After completing development",
                        what_to_avoid=["Attacking without proper preparation"],
                        teaching_explanation="Once you have the London setup, you can attack! Ne5 is often strong, and you can push h3/g4 for a kingside attack."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Challenge with ...c5",
                        description="Strike at White's center with ...c5",
                        key_moves=["c5", "cxd4", "Nc6"],
                        piece_maneuvers=["Develop actively, don't be passive"],
                        pawn_breaks=["c5 challenging d4"],
                        when_to_use="Standard counterplay",
                        what_to_avoid=["Being too passive"],
                        teaching_explanation="Against the London, don't be passive! Challenge the center with ...c5 and develop your pieces actively."
                    ),
                    StrategicPlan(
                        name="Fianchetto Setup",
                        description="Play ...g6 and ...Bg7 to challenge the center",
                        key_moves=["g6", "Bg7", "0-0", "d5"],
                        piece_maneuvers=["Bg7 pressures the center"],
                        pawn_breaks=["d5 and c5"],
                        when_to_use="If you like solid positions",
                        what_to_avoid=["Letting White attack without counterplay"],
                        teaching_explanation="The Bg7 puts pressure on the center from the side. Combined with ...d5, you can challenge White's setup effectively."
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["f3", "d2"], "B": ["f4", "d3"], "R": ["e1", "c1"]},
                    "black": {"N": ["f6", "c6"], "B": ["d6", "g7"], "R": ["e8", "c8"]}
                },
                critical_squares=["e5", "d4", "c5"],
                outposts=["e5 (for White knight)"],
                weak_squares=["c3 (can become a target)"],
                teaching_points=[
                    "The London is simple and solid - great for club players",
                    "Always play Bf4 BEFORE e3",
                    "The pyramid structure (e3/d4/c3) is hard to break",
                    "Black should challenge actively, not sit passively",
                    "White can attack after completing development"
                ],
                common_mistakes=[
                    "White: Playing e3 before Bf4 (blocks the bishop!)",
                    "White: Being too passive - you can attack too!",
                    "Black: Being too passive against the solid setup",
                    "Black: Not challenging with ...c5"
                ],
                famous_games=[
                    "Kamsky's London System games",
                    "Carlsen's occasional London games",
                    "Popular at all levels"
                ],
                difficulty="beginner",
                prerequisites=["Basic opening principles"]
            ),
            
            # ============================================
            # SLAV DEFENSE
            # ============================================
            "slav_defense": StructureTeaching(
                structure_name="Slav Defense",
                structure_type="slav_defense",
                main_idea="Black supports d5 with ...c6 while keeping the light-squared bishop free",
                key_characteristics=[
                    "Black plays ...c6 to support d5 (like Caro-Kann idea)",
                    "The light-squared bishop can develop to f5 or g4",
                    "Very solid opening, popular at all levels",
                    "Can transpose to many other structures",
                    "Both sides have clear plans"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Exchange Variation",
                        description="Exchange on d5 and play for minority attack",
                        key_moves=["cxd5", "cxd5", "Bf4", "Nc3"],
                        piece_maneuvers=["Minority attack setup"],
                        pawn_breaks=["b4-b5 minority attack"],
                        when_to_use="For a quiet positional game",
                        what_to_avoid=["Letting Black equalize too easily"],
                        teaching_explanation="The Exchange Slav leads to the Carlsbad structure. Use the minority attack (b4-b5) to create a weakness on c6."
                    ),
                    StrategicPlan(
                        name="Main Line with e3",
                        description="Solid development with e3 and Bd3",
                        key_moves=["e3", "Bd3", "Nf3", "0-0"],
                        piece_maneuvers=["Natural development"],
                        pawn_breaks=["e4 break when prepared"],
                        when_to_use="Standard main line play",
                        what_to_avoid=["Being too passive"],
                        teaching_explanation="Develop solidly with e3 and Bd3. You have a small space advantage. Look for the e4 break when the time is right."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="...Bf5 Development",
                        description="Develop the bishop actively to f5",
                        key_moves=["Bf5", "e6", "Nf6", "Bd6"],
                        piece_maneuvers=["Bc8-f5 before ...e6"],
                        pawn_breaks=["dxc4 and ...e5"],
                        when_to_use="Standard Slav development",
                        what_to_avoid=["Blocking the bishop with ...e6 too early"],
                        teaching_explanation="Like the Caro-Kann, get your bishop out to f5 BEFORE playing ...e6. This is the Slav's main advantage over the QGD."
                    ),
                    StrategicPlan(
                        name="...dxc4 and ...b5",
                        description="Capture on c4 and hold the pawn with ...b5",
                        key_moves=["dxc4", "b5", "a6"],
                        piece_maneuvers=["Hold the c4 pawn"],
                        pawn_breaks=["b5 to hold c4"],
                        when_to_use="In the Slav Gambit lines",
                        what_to_avoid=["Getting your pawns overextended"],
                        teaching_explanation="You can grab the c4 pawn and try to hold it with ...b5. It's risky but gives you a pawn. Be careful of your queenside pawns!"
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["c3", "f3"], "B": ["d3", "g5"], "R": ["c1", "e1"]},
                    "black": {"N": ["d7", "f6"], "B": ["f5", "e7"], "R": ["c8", "e8"]}
                },
                critical_squares=["d5", "e4", "c4"],
                outposts=["e5 (for White)", "d5 (for Black)"],
                weak_squares=["c6 (can become weak)"],
                teaching_points=[
                    "The Slav is solid and reliable",
                    "Develop the bishop to f5 BEFORE ...e6",
                    "The ...dxc4 lines are sharp and tactical",
                    "Can transpose to many other openings",
                    "Both sides have clear, understandable plans"
                ],
                common_mistakes=[
                    "Black: Playing ...e6 before ...Bf5",
                    "Black: Being too passive",
                    "White: Not preparing e4 properly",
                    "White: Underestimating Black's counterplay"
                ],
                famous_games=[
                    "Anand's Slav games",
                    "Kramnik's Slav Defense",
                    "Modern GM practice"
                ],
                difficulty="intermediate",
                prerequisites=["Basic opening principles", "QGD understanding"]
            ),
            
            # ============================================
            # BENONI DEFENSE
            # ============================================
            "benoni": StructureTeaching(
                structure_name="Modern Benoni",
                structure_type="benoni",
                main_idea="Black accepts space disadvantage for dynamic counterplay with ...c5",
                key_characteristics=[
                    "Asymmetric pawn structure after d5-c5 exchange",
                    "White has central space advantage (d5 pawn)",
                    "Black's queenside majority can become powerful",
                    "Very dynamic and unbalanced positions",
                    "Not for the faint of heart!"
                ],
                white_plans=[
                    StrategicPlan(
                        name="e4-e5 Central Breakthrough",
                        description="Push e5 to gain more space and attack",
                        key_moves=["e4", "f4", "e5"],
                        piece_maneuvers=["Bd3", "0-0", "f4-e5"],
                        pawn_breaks=["e4-e5 is the dream"],
                        when_to_use="When you can prepare e5 safely",
                        what_to_avoid=["Playing e5 when Black can blockade on d6"],
                        teaching_explanation="The e5 break is your goal! If you can play e5 effectively, Black is in trouble. But you need to prepare it carefully."
                    ),
                    StrategicPlan(
                        name="Squeeze and Restrict",
                        description="Keep Black restricted and slowly improve",
                        key_moves=["Nf3", "Be2", "0-0", "a4"],
                        piece_maneuvers=["Control b5 square with a4"],
                        pawn_breaks=["a4 to stop ...b5"],
                        when_to_use="For a slower, positional approach",
                        what_to_avoid=["Letting Black get ...b5 counterplay"],
                        teaching_explanation="If you can stop ...b5, Black is very cramped. Play a4 and slowly improve your position. Black will struggle."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="...b5 Queenside Expansion",
                        description="Push ...b5 to activate the queenside majority",
                        key_moves=["b5", "b4", "Rb8"],
                        piece_maneuvers=["Nc6-a5-c4", "Rb8"],
                        pawn_breaks=["b5-b4 is the key break"],
                        when_to_use="The main plan in the Benoni",
                        what_to_avoid=["Being too slow - White will crush you"],
                        teaching_explanation="You MUST get ...b5 in! Your whole position depends on queenside counterplay. If White stops ...b5, you're in big trouble."
                    ),
                    StrategicPlan(
                        name="...f5 Kingside Break",
                        description="Play ...f5 to challenge e4",
                        key_moves=["f5", "exf5", "gxf5"],
                        piece_maneuvers=["Prepare ...f5 with Re8"],
                        pawn_breaks=["f5 attacking e4"],
                        when_to_use="When ...b5 is blocked",
                        what_to_avoid=["Weakening your king too much"],
                        teaching_explanation="If ...b5 isn't working, try ...f5! It's risky because it weakens your king, but it can give you counterplay."
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["c3", "f3"], "B": ["d3", "e2"], "R": ["e1", "b1"]},
                    "black": {"N": ["a6", "f6", "e7"], "B": ["g7", "d7"], "R": ["b8", "e8"]}
                },
                critical_squares=["d5", "e5", "b5", "c4"],
                outposts=["d5 (White's powerful pawn)", "c4 (for Black knight)"],
                weak_squares=["d6 (Black's eternal weakness)", "e6"],
                teaching_points=[
                    "The Benoni is SHARP - you must know the theory!",
                    "Black MUST get ...b5 counterplay",
                    "If White plays e5 effectively, Black is lost",
                    "Not for passive players - requires active play",
                    "The d6 pawn is Black's structural weakness"
                ],
                common_mistakes=[
                    "Black: Being too slow with ...b5",
                    "Black: Playing the Benoni without knowing theory",
                    "White: Not controlling b5",
                    "White: Allowing Black's counterplay to develop"
                ],
                famous_games=[
                    "Tal's Benoni sacrifices",
                    "Kasparov's Benoni games",
                    "Modern Benoni theory"
                ],
                difficulty="advanced",
                prerequisites=["Dynamic play", "Opening theory", "Calculation"]
            ),
            
            # ============================================
            # GRUNFELD DEFENSE
            # ============================================
            "grunfeld": StructureTeaching(
                structure_name="Grünfeld Defense",
                structure_type="grunfeld",
                main_idea="Black lets White build a big center, then attacks it with pieces",
                key_characteristics=[
                    "Black plays ...d5 to challenge then exchanges: exd5 Nxd5",
                    "White gets a big pawn center (c4/d4/e4)",
                    "Black attacks the center with pieces, not pawns",
                    "The Bg7 is Black's most important piece",
                    "Very theoretical and sharp"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Maintain the Center",
                        description="Keep the big center and squeeze Black",
                        key_moves=["e4", "Be3", "Qd2", "Rc1"],
                        piece_maneuvers=["Protect d4 and e4"],
                        pawn_breaks=["d5 to gain more space"],
                        when_to_use="The classical approach",
                        what_to_avoid=["Losing a center pawn for nothing"],
                        teaching_explanation="Your big center is your advantage. Protect it and try to advance d5 or use the space to attack. Don't let Black destroy it!"
                    ),
                    StrategicPlan(
                        name="Exchange on d5",
                        description="Simplify and keep a solid position",
                        key_moves=["cxd5", "Nxd5", "e4", "Nxc3"],
                        piece_maneuvers=["Develop simply"],
                        pawn_breaks=[],
                        when_to_use="For a simpler game",
                        what_to_avoid=["Being too passive"],
                        teaching_explanation="The Exchange variation is simpler. You don't get a huge center but also don't have to defend it. More balanced but less exciting."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Attack the Center",
                        description="Use pieces to pressure d4 and c4",
                        key_moves=["c5", "Nc6", "Qa5", "cxd4"],
                        piece_maneuvers=["Nc6 pressures d4", "Qa5 adds pressure"],
                        pawn_breaks=["c5 challenging d4"],
                        when_to_use="The classic Grünfeld strategy",
                        what_to_avoid=["Letting White consolidate the center"],
                        teaching_explanation="Your strategy is to ATTACK the center, not build your own. The Bg7 and ...c5 put pressure on d4. If the center falls, you win!"
                    ),
                    StrategicPlan(
                        name="...e5 Counterblow",
                        description="Strike in the center with ...e5",
                        key_moves=["e5", "dxe5", "Qa5"],
                        piece_maneuvers=["Prepare ...e5 carefully"],
                        pawn_breaks=["e5 destroying the center"],
                        when_to_use="In some variations",
                        what_to_avoid=["Playing ...e5 when it loses material"],
                        teaching_explanation="Sometimes ...e5 can destroy White's center in one blow. But calculate carefully - it's a committal move!"
                    )
                ],
                ideal_piece_placement={
                    "white": {"N": ["c3", "f3"], "B": ["e3", "e2"], "R": ["c1", "d1"]},
                    "black": {"N": ["c6", "d5"], "B": ["g7", "e6"], "R": ["c8", "d8"]}
                },
                critical_squares=["d4", "c4", "e4", "d5"],
                outposts=["d5 (contested)", "c4"],
                weak_squares=["d4 (can become weak)", "c3 (after ...Bxc3)"],
                teaching_points=[
                    "The Grünfeld is all about ATTACKING the center",
                    "Black's Bg7 is the most important piece",
                    "Don't try to build a pawn center as Black",
                    "White must protect the center or it will collapse",
                    "Very theoretical - study the main lines!"
                ],
                common_mistakes=[
                    "Black: Trying to build a pawn center",
                    "Black: Not putting enough pressure on d4",
                    "White: Losing a center pawn carelessly",
                    "White: Overextending the center"
                ],
                famous_games=[
                    "Kasparov's legendary Grünfeld games",
                    "Svidler's Grünfeld expertise",
                    "Modern super-GM theory"
                ],
                difficulty="advanced",
                prerequisites=["Dynamic play", "Piece activity concepts", "Opening theory"]
            ),
            
            # ============================================
            # BISHOP VS KNIGHT ENDGAME
            # ============================================
            "bishop_vs_knight_endgame": StructureTeaching(
                structure_name="Bishop vs Knight Endgame",
                structure_type="bishop_vs_knight_endgame",
                main_idea="Bishop is better in open positions, knight is better in closed positions",
                key_characteristics=[
                    "Bishop is long-range, knight is short-range",
                    "In open positions, bishop dominates",
                    "In closed positions, knight can be superior",
                    "Pawns on both flanks favor the bishop",
                    "Knight needs outposts to be effective"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Open the Position (if you have bishop)",
                        description="Create pawn breaks to open lines for your bishop",
                        key_moves=["Pawn breaks to open position"],
                        piece_maneuvers=["Keep bishop on long diagonal"],
                        pawn_breaks=["Any pawn break that opens lines"],
                        when_to_use="When you have the bishop",
                        what_to_avoid=["Closing the position"],
                        teaching_explanation="If you have the bishop, OPEN the position! Create pawn breaks to give your bishop long diagonals. The knight can't compete in open positions."
                    ),
                    StrategicPlan(
                        name="Create Outposts (if you have knight)",
                        description="Find strong squares for your knight",
                        key_moves=["Knight to outpost", "Support with pawns"],
                        piece_maneuvers=["Knight to central outpost"],
                        pawn_breaks=["Avoid opening the position"],
                        when_to_use="When you have the knight",
                        what_to_avoid=["Opening the position"],
                        teaching_explanation="If you have the knight, find an OUTPOST - a square where your knight can't be attacked by pawns. From there, it can dominate."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Pawns on Both Flanks",
                        description="Keep pawns on both sides to maximize bishop's range",
                        key_moves=["Keep pawns spread out"],
                        piece_maneuvers=["Bishop controls long diagonal"],
                        pawn_breaks=[],
                        when_to_use="When you have the bishop",
                        what_to_avoid=["Trading all pawns to one side"],
                        teaching_explanation="Bishops love pawns on BOTH sides of the board. The knight can only cover one side at a time, but your bishop covers everything!"
                    ),
                    StrategicPlan(
                        name="Block the Bishop",
                        description="Use pawns to block the bishop's diagonals",
                        key_moves=["Fixed pawns", "Knight to strong square"],
                        piece_maneuvers=["Knight dominates fixed position"],
                        pawn_breaks=["Avoid pawn breaks"],
                        when_to_use="When you have the knight",
                        what_to_avoid=["Opening the position"],
                        teaching_explanation="Block the bishop's diagonals with fixed pawns. Your knight becomes stronger than the 'bad' bishop in closed positions."
                    )
                ],
                ideal_piece_placement={
                    "white": {"B": ["long diagonal"], "N": ["central outpost"]},
                    "black": {"B": ["long diagonal"], "N": ["central outpost"]}
                },
                critical_squares=["Central outposts", "Key diagonals"],
                outposts=["Central squares unreachable by pawns"],
                weak_squares=["Fixed pawns on bishop's color"],
                teaching_points=[
                    "Bishop is better in OPEN positions",
                    "Knight is better in CLOSED positions",
                    "Pawns on both sides favor the bishop",
                    "Knight needs outposts to be effective",
                    "Judge the position to know which is better"
                ],
                common_mistakes=[
                    "Opening position when you have knight",
                    "Closing position when you have bishop",
                    "Not using pawns to support your piece",
                    "Trading into a bad minor piece endgame"
                ],
                famous_games=[
                    "Fischer's bishop endgames",
                    "Capablanca's technique",
                    "Classic endgame treatises"
                ],
                difficulty="intermediate",
                prerequisites=["Basic endgame knowledge", "Minor piece understanding"]
            ),
            
            # ============================================
            # QUEEN ENDGAME
            # ============================================
            "queen_endgame": StructureTeaching(
                structure_name="Queen Endgame",
                structure_type="queen_endgame",
                main_idea="Queens are powerful but often lead to perpetual checks and draws",
                key_characteristics=[
                    "Queens can give perpetual check easily",
                    "Even extra pawns can be hard to convert",
                    "King safety is paramount",
                    "Passed pawns become very dangerous",
                    "Many queen endgames are drawn"
                ],
                white_plans=[
                    StrategicPlan(
                        name="Protect Your King",
                        description="Ensure your king is safe from perpetual check",
                        key_moves=["King to corner", "Pawns shield king"],
                        piece_maneuvers=["Queen supports pawns and defends"],
                        pawn_breaks=["Push passed pawn when king is safe"],
                        when_to_use="Always prioritize king safety",
                        what_to_avoid=["Leaving your king exposed"],
                        teaching_explanation="In queen endgames, your king MUST be safe from perpetual check. Even if you're up a pawn, a perpetual is a draw!"
                    ),
                    StrategicPlan(
                        name="Push Passed Pawns",
                        description="Advance passed pawns with queen support",
                        key_moves=["Queen escorts the pawn"],
                        piece_maneuvers=["Queen ahead of pawn, or supporting from behind"],
                        pawn_breaks=["Create a passed pawn if you don't have one"],
                        when_to_use="When your king is safe",
                        what_to_avoid=["Pushing pawns when your king is exposed"],
                        teaching_explanation="Once your king is safe, push your passed pawn. The queen can support it while still checking or threatening the enemy king."
                    )
                ],
                black_plans=[
                    StrategicPlan(
                        name="Perpetual Check Defense",
                        description="Try to get perpetual check to draw",
                        key_moves=["Queen checks", "Keep checking"],
                        piece_maneuvers=["Queen hunts the enemy king"],
                        pawn_breaks=[],
                        when_to_use="When you're losing",
                        what_to_avoid=["Letting your opponent's king escape"],
                        teaching_explanation="If you're worse in a queen endgame, look for PERPETUAL CHECK. Even if you're down material, a perpetual is a draw!"
                    ),
                    StrategicPlan(
                        name="Counterattack",
                        description="Create threats against opponent's king",
                        key_moves=["Queen attacks king", "Push passed pawns"],
                        piece_maneuvers=["Queen active on both flanks"],
                        pawn_breaks=["Create your own passed pawn"],
                        when_to_use="When you have counterplay",
                        what_to_avoid=["Being purely defensive"],
                        teaching_explanation="Queens are powerful attackers. Even if you're defending, look for counterattacking chances. A threat against their king can save you!"
                    )
                ],
                ideal_piece_placement={
                    "white": {"Q": ["active, supporting pawns"]},
                    "black": {"Q": ["active, threatening perpetual"]}
                },
                critical_squares=["Queening squares", "King escape squares"],
                outposts=[],
                weak_squares=["Exposed king positions"],
                teaching_points=[
                    "King safety is MORE important than material",
                    "Perpetual check is always a resource",
                    "Passed pawns are very dangerous in queen endgames",
                    "Many queen endgames end in draws",
                    "Calculate checks and counter-checks carefully"
                ],
                common_mistakes=[
                    "Leaving your king exposed to perpetual",
                    "Not looking for perpetual when you're worse",
                    "Pushing pawns when your king is unsafe",
                    "Forgetting that queens can give check from far away"
                ],
                famous_games=[
                    "World Championship queen endgames",
                    "Famous perpetual check saves",
                    "Queen endgame studies"
                ],
                difficulty="intermediate",
                prerequisites=["Basic endgame knowledge", "Calculation skills"]
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
