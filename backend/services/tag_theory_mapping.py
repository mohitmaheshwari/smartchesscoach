"""
Tag-to-Theory Mapping
======================

Links game tags (from critical moments) to relevant theory modules.
When a user makes a mistake tagged as "back_rank_weakness", we can
suggest the "BACK_RANK_WEAKNESS" theory module.

This creates the connection between diagnosis (tags) and teaching (theory).
"""

# Map game tags to theory module IDs
TAG_TO_THEORY = {
    # Tactical tags -> Tactical theories
    "one_move_blunder": ["LPDO", "FORCING_MOVES_FIRST"],
    "hung_piece": ["LPDO"],
    "walked_into_check": ["FORCING_MOVES_FIRST"],
    "missed_fork": ["FORCING_MOVES_FIRST"],
    "captured_in_fork": ["FORCING_MOVES_FIRST"],
    "missed_pin": ["OVERLOADED_DEFENDER"],
    "pinned_piece_moved": ["OVERLOADED_DEFENDER"],
    "missed_skewer": ["FORCING_MOVES_FIRST"],
    "missed_discovery": ["DISCOVERED_ATTACK"],
    "back_rank_weakness": ["BACK_RANK_WEAKNESS"],
    "missed_back_rank_mate": ["BACK_RANK_WEAKNESS"],
    "king_exposed": ["BACK_RANK_WEAKNESS", "CASTLE_BEFORE_ATTACKING"],
    
    # Calculation tags -> Calculation theories
    "didnt_see_far_enough": ["ZWISCHENZUG", "FORCING_MOVES_FIRST"],
    "missed_zwischenzug": ["ZWISCHENZUG"],
    "premature_capture": ["ZWISCHENZUG", "FORCING_MOVES_FIRST"],
    
    # Positional tags -> Positional theories
    "weakened_pawn_structure": ["PAWN_BREAK_AWARENESS"],
    "bad_piece_trade": ["MINOR_PIECE_SUPERIORITY", "TRADE_ACTIVE_PIECES"],
    "passive_move": ["IMPROVE_WORST_PIECE"],
    "ignored_piece_activity": ["IMPROVE_WORST_PIECE", "OPEN_FILE_CONTROL"],
    
    # Opening tags -> Opening theories
    "opening_theory_deviation": ["FIGHT_FOR_CENTER", "DONT_MOVE_SAME_PIECE_TWICE"],
    "early_queen_adventure": ["QUEEN_OUT_TOO_EARLY"],
    "development_neglected": ["DONT_MOVE_SAME_PIECE_TWICE", "FIGHT_FOR_CENTER"],
    "castling_delayed": ["CASTLE_BEFORE_ATTACKING"],
    
    # Strategic tags -> Strategic theories
    "wrong_plan": ["CONVERT_BY_RESTRICTION"],
    "missed_breakthrough": ["FORCING_MOVES_FIRST", "PAWN_BREAK_AWARENESS"],
    "premature_attack": ["CASTLE_BEFORE_ATTACKING", "DONT_RUSH_PAWNS"],
    
    # Endgame tags -> Endgame theories
    "endgame_technique_error": ["ACTIVATE_KING_ENDGAME", "SIMPLIFY_WHEN_AHEAD"],
    "king_not_active": ["ACTIVATE_KING_ENDGAME"],
    "wrong_pawn_push": ["PUSH_PASSERS_CAREFULLY", "OUTSIDE_PASSED_PAWN"],
    "missed_opposition": ["OPPOSITION", "SQUARE_RULE"],
    
    # Conversion tags -> Conversion theories
    "threw_winning_position": ["SIMPLIFY_WHEN_AHEAD", "AVOID_COUNTERPLAY"],
    "drew_winning_endgame": ["PUSH_PASSERS_CAREFULLY", "ROOK_BEHIND_PASSER"],
    
    # Time tags
    "time_pressure_blunder": ["FORCING_MOVES_FIRST"],  # Quick decision framework
}


# Theory module details (from theory_modules.py)
THEORY_DETAILS = {
    # Tactical
    "LPDO": {
        "name": "Loose Pieces Drop Off",
        "category": "tactical",
        "summary": "Undefended pieces are targets. Before moving, check: Is anything hanging?",
        "key_insight": "Every piece should be protected or out of reach.",
    },
    "FORCING_MOVES_FIRST": {
        "name": "Checks, Captures, Threats",
        "category": "tactical",
        "summary": "Look for forcing moves before anything else: checks, captures, attacks.",
        "key_insight": "CCT order: Check first, then Capture, then Threat.",
    },
    "BACK_RANK_WEAKNESS": {
        "name": "Back Rank Safety",
        "category": "tactical",
        "summary": "A king trapped on the back rank with no escape is a target for mate.",
        "key_insight": "Create luft (escape square) early. h3/h6 is often worth a tempo.",
    },
    "ZWISCHENZUG": {
        "name": "In-Between Move",
        "category": "tactical",
        "summary": "Before making the 'obvious' recapture, check for a stronger intermediate move.",
        "key_insight": "The unexpected check or threat can flip the position.",
    },
    "DISCOVERED_ATTACK": {
        "name": "Discovered Attack",
        "category": "tactical",
        "summary": "Moving one piece to reveal an attack from another is powerful.",
        "key_insight": "The moving piece attacks while the revealed piece also attacks.",
    },
    "OVERLOADED_DEFENDER": {
        "name": "Overloaded Pieces",
        "category": "tactical",
        "summary": "A piece defending two things at once can be exploited.",
        "key_insight": "Make one defender do two jobs, then attack both targets.",
    },
    
    # Endgame
    "SQUARE_RULE": {
        "name": "Square of the Pawn",
        "category": "endgame",
        "summary": "If the king can enter the pawn's 'square', it can catch the pawn.",
        "key_insight": "Draw a diagonal from pawn to promotion; if king is inside, it catches.",
    },
    "OPPOSITION": {
        "name": "King Opposition",
        "category": "endgame",
        "summary": "Controlling the opposition means the enemy king must give way.",
        "key_insight": "Same file/rank, odd squares between = you have opposition.",
    },
    "ACTIVATE_KING_ENDGAME": {
        "name": "King Activity",
        "category": "endgame",
        "summary": "In the endgame, the king is a fighting piece. Activate it!",
        "key_insight": "Bring the king to the center as soon as queens are off.",
    },
    "ROOK_BEHIND_PASSER": {
        "name": "Rook Behind Passed Pawn",
        "category": "endgame",
        "summary": "Place your rook behind passed pawns - yours or opponent's.",
        "key_insight": "Rook activity increases as the pawn advances.",
    },
    "PUSH_PASSERS_CAREFULLY": {
        "name": "Passed Pawn Technique",
        "category": "endgame",
        "summary": "Don't rush passers. Advance when the opponent can't stop them.",
        "key_insight": "A passed pawn's power is in its threat, not always its advance.",
    },
    "OUTSIDE_PASSED_PAWN": {
        "name": "Outside Passed Pawn",
        "category": "endgame",
        "summary": "A pawn far from the action draws the enemy king away.",
        "key_insight": "Create an outside passer to distract the enemy king.",
    },
    "WRONG_BISHOP_CORNER": {
        "name": "Wrong Color Bishop",
        "category": "endgame",
        "summary": "A rook pawn + bishop of wrong color = draw against lone king.",
        "key_insight": "If your bishop can't control the promotion square, it's a draw.",
    },
    
    # Positional
    "GOOD_VS_BAD_BISHOP": {
        "name": "Good vs Bad Bishop",
        "category": "positional",
        "summary": "A bishop blocked by its own pawns is 'bad'. Keep pawns on opposite color.",
        "key_insight": "Put pawns on opposite color to your bishop.",
    },
    "KNIGHT_OUTPOSTS": {
        "name": "Knight Outposts",
        "category": "positional",
        "summary": "A knight on an outpost (protected, can't be challenged) is powerful.",
        "key_insight": "d5, e5, d4, e4 with pawn support = strong knight.",
    },
    "IMPROVE_WORST_PIECE": {
        "name": "Worst Piece Principle",
        "category": "positional",
        "summary": "Find your worst-placed piece and improve it.",
        "key_insight": "Your position is only as good as your worst piece.",
    },
    "PAWN_BREAK_AWARENESS": {
        "name": "Pawn Breaks",
        "category": "positional",
        "summary": "Pawn breaks open lines and create weaknesses. Time them well.",
        "key_insight": "c4, d4, e4, f4 breaks open the center. Use them!",
    },
    "OPEN_FILE_CONTROL": {
        "name": "Open File Control",
        "category": "positional",
        "summary": "Rooks belong on open files. Control them before your opponent.",
        "key_insight": "Rook on open file + 7th rank = domination.",
    },
    
    # Conversion
    "SIMPLIFY_WHEN_AHEAD": {
        "name": "Simplify When Ahead",
        "category": "conversion",
        "summary": "When up material, trade pieces (not pawns) to reach a winning endgame.",
        "key_insight": "More pieces = more chances for opponent. Simplify!",
    },
    "AVOID_COUNTERPLAY": {
        "name": "Avoid Counterplay",
        "category": "conversion",
        "summary": "When winning, prevent opponent's activity. Don't give them chances.",
        "key_insight": "The opponent's only hope is counterplay. Deny it.",
    },
    "TRADE_ACTIVE_PIECES": {
        "name": "Trade Active Pieces",
        "category": "conversion",
        "summary": "Trade off the opponent's active pieces, keep their passive ones.",
        "key_insight": "An opponent with only bad pieces is helpless.",
    },
    "CONVERT_BY_RESTRICTION": {
        "name": "Restriction Technique",
        "category": "conversion",
        "summary": "Limit opponent's pieces before attacking. Zugzwang wins games.",
        "key_insight": "Make opponent's pieces stand still while you improve.",
    },
    
    # Opening
    "DONT_MOVE_SAME_PIECE_TWICE": {
        "name": "Development First",
        "category": "opening",
        "summary": "Move each piece once before moving any piece twice.",
        "key_insight": "Get all pieces into the game before starting tactics.",
    },
    "CASTLE_BEFORE_ATTACKING": {
        "name": "Castle Early",
        "category": "opening",
        "summary": "King safety first. Castle before launching attacks.",
        "key_insight": "An uncastled king is a target. Castle by move 10.",
    },
    "FIGHT_FOR_CENTER": {
        "name": "Central Control",
        "category": "opening",
        "summary": "Control the center with pawns and pieces. It's the key to the board.",
        "key_insight": "d4, e4, d5, e5 - the battle is for these squares.",
    },
    "QUEEN_OUT_TOO_EARLY": {
        "name": "Queen Safety",
        "category": "opening",
        "summary": "Don't bring the queen out early - it becomes a target.",
        "key_insight": "Queen on the board early = tempo loss from attacks.",
    },
    "DONT_RUSH_PAWNS": {
        "name": "Don't Rush Pawns",
        "category": "opening",
        "summary": "Pawn moves can't be taken back. Only advance with purpose.",
        "key_insight": "Every pawn move creates a weakness. Make them count.",
    },
}


def get_theories_for_tag(tag_id: str) -> list:
    """Get relevant theory modules for a game tag"""
    theory_ids = TAG_TO_THEORY.get(tag_id, [])
    return [THEORY_DETAILS.get(tid) for tid in theory_ids if tid in THEORY_DETAILS]


def get_theory_summary(tag_id: str) -> dict:
    """Get a summary of recommended theories for a tag"""
    theories = get_theories_for_tag(tag_id)
    if not theories:
        return None
    
    primary = theories[0]
    return {
        "primary_theory": primary,
        "additional_theories": theories[1:],
        "total_count": len(theories),
    }


def enrich_moment_with_theories(moment: dict) -> dict:
    """Add theory recommendations to a critical moment"""
    tags = moment.get("tags", {})
    primary_tag = tags.get("primary_tag")
    
    if not primary_tag:
        return moment
    
    theory_info = get_theory_summary(primary_tag)
    if theory_info:
        moment["recommended_theory"] = theory_info
    
    return moment
