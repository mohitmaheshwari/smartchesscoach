"""Did the player win, lose or draw? One answer, read against their colour.

Games store `result` as "1-0" / "0-1" / "1/2-1/2" -- never as prose -- so the
outcome is meaningless without `user_color`. That pairing has been restated
inline in at least six places (active_teaching_engine, conversational_coach,
data_freshness, coach_selected_review_service, time_management_service, and
the first-session game picker in routes/journey.py), and the picker got it
wrong: it matched "0-1" as a loss for everybody, so a Black player's WIN was
selected as the game to learn from and their actual loss was invisible.

Measured across every production user with games, that picker opened the first
session on a game the player had WON for 32 of 69 users (46.4%).

Import from here rather than writing the comparison again.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

WIN = "win"
LOSS = "loss"
DRAW = "draw"
UNKNOWN = "unknown"

_DRAW_TOKENS = {"1/2-1/2", "½-½", "draw", "d", "drew"}
_WIN_TOKENS = {"win", "won", "w"}
_LOSS_TOKENS = {"loss", "lost", "l"}


def _is_white(game: Mapping[str, Any]) -> Optional[bool]:
    colour = str(game.get("user_color") or "").strip().lower()
    if colour.startswith("w"):
        return True
    if colour.startswith("b"):
        return False
    return None


def user_outcome(game: Mapping[str, Any]) -> str:
    """Return "win" / "loss" / "draw" / "unknown" from the player's side.

    "unknown" is returned rather than a guess when the colour is missing or
    the result is unfinished ("*"), because a wrong outcome silently picks the
    wrong game to coach from.
    """
    raw = str(game.get("result") or "").strip().lower()
    if not raw or raw == "*":
        return UNKNOWN
    if raw in _DRAW_TOKENS:
        return DRAW
    # Some records store the outcome already resolved to the player's side.
    if raw in _WIN_TOKENS:
        return WIN
    if raw in _LOSS_TOKENS:
        return LOSS

    white = _is_white(game)
    if white is None:
        return UNKNOWN
    if raw == "1-0":
        return WIN if white else LOSS
    if raw == "0-1":
        return LOSS if white else WIN
    return UNKNOWN


def user_lost(game: Mapping[str, Any]) -> bool:
    return user_outcome(game) == LOSS


def user_won(game: Mapping[str, Any]) -> bool:
    return user_outcome(game) == WIN
