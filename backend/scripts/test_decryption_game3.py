"""
Test runner — generate a real Decryption block for Game 3 (the mate walk).

This is the hardest case from the dump: cp_loss=19980, Rd8+ when Qc2#
was sitting there. If the Decryption Voice reads right on this game,
the rest will follow.

Run on the server (where the LLM key is set):
    docker compose exec backend python scripts/test_decryption_game3.py

Outputs to stdout — both the deterministic position-delta facts (so you
can verify the LLM has the right inputs) and the final validated
decryption text. No DB writes, no side effects.
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from services.decryption_voice.position_delta import (
    compute_position_delta, format_delta_for_prompt
)
from services.decryption_voice.decryption import generate_decryption
from services.decryption_voice.truth_line import generate_truth_line


# Game 3 from the dump — the mate walk.
# User color: black (per dump).
# DECISIVE 1: san=Rd8+ best=Qc2# cp_loss=19980 ply=? move_number=23
GAME3_FEN_BEFORE = "1r3k1r/5ppp/4p3/Q1b5/8/3KPP2/PP4qP/nNBR4 b - - 1 23"
GAME3_FEN_AFTER  = "3r1k1r/5ppp/4p3/Q1b5/8/3KPP2/PP4qP/nNBR4 w - - 2 24"
GAME3_MOVE_UCI   = "b8d8"  # rook from b8 to d8
GAME3_GAME_ID    = "6dfa3cb6-2a5b-48df-ba62-333a0b7e46e2"
GAME3_USER_COLOR = "black"


async def main() -> None:
    print("=" * 70)
    print("GAME 3 — MATE WALK")
    print("=" * 70)
    print(f"FEN before : {GAME3_FEN_BEFORE}")
    print(f"FEN after  : {GAME3_FEN_AFTER}")
    print(f"Move (UCI) : {GAME3_MOVE_UCI}  (Rd8+)")
    print(f"User color : {GAME3_USER_COLOR}")
    print(f"cp_loss    : 19980 (catastrophic — winning to lost)")
    print()

    # 1. Show the deterministic delta facts (the LLM's grounding).
    print("─" * 70)
    print("POSITION DELTA (the facts the LLM gets):")
    print("─" * 70)
    delta = compute_position_delta(
        GAME3_FEN_BEFORE, GAME3_FEN_AFTER, GAME3_MOVE_UCI, GAME3_USER_COLOR
    )
    if delta:
        print(format_delta_for_prompt(delta) or "(no facts extracted)")
    else:
        print("(delta extraction failed)")
    print()

    # 2. Show the Truth line for context (uses scenario classifier).
    print("─" * 70)
    print("TRUTH LINE (for context — independent of decryption):")
    print("─" * 70)
    truth = generate_truth_line(
        decryption_v5_data=[{
            "is_user_move": True,
            "is_mistake": True,
            "severity": "blunder",
            "cp_loss": 19980,
            "move_number": 23,
            "move_san": "Rd8+",
        }],
        game_reason="one_move_blunder",
        game_id=GAME3_GAME_ID,
    )
    if truth:
        print(f"  {truth['identity']}")
        print(f"  {truth['anchor']}")
        print(f"  {truth['trigger']}")
    print()

    # 3. The actual Decryption — calls the LLM, validates, retries, may
    #    fall back to template.
    print("─" * 70)
    print("DECRYPTION (the live LLM output):")
    print("─" * 70)
    result = await generate_decryption(
        fen_before=GAME3_FEN_BEFORE,
        fen_after=GAME3_FEN_AFTER,
        move_uci=GAME3_MOVE_UCI,
        user_color=GAME3_USER_COLOR,
    )
    if not result:
        print("(decryption returned None — see logs)")
        return
    print(result.text)
    print()
    print(f"[source={result.source}  attempts={result.attempts}]")
    print()
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
