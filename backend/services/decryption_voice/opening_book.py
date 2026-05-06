"""
Deterministic opening recognizer. Matches a position's recent move
sequence against a curated table of named openings and returns a short
caption describing what's happening.

Replaces V5's opening detection which was buggy (called King's Gambit
"Réti Opening", flagged Caro-Kann c6 as a mistake, etc.).

This is a small, focused database — ~25 of the most common openings
played at 600-1500 rating. Not exhaustive. Future work: load from
ECO database for full coverage.

Each opening entry has:
  moves: list of SAN moves matching the position's history
  name: canonical opening name
  caption: 1-2 sentence Indian English explanation of the idea

Voice: same as templates — short SVO, plain words, names pieces and
ideas, never engine-speak.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import chess

logger = logging.getLogger(__name__)


# (move_sequence, name, caption_for_player_who_played_last_move)
# Move sequences are SAN. Match is by exact prefix on the game's
# move history.

_OPENINGS = [
    # === e4 e5 family ===
    {
        "moves": ["e4", "e5", "Nf3", "Nc6", "Bb5"],
        "name": "ruy_lopez",
        "caption": "Ruy Lopez (Spanish Opening). The bishop pins the knight against the king and pressures e5 indirectly.",
    },
    {
        "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"],
        "name": "italian_game",
        "caption": "Italian Game. The bishop on c4 eyes f7, the weakest square in Black's camp.",
    },
    {
        "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"],
        "name": "italian_giuoco_piano",
        "caption": "Giuoco Piano. Both sides develop bishops to attacking diagonals; play stays calm for now.",
    },
    {
        "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"],
        "name": "italian_two_knights",
        "caption": "Two Knights Defense. Black develops actively and challenges White's plans.",
    },
    {
        "moves": ["e4", "e5", "f4"],
        "name": "kings_gambit",
        "caption": "King's Gambit. White offers a pawn to undermine Black's centre and seek rapid attack.",
    },
    {
        "moves": ["e4", "e5", "f4", "exf4"],
        "name": "kings_gambit_accepted",
        "caption": "King's Gambit Accepted. Black takes the pawn, accepting an open game with both sides developing fast.",
    },
    {
        "moves": ["e4", "e5", "Nf3", "Nf6"],
        "name": "petrov_defense",
        "caption": "Petrov's Defense. Black mirrors White's threat — attacks the e4 pawn instead of defending e5.",
    },
    # === Sicilian family ===
    {
        "moves": ["e4", "c5"],
        "name": "sicilian",
        "caption": "Sicilian Defense. Black plays asymmetrically — fights for the centre with a c-pawn instead of e-pawn.",
    },
    {
        "moves": ["e4", "c5", "Nf3", "d6"],
        "name": "sicilian_najdorf_or_classical",
        "caption": "Sicilian, classical setup. Black prepares a flexible kingside with ...Nf6 and ...e6 or ...g6.",
    },
    {
        "moves": ["e4", "c5", "Nf3", "Nc6"],
        "name": "sicilian_open",
        "caption": "Open Sicilian. Aggressive, sharp positions. Both sides aim for active piece play.",
    },
    # === Caro-Kann ===
    {
        "moves": ["e4", "c6"],
        "name": "caro_kann",
        "caption": "Caro-Kann Defense. Black prepares ...d5 to challenge the centre with a solid pawn structure.",
    },
    {
        "moves": ["e4", "c6", "d4", "d5"],
        "name": "caro_kann_main",
        "caption": "Caro-Kann main line. Black challenges the centre and prepares safe development of the c8 bishop.",
    },
    # === French ===
    {
        "moves": ["e4", "e6"],
        "name": "french_defense",
        "caption": "French Defense. Black prepares ...d5 with a slightly cramped but solid structure.",
    },
    # === Scandinavian ===
    {
        "moves": ["e4", "d5"],
        "name": "scandinavian",
        "caption": "Scandinavian Defense. Black challenges White's centre immediately on move 1.",
    },
    # === d4 family ===
    {
        "moves": ["d4", "d5"],
        "name": "queens_pawn",
        "caption": "Queen's Pawn Game. Both sides claim central pawns and prepare slow positional play.",
    },
    {
        "moves": ["d4", "d5", "c4"],
        "name": "queens_gambit",
        "caption": "Queen's Gambit. White offers a c-pawn to deflect Black's d-pawn and dominate the centre.",
    },
    {
        "moves": ["d4", "d5", "c4", "dxc4"],
        "name": "queens_gambit_accepted",
        "caption": "Queen's Gambit Accepted. Black grabs the pawn but White will recover it with active development.",
    },
    {
        "moves": ["d4", "d5", "c4", "e6"],
        "name": "queens_gambit_declined",
        "caption": "Queen's Gambit Declined. Black holds the centre with a solid pawn chain.",
    },
    {
        "moves": ["d4", "Nf6"],
        "name": "indian_defenses",
        "caption": "Indian Defense setup. Black delays committing pawns to the centre and develops pieces first.",
    },
    {
        "moves": ["d4", "Nf6", "c4", "g6"],
        "name": "kings_indian",
        "caption": "King's Indian Defense. Black gives up the centre temporarily and plans a kingside counter-attack.",
    },
    # === English / Reti ===
    {
        "moves": ["c4"],
        "name": "english_opening",
        "caption": "English Opening. White controls d5 and e5 from the side — a flexible, positional start.",
    },
    {
        "moves": ["Nf3"],
        "name": "reti",
        "caption": "Réti Opening. White develops without committing pawns — flexible, can transpose to many systems.",
    },
    # === Less common but recognizable ===
    {
        "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "b4"],
        "name": "evans_gambit",
        "caption": "Evans Gambit. White sacrifices a pawn to deflect the c5 bishop and seize the centre with c3 + d4.",
    },
    {
        "moves": ["e4", "e5", "Bc4"],
        "name": "bishops_opening",
        "caption": "Bishop's Opening. White develops the bishop early before committing the king's knight.",
    },
    {
        "moves": ["e4", "Nc6"],
        "name": "nimzowitsch_defense",
        "caption": "Nimzowitsch Defense. Black develops the queen's knight first — flexible and slightly offbeat.",
    },
]


def _game_history_san(board: chess.Board, last_played_san: str) -> List[str]:
    """Reconstruct the SAN move history of the position by walking the
    move stack. We're given the position BEFORE the last move and the
    last move's SAN."""
    history = []
    if not board.move_stack:
        # Reconstruct from popping moves
        return []
    # Walk via copy + pop
    b = board.copy()
    while b.move_stack:
        b.pop()
    for mv in board.move_stack:
        try:
            history.append(b.san(mv))
            b.push(mv)
        except Exception:
            break
    history.append(last_played_san)
    return history


def recognize_opening_from_history(
    history: List[str],
) -> Optional[Dict]:
    """Match a SAN move sequence (full history INCLUDING the just-played
    move) against the curated opening table. Returns the longest match
    whose final move equals the last entry in history (so the caption
    fires on the move that completes the opening name)."""
    if not history:
        return None
    last_played_san = history[-1]

    best_match = None
    best_match_len = 0
    for entry in _OPENINGS:
        moves = entry["moves"]
        if len(moves) > len(history):
            continue
        if history[: len(moves)] != moves:
            continue
        if moves[-1] != last_played_san:
            continue
        if len(moves) > best_match_len:
            best_match = entry
            best_match_len = len(moves)

    if not best_match:
        return None
    return {
        "name": best_match["name"],
        "caption": best_match["caption"],
        "match_length": best_match_len,
    }


def recognize_opening(
    board_before: chess.Board,
    last_played_san: str,
) -> Optional[Dict]:
    """Back-compat: reconstruct history from board_before.move_stack +
    last_played_san. Only works when the board has a populated stack
    (e.g., during interactive play). For analysis-page use, prefer
    recognize_opening_from_history with explicit history."""
    history = _game_history_san(board_before, last_played_san)
    return recognize_opening_from_history(history)
