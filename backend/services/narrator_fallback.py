"""narrator_fallback.py — gold-quality why when detectors fail (2026-06-11).

When the deterministic R-rule pipeline produces NO real why for a flagged USER
mistake (empty caption, R_FALLBACK, R16 board-state filler, or a principle-bank
promotion), fetch a real coaching why from the terminal Claude gateway using the
validated why-rule prompt.

Design:
- SYNCHRONOUS. Captions are generated at analysis time (batch) and STORED; the
  user reads stored decryption_v5_data. So a blocking gateway call here never
  hits the live user path — no async machinery needed.
- CACHED (in-process, keyed by fen+move) so a re-render doesn't re-pay.
- CIRCUIT-BROKEN: after N consecutive gateway failures, stop calling for a
  cooldown so a dead tunnel doesn't slow every move.
- GRACEFUL: returns None on ANY failure -> caller keeps the deterministic
  caption. A flagged mistake never ends up worse than before.

Env: LLM_API_BASE, LLM_API_KEY (gateway). Absent -> disabled (returns None).
"""
import os
import time
import requests

_BASE = (os.environ.get("LLM_API_BASE") or "").rstrip("/")
_KEY = os.environ.get("LLM_API_KEY") or ""
_H = {
    "Authorization": f"Bearer {_KEY}",
    "ngrok-skip-browser-warning": "1",
    "Content-Type": "application/json",
}

# rule_name fragments that mean "no real detector why fired" -> narrator-eligible
_FALLBACK_MARKERS = (
    "R_FALLBACK",
    "R16_board_state",
    "R_PROMOTED_principle",
    "R_PROMOTED_opening_intro",
)

_FLAGGED_CP = 30  # codebase "good move" boundary; >=30 = flagged

# Generic/filler "why" template phrases. When a flagged move's caption leans on
# one of these (board-state describer / development count / floor principle), the
# detector produced no position-specific why -> route to the narrator. These are
# fixed templated strings (not fuzzy semantics), so matching is reliable.
import re as _re
_FILLER = _re.compile(
    r"(pieces are still on your side|pieces on the back rank|minor pieces on"
    r"|is passive|squeezed for space|pawn shelter|lost \d+ of|develop with a"
    r" follow-up|each piece should support|fix your worst piece|count attackers"
    r"|before any tactical|in the opening, develop|the [a-h]-file is open"
    r"|creates two threats|pieces doing one job|still have \d+|legal moves"
    r"|alone in opponent|attacks the center)",
    _re.I,
)

_cache = {}
_fail_count = 0
_circuit_open_until = 0.0
_CIRCUIT_THRESHOLD = 3
_CIRCUIT_COOLDOWN_S = 120.0

_PROMPT = """You are a chess coach writing a ONE or TWO sentence caption for a 1200-rated player about the move below. RULES:
- The move was flagged by the engine as a {evaluation}. You MUST explain WHY in plain, simple English (coaching tone) - what the move allows, abandons, or misses, and what was better.
- USE VERY EASY, EVERYDAY WORDS. Write like you are talking to a beginner. Short, common words only. Banned fancy words (and anything like them): strolls, evaporate, stranded, nudges, defuse, neutralize, contest, jeopardize. Use plain swaps: walks, go away, stuck, pushes, stop, fight for.
- Name concrete squares/pieces. No chess jargon.
- NEVER state a capture, target square, or follow-up move unless it is actually true on the board.
- Do not pad with generic principles. The why must fit THIS position.

Position (FEN): {fen}
Side to move: {side}
Move played: {move}  (engine says: {evaluation}, lost ~{cp}cp)
Engine's best instead: {best}
Engine line after best: {pv_best}
Engine line after the played move: {pv_played}

Write only the caption text, nothing else."""


def needs_narrator(caption, rule_name, cp_loss, is_user_move):
    """True when this flagged USER move has no real detector why and should be
    handed to the narrator."""
    if not is_user_move:
        return False
    if (cp_loss or 0) < _FLAGGED_CP:
        return False
    if not (caption or "").strip():
        return True
    rn = rule_name or ""
    if any(m in rn for m in _FALLBACK_MARKERS):
        return True
    # Detector fired a rule (e.g. R12) but the "why" is a generic-filler
    # template, not a position-specific reason -> route to the narrator.
    if _FILLER.search(caption):
        return True
    return False


def narrate_why(fen, move, evaluation, cp_loss, best, pv_best, pv_played,
                timeout_s=150):
    """Return a gold-quality why caption, or None on any failure (graceful)."""
    global _fail_count, _circuit_open_until
    if not _BASE or not _KEY:
        return None
    key = (fen, move)
    if key in _cache:
        return _cache[key]
    if time.time() < _circuit_open_until:
        return None
    try:
        side = "white" if (fen.split(" ")[1] == "w") else "black"
        q = _PROMPT.format(
            evaluation=evaluation or "mistake", fen=fen, side=side, move=move,
            cp=cp_loss or 0, best=best or "?",
            pv_best=" ".join(pv_best or [])[:120],
            pv_played=" ".join(pv_played or [])[:120],
        )
        r = requests.post(f"{_BASE}/ask", headers=_H,
                          json={"question": q, "provider": "claude",
                                "timeout_seconds": timeout_s}, timeout=30)
        r.raise_for_status()
        tid = r.json()["task_id"]
        deadline = time.time() + timeout_s + 40
        while time.time() < deadline:
            t = requests.get(f"{_BASE}/tasks/{tid}", headers=_H, timeout=15).json()
            st = t.get("status")
            if st == "done":
                cap = (t.get("answer") or "").strip()
                _cache[key] = cap or None
                _fail_count = 0
                return cap or None
            if st in ("error", "timeout"):
                raise RuntimeError(t.get("error"))
            time.sleep(3)
        raise TimeoutError("narrator poll timeout")
    except Exception:
        _fail_count += 1
        if _fail_count >= _CIRCUIT_THRESHOLD:
            _circuit_open_until = time.time() + _CIRCUIT_COOLDOWN_S
        return None
