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


# ── CONCEPTS: user_concept_understanding as coaching memory ────────────
# Item B of docs/pwc_memory_wiring_scope.md (2026-07-08). Mohit's ask:
# "coach memory says I am good with finding forks... or if I am not good,
# coach guides me there." The mastery gate already writes 17-33 named
# concepts per active user with lifetime clean_rate. The conductor was
# reading motif + opening but NOT this collection.
#
# Weakness gate: lifetime clean_rate < CONCEPT_WEAKNESS_FLOOR AND ≥
# CONCEPT_MIN_OPPS (small samples = noise). Strength gate: clean_rate ≥
# CONCEPT_STRENGTH_FLOOR (mirrors the "You Learned This" card's floor
# so the two surfaces agree on what counts as owned).
CONCEPT_WEAKNESS_FLOOR = 0.60   # < 60% clean = real weakness worth threading
CONCEPT_STRENGTH_FLOOR = 0.60   # >= 60% clean = strength — silent (never nag)
CONCEPT_MIN_OPPS = 20           # need at least 20 chances before the rate is trustable
CONCEPT_WEAK_CAP = 6            # digest keeps top-N weaknesses by (1-rate)*log(opps)


async def player_concept_threads(db, user_id: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Digest user_concept_understanding into the concepts that are THIS
    player's teaching material.

    Returns:
      {
        "weaknesses": {concept_id: {name, clean_rate_pct, opps, last_violation_at}},
        "strengths":  {concept_id: {name, clean_rate_pct, opps}},
      }

    Weaknesses fire on user's mistake matching the concept ("you keep
    slipping on this — [teach]"). Strengths are the silence-list — the
    conductor never nags a strength, but a WIN thread can fire on the
    good move that touches one ("that's the shape you own — good").

    Same source of truth (services.caption_principles.PRINCIPLES) that
    the InGameMasteryPanel + LearnedThisCard read for names — no new
    naming layer, keeps single-source-of-truth. See
    docs/pwc_memory_wiring_scope.md §5 Item B.
    """
    try:
        from services.caption_principles import PRINCIPLES
        _NAMES = {p["id"]: (p.get("name") or p["id"]) for p in PRINCIPLES}
    except Exception:
        _NAMES = {}

    weaknesses: Dict[str, Dict[str, Any]] = {}
    strengths: Dict[str, Dict[str, Any]] = {}
    try:
        async for row in db.user_concept_understanding.find(
            {"user_id": user_id},
            {"_id": 0, "concept_id": 1, "clean_games_total": 1,
             "violations_total": 1, "last_violation_at": 1, "mastered_at": 1},
        ):
            cid = row.get("concept_id")
            if not cid:
                continue
            clean = int(row.get("clean_games_total") or 0)
            viol = int(row.get("violations_total") or 0)
            opps = clean + viol
            if opps < CONCEPT_MIN_OPPS:
                continue
            rate = clean / opps
            entry = {
                "name": _NAMES.get(cid) or cid,
                "clean_rate_pct": round(rate * 100),
                "opps": opps,
                "last_violation_at": row.get("last_violation_at"),
            }
            if rate < CONCEPT_WEAKNESS_FLOOR:
                weaknesses[cid] = entry
            elif rate >= CONCEPT_STRENGTH_FLOOR:
                strengths[cid] = entry
    except Exception:
        pass

    # Cap weaknesses to the strongest signals — most-often-violated + biggest
    # sample. Sort by (1 - rate) * opps so a 25%-clean-441-opp beats a
    # 55%-clean-40-opp. Prevents the digest ballooning to 30+ concepts.
    if len(weaknesses) > CONCEPT_WEAK_CAP:
        ranked = sorted(
            weaknesses.items(),
            key=lambda kv: -(1.0 - kv[1]["clean_rate_pct"] / 100.0) * kv[1]["opps"],
        )
        weaknesses = dict(ranked[:CONCEPT_WEAK_CAP])

    return {"weaknesses": weaknesses, "strengths": strengths}


def compute_concept_thread(
    *,
    principle_id_used: Optional[str],
    principles_violated: Optional[List[Dict[str, Any]]],
    severity: Optional[str],
    played_san: str,
    is_user_move: bool,
    threads: Optional[Dict[str, Any]],
    threads_pulled: Set[str],
) -> Optional[Dict[str, Any]]:
    """Return a concept STATEMENT for THIS user move, or None.

    Fires on:
      MISS  — severity ∈ {mistake, blunder, serious} AND the move's
              principle_id_used OR any violated principle matches a
              weakness concept in the digest.
      WIN   — severity ∈ {good, best, brilliant} AND the played move's
              principle_id_used matches a weakness concept (the player
              is finally getting it — catch the win).

    Strengths are silent — the conductor never nags a mastered pattern.
    Restraint: one thread per concept per game (keyed `concept:{cid}`).

    All text is a STATEMENT (never "?"), rating-agnostic (caption_facts
    already produced principle_id_used, which is the same signal the
    mastery gate uses — so the concept genuinely applies to this move).
    """
    if not is_user_move or not played_san or not threads:
        return None
    weaknesses = (threads.get("weaknesses") or {})
    if not weaknesses:
        return None

    # Collect all concept IDs the caption facts said this move touches.
    touched: List[str] = []
    if principle_id_used:
        touched.append(principle_id_used)
    for v in (principles_violated or []):
        if isinstance(v, dict):
            vid = v.get("principle_id")
            if vid and vid not in touched:
                touched.append(vid)

    if not touched:
        return None

    # Intersect with weaknesses in a stable order (first-touched wins so
    # the primary caption_facts signal takes priority over the accessory
    # violated list).
    matched = None
    for cid in touched:
        if cid in weaknesses:
            matched = cid
            break
    if matched is None:
        return None

    key = f"concept:{matched}"
    if key in threads_pulled:
        return None

    info = weaknesses[matched]
    name = info["name"]

    sev = (severity or "").lower()
    # Include 'inaccuracy' — a ~200cp move that touches a weakness concept
    # IS a teaching moment even if the eval-adjusted tier softens it.
    # Verified 2026-07-08 against Mohit's real game where a TAC_HANGING_PIECE
    # move at cp_loss=206 came out severity_practical='inaccuracy' but was
    # displayed as "Nd4 is a mistake" in the caption. Restraint (one thread
    # per concept per game) keeps this from over-firing.
    MISS_TIERS = {"inaccuracy", "mistake", "blunder", "serious"}
    WIN_TIERS = {"good", "best", "brilliant", "excellent"}

    if sev in MISS_TIERS:
        threads_pulled.add(key)
        return {
            "kind": "concept_miss", "motif": matched, "side": "concept",
            "text": (
                f"There it is again — {name}. "
                f"This is the pattern you've been slipping on. Slow down here."
            ),
        }
    if sev in WIN_TIERS:
        threads_pulled.add(key)
        return {
            "kind": "concept_win", "motif": matched, "side": "concept",
            "text": (
                f"{played_san} — that's {name}. "
                f"The pattern you've been working on — good."
            ),
        }
    return None


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


# ── OPENINGS: recurring, engine-confirmed opening mistakes ─────────────────
# A deviation from the curriculum mainline is NOT a mistake (d3 in the Italian
# recurs 41× and is sound). So the digest already filtered to patterns the engine
# punishes (user_opening_profile.recurring_mistakes). Here we ALSO gate the live
# instance on EVAL-STATE severity, not raw cp_loss: a move that loses 113cp but
# stays winning reads "d5 is fine — you're still winning", and calling that a
# recurring mistake would contradict its own caption. We fire only when the move's
# practical tier is a real mistake. The thread PREPENDS the recurrence framing,
# leaving the underlying caption's engine why + better move intact.
_OPENING_FIRE_TIERS = ("mistake", "serious", "blunder")


def player_opening_threads(opening_profile: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Digest user_opening_profile into {family: {played_san: {best_san, count, median_cp_loss}}}.
    Only the engine-confirmed recurring mistakes (already cp_loss-filtered upstream)."""
    out: Dict[str, Dict[str, Any]] = {}
    for r in (opening_profile or {}).get("recurring_mistakes") or []:
        fam = r.get("opening_family")
        played = r.get("played_san")
        if not fam or not played:
            continue
        out.setdefault(fam, {})[played] = {
            "best_san": r.get("best_san"),
            "count": r.get("count"),
            "median_cp_loss": r.get("median_cp_loss"),
        }
    return out


# ── IDENTITY: prepend a short identity-cued lead-in to the first-fired
# conductor thread of the session (Item C, docs/pwc_memory_wiring_scope.md).
# Never invents; only fires when player_identity_engine has HIGH confidence
# AND the identity's main_leak / phase_vulnerability aligns with the fired
# thread's kind. Silent otherwise (matches the TRUTH law: no personal claim
# without evidence). At most once per session (keyed `identity` in
# threads_pulled) so it stays a moment, not a signature.


async def player_identity_lead_in(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Load the identity engine's narrative for THIS user. Returns
    {level, main_leak_label, phase_label, style_label} or None if the
    identity isn't confident enough for a lead-in.

    Confidence gate: only 'high' / 'definitive' — 'medium' identities
    are honest ambiguity; a lead-in over medium confidence would be a
    personal claim without evidence.
    """
    try:
        from player_identity_engine import compute_player_identity
        r = await compute_player_identity(db, user_id) or {}
        confidence = (r.get("confidence") or {}).get("level")
        if confidence not in ("high", "definitive"):
            return None
        expanded = r.get("expanded") or {}
        return {
            "level": confidence,
            "main_leak_label": (expanded.get("main_leak") or {}).get("label"),
            "phase_label": (expanded.get("phase_vulnerability") or {}).get("label"),
            "style_label": (expanded.get("playing_style") or {}).get("label"),
        }
    except Exception:
        return None


async def load_player_caption_context(db, user_id: str) -> Dict[str, Any]:
    """Load the evidence-backed player context used by the caption door.

    This is the one construction point for both batch Game Review and live
    coaching.  It deliberately returns empty values when a source is missing:
    absence of evidence must silence personalization, never manufacture it.

    The function only reads existing canonical stores.  It creates no profile,
    recomputes no detector, and contains no new rating/quality thresholds.
    """
    empty = {
        "player_motif_threads": None,
        "player_opening_threads": None,
        "player_concept_threads": None,
        "strong_openings": set(),
        "player_identity": None,
        "session_focus": None,
    }
    if db is None or not user_id:
        return empty

    result = dict(empty)

    try:
        profile = await db.player_profiles.find_one(
            {"user_id": user_id},
            {"_id": 0, "motif_profile": 1, "motif_recognition": 1,
             "motif_anticipation": 1, "games_analyzed_count": 1},
        ) or {}
        result["player_motif_threads"] = player_motif_threads(
            profile.get("motif_profile"),
            profile.get("motif_recognition"),
            profile.get("games_analyzed_count") or 0,
            motif_anticipation_raw=profile.get("motif_anticipation"),
        )
    except Exception:
        result["player_motif_threads"] = None

    try:
        # Read the persisted canonical profile directly.  The public
        # get_opening_profile() accessor may recompute and write when stale;
        # rendering a review must remain a read-only operation.
        opening_profile = await db.user_opening_profiles.find_one(
            {"user_id": user_id}, {"_id": 0}
        )
        result["player_opening_threads"] = player_opening_threads(opening_profile)
    except Exception:
        result["player_opening_threads"] = None

    try:
        result["player_concept_threads"] = await player_concept_threads(db, user_id)
    except Exception:
        result["player_concept_threads"] = None

    try:
        from services.player_performance import get_strong_openings
        result["strong_openings"] = set(await get_strong_openings(db, user_id) or set())
    except Exception:
        result["strong_openings"] = set()

    try:
        result["player_identity"] = await player_identity_lead_in(db, user_id)
    except Exception:
        result["player_identity"] = None

    try:
        from services.focus_bridge import get_active_focus_bundle
        result["session_focus"] = await get_active_focus_bundle(db, user_id)
    except Exception:
        result["session_focus"] = None

    return result


# Map a conductor-thread kind to a matching identity dimension. When the
# fired thread aligns with the user's known main_leak / phase, we get a
# real "the coach knows me" moment instead of a generic prepend.
_IDENTITY_LEAD_IN_MAP = {
    # concept-miss = a mistake matching a weakness concept. Almost always
    # aligns with "main_leak" — the recurring shape of the user's mistakes.
    "concept_miss": "main_leak_label",
    # motif walk-into = defense-side. Same alignment.
    "walk_into": "main_leak_label",
    # motif miss / opening recur = both are recurring blind spots.
    "miss": "main_leak_label",
    "opening_recur": "main_leak_label",
    # endgame missed = phase vulnerability if they slip in endgames.
    "endgame_missed": "phase_label",
}


def maybe_prepend_identity_lead_in(
    thread: Optional[Dict[str, Any]],
    identity: Optional[Dict[str, Any]],
    threads_pulled: Set[str],
) -> Optional[Dict[str, Any]]:
    """When a conductor thread fires, optionally decorate its text with a
    short identity phrase — but only once per session (restraint).

    Mutates thread["text"] in place; returns the (possibly-decorated)
    thread. Silent when the identity isn't confident, doesn't align with
    the fired kind, or the identity lead-in was already spent."""
    if not thread or not identity or "identity" in threads_pulled:
        return thread
    kind = thread.get("kind") or ""
    dim_key = _IDENTITY_LEAD_IN_MAP.get(kind)
    if not dim_key:
        return thread
    label = identity.get(dim_key)
    if not label:
        return thread
    # Short, one-sentence lead-in. Keep it human, not "your identity is X".
    # The label already reads as a narrative phrase from the engine.
    lead = f"Careful — {label.lower()}. "
    thread["text"] = lead + (thread.get("text") or "")
    threads_pulled.add("identity")
    thread["identity_lead_in_applied"] = True
    return thread


# ── SESSION FOCUS: the goal anchor layer (Phase 1, docs/pwc_memory_wiring_scope.md).
# Mohit 2026-07-08: "if it's goal, coach should act on it, somehow it should feel
# like coach is taking this nicely, otherwise it's just there piece of crap."
#
# The session goal is only real if it FILTERS what the coach says. When a
# conductor thread fires AND its kind aligns with the user's active focus,
# decorate the text with a short anchor that names the focus — so the user
# feels the coach connected today's goal to what it just said.
#
# Restraint: at most ONCE per session (key `goal_anchor`) — an anchor on every
# fire becomes a repeated jingle. One well-placed anchor lands.
# Silent when the focus is time_management (Phase 2 handles that separately
# via time-per-move detection).
_FOCUS_THREAD_ALIGNMENT: Dict[str, set] = {
    # Hanging pieces + walk-into weak motifs = the piece-safety topic.
    "piece_safety":       {"concept_miss", "walk_into"},
    # King attacks + walked-into pins/skewers against your king.
    "king_safety":        {"concept_miss", "walk_into"},
    # Missing offensive tactics = motif miss or concept_miss on TAC_*.
    "missed_tactic":      {"miss", "concept_miss"},
    # Same shape, calculation flavor.
    "tactical_oversight": {"miss", "concept_miss"},
    "calculation_depth":  {"miss", "concept_miss"},
    # MID_* concepts on activity.
    "piece_activity":     {"concept_miss", "concept_win"},
    # Opening recurrence thread aligns cleanly.
    "opening_knowledge":  {"opening_recur", "opening_strength"},
    # Endgame technique concept-detectors thread.
    "endgame_technique":  {"endgame_missed", "endgame_applied"},
    # Structural concepts (MID_PAWN_BREAK, etc.).
    "pawn_structure":     {"concept_miss"},
    # Time management is intentionally empty — Phase 2 wires it via a
    # separate impulse-detection path (time-per-move + is_focus_moment).
    "time_management":    set(),
}


def maybe_apply_goal_anchor(
    thread: Optional[Dict[str, Any]],
    session_focus: Optional[Dict[str, Any]],
    threads_pulled: Set[str],
) -> Optional[Dict[str, Any]]:
    """Decorate the fired conductor thread with a goal-anchor phrase when the
    thread kind aligns with today's session focus. Mutates thread["text"];
    silent otherwise. Once per session via `goal_anchor` in threads_pulled.

    Motivation: without this, the coach's chosen thread — even when it's a
    real teaching moment — doesn't reference today's stated goal, and the
    goal card feels passive. Anchoring the thread to the focus makes the
    connection explicit ("this IS the thing we're working on") so the goal
    surface feels connected to the play surface.
    """
    if not thread or not session_focus:
        return thread
    if "goal_anchor" in threads_pulled:
        return thread
    topic = session_focus.get("topic_key") or session_focus.get("focus_topic_key")
    if not topic:
        return thread
    kind = thread.get("kind") or ""
    aligned = _FOCUS_THREAD_ALIGNMENT.get(topic, set())
    if kind not in aligned:
        return thread
    # Human label — prefer what focus_bridge already computed for the UI so
    # the anchor and the goal card read as one voice.
    label = (
        session_focus.get("topic_label")
        or topic.replace("_", " ")
    )
    # Append rather than prepend — the thread text already leads with the
    # specific pattern ("There it is again — Loose piece"); the goal anchor
    # is a footnote that connects that specific to today's frame.
    anchor = f" That's your {label} focus this week."
    thread["text"] = (thread.get("text") or "") + anchor
    thread["goal_anchor_applied"] = True
    threads_pulled.add("goal_anchor")
    return thread


def compute_opening_strength_thread(
    *,
    move_history_san: Optional[List[str]],
    played_san: str,
    practical_tier: Optional[str],
    user_is_white: bool,
    strong_openings: Optional[Set[str]],
    threads_pulled: Set[str],
) -> Optional[Dict[str, Any]]:
    """Item E of docs/pwc_memory_wiring_scope.md. The mirror of
    compute_opening_thread — catches WINS in familiar-strong shapes.

    Fires when ALL hold:
      - User is currently in a canonical opening (opening_lookup gives us the family)
      - That opening is in the user's `strong_openings` set (≥5 games,
        ≥55% win rate — see services/player_performance.get_strong_openings)
      - The move is sound (practical_tier ∈ {good, best, excellent, brilliant})
        so we don't celebrate a strong opening on a blundered move
      - Restraint: once per opening family per game (same key as the
        mistake-side thread so mutually-exclusive within a game)

    Text is a plain STATEMENT — never "?", never a stat recital. Just
    the "trust it, this is your shape" nudge that lets the coach feel
    like it knows what the user owns.
    """
    if not played_san or not move_history_san or not strong_openings:
        return None
    if (practical_tier or "").lower() not in {"good", "best", "excellent", "brilliant"}:
        return None
    try:
        from services.opening_lookup import match_opening_for_mover
        from services.user_opening_profile import _normalize_opening_family
    except Exception:
        return None
    user_color = "white" if user_is_white else "black"
    try:
        current = match_opening_for_mover(list(move_history_san), user_color)
    except Exception:
        current = None
    if not current or not current.get("name"):
        return None
    family = _normalize_opening_family(current.get("name"))
    # strong_openings uses the raw opening name string; match on either
    # the family or the raw name if either is in the strong set.
    raw_name = (current.get("name") or "").lower()
    if family not in strong_openings and raw_name not in strong_openings:
        return None
    key = f"opening:{family}"
    if key in threads_pulled:
        return None
    threads_pulled.add(key)
    display = family or (current.get("name") or "this opening")
    return {
        "kind": "opening_strength", "motif": family, "side": "opening",
        "text": f"You own the {display} — this is your weapon. Trust it.",
    }


def compute_opening_thread(
    *,
    move_history_san: Optional[List[str]],
    played_san: str,
    best_move_san: Optional[str],
    practical_tier: Optional[str],
    user_is_white: bool,
    threads: Dict[str, Dict[str, Any]],
    threads_pulled: Set[str],
) -> Optional[Dict[str, Any]]:
    """Return an opening-recurrence STATEMENT for this user move, or None.

    Fires only when ALL hold (engine-true or silent):
      - the move is a real mistake in EVAL-STATE terms this instance
        (practical_tier in _OPENING_FIRE_TIERS — never on a still-winning move),
      - the canonical recognizer says the user is in a known opening with a book
        move pending (so this is a genuine first-deviation, in-book until now),
      - that opening family + this exact move are in the player's recurring-
        mistake digest (so we can honestly say "again"),
      - restraint: the family's thread hasn't fired yet this game.
    `prepend=True` → the caller prepends this framing to the move's caption,
    keeping the engine-grounded why + better move."""
    if not threads or not played_san or not move_history_san:
        return None
    if practical_tier not in _OPENING_FIRE_TIERS:
        return None
    try:
        from services.opening_lookup import match_opening_for_mover
        from services.user_opening_profile import _normalize_opening_family
    except Exception:
        return None
    user_color = "white" if user_is_white else "black"
    try:
        prior = match_opening_for_mover(list(move_history_san), user_color)
    except Exception:
        prior = None
    # next_expected None → book already ended (not an in-book first-deviation).
    if not prior or not prior.get("next_expected"):
        return None
    family = _normalize_opening_family(prior.get("name"))
    fam_threads = threads.get(family)
    if not fam_threads or played_san not in fam_threads:
        return None
    key = f"opening:{family}"
    if key in threads_pulled:
        return None
    threads_pulled.add(key)
    return {
        "kind": "opening_recur", "motif": family, "side": "opening", "prepend": True,
        # A natural memory lead-in that flows into the move's engine why (which
        # names the move + the better move), so the SAN isn't said twice.
        "text": f"You've been here before in the {family}.",
    }


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
