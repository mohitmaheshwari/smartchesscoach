"""The trap judge: a board-reading agent confirms each trap the finder proposes.

Scope: docs/trap_lesson_from_games_scope.md, section 8 (Mohit, 2026-11-17: "do
what you recommend, you know what chessguru is supposed to become"). Four
board-and-engine rules reached 56-87% precision against two independent board
grades (60 positions); the graders' own method -- set up each board, compare
the move with the alternatives, ask whether the threat existed before the
offer -- is what separated traps from slips. So the finder only proposes, and
this judge decides. Nothing reaches a card or Home unless the judge says TRAP,
and the judge decides nothing live until it agrees with the graders' labels
(scripts/trap_judge_calibrate.py).

The standing rule "the LLM writes English, never chess" is bent here the way
the why queue bends it: the judge reads positions with Stockfish and a board
tool, and its verdict is held to a measured agreement bar, not trusted.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import chess

VERDICTS = ("TRAP", "SLIP", "WRONG_RECAPTURE", "UNRELATED", "OTHER", "UNCLEAR")

SYSTEM_PROMPT = """You are a strict chess coach deciding whether a player fell into a TRAP.

A TRAP: the opponent deliberately offered something (put a piece or pawn where it can be taken,
left one without its guard on purpose, or sacrificed material to get a check or an attack), the
player's move TAKES what was offered (or answers the check that follows the sacrifice), and that is
exactly why it loses: the punishment exists because of what the offer set up (a fork, a deflection,
a trapped piece, an attack, mate). A teacher would show it as "they set a trap and you walked in".
The bait may be objectively unsound; that is fine.

NOT a trap:
- SLIP: the opponent simply blundered and the player failed to punish it; the offer was a mistake,
  not bait.
- WRONG_RECAPTURE: a normal trade where the player recaptured with the wrong piece and nothing was
  baited.
- UNRELATED: the player's move loses for a reason that has nothing to do with the offer, or the
  punishment was already on the board before the offer.
- OTHER: anything else, including a missed threat where taking lost no more than other moves that
  ignored the threat.
- UNCLEAR: you cannot tell from the board and the engine.

Method, every time:
1. Look at the position before the offer (board tool, then analyse). Was the punishment already
   there? If the same winning idea existed before the offer, it is UNRELATED.
2. Look at the position before the player's move. Analyse it with several lines. Compare the
   player's move with the best move that does NOT take, and with the "pass" position given (the
   same position with the opponent to move), when there is one.
3. If taking lost no more than the other moves that ignore the threat, the capture did not cause
   the loss: OTHER.
4. If the opponent's offer simply threw material away with no follow-up, it is a SLIP.
5. Only if the offer set up a punishment that taking the bait walks into: TRAP.

Use the tools; never trust a line you have not checked. Answer in the JSON schema. `evidence` is one
plain sentence of board facts. For a TRAP also fill `offer` (what was offered, piece and square),
`punishment` (what taking it allows, in plain words) and `holds` (the move that keeps the position).
"""

SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "evidence": {"type": "string"},
        "offer": {"type": "string"},
        "punishment": {"type": "string"},
        "holds": {"type": "string"},
    },
    "required": ["verdict", "evidence"],
}

TOOLS_NOTE = ("\n\nTools: mcp__chess__board (a position as text: board, material, checks, legal moves, "
              "pieces attacked with no guard) and mcp__chess__analyse (Stockfish lines). Both take a FEN "
              "and optional SAN moves to play first.")


def pass_fen(fen: str) -> Optional[str]:
    """The same position with the other side to move; None when a pass is illegal."""
    board = chess.Board(fen)
    if board.is_check():
        return None
    board.push(chess.Move.null())
    fresh = chess.Board(board.fen())
    return fresh.fen() if fresh.is_valid() else None


def packet(case: Dict[str, Any]) -> str:
    """The user message for one candidate. Moves and positions only: no names."""
    lines = [
        f"The player has {case['player_color']}.",
        f"Position before the opponent's offer (opponent to move): {case['before_offer_fen']}",
        f"The opponent's offer: {case['offer_san']}"
        + (" (then each side made one more move)" if case.get("offer_moves_back") == 2 else ""),
        f"Position before the player's move (player to move): {case['before_move_fen']}",
        f"The player's move: {case['move_san']}",
        f"Stockfish's better move: {case.get('best_san')}",
        f"Stockfish's line after the player's move: {' '.join(case.get('line_san') or [])}",
    ]
    pf = pass_fen(case["before_move_fen"])
    lines.append(f"Pass position (same position, opponent to move): {pf}" if pf else
                 "Pass position: none, the player is in check.")
    return "\n".join(lines)


def parse(answer: Dict[str, Any]) -> Dict[str, Any]:
    verdict = str(answer.get("verdict") or "UNCLEAR").upper()
    if verdict not in VERDICTS:
        verdict = "UNCLEAR"
    return {"verdict": verdict, "evidence": answer.get("evidence"), "offer": answer.get("offer"),
            "punishment": answer.get("punishment"), "holds": answer.get("holds")}
