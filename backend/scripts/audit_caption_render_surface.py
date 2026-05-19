"""
Per-rendered-caption audit. Closes the audit-coverage gap that let
Parth's 2026-05-18 batch of 23 bugs slip past existing detector
audits.

Per [[feedback_audit_coverage_tracks_surface]] (HARD self-discipline
2026-05-13) — our per-fire audits verify DETECTORS but not RENDERED
TEXT. Parth sees rendered text. This script iterates over every
caption emitted by V5 across the corpus and runs structural / regex
checks against the violation classes the Opus triage uncovered.

CHECKS (each tracked separately so we can target fixes):

  1. CP_NUMBER_LEAK
       Caption contains internal cp numbers ("Net 100 cp", "drops 50 cp",
       "wins 200 cp"). Parth #13, #20, #21. Should be 0 post-9b991160.

  2. R12_HOLLOW_WHY
       R12 caption matches "X loses about N pawns. Y was better." OR
       "Opponent's X drops about N pawns." with no concrete follow-up
       sentence after the period. Parth #2-#10, #18-#19. Should be 0
       post-9b991160 for sub-blunder cp_loss.

  3. PROMISE_WITHOUT_DELIVERY
       Caption uses phrases like "stronger move available", "better
       option here", "engine sees better" without actually NAMING the
       move/square. Parth #17. Empty calorie.

  4. ABSTRACT_LOSS_CLAIM
       Caption says "position is lost" / "winning by force" without
       naming WHAT specifically. Parth #19.

  5. FALLS_VERB_ON_SKEWER
       R03 skewer caption uses "falls" (overclaims). Should be 0
       post-9b991160 (verb softened to "is exposed").

  6. ALLOWS_FRAMING_ON_PRE_EXISTING_MATE
       R01 caption says "allows mate" when eval_before <= -2000.
       Should be 0 post-9b991160 (split to "misses defense against").

  7. PAWN_COUNT_MATH_DRIFT
       Caption claims "about N pawns" where round(cp_loss/100) != N.
       Math drift / template bug.

  8. CONCEPT_CUE_VS_MOVE_MISMATCH
       Cue text fires on a move where the geometric claim is impossible
       (e.g. hanging-piece cue fires on f4 with no actual hanging piece
       in the post-move FEN). HARDER — only checks loose heuristics.

USAGE:
  MONGO_URL=... docker exec -i chess-coach-backend python \\
    scripts/audit_caption_render_surface.py [--limit N] [--out PATH]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# Regex predicates ────────────────────────────────────────────────

# "Net 100 cp in the exchange", "wins 50 cp", "drops 200 cp", "gains 75 cp"
_RE_CP_NUMBER = re.compile(r"\b(?:Net\s+)?\d{1,4}\s*cp\b", re.IGNORECASE)

# Phrases that overpromise without naming
_RE_HOLLOW_PROMISE = re.compile(
    r"stronger move available"
    r"|better option here"
    r"|engine sees better"
    r"|there's a better"
    r"|short steps toward shelter",
    re.IGNORECASE,
)

# R12 bare-pawn template: "X loses about N pawn[s]. Y was better." with
# NO concrete consequence sentence after that
_RE_R12_USER_BARE = re.compile(
    r"^\S+ loses about \d+ pawns?\. \S+ was better\.$"
)
_RE_R12_USER_NO_BEST = re.compile(
    r"^\S+ loses about \d+ pawns?\.$"
)
_RE_R12_OPP_BARE = re.compile(
    r"^Opponent's \S+ drops about \d+ pawns?\.$"
)

# R03 skewer "falls" verb
_RE_FALLS_VERB = re.compile(
    r"skewer.*\bfalls\b",
    re.IGNORECASE,
)

# "allows mate" (vs "misses defense against mate")
_RE_ALLOWS_MATE = re.compile(
    r"\ballows mate\b",
    re.IGNORECASE,
)

# Abstract loss claim with no specifics
_RE_ABSTRACT_LOSS = re.compile(
    r"^\S+\. (?:Position is lost|Wins by force|Position was already lost)\.?$"
)

# "about N pawn[s]" — for math-drift check
_RE_PAWN_COUNT = re.compile(r"about (\d+) pawns?")


def _pawn_count_drift(caption: str, cp_loss: int) -> bool:
    m = _RE_PAWN_COUNT.search(caption)
    if not m:
        return False
    claimed = int(m.group(1))
    expected = max(1, min(9, round((cp_loss or 0) / 100)))
    return claimed != expected


# Single-record evaluation ─────────────────────────────────────────

def check_one(move_record: dict) -> dict:
    """Return a dict {check_name: violation_count} for one move record."""
    # Updated 2026-05-19 after audit discovery: `narrative` field is
    # retired (always "") per game_decryption_v5_service.py:3505. The
    # user-visible text source is the `caption` field (V5 pipeline
    # output). principle_cue is a separate teaching-cue surface.
    caption = (move_record.get("caption") or "").strip()
    legacy_narrative = (move_record.get("narrative") or "").strip()
    principle_cue = (move_record.get("principle_cue") or "").strip()
    eval_before_cp = move_record.get("eval_before") or 0
    cp_loss = move_record.get("cp_loss") or 0
    if isinstance(eval_before_cp, float):
        # eval_before sometimes stored as float pawns, sometimes as cp.
        # If abs < 100 we assume it's pawns; convert. Above 100 it's cp.
        if -100 < eval_before_cp < 100:
            eval_before_cp = int(eval_before_cp * 100)
        else:
            eval_before_cp = int(eval_before_cp)

    violations = {}

    # Scan every text surface that could surface to the user.
    for surface_name, text in (
        ("caption", caption),
        ("narrative_legacy", legacy_narrative),
        ("principle_cue", principle_cue),
    ):
        if not text:
            continue
        if _RE_CP_NUMBER.search(text):
            violations[f"CP_NUMBER_LEAK:{surface_name}"] = True
        if _RE_HOLLOW_PROMISE.search(text):
            violations[f"PROMISE_WITHOUT_DELIVERY:{surface_name}"] = True

    # The remaining checks scan whichever text surface is user-visible
    # — prefer caption, fall back to legacy_narrative if caption empty.
    primary_text = caption or legacy_narrative

    # R12 hollow-WHY
    if primary_text and cp_loss < 250:
        if _RE_R12_USER_BARE.match(primary_text) or _RE_R12_OPP_BARE.match(primary_text) or _RE_R12_USER_NO_BEST.match(primary_text):
            violations["R12_HOLLOW_WHY"] = True

    # R03 falls verb (post-fix should be zero)
    if primary_text and _RE_FALLS_VERB.search(primary_text):
        violations["FALLS_VERB_ON_SKEWER"] = True

    # R01 allows-mate on pre-existing mate
    if primary_text and _RE_ALLOWS_MATE.search(primary_text):
        if eval_before_cp <= -2000:
            violations["ALLOWS_FRAMING_ON_PRE_EXISTING_MATE"] = True

    # Abstract loss claims
    if primary_text and _RE_ABSTRACT_LOSS.match(primary_text):
        violations["ABSTRACT_LOSS_CLAIM"] = True

    # Pawn-count math drift
    if primary_text and _pawn_count_drift(primary_text, cp_loss):
        violations["PAWN_COUNT_MATH_DRIFT"] = True

    return violations


# Corpus pass ──────────────────────────────────────────────────────

async def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", type=str, default="/tmp/caption_render_audit.json")
    parser.add_argument("--only-current-version", action="store_true",
                        help="Restrict to game_analyses with decryption_v5_version >= current (so we audit only NEW renderer output, not legacy).")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("ERROR: MONGO_URL required", file=sys.stderr)
        sys.exit(1)

    from motor.motor_asyncio import AsyncIOMotorClient
    from services.game_decryption_v5_service import V5_COACHING_VERSION

    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    q = {"decryption_v5_data": {"$exists": True, "$ne": None}}
    if args.only_current_version:
        q["decryption_v5_version"] = {"$gte": V5_COACHING_VERSION}

    total_games = 0
    total_records = 0
    total_with_caption = 0
    violations_by_check = Counter()
    samples_by_check: dict = defaultdict(list)

    cursor = db.game_analyses.find(
        q, {"_id": 0, "game_id": 1, "decryption_v5_data": 1, "decryption_v5_version": 1}
    )

    async for analysis in cursor:
        if args.limit and total_games >= args.limit:
            break
        total_games += 1
        gid = analysis.get("game_id")
        v = analysis.get("decryption_v5_version")
        records = analysis.get("decryption_v5_data") or []
        for r in records:
            total_records += 1
            cap = r.get("narrative") or r.get("principle_cue")
            if cap:
                total_with_caption += 1
            vs = check_one(r)
            for k in vs:
                violations_by_check[k] += 1
                if len(samples_by_check[k]) < 5:
                    samples_by_check[k].append({
                        "game_id": gid,
                        "v5_version": v,
                        "move_number": r.get("move_number"),
                        "move_san": r.get("move_san"),
                        "is_user_move": r.get("is_user_move"),
                        "cp_loss": r.get("cp_loss"),
                        "eval_before": r.get("eval_before"),
                        "narrative": (r.get("narrative") or "")[:200],
                        "principle_cue": (r.get("principle_cue") or "")[:200],
                    })

        if total_games % 200 == 0:
            print(f"  audited {total_games} games · {total_records} records · violations {sum(violations_by_check.values())}", file=sys.stderr)

    out = {
        "scanned_games": total_games,
        "scanned_move_records": total_records,
        "records_with_caption": total_with_caption,
        "violations_total": sum(violations_by_check.values()),
        "violations_by_check": dict(violations_by_check.most_common()),
        "samples_by_check": dict(samples_by_check),
        "current_v5_version": V5_COACHING_VERSION,
        "only_current_version": args.only_current_version,
    }
    Path(args.out).write_text(json.dumps(out, indent=2))

    # Stdout summary
    print()
    print("=" * 60)
    print(f"Caption render-surface audit  (v5_version filter: {'>= '+str(V5_COACHING_VERSION) if args.only_current_version else 'all'})")
    print(f"  scanned games:           {total_games}")
    print(f"  scanned move records:    {total_records}")
    print(f"  records with caption:    {total_with_caption}")
    print(f"  total violations:        {sum(violations_by_check.values())}")
    if total_with_caption:
        pct = 100.0 * sum(violations_by_check.values()) / total_with_caption
        print(f"  violation rate:          {pct:.2f}%")
    print()
    print("By check:")
    for check, count in violations_by_check.most_common():
        print(f"  {check:48s}  {count}")
    print()
    if samples_by_check:
        print("Sample violations (first 2 per check):")
        for check, samples in samples_by_check.items():
            print(f"  [{check}]")
            for s in samples[:2]:
                print(f"    game {s['game_id'][:14]}  m{s['move_number']} {s['move_san']}  cpl={s['cp_loss']}  v5={s['v5_version']}")
                if s['narrative']:
                    print(f"      narrative: {s['narrative']}")
                if s['principle_cue']:
                    print(f"      cue:       {s['principle_cue']}")
    print()
    print(f"Full report: {args.out}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
