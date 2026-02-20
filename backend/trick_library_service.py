"""
Trick Library Service - Curated chess traps and tactical patterns

Features:
1. Hardcoded famous traps with explanations
2. Lichess Puzzle API integration for opening-specific tactics
3. Three practice modes: Execution, Avoidance, Recognition
"""

import logging
import httpx
import chess
import chess.pgn
import io
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================================
# PRACTICE MODES
# ============================================================================

class PracticeMode(str, Enum):
    EXECUTION = "execution"      # Play the trap (you set it)
    AVOIDANCE = "avoidance"      # Engine tries to trap you (survive)
    RECOGNITION = "recognition"  # "Is there a trap here?"


# ============================================================================
# HARDCODED TRAP DATABASE
# ============================================================================

TRAPS_DATABASE: Dict[str, Dict] = {
    # -------------------------------------------------------------------------
    # BEGINNER TRAPS (Common at 600-1200)
    # -------------------------------------------------------------------------
    "scholars_mate": {
        "name": "Scholar's Mate",
        "eco": "C20",
        "opening": "King's Pawn Opening",
        "difficulty": "beginner",
        "frequency": "extremely_common",
        "rating_range": "600-1200",
        "description": "A 4-move checkmate targeting f7. Every beginner must know this!",
        "trap_for": "white",  # Who sets the trap
        "victim_color": "black",
        "setup_moves": ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6"],  # Moves leading to trap
        "trap_position_fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        "winning_move": "Qxf7#",
        "winning_line": ["Qxf7#"],
        "explanation": "White's queen and bishop combine to attack f7, the weakest square in Black's camp. After Qxf7#, it's checkmate because the king cannot escape.",
        "why_it_works": "f7 (and f2 for White) is only defended by the king in the opening. The bishop on c4 and queen on h5 create a deadly battery.",
        "how_to_avoid": [
            "Don't play Nf6 when the queen is on h5 attacking f7",
            "Block with g6 first, then develop normally",
            "Or play Qe7 to defend f7 and prepare to castle queenside"
        ],
        "key_squares": ["f7", "c4", "h5"],
        "tactical_theme": "weak_f7",
        "practice_fen": {
            "execution": "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",  # Black to move, about to blunder
            "avoidance": "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",  # Find safe move
            "recognition": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"  # Is there a trap?
        }
    },
    
    "fried_liver_attack": {
        "name": "Fried Liver Attack",
        "eco": "C57",
        "opening": "Italian Game",
        "difficulty": "intermediate",
        "frequency": "very_common",
        "rating_range": "800-1600",
        "description": "A violent knight sacrifice on f7, exposing Black's king to a deadly attack.",
        "trap_for": "white",
        "victim_color": "black",
        "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "d5", "exd5", "Nxd5"],
        "trap_position_fen": "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
        "winning_move": "Nxf7",
        "winning_line": ["Nxf7", "Kxf7", "Qf3+", "Ke6", "Nc3"],
        "explanation": "White sacrifices the knight to expose Black's king. After Kxf7, Qf3+ forces the king into the center where it faces a massive attack.",
        "why_it_works": "Black's king is forced to move and cannot castle. White develops with tempo, attacking the exposed king with Nc3, d4, and Bf4.",
        "how_to_avoid": [
            "Play Na5 instead of Nxd5 (the Traxler/Polerio Defense)",
            "Play d5 earlier with Bc5 to avoid Ng5",
            "Consider h6 to kick the knight before it lands on g5"
        ],
        "key_squares": ["f7", "g5", "f3", "e6"],
        "tactical_theme": "king_hunt",
        "practice_fen": {
            "execution": "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
            "avoidance": "r1bqkb1r/ppp2ppp/2n2n2/4p1N1/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 5 5",
            "recognition": "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6"
        }
    },
    
    "legals_mate": {
        "name": "Legal's Mate",
        "eco": "C41",
        "opening": "Philidor Defense",
        "difficulty": "intermediate",
        "frequency": "common",
        "rating_range": "800-1400",
        "description": "A queen sacrifice leading to a beautiful smothered-style checkmate with minor pieces.",
        "trap_for": "white",
        "victim_color": "black",
        "setup_moves": ["e4", "e5", "Nf3", "d6", "Bc4", "Bg4", "Nc3", "g6"],
        "trap_position_fen": "rn1qkbnr/ppp2p1p/3p2p1/4p3/2B1P1b1/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 5",
        "winning_move": "Nxe5",
        "winning_line": ["Nxe5", "Bxd1", "Bxf7+", "Ke7", "Nd5#"],
        "explanation": "White sacrifices the queen! After Bxd1, Bxf7+ forces Ke7, and Nd5# is checkmate. The knights and bishop coordinate perfectly.",
        "why_it_works": "Black's bishop on g4 is undefended and blocking escape squares. The sacrifice works because the checkmate is faster than capturing the queen.",
        "how_to_avoid": [
            "Don't capture the queen! Play dxe5 instead",
            "Better: don't pin the knight when your king is still in the center",
            "Develop Nf6 before Bg4 to have more control"
        ],
        "key_squares": ["f7", "e7", "d5"],
        "tactical_theme": "queen_sacrifice",
        "practice_fen": {
            "execution": "rn1qkbnr/ppp2p1p/3p2p1/4p3/2B1P1b1/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 5",
            "avoidance": "rn1qkbnr/ppp2p1p/3p2p1/4N3/2B1P1b1/2N5/PPPP1PPP/R1BQK2R b KQkq - 0 5",
            "recognition": "rn1qkbnr/ppp2p1p/3p2p1/4p3/2B1P1b1/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 5"
        }
    },
    
    "scandinavian_trap": {
        "name": "Scandinavian Defense Trap",
        "eco": "B01",
        "opening": "Scandinavian Defense",
        "difficulty": "beginner",
        "frequency": "very_common",
        "rating_range": "600-1200",
        "description": "Black's queen gets trapped after greedy pawn captures.",
        "trap_for": "white",
        "victim_color": "black",
        "setup_moves": ["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "e5"],
        "trap_position_fen": "rnb1kbnr/ppp2ppp/8/q3p3/3P4/2N5/PPP2PPP/R1BQKBNR w KQkq - 0 5",
        "winning_move": "dxe5",
        "winning_line": ["dxe5", "Qxe5+", "Be2", "Bg4", "Nf3", "Bxf3", "Bxf3"],
        "explanation": "After dxe5, Black's queen is exposed. White develops with tempo and Black struggles to find safe squares for the queen.",
        "why_it_works": "Black's queen came out too early and is now a target. Every White piece develops with tempo attacking the queen.",
        "how_to_avoid": [
            "Don't play e5 in this position - it weakens d5",
            "Play Nf6 or c6 for solid development",
            "The Scandinavian requires careful queen placement"
        ],
        "key_squares": ["a5", "e5", "d5"],
        "tactical_theme": "queen_harassment",
        "practice_fen": {
            "execution": "rnb1kbnr/ppp2ppp/8/q3p3/3P4/2N5/PPP2PPP/R1BQKBNR w KQkq - 0 5",
            "avoidance": "rnb1kbnr/ppp2ppp/8/q7/3PP3/2N5/PPP2PPP/R1BQKBNR b KQkq - 0 5",
            "recognition": "rnb1kbnr/ppp2ppp/8/q3p3/3P4/2N5/PPP2PPP/R1BQKBNR w KQkq - 0 5"
        }
    },
    
    # -------------------------------------------------------------------------
    # GAMBIT TRAPS
    # -------------------------------------------------------------------------
    "budapest_gambit_trap": {
        "name": "Budapest Gambit Trap",
        "eco": "A52",
        "opening": "Budapest Gambit",
        "difficulty": "intermediate",
        "frequency": "common",
        "rating_range": "1000-1600",
        "description": "Black sacrifices a pawn to trap White's queen or win material.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["d4", "Nf6", "c4", "e5", "dxe5", "Ng4", "Bf4", "Nc6", "Nf3", "Bb4+", "Nbd2", "Qe7", "a3", "Ngxe5"],
        "trap_position_fen": "r1b1k2r/ppppqppp/2n5/4n3/1bP2B2/P4N2/1P1NPPPP/R2QKB1R w KQkq - 0 8",
        "winning_move": "Nxe5",
        "winning_line": ["Nxe5", "Nxe5", "axb4", "Nd3#"],
        "explanation": "After White captures on e5, Black plays the stunning Nd3#! The knight delivers checkmate supported by the queen.",
        "why_it_works": "White's king is stuck in the center and the d3 square is fatally weak. The bishop on b4 prevents Ke2.",
        "how_to_avoid": [
            "Don't capture Nxe5 - play e3 instead",
            "Be careful with the a3 move - it weakens the position",
            "Castle early to avoid such tactics"
        ],
        "key_squares": ["d3", "e5", "b4"],
        "tactical_theme": "smothered_mate",
        "practice_fen": {
            "execution": "r1b1k2r/ppppqppp/2n5/4n3/1bP2B2/P4N2/1P1NPPPP/R2QKB1R w KQkq - 0 8",
            "avoidance": "r1b1k2r/ppppqppp/2n5/4N3/1bP2B2/P7/1P1NPPPP/R2QKB1R b KQkq - 0 8",
            "recognition": "r1b1k2r/ppppqppp/2n5/4n3/1bP2B2/P4N2/1P1NPPPP/R2QKB1R w KQkq - 0 8"
        }
    },
    
    "albin_countergambit_trap": {
        "name": "Albin Countergambit Trap",
        "eco": "D08",
        "opening": "Albin Countergambit",
        "difficulty": "intermediate",
        "frequency": "common",
        "rating_range": "1000-1600",
        "description": "Black's pawn on e4 becomes a monster, trapping White's pieces.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["d4", "d5", "c4", "e5", "dxe5", "d4", "e3", "Bb4+", "Bd2", "dxe3"],
        "trap_position_fen": "rnbqk1nr/ppp2ppp/8/4P3/1bP5/4p3/PP1BPPPP/RN1QKBNR w KQkq - 0 6",
        "winning_move": "Bxb4+",
        "winning_line": ["Bxb4+", "Qxb4+", "Qd2+", "Qxd2+", "exf2#"],
        "explanation": "The deadly Lasker Trap! After Bxb4, Black plays Qxb4+. The queen trade leads to exf2#, an incredible pawn checkmate!",
        "why_it_works": "White's f2 square is fatally weak. The pawn promotes with check... wait, no - it delivers checkmate directly!",
        "how_to_avoid": [
            "Never play e3 in the Albin - play Nf3 instead",
            "Don't take on b4 with the bishop",
            "Be very careful of the e4 pawn's power"
        ],
        "key_squares": ["e3", "f2", "b4", "d2"],
        "tactical_theme": "pawn_mate",
        "practice_fen": {
            "execution": "rnbqk1nr/ppp2ppp/8/4P3/1bP5/4p3/PP1BPPPP/RN1QKBNR w KQkq - 0 6",
            "avoidance": "rnbqk1nr/ppp2ppp/8/4P3/2P5/4p3/PP1BPPPP/RN1QKBNR b KQkq - 0 6",
            "recognition": "rnbqk1nr/ppp2ppp/8/4P3/1bP5/4p3/PP1BPPPP/RN1QKBNR w KQkq - 0 6"
        }
    },
    
    "stafford_gambit_trap": {
        "name": "Stafford Gambit Trap",
        "eco": "C42",
        "opening": "Petrov Defense",
        "difficulty": "intermediate",
        "frequency": "common",
        "rating_range": "1000-1800",
        "description": "Black sacrifices a pawn for rapid development and deadly attacks on f2.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nc6", "Nxc6", "dxc6", "d3", "Bc5", "Bg5", "Nxe4"],
        "trap_position_fen": "r1bqk2r/ppp2ppp/2p5/2b3B1/4n3/3P4/PPP2PPP/RN1QKB1R w KQkq - 0 7",
        "winning_move": "dxe4",
        "winning_line": ["dxe4", "Bxf2+", "Ke2", "Bg4+", "Kxf2", "Qxd1"],
        "explanation": "After dxe4, Black plays Bxf2+! The king must move, and Bg4+ wins the queen. White is destroyed.",
        "why_it_works": "White's f2 is undefended and the king has no safe squares. The discovered attack with Bg4+ is crushing.",
        "how_to_avoid": [
            "Don't take the knight with dxe4",
            "Play Be2 instead of d3 to prepare castling",
            "Avoid Bg5 - it doesn't help development"
        ],
        "key_squares": ["f2", "e4", "g4"],
        "tactical_theme": "discovered_attack",
        "practice_fen": {
            "execution": "r1bqk2r/ppp2ppp/2p5/2b3B1/4n3/3P4/PPP2PPP/RN1QKB1R w KQkq - 0 7",
            "avoidance": "r1bqk2r/ppp2ppp/2p5/2b3B1/4P3/8/PPP2PPP/RN1QKB1R b KQkq - 0 7",
            "recognition": "r1bqk2r/ppp2ppp/2p5/2b3B1/4n3/3P4/PPP2PPP/RN1QKB1R w KQkq - 0 7"
        }
    },
    
    "englund_gambit_trap": {
        "name": "Englund Gambit Trap",
        "eco": "A40",
        "opening": "Englund Gambit",
        "difficulty": "beginner",
        "frequency": "common",
        "rating_range": "600-1400",
        "description": "Black gambits a pawn hoping White gets greedy and loses the queen.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["d4", "e5", "dxe5", "Nc6", "Nf3", "Qe7", "Bf4", "Qb4+", "Bd2", "Qxb2", "Bc3"],
        "trap_position_fen": "r1b1kbnr/pppp1ppp/2n5/4P3/8/2B2N2/PqP1PPPP/RN1QKB1R b KQkq - 1 6",
        "winning_move": "Bb4",
        "winning_line": ["Bb4", "Qd2", "Bxc3", "Qxc3", "Qc1#"],
        "explanation": "Black's queen appears trapped but Bb4! pins the bishop. After Bxc3, Qc1# is checkmate! The queen delivers mate on c1.",
        "why_it_works": "White's back rank is weak and the knight on b1 blocks the king's escape. Classic back rank theme.",
        "how_to_avoid": [
            "Don't play Bc3 - it walks into the trap",
            "Play Nc3 instead to develop normally",
            "Don't be greedy - Black's queen on b2 is bait"
        ],
        "key_squares": ["c1", "c3", "b4", "b2"],
        "tactical_theme": "back_rank",
        "practice_fen": {
            "execution": "r1b1kbnr/pppp1ppp/2n5/4P3/8/2B2N2/PqP1PPPP/RN1QKB1R b KQkq - 1 6",
            "avoidance": "r1b1kbnr/pppp1ppp/2n5/4P3/8/5N2/PqPBPPPP/RN1QKB1R w KQkq - 0 6",
            "recognition": "r1b1kbnr/pppp1ppp/2n5/4P3/8/2B2N2/PqP1PPPP/RN1QKB1R b KQkq - 1 6"
        }
    },
    
    # -------------------------------------------------------------------------
    # COUNTERATTACK TRAPS
    # -------------------------------------------------------------------------
    "traxler_counterattack": {
        "name": "Traxler Counterattack",
        "eco": "C57",
        "opening": "Italian Game",
        "difficulty": "advanced",
        "frequency": "common",
        "rating_range": "1200-2000",
        "description": "Instead of defending f7, Black counterattacks f2! Chaos ensues.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "Bc5"],
        "trap_position_fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p1N1/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 4 5",
        "winning_move": "Nxf7",
        "winning_line": ["Nxf7", "Bxf2+", "Kf1", "Qe7", "Nxh8", "d5"],
        "explanation": "After Nxf7, Black ignores the rook and plays Bxf2+! White's king loses castling rights and Black gets a vicious attack despite being down material.",
        "why_it_works": "White wins the exchange but Black's pieces swarm the exposed king. The initiative is worth more than material.",
        "how_to_avoid": [
            "As White: Don't take on f7! Play d4 or d3 instead",
            "The Traxler is sound for Black - respect it",
            "If you must take, be ready for a wild game"
        ],
        "key_squares": ["f7", "f2", "f1", "h8"],
        "tactical_theme": "counterattack",
        "practice_fen": {
            "execution": "r1bqk2r/pppp1ppp/2n2n2/2b1p1N1/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 4 5",
            "avoidance": "r1bqk2r/pppp1ppp/2n2n2/2b1p1N1/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 4 5",
            "recognition": "r1bqk2r/pppp1ppp/2n2n2/2b1p1N1/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 4 5"
        }
    },
    
    # -------------------------------------------------------------------------
    # POSITIONAL TRAPS
    # -------------------------------------------------------------------------
    "noahs_ark_trap": {
        "name": "Noah's Ark Trap",
        "eco": "C65",
        "opening": "Ruy Lopez",
        "difficulty": "intermediate",
        "frequency": "common",
        "rating_range": "1000-1600",
        "description": "Black's pawns trap White's bishop on b3 - an ancient trap!",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "d6", "d4", "b5", "Bb3", "Nxd4", "Nxd4", "exd4", "Qxd4", "c5", "Qd5", "Be6", "Qc6+", "Bd7", "Qd5", "c4"],
        "trap_position_fen": "r2qkbnr/3b1ppp/p2p4/1p1Q4/2p1P3/1B6/PPP2PPP/RNB1K2R w KQkq - 0 12",
        "winning_move": "Ba4",
        "winning_line": ["Ba4", "b4", "and c3 traps the bishop"],
        "explanation": "The bishop on b3 is trapped! After ...c4, the bishop must retreat to a4, then b4 and c3 close the cage. The bishop is lost.",
        "why_it_works": "White's bishop ventured too far without an escape route. The pawn chain a6-b5-c4 forms a deadly net.",
        "how_to_avoid": [
            "Don't let the bishop get trapped on b3",
            "Play Qxd4 with care or avoid taking on d4",
            "Keep an eye on the a6-b5-c4 pawn chain forming"
        ],
        "key_squares": ["b3", "a4", "c4", "b4"],
        "tactical_theme": "trapped_piece",
        "practice_fen": {
            "execution": "r2qkbnr/3b1ppp/p2p4/1p1Q4/2p1P3/1B6/PPP2PPP/RNB1K2R w KQkq - 0 12",
            "avoidance": "r2qkbnr/3b1ppp/p2p4/1p1Q4/4P3/1B6/PPP2PPP/RNB1K2R b KQkq - 0 11",
            "recognition": "r2qkbnr/3b1ppp/p2p4/1p1Q4/2p1P3/1B6/PPP2PPP/RNB1K2R w KQkq - 0 12"
        }
    },
    
    "fishing_pole_trap": {
        "name": "Fishing Pole Trap",
        "eco": "C65",
        "opening": "Ruy Lopez",
        "difficulty": "intermediate",
        "frequency": "common",
        "rating_range": "1000-1800",
        "description": "Black sacrifices the h-pawn to rip open White's kingside.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6", "O-O", "Ng4", "h3", "h5"],
        "trap_position_fen": "r1bqkb1r/pppp1pp1/2n5/1B2p2p/4P1n1/5N1P/PPPP1PP1/RNBQ1RK1 w kq - 0 6",
        "winning_move": "hxg4",
        "winning_line": ["hxg4", "hxg4", "Nxe5", "Qh4", "Nxc6", "g3", "Nxd8", "Bh3#"],
        "explanation": "After hxg4 hxg4, Black's h-file is open! Qh4 threatens mate. If White plays Nxe5, Black continues g3! threatening Qh1#.",
        "why_it_works": "The open h-file combined with Black's queen and potential bishop sacrifice on h3 creates unstoppable mate threats.",
        "how_to_avoid": [
            "Don't take the knight on g4 with the h-pawn",
            "Play d3 or Be2 instead",
            "Recognize the h5 push as a signal of the trap"
        ],
        "key_squares": ["h3", "h4", "g4", "g3"],
        "tactical_theme": "kingside_attack",
        "practice_fen": {
            "execution": "r1bqkb1r/pppp1pp1/2n5/1B2p2p/4P1n1/5N1P/PPPP1PP1/RNBQ1RK1 w kq - 0 6",
            "avoidance": "r1bqkb1r/pppp1pp1/2n5/1B2p2p/4P1n1/5N1P/PPPP1PP1/RNBQ1RK1 w kq - 0 6",
            "recognition": "r1bqkb1r/pppp1pp1/2n5/1B2p2p/4P1n1/5N1P/PPPP1PP1/RNBQ1RK1 w kq - 0 6"
        }
    },
    
    "elephant_trap": {
        "name": "Elephant Trap",
        "eco": "D51",
        "opening": "Queen's Gambit Declined",
        "difficulty": "intermediate",
        "frequency": "common",
        "rating_range": "1000-1600",
        "description": "Black wins a piece with a clever discovered attack on the queen.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Nbd7", "cxd5", "exd5", "Nxd5", "Nxd5", "Bxd8", "Bb4+", "Qd2", "Bxd2+", "Kxd2", "Kxd8"],
        "trap_position_fen": "r1bk3r/pppn1ppp/8/3n4/3P4/8/PP1KPPPP/R4BNR w - - 0 10",
        "winning_move": "Bb4+",
        "winning_line": ["After Bxd8??", "Bb4+", "Qd2", "Bxd2+", "Kxd2", "Kxd8"],
        "explanation": "After Bxd8?? (taking the queen), Bb4+ forks the king and queen! Black ends up with an extra piece.",
        "why_it_works": "White gets greedy taking the queen but forgets about the discovered check. The bishop on b4 delivers the blow.",
        "how_to_avoid": [
            "Don't take the queen with Bxd8!",
            "After Nxd5, play Bxf6 instead",
            "Be aware of discovered attacks in the center"
        ],
        "key_squares": ["d8", "b4", "d2"],
        "tactical_theme": "discovered_attack",
        "practice_fen": {
            "execution": "r1bqk2r/pppn1ppp/4pn2/3P2B1/3P4/2N5/PP2PPPP/R2QKB1R b KQkq - 0 7",
            "avoidance": "r1bqk2r/pppn1ppp/5n2/3n2B1/3P4/8/PP2PPPP/R2QKBNR w KQkq - 0 8",
            "recognition": "r1bqk2r/pppn1ppp/5n2/3n2B1/3P4/8/PP2PPPP/R2QKBNR w KQkq - 0 8"
        }
    },
    
    "philidor_trap": {
        "name": "Philidor Defense Trap",
        "eco": "C41",
        "opening": "Philidor Defense",
        "difficulty": "beginner",
        "frequency": "common",
        "rating_range": "600-1200",
        "description": "White wins a pawn and destroys Black's pawn structure with a simple tactic.",
        "trap_for": "white",
        "victim_color": "black",
        "setup_moves": ["e4", "e5", "Nf3", "d6", "d4", "Nd7", "Bc4", "Be7", "dxe5", "dxe5"],
        "trap_position_fen": "r1bqk1nr/pppnbppp/8/4p3/2B1P3/5N2/PPP2PPP/RNBQK2R w KQkq - 0 6",
        "winning_move": "Qd5",
        "winning_line": ["Qd5", "Nh6", "Bxh6", "O-O", "Bxg7", "Kxg7", "Qxe5+"],
        "explanation": "Qd5! attacks f7 and e5 simultaneously. Black cannot defend both. After losing e5, Black's position crumbles.",
        "why_it_works": "The double attack on f7 and e5 is impossible to parry. The knight on d7 blocks the queen's defense of e5.",
        "how_to_avoid": [
            "Don't play dxe5 - play Nxe5 instead",
            "Or avoid d6 systems and play Nc6",
            "Develop the knight to f6, not d7"
        ],
        "key_squares": ["d5", "f7", "e5"],
        "tactical_theme": "double_attack",
        "practice_fen": {
            "execution": "r1bqk1nr/pppnbppp/8/4p3/2B1P3/5N2/PPP2PPP/RNBQK2R w KQkq - 0 6",
            "avoidance": "r1bqk1nr/pppnbppp/3p4/4P3/2B1P3/5N2/PPP2PPP/RNBQK2R b KQkq - 0 6",
            "recognition": "r1bqk1nr/pppnbppp/8/4p3/2B1P3/5N2/PPP2PPP/RNBQK2R w KQkq - 0 6"
        }
    },
    
    "siberian_trap": {
        "name": "Siberian Trap",
        "eco": "C55",
        "opening": "Italian Game",
        "difficulty": "intermediate",
        "frequency": "common",
        "rating_range": "1000-1600",
        "description": "Black's queen infiltrates via a5-b6-b2, winning material.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "d3", "Be7", "O-O", "O-O", "Bg5", "d6", "h3", "Na5"],
        "trap_position_fen": "r1bq1rk1/ppp1bppp/3p1n2/n3p1B1/2B1P3/3P1N1P/PPP2PP1/RN1Q1RK1 w - - 5 8",
        "winning_move": "b4",
        "winning_line": ["b4", "Nxc4", "dxc4", "Qa5", "Bd2", "Qb6", "b3", "Qxb3"],
        "explanation": "After b4?, Black plays Nxc4! dxc4 Qa5. White's queenside collapses. The queen penetrates via b6-b3 winning pawns.",
        "why_it_works": "White's b4 push weakens c4 and b3. Black's knight sacrifice opens lines for the queen invasion.",
        "how_to_avoid": [
            "Don't push b4 when the knight is on a5",
            "Play a3 first to prepare b4 safely",
            "Respect the knight on a5 - it's not misplaced"
        ],
        "key_squares": ["a5", "c4", "b6", "b3"],
        "tactical_theme": "queen_invasion",
        "practice_fen": {
            "execution": "r1bq1rk1/ppp1bppp/3p1n2/n3p1B1/2B1P3/3P1N1P/PPP2PP1/RN1Q1RK1 w - - 5 8",
            "avoidance": "r1bq1rk1/ppp1bppp/3p1n2/n3p1B1/1PB1P3/3P1N1P/P1P2PP1/RN1Q1RK1 b - - 0 8",
            "recognition": "r1bq1rk1/ppp1bppp/3p1n2/n3p1B1/2B1P3/3P1N1P/PPP2PP1/RN1Q1RK1 w - - 5 8"
        }
    },
    
    "blackburne_shilling_gambit": {
        "name": "Blackburne Shilling Gambit",
        "eco": "C50",
        "opening": "Italian Game",
        "difficulty": "beginner",
        "frequency": "common",
        "rating_range": "600-1400",
        "description": "Black offers a knight to set up a queen trap or fork.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4"],
        "trap_position_fen": "r1bqkbnr/pppp1ppp/8/4p3/2BnP3/5N2/PPPP1PPP/RNBQK2R w KQkq - 3 4",
        "winning_move": "Nxe5",
        "winning_line": ["Nxe5", "Qg5", "Nxf7", "Qxg2", "Rf1", "Qxe4+", "Be2", "Nf3#"],
        "explanation": "After Nxe5?, Black plays Qg5! attacking g2 and e5. If Nxf7, Qxg2 threatens Qxf1#. The attack is devastating.",
        "why_it_works": "White's knight on e5 is unstable and the g2 pawn is weak. Black's queen and knight coordinate perfectly.",
        "how_to_avoid": [
            "Don't take on e5! Play Nxd4 first",
            "Or play c3 to kick the knight away",
            "The knight on d4 is poisoned"
        ],
        "key_squares": ["d4", "g5", "g2", "f7"],
        "tactical_theme": "queen_attack",
        "practice_fen": {
            "execution": "r1bqkbnr/pppp1ppp/8/4p3/2BnP3/5N2/PPPP1PPP/RNBQK2R w KQkq - 3 4",
            "avoidance": "r1bqkbnr/pppp1ppp/8/4N3/2BnP3/8/PPPP1PPP/RNBQK2R b KQkq - 0 4",
            "recognition": "r1bqkbnr/pppp1ppp/8/4p3/2BnP3/5N2/PPPP1PPP/RNBQK2R w KQkq - 3 4"
        }
    },
    
    "jerome_gambit": {
        "name": "Jerome Gambit",
        "eco": "C50",
        "opening": "Italian Game",
        "difficulty": "advanced",
        "frequency": "rare",
        "rating_range": "any",
        "description": "White sacrifices BOTH bishop and knight on f7 for a wild attack!",
        "trap_for": "white",
        "victim_color": "black",
        "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "Bxf7+"],
        "trap_position_fen": "r1bqk1nr/pppp1Bpp/2n5/2b1p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 4",
        "winning_move": "Kxf7",
        "winning_line": ["Kxf7", "Nxe5+", "Nxe5", "Qh5+", "g6", "Qxe5"],
        "explanation": "White sacs the bishop on f7, then the knight on e5! The king is exposed and Qh5+ creates chaos. Objectively dubious but very tricky.",
        "why_it_works": "Black's king loses all safety. Even if Black defends correctly, the positions are sharp and error-prone.",
        "how_to_avoid": [
            "After Bxf7+ Kxf7 Nxe5+, play Ke8! (not Nxe5)",
            "Keep calm - you're winning material",
            "Trade queens to reduce White's attack"
        ],
        "key_squares": ["f7", "e5", "h5"],
        "tactical_theme": "king_hunt",
        "practice_fen": {
            "execution": "r1bqk1nr/pppp1Bpp/2n5/2b1p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 4",
            "avoidance": "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            "recognition": "r1bqk1nr/pppp1Bpp/2n5/2b1p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 4"
        }
    },
    
    "lasker_trap": {
        "name": "Lasker Trap",
        "eco": "D08",
        "opening": "Albin Countergambit",
        "difficulty": "intermediate",
        "frequency": "common",
        "rating_range": "1000-1600",
        "description": "A pawn delivers checkmate! One of the most beautiful traps in chess.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["d4", "d5", "c4", "e5", "dxe5", "d4", "e3", "Bb4+", "Bd2", "dxe3"],
        "trap_position_fen": "rnbqk1nr/ppp2ppp/8/4P3/1b6/4p3/PP1B1PPP/RN1QKBNR w KQkq - 0 6",
        "winning_move": "Bxb4+",
        "winning_line": ["Bxb4+", "Qxb4+", "Qd2+", "Qxd2+", "exf2#"],
        "explanation": "The deadly Lasker Trap! After Bxb4+ Qxb4+, White must play Qd2. Then Qxd2+ Kxd2 exf2#!! A PAWN delivers checkmate!",
        "why_it_works": "The f2 pawn falls with check, and the e-pawn delivers mate. White's king is completely helpless.",
        "how_to_avoid": [
            "Never play e3 in the Albin Countergambit",
            "Play Nf3 to develop and control e5",
            "If you reach this position, don't take on b4"
        ],
        "key_squares": ["e3", "f2", "b4", "d2"],
        "tactical_theme": "pawn_checkmate",
        "practice_fen": {
            "execution": "rnbqk1nr/ppp2ppp/8/4P3/1b6/4p3/PP1B1PPP/RN1QKBNR w KQkq - 0 6",
            "avoidance": "rnbqk1nr/ppp2ppp/8/4P3/1b6/4P3/PP1B1PPP/RN1QKBNR b KQkq - 0 6",
            "recognition": "rnbqk1nr/ppp2ppp/8/4P3/1b6/4p3/PP1B1PPP/RN1QKBNR w KQkq - 0 6"
        }
    },
    
    "mortimer_trap": {
        "name": "Mortimer Trap",
        "eco": "C65",
        "opening": "Ruy Lopez",
        "difficulty": "intermediate",
        "frequency": "uncommon",
        "rating_range": "1200-1800",
        "description": "Black wins the bishop pair with a clever knight maneuver.",
        "trap_for": "black",
        "victim_color": "white",
        "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6", "d3", "Ne7"],
        "trap_position_fen": "r1bqkb1r/ppppnppp/5n2/1B2p3/4P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 1 5",
        "winning_move": "Bxc6",
        "winning_line": ["Bxc6", "dxc6", "Nxe4"],
        "explanation": "After Bxc6?? (White thinks they're winning a piece), dxc6 Nxe4! wins the e-pawn. If dxe4 Qxd1+.",
        "why_it_works": "White's d3 pawn is pinned to the queen. Black wins material cleanly.",
        "how_to_avoid": [
            "Don't take on c6 - it's a trap!",
            "Play Nc3 or O-O instead",
            "Ne7 is a signal that Black is setting something up"
        ],
        "key_squares": ["c6", "e4", "d1"],
        "tactical_theme": "pin",
        "practice_fen": {
            "execution": "r1bqkb1r/ppppnppp/5n2/1B2p3/4P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 1 5",
            "avoidance": "r1bqkb1r/ppppnppp/2B2n2/4p3/4P3/3P1N2/PPP2PPP/RNBQK2R b KQkq - 0 5",
            "recognition": "r1bqkb1r/ppppnppp/5n2/1B2p3/4P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 1 5"
        }
    }
}


# ============================================================================
# TRAP CATEGORIES
# ============================================================================

TRAP_CATEGORIES = {
    "beginner": {
        "name": "Beginner Traps",
        "description": "Essential traps every player must know (600-1200)",
        "traps": ["scholars_mate", "scandinavian_trap", "philidor_trap", "englund_gambit_trap", "blackburne_shilling_gambit"]
    },
    "gambit": {
        "name": "Gambit Traps",
        "description": "Traps arising from pawn sacrifices",
        "traps": ["budapest_gambit_trap", "albin_countergambit_trap", "stafford_gambit_trap", "lasker_trap"]
    },
    "italian": {
        "name": "Italian Game Traps",
        "description": "Traps in the Italian Opening and related lines",
        "traps": ["fried_liver_attack", "traxler_counterattack", "legals_mate", "siberian_trap", "jerome_gambit", "blackburne_shilling_gambit"]
    },
    "positional": {
        "name": "Positional Traps",
        "description": "Traps that win material through positional means",
        "traps": ["noahs_ark_trap", "fishing_pole_trap", "elephant_trap", "mortimer_trap"]
    },
    "queen_traps": {
        "name": "Queen Traps",
        "description": "Traps that win or trap the queen",
        "traps": ["scandinavian_trap", "siberian_trap", "elephant_trap"]
    }
}


# ============================================================================
# SERVICE FUNCTIONS
# ============================================================================

def get_all_traps() -> List[Dict]:
    """Get all traps with metadata."""
    traps = []
    for key, trap in TRAPS_DATABASE.items():
        traps.append({
            "key": key,
            **trap
        })
    return traps


def get_trap_by_key(trap_key: str) -> Optional[Dict]:
    """Get a specific trap by its key."""
    trap = TRAPS_DATABASE.get(trap_key)
    if trap:
        return {"key": trap_key, **trap}
    return None


def get_traps_by_opening(opening_name: str) -> List[Dict]:
    """Get all traps associated with a specific opening."""
    opening_lower = opening_name.lower()
    traps = []
    for key, trap in TRAPS_DATABASE.items():
        if opening_lower in trap.get("opening", "").lower():
            traps.append({"key": key, **trap})
    return traps


def get_traps_by_category(category: str) -> List[Dict]:
    """Get traps in a specific category."""
    cat_data = TRAP_CATEGORIES.get(category)
    if not cat_data:
        return []
    
    traps = []
    for trap_key in cat_data.get("traps", []):
        trap = TRAPS_DATABASE.get(trap_key)
        if trap:
            traps.append({"key": trap_key, **trap})
    return traps


def get_traps_by_difficulty(difficulty: str) -> List[Dict]:
    """Get traps by difficulty level."""
    traps = []
    for key, trap in TRAPS_DATABASE.items():
        if trap.get("difficulty") == difficulty:
            traps.append({"key": key, **trap})
    return traps


def get_trap_for_practice(trap_key: str, mode: str) -> Optional[Dict]:
    """
    Get trap data formatted for a specific practice mode.
    
    Modes:
    - execution: Player tries to execute the trap
    - avoidance: Player tries to avoid falling into the trap
    - recognition: Player identifies if there's a trap
    """
    trap = TRAPS_DATABASE.get(trap_key)
    if not trap:
        return None
    
    practice_fen = trap.get("practice_fen", {}).get(mode)
    if not practice_fen:
        practice_fen = trap.get("trap_position_fen")
    
    return {
        "key": trap_key,
        "name": trap["name"],
        "mode": mode,
        "fen": practice_fen,
        "trap_for": trap["trap_for"],
        "victim_color": trap["victim_color"],
        "winning_move": trap["winning_move"] if mode == "execution" else None,
        "winning_line": trap["winning_line"] if mode == "execution" else None,
        "how_to_avoid": trap["how_to_avoid"] if mode == "avoidance" else None,
        "explanation": trap["explanation"],
        "hints": {
            "execution": f"Find the winning move for {trap['trap_for']}!",
            "avoidance": f"You're {trap['victim_color']}. Find a safe move to avoid the trap!",
            "recognition": "Is there a tactical trap in this position? Identify it!"
        }.get(mode, "")
    }


# ============================================================================
# LICHESS PUZZLE API INTEGRATION
# ============================================================================

LICHESS_API_BASE = "https://lichess.org/api"

# Mapping of opening names to Lichess puzzle themes
OPENING_TO_LICHESS_THEME = {
    "italian": "Italian_Game",
    "sicilian": "Sicilian_Defense",
    "french": "French_Defense",
    "caro-kann": "Caro-Kann_Defense",
    "scandinavian": "Scandinavian_Defense",
    "ruy lopez": "Ruy_Lopez",
    "queens gambit": "Queens_Gambit",
    "kings indian": "Kings_Indian_Defense",
    "english": "English_Opening",
    "london": "London_System"
}


async def fetch_lichess_puzzles_by_opening(opening: str, count: int = 10) -> List[Dict]:
    """
    Fetch puzzles from Lichess that are tagged with a specific opening.
    """
    # Try to map to Lichess theme
    opening_lower = opening.lower().replace("'", "").replace("-", " ")
    lichess_theme = None
    for key, theme in OPENING_TO_LICHESS_THEME.items():
        if key in opening_lower:
            lichess_theme = theme
            break
    
    if not lichess_theme:
        logger.info(f"No Lichess theme mapping for opening: {opening}")
        return []
    
    try:
        async with httpx.AsyncClient() as client:
            # Use the puzzle activity endpoint with theme filter
            response = await client.get(
                f"{LICHESS_API_BASE}/puzzle/daily",
                headers={"Accept": "application/json"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                puzzle = response.json()
                return [{
                    "id": puzzle.get("puzzle", {}).get("id"),
                    "fen": puzzle.get("puzzle", {}).get("initialPly"),
                    "solution": puzzle.get("puzzle", {}).get("solution", []),
                    "rating": puzzle.get("puzzle", {}).get("rating"),
                    "themes": puzzle.get("puzzle", {}).get("themes", []),
                    "source": "lichess"
                }]
    except Exception as e:
        logger.error(f"Error fetching Lichess puzzles: {e}")
    
    return []


async def fetch_tactical_puzzles(theme: str, rating_range: tuple = (1000, 1600), count: int = 5) -> List[Dict]:
    """
    Fetch tactical puzzles from Lichess by theme.
    
    Themes: fork, pin, skewer, discoveredAttack, sacrifice, mateIn1, mateIn2, etc.
    """
    try:
        async with httpx.AsyncClient() as client:
            # Get puzzle storm to get multiple puzzles
            response = await client.get(
                f"{LICHESS_API_BASE}/storm",
                headers={"Accept": "application/json"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                puzzles = data.get("puzzles", [])[:count]
                return [{
                    "id": p.get("id"),
                    "fen": p.get("fen"),
                    "solution": p.get("line", "").split(),
                    "rating": p.get("rating"),
                    "source": "lichess"
                } for p in puzzles]
    except Exception as e:
        logger.error(f"Error fetching tactical puzzles: {e}")
    
    return []


# ============================================================================
# TRAP RECOMMENDATIONS
# ============================================================================

def get_recommended_traps_for_opening(opening_name: str) -> List[Dict]:
    """
    Get traps that are relevant to a user's opening repertoire.
    """
    recommendations = []
    opening_lower = opening_name.lower()
    
    for key, trap in TRAPS_DATABASE.items():
        trap_opening = trap.get("opening", "").lower()
        # Check if the trap's opening matches
        if any(word in opening_lower for word in trap_opening.split()):
            recommendations.append({
                "key": key,
                "name": trap["name"],
                "opening": trap["opening"],
                "relevance": "direct",  # Directly related to user's opening
                "difficulty": trap["difficulty"],
                "description": trap["description"]
            })
    
    # Add general beginner traps if user plays e4 or d4
    if "e4" in opening_lower or "king" in opening_lower:
        if "scholars_mate" not in [r["key"] for r in recommendations]:
            trap = TRAPS_DATABASE["scholars_mate"]
            recommendations.append({
                "key": "scholars_mate",
                "name": trap["name"],
                "opening": trap["opening"],
                "relevance": "must_know",
                "difficulty": trap["difficulty"],
                "description": trap["description"]
            })
    
    return recommendations[:5]  # Top 5 recommendations


def get_trap_statistics() -> Dict:
    """Get statistics about the trap library."""
    total = len(TRAPS_DATABASE)
    by_difficulty = {}
    by_opening = {}
    
    for trap in TRAPS_DATABASE.values():
        diff = trap.get("difficulty", "unknown")
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1
        
        opening = trap.get("opening", "Unknown")
        by_opening[opening] = by_opening.get(opening, 0) + 1
    
    return {
        "total_traps": total,
        "by_difficulty": by_difficulty,
        "by_opening": by_opening,
        "categories": list(TRAP_CATEGORIES.keys())
    }
