"""motif_profile_service.py — two-sided per-user tactical-motif profile (2026-06-21).

Diagnoses, per motif, whether the user FINDS it (strength), keeps WALKING INTO it
(weakness), or MADE it but blundered (tunnel vision) — the diagnosis half of the
coaching loop (docs/motif_profile_scope.md). The weakness positions are captured so
the practice layer can drill that motif from the user's own games.

LOAD-BEARING RULE: geometry is never credited without the move-quality gate, and the
GEOMETRY itself comes from the verified, winnability-checked detector
(caption_facts.multi_target_attack_evidence) on BOTH sides — symmetric, single-source.
Audited 2026-06-21: made-side consolidated (old heuristic was 96% FP); got-side via the
same detector on the opponent's reply = 86% independently-confirmed (the loose
opp_reply_creates_fork was 45%, rejected).

Phase 1: FORK only (audited). pin/skewer/discovered follow once each is audited clean.
"""
from typing import Dict, List, Any, Optional
import chess

# Move-quality gates (cp_loss). Lock thresholds via /lock-via-data after a corpus histogram.
SOUND_CP = 40      # <= this: the motif move was good → strength
BLUNDER_CP = 100   # >= this: a real blunder → tunnel-vision (made) / got-forked (allowed)

# 2026-07-07: added "discovered" (audit gate lifted after 4.59% probe rate
# on 5,290 moves — ideal motif frequency) and "loose" (Stockfish-PV-gated
# loose-piece events — 1.83% defensive, ~49% offensive recognition rate).
# See docs/motif_profile_backlog.md "Scope — discovered-attack + loose-piece"
# section for the data lock and design decisions.
MOTIFS = ["fork", "pin", "skewer", "discovered", "loose"]
SKEWER_GAP_CP = 150  # front must be a real piece more valuable than rear (not B-over-N)


def _move_captures_loose(fen_before: str, move_san: str) -> bool:
    """True if `move_san` captures an enemy piece that had ZERO defenders in
    board_before. The atomic offensive-loose-piece primitive — mirrors the
    "did you spot the free enemy piece?" question my probe measured.

    Kings excluded (they can't be "loose"). Pawns included — a hanging pawn
    is a real material win at 600-1500.
    """
    try:
        board = chess.Board(fen_before)
        own_color = board.turn
        mv = board.parse_san(move_san)
        captured_sq = mv.to_square
        piece = board.piece_at(captured_sq)
        if not piece or piece.color == own_color or piece.piece_type == chess.KING:
            return False
        opp_color = not own_color
        defenders = board.attackers(opp_color, captured_sq)
        return not defenders
    except Exception:
        return False


def _pv_captures_own_loose(fen_after: str, pv_first_san: str) -> bool:
    """DEFENSIVE loose primitive: after the user's move (board = `fen_after`),
    does the opponent's PV first reply capture an OWN (user's) piece that had
    zero defenders? Same shape as `_move_captures_loose` but for the mirror
    side. Kings excluded.
    """
    try:
        board = chess.Board(fen_after)
        opp_color = board.turn  # opponent is about to move
        own_color = not opp_color
        mv = board.parse_san(pv_first_san)
        captured_sq = mv.to_square
        piece = board.piece_at(captured_sq)
        if not piece or piece.color != own_color or piece.piece_type == chess.KING:
            return False
        defenders = board.attackers(own_color, captured_sq)
        return not defenders
    except Exception:
        return False


def _classify_aligned(aligned) -> set:
    """Pin / skewer from the verified aligned_pieces geometry. Audited 2026-06-21:
    pin 100%, skewer 87% (after the value-gap gate that drops near-equal 'skewers').
    pin = cheaper front stuck in front of a more valuable rear (absolute if rear=king,
    or relative when the front can't slide off the line). skewer = clearly more valuable
    front forced to move, exposing the rear. front=king is a check, not pin/skewer."""
    out = set()
    for a in aligned or []:
        if a.get("front_is_king"):
            continue
        rel = a.get("front_value_vs_rear")
        if rel == "lower" and (a.get("rear_is_king") or not a.get("front_can_move_along_line")):
            out.add("pin")
        elif rel == "higher" and (int(a.get("front_piece_value_cp", 0)) - int(a.get("rear_piece_value_cp", 0))) >= SKEWER_GAP_CP:
            out.add("skewer")
    return out


def _empty_motif() -> Dict[str, Any]:
    return {"made_sound": 0, "made_tunnel": 0, "got": 0, "got_positions": []}


def merge_motifs(stored: Optional[Dict[str, Dict]], game: Dict[str, Dict],
                 keep_positions: int = 30) -> Dict[str, Dict]:
    """Incrementally add one game's motif tallies into the stored running totals (so the
    analysis worker doesn't re-read every game). Stores RAW totals; the verdict is applied
    at read time so thresholds can change without re-aggregating."""
    out = stored or {m: _empty_motif() for m in MOTIFS}
    for mt in MOTIFS:
        s = out.setdefault(mt, _empty_motif())
        g = game.get(mt, _empty_motif())
        for k in ("made_sound", "made_tunnel", "got"):
            s[k] = int(s.get(k, 0)) + int(g.get(k, 0))
        s["got_positions"] = (list(s.get("got_positions", [])) + list(g.get("got_positions", [])))[-keep_positions:]
    return out


def compute_game_motifs(move_evaluations: List[Dict], user_color: Optional[str] = None) -> Dict[str, Dict]:
    """Tally a single game's motif signals from the USER's moves, using the verified
    geometry detector on both sides. Pure fn over stored move_evaluations (user moves
    identified by is_opponent_move, so user_color is unused — kept for call-site compat)."""
    from services.caption_facts import extract_facts
    out = {m: _empty_motif() for m in MOTIFS}
    for ev in move_evaluations or []:
        if ev.get("is_opponent_move"):
            continue
        fen = ev.get("fen_before")
        fen_after = ev.get("fen_after")
        played = ev.get("move")
        best = ev.get("best_move")
        if not (fen and played):
            continue
        cp = abs(int(ev.get("cp_loss") or 0))
        pv = ev.get("pv_after_played") or []

        # MADE side (user's own move): fork (winnability-checked) + pin/skewer
        # (aligned geom) + discovered attack (uncovered ray) + loose-piece capture
        # (direct board check).
        try:
            mf = extract_facts(fen_before=fen, played_san=played, best_move_san=best,
                               cp_loss=cp, pv_after_played=pv, mover_is_user=True)
            made = set()
            if mf.get("multi_target_attack_evidence"):
                made.add("fork")
            made |= _classify_aligned(mf.get("aligned_pieces_evidence"))
            if mf.get("discovered_attack_evidence"):
                made.add("discovered")
        except Exception:
            made = set()
        # Loose-capture is a direct board check, outside the extract_facts try —
        # keeps loose signal alive even if caption_facts throws on a weird FEN.
        if _move_captures_loose(fen, played):
            made.add("loose")
        for mt in made:
            out[mt]["made_sound" if cp <= SOUND_CP else "made_tunnel"] += 1

        # GOT side: the user's move was a blunder whose engine reply creates the motif
        # against the user (same verified detectors, applied to the opponent's reply).
        # Drill teaches: "in this position, avoid the blunder that lets opponent create the motif"
        # Store: position before user's move (fen) + best move (what user should play instead)
        # + opponent's creating move (so UI can show "see how they create it")
        if fen_after and pv and cp >= BLUNDER_CP:
            try:
                gf = extract_facts(fen_before=fen_after, played_san=pv[0],
                                   cp_loss=0, mover_is_user=False)
                got = set()
                if gf.get("multi_target_attack_evidence"):
                    got.add("fork")
                got |= _classify_aligned(gf.get("aligned_pieces_evidence"))
                if gf.get("discovered_attack_evidence"):
                    got.add("discovered")
            except Exception:
                got = set()
            # Loose-defensive: does the opp PV first move capture an own
            # loose piece? Direct board check, not via caption_facts.
            if _pv_captures_own_loose(fen_after, pv[0]):
                got.add("loose")
            for mt in got:
                out[mt]["got"] += 1
                # Store position AFTER user's blunder but BEFORE opponent replies
                # This way opp_creates_motif move is playable in this FEN
                out[mt]["got_positions"].append({
                    "fen": fen_after,  # position after user's blunder, ready for opponent's move
                    "solution": best,  # what user should have played instead
                    "user_blunder_move": played,  # the blunder move that led here
                    "opp_creates_motif": pv[0]  # opponent's reply that creates the motif (NOW LEGAL)
                })
    return out


# Lock-via-data (2026-06-22): per-motif p70 of the got/made-per-game distribution over 53
# users (>=5 games). Relative thresholds — "you walk into X MORE than most players" — so the
# card flags each user's standout ~30%, not everyone-on-everything. Pins/skewers are
# inherently more common than forks, hence per-motif cutoffs.
#
# 2026-07-07: discovered/loose defaults are PROVISIONAL — derived from the
# 8-user probe (5,290 moves) as starting points. Formal p70 population lock
# happens after the first full-cohort backfill produces distributions.
#   discovered got:  ~0.05 events/game observed, use 0.20 (parity with fork)
#   discovered made: ~4.6% of moves, ~0.30/game, use 0.35 for strength
#   loose got:       ~1.8% of moves, ~0.60/game, use 0.40 for weakness
#   loose made:      ~49% recognition of ~0.65 opps/game, use 0.30 for strength
WEAKNESS_RATE = {"fork": 0.18, "pin": 0.30, "skewer": 0.26,
                 "discovered": 0.20, "loose": 0.40}   # got per game
STRENGTH_RATE = {"fork": 0.26, "pin": 0.77, "skewer": 0.69,
                 "discovered": 0.35, "loose": 0.30}   # made_sound per game


def _verdict(m: Dict[str, Any], games: int, motif: str) -> Dict[str, Any]:
    """Strength/weakness verdict, RATE-based vs the population per motif (lock-via-data)."""
    made = m["made_sound"] + m["made_tunnel"]
    sound_rate = (m["made_sound"] / made) if made else None
    g = max(1, games)
    got_rate = m["got"] / g
    made_rate = m["made_sound"] / g
    return {
        **{k: m[k] for k in ("made_sound", "made_tunnel", "got")},
        "sound_rate": round(sound_rate, 2) if sound_rate is not None else None,
        # strength: you make this motif soundly MORE than most + clean execution
        "is_strength": (m["made_sound"] >= 3 and made_rate >= STRENGTH_RATE.get(motif, 0.3)
                        and (sound_rate is None or sound_rate >= 0.7)),
        # weakness: you walk into it MORE than most players (top ~30%), real & recurring
        "is_weakness": m["got"] >= 3 and got_rate >= WEAKNESS_RATE.get(motif, 0.2),
        "drill_positions": m["got_positions"][:20],
    }


# General per-motif reminder for the profile card (distinct from per-position captions —
# this is the "remember this about forks" line on the diagnosis card). Audience 600-1500.
MOTIF_LESSON = {
    "fork": {
        "strength": "You spot forks well — keep hunting for one move that hits two pieces at once.",
        "weakness": "Before each move, scan: can one enemy piece (knights especially) hit two of yours at once? That's the fork you keep walking into.",
    },
    "pin": {
        "strength": "You use pins well — keep looking to freeze an enemy piece against a bigger one behind it.",
        "weakness": "Watch your lines: don't let a piece get stuck in front of your king or queen on the same rank, file, or diagonal — that's the pin catching you.",
    },
    "skewer": {
        "strength": "You find skewers well — keep lining up their big piece with a smaller one behind it.",
        "weakness": "Don't line up a valuable piece in front of a smaller one — when it's attacked and must move, the piece behind falls. That's the skewer.",
    },
    "discovered": {
        "strength": "You use discovered attacks well — moving one piece uncovers another's attack. Keep looking for this pattern.",
        "weakness": "Before moving a piece that stands between yours and theirs, check what's BEHIND you on that line. Moving it can uncover a hit on your own piece.",
    },
    "loose": {
        "strength": "You spot free pieces well — you take undefended enemy pieces cleanly.",
        "weakness": "Before every move, scan your pieces: which one has NO defender? Those are the ones that get taken. Loose pieces drop off.",
    },
}
MOTIF_LABEL = {"fork": "Forks", "pin": "Pins", "skewer": "Skewers",
               "discovered": "Discovered attacks", "loose": "Loose pieces"}


def render_motif_card(motif_profile_raw: Optional[Dict[str, Dict]], games: int = 0) -> Dict[str, Any]:
    """Verdict-applied card data: strengths (you find it) + weaknesses (you walk into it,
    with a lesson + a motif-tagged drill link). The diagnose→lesson→drill loop. `games` =
    the user's analyzed-game count, for the rate-based (lock-via-data) verdict."""
    motifs = motif_profile_raw or {}
    strengths, weaknesses = [], []
    for mt in MOTIFS:
        v = _verdict(motifs.get(mt, _empty_motif()), games, mt)
        if v["is_strength"]:
            strengths.append({"motif": mt, "label": MOTIF_LABEL.get(mt, mt),
                              "made_sound": v["made_sound"], "lesson": MOTIF_LESSON[mt]["strength"]})
        if v["is_weakness"]:
            weaknesses.append({"motif": mt, "label": MOTIF_LABEL.get(mt, mt),
                               "got": v["got"], "tunnel": v["made_tunnel"],
                               "lesson": MOTIF_LESSON[mt]["weakness"],
                               "drill_count": len(v["drill_positions"]),
                               "drill_pattern": mt})  # → /training/pattern/{mt}, own-then-community
    return {"strengths": strengths, "weaknesses": weaknesses}


def position_allows_motif(ev: Dict) -> Optional[str]:
    """For a user blunder eval, which motif did the move WALK INTO (via the opponent's
    verified reply)? Returns 'fork'/'pin'/'skewer'/'discovered'/'loose' or None. Used to
    motif-tag extracted puzzles so weakness drills filter by motif — SAME verified detector
    as the profile's got-side, so the tag and the diagnosis never disagree.

    Priority order when multiple fire on the same position: fork > pin > skewer >
    discovered > loose. Fork is highest-teaching-value (creates two threats),
    loose is lowest (one piece drops). Only one motif tag per position.
    """
    from services.caption_facts import extract_facts
    fa = ev.get("fen_after")
    pv = ev.get("pv_after_played") or []
    if not (fa and pv and abs(int(ev.get("cp_loss") or 0)) >= BLUNDER_CP):
        return None
    try:
        gf = extract_facts(fen_before=fa, played_san=pv[0], cp_loss=0, mover_is_user=False)
        if gf.get("multi_target_attack_evidence"):
            return "fork"
        aligned = _classify_aligned(gf.get("aligned_pieces_evidence"))
        if "pin" in aligned:
            return "pin"
        if "skewer" in aligned:
            return "skewer"
        if gf.get("discovered_attack_evidence"):
            return "discovered"
    except Exception:
        pass
    # Loose defensive — separate primitive, checked outside the try/except.
    if _pv_captures_own_loose(fa, pv[0]):
        return "loose"
    return None


def get_drills(motif_profile_raw: Optional[Dict[str, Dict]], motif: str) -> List[Dict[str, str]]:
    """The user's OWN positions for a motif (drill = find the move that avoids it).
    Community positions (motif-tagged) are appended by the route, own-first."""
    m = (motif_profile_raw or {}).get(motif) or {}
    out = []
    for p in m.get("got_positions", []):
        if isinstance(p, dict) and p.get("fen"):
            out.append({"fen": p["fen"], "solution": p.get("solution"), "source": "own"})
    return out


# Identity-level opener per motif, paired with the existing MOTIF_LESSON
# instructional line. Deterministic, no LLM (2026-08-07 — see Decision
# Log / Knowledge Base for why): states the recurring pattern as a fact
# about the player, not a count. "You keep..." not "you did X N times."
MOTIF_WEAKNESS_OPENER = {
    "fork": "You keep getting forked.",
    "pin": "You keep getting pinned.",
    "skewer": "You keep getting skewered.",
    "discovered": "Discovered attacks keep hitting you.",
    "loose": "You keep leaving pieces hanging.",
}

# Asymmetry case: same motif is BOTH a strength on offense (made_sound)
# and a weakness on defense (got) -- the player spots it against their
# opponent but doesn't spot it against themselves. Real, specific,
# checkable from the two-sided profile that already exists -- not a
# generic template, a real comparison of two numbers for this one motif.
MOTIF_ASYMMETRY_OPENER = {
    "fork": "You're sharp at spotting forks against your opponent — you don't see them coming your own way.",
    "pin": "You use pins well yourself — you don't see them coming when they're used on you.",
    "skewer": "You find skewers against your opponent — you don't see them coming your own way.",
    "discovered": "You use discovered attacks well yourself — you don't see them coming when your opponent plays one.",
    "loose": "Your loose pieces are the problem, not theirs — you spot when they leave something hanging, but you keep leaving your own open.",
}


def build_motif_blindspot_callout(
    motif_profile_raw: Optional[Dict[str, Dict]],
    games_analyzed_count: int,
    current_game_move_evaluations: Optional[List[Dict]] = None,
) -> Optional[str]:
    """One deterministic, memory-carrying line for Game Review: the
    player's single top recurring tactical blind spot (or strength/
    weakness asymmetry), anchored to a real moment in the game being
    reviewed right now when one exists.

    Deliberately NOT the old shape ("piece_safety, 15 times recently")
    -- see docs/chessguru_decision_log.md 2026-08-07. No LLM: every
    clause is a template selected by a real, checkable data pattern
    (which motif, which side, which move), not generated text.

    Returns None when there's nothing real to say (no weakness clears
    the population-normalized bar) -- frontend treats None as "don't
    render," same convention as cct_narrative.
    """
    card = render_motif_card(motif_profile_raw, games_analyzed_count)
    weaknesses = card.get("weaknesses") or []
    if not weaknesses:
        return None

    # Top weakness = highest raw got-count among those that already
    # cleared the population-normalized WEAKNESS_RATE bar (render_motif_card
    # only includes real, rate-confirmed weaknesses here already).
    top = max(weaknesses, key=lambda w: w.get("got", 0))
    motif = top["motif"]

    strength_motifs = {s["motif"] for s in (card.get("strengths") or [])}
    is_asymmetry = motif in strength_motifs

    if is_asymmetry:
        opener = MOTIF_ASYMMETRY_OPENER.get(motif, MOTIF_WEAKNESS_OPENER.get(motif, ""))
    else:
        opener = MOTIF_WEAKNESS_OPENER.get(motif, "")

    # Deliberately NOT appending MOTIF_LESSON's instructional line here --
    # that's generic chess advice ("before every move, scan...") and
    # stacking it onto the identity opener re-creates the over-explaining
    # problem this was built to avoid. Opener + anchor only, matching the
    # approved shape exactly (2026-08-06 conversation). MOTIF_LESSON stays
    # in use elsewhere (the Lab motif card) where that instructional voice
    # is the right fit.
    parts = [p for p in (opener,) if p]

    # Anchor to THIS game, if it actually shows the same motif -- only
    # cite "just now" when it's real for the game being reviewed, never
    # a stale example from a different game passed off as current.
    anchor = None
    for ev in (current_game_move_evaluations or []):
        if ev.get("is_opponent_move"):
            continue
        if position_allows_motif(ev) == motif:
            move_san = ev.get("move")
            move_number = ev.get("move_number")
            if move_san and move_number:
                anchor = f"That {move_san} just now, move {move_number} — same thing again."
            break

    if anchor:
        parts.append(anchor)

    return " ".join(parts) if parts else None


def aggregate_user_motif_profile(db, user_id: str) -> Dict[str, Any]:
    """Sum motif signals across the user's analyzed games → a two-sided profile."""
    totals = {m: _empty_motif() for m in MOTIFS}
    n_games = 0
    for g in db.games.find({"user_id": user_id, "is_analyzed": True}, {"_id": 0, "game_id": 1, "user_color": 1}):
        a = db.game_analyses.find_one({"game_id": g.get("game_id")},
                                      {"_id": 0, "stockfish_analysis": 1})
        mevals = (a or {}).get("stockfish_analysis", {}).get("move_evaluations") or []
        if not mevals:
            continue
        n_games += 1
        per = compute_game_motifs(mevals, (g.get("user_color") or "white").lower())
        for mt in MOTIFS:
            for k in ("made_sound", "made_tunnel", "got"):
                totals[mt][k] += per[mt][k]
            totals[mt]["got_positions"].extend(per[mt]["got_positions"])
    return {"games_analyzed": n_games, "motifs": {mt: _verdict(totals[mt], n_games, mt) for mt in MOTIFS}}


# ─────────────────────────────────────────────────────────────────────────────
# OFFENSE RECOGNITION RATE — the recognition-rate card (docs/motif_recognition_card_scope.md)
#
# The metric that distinguishes a fundamental weakness from a blind spot: when a
# motif WAS the engine's best move (an opportunity), did the player play it?
#   recognition = found / available, per motif.
# A count or per-game rate has no denominator of opportunity; this does. Same
# verified detectors as everywhere (single-source) — fork is winnability-checked
# (trustworthy absolute %), pin/skewer "available" includes some incidental aligned
# geometry so the card frames them as RANK vs peers, not a precise absolute.
#
# Population breakpoints locked-via-data 2026-06-22 (45 users, 120-game samples,
# >=8 opportunities/motif): p25 / median / p75 of found/available. Refit as the
# user base grows.
RECOGNITION_LABEL = {"fork": "Forks", "pin": "Pins", "skewer": "Skewers",
                     "discovered": "Discovered attacks", "loose": "Loose pieces"}
# trust of the standing: fork verified-winnable; pin/skewer detector is noisier (rougher tier)
# discovered: ray-uncover geometry, feedback-hardened (fb_a6f596afbba0 fixes) → solid
# loose: direct board attackers/defenders count, no ambiguity → solid
RECOGNITION_TRUST = {"fork": "solid", "pin": "rough", "skewer": "rough",
                     "discovered": "solid", "loose": "solid"}
MIN_OPPS_TO_SHOW = 8       # lifetime opportunities before a motif row appears at all
MIN_OPPS_TREND = 6         # opportunities needed in BOTH windows to show a trend arrow
TREND_DELTA = 0.04         # rate change (pts) to call it up/down vs steady

# ── Mastery ladder (the self-improvement card) ──────────────────────────────
# A level on the user's OWN path to mastering each motif. The population CALIBRATES
# the tier lines (so "Sharp" is meaningful, not arbitrary) but the card never shows a
# rank vs other people — it shows your level + which way you're moving (you vs your
# past self). docs/motif_recognition_card_scope.md
TIER_NAMES = ["Learning", "Developing", "Solid", "Sharp", "Mastered"]
# Locked-via-data 2026-06-22 from all 55 backfilled profiles (lifetime found/available,
# >=8 opps): the 4 internal tier boundaries [p25, median, p75, p90] per motif.
MASTERY_EDGES = {
    "fork":   [0.36, 0.44, 0.53, 0.57],
    "pin":    [0.35, 0.41, 0.45, 0.49],
    "skewer": [0.33, 0.41, 0.47, 0.51],
    # 2026-07-07: PROVISIONAL — locked from the 8-user probe. Refit after
    # first full-cohort backfill produces the real distribution. Starting
    # tier lines: [p25, med, p75, p90] estimates from probe recognition
    # rates. discovered was ~30% found on offensive availability; loose
    # was ~49% on the 8-user cohort — hence higher tiers for loose.
    "discovered": [0.20, 0.30, 0.42, 0.55],
    "loose":      [0.35, 0.49, 0.60, 0.72],
}


def _tier_for(rate: float, motif: str):
    """(tier_index, tier_name, ladder_fill_pct 0..100) for a lifetime rate."""
    p25, med, p75, p90 = MASTERY_EDGES.get(motif, [0.33, 0.41, 0.47, 0.51])
    ceil = p90 + 0.15                                  # headroom above 'Mastered'
    edges = [0.0, p25, med, p75, p90, ceil]            # 6 edges -> 5 equal segments
    idx = 4
    for i in range(5):
        if rate < edges[i + 1]:
            idx = i
            break
    lo, hi = edges[idx], edges[idx + 1]
    within = (rate - lo) / (hi - lo) if hi > lo else 1.0
    fill = max(0.0, min(100.0, 20 * idx + 20 * max(0.0, min(1.0, within))))
    return idx, TIER_NAMES[idx], round(fill)


def _move_motifs(fen, move, pv, mover_user) -> set:
    """Which verified motifs `move` creates (or exploits) in this position —
    single-source detectors. Returns a subset of MOTIFS.

    fork / pin / skewer / discovered are "the move CREATES this pattern"
    (checked via caption_facts geometry facts on board_after).

    loose is different — it's "the move CAPTURES a free enemy piece" — an
    exploitation of pre-existing geometry, not a creation. Checked directly
    against board_before via `_move_captures_loose`. Same aggregation shape
    still works because a loose-piece capture at cp_loss<=SOUND_CP is a
    strength (you spotted it) and at cp_loss>=BLUNDER_CP would be a very
    weird tunnel-vision (grabbed the pawn, missed mate) — same tiers apply.
    """
    from services.caption_facts import extract_facts
    out = set()
    if not (fen and move):
        return out
    try:
        f = extract_facts(fen_before=fen, played_san=move, best_move_san=move,
                          cp_loss=0, pv_after_played=pv or [], mover_is_user=mover_user)
        if f.get("multi_target_attack_evidence"):
            out.add("fork")
        out |= _classify_aligned(f.get("aligned_pieces_evidence"))
        if f.get("discovered_attack_evidence"):
            out.add("discovered")
    except Exception:
        pass
    # Loose-piece capture — direct board check, no caption_facts needed.
    # Kept OUTSIDE the try/except above so a caption_facts failure doesn't
    # also hide the loose signal.
    if _move_captures_loose(fen, move):
        out.add("loose")
    return out


def compute_game_recognition(move_evaluations: List[Dict]) -> Dict[str, Dict[str, int]]:
    """Per-game OFFENSE recognition tallies. For each USER move where the engine's
    best move CREATES a motif (available), did the player play a SOUND instance of
    that same motif (found)? Returns {'av': {fork,pin,skewer}, 'fo': {...}}."""
    av = {m: 0 for m in MOTIFS}
    fo = {m: 0 for m in MOTIFS}
    for ev in move_evaluations or []:
        if ev.get("is_opponent_move"):
            continue
        fen = ev.get("fen_before"); best = ev.get("best_move"); played = ev.get("move")
        if not (fen and best):
            continue
        cp = abs(int(ev.get("cp_loss") or 0))
        best_motifs = _move_motifs(fen, best, ev.get("pv_after_best") or [], True)
        if not best_motifs:
            continue
        played_motifs = (_move_motifs(fen, played, ev.get("pv_after_played") or [], True)
                         if cp <= SOUND_CP else set())
        for m in best_motifs:
            av[m] += 1
            if m in played_motifs:
                fo[m] += 1
    return {"av": av, "fo": fo}


def compute_game_anticipation(move_evaluations: List[Dict]) -> Dict[str, Dict[str, int]]:
    """Per-game DEFENSE ANTICIPATION tallies — the mirror of recognition, the "do you
    see motifs coming?" skill (Mohit's Skill 3). For each USER move, look at the motif
    the opponent's best reply now creates AGAINST the user (a threat that materialized);
    then check whether the engine's BEST user move would have AVOIDED it. If best avoids
    it, the threat was the user's to prevent and they didn't — a failed anticipation.

    Returns {'faced': {fork,pin,skewer}, 'allowed': {...}} where:
      faced[m]   = times a motif-m threat against the user materialized after their move,
      allowed[m] = of those, the ones that were AVOIDABLE (best move would not have allowed
                   it) — i.e. the user failed to see it coming.
    Anticipation rate = 1 - allowed/faced (higher = better). Engine-true: every motif
    comes from the verified detector applied to the engine's PV."""
    faced = {m: 0 for m in MOTIFS}
    allowed = {m: 0 for m in MOTIFS}
    for ev in move_evaluations or []:
        if ev.get("is_opponent_move"):
            continue
        fen_before = ev.get("fen_before"); fen_after = ev.get("fen_after")
        pvp = ev.get("pv_after_played") or []; pvb = ev.get("pv_after_best") or []
        best = ev.get("best_move")
        if not (fen_after and pvp):
            continue
        got_played = _move_motifs(fen_after, pvp[0], pvp[1:], False)
        if not got_played:
            continue
        # Would the engine's best user move have avoided the same motif threat?
        got_best = set()
        if best and pvb and fen_before:
            try:
                _b = chess.Board(fen_before); _b.push_san(best)
                got_best = _move_motifs(_b.fen(), pvb[0], pvb[1:], False)
            except Exception:
                got_best = set()
        for m in got_played:
            faced[m] += 1
            if m not in got_best:   # avoidable -> the user walked into it (failed to anticipate)
                allowed[m] += 1
    return {"faced": faced, "allowed": allowed}


def merge_recognition(stored: Optional[Dict], game_id: str, date_played: Optional[str],
                      per_game: Dict[str, Dict[str, int]]) -> Dict:
    """Idempotent per-game store keyed by game_id — re-analysis OVERWRITES that game's
    entry, never double-counts. Per-game records carry the date so the read endpoint can
    window to the last N days without re-aggregating."""
    out = stored or {"by_game": {}}
    out.setdefault("by_game", {})[str(game_id)] = {
        "date": date_played, "av": per_game["av"], "fo": per_game["fo"],
    }
    return out


def merge_anticipation(stored: Optional[Dict], game_id: str, date_played: Optional[str],
                       per_game: Dict[str, Dict[str, int]]) -> Dict:
    """Idempotent per-game DEFENSE-anticipation store (mirror of merge_recognition)."""
    out = stored or {"by_game": {}}
    out.setdefault("by_game", {})[str(game_id)] = {
        "date": date_played, "faced": per_game["faced"], "allowed": per_game["allowed"],
    }
    return out


def anticipation_rates(motif_anticipation: Optional[Dict]) -> Dict[str, Dict[str, Any]]:
    """Aggregate stored anticipation into per-motif {faced, allowed, rate} where
    rate = anticipation % = 1 - allowed/faced (higher = you see them coming; low = you
    walk into them). None rate when too few faced to be meaningful."""
    out: Dict[str, Dict[str, Any]] = {}
    bg = (motif_anticipation or {}).get("by_game") or {}
    for m in MOTIFS:
        f = sum((g.get("faced") or {}).get(m, 0) for g in bg.values())
        a = sum((g.get("allowed") or {}).get(m, 0) for g in bg.values())
        out[m] = {"faced": f, "allowed": a,
                  "rate": round(100 * (1 - a / f)) if f >= 5 else None}
    return out


def _trend(now_av, now_fo, prior_av, prior_fo):
    """Your-own trajectory: this window vs the one before it. Self-improvement, not peers."""
    if now_av < MIN_OPPS_TREND or prior_av < MIN_OPPS_TREND:
        return {"dir": "new"}  # not enough history in one window to call a direction
    to = now_fo / now_av
    fr = prior_fo / prior_av
    diff = to - fr
    direction = "up" if diff >= TREND_DELTA else "down" if diff <= -TREND_DELTA else "steady"
    return {"dir": direction, "from_pct": round(100 * fr), "to_pct": round(100 * to)}


# Defense (anticipation) tier — ABSOLUTE breakpoints over "how often you see the motif
# COMING", not population-relative. MASTERY NEEDS BOTH SIDES: a motif you walk into is not
# mastered, however well you ATTACK with it. So the card's overall standing is governed by
# the WEAKER of attack (recognition) and defense (anticipation).
_DEFENSE_EDGES = [0.0, 25.0, 40.0, 55.0, 70.0, 85.0]  # 5 segments over anticipation %


def _defense_tier(rate: Optional[float]):
    if rate is None:
        return None, 0
    idx = 4
    for i in range(5):
        if rate < _DEFENSE_EDGES[i + 1]:
            idx = i
            break
    lo, hi = _DEFENSE_EDGES[idx], _DEFENSE_EDGES[idx + 1]
    within = (rate - lo) / (hi - lo) if hi > lo else 1.0
    return idx, round(20 * idx + 20 * max(0.0, min(1.0, within)))


def _two_sided_note(off_idx: int, def_idx: Optional[int]) -> str:
    so = off_idx is not None and off_idx >= 2   # Solid+
    sd = def_idx is not None and def_idx >= 2
    if so and not sd:
        return "Sharp on attack — but they keep catching you. Defense is the gap."
    if sd and not so:
        return "Solid defense — now sharpen your eye for playing them on attack."
    if not so and not sd:
        return "Work on both sides — finding them, and seeing them coming."
    return "Strong both sides."


def render_recognition_card(motif_recognition: Optional[Dict], now=None,
                            window_days: int = 15,
                            motif_anticipation: Optional[Dict] = None) -> Dict[str, Any]:
    """Two-sided mastery card: per motif, the user's LEVEL on the path to mastering it —
    governed by the WEAKER of ATTACK (recognition: do you find them?) and DEFENSE
    (anticipation: do you see them coming?). A motif that keeps catching the user can NOT
    show "Mastered" no matter how well they attack with it. Pure arithmetic over the stored
    per-game tallies. docs/motif_recognition_card_scope.md + pwc_coach_conductor_scope.md."""
    from datetime import datetime, timedelta, timezone
    data = (motif_recognition or {}).get("by_game") or {}
    now = now or datetime.now(timezone.utc)
    recent_cut = now - timedelta(days=window_days)
    prior_cut = now - timedelta(days=2 * window_days)

    def _parse(d):
        if not isinstance(d, str):
            return None
        try:
            dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    life_av = {m: 0 for m in MOTIFS}; life_fo = {m: 0 for m in MOTIFS}
    now_av = {m: 0 for m in MOTIFS}; now_fo = {m: 0 for m in MOTIFS}
    pri_av = {m: 0 for m in MOTIFS}; pri_fo = {m: 0 for m in MOTIFS}
    recent_games = total_games = 0
    for rec in data.values():
        total_games += 1
        d = _parse(rec.get("date"))
        is_recent = d is not None and d >= recent_cut
        is_prior = d is not None and prior_cut <= d < recent_cut
        if is_recent:
            recent_games += 1
        for m in MOTIFS:
            av = int((rec.get("av") or {}).get(m, 0)); fo = int((rec.get("fo") or {}).get(m, 0))
            life_av[m] += av; life_fo[m] += fo
            if is_recent:
                now_av[m] += av; now_fo[m] += fo
            elif is_prior:
                pri_av[m] += av; pri_fo[m] += fo

    ant = anticipation_rates(motif_anticipation)
    rows = []
    for m in MOTIFS:
        if life_av[m] < MIN_OPPS_TO_SHOW:
            continue  # not enough lifetime data to place a level honestly
        rate = life_fo[m] / life_av[m]                       # ATTACK standing (find-rate)
        off_idx, off_tier, off_fill = _tier_for(rate, m)
        # DEFENSE standing (anticipation) — absolute. None when too few threats faced.
        def_rate = (ant.get(m) or {}).get("rate")
        def_idx, def_fill = _defense_tier(def_rate) if def_rate is not None else (None, None)
        # OVERALL = the weaker side. Mastery needs both. When defense is unknown, fall back
        # to attack (don't invent a low score from missing data).
        if def_idx is not None and def_idx < off_idx:
            idx, tier, fill = def_idx, TIER_NAMES[def_idx], def_fill
        else:
            idx, tier, fill = off_idx, off_tier, off_fill
        trend = _trend(now_av[m], now_fo[m], pri_av[m], pri_fo[m])
        drill = idx <= 1 or trend.get("dir") == "down" or (def_idx is not None and def_idx <= 1)
        rows.append({
            "motif": m, "label": RECOGNITION_LABEL[m],
            "tiers": TIER_NAMES,
            "tier": tier, "tier_index": idx, "fill_pct": fill,
            "next_tier": TIER_NAMES[idx + 1] if idx < len(TIER_NAMES) - 1 else None,
            "trend": trend,
            "drill": drill,
            "trust": RECOGNITION_TRUST[m],
            # Two-sided breakdown — so the card can show WHY the standing is what it is.
            "attack": {"tier": off_tier, "tier_index": off_idx, "rate": round(100 * rate)},
            "defense": {"tier": TIER_NAMES[def_idx] if def_idx is not None else None,
                        "tier_index": def_idx, "rate": def_rate,
                        "caught": (ant.get(m) or {}).get("allowed")},
            "two_sided_note": _two_sided_note(off_idx, def_idx),
        })
    return {"recent_games": recent_games, "total_games": total_games,
            "window_days": window_days, "rows": rows}
