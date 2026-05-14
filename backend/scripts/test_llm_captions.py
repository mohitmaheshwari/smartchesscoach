"""
Test LLM caption generation on N games (default 10).

Loads existing decryption_v5_data from game_analyses, extracts facts per
move, sends to gpt-4o-mini through call_llm with:
  - Coach Voice rules (services/coach_voice_prompt.py)
  - The 28 caption principle catalog (services/caption_principles.py)
  - The 23 shape pattern catalog (services/shape_patterns.py)

LLM decides per move: is there a teaching idea here, or is it a nothing
position? Empty output = skip (better silence than fluff).

Writes a side-by-side markdown report (existing caption vs LLM caption +
the facts that were sent). Does NOT touch production data.

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
import sys
from pathlib import Path
from typing import Any, Dict, List

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


CAPTION_TASK_PROMPT = """You are writing ONE-SENTENCE captions for chess moves, for players rated 600–1500.

You receive structured facts about ONE move. Your job is to find the TEACHING IDEA in this position, if any.

THE TEACHING IDEA might be:
  - ABOUT THE PLAYED MOVE — if it was a mistake/blunder, or if it applied/violated a principle or shape pattern. Critique or praise it by NAMING the principle or shape pattern.
  - ABOUT THE BEST MOVE — if the played move was just "fine but not best". The lesson lives in what the BEST move would have done. Explain that.
  - NOTHING — if there is no real principle, no shape pattern, no concrete teaching idea (forced recaptures, only-legal-moves, quiet shuffles). Return empty. Better silence than fluff.

HARD RULES (failing any = task failed):

1. Max 18 words. ONE sentence.
2. Use ONLY principle and shape-pattern NAMES from the catalogs in this prompt. If your idea doesn't match any catalog entry, return empty.
3. Use ONLY the moves and squares actually named in the facts. Invent nothing — no fake squares, no fake pieces, no fake moves.
4. NEVER use engine words: cp, eval, evaluation, centipawn, accuracy, %.
5. NEVER use words your catalogs don't contain: outpost, prophylactic, minority attack, in-between move, zugzwang, luft, repositions, controls.
6. NEVER end with advice tails: "focus on…", "try to…", "in future games…", "consider…".
7. If best_move differs from move_played and the played move is just fine: name the best move and what it does (the principle/shape it applies).
8. The caption stands on its own. Don't say "this move" — name the move (e.g., "Nf3" not "this move").

OUTPUT FORMAT:
  - If there is a teaching idea: output the single sentence. Nothing else.
  - If there is nothing to teach: output an empty string (just press enter). No "N/A", no "skip", no explanation.

Re-read your sentence before output: would the smartest friend who plays chess actually say this to a 1000-rated player?"""


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
        "primary_principle_id": move.get("caption_facts_primary_reason"),
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


async def generate_caption(move: Dict[str, Any], sys_prompt: str) -> str:
    facts = build_move_facts(move)
    user_prompt = f"MOVE FACTS:\n{json.dumps(facts, indent=2)}\n\nWrite the caption."
    try:
        out = await call_llm(
            system_message=sys_prompt,
            user_message=user_prompt,
            model="gpt-4o-mini",
            max_tokens=80,
        )
        return (out or "").strip().strip('"').strip("'")
    except Exception as e:
        return f"[ERROR: {e}]"


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
    ap.add_argument("--output", type=str, default="llm_caption_test.md")
    ap.add_argument("--source", choices=["queue", "random"], default="queue",
                    help="queue=use active authoring_queue (default), random=random sample")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    games = await pick_games(db, args.n, args.source)
    print(f"[test] selected {len(games)} games", file=sys.stderr)

    # Build the system prompt once and reuse across every call.
    sys_prompt = with_coach_voice(
        CAPTION_TASK_PROMPT
        + "\n\n" + build_principle_catalog_block()
        + "\n\n" + build_shape_catalog_block()
    )
    print(f"[test] system prompt: {len(sys_prompt):,} chars", file=sys.stderr)

    out_lines: List[str] = [
        "# LLM Caption Test",
        f"_Source: {args.source} · Games: {len(games)} · Model: gpt-4o-mini_",
        "",
    ]

    total_moves = 0
    total_empty = 0
    total_errors = 0

    for idx, item in enumerate(games, 1):
        gid = item["game_id"]
        bucket = item.get("bucket", "?")
        analysis = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "decryption_v5_data": 1},
        )
        if not analysis or not analysis.get("decryption_v5_data"):
            out_lines.append(f"## {idx}. `{gid}` ({bucket}) — NO V5 DATA")
            out_lines.append("")
            continue

        moves = analysis["decryption_v5_data"]
        out_lines.append(f"## {idx}. `{gid}` ({bucket}) — {len(moves)} moves")
        out_lines.append("")

        for m in moves:
            existing = (m.get("caption") or "").strip() or "_(no caption)_"
            llm_caption = await generate_caption(m, sys_prompt)
            total_moves += 1
            if not llm_caption:
                total_empty += 1
            elif llm_caption.startswith("[ERROR"):
                total_errors += 1

            tag = m.get("severity", "?")
            cpl = m.get("cp_loss", 0)
            mover = "user" if m.get("is_user_move") else "opp"
            mv = m.get("move_san", "?")
            mn = m.get("move_number", "?")

            out_lines.append(f"**{mn}. {mv}** ({mover} · {tag} · cp_loss={cpl})")
            out_lines.append(f"- existing: {existing}")
            out_lines.append(f"- **LLM**: {llm_caption or '_(empty — nothing to teach)_'}")
            out_lines.append(f"- facts: {format_facts_inline(m)}")
            out_lines.append("")

    pct_empty = 100 * total_empty // max(1, total_moves)
    out_lines.append("---")
    out_lines.append(f"**Total moves:** {total_moves}  ·  "
                     f"**Empty (skipped):** {total_empty} ({pct_empty}%)  ·  "
                     f"**Errors:** {total_errors}")

    output_path = Path(args.output)
    output_path.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"[test] wrote {output_path.resolve()}", file=sys.stderr)
    print(f"[test] {total_moves} moves, {total_empty} empty ({pct_empty}%), {total_errors} errors", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
