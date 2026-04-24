"""
Cross-Game Repeat Mistake Detector
===================================

Finds mistake patterns that recur across a user's games — the "you've
done this in 4 different games" signal a human coach would catch.

Bucketing: (cognitive_gap, piece_letter, phase). If the same signature
appears in ≥ 3 distinct games, it becomes a repeat pattern worth naming.

Example outputs:
  - "You've hung your queen in 4 games."
  - "You've missed knight tactics in 3 different middlegames."
  - "Your king has gotten trapped in 3 endgames."

Different from the decay model, which counts raw cognitive_gap occurrences
without piece or game granularity. This one names the specific pattern
tighter — "your queen" vs "piece safety in general."
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MIN_GAMES_FOR_PATTERN = 3

# Pretty names for piece letters (extracted from played-move SAN)
PIECE_NAMES = {
    "Q": "your queen",
    "R": "a rook",
    "B": "a bishop",
    "N": "a knight",
    "K": "your king",
    "P": "a pawn",
}

PHASE_LABELS = {
    "opening": "in the opening",
    "middlegame": "in the middlegame",
    "endgame": "in the endgame",
}

GAP_VERB_PHRASES = {
    "piece_safety": "hung",
    "missed_tactic": "missed tactics with",
    "tactical_oversight": "missed opponent threats against",
    "calculation_depth": "miscalculated with",
    "king_safety": "put your king in trouble with",
    "ignore_threat": "ignored a threat against",
    "pawn_structure": "weakened pawn structure with",
    "piece_activity": "left inactive",
    "opening_knowledge": "misplayed",
    "endgame_technique": "mishandled",
}


def _piece_letter_of_move(san: str) -> str:
    """First uppercase letter of the SAN = piece type. Pawn moves have no
    piece letter (start with lowercase) — return 'P'. Castling returns 'K'."""
    if not san:
        return ""
    s = san.strip()
    if s.startswith("O-O"):
        return "K"
    return s[0] if s[0].isupper() else "P"


# python-chess piece_type → SAN letter
_PIECE_TYPE_TO_LETTER = {
    1: "P",  # PAWN
    2: "N",  # KNIGHT
    3: "B",  # BISHOP
    4: "R",  # ROOK
    5: "Q",  # QUEEN
    6: "K",  # KING
}

# Material values used for the "trade, not hang" check. Standard values.
_PIECE_VALUE = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 1000}


def _hung_piece_letter_after_move(fen_before: str, move_uci: str) -> Optional[str]:
    """Return the SAN letter of the most-valuable piece the played move
    genuinely left hanging. "Genuinely" = after netting out what the
    move itself captured.

    Why the netting matters: if the move was Qxg5 capturing a queen,
    the user's queen is now sitting on g5 possibly attacked by a pawn
    — but the *net material* of the whole trade is even. That's not a
    hang, it's a trade. A naive "attacked + undefended" check would
    mis-classify these as piece-hangs. This is what caused the
    "you hung your queen" reports on forced queen trades.

    Returns None when no piece is genuinely hung.
    """
    if not fen_before or not move_uci or len(move_uci) < 4:
        return None
    try:
        import chess
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(move_uci)
        if mv not in board.legal_moves:
            return None

        # What did we capture, if anything? This OFFSETS a hang loss.
        captured_piece = board.piece_at(mv.to_square)
        captured_value = (
            _PIECE_VALUE.get(captured_piece.piece_type, 0) if captured_piece else 0
        )
        # En passant — the captured pawn is on a different square.
        if board.is_en_passant(mv):
            captured_value = _PIECE_VALUE[1]  # pawn

        board.push(mv)
        user_color = not board.turn
        worst_victim_letter = None
        worst_net_loss = 0  # strictly positive means real net loss (hang)

        for sq, piece in board.piece_map().items():
            if piece.color != user_color or piece.piece_type == chess.KING:
                continue
            attackers = board.attackers(not user_color, sq)
            if not attackers:
                continue
            victim_value = _PIECE_VALUE.get(piece.piece_type, 0)
            defenders = board.attackers(user_color, sq)
            cheapest_attacker = min(
                (_PIECE_VALUE.get(board.piece_at(a).piece_type, 0) for a in attackers),
                default=0,
            )

            # Estimate what opponent gains by capturing. Undefended =
            # opponent gets victim_value clean. Defended but attacker
            # worth >= victim = we recapture, net victim vs attacker;
            # opponent would only take if trade is favorable for them.
            if not defenders:
                gross_loss = victim_value
            else:
                # Simplified SEE: if attacker < victim, opponent wins
                # (victim - attacker) material after we recapture.
                # If attacker >= victim, they wouldn't voluntarily trade
                # (and we wouldn't see this as a hang).
                if cheapest_attacker < victim_value:
                    gross_loss = victim_value - cheapest_attacker
                else:
                    continue  # not a hang — trade is bad for opponent

            # Offset by what WE captured on this move (trade balancing).
            net_loss = gross_loss - captured_value
            if net_loss <= 0:
                continue  # even or favorable — not a hang

            # Track the worst net-loss; pick that piece as the headline.
            if net_loss > worst_net_loss:
                worst_net_loss = net_loss
                worst_victim_letter = _PIECE_TYPE_TO_LETTER.get(piece.piece_type)

        return worst_victim_letter
    except Exception:
        return None


def _phase_from_move_number(move_number: int) -> str:
    if move_number <= 10:
        return "opening"
    if move_number <= 25:
        return "middlegame"
    return "endgame"


def _build_headline(gap: str, piece_letter: str, phase: str, occurrences: int) -> str:
    """Coach-voice headline naming the specific recurrence."""
    piece_name = PIECE_NAMES.get(piece_letter, "material")
    verb = GAP_VERB_PHRASES.get(gap, "kept making this mistake with")
    phase_clause = PHASE_LABELS.get(phase, "")
    games_word = "game" if occurrences == 1 else "games"

    # Assemble coach-voice sentence. For piece_safety + queen we want
    # "You've hung your queen in 4 games" — not "You've hung your queen
    # in the middlegame in 4 games."
    # For patterns that vary only in phase, include the phase clause.
    if gap == "piece_safety":
        return f"You've hung {piece_name} in {occurrences} {games_word}."
    if gap == "king_safety":
        return f"Your king has been in trouble {phase_clause} in {occurrences} {games_word}."
    if gap in ("missed_tactic", "tactical_oversight"):
        return f"You've {verb} {piece_name} in {occurrences} different {games_word}."
    # Default
    return f"You've {verb} {piece_name} {phase_clause} in {occurrences} {games_word}."


async def get_user_repeat_mistakes(db, user_id: str) -> Dict:
    """
    Walk all analyzed games for `user_id`, bucket critical moves by
    (cognitive_gap, piece_letter, phase), return patterns that recur in
    ≥ MIN_GAMES_FOR_PATTERN distinct games.

    Returns:
      has_data: bool
      top_pattern: dict | None   — the most-recurring pattern
      all_patterns: list of patterns sorted by occurrences desc
      total_games_analyzed: int
    """
    empty = {
        "has_data": False,
        "top_pattern": None,
        "all_patterns": [],
        "total_games_analyzed": 0,
    }

    # Pull analyzed games with move_evaluations (only the fields we need)
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "user_color": 1, "result": 1, "imported_at": 1},
    ).to_list(500)
    if not games:
        return empty

    game_ids = [g["game_id"] for g in games if g.get("game_id")]

    # Pull analyses
    analyses = {}
    async for a in db.game_analyses.find(
        {"user_id": user_id, "game_id": {"$in": game_ids}},
        {
            "_id": 0,
            "game_id": 1,
            "stockfish_analysis.move_evaluations.move": 1,
            "stockfish_analysis.move_evaluations.move_uci": 1,
            "stockfish_analysis.move_evaluations.cp_loss": 1,
            "stockfish_analysis.move_evaluations.fen_before": 1,
            "stockfish_analysis.move_evaluations.cognitive_gap": 1,
            "stockfish_analysis.move_evaluations.move_number": 1,
        },
    ):
        analyses[a["game_id"]] = a

    game_meta = {g["game_id"]: g for g in games if g.get("game_id")}

    # Signature: (cognitive_gap, piece_letter, phase) → set of game_ids
    buckets: Dict[tuple, set] = defaultdict(set)
    # Also track game metadata for each signature's first-seen example
    example_games: Dict[tuple, List[Dict]] = defaultdict(list)

    for game_id, analysis in analyses.items():
        g_meta = game_meta.get(game_id)
        if not g_meta:
            continue
        user_color = (g_meta.get("user_color") or "white").lower()
        user_is_white = user_color == "white"

        sf = analysis.get("stockfish_analysis") or {}
        for ev in sf.get("move_evaluations") or []:
            # Determine whose move (fen-based)
            fen = ev.get("fen_before") or ""
            parts = fen.split(" ")
            side = parts[1] if len(parts) > 1 else ""
            if side in ("w", "b"):
                is_user = (side == "w") == user_is_white
            else:
                continue  # skip if we can't tell
            if not is_user:
                continue

            cp_loss = ev.get("cp_loss") or 0
            if cp_loss < 100:
                continue  # only real mistakes

            gap = ev.get("cognitive_gap") or ""
            if not gap:
                continue

            san = ev.get("move") or ""
            move_number = ev.get("move_number") or 0
            phase = _phase_from_move_number(move_number)

            # For piece_safety, the piece that matters is the one ACTUALLY
            # left hanging — which is often different from the moving
            # piece. Recompute from the position. If the post-move scan
            # finds no real hang (e.g., forced trade, defended piece,
            # lower-value attacker), this move is NOT a genuine piece_safety
            # incident — drop it rather than mislabel it.
            if gap == "piece_safety":
                hung_letter = _hung_piece_letter_after_move(
                    ev.get("fen_before") or "",
                    ev.get("move_uci") or "",
                )
                if not hung_letter:
                    continue  # classifier mis-fired on a trade; skip
                piece_letter = hung_letter
            else:
                piece_letter = _piece_letter_of_move(san)

            sig = (gap, piece_letter, phase)
            buckets[sig].add(game_id)
            if len(example_games[sig]) < 5:
                example_games[sig].append({
                    "game_id": game_id,
                    "move_number": move_number,
                    "san": san,
                    "cp_loss": cp_loss,
                    "imported_at": str(g_meta.get("imported_at") or ""),
                    "result": g_meta.get("result"),
                })

    # Keep only signatures that recur in ≥ MIN_GAMES_FOR_PATTERN distinct games
    patterns = []
    for sig, game_set in buckets.items():
        occurrences = len(game_set)
        if occurrences < MIN_GAMES_FOR_PATTERN:
            continue
        gap, piece_letter, phase = sig
        patterns.append({
            "cognitive_gap": gap,
            "piece_letter": piece_letter,
            "phase": phase,
            "occurrences": occurrences,
            "example_games": example_games[sig],
            "headline": _build_headline(gap, piece_letter, phase, occurrences),
            "training_weakness": gap,  # routes to /training/prescribed?weakness=<gap>
        })

    patterns.sort(key=lambda p: (-p["occurrences"], -len(p["example_games"])))

    return {
        "has_data": bool(patterns),
        "top_pattern": patterns[0] if patterns else None,
        "all_patterns": patterns,
        "total_games_analyzed": len(analyses),
    }
