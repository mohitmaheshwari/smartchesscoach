"""
Opening Plans Database - 20 Common Openings

Each opening has:
- Name and ECO code
- Key moves to identify it
- Main PLANS (not just moves)
- Teaching points for 800-1800 players
- Simple explanations without jargon
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class OpeningPlan:
    """A complete opening plan for teaching"""
    name: str
    eco_codes: List[str]  # ECO codes this covers
    identifying_moves: List[str]  # Move sequence to identify
    main_ideas: List[str]  # 2-3 main plans in plain language
    key_squares: List[str]  # Important squares to highlight
    typical_mistakes: List[str]  # Common errors at club level
    simple_explanation: str  # One-liner for beginners
    teaching_moments: Dict[str, str]  # move -> what to teach


# ==================== WHITE OPENINGS ====================

ITALIAN_GAME = OpeningPlan(
    name="Italian Game",
    eco_codes=["C50", "C51", "C52", "C53", "C54"],
    identifying_moves=["e4", "e5", "Nf3", "Nc6", "Bc4"],
    main_ideas=[
        "Put your bishop on c4 pointing at f7 - their weak spot",
        "Castle quickly to keep your king safe",
        "Control the center, then attack the kingside"
    ],
    key_squares=["c4", "f7", "d4", "f4"],
    typical_mistakes=[
        "Attacking f7 too early before castling",
        "Forgetting to develop the other pieces",
        "Moving the same piece twice in opening"
    ],
    simple_explanation="Your bishop aims at f7 (only the king guards it). Develop, castle, then attack.",
    teaching_moments={
        "e5": "Fighting for the center! This creates an open game with lots of tactics. Ready for some action?",
        "Nf6": "Good development! The knight attacks e4. Can you see what square it's aiming for?",
        "Nc6": "Natural move - the knight develops and defends e5. How many pieces protect that pawn now?",
        "Bc5": "Mirror image! Your bishop also eyes f2 - white's weak pawn. Now it's a real battle!",
        "Be7": "Solid choice - preparing to castle. Sometimes safe is better than aggressive.",
        "Bc4": "This is the Italian Game! The bishop stares at f7 - the weakest point. Only the king guards it.",
        "O-O": "Castle! King safety first, attack second. This is how grandmasters play.",
        "d3": "Supporting the center and opening a path for the bishop. Good technique!",
        "c3": "Preparing d4 - the big center push. Can you see the plan coming together?",
        "d6": "Solid - defending e5 and preparing development. What should develop next?",
    }
)

RUY_LOPEZ = OpeningPlan(
    name="Ruy Lopez (Spanish Game)",
    eco_codes=["C60", "C61", "C62", "C63", "C64", "C65", "C66", "C67", "C68", "C69", "C70", "C71", "C72", "C73", "C74", "C75", "C76", "C77", "C78", "C79", "C80", "C81", "C82", "C83", "C84", "C85", "C86", "C87", "C88", "C89", "C90", "C91", "C92", "C93", "C94", "C95", "C96", "C97", "C98", "C99"],
    identifying_moves=["e4", "e5", "Nf3", "Nc6", "Bb5"],
    main_ideas=[
        "Put pressure on their knight that defends e5",
        "Build a strong center with d4 later",
        "Slow, strategic game - be patient"
    ],
    key_squares=["b5", "c6", "d4", "e5"],
    typical_mistakes=[
        "Taking the knight too early (Bxc6) without a plan",
        "Rushing the attack before completing development",
        "Forgetting that your bishop can retreat to a4 or c2"
    ],
    simple_explanation="Your bishop puts pressure on the knight guarding e5. It's a slow, strong opening.",
    teaching_moments={
        "Bb5": "This pins their knight to the king's defense of e5. They have to worry about it.",
        "O-O": "Castle first, attack later. The Ruy Lopez is a patient opening.",
        "Re1": "Your rook now supports the e4 pawn. Solid.",
        "c3": "Preparing d4. This is the main plan in the Ruy Lopez.",
    }
)

LONDON_SYSTEM = OpeningPlan(
    name="London System",
    eco_codes=["D00", "A46", "A48"],
    identifying_moves=["d4", "Nf3", "Bf4"],
    main_ideas=[
        "Develop bishop to f4 BEFORE playing e3",
        "Build a solid pyramid: pawns on d4, e3, c3",
        "Simple and safe - hard for opponent to attack"
    ],
    key_squares=["f4", "d4", "e3", "c3"],
    typical_mistakes=[
        "Playing e3 before Bf4 (bishop gets trapped)",
        "Being too passive - you still need to make a plan",
        "Forgetting to castle"
    ],
    simple_explanation="Put bishop on f4 first, then build a solid wall. Safe and easy to play.",
    teaching_moments={
        "Bf4": "Get this bishop out BEFORE e3, otherwise it's stuck forever.",
        "e3": "Now your pawn structure is solid. The bishop is already out.",
        "Bd3": "Your bishops are developed. Looking good!",
        "O-O": "Perfect. Safe king, developed pieces. Now look for a plan.",
        "c3": "Supporting d4 and giving your queen a square on c2.",
    }
)

QUEENS_GAMBIT = OpeningPlan(
    name="Queen's Gambit",
    eco_codes=["D06", "D07", "D08", "D09", "D10", "D11", "D12", "D13", "D14", "D15", "D16", "D17", "D18", "D19", "D20", "D21", "D22", "D23", "D24", "D25", "D26", "D27", "D28", "D29", "D30", "D31", "D32", "D33", "D34", "D35", "D36", "D37", "D38", "D39", "D40", "D41", "D42", "D43", "D44", "D45", "D46", "D47", "D48", "D49"],
    identifying_moves=["d4", "d5", "c4"],
    main_ideas=[
        "Offer the c4 pawn to open the center",
        "If they take, you get a strong center with e4",
        "Control the center, then attack"
    ],
    key_squares=["c4", "d4", "d5", "e4"],
    typical_mistakes=[
        "Trying to hold the gambit pawn (wastes time)",
        "Forgetting to develop pieces while fighting for center",
        "Moving the queen out too early"
    ],
    simple_explanation="Offer a pawn to control the center. If they take, you play e4 and dominate.",
    teaching_moments={
        "c4": "This is the Queen's Gambit. You're offering a pawn to fight for the center.",
        "e4": "Now you have two pawns in the center. Very strong!",
        "Nc3": "Developing and supporting your center. Good move.",
        "Nf3": "Knights before bishops. Classic development.",
    }
)

SCOTCH_GAME = OpeningPlan(
    name="Scotch Game",
    eco_codes=["C44", "C45"],
    identifying_moves=["e4", "e5", "Nf3", "Nc6", "d4"],
    main_ideas=[
        "Open the center immediately",
        "Get active piece play quickly",
        "Don't worry about giving up the d4 pawn"
    ],
    key_squares=["d4", "e5", "c3"],
    typical_mistakes=[
        "Taking back with the queen too early (Qxd4 gets attacked)",
        "Not developing pieces fast enough",
        "Forgetting to castle"
    ],
    simple_explanation="Open the center right away. Fast, attacking chess. Don't be passive!",
    teaching_moments={
        "d4": "Opening the center immediately. This is the Scotch Game - aggressive!",
        "Nxd4": "Good recapture with the knight. Keeps developing.",
        "Bc4": "Now your bishop is active, pointing at f7.",
    }
)

VIENNA_GAME = OpeningPlan(
    name="Vienna Game",
    eco_codes=["C25", "C26", "C27", "C28", "C29"],
    identifying_moves=["e4", "e5", "Nc3"],
    main_ideas=[
        "Prepare f4 to attack the center",
        "Can transpose into sharp or quiet positions",
        "Flexible - keep your options open"
    ],
    key_squares=["c3", "f4", "d5"],
    typical_mistakes=[
        "Playing f4 too early without preparation",
        "Not knowing what plan to follow",
        "Being passive"
    ],
    simple_explanation="Knight to c3 prepares f4. Flexible opening - you choose if it's sharp or calm.",
    teaching_moments={
        "Nc3": "This is the Vienna Game. You're preparing f4 or Bc4 - flexible!",
        "f4": "Now it's sharp! You're attacking their e5 pawn.",
        "Bc4": "Good development, similar ideas to the Italian.",
    }
)


# ==================== BLACK RESPONSES ====================

SICILIAN_DEFENSE = OpeningPlan(
    name="Sicilian Defense",
    eco_codes=["B20", "B21", "B22", "B23", "B24", "B25", "B26", "B27", "B28", "B29", "B30", "B31", "B32", "B33", "B34", "B35", "B36", "B37", "B38", "B39", "B40", "B41", "B42", "B43", "B44", "B45", "B46", "B47", "B48", "B49", "B50", "B51", "B52", "B53", "B54", "B55", "B56", "B57", "B58", "B59", "B60", "B61", "B62", "B63", "B64", "B65", "B66", "B67", "B68", "B69", "B70", "B71", "B72", "B73", "B74", "B75", "B76", "B77", "B78", "B79", "B80", "B81", "B82", "B83", "B84", "B85", "B86", "B87", "B88", "B89", "B90", "B91", "B92", "B93", "B94", "B95", "B96", "B97", "B98", "B99"],
    identifying_moves=["e4", "c5"],
    main_ideas=[
        "Fight for the center from the side with c5",
        "After d4 exchange, you get the open c-file for your rook",
        "Counter-attack on the queenside while white attacks kingside"
    ],
    key_squares=["c5", "d4", "c-file"],
    typical_mistakes=[
        "Playing too passively - the Sicilian needs active play",
        "Forgetting to develop the queenside pieces",
        "Castling kingside when white has a strong attack there"
    ],
    simple_explanation="c5 fights for the center sideways. When pawns trade on d4, your rook uses the c-file.",
    teaching_moments={
        "c5": "The Sicilian Defense! Notice how c5 fights for the d4 square from the side? This is chess's most combative response to e4.",
        "d6": "Solid setup - this is often the start of the Dragon or Najdorf. Can you guess why we delay developing the knight?",
        "d5": "Direct challenge! We're not waiting around. This grabs space immediately. What do you think happens if white takes?",
        "Nf6": "See how this knight attacks e4? In the Sicilian, we constantly pressure white's center. What would happen if they ignore it?",
        "Nc6": "The knight develops toward d4 - our dream square. Every piece should aim for the center. Where should your knight go?",
        "e6": "The Scheveningen - very solid. We're preparing to play d5 when the time is right. Patience is key here.",
        "a6": "The Najdorf! A small move with big ideas - it prevents Bb5 pins and prepares b5-b4 expansion. One of the richest openings in chess!",
        "g6": "The Dragon setup! The bishop on g7 will be a monster on that diagonal. What diagonal is it aiming at?",
    }
)

FRENCH_DEFENSE = OpeningPlan(
    name="French Defense",
    eco_codes=["C00", "C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14", "C15", "C16", "C17", "C18", "C19"],
    identifying_moves=["e4", "e6"],
    main_ideas=[
        "Solid structure - let white overextend",
        "Your light bishop is blocked but your position is solid",
        "Attack white's center with c5 and f6 later"
    ],
    key_squares=["e6", "d5", "c5"],
    typical_mistakes=[
        "Not playing c5 to challenge the center",
        "Leaving the light bishop stuck forever",
        "Being too passive"
    ],
    simple_explanation="e6 is solid. You'll play d5 next and challenge white's center with c5 later.",
    teaching_moments={
        "e6": "The French Defense - very solid! The plan is to play d5 next and create a strong center. Ready?",
        "d5": "Perfect timing! Now we're fighting for the center. What happens to the pawns if white captures?",
        "c5": "This is THE key move in the French! We're attacking d4 - white's center is under pressure. See the idea?",
        "Nc6": "Knight to c6 adds more pressure to d4. Count the attackers - how many pieces target that square now?",
        "Bb4": "Pinning the knight! This is the Winawer variation. If the knight moves, what happens to d4?",
    }
)

CARO_KANN = OpeningPlan(
    name="Caro-Kann Defense",
    eco_codes=["B10", "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18", "B19"],
    identifying_moves=["e4", "c6"],
    main_ideas=[
        "Prepare d5 with c6 supporting it",
        "Solid structure like the French, but bishop isn't trapped",
        "Exchange pawns in center, then develop freely"
    ],
    key_squares=["c6", "d5", "c8"],
    typical_mistakes=[
        "Not playing d5 after c6",
        "Being too passive in the middlegame",
        "Forgetting to develop the kingside"
    ],
    simple_explanation="c6 prepares d5 with support. Unlike the French, your bishop stays free.",
    teaching_moments={
        "c6": "The Caro-Kann! Preparing d5 with pawn support.",
        "d5": "Good! Now you're fighting for the center with your pawn supported.",
        "Bf5": "See? Your bishop is free, unlike in the French Defense.",
        "e6": "Solid. Supporting d5 and preparing development.",
    }
)

KINGS_INDIAN = OpeningPlan(
    name="King's Indian Defense",
    eco_codes=["E60", "E61", "E62", "E63", "E64", "E65", "E66", "E67", "E68", "E69", "E70", "E71", "E72", "E73", "E74", "E75", "E76", "E77", "E78", "E79", "E80", "E81", "E82", "E83", "E84", "E85", "E86", "E87", "E88", "E89", "E90", "E91", "E92", "E93", "E94", "E95", "E96", "E97", "E98", "E99"],
    identifying_moves=["d4", "Nf6", "c4", "g6", "Nc3", "Bg7"],
    main_ideas=[
        "Let white build a big center, then attack it",
        "Fianchetto your bishop to g7 - it's a monster on the diagonal",
        "Play e5 and attack on the kingside"
    ],
    key_squares=["g7", "e5", "f4", "h5"],
    typical_mistakes=[
        "Playing too passively and letting white crush you",
        "Not playing e5 to challenge the center",
        "Forgetting the kingside attack with f5"
    ],
    simple_explanation="Let white build up, then explode on the kingside with e5 and f5. Your g7 bishop is powerful.",
    teaching_moments={
        "Nf6": "Good start. Flexible - can go to many openings.",
        "g6": "Fianchetto! Your bishop will be strong on g7.",
        "Bg7": "Beautiful. This bishop controls the whole diagonal.",
        "O-O": "King is safe. Now prepare e5 and the kingside attack!",
        "e5": "The key break! Now you have counterplay.",
    }
)

NIMZO_INDIAN = OpeningPlan(
    name="Nimzo-Indian Defense",
    eco_codes=["E20", "E21", "E22", "E23", "E24", "E25", "E26", "E27", "E28", "E29", "E30", "E31", "E32", "E33", "E34", "E35", "E36", "E37", "E38", "E39", "E40", "E41", "E42", "E43", "E44", "E45", "E46", "E47", "E48", "E49", "E50", "E51", "E52", "E53", "E54", "E55", "E56", "E57", "E58", "E59"],
    identifying_moves=["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"],
    main_ideas=[
        "Pin the knight on c3 with your bishop",
        "Control e4 - don't let white play e4 easily",
        "If they play a3, trade bishop for knight and double their pawns"
    ],
    key_squares=["b4", "c3", "e4"],
    typical_mistakes=[
        "Trading the bishop too early without a plan",
        "Not fighting for e4 control",
        "Being too passive after the opening"
    ],
    simple_explanation="Pin their knight with Bb4. If they kick your bishop, trade it and give them doubled pawns.",
    teaching_moments={
        "Bb4": "The Nimzo-Indian! You're pinning their knight and controlling e4.",
        "O-O": "Good. Castle first, make plans later.",
        "c5": "Attacking d4. Good counterplay!",
        "Bxc3": "Now they have doubled pawns on c3. That's a weakness.",
    }
)

QUEENS_GAMBIT_DECLINED = OpeningPlan(
    name="Queen's Gambit Declined",
    eco_codes=["D30", "D31", "D32", "D33", "D34", "D35", "D36", "D37", "D38", "D39", "D40", "D41", "D42", "D43", "D44", "D45", "D46", "D47", "D48", "D49"],
    identifying_moves=["d4", "d5", "c4", "e6"],
    main_ideas=[
        "Don't take the pawn - defend d5 solidly",
        "Develop pieces behind your pawn wall",
        "Wait for the right moment to free your position with c5 or e5"
    ],
    key_squares=["d5", "e6", "c5"],
    typical_mistakes=[
        "Never playing c5 or e5 to free your pieces",
        "Leaving your light bishop trapped",
        "Being too passive"
    ],
    simple_explanation="Defend d5 with e6. Solid, but you must play c5 eventually to free your pieces.",
    teaching_moments={
        "e6": "The Queen's Gambit Declined. Solid! You keep your d5 pawn.",
        "Nf6": "Good development, attacking their e4 square.",
        "Be7": "Developing and preparing to castle.",
        "O-O": "Safe king. Now look for c5 to free your position.",
        "c5": "The key break! Now your pieces have room.",
    }
)

SLAV_DEFENSE = OpeningPlan(
    name="Slav Defense",
    eco_codes=["D10", "D11", "D12", "D13", "D14", "D15", "D16", "D17", "D18", "D19"],
    identifying_moves=["d4", "d5", "c4", "c6"],
    main_ideas=[
        "Defend d5 with c6 (not e6) so your bishop is free",
        "Your light bishop can go to f5 or g4",
        "Solid structure with active pieces"
    ],
    key_squares=["c6", "d5", "f5", "g4"],
    typical_mistakes=[
        "Playing e6 and blocking your bishop anyway",
        "Being too passive",
        "Not developing the light bishop early"
    ],
    simple_explanation="Defend d5 with c6 so your bishop can go to f5. Best of both worlds!",
    teaching_moments={
        "c6": "The Slav! You defend d5 AND keep your bishop free.",
        "Bf5": "See? Your bishop is out and active. That's the point of the Slav.",
        "e6": "Now solid. But make sure you got your bishop out first!",
        "Nf6": "Good development.",
    }
)

SCANDINAVIAN = OpeningPlan(
    name="Scandinavian Defense",
    eco_codes=["B01"],
    identifying_moves=["e4", "d5"],
    main_ideas=[
        "Immediately challenge e4",
        "After exd5 Qxd5, queen comes out early but it's okay",
        "Simple development, solid position"
    ],
    key_squares=["d5", "e4", "a5", "d6"],
    typical_mistakes=[
        "Keeping the queen in the center too long",
        "Not developing pieces quickly",
        "Forgetting to castle"
    ],
    simple_explanation="Immediately attack e4. Your queen comes out early but finds a safe square on a5.",
    teaching_moments={
        "d5": "The Scandinavian! Direct attack on e4.",
        "Qxd5": "Your queen is out early but it's okay here.",
        "Qa5": "Good square. Your queen is safe and active.",
        "Nf6": "Developing with tempo if white's queen is on d1.",
    }
)

PHILIDOR_DEFENSE = OpeningPlan(
    name="Philidor Defense",
    eco_codes=["C41"],
    identifying_moves=["e4", "e5", "Nf3", "d6"],
    main_ideas=[
        "Very solid - protect e5 with d6",
        "You can play f5 later for counterplay",
        "Patient, waiting for white to overextend"
    ],
    key_squares=["d6", "e5", "f5"],
    typical_mistakes=[
        "Being too passive",
        "Never playing f5 for counterplay",
        "Letting white dominate the center"
    ],
    simple_explanation="d6 is very solid. Protect e5 first, then look for f5 to counter-attack.",
    teaching_moments={
        "d6": "The Philidor Defense. Very solid! You protect e5 first.",
        "Nf6": "Developing and attacking e4.",
        "Be7": "Preparing to castle. Solid.",
        "O-O": "Good. Now you can think about f5 for counterplay.",
    }
)

PETROV_DEFENSE = OpeningPlan(
    name="Petrov Defense (Russian Game)",
    eco_codes=["C42", "C43"],
    identifying_moves=["e4", "e5", "Nf3", "Nf6"],
    main_ideas=[
        "Counter-attack e4 instead of defending e5",
        "Leads to equal, solid positions",
        "If white takes e5, don't take back immediately - play d6 first"
    ],
    key_squares=["e4", "e5", "d6"],
    typical_mistakes=[
        "Taking back on e5 immediately (Nxe4 is a trap!)",
        "Not knowing the theory",
        "Being passive"
    ],
    simple_explanation="Attack e4 right back! If they take your e5, play d6 first, then take back safely.",
    teaching_moments={
        "Nf6": "The Petrov! You attack e4 right back instead of defending e5.",
        "d6": "Important! This protects your knight on f6 and controls the center.",
        "Nxe4": "Now you can take back safely.",
    }
)


# ==================== OPENING DATABASE ====================

OPENING_PLANS: Dict[str, OpeningPlan] = {
    # White openings
    "italian": ITALIAN_GAME,
    "ruy_lopez": RUY_LOPEZ,
    "spanish": RUY_LOPEZ,
    "london": LONDON_SYSTEM,
    "queens_gambit": QUEENS_GAMBIT,
    "scotch": SCOTCH_GAME,
    "vienna": VIENNA_GAME,
    
    # Black responses
    "sicilian": SICILIAN_DEFENSE,
    "french": FRENCH_DEFENSE,
    "caro_kann": CARO_KANN,
    "kings_indian": KINGS_INDIAN,
    "nimzo_indian": NIMZO_INDIAN,
    "qgd": QUEENS_GAMBIT_DECLINED,
    "slav": SLAV_DEFENSE,
    "scandinavian": SCANDINAVIAN,
    "philidor": PHILIDOR_DEFENSE,
    "petrov": PETROV_DEFENSE,
}


def get_opening_by_moves(moves: List[str]) -> Optional[OpeningPlan]:
    """
    Try to identify opening from move list.
    Returns the best matching opening plan.
    """
    move_str = " ".join(moves[:6]).lower()
    
    # Italian: e4 e5 Nf3 Nc6 Bc4
    if "e4" in move_str and "e5" in move_str and "bc4" in move_str:
        return ITALIAN_GAME
    
    # Ruy Lopez: e4 e5 Nf3 Nc6 Bb5
    if "e4" in move_str and "e5" in move_str and "bb5" in move_str:
        return RUY_LOPEZ
    
    # Sicilian: e4 c5
    if move_str.startswith("e4") and "c5" in move_str[:8]:
        return SICILIAN_DEFENSE
    
    # French: e4 e6
    if "e4" in move_str and "e6" in move_str[:8]:
        return FRENCH_DEFENSE
    
    # Caro-Kann: e4 c6
    if "e4" in move_str and "c6" in move_str[:8]:
        return CARO_KANN
    
    # London: d4 Nf3 Bf4
    if "d4" in move_str and "bf4" in move_str:
        return LONDON_SYSTEM
    
    # Queen's Gambit: d4 d5 c4
    if "d4" in move_str and "d5" in move_str and "c4" in move_str:
        # Check if declined
        if "e6" in move_str:
            return QUEENS_GAMBIT_DECLINED
        if "c6" in move_str:
            return SLAV_DEFENSE
        return QUEENS_GAMBIT
    
    # King's Indian: d4 Nf6 c4 g6
    if "d4" in move_str and "g6" in move_str:
        return KINGS_INDIAN
    
    # Scandinavian: e4 d5
    if "e4" in move_str and "d5" in move_str[:8]:
        return SCANDINAVIAN
    
    # Petrov: e4 e5 Nf3 Nf6
    if "e4" in move_str and "e5" in move_str and move_str.count("nf") >= 2:
        return PETROV_DEFENSE
    
    return None


def get_teaching_for_move(opening: OpeningPlan, move_san: str) -> Optional[str]:
    """Get teaching moment for a specific move in an opening"""
    # Normalize move (remove + and # symbols)
    clean_move = move_san.replace("+", "").replace("#", "")
    return opening.teaching_moments.get(clean_move)


def get_all_openings() -> List[OpeningPlan]:
    """Get all opening plans"""
    return list(set(OPENING_PLANS.values()))
