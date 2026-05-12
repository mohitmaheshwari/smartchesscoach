"""
V5 caption pipeline corpus audit.

Runs `generate_game_decryption_v5` over every analyzed game in the DB
and aggregates the rule_name histogram, silent rate, and a flagged
list of captions that look architecturally wrong. The point is to
find where the renderer bends under broader usage — d7ce40cf was a
single game, but the v5 pipeline now sees the whole corpus.

Suspects flagged:
  S1  silent_on_user_blunder    — cp_loss ≥ 100 user move + empty caption
  S2  fallback_no_trigger       — primary_reason picked a category but no
                                  rule in that category fired (priority
                                  ordering bug, R10/R11/etc threshold drift)
  S3  fallback_no_primary_high  — caption silent + cp_loss ≥ 100 (R12 hole)
  S4  r12_fired_low_cpl         — R12_blunder on cp_loss < 100 (gate drift)
  S5  tactic_on_losing_move     — R02/R03/R04 on cp_loss ≥ 100 (bend #1 drift)
  S6  threat_on_losing_move     — R10_threat on cp_loss ≥ 100 (bend #1 drift)
  S7  mate_no_sentinel          — R01_mate but neither eval is mate-range

Stats accumulated:
  - Total move records
  - Per-rule firing count (full histogram)
  - Silent rate (caption empty)
  - User-blunder caption rate (captions on cp_loss ≥ 100 user moves)
  - Distinct caption strings (template repetition check)

By default DOES NOT write back to MongoDB. Pass --write-db to persist
the regenerated decryption_v5_data alongside the audit.

Usage (inside the backend container OR with backend/.env loadable):

    python scripts/audit_caption_v5_corpus.py
    python scripts/audit_caption_v5_corpus.py --limit 50
    python scripts/audit_caption_v5_corpus.py --user-id <uid>
    python scripts/audit_caption_v5_corpus.py --since-days 30
    python scripts/audit_caption_v5_corpus.py --output /tmp/v5_audit.txt
    python scripts/audit_caption_v5_corpus.py --write-db
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


# ── Thresholds used to flag suspects (mirror caption_config) ──────────
USER_BLUNDER_CP = 100   # cp_loss ≥ this on user move ⇒ should fire R12 or R01
TACTIC_CP_GATE = 100    # MAX_CP_LOSS_FOR_TACTIC_CELEBRATION
MATE_SENTINEL = 9000    # |eval| ≥ this is engine mate score


def _is_mate_sentinel(*evals: Optional[int]) -> bool:
    return any(e is not None and abs(e) >= MATE_SENTINEL for e in evals)


def _classify_suspect(mv: Dict[str, Any]) -> List[str]:
    """Return the suspect tags this move record matches. Empty list = clean."""
    tags: List[str] = []
    rule = mv.get("rule_name") or ""
    cap = mv.get("caption") or ""
    cpl = mv.get("cp_loss") or 0
    is_user = bool(mv.get("is_user_move"))
    primary = mv.get("caption_facts_primary_reason") or {}
    eb = mv.get("eval_before")
    ea = mv.get("eval_after")

    silent = not cap.strip()

    if silent and is_user and cpl >= USER_BLUNDER_CP:
        tags.append("S1_silent_on_user_blunder")
    if rule == "R_FALLBACK_no_trigger_fired":
        tags.append("S2_fallback_no_trigger")
    if rule == "R_FALLBACK_no_primary" and cpl >= USER_BLUNDER_CP and is_user:
        tags.append("S3_fallback_no_primary_high")
    if rule == "R12_blunder" and cpl < USER_BLUNDER_CP:
        tags.append("S4_r12_fired_low_cpl")
    if rule in ("R02_multi_target_attack", "R03_aligned_pieces",
                "R04_discovered_attack") and cpl >= TACTIC_CP_GATE:
        tags.append("S5_tactic_on_losing_move")
    if rule == "R10_threat" and cpl >= TACTIC_CP_GATE:
        tags.append("S6_threat_on_losing_move")
    if rule == "R01_mate" and not _is_mate_sentinel(eb, ea):
        tags.append("S7_mate_no_sentinel")
    return tags


def _short(text: Optional[str], n: int = 90) -> str:
    if not text:
        return ""
    s = str(text).replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0,
                   help="Process only first N games (0 = all).")
    p.add_argument("--user-id", default=None,
                   help="Only games for this user_id.")
    p.add_argument("--since-days", type=int, default=0,
                   help="Only games imported in the last N days (0 = all).")
    p.add_argument("--game-id", default=None,
                   help="Audit just this single game (overrides other filters).")
    p.add_argument("--output", default=None,
                   help="Also write the report to this path "
                        "(relative to repo root if not absolute).")
    p.add_argument("--write-db", action="store_true",
                   help="Persist regenerated decryption_v5_data alongside "
                        "the audit. Default: in-memory only.")
    p.add_argument("--samples-per-rule", type=int, default=3,
                   help="How many sample captions to print per rule_name.")
    p.add_argument("--samples-per-suspect", type=int, default=10,
                   help="How many suspect samples to print per tag.")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress the report on stdout — only write it to "
                        "--output. Per-game progress lines still print so "
                        "you can see the run is alive.")
    args = p.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    flt: Dict[str, Any] = {"is_analyzed": True}
    if args.game_id:
        flt = {"game_id": args.game_id}
    else:
        if args.user_id:
            flt["user_id"] = args.user_id
        if args.since_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=args.since_days)
            flt["imported_at"] = {"$gte": cutoff.isoformat()}

    cursor = db.games.find(flt, {"_id": 0}).sort("imported_at", -1)
    if args.limit > 0:
        cursor = cursor.limit(args.limit)
    games = await cursor.to_list(args.limit if args.limit > 0 else 10000)

    if not games:
        print("No games match the filters.")
        client.close()
        return 0

    # Stub Stockfish-candidate lookups — they make regen 20× slower and the
    # caption pipeline doesn't depend on them.
    from services import game_decryption_v5_service as v5_mod
    from services.game_decryption_v5_service import generate_game_decryption_v5

    async def _noop_candidates(*_a, **_kw):
        return []
    v5_mod._get_stockfish_candidates = _noop_candidates

    rule_counts: Counter = Counter()
    suspect_examples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    rule_examples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    caption_text_counts: Counter = Counter()

    # Teaching-layer aggregates (caption_facts_principles_violated).
    # Shipped detectors fire here as evidence dicts; this audit groups
    # them by principle_id + engine_endorsement so we can see whether
    # each detector is hitting realistic positions or over-firing.
    principle_counts: Counter = Counter()
    principle_endorsement_counts: Dict[str, Counter] = defaultdict(Counter)
    principle_samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    total_moves = 0
    silent_moves = 0
    user_moves = 0
    user_blunder_moves = 0
    user_blunder_captioned = 0
    n_games_ok = 0
    n_games_skipped = 0
    n_games_failed = 0
    n_games_written = 0

    t0 = time.time()
    for i, game in enumerate(games, 1):
        game_id = game.get("game_id")
        user_id = game.get("user_id") or "unknown"
        analysis = await db.game_analyses.find_one({"game_id": game_id}, {"_id": 0})
        if not analysis:
            n_games_skipped += 1
            continue
        sf = analysis.get("stockfish_analysis") or {}
        move_evaluations = sf.get("move_evaluations") or []
        pgn = game.get("pgn") or ""
        user_color = (game.get("user_color") or "white").lower()
        if not pgn or not move_evaluations:
            n_games_skipped += 1
            continue

        try:
            decryption = await generate_game_decryption_v5(
                pgn=pgn,
                user_color=user_color,
                move_evaluations=move_evaluations,
                user_id=user_id,
                db=db,
            )
        except Exception as exc:
            print(f"  [{i}/{len(games)}] {game_id}  FAIL: {exc}")
            n_games_failed += 1
            continue

        if args.write_db:
            try:
                await db.game_analyses.update_one(
                    {"game_id": game_id},
                    {"$set": {
                        "decryption_v5_data": decryption,
                        "decryption_v5_regen_at": datetime.now(timezone.utc),
                    }},
                )
                n_games_written += 1
            except Exception as exc:
                print(f"  [{i}/{len(games)}] {game_id}  WRITE-FAIL: {exc}")

        for mv in decryption:
            total_moves += 1
            rule = mv.get("rule_name") or "(no_rule)"
            cap = mv.get("caption") or ""
            rule_counts[rule] += 1
            if not cap.strip():
                silent_moves += 1
            else:
                caption_text_counts[cap] += 1
                if len(rule_examples[rule]) < args.samples_per_rule:
                    rule_examples[rule].append({
                        "game_id": game_id,
                        "move_no": mv.get("move_number"),
                        "side": "USER" if mv.get("is_user_move") else "OPP",
                        "move_san": mv.get("move_san"),
                        "cp_loss": mv.get("cp_loss"),
                        "caption": cap,
                    })

            if mv.get("is_user_move"):
                user_moves += 1
                if (mv.get("cp_loss") or 0) >= USER_BLUNDER_CP:
                    user_blunder_moves += 1
                    if cap.strip():
                        user_blunder_captioned += 1

            for tag in _classify_suspect(mv):
                if len(suspect_examples[tag]) < args.samples_per_suspect:
                    suspect_examples[tag].append({
                        "game_id": game_id,
                        "move_no": mv.get("move_number"),
                        "side": "USER" if mv.get("is_user_move") else "OPP",
                        "move_san": mv.get("move_san"),
                        "cp_loss": mv.get("cp_loss"),
                        "rule_name": rule,
                        "caption": cap or "(silent)",
                    })

            # Teaching layer: aggregate principle firings.
            for pv_entry in (mv.get("caption_facts_principles_violated") or []):
                pid = pv_entry.get("principle_id") or "(unknown)"
                endorsement = pv_entry.get("engine_endorsement") or "(unknown)"
                principle_counts[pid] += 1
                principle_endorsement_counts[pid][endorsement] += 1
                if len(principle_samples[pid]) < args.samples_per_rule:
                    principle_samples[pid].append({
                        "game_id": game_id,
                        "move_no": mv.get("move_number"),
                        "side": "USER" if mv.get("is_user_move") else "OPP",
                        "move_san": mv.get("move_san"),
                        "cp_loss": mv.get("cp_loss"),
                        "endorsement": endorsement,
                        "evidence": pv_entry.get("evidence"),
                    })

        n_games_ok += 1
        if i % 10 == 0 or i == len(games):
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  [{i}/{len(games)}] {game_id}  ({rate:.1f} games/s)")

    elapsed = time.time() - t0

    # Build the report
    out_lines: List[str] = []
    out_lines.append("=" * 78)
    out_lines.append("V5 CAPTION PIPELINE — CORPUS AUDIT")
    out_lines.append("=" * 78)
    out_lines.append(f"games examined          : {len(games)}")
    out_lines.append(f"  succeeded             : {n_games_ok}")
    out_lines.append(f"  skipped (no data)     : {n_games_skipped}")
    out_lines.append(f"  failed                : {n_games_failed}")
    if args.write_db:
        out_lines.append(f"  written to DB         : {n_games_written}")
    out_lines.append(f"elapsed                 : {elapsed:.1f}s")
    out_lines.append("")
    out_lines.append(f"total move records      : {total_moves}")
    out_lines.append(f"silent moves            : {silent_moves}  "
                     f"({(silent_moves / total_moves * 100) if total_moves else 0:.1f}%)")
    out_lines.append(f"user moves              : {user_moves}")
    out_lines.append(f"  blunders (cpl≥100)    : {user_blunder_moves}")
    out_lines.append(f"  blunders captioned    : {user_blunder_captioned}  "
                     f"({(user_blunder_captioned / user_blunder_moves * 100) if user_blunder_moves else 0:.1f}%)")
    out_lines.append(f"distinct caption texts  : {len(caption_text_counts)}")
    out_lines.append("")

    out_lines.append("─" * 78)
    out_lines.append("RULE HISTOGRAM")
    out_lines.append("─" * 78)
    for rule, n in rule_counts.most_common():
        pct = (n / total_moves * 100) if total_moves else 0
        out_lines.append(f"  {rule:<34} {n:>6}  ({pct:.1f}%)")
    out_lines.append("")

    out_lines.append("─" * 78)
    out_lines.append("SUSPECTS (architecturally wrong-looking captions)")
    out_lines.append("─" * 78)
    if not suspect_examples:
        out_lines.append("  (none — corpus is clean)")
    for tag in sorted(suspect_examples):
        out_lines.append("")
        out_lines.append(f"  [{tag}]  count seen: {len(suspect_examples[tag])} "
                         f"(showing first {min(len(suspect_examples[tag]), args.samples_per_suspect)})")
        for ex in suspect_examples[tag]:
            out_lines.append(
                f"    {ex['game_id'][:8]}  m{ex['move_no']:>3} {ex['side']:<4} "
                f"{(ex['move_san'] or ''):<8} cpl={ex['cp_loss']:>5}  "
                f"{ex['rule_name']:<26} {_short(ex['caption'])}"
            )
    out_lines.append("")

    out_lines.append("─" * 78)
    out_lines.append("TEMPLATE REPETITION (caption texts seen ≥ 5 times)")
    out_lines.append("─" * 78)
    repeats = [(c, t) for t, c in caption_text_counts.most_common(50) if c >= 5]
    if not repeats:
        out_lines.append("  (no caption text repeats ≥5 times)")
    else:
        for c, t in repeats:
            out_lines.append(f"  {c:>4}× {_short(t, 70)}")
    out_lines.append("")

    out_lines.append("─" * 78)
    out_lines.append("RULE SAMPLES (a few non-silent captions per rule for spot-check)")
    out_lines.append("─" * 78)
    for rule in sorted(rule_examples):
        out_lines.append("")
        out_lines.append(f"  [{rule}]")
        for ex in rule_examples[rule]:
            out_lines.append(
                f"    {ex['game_id'][:8]}  m{ex['move_no']:>3} {ex['side']:<4} "
                f"{(ex['move_san'] or ''):<8} cpl={ex['cp_loss']:>5}  "
                f"{_short(ex['caption'])}"
            )
    out_lines.append("")

    # Teaching layer audit — one section per shipped detector. Empty
    # when no detector has fired yet (catalog text-only state).
    out_lines.append("─" * 78)
    out_lines.append("TEACHING LAYER — principle firing summary")
    out_lines.append("─" * 78)
    if not principle_counts:
        out_lines.append("  (no principle detectors enabled yet, or none fired in this run)")
    else:
        total_principle_firings = sum(principle_counts.values())
        out_lines.append(f"  total principle firings : {total_principle_firings}")
        out_lines.append(f"  firings per move record : "
                         f"{(total_principle_firings / total_moves * 100) if total_moves else 0:.2f}%")
        out_lines.append("")
        for pid, count in principle_counts.most_common():
            endorse = principle_endorsement_counts[pid]
            endorse_str = " · ".join(f"{tier}={n}" for tier, n in endorse.most_common())
            out_lines.append(f"  {pid:<34} {count:>5}   ({endorse_str})")
    out_lines.append("")

    out_lines.append("─" * 78)
    out_lines.append("PRINCIPLE SAMPLES (a few firings per principle for spot-check)")
    out_lines.append("─" * 78)
    if not principle_samples:
        out_lines.append("  (no principle firings to sample)")
    for pid in sorted(principle_samples):
        out_lines.append("")
        out_lines.append(f"  [{pid}]")
        for ex in principle_samples[pid]:
            out_lines.append(
                f"    {ex['game_id'][:8]}  m{ex['move_no']:>3} {ex['side']:<4} "
                f"{(ex['move_san'] or ''):<8} cpl={ex['cp_loss']:>5}  "
                f"endorsement={ex['endorsement']:<7} evidence={ex['evidence']}"
            )
    out_lines.append("")

    report = "\n".join(out_lines)
    if not args.quiet:
        print(report)

    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = (BACKEND_DIR.parent / args.output).resolve()
        out_path.write_text(report, encoding="utf-8")
        print(f"\n[wrote] {out_path}")

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
