"""Audit stored V5 captions for teaching value — does each caption have a WHY?

A caption has a WHY if any of three heuristics fires:
  H1 — concrete consequence (names a square/piece/move beyond the played SAN)
  H2 — causal connector (because/since/so/—/loses to/walks into/hits/hangs)
  H3 — principle ending (transferable rule in the closing sentence)

Captions failing ALL THREE are the "X is a mistake. Y was better." shape — the
canonical zero-teaching caption that produced fb_ec0098264c8e ("Qe2 is a
mistake. O-O was better." → user replied "why??").

Restrict to severity ∈ {mistake, blunder}. good/context/inaccuracy are allowed
to be brief.

Usage:
  docker exec chess-coach-backend python \\
    /app/backend/scripts/audit_captions_for_why.py --n 500
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

SEVERITIES_AUDITED = {"mistake", "blunder"}

# Compiled once.
SQUARE_RE = re.compile(r"\b[a-h][1-8]\b")  # any algebraic square reference
PIECE_NAME_RE = re.compile(
    r"\b(king|queen|rook|bishop|knight|pawn|kings|queens|rooks|bishops|knights|pawns)\b",
    re.IGNORECASE,
)
CAUSAL_CONNECTOR_RE = re.compile(
    r"\b(because|since|so that|in order to|otherwise)\b|—|"
    r"\b(loses to|walks into|leaves \w+ hanging|hangs|hits|grabs|"
    r"falls|threatens|attacks|exposes|wins the|abandons|opens)\b",
    re.IGNORECASE,
)
# Principle endings: transferable rules. Looking at the closing sentence.
PRINCIPLE_VERB_RE = re.compile(
    r"\b(always|never|before .* (check|count|look)|"
    r"when .*?, (do|play|move|take|check)|"
    r"remember|this is why|count what|look for|"
    r"avoid moving|prefer .* over|the rule is|keep your)\b",
    re.IGNORECASE,
)


def has_concrete_consequence(caption: str, played_san: str, best_san: str | None) -> bool:
    """H1: caption names a square or piece beyond what's in the SAN itself.

    "Qe2 is a mistake. O-O was better." — has 'Qe2' and 'O-O' which are the SANs.
    No additional squares or pieces referenced. Fails H1.

    "Qe2 leaves d4 hanging — Qxd4 wins the pawn" — references d4 and 'pawn'
    beyond the SAN. Passes H1.
    """
    text = caption
    # Strip the SAN itself to avoid double-counting.
    for san in (played_san, best_san or ""):
        if san:
            text = text.replace(san, " ")
    squares_mentioned = set(SQUARE_RE.findall(text))
    pieces_mentioned = bool(PIECE_NAME_RE.search(text))
    # ≥1 extra square OR a piece-type word counts as concrete.
    return len(squares_mentioned) >= 1 or pieces_mentioned


def has_causal_connector(caption: str) -> bool:
    """H2: caption uses an explanation marker."""
    return bool(CAUSAL_CONNECTOR_RE.search(caption))


def has_principle_ending(caption: str) -> bool:
    """H3: closing sentence contains a generalization verb pattern."""
    # Last sentence after the final period (or whole thing if no period).
    sentences = re.split(r"(?<=[.!?])\s+", caption.strip())
    if not sentences:
        return False
    last = sentences[-1]
    return bool(PRINCIPLE_VERB_RE.search(last))


def caption_shape(caption: str) -> str:
    """Normalize a caption to its template shape for grouping.

    "Qe2 is a mistake. O-O was better." → "{X} is a mistake. {Y} was better."
    """
    s = caption
    # Strip leading/trailing whitespace + quotes.
    s = s.strip().strip('"').strip("'")
    # Replace SAN-like tokens with {X}/{Y}.
    s = re.sub(r"\bO-O-O\b|\bO-O\b|\b[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?\+?#?\b", "{M}", s)
    # Replace square refs (any leftover).
    s = re.sub(r"\b[a-h][1-8]\b", "{S}", s)
    # Collapse multiple {M}/{S} runs.
    s = re.sub(r"(\{M\} )+", "{M} ", s)
    return s


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500, help="games to sample")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--severities", type=str, default="mistake,blunder")
    ap.add_argument("--sample-fail-count", type=int, default=12,
                    help="how many failing captions to print as examples")
    ap.add_argument("--min-version", type=int, default=None,
                    help="Only audit games at this V5 version or newer. Use to compare "
                         "current-pipeline output against historical stored captions.")
    args = ap.parse_args()

    severities = {s.strip() for s in args.severities.split(",") if s.strip()}
    random.seed(args.seed)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Sample N analyzed games with v5 data — random selection.
    pool_filter: dict = {"decryption_v5_data": {"$type": "array"}}
    if args.min_version is not None:
        pool_filter["decryption_v5_version"] = {"$gte": args.min_version}
        print(f"[audit] Restricting pool to V5 v{args.min_version}+ "
              "(current-pipeline output only)", file=sys.stderr)
    all_gids = await db.game_analyses.distinct("game_id", pool_filter)
    # Sort before sampling: distinct() order is engine-defined and not stable.
    # Without this, seed=42 here vs in regen_v5_sample.py picks different
    # 100 games — masquerading as "regen didn't help" when really regen ran
    # on a different sample than audit.
    all_gids.sort()
    print(f"[audit] Pool with v5 data: {len(all_gids)} games", file=sys.stderr)
    if len(all_gids) > args.n:
        sample_gids = random.sample(all_gids, args.n)
    else:
        sample_gids = all_gids
    print(f"[audit] Sampling {len(sample_gids)} games", file=sys.stderr)

    total_scanned = 0
    pass_count = 0
    fail_count = 0
    fail_by_severity: Counter[str] = Counter()
    total_by_severity: Counter[str] = Counter()
    fail_shapes: Counter[str] = Counter()
    fail_examples: list[dict] = []
    h_hits: Counter[str] = Counter()

    BATCH = 50
    for batch_start in range(0, len(sample_gids), BATCH):
        batch_gids = sample_gids[batch_start:batch_start + BATCH]
        async for ga in db.game_analyses.find(
            {"game_id": {"$in": batch_gids}, "decryption_v5_data": {"$type": "array"}},
            {"_id": 0, "game_id": 1, "decryption_v5_data": 1},
        ):
            gid = ga["game_id"]
            for rec in ga.get("decryption_v5_data", []):
                if not isinstance(rec, dict):
                    continue
                sev = rec.get("severity")
                if sev not in severities:
                    continue
                # Only audit USER moves.
                if not rec.get("is_user_move"):
                    continue
                caption = (rec.get("caption") or "").strip()
                if not caption:
                    continue
                total_scanned += 1
                total_by_severity[sev] += 1
                played = rec.get("move_san") or ""
                best = rec.get("best_move_san")
                h1 = has_concrete_consequence(caption, played, best)
                h2 = has_causal_connector(caption)
                h3 = has_principle_ending(caption)
                if h1:
                    h_hits["H1_concrete"] += 1
                if h2:
                    h_hits["H2_causal"] += 1
                if h3:
                    h_hits["H3_principle"] += 1
                if h1 or h2 or h3:
                    pass_count += 1
                else:
                    fail_count += 1
                    fail_by_severity[sev] += 1
                    shape = caption_shape(caption)
                    fail_shapes[shape] += 1
                    if len(fail_examples) < args.sample_fail_count * 4:
                        fail_examples.append({
                            "game_id": gid,
                            "move_number": rec.get("move_number"),
                            "move_san": played,
                            "severity": sev,
                            "cp_loss": rec.get("cp_loss"),
                            "caption": caption,
                        })

    print()
    print("══════════════════════════════════════════════════════════════════")
    print(f"  CAPTIONS-FOR-WHY AUDIT — sampled {len(sample_gids)} games")
    print("══════════════════════════════════════════════════════════════════")
    print(f"  Severities audited: {sorted(severities)}")
    print(f"  Total captions scanned: {total_scanned}")
    if total_scanned == 0:
        print("  (no captions matched filter)")
        return 0
    print(f"    passes WHY:  {pass_count:>5}  ({100*pass_count/total_scanned:.1f}%)")
    print(f"    fails  WHY:  {fail_count:>5}  ({100*fail_count/total_scanned:.1f}%)")
    print()
    print("  Heuristic hit rates (any-of passes):")
    for k, v in h_hits.most_common():
        print(f"    {k:<18}: {v} ({100*v/total_scanned:.1f}%)")
    print()
    print("  Fail rate by severity:")
    for sev in sorted(severities):
        t = total_by_severity.get(sev, 0)
        f = fail_by_severity.get(sev, 0)
        if t:
            print(f"    {sev:<10}: {f}/{t} = {100*f/t:.1f}%")
    print()
    print("  Top failing caption shapes:")
    for shape, cnt in fail_shapes.most_common(8):
        print(f"    [{cnt:>4}]  {shape[:100]}")
    print()
    sample = random.sample(fail_examples, min(args.sample_fail_count, len(fail_examples)))
    print(f"  Sample failing captions ({len(sample)} of {len(fail_examples)}):")
    for ex in sample:
        cpl = ex.get("cp_loss")
        print(f"    game={ex['game_id'][:18]:<18}  m{ex['move_number']:<2} {ex['move_san']:<7}  "
              f"sev={ex['severity']:<8} cp_loss={cpl}")
        print(f"      > \"{ex['caption'][:160]}\"")

    # Snapshot for later comparison.
    out_path = "/app/backend/scripts/_snapshots/audit_captions_for_why.json"
    snapshot = {
        "args": vars(args),
        "total_scanned": total_scanned,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "fail_rate_pct": round(100 * fail_count / total_scanned, 2),
        "h_hits": dict(h_hits),
        "total_by_severity": dict(total_by_severity),
        "fail_by_severity": dict(fail_by_severity),
        "fail_shapes_top": fail_shapes.most_common(20),
        "fail_examples_sample": sample,
    }
    with open(out_path, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)
    print()
    print(f"  Snapshot → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
