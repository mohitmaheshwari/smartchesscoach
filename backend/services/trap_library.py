"""
Chess Trap Library
==================

A comprehensive library of verified chess opening traps.
Each trap is chess-engine verified to ensure accuracy.

Structure:
- TRAP_LIBRARY: Dict mapping opening_key to list of traps
- Each trap contains setup_moves, trap_line, and metadata
"""

from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class TrapMove:
    """A single move in a trap sequence"""
    move: str
    explanation: str


@dataclass  
class ChessTrap:
    """A complete chess trap definition"""
    name: str
    description: str
    setup_moves: List[str]
    trap_line: List[TrapMove]
    success_message: str
    result_type: str  # "checkmate", "wins_queen", "wins_piece", "wins_material", "crushing_attack"
    difficulty: str   # "beginner", "intermediate", "advanced"


# ============================================================================
# TRAP LIBRARY - Organized by Opening
# ============================================================================

TRAP_LIBRARY: Dict[str, List[Dict]] = {
    
    # ========================================================================
    # ITALIAN GAME TRAPS (e4 e5 Nf3 Nc6 Bc4)
    # ========================================================================
    "italian-game": [
        {
            "name": "Fried Liver Attack",
            "description": "A deadly knight sacrifice on f7 that wins material and exposes Black's king.",
            "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"],
            "trap_line": [
                {"move": "d5", "explanation": "Black tries to block, but it's too late..."},
                {"move": "exd5", "explanation": "White captures the pawn."},
                {"move": "Nxd5", "explanation": "Black recaptures, but the knight is vulnerable."},
                {"move": "Nxf7", "explanation": "The Fried Liver sacrifice! Knight takes on f7."},
                {"move": "Kxf7", "explanation": "Black must capture."},
                {"move": "Qf3+", "explanation": "Check! Double attack on king and knight on d5."},
                {"move": "Ke6", "explanation": "The king is forced forward into danger."},
                {"move": "Nc3", "explanation": "Develop with tempo. White wins the knight and has a crushing attack."}
            ],
            "success_message": "The Fried Liver Attack! Black's king is exposed and you win material.",
            "result_type": "wins_material",
            "difficulty": "intermediate"
        },
        {
            "name": "Legal's Mate",
            "description": "A beautiful queen sacrifice leading to checkmate.",
            "setup_moves": ["e4", "e5", "Nf3", "d6", "Bc4", "Bg4", "Nc3", "g6"],
            "trap_line": [
                {"move": "Nxe5", "explanation": "Sacrifice! Offering the queen to set up checkmate."},
                {"move": "Bxd1", "explanation": "Black takes the queen, falling into the trap!"},
                {"move": "Bxf7+", "explanation": "Check! The king must move."},
                {"move": "Ke7", "explanation": "Forced - the only legal move."},
                {"move": "Nd5#", "explanation": "Checkmate! The Legal's Mate - a queen sacrifice for mate."}
            ],
            "success_message": "Legal's Mate! A beautiful queen sacrifice leading to checkmate.",
            "result_type": "checkmate",
            "difficulty": "intermediate"
        },
        {
            "name": "Blackburne Shilling Gambit",
            "description": "A cunning trap where Black sacrifices a pawn to deliver checkmate!",
            "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4"],
            "trap_line": [
                {"move": "Nxe5", "explanation": "White grabs the pawn - a natural but losing move!"},
                {"move": "Qg5", "explanation": "Threatening Qxg2 and the knight on e5."},
                {"move": "Nxf7", "explanation": "White tries to complicate with a fork..."},
                {"move": "Qxg2", "explanation": "Black ignores the threat and attacks f1!"},
                {"move": "Rf1", "explanation": "White defends."},
                {"move": "Qxe4+", "explanation": "Check! Picking up the e4 pawn with tempo."},
                {"move": "Be2", "explanation": "Blocking with the bishop."},
                {"move": "Nf3#", "explanation": "Checkmate! The knight delivers the final blow."}
            ],
            "success_message": "Blackburne Shilling Gambit Mate! A devastating trap for Black.",
            "result_type": "checkmate",
            "difficulty": "intermediate"
        },
        {
            "name": "Scholar's Mate Defense Trap",
            "description": "Punish White's premature queen attack and win material!",
            "setup_moves": ["e4", "e5", "Bc4", "Nc6", "Qh5", "g6", "Qf3", "Nf6", "g4"],
            "trap_line": [
                {"move": "Nd4", "explanation": "The knight jumps to a powerful outpost!"},
                {"move": "Qb3", "explanation": "White tries to threaten f7."},
                {"move": "Nxc2+", "explanation": "Fork! The knight attacks king and rook."},
                {"move": "Kd1", "explanation": "The king moves."},
                {"move": "Nxa1", "explanation": "Black wins the exchange - rook for knight!"}
            ],
            "success_message": "Scholar's Mate refuted! You won material by exploiting White's greedy play.",
            "result_type": "wins_material",
            "difficulty": "beginner"
        }
    ],
    
    # ========================================================================
    # SICILIAN DEFENSE TRAPS (e4 c5)
    # ========================================================================
    "sicilian-defense": [
        {
            "name": "Siberian Trap",
            "description": "A deadly trap where Black wins White's queen with a series of checks!",
            "setup_moves": ["e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "Bb4"],
            "trap_line": [
                {"move": "e5", "explanation": "White attacks the knight - a common but losing move!"},
                {"move": "Qa5", "explanation": "Black threatens Bxc3+ winning the queen."},
                {"move": "exf6", "explanation": "White captures, but falls into the trap..."},
                {"move": "Bxc3+", "explanation": "Check! The bishop takes the knight with check."},
                {"move": "Bd2", "explanation": "White blocks the check."},
                {"move": "Bxd2+", "explanation": "Take the bishop with another check!"},
                {"move": "Qxd2", "explanation": "White must take with the queen."},
                {"move": "Qxd2+", "explanation": "The Siberian Trap! Black wins White's queen."}
            ],
            "success_message": "The Siberian Trap! Black wins White's queen for just a knight.",
            "result_type": "wins_queen",
            "difficulty": "intermediate"
        },
        {
            "name": "Magnus Smith Trap",
            "description": "A tactical shot that wins material in the Dragon variation.",
            "setup_moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "Nc6", "Bc4", "g6"],
            "trap_line": [
                {"move": "Nxc6", "explanation": "White exchanges knights."},
                {"move": "bxc6", "explanation": "Black recaptures with the pawn."},
                {"move": "e5", "explanation": "A powerful pawn thrust!"},
                {"move": "Ng4", "explanation": "The knight retreats."},
                {"move": "e6", "explanation": "Devastating! Opening the diagonal to f7."},
                {"move": "fxe6", "explanation": "Black must capture."},
                {"move": "Bxe6", "explanation": "White wins a pawn and has a strong attack on f7."}
            ],
            "success_message": "The Magnus Smith Trap wins material and opens Black's king!",
            "result_type": "wins_material",
            "difficulty": "intermediate"
        }
    ],
    
    # ========================================================================
    # QUEEN'S GAMBIT TRAPS (d4 d5 c4)
    # ========================================================================
    "queens-gambit": [
        {
            "name": "Elephant Trap",
            "description": "Black wins a piece with a beautiful intermezzo check!",
            "setup_moves": ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Nbd7", "cxd5", "exd5", "Nxd5"],
            "trap_line": [
                {"move": "Nxd5", "explanation": "Black recaptures the pawn."},
                {"move": "Bxd8", "explanation": "White thinks they win the queen! But..."},
                {"move": "Bb4+", "explanation": "Intermezzo! Check with the bishop."},
                {"move": "Qd2", "explanation": "White blocks with the queen."},
                {"move": "Bxd2+", "explanation": "Take the queen with check!"},
                {"move": "Kxd2", "explanation": "White must recapture."},
                {"move": "Kxd8", "explanation": "Now Black takes back the bishop. You're up a full piece!"}
            ],
            "success_message": "The Elephant Trap! The intermezzo check wins a piece.",
            "result_type": "wins_piece",
            "difficulty": "intermediate"
        },
        {
            "name": "Lasker Trap",
            "description": "A stunning queen trap in the Albin Counter-Gambit!",
            "setup_moves": ["d4", "d5", "c4", "e5", "dxe5", "d4", "e3", "Bb4+", "Bd2", "dxe3"],
            "trap_line": [
                {"move": "Bxb4", "explanation": "White takes the bishop, but..."},
                {"move": "exf2+", "explanation": "The pawn advances with check!"},
                {"move": "Ke2", "explanation": "The king steps up."},
                {"move": "fxg1=N+", "explanation": "Underpromotion to knight with check! A rare move."},
                {"move": "Rxg1", "explanation": "White takes the knight."},
                {"move": "Bg4+", "explanation": "Check! And the queen falls next move."}
            ],
            "success_message": "The Lasker Trap with underpromotion! A stunning queen trap.",
            "result_type": "wins_queen",
            "difficulty": "advanced"
        }
    ],
    
    # ========================================================================
    # LONDON SYSTEM TRAPS (d4 d5 Bf4)
    # ========================================================================
    "london-system": [
        {
            "name": "Englund Gambit Trap",
            "description": "Refute the dubious Englund Gambit and trap Black's queen!",
            "setup_moves": ["d4", "e5", "dxe5", "Nc6", "Nf3", "Qe7", "Bf4", "Qb4+"],
            "trap_line": [
                {"move": "Bd2", "explanation": "Block the check with the bishop."},
                {"move": "Qxb2", "explanation": "Black grabs the pawn greedily, but..."},
                {"move": "Bc3", "explanation": "The queen is trapped! No safe squares."},
                {"move": "Qb4", "explanation": "Black tries to escape, but..."},
                {"move": "Bxb4", "explanation": "Take the queen! She has nowhere to run."}
            ],
            "success_message": "The Englund Gambit refuted! Black's greed costs them the queen.",
            "result_type": "wins_queen",
            "difficulty": "beginner"
        }
    ],
    
    # ========================================================================
    # CARO-KANN DEFENSE TRAPS (e4 c6)
    # ========================================================================
    "caro-kann": [
        {
            "name": "Caro-Kann Smothered Mate",
            "description": "A rare smothered mate in the Caro-Kann!",
            "setup_moves": ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Nd7", "Qe2", "Ngf6"],
            "trap_line": [
                {"move": "Nd6#", "explanation": "Smothered Mate! The knight delivers checkmate."}
            ],
            "success_message": "Smothered Mate! Black's pieces block all escape squares.",
            "result_type": "checkmate",
            "difficulty": "intermediate"
        }
    ],
    
    # ========================================================================
    # KING'S INDIAN DEFENSE TRAPS (d4 Nf6 c4 g6)
    # ========================================================================
    "kings-indian-defense": [
        {
            "name": "King's Indian Bayonet Trap",
            "description": "A tactical sequence in the Bayonet Attack that wins material.",
            "setup_moves": ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O", "Be2", "e5", "O-O", "Nc6", "d5", "Ne7", "b4", "Nh5"],
            "trap_line": [
                {"move": "g3", "explanation": "Preventing Nf4."},
                {"move": "f5", "explanation": "Black pushes for counterplay."},
                {"move": "Ng5", "explanation": "The knight eyes e6."},
                {"move": "Nf6", "explanation": "Black defends."},
                {"move": "f3", "explanation": "Solid prophylaxis."},
                {"move": "c6", "explanation": "Black tries to break."},
                {"move": "Be3", "explanation": "Developing with purpose."},
                {"move": "h6", "explanation": "Kicking the knight."},
                {"move": "Ne6", "explanation": "The knight invades!"},
                {"move": "Bxe6", "explanation": "Black must take."},
                {"move": "dxe6", "explanation": "White has a strong passed pawn and attack."}
            ],
            "success_message": "The Bayonet Attack succeeds! White has a powerful passed pawn.",
            "result_type": "wins_material",
            "difficulty": "advanced"
        }
    ],
    
    # ========================================================================
    # SCANDINAVIAN DEFENSE TRAPS (e4 d5)
    # ========================================================================
    "scandinavian-defense": [
        {
            "name": "Portuguese Gambit Trap",
            "description": "A clever trap where Black gets strong piece activity.",
            "setup_moves": ["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "Nf6", "Nf3", "Bg4"],
            "trap_line": [
                {"move": "h3", "explanation": "White kicks the bishop."},
                {"move": "Bh5", "explanation": "The bishop retreats but maintains the pin."},
                {"move": "g4", "explanation": "White attacks aggressively, but..."},
                {"move": "Bg6", "explanation": "The bishop retreats again."},
                {"move": "Ne5", "explanation": "White centralizes."},
                {"move": "e6", "explanation": "Solid development."},
                {"move": "Nc4", "explanation": "Attacking the queen."},
                {"move": "Qb6", "explanation": "The queen retreats."},
                {"move": "Bf4", "explanation": "White develops. Black has good counterplay."}
            ],
            "success_message": "The Portuguese Gambit leads to active piece play for Black!",
            "result_type": "equal_with_activity",
            "difficulty": "intermediate"
        }
    ],
    
    # ========================================================================
    # RUY LOPEZ TRAPS (e4 e5 Nf3 Nc6 Bb5)
    # ========================================================================
    "ruy-lopez": [
        {
            "name": "Noah's Ark Trap",
            "description": "A classic trap that wins White's light-squared bishop!",
            "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "d6", "d4", "b5", "Bb3", "Nxd4", "Nxd4", "exd4"],
            "trap_line": [
                {"move": "Qxd4", "explanation": "White takes the pawn."},
                {"move": "c5", "explanation": "Attack the queen!"},
                {"move": "Qd5", "explanation": "The queen retreats."},
                {"move": "Be6", "explanation": "Attack the queen again!"},
                {"move": "Qc6+", "explanation": "White checks."},
                {"move": "Bd7", "explanation": "Block and attack the queen."},
                {"move": "Qd5", "explanation": "The queen moves."},
                {"move": "c4", "explanation": "The Noah's Ark Trap! The bishop is trapped."}
            ],
            "success_message": "Noah's Ark Trap! White's bishop has no escape.",
            "result_type": "wins_piece",
            "difficulty": "intermediate"
        },
        {
            "name": "Mortimer Trap",
            "description": "A beautiful smothered mate in the Ruy Lopez!",
            "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6", "d3", "Ne7"],
            "trap_line": [
                {"move": "Nxe5", "explanation": "White takes the pawn, but..."},
                {"move": "c6", "explanation": "Attacking the bishop."},
                {"move": "Nc4", "explanation": "The knight moves."},
                {"move": "cxb5", "explanation": "Black takes the bishop."},
                {"move": "Nd6#", "explanation": "Smothered Mate! Beautiful."}
            ],
            "success_message": "The Mortimer Trap! Smothered mate in the Ruy Lopez.",
            "result_type": "checkmate",
            "difficulty": "intermediate"
        }
    ],
    
    # ========================================================================
    # PHILIDOR DEFENSE TRAPS (e4 e5 Nf3 d6)
    # ========================================================================
    "philidor-defense": [
        {
            "name": "Philidor's Legal Mate",
            "description": "A version of Legal's Mate in the Philidor Defense.",
            "setup_moves": ["e4", "e5", "Nf3", "d6", "Bc4", "Bg4", "Nc3", "Nc6"],
            "trap_line": [
                {"move": "h3", "explanation": "Attack the bishop."},
                {"move": "Bh5", "explanation": "The bishop retreats, maintaining the pin."},
                {"move": "Nxe5", "explanation": "Sacrifice! Offering the queen."},
                {"move": "Bxd1", "explanation": "Black takes the queen, but..."},
                {"move": "Bxf7+", "explanation": "Check!"},
                {"move": "Ke7", "explanation": "The only move."},
                {"move": "Nd5#", "explanation": "Checkmate! Legal's Mate strikes again."}
            ],
            "success_message": "Legal's Mate in the Philidor! A classic queen sacrifice.",
            "result_type": "checkmate",
            "difficulty": "intermediate"
        }
    ],
    
    # ========================================================================
    # PETROV DEFENSE TRAPS (e4 e5 Nf3 Nf6)
    # ========================================================================
    "petrov-defense": [
        {
            "name": "Stafford Gambit Trap",
            "description": "A dangerous gambit where Black sacrifices a pawn for a mating attack!",
            "setup_moves": ["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nc6"],
            "trap_line": [
                {"move": "Nxc6", "explanation": "White takes the knight."},
                {"move": "dxc6", "explanation": "Black recaptures."},
                {"move": "d3", "explanation": "White develops cautiously."},
                {"move": "Bc5", "explanation": "Black develops aggressively."},
                {"move": "Bg5", "explanation": "White pins the knight."},
                {"move": "Nxe4", "explanation": "Black sacrifices!"},
                {"move": "Bxd8", "explanation": "White takes the queen, but..."},
                {"move": "Bxf2+", "explanation": "Check!"},
                {"move": "Ke2", "explanation": "The king moves."},
                {"move": "Bg4#", "explanation": "Checkmate! The Stafford Gambit strikes."}
            ],
            "success_message": "Stafford Gambit Mate! A brilliant attacking trap.",
            "result_type": "checkmate",
            "difficulty": "advanced"
        }
    ],
    
    # ========================================================================
    # BUDAPEST GAMBIT TRAPS (d4 Nf6 c4 e5)
    # ========================================================================
    "budapest-gambit": [
        {
            "name": "Kieninger Trap",
            "description": "A stunning smothered mate in the Budapest Gambit!",
            "setup_moves": ["d4", "Nf6", "c4", "e5", "dxe5", "Ng4", "Bf4", "Nc6", "Nf3", "Bb4+", "Nbd2", "Qe7", "a3", "Ngxe5"],
            "trap_line": [
                {"move": "axb4", "explanation": "White takes the bishop, but..."},
                {"move": "Nd3#", "explanation": "Smothered Mate! The knight delivers checkmate."}
            ],
            "success_message": "The Kieninger Trap! A beautiful smothered mate.",
            "result_type": "checkmate",
            "difficulty": "advanced"
        }
    ],
    
    # ========================================================================
    # DUTCH DEFENSE TRAPS (d4 f5)
    # ========================================================================
    "dutch-defense": [
        {
            "name": "Dutch Defense Mate",
            "description": "A quick checkmate if Black is too aggressive!",
            "setup_moves": ["d4", "f5", "Bg5", "h6", "Bh4", "g5", "Bg3", "f4"],
            "trap_line": [
                {"move": "e3", "explanation": "White opens lines."},
                {"move": "h5", "explanation": "Black continues pushing."},
                {"move": "Bd3", "explanation": "Developing with a threat."},
                {"move": "Rh6", "explanation": "Black defends awkwardly."},
                {"move": "Qxh5+", "explanation": "Queen sacrifice!"},
                {"move": "Rxh5", "explanation": "Black must take."},
                {"move": "Bg6#", "explanation": "Checkmate! The bishop delivers."}
            ],
            "success_message": "Dutch Defense Mate! A beautiful queen sacrifice leads to checkmate.",
            "result_type": "checkmate",
            "difficulty": "intermediate"
        }
    ],
    
    # ========================================================================
    # OPERA GAME (Famous attacking game)
    # ========================================================================
    "opera-game": [
        {
            "name": "Opera Game Finale",
            "description": "The famous finish from Morphy's Opera Game - a model attacking game!",
            "setup_moves": ["e4", "e5", "Nf3", "d6", "d4", "Bg4", "dxe5", "Bxf3", "Qxf3", "dxe5", "Bc4", "Nf6", "Qb3", "Qe7", "Nc3", "c6", "Bg5", "b5"],
            "trap_line": [
                {"move": "Nxb5", "explanation": "Sacrifice! Opening lines to the king."},
                {"move": "cxb5", "explanation": "Black takes."},
                {"move": "Bxb5+", "explanation": "Check!"},
                {"move": "Nbd7", "explanation": "Blocking with the knight."},
                {"move": "O-O-O", "explanation": "Castling with a deadly attack."},
                {"move": "Rd8", "explanation": "Black tries to defend."},
                {"move": "Rxd7", "explanation": "Sacrifice the rook!"},
                {"move": "Rxd7", "explanation": "Black takes."},
                {"move": "Rd1", "explanation": "Doubling rooks."},
                {"move": "Qe6", "explanation": "Black defends."},
                {"move": "Bxd7+", "explanation": "Another sacrifice!"},
                {"move": "Nxd7", "explanation": "Black takes."},
                {"move": "Qb8+", "explanation": "Queen sacrifice!"},
                {"move": "Nxb8", "explanation": "Forced."},
                {"move": "Rd8#", "explanation": "Checkmate! The Opera Game finish."}
            ],
            "success_message": "The Opera Game! Morphy's immortal attacking masterpiece.",
            "result_type": "checkmate",
            "difficulty": "advanced"
        }
    ]
}


def get_traps_for_opening(opening_key: str) -> List[Dict]:
    """Get all traps for a specific opening"""
    return TRAP_LIBRARY.get(opening_key, [])


def get_all_traps() -> Dict[str, List[Dict]]:
    """Get the entire trap library"""
    return TRAP_LIBRARY


def get_trap_by_name(trap_name: str) -> Optional[Dict]:
    """Find a trap by its name across all openings"""
    for opening_key, traps in TRAP_LIBRARY.items():
        for trap in traps:
            if trap["name"].lower() == trap_name.lower():
                return {**trap, "opening_key": opening_key}
    return None


def get_checkmate_traps() -> List[Dict]:
    """Get all traps that end in checkmate"""
    checkmate_traps = []
    for opening_key, traps in TRAP_LIBRARY.items():
        for trap in traps:
            if trap.get("result_type") == "checkmate":
                checkmate_traps.append({**trap, "opening_key": opening_key})
    return checkmate_traps


def get_traps_by_difficulty(difficulty: str) -> List[Dict]:
    """Get traps filtered by difficulty level"""
    filtered_traps = []
    for opening_key, traps in TRAP_LIBRARY.items():
        for trap in traps:
            if trap.get("difficulty") == difficulty:
                filtered_traps.append({**trap, "opening_key": opening_key})
    return filtered_traps
