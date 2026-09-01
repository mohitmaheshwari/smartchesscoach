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
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 17  # v17 (2026-08-25): additive piece_safety.d_live.v1 fact.
# v16 introduced strict SEE for simple_hang. Schemas <16 are pre-SEE and must
# never enter PIC diagnosis/proof. v17 retains that detector and adds the
# comparable-decision fact validated in docs/simple_hang_corpus_evidence.md.

D_LIVE_FACT_VERSION = "piece_safety.d_live.v1"
D_LIVE_SEE_FLOOR_CP = 150
D_LIVE_CP_LOSS_FLOOR = 150
DERIVER_SEMANTIC_VERSION = "move_observation_deriver.17.1"


@lru_cache(maxsize=1)
def _deriver_identity_json() -> str:
    """Return the canonical semantic manifest once per process."""
    backend_root = Path(__file__).resolve().parent.parent
    dependency_paths = {
        "move_observation_deriver": Path(__file__).resolve(),
        "material_safety": backend_root
        / "coach_play"
        / "coach_blunder_guard.py",
        "opponent_threat": backend_root
        / "services"
        / "opponent_threat_detector.py",
    }
    dependencies = {}
    for name, path in sorted(dependency_paths.items()):
        dependencies[name] = {
            "path": path.relative_to(backend_root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    manifest = {
        "semantic_version": DERIVER_SEMANTIC_VERSION,
        "schema_version": SCHEMA_VERSION,
        "dependencies": dependencies,
    }
    canonical = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
    )
    identity = {
        **manifest,
        "manifest_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    return json.dumps(identity, sort_keys=True, separators=(",", ":"))


def current_deriver_identity() -> Dict[str, Any]:
    """Return a defensive copy of the current deterministic identity."""
    return json.loads(_deriver_identity_json())


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


def _safe_cp(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _derive_d_live_fact(mv: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the canonical piece_safety.d_live.v1 fact for one move.

    Eligibility and outcome are deliberately separate from `simple_hang`.
    `simple_hang` remains a high-precision positive diagnosis; D_live records
    every comparable destination-safety decision, including handled ones.
    """
    fact: Dict[str, Any] = {
        "version": D_LIVE_FACT_VERSION,
        "derivation_status": "ok",
        "eligible": False,
        "outcome": "not_eligible",
        "moved_piece": None,
        "legal_destination_captures": 0,
        "destination_see_cp": 0,
        "stockfish_cp_loss": _safe_cp(mv.get("cp_loss")),
    }
    fen = mv.get("fen_before")
    uci = str(mv.get("move_uci") or "")
    if not fen or len(uci) < 4:
        fact["derivation_status"] = "unavailable"
        fact["reason"] = "missing_position"
        return fact

    try:
        import chess
        from coach_play.coach_blunder_guard import see_gain

        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            fact["derivation_status"] = "unavailable"
            fact["reason"] = "illegal_move"
            return fact
        moved_piece = board.piece_at(move.from_square)
        if moved_piece is None:
            fact["derivation_status"] = "unavailable"
            fact["reason"] = "missing_piece"
            return fact

        fact["moved_piece"] = chess.piece_name(moved_piece.piece_type)
        if moved_piece.piece_type not in (
            chess.KNIGHT,
            chess.BISHOP,
            chess.ROOK,
            chess.QUEEN,
        ):
            fact["reason"] = "piece_not_eligible"
            return fact

        board_after = board.copy()
        board_after.push(move)
        captures = [
            reply
            for reply in board_after.legal_moves
            if board_after.is_capture(reply) and reply.to_square == move.to_square
        ]
        fact["legal_destination_captures"] = len(captures)
        if not captures:
            fact["reason"] = "not_legally_capturable"
            return fact

        destination_see = max(
            0,
            max(see_gain(board_after, reply) for reply in captures),
        )
        fact["eligible"] = True
        fact["destination_see_cp"] = destination_see
        fact["outcome"] = (
            "miss"
            if destination_see >= D_LIVE_SEE_FLOOR_CP
            and fact["stockfish_cp_loss"] >= D_LIVE_CP_LOSS_FLOOR
            else "handled"
        )
        return fact
    except Exception:
        fact["derivation_status"] = "unavailable"
        fact["reason"] = "derivation_error"
        return fact


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


# ---------------- Piece-safety subtype + severity classifier -------------
# See docs/piece_safety_subtype_scope.md for the full contract.

_PIECE_VALUES = {"p": 100, "n": 300, "b": 300, "r": 500, "q": 900, "k": 0}
_SEVERITY_LEVELS = ["minor", "moderate", "critical"]
_PS_BASE_SEVERITY = {
    "threat_ignored":    "moderate",
    "tactical_seq_loss": "moderate",
    "simple_hang":       "critical",
    "quiet_blunder":     "moderate",   # non-forcing high-cp loss, not a literal hang
    "small_slip":        "minor",
}


def _san_indicates_capture(san: str) -> bool:
    """SAN 'x' → capture. Robust fallback for the analyzer's unreliable
    cct_is_capture flag (which returns False for real captures like
    Rxc3, Qxc8 in some analyses)."""
    return isinstance(san, str) and "x" in san


def _is_king_move(fen_before: str, move_uci: str) -> bool:
    """Was the piece moved a king? King moves that lose material are
    king-safety issues, not piece-safety."""
    if not fen_before or not move_uci or len(move_uci) < 4:
        return False
    try:
        import chess
        board = chess.Board(fen_before)
        piece = board.piece_at(chess.Move.from_uci(move_uci).from_square)
        return piece is not None and piece.piece_type == chess.KING
    except Exception:
        return False


def _piece_is_hanging_after_move(
    fen_before: str, move_uci: str, floor_cp: int = 150
) -> Optional[bool]:
    """After the user makes the move, does it hang material — i.e. can the
    opponent win >= floor_cp in a single capture sequence (Static Exchange
    Evaluation)?

    Returns None if we can't tell (bad FEN, illegal move).

    v3 (2026-07-05): upgraded from a raw attacker>defender COUNT to proper
    SEE. The count version over-fired ~1/3 of the time — measured on the live
    corpus, only 66% of `simple_hang` events were real hangs under strict SEE.
    A bare count ignores piece VALUES and exchange order: a square with 2
    attackers vs 1 defender is NOT a hang if the cheapest attacker is worth
    more than it wins back (e.g. a pawn defended by a pawn, "attacked" by a
    rook and a queen — capturing loses the opponent material). SEE sorts by
    least-valuable attacker and models the option to stop capturing, so it
    only fires on a real net material loss. It also catches a hang on ANY
    square (a piece left hanging elsewhere), not just the destination.

    Reuses `material_hung_after` from coach_blunder_guard — the single source
    of truth for one-move material safety across the codebase."""
    if not fen_before or not move_uci or len(move_uci) < 4:
        return None
    try:
        import chess
        from coach_play.coach_blunder_guard import material_hung_after
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(move_uci)
        if mv not in board.legal_moves:
            return None
        worst, _ = material_hung_after(board, mv)
        return worst >= floor_cp
    except Exception:
        return None


def _opp_captured_users_piece(
    user_mv: Dict[str, Any], opp_next: Optional[Dict[str, Any]]
) -> bool:
    """Did opponent's next move capture on the square user just moved to?"""
    if not opp_next:
        return False
    user_uci = user_mv.get("move_uci") or ""
    opp_uci = opp_next.get("move_uci") or ""
    if len(user_uci) < 4 or len(opp_uci) < 4:
        return False
    if user_uci[2:4] != opp_uci[2:4]:
        return False
    return _san_indicates_capture(opp_next.get("move") or "") or bool(opp_next.get("cct_is_capture"))


def _material_value_captured(opp_next: Optional[Dict[str, Any]]) -> int:
    """Piece value the opponent's next move captured (0 if no capture / unknown).
    Uses python-chess against the FEN stored on opp_next."""
    if not opp_next:
        return 0
    try:
        import chess
        fen = opp_next.get("fen_before")
        uci = opp_next.get("move_uci")
        if not fen or not uci or len(uci) < 4:
            return 0
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        if not board.is_capture(move):
            return 0
        # En-passant target isn't on to_square
        if board.is_en_passant(move):
            return _PIECE_VALUES["p"]
        target = board.piece_at(move.to_square)
        if not target:
            return 0
        return _PIECE_VALUES.get(target.symbol().lower(), 0)
    except Exception:
        return 0


def _classify_piece_safety_subtype(
    mv: Dict[str, Any],
    opponent_previous: Optional[Dict[str, Any]],
    opp_next: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Classify a piece_safety event into a verified subtype.

    Returns None if the event should be DROPPED from piece_safety (e.g.,
    it was a king move — that's king_safety, not piece_safety).

    v2 (2026-07-02) — board-verified after Mohit found 86% mislabel rate:
      - was_capture uses SAN 'x' as source of truth (analyzer flag lies)
      - king moves get DROPPED (return None)
      - simple_hang REQUIRES python-chess to confirm the destination
        square has more attackers than defenders

    Order: king filter → threat_ignored → tactical_seq_loss → simple_hang
           → small_slip
    """
    cp_loss = mv.get("cp_loss") or 0
    san = mv.get("move") or ""
    fen = mv.get("fen_before")
    uci = mv.get("move_uci")

    # ── Drop king moves entirely — that's king_safety, not piece_safety
    if _is_king_move(fen, uci):
        return None

    # ── Real was_capture + was_forcing (SAN is source of truth; the
    # analyzer's cct_is_capture / cct_forcing flags are unreliable —
    # both were caught mislabeling ~13% of Parth's moves on 2026-07-02).
    was_capture = _san_indicates_capture(san)
    was_forcing = was_capture or san.endswith("+") or san.endswith("#")

    # threat_ignored fires ONLY when user did NOT respond forcefully.
    # A capture IS a response (right or wrong) — those route to
    # tactical_seq_loss below. Only quiet moves that leave the threat
    # unaddressed count as "ignoring."
    if (opponent_previous and opponent_previous.get("created_threat")
            and cp_loss >= 200 and not was_capture and not was_forcing):
        return "threat_ignored"
    if (was_forcing or was_capture) and cp_loss >= 150:
        return "tactical_seq_loss"
    # simple_hang REQUIRES board verification — the piece must actually be
    # attacked more than defended after the move.
    if (not was_forcing) and (not was_capture) and cp_loss >= 200:
        hanging = _piece_is_hanging_after_move(fen, uci)
        if hanging is True:
            return "simple_hang"
        # High cp, quiet move, but NOT board-verified as hanging — this is
        # a positional/strategic blunder, not a literal hang. Require a
        # LARGE cp_loss (>= 400) to be sure — otherwise the analyzer's
        # cognitive_gap tag is likely mis-attributed and coaching gets fuzzy.
        # (2026-07-03 R5: was 200, tightened after Shobhit-style fork
        # blunders showed cp=200-350 with dest_hanging=False.)
        if cp_loss >= 400:
            return "quiet_blunder"
        return "small_slip"
    return "small_slip"


def _classify_piece_safety_severity(
    subtype: str,
    mv: Dict[str, Any],
    opp_next: Optional[Dict[str, Any]],
) -> str:
    """Base severity from subtype; promote one level if ANY:
       A. execution_quality == "blunder"
       B. opp captures user's piece and material ≥ 300cp
       C. cp_loss ≥ 400 AND eval_before ≥ -300 (very bad, not already hopeless)
    """
    sev = _PS_BASE_SEVERITY.get(subtype, "minor")
    idx = _SEVERITY_LEVELS.index(sev)

    cp_loss = mv.get("cp_loss") or 0
    eval_before = mv.get("eval_before")
    if eval_before is None:
        eval_before = 0

    promote = False
    if mv.get("evaluation") == "blunder":
        promote = True
    elif _opp_captured_users_piece(mv, opp_next) and _material_value_captured(opp_next) >= 300:
        promote = True
    elif cp_loss >= 400 and eval_before >= -300:
        promote = True

    if promote:
        idx = min(idx + 1, len(_SEVERITY_LEVELS) - 1)
    return _SEVERITY_LEVELS[idx]


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

def _classify_time_flag(
    mv: Dict[str, Any],
    time_spent: Optional[float],
    time_left: Optional[float],
    user_color: str = "white",
) -> Optional[str]:
    """Per-move time flag. Returns None if the move doesn't hit any
    time-management pattern.

      - impulsive_critical  — critical moment played in <3s and mistake/blunder
      - time_pressure_blunder — <30s left and it was a blunder
      - slow_paralysis      — >90s spent on a non-critical move that blundered

    Coaching-relevance gate: skip moves where the user was ALREADY LOSING
    heavily (an impulsive move when you're down a queen isn't coachable).

    eval_before is stored from WHITE's perspective, so we sign-flip for
    black users. "Already losing heavily" = user_eval_before < -400.
    """
    quality = mv.get("evaluation")
    if quality not in ("mistake", "blunder"):
        return None

    # Coaching-relevance gate: skip when the blunder didn't change the
    # game's outcome. Two shapes to skip:
    #   (a) was already losing decisively AND still losing → not coachable
    #   (b) was already winning decisively AND still winning → not coachable
    # Both apply to the USER's perspective (sign-flip for black).
    eval_before = mv.get("eval_before")
    eval_after = mv.get("eval_after")
    if eval_before is not None and eval_after is not None:
        sign = 1 if user_color == "white" else -1
        user_eval_before = eval_before * sign
        user_eval_after = eval_after * sign
        # winning → still winning
        if user_eval_before > 300 and user_eval_after > 300:
            return None
        # losing → still losing
        if user_eval_before < -300 and user_eval_after < -300:
            return None
    was_critical = bool(mv.get("is_critical"))
    # v10/v14: suppress at low elapsed — clock-not-ticking data artifact,
    # not human impulse. Real fast moves take >= 0.5s to submit (v14
    # tightened from 0.1 after Parth mv61 Kg7 0.1s showed as impulse
    # in what was actually an increment-refreshed clock).
    if time_spent is not None and time_spent < 0.5:
        return None
    if time_spent is not None and was_critical and time_spent < 3:
        return "impulsive_critical"
    if time_left is not None and time_left < 30 and quality == "blunder":
        return "time_pressure_blunder"
    if time_spent is not None and time_spent > 90 and not was_critical:
        return "slow_paralysis"
    return None


def _time_flag_severity(flag: Optional[str], mv: Dict[str, Any]) -> Optional[str]:
    if flag is None:
        return None
    base = {"impulsive_critical": "critical",
            "time_pressure_blunder": "critical",
            "slow_paralysis": "moderate"}.get(flag, "minor")
    idx = ["minor", "moderate", "critical"].index(base)
    cp = mv.get("cp_loss") or 0
    eb = mv.get("eval_before") or 0
    if cp >= 400 and eb >= -300:
        idx = min(idx + 1, 2)
    return ["minor", "moderate", "critical"][idx]


def derive_observations_for_game(
    stockfish_analysis: Dict[str, Any],
    game_id: str,
    user_id: str,
    user_color: str = "white",
    decryption_v5_data: Optional[List[Dict[str, Any]]] = None,
    derived_at: Optional[datetime] = None,
    pgn: Optional[str] = None,
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

    # v9: parse PGN clocks once per game
    clocks: List[Optional[float]] = []
    increment: int = 0
    if pgn:
        try:
            from services.pgn_clock_parser import (
                parse_clocks_from_pgn, parse_increment_from_pgn,
            )
            clocks = parse_clocks_from_pgn(pgn)
            increment = parse_increment_from_pgn(pgn)
        except Exception:
            clocks = []
            increment = 0
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

        # Opponent's NEXT move (the one AFTER the user's move) — needed for
        # piece_safety subtype detection (did they capture our just-moved piece?)
        if user_color == "white":
            opp_next_mn = mn  # white plays N, then black plays N → opp N is next
        else:
            opp_next_mn = mn + 1  # black plays N, then white plays N+1 → opp N+1 is next
        opp_next = opp_by_mn.get(opp_next_mn)

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

        # Subtype + severity classification.
        # piece_safety uses the historical in-file classifier (board-verified).
        # All other 8 tags dispatch to services.cognitive_gap_subtypes.
        subtype: Optional[str] = None
        severity: Optional[str] = None
        if missed_pattern == "piece_safety":
            subtype = _classify_piece_safety_subtype(mv, opponent_previous, opp_next)
            if subtype is None:
                # King move — this isn't a piece_safety event. Reclassify.
                missed_pattern = "king_safety"
            else:
                severity = _classify_piece_safety_severity(subtype, mv, opp_next)

        if missed_pattern and subtype is None:
            # v8: king_safety events that are ENDGAME KING MOVES get rerouted
            # to endgame_technique. A king walking around in a rook endgame
            # is endgame technique, not middlegame king safety.
            if missed_pattern == "king_safety":
                try:
                    from services.cognitive_gap_subtypes import should_reroute_king_safety_to_endgame
                    if should_reroute_king_safety_to_endgame(mv):
                        missed_pattern = "endgame_technique"
                except Exception:
                    pass

            # v10: king_safety events where the MOVE actually hangs a piece
            # (board-verified attackers > defenders on destination) get
            # rerouted to piece_safety. This fixes Shobhit-style
            # "d6 tagged king_safety just because opp has pieces near king"
            # when the real mistake is losing the pawn on d6.
            if missed_pattern == "king_safety":
                try:
                    import chess as _chess
                    _fen = mv.get("fen_before")
                    _uci = mv.get("move_uci")
                    if _fen and _uci and len(_uci) >= 4:
                        _b = _chess.Board(_fen)
                        _mv2 = _chess.Move.from_uci(_uci)
                        _piece = _b.piece_at(_mv2.from_square)
                        if _piece and _piece.piece_type != _chess.KING:
                            _b.push(_mv2)
                            _dest = _mv2.to_square
                            _opp_col = _b.turn
                            _n_att = len(list(_b.attackers(_opp_col, _dest)))
                            _n_def = len(list(_b.attackers(not _opp_col, _dest)))
                            if _n_att > _n_def:
                                missed_pattern = "piece_safety"
                                # Re-run the piece_safety classifier now
                                subtype = _classify_piece_safety_subtype(mv, opponent_previous, opp_next)
                                if subtype is not None:
                                    severity = _classify_piece_safety_severity(subtype, mv, opp_next)
                except Exception:
                    pass

            # Dispatch to the multi-tag classifier
            try:
                from services.cognitive_gap_subtypes import classify as _classify_gap
                subtype, severity = _classify_gap(missed_pattern, mv, opponent_previous, opp_next)
            except Exception:
                subtype, severity = (None, None)

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
            "deriver_identity": current_deriver_identity(),

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
            "subtype": subtype,           # e.g., simple_hang / threat_ignored / tactical_seq_loss / small_slip
            "severity": severity,         # minor / moderate / critical (base + contextual promotion)
            "missed_free_piece": missed_free_piece,
            "ignored_opponent_threat": ignored_opponent_threat,
            "missed_opponent_blunder": missed_opponent_blunder,

            # Decision style
            "decision_register": _classify_register(mv),

            # PIC comparable decision. Exact nested version is mandatory for
            # proof queries; schemas <16 are never eligible for PIC evidence.
            "piece_safety_decision": _derive_d_live_fact(mv),
        }

        # v9: time management signals from PGN clocks
        time_spent = None
        time_left = None
        time_flag = None
        time_flag_severity = None
        if clocks:
            from services.pgn_clock_parser import (
                halfmove_index, time_spent_at_halfmove, time_left_at_halfmove,
            )
            hidx = halfmove_index(mv.get("move_number") or 0, user_color)
            time_spent = time_spent_at_halfmove(clocks, hidx, increment)
            time_left = time_left_at_halfmove(clocks, hidx)
            time_flag = _classify_time_flag(mv, time_spent, time_left, user_color=user_color)
            time_flag_severity = _time_flag_severity(time_flag, mv)
        obs["time_spent_seconds"] = time_spent
        obs["time_left_seconds"] = time_left
        obs["time_flag"] = time_flag
        obs["time_flag_severity"] = time_flag_severity

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
        "pattern_subtype_severity": {},
        "concept_used_counts": {},
        "tactical_pattern_executed_counts": {},
        "decision_register_counts": {},
        # v9: time-management signals rolled up per user
        "time_flag_counts": {},                # {flag_name: count}
        "time_flag_severity": {},              # {flag_name: {severity: count}}
        "time_spent_on_critical_moments": [],  # list of seconds; picker computes avg
        "n_critical_with_time_data": 0,
        "n_moves_with_time_data": 0,
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
            st = o.get("subtype")
            sv = o.get("severity")
            if st and sv:
                bucket = out["pattern_subtype_severity"].setdefault(mp, {}).setdefault(st, {})
                bucket[sv] = bucket.get(sv, 0) + 1
        if o.get("concept_used"):
            cu = o["concept_used"]
            out["concept_used_counts"][cu] = out["concept_used_counts"].get(cu, 0) + 1
        if o.get("tactical_pattern_executed"):
            tp = o["tactical_pattern_executed"]
            out["tactical_pattern_executed_counts"][tp] = out["tactical_pattern_executed_counts"].get(tp, 0) + 1
        if o.get("decision_register"):
            dr = o["decision_register"]
            out["decision_register_counts"][dr] = out["decision_register_counts"].get(dr, 0) + 1

        # v9: time management
        if o.get("time_spent_seconds") is not None:
            out["n_moves_with_time_data"] += 1
            if o.get("was_critical_moment"):
                out["time_spent_on_critical_moments"].append(o["time_spent_seconds"])
                out["n_critical_with_time_data"] += 1
        tf = o.get("time_flag")
        if tf:
            out["time_flag_counts"][tf] = out["time_flag_counts"].get(tf, 0) + 1
            tsev = o.get("time_flag_severity")
            if tsev:
                bucket = out["time_flag_severity"].setdefault(tf, {})
                bucket[tsev] = bucket.get(tsev, 0) + 1

    # Useful derived rates
    threats_total = out["responded_to_threat"] + out["ignored_opponent_threat"]
    if threats_total > 0:
        out["threat_response_rate"] = round(out["responded_to_threat"] / threats_total, 3)
    blunder_punish_total = out["punished_opponent_blunder"] + out["missed_opponent_blunder"]
    if blunder_punish_total > 0:
        out["blunder_punish_rate"] = round(out["punished_opponent_blunder"] / blunder_punish_total, 3)
    if out["critical_moments"] > 0:
        out["critical_find_rate"] = round(out["found_best_in_critical"] / out["critical_moments"], 3)

    # v9: derived time metrics
    if out["time_spent_on_critical_moments"]:
        tc = out["time_spent_on_critical_moments"]
        out["avg_time_on_critical_moment"] = round(sum(tc) / len(tc), 1)
        n_fast = sum(1 for t in tc if t < 10)
        out["pct_critical_played_fast"] = round(n_fast / len(tc), 3)
    # Drop the raw list from the returned aggregate (was a working buffer)
    del out["time_spent_on_critical_moments"]

    return out
