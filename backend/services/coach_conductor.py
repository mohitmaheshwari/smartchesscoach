"""coach_conductor.py — the player-model layer for live coaching.

Turns the stored motif profile into per-move THREADS: STATEMENTS (never quizzes)
that surface the player's OWN recurring pattern at the engine-confirmed moment it
recurs — with restraint, and catching wins as well as misses.

Laws (docs/pwc_coach_conductor_scope.md):
  - STATE, never ASK (no "?").
  - thread, not stat (reference the recurrence/slipping, never "you did X N times").
  - engine-true or silent (every motif claim comes from the verified detectors +
    the engine's best_move / pv — never a guess).
  - restraint: a given thread fires at most once per game (threads_pulled).
  - catch the wins too.

Pure functions. `player_motif_threads()` builds the per-player digest once (at
session start); `compute_motif_thread()` runs per move and returns a thread dict
(or None). The caller (the caption door / PWC path) makes a fired thread the
conductor's chosen caption.
"""
from __future__ import annotations
from typing import Optional, Dict, Any, Set, List

import chess

from services.motif_profile_service import (
    _move_motifs, SOUND_CP, BLUNDER_CP, MOTIFS,
    render_motif_card, render_recognition_card, anticipation_rates,
)

# Below this anticipation %, the player walks into the motif more than they see it
# coming — a real defensive weakness worth threading.
_LOW_ANTICIPATION = 40

# A missed offense motif only counts when missing it cost a real tactic's worth
# of eval (not a marginal transposition). A win only counts when the motif move
# actually WON material (filters routine best-moves that incidentally align pieces).
_MISS_CP = BLUNDER_CP   # 100 — you lost a pawn+ by not playing the motif
_WIN_GAIN_CP = 60       # the motif move improved your eval by ~0.6 pawn+ (a real tactic)


def player_motif_threads(
    motif_profile_raw: Optional[Dict[str, Any]],
    motif_recognition_raw: Optional[Dict[str, Any]],
    games_analyzed: int = 0,
    motif_anticipation_raw: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Digest the stored profile into the motifs that are THIS player's story.

    Returns:
      {
        "defense": {motif: {"got": int}},        # motifs the player walks INTO
        "offense": {motif: {"rate": int|None,    # REAL recognition % (honest, not the bar)
                            "trend": str,        # "up"|"down"|"steady"|"new"
                            "tier": str}},       # motifs the player misses / is slipping on
      }
    Only motifs that are a genuine weakness/slip appear — strengths are silent
    (we never nag a pattern the player owns).
    """
    defense: Dict[str, Any] = {}
    offense: Dict[str, Any] = {}

    # Defense — "you walk into these" (is_weakness verdict on the GOT side).
    try:
        card = render_motif_card(
            (motif_profile_raw or {}).get("motifs") if motif_profile_raw and "motifs" in motif_profile_raw
            else motif_profile_raw,
            games_analyzed,
        )
        for w in card.get("weaknesses") or []:
            m = w.get("motif")
            if m in MOTIFS:
                defense[m] = {"got": w.get("got", 0)}
    except Exception:
        pass

    # Offense — "you miss / are slipping on these" (low tier OR downward trend).
    try:
        rec = render_recognition_card(motif_recognition_raw)
        for row in rec.get("rows") or []:
            m = row.get("motif")
            if m not in MOTIFS:
                continue
            tier_idx = row.get("tier_index", 99)
            trend = (row.get("trend") or {})
            tdir = trend.get("dir")
            to_pct = trend.get("to_pct")
            # Slipping (trend down) OR stuck low (Learning/Developing = tier 0/1).
            if tdir == "down" or tier_idx <= 1:
                offense[m] = {"rate": to_pct, "trend": tdir, "tier": row.get("tier")}
    except Exception:
        pass

    # Defense (anticipation) — motifs you don't see COMING (Skill 3). Low anticipation
    # = you walk into them more than you stop them, so add them to the defense set even
    # when the coarse got-weakness didn't flag them. Mohit: skewer 8% joins fork here.
    try:
        for m, info in anticipation_rates(motif_anticipation_raw).items():
            r = info.get("rate")
            if r is not None and r < _LOW_ANTICIPATION:
                d = defense.setdefault(m, {})
                d["anticipation"] = r
                d.setdefault("got", info.get("allowed", 0))
    except Exception:
        pass

    return {"defense": defense, "offense": offense}


# Known-endgame technique recognition — STATEMENTS (no quiz), fired when the
# existing concept detectors confirm a textbook endgame. "missed" = teach the
# technique; "applied" = name + credit it. docs/pwc_coach_conductor_scope.md.
_ENDGAME_SAY = {
    "endgame_lucena": {
        "applied": "That's the Lucena — your rook builds the bridge so your king escapes the checks and the pawn promotes. Textbook.",
        "missed": "This is a winning Lucena position. The technique is the bridge: put your rook on the rank just in front of your king so it blocks the checks while your king steps out and the pawn queens.",
    },
    "endgame_philidor": {
        "applied": "That's the Philidor — rook on the third rank holds the draw until their pawn commits.",
        "missed": "This is a Philidor draw. Keep your rook on the third rank to stop their king coming forward; once their pawn reaches the third, swing your rook behind it and check from there.",
    },
    "endgame_opposition": {
        "applied": "Good — you took the opposition, kings facing with one square between, forcing their king to give ground.",
        "missed": "Take the opposition here — your king directly facing theirs with one square between. It forces their king back and clears the path for your pawn.",
    },
    "endgame_rule_of_square": {
        "applied": "Good — your king is inside the square of the pawn, so you catch it.",
        "missed": "Use the rule of the square: picture a box from the pawn to its promotion square; if your king can step inside that box, it catches the pawn.",
    },
}


def compute_endgame_thread(
    *,
    fen_before: str,
    played_san: str,
    user_is_white: bool,
    threads_pulled: Set[str],
) -> Optional[Dict[str, Any]]:
    """Return a known-endgame technique STATEMENT for this user move, or None.
    Technique-verified by the existing concept detectors; restraint per technique."""
    if not fen_before or not played_san:
        return None
    try:
        from services.concept_detectors.registry import get_detector
        board = chess.Board(fen_before)
        move = board.parse_san(played_san)
    except Exception:
        return None
    user_color = chess.WHITE if user_is_white else chess.BLACK
    for skill, say in _ENDGAME_SAY.items():
        key = f"endgame:{skill}"
        if key in threads_pulled:
            continue
        fn = get_detector(skill)
        if fn is None:
            continue
        try:
            r = fn(board, move, user_color)
        except Exception:
            r = None
        if r in ("applied", "missed"):
            threads_pulled.add(key)
            return {"kind": f"endgame_{r}", "motif": skill, "side": "endgame", "text": say[r]}
    return None


def _slip_tag(info: Dict[str, Any]) -> str:
    """A short, honest thread tag for an offense motif — references the slip, never a count."""
    if info.get("trend") == "down":
        return "the one that's been slipping on you lately"
    return "the one you've been missing lately"


def compute_motif_thread(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: Optional[str],
    pv_after_played: Optional[List[str]],
    pv_after_best: Optional[List[str]],
    cp_loss: int,
    is_user_move: bool,
    threads: Dict[str, Dict[str, Any]],
    threads_pulled: Set[str],
    eval_before_cp: Optional[int] = None,
    eval_after_cp: Optional[int] = None,
    mover_is_white: bool = True,
) -> Optional[Dict[str, Any]]:
    """Return the single most relevant motif thread for THIS move, or None.

    `threads` = player_motif_threads() digest. `threads_pulled` = motif-thread keys
    already pulled this game (mutated on fire, for restraint). All returned text is
    a STATEMENT (no "?") and engine-grounded (the motif comes from the verified
    detector applied to the engine's best_move / pv).
    """
    if not is_user_move or not fen_before or not played_san:
        return None
    cp = abs(int(cp_loss or 0))
    defense = threads.get("defense") or {}
    offense = threads.get("offense") or {}

    # ── OFFENSE: was a slipping/weak motif the engine's best move — did you find it or miss it?
    if offense and best_move_san:
        try:
            best_motifs = _move_motifs(fen_before, best_move_san, pv_after_best or [], True)
        except Exception:
            best_motifs = set()
        weak_best = sorted(best_motifs & set(offense.keys()))
        if weak_best:
            m = weak_best[0]
            key = f"offense:{m}"
            if key not in threads_pulled:
                # WIN: the player played the EXACT engine-best motif move AND it
                # actually WON material (eval improved by a tactic's worth). The
                # eval-gain gate filters routine best-moves that merely align pieces
                # (pin/skewer geometry) without winning anything — those are not a
                # "you found the skewer", they're just geometry. Engine-true.
                _norm = lambda s: (s or "").replace("+", "").replace("#", "")
                _gain = None
                if eval_before_cp is not None and eval_after_cp is not None:
                    _gain = (eval_after_cp - eval_before_cp) if mover_is_white else (eval_before_cp - eval_after_cp)
                # fork is winnability-checked (trustworthy) → a fork-win needs no
                # gain gate; pin/skewer are geometric → require a real material gain.
                _win_ok = _norm(played_san) == _norm(best_move_san) and (
                    m == "fork" or (_gain is not None and _gain >= _WIN_GAIN_CP))
                if _win_ok:
                    threads_pulled.add(key)
                    return {
                        "kind": "win", "motif": m, "side": "offense",
                        "text": f"{played_san} — you found the {m}. That's {_slip_tag(offense[m])} — good.",
                    }
                if cp >= _MISS_CP:
                    threads_pulled.add(key)
                    return {
                        "kind": "miss", "motif": m, "side": "offense",
                        "text": f"There was a {m} here — {best_move_san}. That's {_slip_tag(offense[m])}.",
                    }

    # ── DEFENSE: did your move walk into a motif you keep walking into?
    if defense and cp >= BLUNDER_CP and pv_after_played:
        try:
            b = chess.Board(fen_before)
            b.push_san(played_san)
            got = _move_motifs(b.fen(), pv_after_played[0], pv_after_played[1:], False)
        except Exception:
            got = set()
        weak_got = sorted(got & set(defense.keys()))
        if weak_got:
            m = weak_got[0]
            key = f"defense:{m}"
            if key not in threads_pulled:
                threads_pulled.add(key)
                opp = pv_after_played[0]
                best_clause = f" {best_move_san} held it." if best_move_san else ""
                return {
                    "kind": "walk_into", "motif": m, "side": "defense",
                    "text": f"The {m} again — {played_san} lets {opp} in. You keep walking into these.{best_clause}",
                }

    return None
