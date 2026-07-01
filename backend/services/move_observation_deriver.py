"""
Move Observation Deriver.

Reads existing stockfish_analysis.move_evaluations (+ optional
decryption_v5_data) and emits one structured behavioral observation per
USER move. No DB writes here — that's the backfill script's job. No
analyzer changes here — this is pure derivation from already-stored fields.

See docs/move_observations_scope.md for the data model + derivation
contract this implements.

Usage (pure function):
    obs_list = derive_observations_for_game(stockfish_analysis_dict,
                                             game_id, user_id,
                                             decryption_v5_data=None)
    # obs_list is a list of dicts, one per user move.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 3  # bumped: opponent threats now derived via python-chess from FEN when stored `threat` field is null


# ---------------- Small helpers -----------------------------------------

def _classify_phase(move_number: int) -> str:
    if move_number <= 15:
        return "opening"
    if move_number <= 35:
        return "middlegame"
    return "endgame"


def _is_good_enough(mv: Dict[str, Any]) -> bool:
    """Did the user effectively address what the position demanded?"""
    ev = mv.get("evaluation")
    cp_loss = mv.get("cp_loss") or 0
    return ev in ("best", "excellent", "good", "brilliant") and cp_loss < 50


def _classify_register(mv: Dict[str, Any]) -> Optional[str]:
    """forcing_when_best_was_forcing | quiet_when_best_was_quiet | wrong_register | None"""
    user_played_forcing = bool(mv.get("cct_forcing"))
    best_was_forcing = bool(mv.get("cct_best_was_forcing"))
    had_forcing_options = bool(mv.get("cct_had_forcing_options"))

    if not had_forcing_options:
        return None  # no decision to make about register
    if best_was_forcing and user_played_forcing:
        return "forcing_when_best_was_forcing"
    if (not best_was_forcing) and (not user_played_forcing):
        return "quiet_when_best_was_quiet"
    return "wrong_register"


def _build_opponent_previous(prev_mv: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Snapshot of opponent's previous move for context.

    v3: created_threat now derived via python-chess when the analyzer's
    stored `threat` field is null (which is ~always). Uses fen_before +
    move_uci to compute what target squares the opponent's move newly
    attacks. See services.opponent_threat_detector.
    """
    if not prev_mv:
        return None

    # First check the stored field
    stored_threat = prev_mv.get("threat")

    # Derive threats from the board if stored field is missing
    derived_threats: list = []
    if stored_threat is None:
        try:
            from services.opponent_threat_detector import detect_threats
            derived_threats = detect_threats(
                prev_mv.get("fen_before"),
                prev_mv.get("move_uci"),
            )
        except Exception:
            derived_threats = []

    created_threat = stored_threat is not None or bool(derived_threats)
    threat_squares = [t["square"] for t in derived_threats] if derived_threats else (
        [stored_threat] if stored_threat else []
    )

    # Also note if the derived threat included a "free piece" (undefended target)
    has_free_piece_threat = any(t.get("is_free") for t in derived_threats)
    has_fork = any(t.get("is_fork_component") for t in derived_threats)

    return {
        "move_san": prev_mv.get("move"),
        "created_threat": created_threat,
        "threat_squares": threat_squares,
        "has_free_piece_threat": has_free_piece_threat,
        "has_fork": has_fork,
        "was_capture": "x" in (prev_mv.get("move") or ""),  # SAN heuristic
        "was_check": (prev_mv.get("move") or "").endswith("+") or (prev_mv.get("move") or "").endswith("#"),
        "blundered": prev_mv.get("evaluation") == "blunder",
        "cp_loss": prev_mv.get("cp_loss") or 0,
    }


def _index_v5_by_move_number(v5_data: Optional[List[Dict[str, Any]]]) -> Dict[int, Dict[str, Any]]:
    out = {}
    for entry in (v5_data or []):
        mn = entry.get("move_number")
        if isinstance(mn, int) and entry.get("is_user_move"):
            out[mn] = entry
    return out


def _generate_coaching_takeaway(obs: Dict[str, Any]) -> str:
    """One-line human-readable takeaway from the structured observation.

    Deliberately template-based, not LLM-based — this runs over 9,500
    games and we want it deterministic + cheap. The LLM layer can polish
    these later if surfaced to users.
    """
    if obs.get("ignored_opponent_threat") and obs.get("execution_quality") in ("blunder", "mistake"):
        return f"Missed opponent's threat from {obs['opponent_previous']['move_san']} and {obs['execution_quality']}-ed."
    if obs.get("missed_opponent_blunder"):
        return f"Opponent blundered with {obs['opponent_previous']['move_san']}; you didn't punish it."
    if obs.get("punished_opponent_blunder"):
        return f"Opponent blundered with {obs['opponent_previous']['move_san']}; you punished it correctly."
    if obs.get("found_best_in_critical"):
        return "Found the best move in a critical moment."
    if obs.get("execution_quality") == "brilliant":
        return f"Brilliant move ({obs['move_san']})."
    if obs.get("tactical_pattern_executed"):
        return f"Executed a {obs['tactical_pattern_executed']} pattern."
    if obs.get("concept_used"):
        return f"Applied {obs['concept_used'].replace('_', ' ')}."
    if obs.get("execution_quality") == "blunder":
        pat = obs.get("missed_pattern")
        return f"Blunder ({obs['cp_loss']}cp loss" + (f", {pat})." if pat else ").")
    if obs.get("execution_quality") == "mistake":
        return f"Mistake ({obs['cp_loss']}cp loss)."
    if obs.get("decision_register") == "wrong_register":
        return "Played in the wrong register — forcing vs quiet mismatch."
    if obs.get("execution_quality") == "inaccuracy":
        # Small fallback so inaccuracies don't go uncoached. We don't have a
        # specific cognitive_gap (that fires mostly for blunder/mistake), but
        # we can still note it for the per-move record.
        return f"Inaccuracy ({obs['cp_loss']}cp loss) — close to best but not quite."
    return ""  # routine good/best move, nothing notable


# ---------------- The main derivation function ---------------------------

def derive_observations_for_game(
    stockfish_analysis: Dict[str, Any],
    game_id: str,
    user_id: str,
    user_color: str = "white",
    decryption_v5_data: Optional[List[Dict[str, Any]]] = None,
    derived_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Returns a list of observation dicts (one per user move) for a single game.

    v2: reads BOTH stockfish_analysis.move_evaluations (user moves) AND
    stockfish_analysis.opponent_move_evaluations (opponent moves). Pairs
    them by move_number to derive opponent_previous context. When
    user_color=white, the "previous opponent move" for user's move N is
    opponent's move N-1. When user_color=black, opponent's move N came
    BEFORE user's move N.
    """
    derived_at = derived_at or datetime.now(timezone.utc)
    moves = stockfish_analysis.get("move_evaluations") or []
    opp_moves = stockfish_analysis.get("opponent_move_evaluations") or []
    # Index opponent moves by move_number for O(1) lookup
    opp_by_mn: Dict[int, Dict[str, Any]] = {}
    for om in opp_moves:
        mn = om.get("move_number")
        if isinstance(mn, int):
            opp_by_mn[mn] = om
    v5_by_mn = _index_v5_by_move_number(decryption_v5_data)

    obs_list: List[Dict[str, Any]] = []
    for mv in moves:
        if mv.get("is_opponent_move"):
            continue  # defensive — move_evaluations should already be user-only

        # Look up opponent's PREVIOUS move (the one they just played before the user)
        mn = mv.get("move_number") or 0
        if user_color == "white":
            # White plays move N first, then black plays move N. Opponent's previous = move N-1.
            opp_previous_mn = mn - 1
        else:
            # Black is user. White plays move N first, THEN black plays move N.
            # Opponent's previous = same move_number.
            opp_previous_mn = mn
        prev = opp_by_mn.get(opp_previous_mn) if opp_previous_mn > 0 else None
        opponent_previous = _build_opponent_previous(prev)

        # v5 enrichment if available (concept_applied, shape_pattern_id, etc.)
        v5_entry = v5_by_mn.get(mv.get("move_number"))
        concept_used = None
        tactical_pattern_executed = None
        if v5_entry and mv.get("evaluation") in ("best", "excellent", "good", "brilliant"):
            ca = v5_entry.get("concept_applied")
            if ca and ca != "None":
                concept_used = ca
            sp = v5_entry.get("shape_pattern_id")
            if sp and sp != "None":
                tactical_pattern_executed = sp

        missed_pattern = None
        missed_free_piece = False
        if mv.get("evaluation") in ("blunder", "mistake"):
            cg = mv.get("cognitive_gap")
            if cg and cg != "none":
                missed_pattern = cg
            if v5_entry:
                sp = v5_entry.get("shape_pattern_id")
                if sp == "free_piece":
                    missed_free_piece = True

        responded_to_threat = (
            opponent_previous is not None
            and opponent_previous["created_threat"]
            and _is_good_enough(mv)
        )
        ignored_opponent_threat = (
            opponent_previous is not None
            and opponent_previous["created_threat"]
            and not _is_good_enough(mv)
        )
        punished_opponent_blunder = (
            opponent_previous is not None
            and opponent_previous["blundered"]
            and mv.get("evaluation") in ("best", "excellent", "brilliant")
        )
        missed_opponent_blunder = (
            opponent_previous is not None
            and opponent_previous["blundered"]
            and mv.get("evaluation") not in ("best", "excellent", "brilliant")
        )
        found_best_in_critical = (
            bool(mv.get("is_critical"))
            and mv.get("evaluation") == "best"
        )

        obs = {
            "user_id": user_id,
            "game_id": game_id,
            "move_number": mv.get("move_number"),
            "ply": (mv.get("move_number") or 0) * 2 - (0 if user_color == "white" else 1),
            "color": user_color,
            "derived_at": derived_at,
            "schema_version": SCHEMA_VERSION,

            # Position context
            "fen_before": mv.get("fen_before"),
            "phase": _classify_phase(mv.get("move_number") or 0),
            "was_critical_moment": bool(mv.get("is_critical")),

            # Opponent's previous move
            "opponent_previous": opponent_previous,

            # The user's move (raw)
            "move_san": mv.get("move"),
            "move_uci": mv.get("move_uci"),
            "execution_quality": mv.get("evaluation"),
            "cp_loss": mv.get("cp_loss") or 0,
            "eval_before": mv.get("eval_before"),
            "eval_after": mv.get("eval_after"),
            "was_forcing": bool(mv.get("cct_forcing")),
            "was_check": bool(mv.get("cct_is_check")),
            "was_capture": bool(mv.get("cct_is_capture")),
            "was_castle": (mv.get("move") or "") in ("O-O", "O-O-O", "0-0", "0-0-0"),

            # Positive observations
            "concept_used": concept_used,
            "tactical_pattern_executed": tactical_pattern_executed,
            "responded_to_threat": responded_to_threat,
            "punished_opponent_blunder": punished_opponent_blunder,
            "found_best_in_critical": found_best_in_critical,

            # Gap observations
            "missed_pattern": missed_pattern,
            "missed_free_piece": missed_free_piece,
            "ignored_opponent_threat": ignored_opponent_threat,
            "missed_opponent_blunder": missed_opponent_blunder,

            # Decision style
            "decision_register": _classify_register(mv),
        }

        obs["coaching_takeaway"] = _generate_coaching_takeaway(obs)
        obs_list.append(obs)

    return obs_list


# ---------------- Aggregation helpers (for downstream consumers) ---------

def aggregate_user_signals(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll up per-user-aggregate signals from a list of that user's observations.

    Designed to replace what player_profile.top_weaknesses does — but with
    POSITIVE signals too. Pure function; caller decides how to use it.
    """
    if not observations:
        return {}

    total = len(observations)
    out: Dict[str, Any] = {
        "total_user_moves": total,
        "phases": {"opening": 0, "middlegame": 0, "endgame": 0},
        "execution_dist": {},
        "critical_moments": 0,
        "found_best_in_critical": 0,
        "responded_to_threat": 0,
        "ignored_opponent_threat": 0,
        "punished_opponent_blunder": 0,
        "missed_opponent_blunder": 0,
        "missed_pattern_counts": {},
        "concept_used_counts": {},
        "tactical_pattern_executed_counts": {},
        "decision_register_counts": {},
    }
    for o in observations:
        out["phases"][o.get("phase", "middlegame")] = out["phases"].get(o.get("phase", "middlegame"), 0) + 1
        ev = o.get("execution_quality") or "unknown"
        out["execution_dist"][ev] = out["execution_dist"].get(ev, 0) + 1
        if o.get("was_critical_moment"):
            out["critical_moments"] += 1
            if o.get("found_best_in_critical"):
                out["found_best_in_critical"] += 1
        for k in ("responded_to_threat", "ignored_opponent_threat",
                  "punished_opponent_blunder", "missed_opponent_blunder"):
            if o.get(k):
                out[k] += 1
        if o.get("missed_pattern"):
            mp = o["missed_pattern"]
            out["missed_pattern_counts"][mp] = out["missed_pattern_counts"].get(mp, 0) + 1
        if o.get("concept_used"):
            cu = o["concept_used"]
            out["concept_used_counts"][cu] = out["concept_used_counts"].get(cu, 0) + 1
        if o.get("tactical_pattern_executed"):
            tp = o["tactical_pattern_executed"]
            out["tactical_pattern_executed_counts"][tp] = out["tactical_pattern_executed_counts"].get(tp, 0) + 1
        if o.get("decision_register"):
            dr = o["decision_register"]
            out["decision_register_counts"][dr] = out["decision_register_counts"].get(dr, 0) + 1

    # Useful derived rates
    threats_total = out["responded_to_threat"] + out["ignored_opponent_threat"]
    if threats_total > 0:
        out["threat_response_rate"] = round(out["responded_to_threat"] / threats_total, 3)
    blunder_punish_total = out["punished_opponent_blunder"] + out["missed_opponent_blunder"]
    if blunder_punish_total > 0:
        out["blunder_punish_rate"] = round(out["punished_opponent_blunder"] / blunder_punish_total, 3)
    if out["critical_moments"] > 0:
        out["critical_find_rate"] = round(out["found_best_in_critical"] / out["critical_moments"], 3)

    return out
