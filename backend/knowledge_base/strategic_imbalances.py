"""
ChessGuru Canon - Strategic Imbalances Knowledge Base

These are the key positional concepts that determine middlegame strategy.
Each entry follows the same structured schema for RAG retrieval.
"""

STRATEGIC_IMBALANCES = {
    # ============================================
    # 1. GOOD BISHOP vs BAD BISHOP
    # ============================================
    "good_bishop": {
        "concept_id": "good_bishop",
        "name": "Good Bishop (vs Bad Bishop)",
        "trigger_conditions": [
            "Bishop on opposite color to own pawns",
            "Bishop has open diagonals",
            "Opponent bishop blocked by own pawns",
            "Common in French, Caro-Kann structures"
        ],
        "strategic_goal_with": {
            "summary": "Exploit the bishop imbalance",
            "plans": [
                "Keep center pawns fixed on opponent bishop's color",
                "Open diagonals for your bishop",
                "Avoid trading your good bishop",
                "Create targets on squares your bishop controls"
            ],
            "key_moves": ["Maneuver to long diagonal", "Fix opponent's pawns"]
        },
        "strategic_goal_against": {
            "summary": "Trade bad bishop or change pawn structure",
            "plans": [
                "Trade bad bishop for ANY piece",
                "Push pawns to open bishop's diagonal",
                "Change pawn structure with breaks",
                "Use knights on squares bishop can't control"
            ],
            "key_moves": ["Bishop trade maneuvers", "Pawn breaks to free bishop"]
        },
        "amateur_errors": {
            "with_good": [
                "Trading good bishop for knight without reason",
                "Allowing pawn structure to change in opponent's favor",
                "Not using bishop's superiority actively"
            ],
            "with_bad": [
                "Keeping bad bishop instead of trading",
                "Not trying to free it with pawn breaks",
                "Ignoring the long-term disadvantage"
            ]
        },
        "conversion_pattern": {
            "summary": "Good bishop in endgame is usually decisive",
            "method": "Trade into bishop vs knight or bishop vs bad bishop endgame"
        },
        "model_positions": ["French Defense", "Caro-Kann Exchange", "Slav Defense"]
    },

    # ============================================
    # 2. BISHOP PAIR
    # ============================================
    "bishop_pair": {
        "concept_id": "bishop_pair",
        "name": "Bishop Pair Advantage",
        "trigger_conditions": [
            "Two bishops vs bishop + knight or two knights",
            "Open or semi-open position",
            "Pawns on both flanks"
        ],
        "strategic_goal_with": {
            "summary": "Open the position and use diagonals",
            "plans": [
                "Open position with pawn exchanges",
                "Place bishops on long diagonals",
                "Create threats on both flanks simultaneously",
                "Bishops work best in open positions with play on both wings"
            ],
            "key_moves": ["Pawn breaks to open position", "Diagonal control"]
        },
        "strategic_goal_against": {
            "summary": "Keep position closed, trade one bishop",
            "plans": [
                "Keep pawns fixed, position closed",
                "Trade one bishop to destroy the pair",
                "Create outposts for knights",
                "Block diagonals with pawns"
            ],
            "key_moves": ["Close position", "Force bishop trade"]
        },
        "amateur_errors": {
            "with_pair": [
                "Trading one bishop unnecessarily",
                "Keeping position closed",
                "Not using both bishops actively"
            ],
            "against_pair": [
                "Opening the position",
                "Not trading one bishop when possible",
                "Letting bishops dominate diagonals"
            ]
        },
        "conversion_pattern": {
            "summary": "Bishop pair is worth ~0.5 pawn in open positions",
            "method": "Open position, create threats on both flanks"
        }
    },

    # ============================================
    # 3. KNIGHT OUTPOST
    # ============================================
    "knight_outpost": {
        "concept_id": "knight_outpost",
        "name": "Knight Outpost",
        "trigger_conditions": [
            "Knight on advanced square (4th-6th rank)",
            "Cannot be attacked by opponent pawns",
            "Square is protected by own pawn",
            "Classic: Nd5 in Sicilian, Ne4 in Slav"
        ],
        "strategic_goal_with": {
            "summary": "Knight outpost = permanent advantage",
            "plans": [
                "Knight on outpost controls key squares",
                "Outpost knight often worth more than bishop",
                "Use knight as anchor for attack",
                "Only trade knight for clear compensation"
            ],
            "key_moves": ["Maintain knight on outpost", "Support with other pieces"]
        },
        "strategic_goal_against": {
            "summary": "Trade the knight or create counterplay",
            "plans": [
                "Trade the outposted knight immediately if possible",
                "Undermine the pawn supporting the outpost",
                "Create threats elsewhere to distract",
                "Challenge with your own knight"
            ],
            "key_moves": ["Bishop trade for knight", "Pawn advance to challenge"]
        },
        "amateur_errors": {
            "with_outpost": [
                "Trading outpost knight too easily",
                "Not supporting the knight properly",
                "Overestimating knight - still need other play"
            ],
            "against_outpost": [
                "Allowing knight to settle permanently",
                "Not challenging the supporting pawn",
                "Passive play accepting the outpost"
            ]
        },
        "key_squares": ["d5/e5 for White", "d4/e4 for Black"]
    },

    # ============================================
    # 4. WEAK SQUARES / COLOR COMPLEX
    # ============================================
    "weak_squares": {
        "concept_id": "weak_squares",
        "name": "Weak Square Complex",
        "trigger_conditions": [
            "Multiple squares of same color cannot be defended by pawns",
            "Usually after bishop trade of that color",
            "Common: weak dark squares after trading dark-squared bishop"
        ],
        "strategic_goal_with": {
            "summary": "Occupy and exploit weak squares",
            "plans": [
                "Place pieces (especially knights) on weak squares",
                "Attack along the weak diagonal",
                "Create entry points through weak squares",
                "Weak squares don't heal - permanent advantage"
            ],
            "key_moves": ["Knight to weak square", "Rook entry via weak square"]
        },
        "strategic_goal_against": {
            "summary": "Minimize damage, block key squares",
            "plans": [
                "Place pieces on weak squares defensively",
                "Trade pieces that exploit the weakness",
                "Create counterplay elsewhere",
                "Don't create MORE weak squares"
            ],
            "key_moves": ["Defensive piece placement", "Active counterplay"]
        },
        "amateur_errors": {
            "exploiting": [
                "Not using weak squares actively",
                "Trading pieces that control weak squares",
                "Slow play when direct action is possible"
            ],
            "defending": [
                "Creating additional weak squares",
                "Not blocking entry with pieces",
                "Passive defense without counterplay"
            ]
        }
    },

    # ============================================
    # 5. SPACE ADVANTAGE
    # ============================================
    "space_advantage": {
        "concept_id": "space_advantage",
        "name": "Space Advantage",
        "trigger_conditions": [
            "Pawns advanced beyond 4th rank",
            "More squares controlled in enemy half",
            "Opponent pieces cramped",
            "Common in French Advance, King's Indian Attack"
        ],
        "strategic_goal_with": {
            "summary": "Use space to maneuver, prevent breaks",
            "plans": [
                "Transfer pieces easily behind pawn chain",
                "Prevent opponent's pawn breaks",
                "Build up slowly - space restricts opponent",
                "Don't rush - cramped positions collapse gradually"
            ],
            "key_moves": ["Prevent breaks", "Piece maneuvers"]
        },
        "strategic_goal_against": {
            "summary": "Break through or trade pieces",
            "plans": [
                "Seek pawn breaks to challenge space",
                "Trade pieces to reduce cramping",
                "Don't let position get worse slowly",
                "Counter-attack rather than defend"
            ],
            "key_moves": ["Pawn break!", "Piece trades"]
        },
        "amateur_errors": {
            "with_space": [
                "Rushing attack when slow buildup wins",
                "Allowing opponent to break",
                "Overextending the pawns"
            ],
            "against_space": [
                "Passive waiting instead of breaking",
                "Not trading pieces",
                "Allowing position to deteriorate"
            ]
        },
        "conversion_pattern": {
            "summary": "Space advantage usually leads to material or mating attack",
            "method": "Gradual squeeze until position collapses"
        }
    },

    # ============================================
    # 6. LEAD IN DEVELOPMENT
    # ============================================
    "development_lead": {
        "concept_id": "development_lead",
        "name": "Lead in Development",
        "trigger_conditions": [
            "More pieces developed than opponent",
            "King safely castled vs king in center",
            "Opponent pieces undeveloped or misplaced",
            "Temporary advantage - must be used quickly"
        ],
        "strategic_goal_with": {
            "summary": "Attack before opponent catches up",
            "plans": [
                "Open the position immediately",
                "Attack the uncastled king",
                "Create concrete threats",
                "Development lead is TEMPORARY - use it or lose it"
            ],
            "key_moves": ["Open center", "Direct attack on king"]
        },
        "strategic_goal_against": {
            "summary": "Survive and complete development",
            "plans": [
                "Castle immediately",
                "Keep position closed",
                "Trade pieces to reduce attack",
                "Return material if needed for development"
            ],
            "key_moves": ["Castle!", "Keep position closed"]
        },
        "amateur_errors": {
            "with_lead": [
                "Slow play allowing catch-up",
                "Not opening the position",
                "Missing concrete attacking chances"
            ],
            "behind_development": [
                "Grabbing more material instead of developing",
                "Not recognizing danger",
                "Opening position when undeveloped"
            ]
        },
        "conversion_pattern": {
            "summary": "Convert to material or mating attack",
            "method": "Direct assault on king before development completes"
        }
    },

    # ============================================
    # 7. ROOK ON OPEN FILE
    # ============================================
    "open_file": {
        "concept_id": "open_file",
        "name": "Rook on Open File",
        "trigger_conditions": [
            "No pawns on a file for either side",
            "Rook can reach 7th or 8th rank",
            "File leads to weak points in opponent position"
        ],
        "strategic_goal_with": {
            "summary": "Penetrate with rooks to 7th rank",
            "plans": [
                "Double rooks on open file",
                "Invade 7th rank - rook on 7th is powerful",
                "Attack backward pawns on the file",
                "Create entry points for other pieces"
            ],
            "key_moves": ["Rd7!", "Double on d-file", "7th rank invasion"]
        },
        "strategic_goal_against": {
            "summary": "Contest or block the file",
            "plans": [
                "Place own rook on the file",
                "Exchange rooks",
                "Block file with minor piece if needed",
                "Create counter-threats on other files"
            ],
            "key_moves": ["Contest the file", "Trade rooks"]
        },
        "amateur_errors": {
            "with_open_file": [
                "Not using the open file actively",
                "Trading rooks too easily",
                "Not invading 7th rank when possible"
            ],
            "against_open_file": [
                "Not contesting the file",
                "Allowing doubled rooks",
                "Letting 7th rank invasion happen"
            ]
        }
    },

    # ============================================
    # 8. THE TWO WEAKNESSES
    # ============================================
    "two_weaknesses": {
        "concept_id": "two_weaknesses",
        "name": "Principle of Two Weaknesses",
        "trigger_conditions": [
            "One weakness can often be defended",
            "Creating second weakness overloads defense",
            "Classic endgame/middlegame technique"
        ],
        "strategic_goal_with": {
            "summary": "Create second weakness, stretch defense",
            "plans": [
                "Identify first weakness",
                "Create second weakness on opposite flank",
                "Attack both - opponent can't defend everything",
                "Win material or position when defense breaks"
            ],
            "key_moves": ["Create weakness on opposite flank", "Switch attack points"]
        },
        "strategic_goal_against": {
            "summary": "Eliminate weaknesses or create counterplay",
            "plans": [
                "Fix your weaknesses if possible",
                "Don't allow second weakness",
                "Create active counterplay",
                "Trade pieces to simplify defense"
            ],
            "key_moves": ["Fix weaknesses", "Active defense"]
        },
        "amateur_errors": {
            "attacking": [
                "Focusing only on one weakness",
                "Not creating second weakness when possible",
                "Missing strategic moments"
            ],
            "defending": [
                "Creating unnecessary weaknesses",
                "Passive defense",
                "Not recognizing two-weakness danger"
            ]
        }
    },

    # ============================================
    # 9. KING ACTIVITY (ENDGAME)
    # ============================================
    "king_activity": {
        "concept_id": "king_activity",
        "name": "King Activity in Endgame",
        "trigger_conditions": [
            "Queens are off the board",
            "Few pieces remaining",
            "King becomes active piece"
        ],
        "strategic_goal_with": {
            "summary": "Centralize king immediately",
            "plans": [
                "King to center is first priority in endgame",
                "Active king supports pawns and attacks",
                "King can penetrate opponent's position",
                "Opposition often decides pawn endgames"
            ],
            "key_moves": ["Ke2-d3-c4 (centralization)", "Active king march"]
        },
        "strategic_goal_against": {
            "summary": "Match opponent's king activity",
            "plans": [
                "Don't let opponent's king get too active",
                "Activate your own king",
                "Use opposition to block king",
                "Cut off king with rook if applicable"
            ],
            "key_moves": ["Match centralization", "Use opposition"]
        },
        "amateur_errors": {
            "both_sides": [
                "Not activating king in endgame",
                "Leaving king on back rank",
                "Not understanding opposition",
                "Passive king play"
            ]
        }
    },

    # ============================================
    # 10. MATERIAL IMBALANCE
    # ============================================
    "material_imbalance": {
        "concept_id": "material_imbalance",
        "name": "Material Imbalance (Queen vs Pieces)",
        "trigger_conditions": [
            "Queen vs Rook + Minor piece",
            "Queen vs Two Rooks",
            "Queen vs Three Minor pieces"
        ],
        "strategic_goal_with": {
            "summary": "Depends on specific imbalance",
            "plans": [
                "Queen likes open positions, weak king",
                "Pieces like coordination, closed positions",
                "Create targets for queen checks",
                "Or coordinate pieces against exposed queen"
            ]
        },
        "queen_strong": [
            "Exposed enemy king",
            "Weak pawns to attack",
            "Ability to create threats on multiple fronts"
        ],
        "pieces_strong": [
            "Piece coordination possible",
            "Protected king",
            "Closed position",
            "Active pieces with targets"
        ]
    }
}

# ============================================
# RETRIEVAL FUNCTIONS
# ============================================

def get_imbalance_by_id(concept_id: str) -> dict:
    """Get imbalance data by ID"""
    return STRATEGIC_IMBALANCES.get(concept_id, {})

def get_all_imbalance_ids() -> list:
    """Get list of all imbalance IDs"""
    return list(STRATEGIC_IMBALANCES.keys())

def detect_imbalances_from_themes(themes: list) -> list:
    """Match detected themes to knowledge base entries"""
    matched = []
    
    theme_mapping = {
        "good bishop": "good_bishop",
        "bad bishop": "good_bishop",
        "bishop pair": "bishop_pair",
        "knight outpost": "knight_outpost",
        "outpost": "knight_outpost",
        "weak squares": "weak_squares",
        "color complex": "weak_squares",
        "space advantage": "space_advantage",
        "cramped": "space_advantage",
        "development": "development_lead",
        "open file": "open_file",
        "rook on": "open_file",
        "two weaknesses": "two_weaknesses",
        "king activity": "king_activity",
        "material imbalance": "material_imbalance"
    }
    
    for theme in themes:
        theme_lower = theme.lower() if isinstance(theme, str) else str(theme).lower()
        for key, concept_id in theme_mapping.items():
            if key in theme_lower:
                if concept_id not in matched:
                    matched.append(concept_id)
                break
    
    return [STRATEGIC_IMBALANCES.get(m, {}) for m in matched if m in STRATEGIC_IMBALANCES]
