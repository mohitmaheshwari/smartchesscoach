"""
ChessGuru Canon - Pawn Structures Knowledge Base

This is the TRUTH LAYER for positional coaching.
All entries are structured, deterministic, and designed for RAG retrieval.

Schema:
- structure_id: Unique identifier for retrieval
- trigger_conditions: Deterministic detection rules
- strategic_goal_with: Plan for the side WITH this structure  
- strategic_goal_against: Plan for the side AGAINST this structure
- typical_plans: Concrete move patterns and ideas
- amateur_errors: Common mistakes at club level
- conversion_pattern: How to transition to winning
- key_squares: Important squares to control/occupy
- piece_placement: Where pieces belong
"""

PAWN_STRUCTURES = {
    # ============================================
    # 1. ISOLATED QUEEN'S PAWN (IQP)
    # ============================================
    "iqp": {
        "structure_id": "iqp",
        "name": "Isolated Queen's Pawn (IQP)",
        "trigger_conditions": [
            "d-pawn has no neighboring pawns on c or e file",
            "Common after 1.d4 d5 2.c4 exd5 cxd5 exchanges",
            "Also arises from Sicilian, French, Caro-Kann"
        ],
        "strategic_goal_with": {
            "summary": "Attack before the structure becomes a weakness",
            "plans": [
                "Use piece activity advantage - your pieces are more mobile",
                "Control e5/c5 outposts with knights",
                "Build pressure on kingside with Qd3, Bc2, Rd1 battery",
                "Time the d4-d5 breakthrough when pieces are optimally placed",
                "Avoid piece trades - each trade makes IQP weaker"
            ],
            "key_moves": ["Nd4-f5 attacking h6", "Qd3 + Bc2 battery on h7", "d4-d5! breakthrough"]
        },
        "strategic_goal_against": {
            "summary": "Blockade the pawn, trade pieces, head for endgame",
            "plans": [
                "Place a knight on d5 - the perfect blockade square",
                "Trade pieces systematically - especially active attacking pieces",
                "Aim for endgame where IQP is pure weakness",
                "Control the d-file to prevent d4-d5 advance",
                "Be patient - time is on your side"
            ],
            "key_moves": ["Nd5 blockade", "Qe7-c7 controlling d-file", "Rd8 pressure on d4"]
        },
        "typical_plans": {
            "with_iqp": [
                "Minority attack on queenside is NOT the plan",
                "Focus on kingside attack with f3-e4 support",
                "Rooks belong on d1 and e1 (or c1)"
            ],
            "against_iqp": [
                "Rooks on d8 and c8 controlling key files",
                "Trade your light-squared bishop for their knight",
                "Push a6-b5 only after full development"
            ]
        },
        "amateur_errors": {
            "with_iqp": [
                "Trading pieces too early - kills your attacking potential",
                "Pushing d4-d5 prematurely without piece support",
                "Allowing blockade on d5 without contesting it",
                "Playing passively and drifting into bad endgame"
            ],
            "against_iqp": [
                "Rushing to attack the d4 pawn directly",
                "Not establishing blockade knight early enough",
                "Trading your blockading knight for no compensation",
                "Fearing the d4-d5 push instead of preventing it"
            ]
        },
        "conversion_pattern": {
            "with_iqp": "Convert piece activity into direct attack. Win material or mate before endgame.",
            "against_iqp": "Simplify to endgame. IQP becomes target. King + rook vs king + rook + IQP = winning technique."
        },
        "key_squares": ["d5 (blockade)", "e5/c5 (outposts)", "d1/d8 (file control)"],
        "piece_placement": {
            "with_iqp": "Knights on e5/c5, Queen on d3, Bishops active on diagonals",
            "against_iqp": "Knight on d5, Queen controlling d-file, Rooks doubled on d-file"
        },
        "model_games": ["Karpov's blockade technique", "Kasparov's IQP attacks"]
    },

    # ============================================
    # 2. HANGING PAWNS
    # ============================================
    "hanging_pawns": {
        "structure_id": "hanging_pawns",
        "name": "Hanging Pawns (c4-d4 or c5-d5)",
        "trigger_conditions": [
            "Two pawns on adjacent files (c+d) without support",
            "Both pawns advanced beyond their starting ranks",
            "No pawns on b or e files to support them"
        ],
        "strategic_goal_with": {
            "summary": "Maintain dynamic tension, prepare central advance",
            "plans": [
                "Keep both pawns mobile - don't fix them",
                "Prepare d4-d5 or c4-c5 advance at right moment",
                "Use piece pressure to cover pawn weaknesses",
                "Central advance should create passed pawn or open lines"
            ],
            "key_moves": ["d4-d5! advance", "c4-c5! creating passed pawn"]
        },
        "strategic_goal_against": {
            "summary": "Fix the pawns, then attack the fixed targets",
            "plans": [
                "Force one pawn to advance, creating fixed weakness",
                "Blockade the remaining pawn",
                "Attack from both flanks - they can't defend everything",
                "Trade pieces to expose pawn weaknesses"
            ],
            "key_moves": ["Provoke d4-d5, then blockade on d6", "Attack c4 and d4 simultaneously"]
        },
        "amateur_errors": {
            "with_hanging": [
                "Advancing one pawn too early, creating IQP",
                "Not maintaining piece pressure",
                "Allowing blockade without compensation"
            ],
            "against_hanging": [
                "Allowing free advance without preparation",
                "Attacking only one pawn instead of both",
                "Not exploiting temporary weakness after advance"
            ]
        },
        "conversion_pattern": {
            "with_hanging": "Advance at the right moment to create passed pawn or destroy opponent's position",
            "against_hanging": "Fix one pawn, win the other, then convert material advantage"
        },
        "key_squares": ["d5/c5 (advance targets)", "e4/b4 (attack squares)"],
        "piece_placement": {
            "with_hanging": "Pieces must actively defend - no passive defense",
            "against_hanging": "Pieces coordinated to attack both pawns"
        }
    },

    # ============================================
    # 3. DOUBLED PAWNS
    # ============================================
    "doubled_pawns": {
        "structure_id": "doubled_pawns",
        "name": "Doubled Pawns",
        "trigger_conditions": [
            "Two pawns on same file",
            "Usually from capture toward center (cxd, dxc)",
            "Common in Nimzo-Indian, Sicilian, Exchange variations"
        ],
        "strategic_goal_with": {
            "summary": "Use the open file and extra central control",
            "plans": [
                "Doubled pawns often provide extra central control",
                "Use the half-open file created by capture",
                "Activity compensation for structural weakness",
                "Avoid pure pawn endgames where weakness shows"
            ],
            "key_moves": ["Rook to the opened file", "Central pawn advance"]
        },
        "strategic_goal_against": {
            "summary": "Target in endgame, avoid letting them undouble",
            "plans": [
                "Blockade the front doubled pawn",
                "Steer toward endgame where weakness matters",
                "Prevent them from undoubling via pawn exchanges",
                "Use extra pawn majority elsewhere"
            ],
            "key_moves": ["Blockade", "Trade into favorable endgame"]
        },
        "amateur_errors": {
            "with_doubled": [
                "Playing passively instead of using file compensation",
                "Entering pure pawn endgame",
                "Neglecting piece activity"
            ],
            "against_doubled": [
                "Trading into position where their activity compensates",
                "Allowing them to undouble",
                "Attacking too early before endgame"
            ]
        },
        "conversion_pattern": {
            "with_doubled": "Win with piece activity before endgame exposes weakness",
            "against_doubled": "Reach endgame and win the pawn race with healthy majority"
        },
        "key_squares": ["File where capture occurred", "Blockade square in front of doubled pawn"]
    },

    # ============================================
    # 4. PAWN MAJORITY (KINGSIDE)
    # ============================================
    "kingside_majority": {
        "structure_id": "kingside_majority",
        "name": "Kingside Pawn Majority",
        "trigger_conditions": [
            "More pawns on kingside (e,f,g,h files) than opponent",
            "Often from queenside pawn exchanges",
            "Common in Sicilian, Exchange QGD"
        ],
        "strategic_goal_with": {
            "summary": "Create passed pawn on kingside",
            "plans": [
                "Advance f4-f5 to open lines and create passed pawn",
                "Time the advance when king is safe or in endgame",
                "Use majority to create outside passed pawn",
                "In middlegame, advance can also be attacking weapon"
            ],
            "key_moves": ["f4-f5!", "g4-g5 supporting f-pawn advance"]
        },
        "strategic_goal_against": {
            "summary": "Blockade and use queenside counter",
            "plans": [
                "Blockade kingside with pieces",
                "Create your own passed pawn on queenside",
                "Trade pawns on kingside to reduce their majority",
                "Keep king flexible to deal with both sides"
            ],
            "key_moves": ["f6 blockade", "Queenside pawn advance"]
        },
        "amateur_errors": {
            "with_majority": [
                "Advancing too early with king still in center",
                "Creating weak squares around own king",
                "Not supporting advance with pieces"
            ],
            "against_majority": [
                "Passive defense instead of counterplay",
                "Ignoring own majority on other flank",
                "Allowing unopposed passed pawn creation"
            ]
        },
        "key_squares": ["f5 (advance square)", "e5 (outpost)"]
    },

    # ============================================
    # 5. PAWN MAJORITY (QUEENSIDE)
    # ============================================
    "queenside_majority": {
        "structure_id": "queenside_majority",
        "name": "Queenside Pawn Majority",
        "trigger_conditions": [
            "More pawns on queenside (a,b,c,d files) than opponent",
            "Classic structure from Exchange Spanish, QGD",
            "Minority attack creates this for opponent"
        ],
        "strategic_goal_with": {
            "summary": "Create outside passed pawn",
            "plans": [
                "Advance pawns to create passed pawn on a or b file",
                "Outside passed pawn is powerful in endgame",
                "b4-b5-b6 advance is typical",
                "King walks over to support passed pawn"
            ],
            "key_moves": ["b4-b5!", "a4 supporting b-pawn", "c4-c5 breakthrough"]
        },
        "strategic_goal_against": {
            "summary": "Blockade and create kingside chances",
            "plans": [
                "Blockade queenside advance",
                "Create kingside counterplay",
                "Keep pieces active on both flanks",
                "Don't let outside passed pawn advance freely"
            ],
            "key_moves": ["a5 blockade", "Kingside pawn storm if safe"]
        },
        "amateur_errors": {
            "with_majority": [
                "Advancing without piece support",
                "Creating weak squares in the process",
                "Forgetting about opponent's counterplay"
            ],
            "against_majority": [
                "Purely defensive stance",
                "Not creating counterchances",
                "Ignoring central play options"
            ]
        },
        "key_squares": ["b5 (advance)", "c5 (support)", "d5 (outpost)"]
    },

    # ============================================
    # 6. CARLSBAD STRUCTURE
    # ============================================
    "carlsbad": {
        "structure_id": "carlsbad",
        "name": "Carlsbad Structure",
        "trigger_conditions": [
            "White: pawns on d4, e3 - Black: pawns on d5, e6",
            "c-pawns have been exchanged",
            "Classic QGD Exchange structure"
        ],
        "strategic_goal_with": {
            "summary": "Minority attack on queenside",
            "plans": [
                "b4-b5 minority attack to create weakness on c6",
                "Trade b-pawn for c-pawn, leaving isolated a-pawn",
                "Open c-file for rooks",
                "Place knight on c5 outpost"
            ],
            "key_moves": ["b4-b5xc6!", "Rc1 controlling open file", "Nc5 outpost"]
        },
        "strategic_goal_against": {
            "summary": "Kingside counterplay",
            "plans": [
                "f6-f5 central counter",
                "Nf6-e4 active knight",
                "Prepare e6-e5 central break",
                "Don't be passive - create threats"
            ],
            "key_moves": ["f5! break", "Ne4 activity", "Kingside piece play"]
        },
        "amateur_errors": {
            "white": [
                "Rushing minority attack without completing development",
                "Neglecting kingside defense",
                "Not using open c-file after exchange"
            ],
            "black": [
                "Passive defense of c6",
                "Not creating kingside counter",
                "Trading pieces when defending is needed"
            ]
        },
        "key_squares": ["c5 (outpost for White)", "e4 (outpost for Black)", "c6 (target)"]
    },

    # ============================================
    # 7. FRENCH STRUCTURE (Advance)
    # ============================================
    "french_advance": {
        "structure_id": "french_advance",
        "name": "French Advance Structure",
        "trigger_conditions": [
            "White e5 pawn vs Black e6-d5 chain",
            "Locked center after 1.e4 e6 2.d4 d5 3.e5",
            "Space advantage for White"
        ],
        "strategic_goal_with": {
            "summary": "Use space advantage, attack kingside",
            "plans": [
                "f4 supporting e5, preparing f5 push",
                "Kingside attack with g4, h4 pawn storm",
                "Maintain e5 outpost for knight",
                "Keep Black's bad bishop locked in"
            ],
            "key_moves": ["f4", "g4-g5 attack", "Nf3-h4-f5"]
        },
        "strategic_goal_against": {
            "summary": "Undermine e5 with f6 and c5",
            "plans": [
                "f6 attacking e5 chain",
                "c5 attacking d4 base",
                "Trade bad bishop via b6-a6 maneuver",
                "Once e5 falls, Black equalizes"
            ],
            "key_moves": ["f6!", "cxd4 opening lines", "Ba6 trading bad bishop"]
        },
        "amateur_errors": {
            "white": [
                "Passively defending e5",
                "Not using space for kingside attack",
                "Allowing Black to undermine without punishment"
            ],
            "black": [
                "Not challenging e5 quickly enough",
                "Leaving bad bishop on c8",
                "Passive kingside defense"
            ]
        },
        "key_squares": ["e5 (key point)", "f6 (break square)", "d4 (base of chain)"]
    },

    # ============================================
    # 8. SICILIAN STRUCTURE (Open)
    # ============================================
    "sicilian_open": {
        "structure_id": "sicilian_open",
        "name": "Open Sicilian Structure",
        "trigger_conditions": [
            "White d4 has been exchanged for c5",
            "Semi-open c-file for Black",
            "Typical after 1.e4 c5 2.Nf3 d6 3.d4 cxd4"
        ],
        "strategic_goal_with": {
            "summary": "Kingside attack with piece activity",
            "plans": [
                "f3, Be3, Qd2, O-O-O typical setup",
                "g4-g5 pawn storm against Black's king",
                "Nd5 outpost when possible",
                "Use lead in development for attack"
            ],
            "key_moves": ["g4!", "h4 pawn storm", "Nd5 outpost"]
        },
        "strategic_goal_against": {
            "summary": "Queenside counterattack",
            "plans": [
                "a6-b5-b4 queenside expansion",
                "Pressure on c-file and a2 pawn",
                "d5 break when prepared",
                "Trade dark-squared bishops to weaken White's king"
            ],
            "key_moves": ["b5!", "Rc8 pressure", "d5! break"]
        },
        "amateur_errors": {
            "white": [
                "Attacking without completing development",
                "Ignoring Black's queenside threats",
                "Premature piece sacrifices"
            ],
            "black": [
                "Passive play - Sicilian requires action",
                "Delaying queenside counterplay",
                "Castling kingside into White's attack"
            ]
        },
        "key_squares": ["d5 (outpost)", "c-file (Black's pressure)", "g5 (attack point)"]
    },

    # ============================================
    # 9. SYMMETRICAL STRUCTURE
    # ============================================
    "symmetrical": {
        "structure_id": "symmetrical",
        "name": "Symmetrical Pawn Structure",
        "trigger_conditions": [
            "Mirror pawn structure (e.g., both have d and e pawns)",
            "Common in Exchange Slav, Exchange Spanish",
            "Equal pawn structure = piece play decides"
        ],
        "strategic_goal_with": {
            "summary": "Find small advantages through piece play",
            "plans": [
                "Activity is key - active pieces beat passive ones",
                "Minor piece superiority matters greatly",
                "Create targets through opponent's weaknesses",
                "Patience and maneuvering"
            ],
            "key_moves": ["Improve worst placed piece", "Create outposts"]
        },
        "strategic_goal_against": {
            "summary": "Same as above - it's symmetrical",
            "plans": [
                "Match opponent's activity",
                "Don't create unnecessary weaknesses",
                "Look for imbalances in piece placement",
                "Be willing to accept draw if needed"
            ],
            "key_moves": ["Piece improvement", "Prophylaxis"]
        },
        "amateur_errors": {
            "both_sides": [
                "Creating weaknesses trying to force play",
                "Passive defense when activity is needed",
                "Missing small tactical opportunities",
                "Impatience leading to errors"
            ]
        },
        "key_squares": ["Depends on exact position", "Usually d5/d4 outpost squares"]
    },

    # ============================================
    # 10. CLOSED CENTER
    # ============================================
    "closed_center": {
        "structure_id": "closed_center",
        "name": "Closed Center",
        "trigger_conditions": [
            "Locked pawn chain in center (e.g., d4-e5 vs d5-e6)",
            "No pawn exchanges possible centrally",
            "Typical in French, King's Indian, certain Sicilians"
        ],
        "strategic_goal_with": {
            "summary": "Flank attack - play where you have space",
            "plans": [
                "Pawn storm on flank where you have more space",
                "If space on kingside, attack kingside",
                "If space on queenside, attack queenside",
                "Transfer pieces to attacking flank"
            ],
            "key_moves": ["Pawn storm (g4-h4 or b4-a4)", "Piece transfers"]
        },
        "strategic_goal_against": {
            "summary": "Counter on opposite flank",
            "plans": [
                "While opponent attacks, counter-attack",
                "Race situation - who gets there first",
                "Don't defend passively on attacked flank",
                "Break center if possible to change nature of game"
            ],
            "key_moves": ["Counter pawn storm", "Central break if possible"]
        },
        "amateur_errors": {
            "both_sides": [
                "Playing on wrong flank",
                "Defensive moves when attack is needed",
                "Not recognizing flank play requirement",
                "Trying to open locked center prematurely"
            ]
        },
        "key_squares": ["Flank squares where pawns can advance"]
    }
}

# ============================================
# RETRIEVAL FUNCTION
# ============================================

def get_structure_by_id(structure_id: str) -> dict:
    """Get pawn structure data by ID"""
    return PAWN_STRUCTURES.get(structure_id, {})

def get_all_structure_ids() -> list:
    """Get list of all structure IDs for indexing"""
    return list(PAWN_STRUCTURES.keys())

def match_structure_from_analysis(structure_type: str) -> dict:
    """Match detected structure type to knowledge base entry"""
    # Map common names to knowledge base IDs
    mapping = {
        "isolated queen's pawn": "iqp",
        "isolated queen pawn": "iqp",
        "iqp": "iqp",
        "hanging pawns": "hanging_pawns",
        "doubled pawns": "doubled_pawns",
        "doubled": "doubled_pawns",
        "kingside pawn majority": "kingside_majority",
        "kingside majority": "kingside_majority",
        "queenside pawn majority": "queenside_majority",
        "queenside majority": "queenside_majority",
        "carlsbad": "carlsbad",
        "french advance": "french_advance",
        "french structure": "french_advance",
        "sicilian": "sicilian_open",
        "open sicilian": "sicilian_open",
        "symmetrical": "symmetrical",
        "balanced": "symmetrical",
        "closed center": "closed_center",
        "closed": "closed_center",
        "standard": "symmetrical"
    }
    
    structure_lower = structure_type.lower().strip()
    matched_id = mapping.get(structure_lower)
    
    if matched_id:
        return PAWN_STRUCTURES.get(matched_id, {})
    
    # Fuzzy match
    for key, struct_id in mapping.items():
        if key in structure_lower or structure_lower in key:
            return PAWN_STRUCTURES.get(struct_id, {})
    
    return {}
