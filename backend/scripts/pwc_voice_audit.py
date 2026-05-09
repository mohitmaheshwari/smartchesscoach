"""
Play-with-Coach voice audit — sample real messages, classify quality.

Static template audit was clean (no banned terms in code). This script
takes the next step: pull actual messages from coach_messages and
postgame_analyses in production, eyeball them for voice quality.

Checks per message:
  1. Concrete content (mentions a square, piece name, or specific move)
  2. Teaching tone (uses "you", or a coaching question — not just description)
  3. No banned jargon (outpost, minority attack, luft, engine prefers,
     controls, centipawn, evaluation, stockfish, cp loss)
  4. Reasonable length (10–200 chars; longer = wall of text, shorter = empty)

Usage:
    python scripts/pwc_voice_audit.py --limit 200 --samples 25
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# Banned jargon (case-insensitive). "fianchetto" is allowed per memo.
BANNED_TERMS = [
    "outpost", "minority attack", "luft", "engine prefers", "stockfish",
    "centipawn", "cp loss", "evaluation drops", "evaluation drop",
    "the evaluation", "swing of",
]

# Coach-voice signals: concrete pieces, squares, "you", questions.
SQUARE_RE = re.compile(r"\b[a-h][1-8]\b")
PIECE_NAMES = {"king", "queen", "rook", "bishop", "knight", "pawn"}
COACH_PRONOUNS = {"you", "your", "yours"}


def has_banned_term(text: str) -> List[str]:
    lo = text.lower()
    return [term for term in BANNED_TERMS if term in lo]


def has_square(text: str) -> bool:
    return bool(SQUARE_RE.search(text))


def has_piece(text: str) -> bool:
    lo = text.lower()
    return any(p in lo.split() or f"{p}'s" in lo or f"{p}s" in lo for p in PIECE_NAMES) \
           or any(re.search(rf"\b{p}\b", lo) for p in PIECE_NAMES)


def has_pronoun(text: str) -> bool:
    lo = text.lower()
    return any(re.search(rf"\b{p}\b", lo) for p in COACH_PRONOUNS)


def has_question(text: str) -> bool:
    return "?" in text


def classify_voice(text: str) -> Dict:
    """Voice quality scoring per coach-not-narrator memo."""
    if not text:
        return {"score": 0, "issues": ["empty"]}

    issues = []
    signals = []

    banned = has_banned_term(text)
    if banned:
        issues.append(f"banned: {','.join(banned)}")

    if len(text) < 10:
        issues.append("too short")
    if len(text) > 250:
        issues.append("too long")

    if has_square(text):
        signals.append("square")
    if has_piece(text):
        signals.append("piece")
    if has_pronoun(text):
        signals.append("pronoun")
    if has_question(text):
        signals.append("question")

    # Scoring: 1 point per concrete signal, -2 per banned, -1 per length issue.
    score = len(signals) - 2 * len(banned)
    if "too short" in issues or "too long" in issues:
        score -= 1

    return {
        "score": score,
        "issues": issues,
        "signals": signals,
    }


def verdict(score: int, issues: List[str]) -> str:
    if any("banned" in i for i in issues):
        return "RED"
    if score >= 2:
        return "GREEN"
    if score >= 1:
        return "YELLOW"
    return "RED"


async def run(args):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print(f"\n=== Sampling coach_messages (limit {args.limit}) ===\n")
    cursor = db.coach_messages.find(
        {"message": {"$exists": True, "$ne": ""}},
        {"_id": 0, "message": 1, "trigger": 1, "move": 1, "move_number": 1,
         "created_at": 1, "session_id": 1},
    ).sort("created_at", -1).limit(args.limit)

    msgs = await cursor.to_list(args.limit)
    print(f"Pulled {len(msgs)} messages\n")

    verdict_counts: Counter = Counter()
    by_trigger: Dict[str, Counter] = {}
    samples_by_verdict: Dict[str, List[Dict]] = {"GREEN": [], "YELLOW": [], "RED": []}
    issue_counts: Counter = Counter()

    for m in msgs:
        text = (m.get("message") or "").strip()
        cls = classify_voice(text)
        v = verdict(cls["score"], cls["issues"])
        verdict_counts[v] += 1

        trig = m.get("trigger") or "unknown"
        by_trigger.setdefault(trig, Counter())[v] += 1

        for issue in cls["issues"]:
            issue_counts[issue.split(":")[0]] += 1

        if len(samples_by_verdict[v]) < args.samples:
            samples_by_verdict[v].append({
                "trigger": trig,
                "move": m.get("move"),
                "move_number": m.get("move_number"),
                "text": text[:200],
                "signals": cls["signals"],
                "issues": cls["issues"],
            })

    total = sum(verdict_counts.values()) or 1
    print("=" * 70)
    print("VERDICT DISTRIBUTION")
    print("=" * 70)
    for v in ("GREEN", "YELLOW", "RED"):
        n = verdict_counts.get(v, 0)
        print(f"  {v:>6}: {n:5d}  ({100.0 * n / total:5.1f}%)")
    print()

    if issue_counts:
        print("ISSUE FREQUENCY:")
        for issue, n in issue_counts.most_common():
            print(f"  {n:5d}  {issue}")
        print()

    print("=" * 70)
    print("BY TRIGGER (verdicts per coach-message trigger type)")
    print("=" * 70)
    for trig, vcount in sorted(by_trigger.items(), key=lambda x: -sum(x[1].values())):
        sub_total = sum(vcount.values())
        g = vcount.get("GREEN", 0)
        y = vcount.get("YELLOW", 0)
        r = vcount.get("RED", 0)
        print(f"  {trig:<25} n={sub_total:4d}   G={g:3d} ({100*g/sub_total:4.0f}%)  Y={y:3d}  R={r:3d}")
    print()

    for v in ("RED", "YELLOW", "GREEN"):
        if not samples_by_verdict[v]:
            continue
        print("=" * 70)
        print(f"SAMPLE MESSAGES — {v}  (showing {len(samples_by_verdict[v])})")
        print("=" * 70)
        for s in samples_by_verdict[v]:
            print(f"\n  trigger: {s['trigger']}   move: {s.get('move')}   #: {s.get('move_number')}")
            print(f"  signals: {s['signals']}    issues: {s['issues']}")
            print(f"  text: \"{s['text']}\"")
        print()

    # ── Postgame analysis voice check ──────────────────────────────
    print("=" * 70)
    print("POSTGAME ANALYSES (from PwC games — voice check on stored summaries)")
    print("=" * 70)
    pg_cursor = db.postgame_analyses.find(
        {},
        {"_id": 0},
    ).sort("created_at", -1).limit(20)
    pgs = await pg_cursor.to_list(20)
    print(f"  pulled {len(pgs)} postgame analyses\n")
    if pgs:
        # Look for any text fields we want to eyeball
        sample = pgs[0]
        print("  Top-level keys on most-recent postgame:")
        for k in sorted(sample.keys()):
            v = sample[k]
            preview = str(v)[:100] if not isinstance(v, (list, dict)) else f"<{type(v).__name__}>"
            print(f"    {k}: {preview}")
        print()

    client.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=300, help="messages to sample")
    p.add_argument("--samples", type=int, default=15, help="examples per verdict")
    asyncio.run(run(p.parse_args()))
