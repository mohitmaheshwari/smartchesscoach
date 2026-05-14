"""
Test LLM caption generation on N games (default 1).

Loads existing decryption_v5_data from game_analyses, extracts facts per
move, and (when there's a teaching signal) sends to gpt-4o-mini through
call_llm with:
  - Coach Voice rules (services/coach_voice_prompt.py)
  - The 28 caption principle catalog (services/caption_principles.py)
  - The 23 shape pattern catalog (services/shape_patterns.py)

Per-move gate: if facts contain no best_move-difference, no shape
pattern, no principles, and severity is non-teaching ("good"/"context"),
the LLM is never called for that move — empty caption returned. This
stops the model from hallucinating on quiet positions.

Retry-with-backoff handles 429 rate-limit errors transparently.

Does NOT touch production data. Writes a side-by-side markdown report.

Usage:
    docker exec -it chess-coach-backend python scripts/test_llm_captions.py
    docker exec -it chess-coach-backend python scripts/test_llm_captions.py --n 10 --source queue
    docker exec -it chess-coach-backend python scripts/test_llm_captions.py --n 5 --source random --output /tmp/llm_test.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

from llm_service import call_llm
from services.coach_voice_prompt import with_coach_voice
from services.shape_patterns import SHAPE_PATTERNS
from services.caption_principles import PRINCIPLES

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

TEACHING_SEVERITIES = {"mistake", "blunder", "opp_mistake", "opp_blunder"}


def build_principle_catalog_block() -> str:
    """The 28 named teaching principles, condensed for the LLM prompt.

    Sends `id`, `name`, `phase_in_scope`, and `cue_top_n` (the standard
    coach-voice line for when this principle fires). The LLM uses these
    names verbatim; it must not invent new ones.
    """
    lines = [
        "TEACHING PRINCIPLES — use these NAMES verbatim. Do not invent new principle names.",
        "Each entry: name | phases | example coach line.",
        "",
    ]
    for p in PRINCIPLES:
        phases = ",".join(p.get("phase_in_scope") or [])
        cue = (p.get("cue_top_n") or p.get("cue_best") or "").strip()
        lines.append(f"- {p['name']} ({p['id']}) [{phases}] — e.g. \"{cue}\"")
    return "\n".join(lines)


def build_shape_catalog_block() -> str:
    """The 23 named shape patterns the coach can call out on the board."""
    lines = [
        "SHAPE PATTERNS — use these NAMES verbatim when the facts say one is present.",
        "Each entry: name | description.",
        "",
    ]
    for s in SHAPE_PATTERNS:
        lines.append(f"- {s['name']} — {s['description']}")
    return "\n".join(lines)


# Tightened prompt v2:
# - Forbidden phrases moved to top (was rule #6, now rule #1+#2).
# - Explicit "Good move!" / "Nice!" ban (anti-pattern from v1 output).
# - Explicit "if facts give nothing concrete → empty" reinforcement with example.
# - Anti-hallucination: only use squares/pieces/moves from facts JSON.
CAPTION_TASK_PROMPT = """You write ONE-SENTENCE captions for chess moves, for players rated 600-1500.

You receive a facts dict about ONE move. Your only job: find a TEACHING IDEA grounded in those facts.

═════ NEVER DO THESE — each one fails the task ═════

A. NEVER end with advice: "focus on...", "try to...", "in future games...", "consider...", "watch for...", "castle soon", "remember to...", "be careful with...".
B. NEVER use generic praise: "Good move!", "Nice!", "Great move!", "Well done!", "Excellent!". Praise must name a specific principle or shape pattern from the catalogs.
C. NEVER name a square, piece, or move that is NOT in the facts dict. If facts don't say "d1", you must not write "d1".
D. NEVER invent a principle or shape pattern not in the catalogs (no "outpost", "luft", "minority attack", "controls", "repositions", "weak squares", "strong attack").
E. NEVER use engine words: cp, eval, evaluation, centipawn, accuracy, %.
F. NEVER say "this move" — name the move (e.g. "Nf3", not "this move").

═════ WHAT TO WRITE ═════

ONE sentence, max 18 words.

Use the facts to choose ONE of these three teaching frames:

1. Mistake/blunder critique — if severity is mistake/blunder/opp_mistake/opp_blunder, OR principles_present is non-empty, OR shape_pattern is present and was missed by played move.
   Form: "{played_move} {what went wrong using a principle/shape name}. {best_move} {what it does}."
   Example: "Nd5 was sharper here — Nf3 gives up the center."

2. Best-move teaching — if played move is fine (severity good/context, cp_loss low) BUT best_move differs AND a principle/shape applies to the best move.
   Form: "Decent — {best_move} {what it does using a principle/shape name}."
   Example: "Decent — Qg4+ sets up the Skewer."

3. Specific praise — if played move applied a named principle/shape (catalog has the name).
   Form: "{played_move} {names the principle/shape that fires}."
   Example: "Qg5 — clean Knight Fork on the queen and rook."

═════ EMPTY OUTPUT RULE — STRICT ═════

If ALL of these are true, output an empty string (single space, nothing else):
  - principles_present is [] or null AND
  - shape_pattern is null AND
  - severity is not mistake/blunder/opp_mistake/opp_blunder AND
  - best_move is missing or equal to move_played

Examples that MUST be empty:
  - opponent quiet move with no facts → empty
  - forced recapture → empty
  - any move where you'd have to invent a chess idea to fill the caption → empty

Better silence than a generic line.

═════ OUTPUT ═════

Just the sentence text. No labels, no quotes, no JSON. Empty allowed."""


def has_teaching_signal(move: Dict[str, Any]) -> bool:
    """Decide whether to even call the LLM. Hard gate on hallucination."""
    if move.get("shape_pattern_name"):
        return True
    if move.get("caption_facts_principles_violated"):
        return True
    if move.get("severity") in TEACHING_SEVERITIES:
        return True
    best = move.get("best_move_san")
    played = move.get("move_san")
    if best and played and best != played:
        return True
    return False


def build_move_facts(move: Dict[str, Any]) -> Dict[str, Any]:
    """The compact facts dict sent to the LLM. No FEN. No PV. Just facts."""
    pids = [p.get("principle_id") for p in (move.get("caption_facts_principles_violated") or []) if p]
    facts = {
        "move_played": move.get("move_san"),
        "move_number": move.get("move_number"),
        "is_user_move": move.get("is_user_move"),
        "phase": move.get("phase"),
        "opening_name": move.get("opening_name"),
        "best_move": move.get("best_move_san"),
        "severity": move.get("severity"),
        "cp_loss": move.get("cp_loss"),
        "principles_present": pids,
    }
    if move.get("shape_pattern_name"):
        facts["shape_pattern"] = {
            "name": move["shape_pattern_name"],
            "description": move.get("shape_pattern_desc"),
            "mover": move.get("shape_pattern_mover"),
            "targets": move.get("shape_pattern_targets") or [],
            "executing_move": move.get("shape_pattern_executing_move"),
        }
    return facts


def _retry_seconds_from_error(err_text: str) -> Optional[float]:
    """OpenAI 429 messages embed 'Please try again in X.YYYs'. Extract it."""
    m = re.search(r"try again in ([\d.]+)s", err_text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


async def call_with_retry(sys_prompt: str, user_prompt: str, max_attempts: int = 4) -> str:
    """Call the LLM with retry-on-429. Backs off using the suggested wait
    if OpenAI tells us how long, otherwise exponential. Returns the
    response text, or '[ERROR: ...]' if all attempts failed.
    """
    last_err: Optional[Exception] = None
    delay = 2.0
    for attempt in range(1, max_attempts + 1):
        try:
            out = await call_llm(
                system_message=sys_prompt,
                user_message=user_prompt,
                model="gpt-4o-mini",
                max_tokens=80,
            )
            return (out or "").strip().strip('"').strip("'")
        except Exception as e:
            last_err = e
            err_text = str(e)
            if "rate_limit" in err_text or "429" in err_text:
                suggested = _retry_seconds_from_error(err_text)
                wait = suggested + 0.5 if suggested else delay
                print(f"[test] rate limit hit on attempt {attempt}/{max_attempts}, waiting {wait:.1f}s", file=sys.stderr)
                await asyncio.sleep(wait)
                delay = min(delay * 2, 30)
                continue
            return f"[ERROR: {e}]"
    return f"[ERROR after {max_attempts} attempts: {last_err}]"


async def generate_caption(move: Dict[str, Any], sys_prompt: str) -> str:
    if not has_teaching_signal(move):
        return ""  # hard gate — never call LLM on no-signal moves
    facts = build_move_facts(move)
    user_prompt = f"MOVE FACTS:\n{json.dumps(facts, indent=2)}\n\nWrite the caption."
    return await call_with_retry(sys_prompt, user_prompt)


def format_facts_inline(move: Dict[str, Any]) -> str:
    parts = []
    if move.get("best_move_san"):
        parts.append(f"best={move['best_move_san']}")
    if move.get("caption_facts_primary_reason"):
        parts.append(f"rule={move['caption_facts_primary_reason']}")
    if move.get("shape_pattern_name"):
        parts.append(f"shape={move['shape_pattern_name']}")
    pids = [p.get("principle_id") for p in (move.get("caption_facts_principles_violated") or []) if p]
    if pids:
        parts.append(f"principles={','.join(pids)}")
    return " | ".join(parts) or "(none)"


async def pick_games(db, n: int, source: str) -> List[Dict[str, str]]:
    if source == "queue":
        items = await db.authoring_queue.find(
            {},
            {"_id": 0, "game_id": 1, "bucket": 1, "order_in_round": 1},
        ).sort("order_in_round", 1).limit(n).to_list(n)
        if items:
            return items
        print("[test] authoring_queue empty — falling back to random sample", file=sys.stderr)

    items: List[Dict[str, str]] = []
    async for g in db.games.aggregate([
        {"$match": {"is_active": {"$ne": False}, "is_analyzed": True}},
        {"$sample": {"size": n}},
        {"$project": {"_id": 0, "game_id": 1}},
    ]):
        items.append({"game_id": g["game_id"], "bucket": "random"})
    return items


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1,
                    help="Number of games to test (default 1 — keep low until prompt is validated).")
    ap.add_argument("--source", choices=["queue", "random"], default="queue",
                    help="queue=use active authoring_queue (default), random=random sample")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    games = await pick_games(db, args.n, args.source)

    sys_prompt = with_coach_voice(
        CAPTION_TASK_PROMPT
        + "\n\n" + build_principle_catalog_block()
        + "\n\n" + build_shape_catalog_block()
    )

    totals = {"moves": 0, "called": 0, "gated": 0, "llm_empty": 0, "errors": 0}

    for idx, item in enumerate(games, 1):
        gid = item["game_id"]
        bucket = item.get("bucket", "?")

        print("")
        print("═" * 78)
        print(f"GAME {idx}/{len(games)}   game_id: {gid}   bucket: {bucket}")
        print(f"  open in UI:  /game/{gid}")
        print("═" * 78)

        analysis = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "decryption_v5_data": 1},
        )
        if not analysis or not analysis.get("decryption_v5_data"):
            print("  (no V5 data for this game)")
            continue

        moves = analysis["decryption_v5_data"]

        for m in moves:
            totals["moves"] += 1
            mv = m.get("move_san", "?")
            mn = m.get("move_number", "?")
            mover = "user" if m.get("is_user_move") else "opp "
            sev = (m.get("severity") or "?").ljust(13)

            if not has_teaching_signal(m):
                totals["gated"] += 1
                continue  # skip silently — no signal, no print

            totals["called"] += 1
            llm_caption = await generate_caption(m, sys_prompt)

            if not llm_caption:
                totals["llm_empty"] += 1
                tag = "[LLM-EMPTY]"
            elif llm_caption.startswith("[ERROR"):
                totals["errors"] += 1
                tag = "[ERROR]    "
            else:
                tag = "           "

            existing = (m.get("caption") or "").strip() or "(no existing)"
            print(f"\n  move {mn:>3}.{mv:<8}  {mover}  {sev}  {tag}")
            print(f"    existing : {existing}")
            print(f"    LLM      : {llm_caption or '(empty)'}")
            print(f"    facts    : {format_facts_inline(m)}")

    print("")
    print("─" * 78)
    print(
        f"moves={totals['moves']}  called={totals['called']}  "
        f"gated={totals['gated']}  llm_empty={totals['llm_empty']}  errors={totals['errors']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
