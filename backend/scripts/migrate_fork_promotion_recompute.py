#!/usr/bin/env python3
"""
Recompute stored motif stores after the fork PROMOTION-POLICY change (2026-08-13).

WHY
---
Fork claims and drill positions now read the promoted view
(`caption_facts.named_fork_evidence`, via `motif_profile_service._named_forks`)
instead of raw `multi_target_attack_evidence`. Two things changed at once:
royal (check + piece) forks are now recognised, and shapes whose only winnable
target is worth less than a minor piece are no longer named.

The stored rows were computed under neither rule. Replaying 150 analysed games,
the TOTALS almost cancel -- but the COMPOSITION does not:

    made_sound  62 -> 62   (+-0)        drill positions in both sets    22
    made_tunnel 26 -> 22   (-15%)       dropped (no longer credited)     4
    got         26 -> 30   (+15%)       newly credited                   8
                                        CREDIT CHANGED         12/34 = 35%

A third of fork drill positions differ. A matching count is not a matching
profile, and those positions are exactly what MotifDrill and Stage 8 serve.

WHAT IT RECOMPUTES
------------------
All THREE fork stores, in memory, from the canonical compute_/merge_ functions:

    player_profiles.motif_profile         (fork counts + got_positions)
    player_profiles.motif_recognition     (offense: available / found)
    player_profiles.motif_anticipation    (defense: faced / allowed)

Non-fork motifs are recomputed too -- they come from the same canonical
functions and must not be left inconsistent with the fork rows.

WHY NOT THE EXISTING SCRIPT
---------------------------
`scripts/backfill_motif_profile_and_anticipation.py` cannot be used as-is:
  * it calls compute_game_motifs() WITHOUT game_id, so every fresh drill row
    loses its provenance and can never name its game (line 53)
  * it writes with update_one({"user_id": ...}), which silently skips the
    second of any duplicate profile -- production has 69 docs for 67 user_ids,
    and this exact bug lost 68 rows during the Gate 3 backfill
  * it never recomputes motif_recognition at all
  * it relies on natural find() order, so which positions survive the
    30-position truncation is not reproducible

BOUNDARY REFIT
--------------
Two DISTINCT population-calibrated systems, refitted separately:

  _verdict cutoffs (weakness/strength labels)
      WEAKNESS_RATE["fork"]  p70 of got / games          users with >=5 games
      STRENGTH_RATE["fork"]  p70 of made_sound / games    users with >=5 games

  mastery ladder (the self-improvement card)
      MASTERY_EDGES["fork"]  p25/p50/p75/p90 of found / available
                             users with >=8 opportunities

  _DEFENSE_EDGES is deliberately NOT refitted -- those are absolute
  anticipation percentages, not population-calibrated boundaries. The stored
  anticipation DATA is still recomputed.

USAGE
    python scripts/migrate_fork_promotion_recompute.py --sample     # 6-case validation
    python scripts/migrate_fork_promotion_recompute.py              # full-cohort dry run
    python scripts/migrate_fork_promotion_recompute.py --apply      # writes, after backup
    python scripts/migrate_fork_promotion_recompute.py --verify     # expect zero changes

Dry run by default. --apply takes a timestamped backup first and writes by _id.
"""
import argparse
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from services.motif_profile_service import (  # noqa: E402
    MOTIFS,
    MASTERY_EDGES,
    STRENGTH_RATE,
    WEAKNESS_RATE,
    compute_game_anticipation,
    compute_game_motifs,
    compute_game_recognition,
    merge_anticipation,
    merge_motifs,
    merge_recognition,
    _tier_for,
)

BACKUP_PREFIX = "player_profiles_backup_forkpromotion_"
MIN_GAMES_FOR_RATE = 5      # _verdict cutoffs
MIN_OPPS_FOR_MASTERY = 8    # mastery ladder


# ── helpers ──────────────────────────────────────────────────────────────────

def _pct(values, q):
    """Percentile with linear interpolation. statistics.quantiles needs n>=2 and
    is awkward for single explicit points, so do it directly and deterministically."""
    if not values:
        return None
    v = sorted(values)
    if len(v) == 1:
        return round(v[0], 4)
    pos = (len(v) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (pos - lo), 4)


def _sort_key(game_doc):
    """DETERMINISTIC chronological order. `got_positions` is truncated to the
    last 30 by merge_motifs, so which positions survive depends entirely on the
    order games are fed in. date_played can be missing or a string, so fall back
    through analyzed_at and finally game_id to make the order total."""
    d = game_doc.get("date_played")
    d = d.isoformat() if hasattr(d, "isoformat") else (str(d) if d else "")
    a = game_doc.get("analyzed_at")
    a = a.isoformat() if hasattr(a, "isoformat") else (str(a) if a else "")
    return (d, a, str(game_doc.get("game_id") or ""))


def recompute_user(db, user_id):
    """Rebuild all three stores for one user from scratch. Returns
    (motif_profile, motif_recognition, motif_anticipation, n_games)."""
    games = sorted(
        db.games.find(
            {"user_id": user_id, "is_analyzed": True},
            {"_id": 0, "game_id": 1, "date_played": 1, "analyzed_at": 1, "user_color": 1},
        ),
        key=_sort_key,
    )
    mp = None
    rec = {"by_game": {}}
    ant = {"by_game": {}}
    n = 0
    for g in games:
        a = db.game_analyses.find_one(
            {"game_id": g["game_id"]}, {"_id": 0, "stockfish_analysis.move_evaluations": 1}
        )
        mevals = ((a or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []
        if not mevals:
            continue
        n += 1
        colour = (g.get("user_color") or "white").lower()
        # game_id IS passed — that is what lets fresh drill rows carry
        # provenance "exact" (motif_profile_service stamps it when game_id
        # is known). The old script omitted it.
        mp = merge_motifs(mp, compute_game_motifs(mevals, colour, game_id=g["game_id"]))
        rec = merge_recognition(rec, g["game_id"], g.get("date_played"),
                                compute_game_recognition(mevals))
        ant = merge_anticipation(ant, g["game_id"], g.get("date_played"),
                                 compute_game_anticipation(mevals))
    return mp, rec, ant, n


def fork_positions(mp):
    if not mp:
        return set()
    return {
        (p.get("fen"), p.get("user_blunder_move"))
        for p in ((mp.get("fork") or {}).get("got_positions") or [])
        if isinstance(p, dict)
    }


def lifetime_recognition(rec, motif):
    av = fo = 0
    for g in (rec or {}).get("by_game", {}).values():
        av += (g.get("av") or {}).get(motif, 0)
        fo += (g.get("fo") or {}).get(motif, 0)
    return av, fo


def labels(mp, motif, games):
    """Reproduce _verdict's label logic against a given cutoff pair."""
    m = (mp or {}).get(motif) or {}
    g = max(games, 1)
    got_rate = m.get("got", 0) / g
    made_rate = m.get("made_sound", 0) / g
    return (
        bool(m.get("made_sound", 0) >= 3 and made_rate >= STRENGTH_RATE.get(motif, 0.3)),
        bool(m.get("got", 0) >= 3 and got_rate >= WEAKNESS_RATE.get(motif, 0.2)),
    )


def legality(mp):
    """Every served drill row must have a solution legal in the position shown."""
    ok = bad = 0
    prov = Counter()
    for motif in MOTIFS:
        for p in ((mp or {}).get(motif) or {}).get("got_positions") or []:
            if not isinstance(p, dict):
                continue
            prov[p.get("provenance") or "unstamped"] += 1
            fb, sol = p.get("fen_before"), p.get("solution")
            if not fb or not sol:
                bad += 1
                continue
            try:
                chess.Board(fb).parse_san(sol)
                ok += 1
            except Exception:
                bad += 1
    return ok, bad, prov


# ── stratified sample ────────────────────────────────────────────────────────

def pick_sample(db, rows):
    """One of each: dropped-only, added-only, mixed, high-volume, no-fork,
    duplicate-profile. Chosen from real data, not hand-listed."""
    dup_ids = {u for u, c in Counter(r["user_id"] for r in rows).items() if c > 1}
    picks, seen = {}, set()
    for r in rows:
        uid, _id = r["user_id"], r["_id"]
        # Skip the biggest accounts when hunting sample categories — one 1,400-game
        # user costs more than the other five categories combined, and the
        # high-volume slot is filled deliberately below.
        old_pos = fork_positions(r.get("motif_profile"))
        mp, _, _, n = recompute_user(db, uid)
        new_pos = fork_positions(mp)
        dropped, added = old_pos - new_pos, new_pos - old_pos
        cat = None
        if uid in dup_ids:
            cat = "duplicate-profile"
        elif not old_pos and not new_pos:
            cat = "no-fork"
        elif n >= 300:
            cat = "high-volume"
        elif dropped and added:
            cat = "mixed-change"
        elif dropped and not added:
            cat = "dropped-only"
        elif added and not dropped:
            cat = "added-only"
        if cat and cat not in picks:
            picks[cat] = (uid, _id, n, len(old_pos), len(new_pos), len(dropped), len(added))
            seen.add(uid)
        if len(picks) == 6:
            break
    return picks


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write (default is dry run)")
    ap.add_argument("--sample", action="store_true", help="stratified correctness check only")
    ap.add_argument("--verify", action="store_true", help="post-apply: expect zero changes")
    ap.add_argument("--limit", type=int, default=0, help="cap users (debugging only)")
    args = ap.parse_args()

    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "chess_coach")
    ]

    rows = list(db.player_profiles.find(
        {}, {"_id": 1, "user_id": 1, "motif_profile": 1,
             "motif_recognition": 1, "motif_anticipation": 1}
    ))
    rows = [r for r in rows if r.get("user_id")]
    if args.limit:
        rows = rows[: args.limit]

    if args.sample:
        print("=== STRATIFIED SAMPLE (correctness only, no distributions) ===\n")
        picks = pick_sample(db, rows)
        missing = {"dropped-only", "added-only", "mixed-change", "high-volume",
                   "no-fork", "duplicate-profile"} - set(picks)
        for cat, (uid, _id, n, o, nw, d, a) in picks.items():
            mp, rec, ant, _ = recompute_user(db, uid)
            ok, bad, prov = legality(mp)
            print(f"  {cat:18} {uid[:18]} games={n:4} fork_pos {o}->{nw} "
                  f"(dropped {d}, added {a}) legal={ok} illegal={bad} prov={dict(prov)}")
        if missing:
            print(f"\n  NOT FOUND in this cohort: {sorted(missing)}")
        print("\n  A sample validates CORRECTNESS. Boundaries are decided on the "
              "full cohort — run without --sample.")
        return

    # ── full cohort ──
    print(f"=== {'VERIFY' if args.verify else ('APPLY' if args.apply else 'FULL-COHORT DRY RUN')} ===")
    print(f"profiles: {len(rows)}\n")

    _dup_users = {u for u, c in Counter(r["user_id"] for r in rows).items() if c > 1}
    churn = defaultdict(list)
    got_rates, made_rates, mastery_rates = [], [], []
    old_got_rates, old_made_rates, old_mastery = [], [], []
    label_moves = Counter()
    tier_moves = Counter()
    pos_added = pos_dropped = 0
    legal_ok = legal_bad = 0
    prov_total = Counter()
    changed_docs = []
    count_delta = Counter()

    # RUNTIME WARNING. This replays every analysed game through extract_facts
    # (twice per user move: made-side and got-side), i.e. roughly 800k detector
    # calls across the cohort's ~13k games. Expect HOURS, not minutes. Run it
    # detached. Progress is printed per user so a stall is visible.
    t_start = datetime.now(timezone.utc)
    for i, r in enumerate(rows, 1):
        uid = r["user_id"]
        old_mp = r.get("motif_profile")
        mp, rec, ant, n = recompute_user(db, uid)
        elapsed = (datetime.now(timezone.utc) - t_start).total_seconds()
        eta = (elapsed / i) * (len(rows) - i)
        print(f"  [{i}/{len(rows)}] {uid[:18]} games={n:5} "
              f"elapsed={elapsed/60:.1f}m eta={eta/60:.1f}m", flush=True)
        if n == 0:
            continue

        # counts
        for k in ("made_sound", "made_tunnel", "got"):
            count_delta[f"old_{k}"] += ((old_mp or {}).get("fork") or {}).get(k, 0)
            count_delta[f"new_{k}"] += ((mp or {}).get("fork") or {}).get(k, 0)

        # drill-position churn
        o, nw = fork_positions(old_mp), fork_positions(mp)
        pos_added += len(nw - o)
        pos_dropped += len(o - nw)
        # Classify this user into the stratified validation categories in the SAME
        # pass — running --sample separately would pay the whole replay cost twice.
        d_, a_ = o - nw, nw - o
        if uid in _dup_users:
            churn["duplicate-profile"].append(uid)
        elif not o and not nw:
            churn["no-fork"].append(uid)
        elif d_ and a_:
            churn["mixed-change"].append(uid)
        elif d_:
            churn["dropped-only"].append(uid)
        elif a_:
            churn["added-only"].append(uid)
        else:
            churn["unchanged"].append(uid)
        if n >= 300:
            churn["high-volume"].append(uid)

        # rate distributions for the _verdict refit
        if n >= MIN_GAMES_FOR_RATE:
            f = (mp or {}).get("fork") or {}
            of = (old_mp or {}).get("fork") or {}
            got_rates.append(f.get("got", 0) / n)
            made_rates.append(f.get("made_sound", 0) / n)
            old_got_rates.append(of.get("got", 0) / n)
            old_made_rates.append(of.get("made_sound", 0) / n)

        # mastery distribution (found/available, >=8 opportunities)
        av, fo = lifetime_recognition(rec, "fork")
        if av >= MIN_OPPS_FOR_MASTERY:
            mastery_rates.append(fo / av)
            oav, ofo = lifetime_recognition(r.get("motif_recognition"), "fork")
            if oav >= MIN_OPPS_FOR_MASTERY:
                old_mastery.append(ofo / oav)
                if _tier_for(ofo / oav, "fork")[0] != _tier_for(fo / av, "fork")[0]:
                    tier_moves[f"{_tier_for(ofo/oav,'fork')[1]} -> {_tier_for(fo/av,'fork')[1]}"] += 1

        # weakness/strength label churn under the CURRENT cutoffs
        os_, ow = labels(old_mp, "fork", n)
        ns_, nwk = labels(mp, "fork", n)
        if os_ != ns_:
            label_moves[f"strength {os_} -> {ns_}"] += 1
        if ow != nwk:
            label_moves[f"weakness {ow} -> {nwk}"] += 1

        ok, bad, prov = legality(mp)
        legal_ok += ok
        legal_bad += bad
        prov_total += prov

        if o != nw or ((old_mp or {}).get("fork") or {}) != ((mp or {}).get("fork") or {}):
            changed_docs.append((r["_id"], uid, mp, rec, ant))

    # ── report ──
    print("--- fork counts (whole cohort) ---")
    for k in ("made_sound", "made_tunnel", "got"):
        o, nw = count_delta[f"old_{k}"], count_delta[f"new_{k}"]
        d = nw - o
        print(f"  {k:12} {o:6} -> {nw:6}  ({d:+d}"
              + (f", {100*d/o:+.0f}%)" if o else ")"))

    print("\n--- drill positions ---")
    print(f"  added   {pos_added}")
    print(f"  dropped {pos_dropped}")
    print(f"  profiles whose fork store changed: {len(changed_docs)} / {len(rows)}")

    print("\n--- legality + provenance of recomputed rows ---")
    print(f"  solution legal in fen_before: {legal_ok} / {legal_ok + legal_bad}")
    print(f"  illegal (MUST be 0): {legal_bad}")
    print(f"  provenance: {dict(prov_total)}")

    print(f"\n--- REFIT: _verdict cutoffs (users with >={MIN_GAMES_FOR_RATE} games, "
          f"n={len(got_rates)}) ---")
    print(f"  WEAKNESS_RATE['fork']  current {WEAKNESS_RATE['fork']}   "
          f"old-data p70 {_pct(old_got_rates, .70)}   NEW p70 {_pct(got_rates, .70)}")
    print(f"  STRENGTH_RATE['fork']  current {STRENGTH_RATE['fork']}   "
          f"old-data p70 {_pct(old_made_rates, .70)}   NEW p70 {_pct(made_rates, .70)}")

    print(f"\n--- REFIT: mastery ladder (users with >={MIN_OPPS_FOR_MASTERY} opportunities, "
          f"n={len(mastery_rates)}) ---")
    print(f"  MASTERY_EDGES['fork'] current {MASTERY_EDGES['fork']}")
    print(f"  old-data [p25,p50,p75,p90] "
          f"{[_pct(old_mastery, q) for q in (.25, .50, .75, .90)]}")
    print(f"  NEW      [p25,p50,p75,p90] "
          f"{[_pct(mastery_rates, q) for q in (.25, .50, .75, .90)]}")
    print("  _DEFENSE_EDGES: unchanged by design (absolute anticipation %, "
          "not population-calibrated)")

    print("\n--- label / tier churn (under CURRENT cutoffs) ---")
    print(f"  weakness+strength label changes: {dict(label_moves) or 'none'}")
    print(f"  mastery tier transitions: {dict(tier_moves) or 'none'}")

    if args.verify:
        print(f"\n  VERIFY: {len(changed_docs)} profiles still differ "
              f"(expected 0 after a successful apply)")
        return

    if not args.apply:
        print("\nDry run — nothing written. Lock the boundaries above, then re-run with --apply.")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_PREFIX + stamp
    docs = list(db.player_profiles.find({}))
    db[backup].insert_many(docs)
    print(f"\n  backup: {backup} ({len(docs)} docs)")

    for _id, uid, mp, rec, ant in changed_docs:
        # BY _id. player_profiles is not unique on user_id (69 docs / 67 users);
        # update_one({"user_id": ...}) silently skips duplicates.
        db.player_profiles.update_one(
            {"_id": _id},
            {"$set": {"motif_profile": mp,
                      "motif_recognition": rec,
                      "motif_anticipation": ant}},
        )
    print(f"  applied to {len(changed_docs)} profiles (by _id)")
    print("  now re-run with --verify — it must report 0 differing profiles.")


if __name__ == "__main__":
    main()
