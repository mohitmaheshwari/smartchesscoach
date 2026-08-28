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
    MIN_OPPS_TO_SHOW,
    MOTIFS,
    TIER_NAMES,
    _defense_tier,
    anticipation_rates,
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


def fork_only(new_store, old_store, key="fork"):
    """Return `old_store` with ONLY the fork slice replaced.

    The canonical compute_ functions must run over every motif -- they are
    all-or-nothing -- but pin/skewer ATTRIBUTION is known unreliable (29% and
    14% of their events pre-existed the move), so this migration must not
    quietly restate them as freshly verified. Non-fork values stay
    byte-for-byte identical to what is already stored.
    """
    out = dict(old_store or {})
    if new_store and key in new_store:
        out[key] = new_store[key]
    return out


def fork_only_by_game(new_bg, old_bg, key="fork"):
    """Same idea for the per-game stores: replace ONLY the fork counter inside
    each game entry, preserving every other motif's stored value and any game
    entries the recompute did not produce."""
    out = {"by_game": dict((old_bg or {}).get("by_game") or {})}
    for gid, entry in ((new_bg or {}).get("by_game") or {}).items():
        merged = dict(out["by_game"].get(gid) or {})
        merged["date"] = entry.get("date", merged.get("date"))
        for bucket in ("av", "fo", "faced", "allowed"):
            if bucket in entry:
                cur = dict(merged.get(bucket) or {})
                cur[key] = (entry.get(bucket) or {}).get(key, 0)
                merged[bucket] = cur
        out["by_game"][gid] = merged
    return out


def labels(mp, motif, games):
    """Reproduce _verdict's label logic EXACTLY, including the sound_rate gate.

    An earlier version omitted `sound_rate >= 0.7`, so its "strength" churn was
    not the user-visible result -- it counted users who clear the rate bar but
    fail the clean-execution bar and are therefore never shown a strength."""
    m = (mp or {}).get(motif) or {}
    g = max(games, 1)
    made_total = m.get("made_sound", 0) + m.get("made_tunnel", 0)
    sound_rate = (m.get("made_sound", 0) / made_total) if made_total else None
    got_rate = m.get("got", 0) / g
    made_rate = m.get("made_sound", 0) / g
    is_strength = (
        m.get("made_sound", 0) >= 3
        and made_rate >= STRENGTH_RATE.get(motif, 0.3)
        and (sound_rate is None or sound_rate >= 0.7)
    )
    is_weakness = m.get("got", 0) >= 3 and got_rate >= WEAKNESS_RATE.get(motif, 0.2)
    return bool(is_strength), bool(is_weakness)


def displayed_tier(rec, ant, motif="fork", edges=None):
    """The tier the USER actually sees: the WEAKER of attack and defense, and
    only when lifetime opportunities clear MIN_OPPS_TO_SHOW.

    An earlier version reported the attack tier alone and ignored the
    visibility gate, so it both mis-stated the level and missed users crossing
    into (or out of) being shown a row at all.

    Returns None when the row is not displayed.
    """
    av, fo = lifetime_recognition(rec, motif)
    if av < MIN_OPPS_TO_SHOW:
        return None
    rate = fo / av
    off_idx = _tier_for_edges(rate, motif, edges)
    def_rate = (anticipation_rates(ant).get(motif) or {}).get("rate")
    def_idx = _defense_tier(def_rate)[0] if def_rate is not None else None
    return def_idx if (def_idx is not None and def_idx < off_idx) else off_idx


def _tier_for_edges(rate, motif, edges=None):
    """_tier_for with substitutable edges, so a CANDIDATE boundary set can be
    scored without mutating the module constant."""
    if edges is None:
        return _tier_for(rate, motif)[0]
    p25, med, p75, p90 = edges
    e = [0.0, p25, med, p75, p90, p90 + 0.15]
    for i in range(5):
        if rate < e[i + 1]:
            return i
    return 4


def legality(mp, only=None):
    """Every served drill row must have a solution legal in the position shown.

    `only` restricts to one motif so the report can distinguish FORK rows (the
    ones this migration actually rewrites) from all-motif rows (which it leaves
    byte-for-byte alone). Reporting them together would let a clean fork result
    hide behind untouched pin/skewer rows, or vice versa.
    """
    ok = bad = 0
    prov = Counter()
    for motif in ([only] if only else MOTIFS):
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
    store_changed = Counter()
    tier_inputs = []
    got_rates, made_rates, mastery_rates = [], [], []
    old_got_rates, old_made_rates, old_mastery = [], [], []
    label_moves = Counter()
    tier_moves = Counter()
    pos_added = pos_dropped = 0
    legal_ok = legal_bad = 0
    prov_total = Counter()
    all_ok = all_bad = 0
    all_prov = Counter()
    changed_docs = []
    count_delta = Counter()

    # RUNTIME WARNING. This replays every analysed game through extract_facts
    # (twice per user move: made-side and got-side), i.e. roughly 800k detector
    # calls across the cohort's ~13k games. Expect HOURS, not minutes. Run it
    # detached. Progress is printed per user so a stall is visible.
    # ANALYTICS ONCE PER UNIQUE USER. player_profiles holds 69 docs for 67
    # user_ids, so iterating documents let duplicated users influence every
    # percentile twice. Persistence still targets EVERY matching _id.
    by_user = defaultdict(list)
    for r in rows:
        by_user[r["user_id"]].append(r)
    _dups = sum(1 for v in by_user.values() if len(v) > 1)
    print(f"documents: {len(rows)}   unique users: {len(by_user)}   duplicated: {_dups}")
    print()

    t_start = datetime.now(timezone.utc)
    # ETA must be GAMES-weighted, not per-user. Users differ by ~700x (median ~50
    # games, max 1442) and the biggest ones tend to sort first, so a per-user
    # linear ETA over-predicts wildly then collapses -- it read "196m" at user 1
    # and "82m" at user 4 on a run that actually takes ~51m.
    total_games = db.games.count_documents({"is_analyzed": True})
    games_done = 0
    for i, (uid, docs) in enumerate(by_user.items(), 1):
        r = docs[0]                      # analytics use ONE doc per user
        old_mp = r.get("motif_profile")
        mp_all, rec_all, ant_all, n = recompute_user(db, uid)
        # FORK-ONLY projection. Everything else stays exactly as stored.
        mp = fork_only(mp_all, old_mp)
        rec = fork_only_by_game(rec_all, r.get("motif_recognition"))
        ant = fork_only_by_game(ant_all, r.get("motif_anticipation"))
        games_done += n
        elapsed = (datetime.now(timezone.utc) - t_start).total_seconds()
        rate = games_done / elapsed if elapsed else 0
        eta = (total_games - games_done) / rate if rate else 0
        print(f"  [{i}/{len(by_user)}] {uid[:18]} games={n:5} "
              f"({games_done}/{total_games}) elapsed={elapsed/60:.1f}m "
              f"eta={eta/60:.1f}m @{rate*60:.0f} games/min", flush=True)
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
        oav, _ofo = lifetime_recognition(r.get("motif_recognition"), "fork")
        if oav >= MIN_OPPS_FOR_MASTERY:
            old_mastery.append(_ofo / oav)
        # DISPLAYED tier churn: weaker of attack/defense, and crossing the
        # MIN_OPPS_TO_SHOW visibility gate counts as a change the user sees.
        old_t = displayed_tier(r.get("motif_recognition"), r.get("motif_anticipation"))
        new_t = displayed_tier(rec, ant)
        if old_t != new_t:
            nm = lambda t: "(not shown)" if t is None else TIER_NAMES[t]
            tier_moves[f"{nm(old_t)} -> {nm(new_t)}"] += 1
        tier_inputs.append((rec, ant, r.get("motif_recognition"), r.get("motif_anticipation")))

        # weakness/strength label churn under the CURRENT cutoffs
        os_, ow = labels(old_mp, "fork", n)
        ns_, nwk = labels(mp, "fork", n)
        if os_ != ns_:
            label_moves[f"strength {os_} -> {ns_}"] += 1
        if ow != nwk:
            label_moves[f"weakness {ow} -> {nwk}"] += 1

        ok, bad, prov = legality(mp, only="fork")
        legal_ok += ok
        legal_bad += bad
        prov_total += prov
        aok, abad, aprov = legality(mp)
        all_ok += aok
        all_bad += abad
        all_prov += aprov

        # Compare ALL THREE stores in full, not just motif_profile.fork.
        # An earlier version keyed only on the fork sub-dict, which meant a
        # document whose motif_recognition or motif_anticipation changed while
        # its fork profile happened not to would never be written -- and
        # --verify would then report "0 differences" while those two stores sat
        # stale. motif_recognition is what drives the mastery ladder being
        # refitted here, so that failure mode is directly load-bearing. The
        # non-fork motifs are recomputed too and must not be left inconsistent.
        if (
            (old_mp or {}) != (mp or {})
            or (r.get("motif_recognition") or {"by_game": {}}) != rec
            or (r.get("motif_anticipation") or {"by_game": {}}) != ant
        ):
            # EVERY document for this user, not just the one analytics used.
            for d in docs:
                changed_docs.append((d["_id"], uid, mp, rec, ant))
            store_changed["motif_profile"] += int((old_mp or {}) != (mp or {}))
            store_changed["motif_recognition"] += int(
                (r.get("motif_recognition") or {"by_game": {}}) != rec)
            store_changed["motif_anticipation"] += int(
                (r.get("motif_anticipation") or {"by_game": {}}) != ant)

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
    print(f"  profiles needing a write: {len(changed_docs)} / {len(rows)}")
    print(f"  by store: {dict(store_changed)}")

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

    # ── ROUNDING CHECK ───────────────────────────────────────────────────
    # Prefer readable two-decimal constants, but only if rounding changes
    # nothing a user sees. Score exact vs rounded on the SAME recomputed data.
    exact_w, exact_s = _pct(got_rates, .70), _pct(made_rates, .70)
    exact_m = [_pct(mastery_rates, q) for q in (.25, .50, .75, .90)]
    round_w, round_s = round(exact_w or 0, 2), round(exact_s or 0, 2)
    round_m = [round(x, 2) for x in exact_m if x is not None]

    w_flips = sum(1 for v in got_rates if (v >= exact_w) != (v >= round_w))
    s_flips = sum(1 for v in made_rates if (v >= exact_s) != (v >= round_s))
    t_flips = 0
    for rec_n, ant_n, _ro, _ao in tier_inputs:
        if displayed_tier(rec_n, ant_n, edges=exact_m) !=            displayed_tier(rec_n, ant_n, edges=round_m):
            t_flips += 1

    print("\n--- ROUNDING: exact vs two-decimal candidates ---")
    print(f"  WEAKNESS  exact {exact_w}  rounded {round_w}   label flips: {w_flips}")
    print(f"  STRENGTH  exact {exact_s}  rounded {round_s}   label flips: {s_flips}")
    print(f"  MASTERY   exact {exact_m}")
    print(f"            rounded {round_m}                    tier flips: {t_flips}")
    if w_flips == s_flips == t_flips == 0:
        print(f"  -> ROUNDING IS SAFE. Store the readable values: "
              f"{round_w}, {round_s}, {round_m}")
    else:
        print("  -> rounding changes user-visible output; keep the EXACT values")

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

    matched = modified = 0
    for _id, uid, mp, rec, ant in changed_docs:
        # BY _id. player_profiles is not unique on user_id (69 docs / 67 users);
        # update_one({"user_id": ...}) silently skips duplicates.
        res = db.player_profiles.update_one(
            {"_id": _id},
            {"$set": {"motif_profile": mp,
                      "motif_recognition": rec,
                      "motif_anticipation": ant}},
        )
        matched += res.matched_count
        modified += res.modified_count
    print(f"  applied to {len(changed_docs)} profiles (by _id): "
          f"matched={matched} modified={modified}")
    if matched != len(changed_docs):
        print(f"  FAIL: {len(changed_docs) - matched} intended writes did not match a document")
        sys.exit(1)
    print("  now re-run with --verify — it must report 0 differing profiles.")


if __name__ == "__main__":
    main()
