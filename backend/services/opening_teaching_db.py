"""
Opening Teaching Database
=========================

Curated opening knowledge for ~50 common openings.
Each opening has:
- Name and ECO code
- Key move sequence
- Move-by-move teaching explanations
- Plans for both sides
- Common mistakes
- Famous examples

This is the "human knowledge" that makes coaching feel personal.

Usage:
    db = OpeningTeachingDatabase()
    opening = db.identify_opening(moves)
    teaching = db.get_move_teaching(opening_id, move_number, move)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import re


@dataclass
class MoveTeaching:
    """Teaching content for a specific move."""
    move: str  # The move in SAN
    explanation: str  # Why this move is played
    concept: str  # Chess concept being demonstrated
    what_to_watch: str  # What the student should notice
    common_alternative: str = ""  # Common alternative move


@dataclass
class OpeningEntry:
    """Complete opening entry with teaching content."""
    opening_id: str
    name: str
    eco_code: str
    key_moves: List[str]  # Main line moves
    
    # Teaching content
    overview: str
    main_idea_white: str
    main_idea_black: str
    
    # Move-by-move teaching
    move_teachings: Dict[int, Dict[str, MoveTeaching]]  # {move_num: {"e4": MoveTeaching}}
    
    # Strategic guidance
    typical_plans_white: List[str]
    typical_plans_black: List[str]
    critical_moments: List[str]
    common_mistakes: List[str]
    
    # Learning
    difficulty: str  # beginner, intermediate, advanced
    famous_games: List[str]


class OpeningTeachingDatabase:
    """
    Database of ~50 common openings with detailed teaching content.
    """
    
    def __init__(self):
        """Initialize the opening database."""
        self.openings = self._build_database()
        self._build_move_index()
    
    def _build_move_index(self):
        """Build index for opening identification."""
        self.move_sequences = {}
        for opening_id, opening in self.openings.items():
            moves_key = " ".join(opening.key_moves[:6])  # Index first 6 moves
            self.move_sequences[moves_key] = opening_id
    
    def identify_opening(self, moves: List[str]) -> Optional[OpeningEntry]:
        """
        Identify the opening from a list of moves.
        
        Args:
            moves: List of moves in SAN format
            
        Returns:
            OpeningEntry if identified, None otherwise
        """
        # Try matching progressively shorter sequences
        for length in range(min(len(moves), 12), 2, -1):
            moves_key = " ".join(moves[:length])
            # Check exact match
            if moves_key in self.move_sequences:
                return self.openings.get(self.move_sequences[moves_key])
            # Check prefix match
            for seq, opening_id in self.move_sequences.items():
                if seq.startswith(moves_key) or moves_key.startswith(seq):
                    return self.openings.get(opening_id)
        
        return None
    
    def get_opening_by_id(self, opening_id: str) -> Optional[OpeningEntry]:
        """Get opening by its ID."""
        return self.openings.get(opening_id)
    
    def get_move_teaching(
        self,
        opening_id: str,
        move_number: int,
        move: str,
        player_color: str
    ) -> Optional[str]:
        """
        Get teaching explanation for a specific move in an opening.
        
        Args:
            opening_id: Opening identifier
            move_number: Full move number (1, 2, 3...)
            move: The move in SAN
            player_color: "white" or "black"
            
        Returns:
            Teaching explanation string
        """
        opening = self.openings.get(opening_id)
        if not opening:
            return None
        
        teachings = opening.move_teachings.get(move_number, {})
        move_teaching = teachings.get(move)
        
        if not move_teaching:
            # Try without piece disambiguation (e.g., "Nf3" instead of "Ngf3")
            base_move = re.sub(r'[a-h]([a-h])', r'\1', move)
            move_teaching = teachings.get(base_move)
        
        if not move_teaching:
            return None
        
        return f"{move_teaching.explanation} {move_teaching.what_to_watch}"
    
    def get_opening_overview(self, opening_id: str, player_color: str) -> Optional[str]:
        """Get overview for an opening from a player's perspective."""
        opening = self.openings.get(opening_id)
        if not opening:
            return None
        
        if player_color == "white":
            return f"{opening.name}: {opening.overview} As White, {opening.main_idea_white}"
        else:
            return f"{opening.name}: {opening.overview} As Black, {opening.main_idea_black}"
    
    def list_openings_by_difficulty(self, difficulty: str) -> List[str]:
        """List openings filtered by difficulty."""
        return [
            name for name, o in self.openings.items()
            if o.difficulty == difficulty
        ]
    
    def _build_database(self) -> Dict[str, OpeningEntry]:
        """Build the complete opening database."""
        return {
            # ============================================
            # KING'S PAWN OPENINGS (1.e4)
            # ============================================
            "italian_game": OpeningEntry(
                opening_id="italian_game",
                name="Italian Game",
                eco_code="C50-C54",
                key_moves=["e4", "e5", "Nf3", "Nc6", "Bc4"],
                overview="One of the oldest and most classical openings.",
                main_idea_white="Develop quickly and target the f7 square.",
                main_idea_black="Solid development and look for counterplay.",
                move_teachings={
                    1: {
                        "e4": MoveTeaching(
                            move="e4",
                            explanation="The King's Pawn opening - fighting for the center immediately.",
                            concept="Central control",
                            what_to_watch="This opens lines for your queen and bishop."
                        ),
                        "e5": MoveTeaching(
                            move="e5",
                            explanation="Meeting the center challenge directly.",
                            concept="Central control",
                            what_to_watch="Black also gains central space."
                        )
                    },
                    2: {
                        "Nf3": MoveTeaching(
                            move="Nf3",
                            explanation="Developing the knight to its best square while attacking e5.",
                            concept="Development with threat",
                            what_to_watch="The knight attacks the e5 pawn."
                        ),
                        "Nc6": MoveTeaching(
                            move="Nc6",
                            explanation="Defending e5 while developing a piece.",
                            concept="Development with defense",
                            what_to_watch="The knight protects e5 and eyes d4."
                        )
                    },
                    3: {
                        "Bc4": MoveTeaching(
                            move="Bc4",
                            explanation="The Italian Bishop! Targeting the weak f7 square.",
                            concept="Piece activity",
                            what_to_watch="f7 is weak because only the king defends it."
                        ),
                        "Bc5": MoveTeaching(
                            move="Bc5",
                            explanation="The Giuoco Piano - Black mirrors White's development.",
                            concept="Active piece placement",
                            what_to_watch="Both bishops are actively placed."
                        ),
                        "Nf6": MoveTeaching(
                            move="Nf6",
                            explanation="The Two Knights Defense - aggressive counterplay.",
                            concept="Counter-attack",
                            what_to_watch="Black attacks e4 instead of defending f7 directly."
                        )
                    }
                },
                typical_plans_white=[
                    "Castle kingside quickly",
                    "Play d3 and develop bishop to e3 or g5",
                    "Consider c3 and d4 pawn break"
                ],
                typical_plans_black=[
                    "Castle kingside",
                    "Play d6 to support e5",
                    "Look for ...d5 break when ready"
                ],
                critical_moments=["The d4 break", "f7 attacks", "Early central tension"],
                common_mistakes=[
                    "White: Playing d4 too early without preparation",
                    "Black: Moving the f6 knight too early (loses e5)",
                    "Both: Forgetting to castle"
                ],
                difficulty="beginner",
                famous_games=["Many Morphy games", "Greco's original analysis"]
            ),
            
            "ruy_lopez": OpeningEntry(
                opening_id="ruy_lopez",
                name="Ruy Lopez (Spanish Game)",
                eco_code="C60-C99",
                key_moves=["e4", "e5", "Nf3", "Nc6", "Bb5"],
                overview="The 'Spanish Torture' - a strategic masterpiece used at all levels.",
                main_idea_white="Put pressure on Black's center by threatening the knight that defends e5.",
                main_idea_black="Maintain the center and seek counterplay.",
                move_teachings={
                    3: {
                        "Bb5": MoveTeaching(
                            move="Bb5",
                            explanation="The Ruy Lopez! Putting pressure on the knight that defends e5.",
                            concept="Indirect pressure",
                            what_to_watch="If the knight moves, e5 becomes weak."
                        ),
                        "a6": MoveTeaching(
                            move="a6",
                            explanation="The Morphy Defense - asking the bishop its intentions.",
                            concept="Gaining space with tempo",
                            what_to_watch="The bishop must decide: retreat or exchange?"
                        )
                    },
                    4: {
                        "Ba4": MoveTeaching(
                            move="Ba4",
                            explanation="Maintaining the pin. The bishop retreats but keeps the pressure.",
                            concept="Preserving piece activity",
                            what_to_watch="The knight is still pinned to the e5 pawn."
                        ),
                        "Nf6": MoveTeaching(
                            move="Nf6",
                            explanation="Developing while attacking e4.",
                            concept="Counter-attack",
                            what_to_watch="Now e4 is under pressure!"
                        )
                    }
                },
                typical_plans_white=[
                    "Castle and play Re1 to support e4",
                    "Play c3 preparing d4",
                    "Marshall Attack awareness"
                ],
                typical_plans_black=[
                    "Defend e5 with ...d6 or exchange with ...d5",
                    "Play ...b5 and ...Bb7",
                    "The Marshall Attack gambit"
                ],
                critical_moments=[
                    "Whether to take on c6",
                    "The d4 break",
                    "The Marshall Attack"
                ],
                common_mistakes=[
                    "White: Taking on c6 too early",
                    "Black: Not knowing the Marshall",
                    "Both: Missing tactical shots"
                ],
                difficulty="intermediate",
                famous_games=["Kasparov-Karpov matches", "Fischer's Ruy Lopez"]
            ),
            
            "sicilian_defense": OpeningEntry(
                opening_id="sicilian_defense",
                name="Sicilian Defense",
                eco_code="B20-B99",
                key_moves=["e4", "c5"],
                overview="The fighting choice against 1.e4 - asymmetric and sharp.",
                main_idea_white="Open the position and attack on the kingside.",
                main_idea_black="Fight for the center with ...d5 and counterattack on the queenside.",
                move_teachings={
                    1: {
                        "c5": MoveTeaching(
                            move="c5",
                            explanation="The Sicilian! Fighting for d4 without mirroring White.",
                            concept="Asymmetric play",
                            what_to_watch="Black creates imbalance from move one."
                        )
                    },
                    2: {
                        "Nf3": MoveTeaching(
                            move="Nf3",
                            explanation="Preparing d4 while developing.",
                            concept="Preparation",
                            what_to_watch="d4 is coming soon."
                        ),
                        "d6": MoveTeaching(
                            move="d6",
                            explanation="Supporting ...Nf6 and preparing development.",
                            concept="Solid setup",
                            what_to_watch="This is the most popular Sicilian move."
                        ),
                        "Nc6": MoveTeaching(
                            move="Nc6",
                            explanation="Developing and pressuring d4.",
                            concept="Development",
                            what_to_watch="Prepares ...e5 or ...e6 setups."
                        ),
                        "e6": MoveTeaching(
                            move="e6",
                            explanation="The Scheveningen/Kan setup - very flexible.",
                            concept="Flexibility",
                            what_to_watch="Can transpose to many variations."
                        )
                    }
                },
                typical_plans_white=[
                    "Play d4 and develop aggressively",
                    "Castle queenside and attack kingside (Yugoslav)",
                    "English Attack: Be3, f3, Qd2, 0-0-0, g4"
                ],
                typical_plans_black=[
                    "Counterattack on the c-file",
                    "Push ...a6, ...b5, ...b4",
                    "The ...d5 break when possible"
                ],
                critical_moments=[
                    "The d4 moment",
                    "Opposite-side castling attacks",
                    "The ...d5 break"
                ],
                common_mistakes=[
                    "White: Being too slow",
                    "Black: Passive play",
                    "Both: Not knowing the theory"
                ],
                difficulty="intermediate",
                famous_games=["Kasparov's Sicilians", "Fischer's Najdorf"]
            ),
            
            "french_defense": OpeningEntry(
                opening_id="french_defense",
                name="French Defense",
                eco_code="C00-C19",
                key_moves=["e4", "e6"],
                overview="Solid and strategic - Black fights for d5.",
                main_idea_white="Maintain the pawn chain and attack on the kingside.",
                main_idea_black="Attack the base of White's pawn chain with ...c5.",
                move_teachings={
                    1: {
                        "e6": MoveTeaching(
                            move="e6",
                            explanation="The French Defense - preparing ...d5 to fight for the center.",
                            concept="Preparation",
                            what_to_watch="Black will challenge e4 with ...d5."
                        )
                    },
                    2: {
                        "d4": MoveTeaching(
                            move="d4",
                            explanation="Occupying the center with two pawns.",
                            concept="Central control",
                            what_to_watch="White has a classical pawn center."
                        ),
                        "d5": MoveTeaching(
                            move="d5",
                            explanation="Challenging White's center immediately.",
                            concept="Central challenge",
                            what_to_watch="This is the point of the French."
                        )
                    },
                    3: {
                        "e5": MoveTeaching(
                            move="e5",
                            explanation="The Advance Variation - White gains space but fixes the center.",
                            concept="Space vs flexibility",
                            what_to_watch="d4 becomes the base of the chain - Black's target!"
                        ),
                        "c5": MoveTeaching(
                            move="c5",
                            explanation="Attacking the base of White's pawn chain!",
                            concept="Attacking the chain base",
                            what_to_watch="This is the key French idea - attack d4, not e5!"
                        )
                    }
                },
                typical_plans_white=[
                    "Maintain e5 pawn",
                    "f4-f5 kingside attack",
                    "Prevent ...c5 break"
                ],
                typical_plans_black=[
                    "Attack d4 with ...c5",
                    "Activate the 'bad' bishop via a6 or b7",
                    "The ...f6 break"
                ],
                critical_moments=[
                    "Whether White plays e5",
                    "The ...c5 break",
                    "Bad bishop handling"
                ],
                common_mistakes=[
                    "White: Overextending",
                    "Black: Attacking e5 instead of d4",
                    "Black: Leaving the bishop on c8"
                ],
                difficulty="intermediate",
                famous_games=["Korchnoi's French", "Botvinnik's games"]
            ),
            
            "caro_kann_defense": OpeningEntry(
                opening_id="caro_kann_defense",
                name="Caro-Kann Defense",
                eco_code="B10-B19",
                key_moves=["e4", "c6"],
                overview="Solid and reliable - Black's bishop stays free.",
                main_idea_white="Gain central space and attack.",
                main_idea_black="Solid position with active light-squared bishop.",
                move_teachings={
                    1: {
                        "c6": MoveTeaching(
                            move="c6",
                            explanation="The Caro-Kann - preparing ...d5 while keeping the bishop free.",
                            concept="Solid preparation",
                            what_to_watch="Unlike the French, the bishop won't be blocked."
                        )
                    },
                    2: {
                        "d4": MoveTeaching(
                            move="d4",
                            explanation="Classical center occupation.",
                            concept="Central control",
                            what_to_watch="White has space but Black is solid."
                        ),
                        "d5": MoveTeaching(
                            move="d5",
                            explanation="Challenging the center as planned.",
                            concept="Central challenge",
                            what_to_watch="Now the fight for the center begins."
                        )
                    },
                    3: {
                        "Bf5": MoveTeaching(
                            move="Bf5",
                            explanation="Getting the bishop out BEFORE ...e6 blocks it!",
                            concept="Active bishop",
                            what_to_watch="This is the Caro-Kann's advantage over the French."
                        )
                    }
                },
                typical_plans_white=[
                    "Advance Variation: e5 with kingside space",
                    "Classical: Develop and challenge d5",
                    "Exchange: Minority attack"
                ],
                typical_plans_black=[
                    "Develop Bf5 before e6",
                    "Play ...c5 break",
                    "Solid, reliable position"
                ],
                critical_moments=[
                    "Bishop development timing",
                    "The e5 advance",
                    "The ...c5 break"
                ],
                common_mistakes=[
                    "Black: Playing ...e6 before ...Bf5",
                    "White: Underestimating Black's solidity",
                    "Both: Passive play"
                ],
                difficulty="intermediate",
                famous_games=["Karpov's Caro-Kann", "Petrosian's games"]
            ),
            
            # ============================================
            # QUEEN'S PAWN OPENINGS (1.d4)
            # ============================================
            "queens_gambit": OpeningEntry(
                opening_id="queens_gambit",
                name="Queen's Gambit",
                eco_code="D06-D69",
                key_moves=["d4", "d5", "c4"],
                overview="The classical queen's pawn opening - fighting for the center.",
                main_idea_white="Challenge Black's d5 pawn and gain central control.",
                main_idea_black="Decide how to handle the c4 pawn.",
                move_teachings={
                    1: {
                        "d4": MoveTeaching(
                            move="d4",
                            explanation="The Queen's Pawn Game - solid and strategic.",
                            concept="Central control",
                            what_to_watch="c4 will follow to create pressure."
                        ),
                        "d5": MoveTeaching(
                            move="d5",
                            explanation="Claiming central space - the classical response.",
                            concept="Central challenge",
                            what_to_watch="Black fights for the center immediately."
                        )
                    },
                    2: {
                        "c4": MoveTeaching(
                            move="c4",
                            explanation="The Queen's Gambit! Attacking the d5 pawn.",
                            concept="Gambit play",
                            what_to_watch="It's not a real gambit - White can recover the pawn."
                        ),
                        "dxc4": MoveTeaching(
                            move="dxc4",
                            explanation="The Queen's Gambit Accepted - taking the pawn.",
                            concept="Material grab",
                            what_to_watch="White will recover it with Qa4+ or e4."
                        ),
                        "e6": MoveTeaching(
                            move="e6",
                            explanation="The Queen's Gambit Declined - solid defense.",
                            concept="Solid play",
                            what_to_watch="Black maintains the center but the bishop is blocked."
                        ),
                        "c6": MoveTeaching(
                            move="c6",
                            explanation="The Slav Defense - defending d5 solidly.",
                            concept="Solid defense",
                            what_to_watch="The bishop can still develop to f5!"
                        )
                    }
                },
                typical_plans_white=[
                    "Develop with Nc3, Bg5, e3",
                    "If Black takes: recover pawn and develop",
                    "Minority attack in QGD Exchange"
                ],
                typical_plans_black=[
                    "QGD: Play ...c5 or ...c6, develop bishop problem piece",
                    "QGA: ...a6, ...b5 to hold pawn",
                    "Slav: ...Bf5 before ...e6"
                ],
                critical_moments=[
                    "The c4 pawn decision",
                    "Black's bishop development",
                    "The ...c5 break"
                ],
                common_mistakes=[
                    "Black: Holding c4 pawn too long (QGA)",
                    "White: Mindless development",
                    "Both: Forgetting strategic plans"
                ],
                difficulty="intermediate",
                famous_games=["Kasparov-Karpov WC", "Capablanca's QGD"]
            ),
            
            "london_system": OpeningEntry(
                opening_id="london_system",
                name="London System",
                eco_code="D02",
                key_moves=["d4", "Nf6", "Bf4"],
                overview="Solid and easy to learn - the 'system' opening.",
                main_idea_white="Build a solid pyramid and develop the bishop before e3.",
                main_idea_black="Challenge White's setup actively.",
                move_teachings={
                    1: {
                        "d4": MoveTeaching(
                            move="d4",
                            explanation="Starting the London System.",
                            concept="Solid opening",
                            what_to_watch="Bf4 is coming next - BEFORE e3!"
                        )
                    },
                    2: {
                        "Bf4": MoveTeaching(
                            move="Bf4",
                            explanation="The London bishop - developed BEFORE e3!",
                            concept="Active bishop",
                            what_to_watch="Now e3 can be played without blocking the bishop."
                        )
                    },
                    3: {
                        "e3": MoveTeaching(
                            move="e3",
                            explanation="Completing the pyramid - d4, e3, c3 coming.",
                            concept="Solid structure",
                            what_to_watch="The London pyramid is very hard to break."
                        )
                    }
                },
                typical_plans_white=[
                    "Complete pyramid: d4, e3, c3",
                    "Develop with Bd3, Nf3, Nbd2",
                    "Ne5 is often strong"
                ],
                typical_plans_black=[
                    "Challenge with ...c5",
                    "Develop actively",
                    "Don't be passive!"
                ],
                critical_moments=[
                    "Bf4 BEFORE e3",
                    "The ...c5 break",
                    "Ne5 placement"
                ],
                common_mistakes=[
                    "White: Playing e3 before Bf4!",
                    "Black: Passive play",
                    "White: Not attacking when developed"
                ],
                difficulty="beginner",
                famous_games=["Many club games", "Kamsky's London"]
            ),
            
            "kings_indian_defense": OpeningEntry(
                opening_id="kings_indian_defense",
                name="King's Indian Defense",
                eco_code="E60-E99",
                key_moves=["d4", "Nf6", "c4", "g6", "Nc3", "Bg7"],
                overview="Dynamic and aggressive - Black fights back with ...f5.",
                main_idea_white="Gain space and control the center, queenside attack.",
                main_idea_black="Fianchetto and launch kingside attack with ...f5.",
                move_teachings={
                    1: {
                        "Nf6": MoveTeaching(
                            move="Nf6",
                            explanation="Flexible development - can transpose to many openings.",
                            concept="Flexibility",
                            what_to_watch="...g6 and ...Bg7 are coming for the King's Indian."
                        )
                    },
                    2: {
                        "g6": MoveTeaching(
                            move="g6",
                            explanation="Preparing the King's Indian fianchetto.",
                            concept="Fianchetto",
                            what_to_watch="The Bg7 will be Black's strongest piece!"
                        )
                    },
                    3: {
                        "Bg7": MoveTeaching(
                            move="Bg7",
                            explanation="The dragon bishop! Pressures the whole diagonal.",
                            concept="Active bishop",
                            what_to_watch="This bishop is worth more than White's center!"
                        )
                    }
                },
                typical_plans_white=[
                    "c5 break for queenside expansion",
                    "Keep center closed with d5",
                    "Classical: Be2, 0-0, then decide"
                ],
                typical_plans_black=[
                    "...f5-f4 kingside attack",
                    "...e5 to challenge center",
                    "Keep Bg7 alive!"
                ],
                critical_moments=[
                    "The ...f5 timing",
                    "When White plays c5",
                    "Race between attacks"
                ],
                common_mistakes=[
                    "Black: Too slow with ...f5",
                    "White: Ignoring Black's attack",
                    "Both: Wrong timing"
                ],
                difficulty="advanced",
                famous_games=["Kasparov's KID", "Fischer's games"]
            ),
            
            "nimzo_indian_defense": OpeningEntry(
                opening_id="nimzo_indian_defense",
                name="Nimzo-Indian Defense",
                eco_code="E20-E59",
                key_moves=["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"],
                overview="Strategic masterpiece - Black pins the knight.",
                main_idea_white="Develop while dealing with the pin, get the bishop pair.",
                main_idea_black="Double White's pawns with ...Bxc3 and play solidly.",
                move_teachings={
                    3: {
                        "Bb4": MoveTeaching(
                            move="Bb4",
                            explanation="The Nimzo-Indian! Pinning the knight that defends d4.",
                            concept="Pin",
                            what_to_watch="Black is willing to trade bishop for knight."
                        )
                    },
                    4: {
                        "Qc2": MoveTeaching(
                            move="Qc2",
                            explanation="Preparing to recapture with the queen, avoiding doubled pawns.",
                            concept="Avoiding weakness",
                            what_to_watch="White wants to keep the pawn structure intact."
                        ),
                        "Bxc3": MoveTeaching(
                            move="Bxc3",
                            explanation="Taking and doubling White's pawns!",
                            concept="Structural damage",
                            what_to_watch="The doubled pawns are White's weakness forever."
                        )
                    }
                },
                typical_plans_white=[
                    "Get bishop pair advantage",
                    "Open position for bishops",
                    "e4 break to activate pieces"
                ],
                typical_plans_black=[
                    "Double pawns with ...Bxc3",
                    "Keep position closed",
                    "Attack doubled pawns"
                ],
                critical_moments=[
                    "The ...Bxc3 decision",
                    "e4 break timing",
                    "Pawn structure"
                ],
                common_mistakes=[
                    "Black: Opening the position after ...Bxc3",
                    "White: Not using the bishops",
                    "Both: Forgetting strategic goals"
                ],
                difficulty="advanced",
                famous_games=["Nimzowitsch's games", "Kasparov's Nimzo"]
            ),
            
            # ============================================
            # FLANK OPENINGS (1.c4, 1.Nf3, etc.)
            # ============================================
            "english_opening": OpeningEntry(
                opening_id="english_opening",
                name="English Opening",
                eco_code="A10-A39",
                key_moves=["c4"],
                overview="Flexible flank opening - can transpose to many systems.",
                main_idea_white="Control d5 and keep options open.",
                main_idea_black="Counter in the center or mirror with ...c5.",
                move_teachings={
                    1: {
                        "c4": MoveTeaching(
                            move="c4",
                            explanation="The English Opening - flexible and positional.",
                            concept="Flexibility",
                            what_to_watch="White keeps options open - d4 may or may not come."
                        ),
                        "e5": MoveTeaching(
                            move="e5",
                            explanation="Reversed Sicilian - Black grabs the center.",
                            concept="Central control",
                            what_to_watch="Black has an extra tempo vs the Sicilian!"
                        ),
                        "c5": MoveTeaching(
                            move="c5",
                            explanation="Symmetrical English - fighting for d4.",
                            concept="Symmetry",
                            what_to_watch="Mirror structure - very strategic."
                        )
                    }
                },
                typical_plans_white=[
                    "g3, Bg2 fianchetto",
                    "Nc3, controlling d5",
                    "Flexible - can play d3 or d4"
                ],
                typical_plans_black=[
                    "...e5 for reversed Sicilian",
                    "...c5 for symmetrical play",
                    "...d5 break when ready"
                ],
                critical_moments=[
                    "d4 decision",
                    "d5 square control",
                    "Transposition options"
                ],
                common_mistakes=[
                    "White: Committing too early",
                    "Black: Being passive",
                    "Both: Missing transpositions"
                ],
                difficulty="intermediate",
                famous_games=["Botvinnik's English", "Kasparov's games"]
            ),
            
            "reti_opening": OpeningEntry(
                opening_id="reti_opening",
                name="Réti Opening",
                eco_code="A04-A09",
                key_moves=["Nf3", "d5", "g3"],
                overview="Hypermodern approach - let Black occupy the center, then attack it.",
                main_idea_white="Control center with pieces, not pawns.",
                main_idea_black="Occupy the center solidly.",
                move_teachings={
                    1: {
                        "Nf3": MoveTeaching(
                            move="Nf3",
                            explanation="The Réti - hypermodern control without pawns.",
                            concept="Hypermodern",
                            what_to_watch="White will attack the center from the flanks."
                        )
                    },
                    2: {
                        "g3": MoveTeaching(
                            move="g3",
                            explanation="Preparing the fianchetto - Bg2 will pressure d5.",
                            concept="Fianchetto",
                            what_to_watch="The bishop on g2 is very powerful."
                        )
                    }
                },
                typical_plans_white=[
                    "Fianchetto with Bg2",
                    "c4 to attack d5",
                    "Flexible development"
                ],
                typical_plans_black=[
                    "Solid center with ...d5, ...e6, ...c6",
                    "Develop naturally",
                    "Be ready for c4"
                ],
                critical_moments=[
                    "c4 timing",
                    "Center control",
                    "Transposition options"
                ],
                common_mistakes=[
                    "White: Being too passive",
                    "Black: Overextending",
                    "Both: Wrong piece placement"
                ],
                difficulty="intermediate",
                famous_games=["Réti's games", "Karpov's Réti"]
            )
        }


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def identify_opening(moves: List[str]) -> Optional[Dict]:
    """
    Identify the opening from a list of moves.
    
    Returns:
        Dict with opening info or None
    """
    db = OpeningTeachingDatabase()
    opening = db.identify_opening(moves)
    
    if not opening:
        return None
    
    return {
        "opening_id": opening.opening_id,
        "name": opening.name,
        "eco_code": opening.eco_code,
        "overview": opening.overview,
        "difficulty": opening.difficulty
    }


def get_move_teaching(
    moves: List[str],
    move_number: int,
    player_color: str
) -> Optional[str]:
    """
    Get teaching for a specific move in an opening.
    
    Args:
        moves: All moves played so far
        move_number: Move number
        player_color: "white" or "black"
    
    Returns:
        Teaching string or None
    """
    db = OpeningTeachingDatabase()
    opening = db.identify_opening(moves)
    
    if not opening:
        return None
    
    # Get the move at this position
    if move_number <= len(moves):
        move = moves[move_number - 1] if player_color == "white" else (
            moves[move_number] if move_number < len(moves) else None
        )
        
        if move:
            return db.get_move_teaching(opening.opening_id, move_number, move, player_color)
    
    return None
