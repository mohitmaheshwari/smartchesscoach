"""
Puzzle Extraction Pipeline
==========================

Extracts training puzzles from analyzed games automatically.
When a game is analyzed and blunders are detected, the position BEFORE
the bad move becomes a training puzzle tagged with the cognitive gap.

These puzzles form the "community" pool that other users with the same
weakness pattern get served.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import asyncio
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
import chess
import logging
import os

from services.back_rank_mate_puzzle_proof import BACK_RANK_MATE_QUALITY_ID
from services.forced_mate_puzzle_proof import FORCED_MATE_QUALITY_ID
from services.verified_puzzle_admission import (
    ADMISSION_VERSION,
    AdmissionStatus,
    stored_verdict_is_structurally_current,
)
from services.verified_puzzle_builder import build_imported_game_verdict

logger = logging.getLogger(__name__)


# ── The mate drill label ────────────────────────────────────────────────────
# A forced mate is already PROVEN and already recorded on every row it
# applies to: `verified_admission.quality_id` is tactic:forced_mate_exact or
# tactic:back_rank_mate_exact, written by forced_mate_puzzle_proof /
# back_rank_mate_puzzle_proof, each of which carries its own independent
# legal-replay verifier. So this label is a VIEW over that one stored fact.
# Nothing new is detected, nothing is written a second time, and no backfill
# is needed to find the rows that already exist.
#
# Why a view and not a new field. Writing "forced_mate" into `issue_type`
# was the obvious move and is the wrong one: `issue_type` is also the key
# four other readers use, and a mate row would silently leave all of them.
# Measured on the live pool 2026-10-13: 358 of 50,554 approved rows in the
# diagnostic's seven issue types (0.71%) are proven mates and would have
# dropped out of onboarding; home.py's `{"issue_type": problem_cat}` query
# and both PWC pattern maps would have lost them too. Deriving the label
# costs nothing and subtracts nothing.
#
# Why this name. It is the vocabulary the codebase already uses for exactly
# this thing: caption concept_id "tactic.forced_mate" and the module
# forced_mate_puzzle_proof. "mate" is new vocabulary for an old idea;
# "checkmate_pattern" is a dead community_training_positions pattern_type
# with 0 rows of 53,610 (counted, not assumed).
#
# forced_mate is a NARROWER request than the category a mate row is filed
# under, never a replacement for it. A missed mate's cognitive_gap stays
# missed_tactic on purpose -- analysis_interpreter explains why routing
# mates elsewhere was "the single largest source of mislabelling in the
# product" -- so every row that serves forced_mate keeps serving its broad
# category as well.
FORCED_MATE_PATTERN = "forced_mate"
FORCED_MATE_QUALITY_IDS = (FORCED_MATE_QUALITY_ID, BACK_RANK_MATE_QUALITY_ID)


def is_forced_mate_quality(quality_id) -> bool:
    """Whether a proven answer is a proven mate. The one test, in one place."""
    return str(quality_id or "") in FORCED_MATE_QUALITY_IDS


def forced_mate_mongo_clause() -> Dict:
    """Pool filter for the mate label, for an indexed query.

    Deliberately independent of `verified_puzzle_admission_enforced()`: the
    quality_id is only ever written alongside a passing verifier, so this
    predicate proves the mate on its own and needs no help from the
    enforcement clause. That also means an unenforced deployment serves the
    same rows as an enforced one rather than silently serving none.
    """
    return {
        "verified_admission.quality_id": {"$in": list(FORCED_MATE_QUALITY_IDS)}
    }


def pattern_pool_clause(pattern: str) -> Dict:
    """How a pool query names the requested drill.

    For forced_mate the stored `issue_type` is the broad category the row
    was filed under (missed_tactic on 358 of 358 live rows), so asking for
    `issue_type == "forced_mate"` would match nothing. The quality_id is the
    label's actual source, so it is what the query asks for.
    """
    if pattern == FORCED_MATE_PATTERN:
        return forced_mate_mongo_clause()
    return {"issue_type": pattern}


def stored_pattern_label(document: Dict) -> str:
    """The drill label a stored pool row should be served under.

    The read-side half of the same rule the write side applies, so a row can
    never be found under one label and then described to the player as
    another. `community_puzzles` spells the broad label `issue_type` and
    `community_training_positions` spells it `pattern_type`; both are read.
    """
    verdict = document.get("verified_admission") or {}
    if is_forced_mate_quality(verdict.get("quality_id")):
        return FORCED_MATE_PATTERN
    return (
        document.get("issue_type")
        or document.get("pattern_type")
        or verdict.get("broad_category")
        or "calculation_depth"
    )


def verified_puzzle_admission_enforced() -> bool:
    """Whether serving is restricted to current verified-admission rows.

    Fail-closed by default. A deployment must explicitly opt into unsafe
    compatibility during a controlled offline backfill; ordinary starts never
    serve legacy rows. Enabling it never invokes an engine or an LLM.
    """
    return os.getenv("VERIFIED_PUZZLE_ADMISSION_ENFORCED", "true").lower() in {
        "1", "true", "yes", "on",
    }


def verified_issue_type(verdict) -> str:
    if verdict.status in {AdmissionStatus.SPECIFIC, AdmissionStatus.BROAD}:
        return verdict.broad_category or "calculation_depth"
    return "calculation_depth"


def verdict_serves_pattern(document: Dict, pattern: str) -> bool:
    """Return whether a stored verdict honestly supports this drill label."""
    if pattern == FORCED_MATE_PATTERN:
        # Checked before the enforcement shortcut below, which returns True
        # for everything: a mate drill that quietly served non-mates while
        # unenforced would be a worse lie than serving nothing.
        if not stored_verdict_is_structurally_current(document):
            return False
        verdict = document.get("verified_admission") or {}
        return (
            verdict.get("status") in {
                AdmissionStatus.SPECIFIC.value, AdmissionStatus.BROAD.value,
            }
            and is_forced_mate_quality(verdict.get("quality_id"))
        )
    if not verified_puzzle_admission_enforced():
        return True
    if not stored_verdict_is_structurally_current(document):
        return False
    verdict = document.get("verified_admission") or {}
    status = verdict.get("status")
    if status in {AdmissionStatus.SPECIFIC.value, AdmissionStatus.BROAD.value}:
        return verdict.get("broad_category") == pattern
    return status == AdmissionStatus.GENERIC.value and pattern == "calculation_depth"


def verified_mongo_clause(pattern: str) -> Dict:
    """Mongo clause equivalent of verdict_serves_pattern for indexed pools."""
    if pattern == FORCED_MATE_PATTERN:
        # Same ordering as verdict_serves_pattern, for the same reason.
        return {
            "approved": True,
            "verified_admission.admission_version": ADMISSION_VERSION,
            "verified_admission.reason_codes.0": {"$exists": True},
            "verified_admission.source_kind": {"$type": "string", "$ne": ""},
            "verified_admission.source_fingerprint": {"$type": "string", "$ne": ""},
            "verified_admission.analysis_fingerprint": {"$type": "string", "$ne": ""},
            "verified_admission.reconstructed_fen": {"$type": "string", "$ne": ""},
            "verified_admission.played_move_uci": {"$type": "string", "$ne": ""},
            "verified_admission.acceptable_moves_uci.0": {"$exists": True},
            "verified_admission.status": {
                "$in": [
                    AdmissionStatus.SPECIFIC.value,
                    AdmissionStatus.BROAD.value,
                ]
            },
            **forced_mate_mongo_clause(),
        }
    if not verified_puzzle_admission_enforced():
        return {}
    specific_or_broad = {
        "verified_admission.status": {
            "$in": [AdmissionStatus.SPECIFIC.value, AdmissionStatus.BROAD.value]
        },
        "verified_admission.broad_category": pattern,
    }
    supported = [specific_or_broad]
    if pattern == "calculation_depth":
        supported.append({
            "verified_admission.status": AdmissionStatus.GENERIC.value,
        })
    return {
        "approved": True,
        "verified_admission.admission_version": ADMISSION_VERSION,
        "verified_admission.reason_codes.0": {"$exists": True},
        "verified_admission.source_kind": {"$type": "string", "$ne": ""},
        "verified_admission.source_fingerprint": {"$type": "string", "$ne": ""},
        "verified_admission.analysis_fingerprint": {"$type": "string", "$ne": ""},
        "verified_admission.reconstructed_fen": {"$type": "string", "$ne": ""},
        "verified_admission.played_move_uci": {"$type": "string", "$ne": ""},
        "verified_admission.acceptable_moves_uci.0": {"$exists": True},
        "$or": supported,
    }


def verified_pool_mongo_clause() -> Dict:
    """Filter for any current non-quarantined admission level."""
    if not verified_puzzle_admission_enforced():
        return {}
    return {
        "approved": True,
        "verified_admission.admission_version": ADMISSION_VERSION,
        "verified_admission.reason_codes.0": {"$exists": True},
        "verified_admission.source_kind": {"$type": "string", "$ne": ""},
        "verified_admission.source_fingerprint": {"$type": "string", "$ne": ""},
        "verified_admission.analysis_fingerprint": {"$type": "string", "$ne": ""},
        "verified_admission.reconstructed_fen": {"$type": "string", "$ne": ""},
        "verified_admission.played_move_uci": {"$type": "string", "$ne": ""},
        "verified_admission.acceptable_moves_uci.0": {"$exists": True},
        "verified_admission.status": {
            "$in": [
                AdmissionStatus.SPECIFIC.value,
                AdmissionStatus.BROAD.value,
                AdmissionStatus.GENERIC.value,
            ]
        },
    }


# ── Quality gates for "is this position worth keeping as a puzzle?" ──
# Loose extraction gave us positional moves where the engine prefers
# move A over move B by 30cp — bad teaching material because there's
# no clean idea to teach. Real puzzles need a forcing best move OR a
# detectable tactical pattern.

# Mate-detection sentinel cap. cp_loss can spike to 5000+ on missed
# mates; we exclude those — "find mate-in-7" is not a 1200 puzzle.
PUZZLE_MAX_CP_LOSS = 2000

# Below this rating, an endgame-phase mistake (move > END_PHASE_PLY)
# usually isn't tactical training material — they need pattern training,
# not endgame conversion grind.
ENDGAME_FILTER_RATING = 1500


def minimum_extraction_cp_loss(user_rating: int) -> int:
    """Return the candidate floor; admission still decides if it is teachable.

    This intentionally controls candidate recall, not puzzle truth. A position
    above this floor is still rejected unless the stored line and deterministic
    admission/verifier pipeline establish a legal, teachable answer.
    """
    if user_rating < 1000:
        return 75
    if user_rating < 1400:
        return 50
    if user_rating < 1800:
        return 30
    return 20
END_PHASE_PLY = 30  # full-move number, not ply


def _forced_mate_position(
    fen_before: str,
    best_move_san: Optional[str],
    pv_after_best: Optional[List[str]],
    cp_loss: int,
) -> bool:
    """True when the engine's line from here is a forced mate.

    Reuses missed_mate_detector, which forced_mate_puzzle_proof already
    depends on, rather than re-deriving "is this a mate" a second time.
    """
    try:
        import chess as _chess

        from services.missed_mate_detector import detect_missed_mate

        board = _chess.Board(fen_before)
        return bool(detect_missed_mate(
            board, best_move_san, list(pv_after_best or []), cp_loss))
    except Exception:
        return False


def forced_mate_candidate(move_evaluation: Dict) -> bool:
    """Cheap candidate test for "this stored move missed a forced mate".

    The same `_forced_mate_position` prover, reading a stored
    move_evaluation, so a caller that holds one does not unpack it itself.
    This is the CANDIDATE half only; the full proof with its independent
    legal replay still runs in forced_mate_puzzle_proof via admission, and
    the serving filters require that proof, not this.

    It exists because no stored label identifies a missed mate. The
    cognitive_gap of one is deliberately broad -- measured on the 358 live
    mate rows it is `missed_tactic` or `tactical_oversight` -- so a caller
    that pre-filters by gap string would miss them. The prover decides.
    """
    pv = move_evaluation.get("pv_after_best") or []
    try:
        cp_loss = int(move_evaluation.get("cp_loss") or 0)
    except (TypeError, ValueError):
        return False
    return _forced_mate_position(
        move_evaluation.get("fen_before"),
        move_evaluation.get("best_move_san") or move_evaluation.get("best_move"),
        pv if isinstance(pv, list) else [],
        cp_loss,
    )


def _is_puzzle_worthy(
    fen_before: str,
    best_move_san: str,
    best_move_uci: Optional[str],
    pv_after_best: Optional[List[str]],
    move_number: int,
    user_rating: int,
    cp_loss: int,
) -> bool:
    """Decide whether a (position, best_move) pair is good teaching
    material. Three checks:

    1. cp_loss in bounds, OR the line is a proven forced mate
    2. Best move is forcing (capture / check / mate) OR
       pv_tactical_analyzer detects a real pattern

    There is no phase/rating filter: teachability is decided by the
    forcing test and the admission verifier, not by move number.
    """
    # 1. Bounds
    if cp_loss <= 0:
        return False
    if cp_loss > PUZZLE_MAX_CP_LOSS:
        # ...unless the engine line is a PROVEN forced mate. The cap
        # exists to keep mate sentinels out of the pool, but a missed
        # mate IS the sentinel: cp_loss reads 8,701 / 9,028 / 9,279 and
        # the position is the single most teachable thing in the game.
        # Measured on one user: 108 missed mates, 84 over this cap, 96
        # rejected overall, 12 admitted.
        #
        # Proven by detect_missed_mate -- the same prover
        # forced_mate_puzzle_proof uses -- so nothing is admitted on the
        # size of a number alone.
        if not _forced_mate_position(fen_before, best_move_san,
                                     pv_after_best, cp_loss):
            return False

    # 3. (removed 2026-10-13) There used to be a phase filter here:
    #     if user_rating < ENDGAME_FILTER_RATING and
    #        move_number > END_PHASE_PLY: return False
    #
    # It justified itself as "they need pattern training, not endgame
    # conversion grind", but it never tested for an endgame -- it tested
    # move_number > 30, which is usually a middlegame with most pieces
    # still on. And it sat above the two gates that DO judge teaching
    # value: the forcing test below, and the admission verifier whose
    # own comment says "admission still decides if it is teachable".
    #
    # Measured over 3,001 games: of 7,273 positions that passed every
    # other gate, 1,351 (18.6%) were rejected by this rule alone, 93 of
    # them missed MATES. A mate in two at move 40 is the most drillable
    # thing a 1200 can be given.
    #
    # Mohit 2026-10-13: "anything in the game can be taught and should
    # be taught, so every teaching lesson should be taken."

    # 2. Forcing test (cheap): capture / check / mate marker in SAN.
    san = (best_move_san or "").strip()
    if not san:
        return False
    is_forcing = any(ch in san for ch in ("x", "+", "#"))

    if is_forcing:
        return True

    # 2b. Tactical-pattern test (more expensive): does the engine's PV
    # show a fork/pin/skewer/discovery/exposed-defender after best move?
    # If yes, it's a real pattern even though SAN doesn't have x/+/#
    # (e.g., a quiet move that sets up a winning threat).
    if best_move_uci and pv_after_best:
        try:
            from services.pv_tactical_analyzer import explain_best_move_tactically
            tactical = explain_best_move_tactically(
                fen_before, best_move_uci, san, pv_after_best
            )
            if tactical:
                return True
        except Exception as e:
            logger.debug(f"pv_tactical_analyzer failed for puzzle screen: {e}")

    # No forcing move, no detectable pattern — likely a positional
    # preference. Skip; it's not pattern training.
    return False


async def extract_puzzles_from_game(
    db: AsyncIOMotorDatabase,
    game_id: str,
    user_id: str,
) -> List[Dict]:
    """
    Extract training puzzles from an analyzed game.
    Uses rating-aware thresholds to determine what counts as a meaningful
    blunder worth extracting. An 800 player's 80cp inaccuracy isn't
    puzzle-worthy; their 300cp blunder is.
    """
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0},
    )
    if not analysis:
        return []

    game = await db.games.find_one(
        {"game_id": game_id},
        {
            "_id": 0,
            "game_id": 1,
            "pgn": 1,
            "user_color": 1,
            "opening": 1,
            "opening_eco": 1,
        },
    )
    if not game:
        return []

    # Get user's rating for threshold calculation
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "rating": 1})
    user_rating = (user_doc or {}).get("rating", 1200)

    # Rating-aware extraction thresholds (centipawns)
    # AGGRESSIVE backfill: extract ALL mistakes, not just big blunders
    # More drill material = more learning opportunity
    min_cp_loss = minimum_extraction_cp_loss(user_rating)

    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    user_color = game.get("user_color", "white")

    created = []

    skipped_quality = 0
    for ev in evals:
        cp_loss = ev.get("cp_loss", 0)
        # Rating-aware threshold
        if cp_loss < min_cp_loss:
            continue

        fen_before = ev.get("fen_before")
        # Support both field names
        best_move = ev.get("best_move_san") or ev.get("best_move")
        best_move_uci = ev.get("best_move_uci")
        pv_after_best = ev.get("pv_after_best") or []
        cognitive_gap = ev.get("cognitive_gap", "")
        move_number = ev.get("move_number", 0)

        if not fen_before or not best_move:
            continue

        # A training question belongs to the source player, not their
        # opponent. New analyses say this explicitly; the FEN turn is the
        # deterministic fallback for older rows.
        if ev.get("is_opponent_move") is True or ev.get("is_user_move") is False:
            continue
        try:
            mover_is_white = chess.Board(fen_before).turn == chess.WHITE
            if mover_is_white != (str(user_color).lower() == "white"):
                continue
        except ValueError:
            continue

        # Keep the legacy forcing-position screen while the verified feed is
        # dark. Once enforcement is enabled, an objectively answerable quiet
        # move may still become a generic calculation exercise instead of
        # disappearing merely because a tactical recognizer does not fire.
        legacy_worthy = _is_puzzle_worthy(
            fen_before=fen_before,
            best_move_san=best_move,
            best_move_uci=best_move_uci,
            pv_after_best=pv_after_best if isinstance(pv_after_best, list) else [],
            move_number=move_number,
            user_rating=int(user_rating or 1200),
            cp_loss=int(cp_loss),
        )
        if not legacy_worthy and not verified_puzzle_admission_enforced():
            skipped_quality += 1
            continue

        # Do not infer a chess diagnosis from cp_loss or raw attacker counts.
        # The shared builder reconstructs the source PGN, checks the stored
        # answer, and runs independent causal proof where one exists.
        verdict = build_imported_game_verdict(
            game=game,
            move_evaluation=ev,
            broad_category=cognitive_gap or None,
        )
        verified_issue = verified_issue_type(verdict)
        approved = verdict.status != AdmissionStatus.QUARANTINE

        # Skip if puzzle already exists (same FEN + best move)
        existing = await db.community_puzzles.find_one({
            "fen": fen_before,
            "best_move_san": best_move,
        })
        if existing:
            continue

        # Determine difficulty from cp_loss
        if cp_loss >= 400:
            difficulty = "beginner"  # Big blunder = obvious to spot
        elif cp_loss >= 200:
            difficulty = "intermediate"
        else:
            difficulty = "advanced"  # Subtle mistake

        puzzle = {
            "fen": fen_before,
            "best_move_san": best_move,
            "best_move_uci": best_move_uci,
            "played_move": ev.get("move") or ev.get("move_san") or ev.get("played_move"),
            "issue_type": verified_issue,
            "legacy_issue_type": cognitive_gap or None,
            "theme": _gap_to_theme(verified_issue),
            "difficulty": difficulty,
            "opening_name": game.get("opening"),
            "opening_eco": game.get("opening_eco"),
            "move_number": move_number,
            "user_color": user_color,
            "shared_by": user_id,
            "source_game_id": game_id,
            "source": "auto_extracted",
            "description": (
                "From a real game — find the move that keeps every piece safe."
                if verified_issue == "piece_safety"
                else "From a real game — calculate the best continuation."
            ),
            "cp_loss": cp_loss,
            "pv_after_best": pv_after_best if isinstance(pv_after_best, list) else [],
            "pv_after_played": ev.get("pv_after_played") or [],
            "verified_admission": verdict.to_document(),
            "attempts": 0,
            "solves": 0,
            "solve_rate": 0.0,
            # `rating` = rating of the source user (whose game produced this puzzle).
            # Used by the serve-time rating filter so a 900-rated player doesn't
            # get puzzles from 1800-rated games. Stored from user_rating on
            # extraction; `ratings: []` + `avg_rating` separately track the
            # RATINGS OF USERS WHO ATTEMPT this puzzle (a different thing).
            "rating": int(user_rating) if user_rating else 1200,
            "ratings": [],
            "avg_rating": 0.0,
            "created_at": datetime.now(timezone.utc),
            "approved": approved,
            "featured": False,
        }

        # Maia is metadata only: it estimates how findable the already-proven
        # answer is on the measured 800/1000/1200/1400 grid.  It cannot approve,
        # reject, relabel, reorder or change this puzzle's answer/difficulty.
        try:
            from services.puzzle_human_difficulty_shadow import (
                build_puzzle_human_difficulty_shadow,
            )

            shadow_answer_uci = best_move_uci
            if not shadow_answer_uci:
                shadow_answer_uci = chess.Board(fen_before).parse_san(best_move).uci()
            human_shadow, human_shadow_reason = await asyncio.to_thread(
                build_puzzle_human_difficulty_shadow,
                fen=fen_before,
                answer_uci=shadow_answer_uci,
            )
            puzzle["human_difficulty_shadow_reason"] = human_shadow_reason
            if human_shadow is not None:
                puzzle["human_difficulty_shadow"] = human_shadow.contract_dict()
        except Exception:
            puzzle["human_difficulty_shadow_reason"] = "runtime_failure"

        # Motif tag (fork; pin/skewer later) — the tactical motif the blunder walked into,
        # via the verified detector. Lets weakness drills filter by motif (own→community).
        try:
            from services.motif_profile_service import position_allows_motif
            _motif = position_allows_motif(ev)
            if _motif:
                puzzle["motif"] = _motif
        except Exception:
            pass

        result = await db.community_puzzles.insert_one(puzzle)
        puzzle_copy = {k: v for k, v in puzzle.items() if k != "_id"}
        puzzle_copy["puzzle_id"] = str(result.inserted_id)
        created.append(puzzle_copy)

    if created or skipped_quality:
        logger.info(
            f"Extracted {len(created)} puzzles from game {game_id} "
            f"(user {user_id}, skipped {skipped_quality} positional/no-pattern)"
        )

    return created


async def backfill_puzzles_for_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    max_games: int = 30,
) -> int:
    """
    Backfill puzzles from a user's already-analyzed games.
    Returns total puzzles created.
    """
    # Find games that have analyses (regardless of is_analyzed flag)
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1},
    ).sort("created_at", -1).limit(max_games).to_list(max_games)

    total = 0
    for a in analyses:
        puzzles = await extract_puzzles_from_game(db, a["game_id"], user_id)
        total += len(puzzles)

    return total


# Map a cognitive-gap key (community_puzzles.issue_type) to the equivalent
# Play-with-Coach pattern_type(s) in community_training_positions, so the
# pattern-training page serves BOTH pools. Mohit 2026-07-10 — the PWC pool
# (~30k positions) was extracted but hidden from /training/pattern, which read
# community_puzzles (~4k) only.
GAP_TO_PWC_PATTERNS = {
    "piece_safety":       ["piece_safety", "hanging_piece"],
    "missed_tactic":      ["tactical", "tactical_miss", "missed_threat", "pin"],
    "tactical_oversight": ["tactical_oversight", "tactical"],
    "calculation_depth":  ["calculation_depth"],
    "king_safety":        ["king_safety"],
    # A proven mate in the PWC pool is filed under pattern_type
    # "missed_tactic" -- all 344 of them, counted on the live collection
    # 2026-10-13, 0 under any mate-ish name. This collection answers only
    # exact-match queries reliably (see the note further down), so the
    # request asks for the broad pattern_type the rows actually carry and
    # `verdict_serves_pattern` then narrows it to the proven mates. The
    # pattern_type is a candidate filter here; the proof is the gate.
    "forced_mate":        ["missed_tactic"],
    # opening_knowledge / endgame_technique / piece_activity / pawn_structure:
    # no PWC-pool equivalent — those serve from community_puzzles only.
}


async def get_pattern_training_puzzles(
    db: AsyncIOMotorDatabase,
    user_id: str,
    pattern: str,
    limit: int = 15,
    *,
    private: bool = False,
) -> Dict:
    """
    Get training puzzles for a specific cognitive gap pattern.

    Priority:
    1. User's own game positions (most impactful — they recognize the context)
    2. Community puzzles from other users with the same pattern
    Excludes puzzles the user has already solved.

    Now includes decay state and score to help prioritize training.

    Returns:
    {
        "pattern": "piece_safety",
        "pattern_label": "Piece Safety",
        "decay_state": "active",
        "decay_score": 3.2,
        "own_puzzles": [...],
        "community_puzzles": [...],
        "total_available": N,
        "unsolved_count": M,
        "solved_count": P,
    }
    """
    # Get decay score for this pattern to add context to training
    from services.pattern_decay_service import refresh_user_pattern_decay
    pattern_scores = await refresh_user_pattern_decay(db, user_id)
    decay_state = "active"
    decay_score = 0.0
    if pattern in pattern_scores:
        decay_state = pattern_scores[pattern].get("state", "active")
        decay_score = pattern_scores[pattern].get("weighted_score", 0.0)

    # Get puzzle IDs the user has already solved
    solved_cursor = db.puzzle_attempts.find(
        {"user_id": user_id, "correct": True},
        {"_id": 0, "puzzle_id": 1},
    )
    solved_ids = set()
    async for doc in solved_cursor:
        solved_ids.add(doc.get("puzzle_id", ""))

    # THE SOLVED FILTER HAS TO BE IN THE QUERY, NOT AFTER IT.
    #
    # Measured on the deploy gate's user 2026-10-04: every one of the 22 rows
    # the community fetch looked at was already solved, so the lesson got zero
    # candidates and 409'd with "No verified practice positions are available
    # yet" -- the third time that error has failed the deploy gate. There were
    # 3,228 matching positions behind those 22.
    #
    # The cause is that `.limit()` applied BEFORE the solved check. `solve_rate`
    # is 0.0 on every row in this pool, so the sort is entirely tied and the
    # window is whatever the planner returns -- it is not even the same window
    # at limit 22 as at limit 500. Fetching deeper would only move the cliff:
    # the solved set grows every time the player succeeds, so the better they
    # do, the more likely the lesson comes back empty.
    #
    # Excluding them in the query makes the limit apply to rows that can
    # actually be served. Same user, same limit: 0 available becomes 22, out of
    # 3,206. The `_id` tiebreaker is so a fully tied sort is at least
    # reproducible between calls.
    solved_object_ids = []
    for value in solved_ids:
        try:
            solved_object_ids.append(ObjectId(value))
        except Exception:
            # Coach-game ids and `position_id` strings are not ObjectIds. They
            # are excluded by their own field on the pool that uses them.
            continue

    # 1. User's own puzzles for this pattern
    own_cursor = db.community_puzzles.find(
        {
            "shared_by": user_id,
            "approved": True,
            **pattern_pool_clause(pattern),
            **verified_mongo_clause(pattern),
        },
    ).sort("created_at", -1).limit(limit)

    own_puzzles = []
    async for p in own_cursor:
        if not stored_verdict_is_structurally_current(p):
            continue
        pid = str(p["_id"])
        own_puzzles.append({
            "puzzle_id": pid,
            "fen": p["fen"],
            "best_move_san": p["best_move_san"],
            # The move the player actually played. Populated on 100% of both
            # pools (measured 2026-10-07 over 8,000 rows) and dropped by this
            # shape until now, which is why no surface could say "you played
            # Nd4 here" -- the home page's Movement 2 is built on that sentence.
            # Not an answer, so it is not in _PRIVATE_PUZZLE_FIELDS.
            "played_move": p.get("played_move"),
            "issue_type": stored_pattern_label(p),
            "difficulty": p.get("difficulty", "intermediate"),
            "move_number": p.get("move_number"),
            "user_color": p.get("user_color", "white"),
            "source": "own_game",
            "source_game_id": p.get("source_game_id"),
            "description": p.get("description", ""),
            "already_solved": pid in solved_ids,
            "solve_rate": round(p.get("solve_rate", 0), 1),
            "decay_state": decay_state,
            "decay_score": decay_score,
        })

    # 2. Community puzzles (from other users, same pattern, not already solved)
    remaining = max(0, limit - len([p for p in own_puzzles if not p["already_solved"]]))

    community_query = {
        "shared_by": {"$ne": user_id},
        "approved": True,
        **pattern_pool_clause(pattern),
        **verified_mongo_clause(pattern),
    }
    if solved_object_ids:
        community_query["_id"] = {"$nin": solved_object_ids}

    community_cursor = db.community_puzzles.find(community_query).sort(
        # Easier ones first to build confidence, then `_id` so that a pool
        # whose solve_rate is uniformly 0.0 still comes back in a repeatable
        # order rather than whatever the planner picks for this limit.
        [("solve_rate", -1), ("_id", 1)]
    ).limit(remaining + 10)

    community_puzzles = []
    async for p in community_cursor:
        if not stored_verdict_is_structurally_current(p):
            continue
        pid = str(p["_id"])
        if pid in solved_ids:
            continue
        if len(community_puzzles) >= remaining:
            break
        community_puzzles.append({
            "puzzle_id": pid,
            "fen": p["fen"],
            "best_move_san": p["best_move_san"],
            # Carried for symmetry with own_puzzles. Nothing says "you played
            # X" about someone else's game, so no surface should narrate it.
            "played_move": p.get("played_move"),
            "issue_type": stored_pattern_label(p),
            "difficulty": p.get("difficulty", "intermediate"),
            "move_number": p.get("move_number"),
            "user_color": p.get("user_color", "white"),
            "source": "community",
            "description": p.get("description", ""),
            "already_solved": False,
            "solve_rate": round(p.get("solve_rate", 0), 1),
            "decay_state": decay_state,
            "decay_score": decay_score,
        })

    # 3. Play-with-Coach pool (community_training_positions) for the same gap.
    #    This pool is ~7x bigger than community_puzzles and was NOT reaching this
    #    page. The user's OWN coach-game mistakes are the most impactful, so they
    #    lead (own_puzzles); others fill the community list. Mohit 2026-07-10.
    pwc_types = GAP_TO_PWC_PATTERNS.get(pattern, [])
    if pwc_types:
        def _pwc_int(v):
            try:
                return int(v)
            except Exception:
                return None

        def _shape_pwc(p, source):
            pid = p.get("position_id") or str(p.get("_id"))
            return {
                "puzzle_id": pid,
                "fen": p.get("fen"),
                "best_move_san": p.get("best_move_san") or "",
                # This pool spells it `user_move_san`; community_puzzles spells
                # it `played_move`. Normalised here so callers see one name.
                "played_move": p.get("user_move_san") or p.get("played_move"),
                "issue_type": pattern,
                "difficulty": p.get("difficulty", "intermediate"),
                "move_number": _pwc_int(p.get("move_number")),
                "user_color": p.get("user_color", "white"),
                "source": source,
                "source_game_id": p.get("source_game_id"),
                "description": p.get("moment_tag") or "",
                "already_solved": pid in solved_ids,
                "solve_rate": round(float(p.get("solve_rate", 0) or 0), 1),
                "decay_state": decay_state,
                "decay_score": decay_score,
            }

        # IMPORTANT: on prod this collection reliably serves only EXACT-match
        # queries — it has just the _id_ index and $in / $exists return WRONG
        # results (0) on it (Mohit 2026-07-10 — flagged for a reindex). So query
        # each pattern_type EXACTLY and do the rest of the filtering in Python.
        for t in pwc_types:
            # 3a. the user's OWN coach-game mistakes for this pattern — lead.
            #     (compound exact match {pattern_type, source_user_id} works.)
            own_pwc = db.community_training_positions.find(
                {"pattern_type": t, "source_user_id": user_id}
            ).sort("created_at", -1).limit(limit)
            async for p in own_pwc:
                # A reviewer rejecting a position is a human quality decision,
                # and grading refuses those outright. Serving one anyway means
                # the student thinks about the board, answers, and is told we
                # could not verify it -- the worst possible moment to find out.
                # The community_puzzles path already filters approved:True; this
                # pool never did.
                if p.get("approved") is False:
                    continue
                if not verdict_serves_pattern(p, pattern):
                    continue
                sh = _shape_pwc(p, "own_coach_game")
                if sh["fen"] and sh["best_move_san"]:
                    own_puzzles.append(sh)
            # 3b. other users' coach-game puzzles — fill community up to `limit`.
            if len(community_puzzles) < limit:
                # Solved rows are excluded in the query here too, for the same
                # reason as above: at depth 32 for the deploy gate's user, 29
                # of the rows looked at were already solved and only 3 got
                # through. Excluding them first leaves 189 servable in 200.
                #
                # The 2026-07-10 note above says `$in`/`$exists` return wrong
                # results on this collection. Re-measured 2026-10-04 with a
                # positive control before relying on it: `position_id` with a
                # harmless `$nin` returns 8,426 against a plain count of 8,426,
                # so `$nin` on that field is sound now. `$exists` was not
                # re-tested and is still avoided.
                comm_pwc_query = {"pattern_type": t}
                solved_strings = [s for s in solved_ids if s]
                if solved_strings:
                    comm_pwc_query["position_id"] = {"$nin": solved_strings}
                comm_pwc = db.community_training_positions.find(
                    comm_pwc_query
                ).sort([("solve_rate", -1), ("_id", 1)]).limit(limit + 20)
                async for p in comm_pwc:
                    if len(community_puzzles) >= limit:
                        break
                    if p.get("source_user_id") == user_id:
                        continue  # own — already added above
                    if p.get("approved") is False:
                        continue  # rejected by a reviewer; grading will refuse it
                    if not verdict_serves_pattern(p, pattern):
                        continue
                    sh = _shape_pwc(p, "coach_game")
                    if sh["puzzle_id"] in solved_ids or not sh["fen"] or not sh["best_move_san"]:
                        continue
                    community_puzzles.append(sh)

    # Stats
    total_own = len(own_puzzles)
    total_community = len(community_puzzles)
    unsolved_own = len([p for p in own_puzzles if not p["already_solved"]])

    # Calculate games to next state transition
    games_to_next = 999
    if decay_state == "active" and decay_score > 0:
        # How many more clean games until DECLINING (score <= 2)?
        games_to_next = max(0, int(decay_score - 2.0))
    elif decay_state == "declining" and decay_score > 0:
        # How many more clean games until FADING (score < 1)?
        games_to_next = max(0, int(decay_score - 1.0))

    from services.verified_puzzle_runtime import public_puzzle_payload
    shape = (lambda item: dict(item)) if private else public_puzzle_payload
    return {
        "pattern": pattern,
        "pattern_label": pattern.replace("_", " ").title(),
        "decay_state": decay_state,
        "decay_score": round(decay_score, 2),
        "games_to_next_state": games_to_next,
        "own_puzzles": [shape(p) for p in own_puzzles],
        "community_puzzles": [shape(p) for p in community_puzzles],
        "total_available": total_own + total_community,
        "unsolved_count": unsolved_own + total_community,
        "solved_count": len(solved_ids),
    }


def _gap_to_theme(gap: str) -> str:
    """Map cognitive gap to a broader theme category."""
    mapping = {
        "piece_safety": "tactical",
        "missed_tactic": "tactical",
        "missed_fork": "tactical",
        "missed_pin": "tactical",
        "missed_skewer": "tactical",
        "back_rank": "tactical",
        "king_safety": "defensive",
        "pawn_structure": "positional",
        "piece_activity": "positional",
        "calculation_depth": "calculation",
        "time_pressure": "time_management",
        "opening_knowledge": "opening",
        "endgame_technique": "endgame",
    }
    return mapping.get(gap, "tactical")



def _infer_cognitive_gap(fen: str, best_move: str, cp_loss: int) -> str:
    """
    Infer the cognitive gap from position characteristics when not explicitly tagged.
    Uses the position, the best move, and the centipawn loss to classify.
    """
    try:
        board = chess.Board(fen)
        move = board.parse_san(best_move)

        # Check if best move is a capture — likely piece safety issue
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured and captured.piece_type in (chess.QUEEN, chess.ROOK):
                return "piece_safety"
            if captured:
                return "missed_tactic"

        # Check if best move gives check — likely tactical miss
        board.push(move)
        if board.is_check():
            board.pop()
            return "missed_tactic"
        board.pop()

        # Check for hanging pieces in the position
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == board.turn:
                if board.is_attacked_by(not board.turn, sq):
                    if not board.is_attacked_by(board.turn, sq):
                        return "piece_safety"

        # Large cp_loss without obvious tactical features
        if cp_loss >= 300:
            return "piece_safety"
        elif cp_loss >= 150:
            return "calculation_depth"

    except Exception:
        pass

    return ""
