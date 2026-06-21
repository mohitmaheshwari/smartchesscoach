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

MOTIFS = ["fork"]  # pin / skewer / discovered to be added after their audit


def _empty_motif() -> Dict[str, Any]:
    return {"made_sound": 0, "made_tunnel": 0, "got": 0, "got_positions": []}


def compute_game_motifs(move_evaluations: List[Dict], user_color: str) -> Dict[str, Dict]:
    """Tally a single game's motif signals from the USER's moves, using the verified
    geometry detector on both sides. Pure function over stored move_evaluations."""
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

        # MADE a fork (verified, winnability-checked) on the user's own move.
        try:
            mf = extract_facts(fen_before=fen, played_san=played, best_move_san=best,
                               cp_loss=cp, pv_after_played=pv, mover_is_user=True)
            if mf.get("multi_target_attack_evidence"):
                out["fork"]["made_sound" if cp <= SOUND_CP else "made_tunnel"] += 1
        except Exception:
            pass

        # GOT forked: the user's move was a blunder whose engine reply is a verified
        # winnable fork (same detector, applied to the opponent's reply). The drill
        # position is fen_before — "find the move that doesn't walk into the fork".
        if fen_after and pv and cp >= BLUNDER_CP:
            try:
                gf = extract_facts(fen_before=fen_after, played_san=pv[0],
                                   cp_loss=0, mover_is_user=False)
                if gf.get("multi_target_attack_evidence"):
                    out["fork"]["got"] += 1
                    out["fork"]["got_positions"].append(fen)
            except Exception:
                pass
    return out


def _verdict(m: Dict[str, Any]) -> Dict[str, Any]:
    """Turn raw tallies into a strength/weakness verdict (thresholds lock-via-data)."""
    made = m["made_sound"] + m["made_tunnel"]
    sound_rate = (m["made_sound"] / made) if made else None
    return {
        **{k: m[k] for k in ("made_sound", "made_tunnel", "got")},
        "sound_rate": round(sound_rate, 2) if sound_rate is not None else None,
        "is_strength": m["made_sound"] >= 3 and (sound_rate is None or sound_rate >= 0.7),
        "is_weakness": m["got"] >= 3,
        "drill_positions": m["got_positions"][:20],
    }


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
    return {"games_analyzed": n_games, "motifs": {mt: _verdict(totals[mt]) for mt in MOTIFS}}
