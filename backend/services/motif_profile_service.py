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

# Move-quality gates (cp_loss). Lock thresholds via /lock-via-data after a corpus histogram.
SOUND_CP = 40      # <= this: the motif move was good → strength
BLUNDER_CP = 100   # >= this: a real blunder → tunnel-vision (made) / got-forked (allowed)

MOTIFS = ["fork", "pin", "skewer"]  # discovered to be added after its audit
SKEWER_GAP_CP = 150  # front must be a real piece more valuable than rear (not B-over-N)


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

        # MADE side (user's own move): fork (winnability-checked) + pin/skewer (aligned geom).
        try:
            mf = extract_facts(fen_before=fen, played_san=played, best_move_san=best,
                               cp_loss=cp, pv_after_played=pv, mover_is_user=True)
            made = set()
            if mf.get("multi_target_attack_evidence"):
                made.add("fork")
            made |= _classify_aligned(mf.get("aligned_pieces_evidence"))
            for mt in made:
                out[mt]["made_sound" if cp <= SOUND_CP else "made_tunnel"] += 1
        except Exception:
            pass

        # GOT side: the user's move was a blunder whose engine reply creates the motif
        # against the user (same verified detectors, applied to the opponent's reply).
        # Drill position is fen_before — "find the move that avoids it".
        if fen_after and pv and cp >= BLUNDER_CP:
            try:
                gf = extract_facts(fen_before=fen_after, played_san=pv[0],
                                   cp_loss=0, mover_is_user=False)
                got = set()
                if gf.get("multi_target_attack_evidence"):
                    got.add("fork")
                got |= _classify_aligned(gf.get("aligned_pieces_evidence"))
                for mt in got:
                    out[mt]["got"] += 1
                    out[mt]["got_positions"].append({"fen": fen, "solution": best})
            except Exception:
                pass
    return out


# Lock-via-data (2026-06-22): per-motif p70 of the got/made-per-game distribution over 53
# users (>=5 games). Relative thresholds — "you walk into X MORE than most players" — so the
# card flags each user's standout ~30%, not everyone-on-everything. Pins/skewers are
# inherently more common than forks, hence per-motif cutoffs.
WEAKNESS_RATE = {"fork": 0.18, "pin": 0.30, "skewer": 0.26}   # got per game
STRENGTH_RATE = {"fork": 0.26, "pin": 0.77, "skewer": 0.69}   # made_sound per game


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
}
MOTIF_LABEL = {"fork": "Forks", "pin": "Pins", "skewer": "Skewers"}


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
    verified reply)? Returns 'fork' (pin/skewer later) or None. Used to motif-tag extracted
    puzzles so weakness drills filter by motif — SAME verified detector as the profile's
    got-side, so the tag and the diagnosis never disagree."""
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
    except Exception:
        pass
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
