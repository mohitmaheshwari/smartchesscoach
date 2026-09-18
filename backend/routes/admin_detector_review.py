"""Read what a detector would actually say, and rule on it.

Every detector here lands in shadow by default — `_UNKNOWN` grades an
unregistered id SHADOW with "No reviewed promotion packet; unknown IDs fail
closed". That default is right for a live product and wrong for this one.
ChessGuru is not launched. A wrong claim costs one review cycle; silence costs
the review cycle itself, and 47 of 48 registered detectors have been mute
long enough that nobody remembers what they would say.

So this serves the claims. One at a time, rendered exactly as a player would
read them, with the position and the detector's own evidence beside them. A
verdict is true / false / unsure, and it is Mohit's, not a model's.

Two things it deliberately is NOT:

- not a promotion. Verdicts accumulate into the precision figure a promotion
  packet needs, but `detector_quality` remains the only authority on what may
  reach a player, and nothing here writes to it.
- not a sample of the detector's own choosing. Fires are drawn in corpus
  order and skipped once ruled, so the easy ones cannot float to the top.

Follows the geometry-gaps queue (`/admin/geometry-gaps/next` + POST +
`/results`) rather than inventing a fourth review shape.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from routes.admin import require_admin
from routes.auth import User

router = APIRouter(tags=["Admin"])
db = None

VERDICTS = {"true", "false", "unsure"}
COLLECTION = "detector_claim_rulings"

# How many analyses to walk before giving up on finding an unjudged fire. The
# detectors here are sparse by design -- allowed_mate fires on well under 1%
# of moves -- so a small scan window returns nothing and looks broken.
SCAN_LIMIT = 900


def set_db(database):
    global db
    db = database


# ─── The claim producers ────────────────────────────────────────────────
#
# One per detector. Each takes a single stored move (plus the game's colour
# and the analysis, for the two detectors that need wider context) and returns
# either None or (claim_sentence, evidence_dict).
#
# They are deliberately thin adapters over the real detectors rather than
# reimplementations. A review that judged a copy of a detector would certify
# the copy, and the grade would be attached to code no player ever runs.


def _orientation_and_arrow(fen, san):
    """What the reviewer needs to SEE, worked out once, on the server.

    The card was unreadable without these: no indication of whose move it is,
    and no indication of where the move being claimed actually goes. Mohit,
    looking at the first build: "this is not very clear to understand the
    purpose of this page."

    Returns (side_to_move, [from_sq, to_sq]) with the move in UCI squares, or
    (side, None) when the move cannot be parsed in this position.
    """
    import chess

    try:
        board = chess.Board(str(fen or ""))
    except (ValueError, AssertionError):
        return ("white", None)
    side = "white" if board.turn == chess.WHITE else "black"
    if not san:
        return (side, None)
    try:
        move = board.parse_san(str(san))
    except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError,
            chess.AmbiguousMoveError):
        return (side, None)
    return (side, [chess.square_name(move.from_square),
                   chess.square_name(move.to_square)])


def _produce_allowed_mate(move, colour, analysis):
    from services.allowed_mate_detector import detect_allowed_mate, render_claim

    evidence = detect_allowed_mate(move, colour)
    if not evidence:
        return None
    fen = evidence.get("fen_before")
    side, arrow = _orientation_and_arrow(fen, evidence.get("played_san"))
    evidence = dict(evidence)
    evidence.update({"review_fen": fen, "side_to_move": side, "arrow": arrow,
                     "arrow_is": "the move played"})
    return (render_claim(evidence), evidence)


def _produce_simple_hang(move, colour, analysis):
    """`played_hangs_detector` -- 96.9% documented on 260 reviewed fires.

    The closest thing we have to a promotable detector, and the one whose
    review is most worth Mohit's time.
    """
    import chess

    from services.played_hangs_detector import clause_for, detect_played_hangs

    fen = move.get("fen_before")
    uci = move.get("move_uci")
    if not fen or not uci:
        return None
    try:
        board = chess.Board(fen)
        played = chess.Move.from_uci(uci)
        if played not in board.legal_moves:
            return None
    except (ValueError, AssertionError):
        return None
    hang = detect_played_hangs(board, played, move.get("cp_loss"))
    if not hang:
        return None
    return (
        f"After {move.get('move')}, {clause_for(hang)}.",
        {"fen_before": fen, "fen_after": move.get("fen_after"),
         # The claim is "after X your piece hangs", so show the position it
         # hangs in.
         "review_fen": move.get("fen_after") or fen,
         "played_san": move.get("move"), "move_number": move.get("move_number"),
         "cp_loss": move.get("cp_loss"), "hung_piece": hang.get("piece"),
         "hung_square": hang.get("square"),
         "side_to_move": "white" if board.turn == chess.WHITE else "black",
         "highlight": [hang.get("square")],
         "highlight_is": "the piece said to be hanging",
         "defender_moved_away": not hang.get("moved_piece")},
    )


def _missed_motif(builder, label):
    """Shared shape for the two motif proofs.

    Both answer the same question -- did the move the player MISSED create
    this motif -- so the claim is about the best move, not the played one.

    A note on the wording, because the caption guard is right to flag it:
    `fork_puzzle_proof` and `discovered_attack_puzzle_proof` have no claim
    renderer at all. They have never spoken, so there is no player-facing
    sentence to review against, and the threshold lock's "evidence must match
    the player-facing claim" cannot be satisfied yet by anyone.

    So a ruling here certifies the DETECTION, not the prose -- is it true that
    the best move forks? The wording review happens when these are wired into
    `build_move_teaching_decision`, which is where every player-facing caption
    belongs and where the guard will enforce it. The UI says this in as many
    words so the reviewer knows which question they are answering.
    """

    def produce(move, colour, analysis):
        import chess

        fen = move.get("fen_before")
        played, best = move.get("move"), move.get("best_move")
        if not fen or not played or not best:
            return None
        try:
            board = chess.Board(fen)
        except (ValueError, AssertionError):
            return None
        bundle = builder(board, played, best, move.get("pv_after_best") or [],
                         move.get("cp_loss"))
        if not bundle:
            return None
        side, arrow = _orientation_and_arrow(fen, best)
        return (
            # Provisional review wording only, never served to a player --
            # see the docstring above.
            f"You played {played}. {best} was there instead, and it wins "  # allow-noncentral-caption
            f"material with a {label}.",
            {"fen_before": fen, "fen_after": move.get("fen_after"),
             # The claim is about the move that was AVAILABLE, so the reviewer
             # needs the position it was available in. Showing fen_after would
             # ask them to judge a fork on a board where it no longer exists.
             "review_fen": fen,
             "played_san": played, "best_move": best,
             "move_number": move.get("move_number"),
             "cp_loss": move.get("cp_loss"),
             "pv_after_best": list(move.get("pv_after_best") or [])[:6],
             "side_to_move": side,
             "arrow": arrow,
             "arrow_is": f"the {label} that was available",
             "quality_id": getattr(bundle, "quality_id", None),
             "detector_facts": [
                 dict(f) for f in getattr(
                     getattr(bundle, "detector", None), "facts", ()) or ()][:4]},
        )

    return produce


def _produce_left_book(move, colour, analysis):
    """Needs the analysis-level opening deviation, not just the move."""
    from services.cognitive_gap_subtypes import _classify_left_book

    context = {"opening_deviation": analysis.get("opening_deviation") or {}}
    subtype, severity = _classify_left_book(move, context)
    if not subtype:
        return None
    detail = (context["opening_deviation"] or {}).get("deviation") or {}
    side, arrow = _orientation_and_arrow(
        move.get("fen_before"), detail.get("expected_san"))
    return (
        # Provisional review wording only, never served to a player -- see
        # _missed_motif's docstring.
        f"You played {move.get('move')} here and left the book. "  # allow-noncentral-caption
        f"{detail.get('expected_san')} is the move, and it is also what the "
        f"engine plays.",
        {"fen_before": move.get("fen_before"), "fen_after": move.get("fen_after"),
         "review_fen": move.get("fen_before"),
         "played_san": move.get("move"), "book_move": detail.get("expected_san"),
         "best_move": move.get("best_move"),
         "move_number": move.get("move_number"),
         "cp_loss": move.get("cp_loss"), "severity": severity,
         "side_to_move": side, "arrow": arrow,
         "arrow_is": "the book move",
         "opening": detail.get("opening_name")},
    )


def _producers():
    from services.discovered_attack_puzzle_proof import (
        build_discovered_attack_proof,
    )
    from services.fork_puzzle_proof import build_fork_proof

    return {
        "allowed_mate": _produce_allowed_mate,
        "simple_hang": _produce_simple_hang,
        "left_book": _produce_left_book,
        "fork": _missed_motif(build_fork_proof, "fork"),
        "discovered_attack": _missed_motif(
            build_discovered_attack_proof, "discovered attack"),
    }


async def _fires_for(detector: str, skip_fens: set, limit: int) -> List[Dict[str, Any]]:
    """Walk real games and render what this detector would say."""
    producers = _producers()
    produce = producers.get(detector)
    if produce is None:
        raise HTTPException(
            status_code=400,
            detail=f"unknown detector: {detector}. "
                   f"known: {sorted(producers)}")

    found: List[Dict[str, Any]] = []
    scanned = 0
    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations.0": {"$exists": True}},
        {"_id": 0, "game_id": 1, "user_id": 1, "opening_deviation": 1,
         "stockfish_analysis.move_evaluations": 1},
    )
    async for analysis in cursor:
        scanned += 1
        if scanned > SCAN_LIMIT or len(found) >= limit:
            break
        game = await db.games.find_one(
            {"game_id": analysis.get("game_id")},
            {"_id": 0, "user_color": 1, "white": 1, "black": 1, "platform": 1,
             "result": 1, "played_at": 1, "date": 1})
        colour = (game or {}).get("user_color") or "white"
        # Mohit chose full game context for the reviewing coach (2026-09-18):
        # usernames, platform and result travel with every claim. No email --
        # the coach judges the claim, and the account holder is never the
        # question being asked.
        context = {
            "white": (game or {}).get("white"),
            "black": (game or {}).get("black"),
            "platform": (game or {}).get("platform"),
            "result": (game or {}).get("result"),
            "played_at": str((game or {}).get("played_at")
                             or (game or {}).get("date") or "") or None,
            "user_color": colour,
        }
        for move in (analysis.get("stockfish_analysis") or {}).get(
                "move_evaluations") or []:
            if move.get("is_opponent_move"):
                continue
            try:
                produced = produce(move, colour, analysis)
            except Exception:  # noqa: BLE001
                # One malformed stored move must not empty the whole queue.
                continue
            if not produced:
                continue
            claim, evidence = produced
            key = f"{detector}:{analysis.get('game_id')}:{evidence.get('move_number')}"
            if key in skip_fens:
                continue
            found.append({
                "claim_key": key,
                "detector": detector,
                "game_id": analysis.get("game_id"),
                "claim": claim,
                "evidence": evidence,
                "game": context,
            })
            if len(found) >= limit:
                break
    return found


@router.get("/admin/detector-review/next")
async def next_claim(
    detector: str = Query(default="allowed_mate"),
    user: User = Depends(require_admin),
):
    """One unjudged claim, or 404 when the queue is clear."""
    ruled = set(await db[COLLECTION].distinct(
        "claim_key", {"detector": detector}))
    found = await _fires_for(detector, ruled, limit=1)
    if not found:
        raise HTTPException(
            status_code=404,
            detail="No unjudged claims found in the scan window")
    return found[0]


@router.get("/admin/detector-review/batch")
async def batch_claims(
    detector: str = Query(default="allowed_mate"),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(require_admin),
):
    """Several at once — reading fifty claims in ten minutes is the point."""
    ruled = set(await db[COLLECTION].distinct(
        "claim_key", {"detector": detector}))
    return {"detector": detector, "claims": await _fires_for(detector, ruled, limit)}


@router.post("/admin/detector-review")
async def rule_claim(
    payload: Dict = Body(...),
    user: User = Depends(require_admin),
):
    """Record a verdict. It does not promote anything; see the module docstring."""
    claim_key = str(payload.get("claim_key") or "").strip()
    detector = str(payload.get("detector") or "").strip()
    verdict = str(payload.get("verdict") or "").strip().lower()
    if not claim_key or not detector:
        raise HTTPException(status_code=400, detail="claim_key and detector required")
    if verdict not in VERDICTS:
        raise HTTPException(
            status_code=400, detail=f"verdict must be one of {sorted(VERDICTS)}")

    await db[COLLECTION].update_one(
        {"claim_key": claim_key, "detector": detector},
        {"$set": {
            "verdict": verdict,
            "note": str(payload.get("note") or "")[:500],
            "claim": str(payload.get("claim") or "")[:500],
            "ruled_by": user.email,
            # The login is shared with a reviewing coach by Mohit's choice, so
            # `ruled_by` alone cannot tell two reviewers apart. This is not
            # access control -- it is so the promotion packet can say who
            # judged what, and so one reviewer's calls can be re-examined
            # without discarding the other's.
            "reviewer_name": str(payload.get("reviewer_name") or "").strip()[:80]
                             or None,
            "ruled_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"recorded": True, "claim_key": claim_key, "verdict": verdict}


@router.get("/admin/detector-review/results")
async def review_results(user: User = Depends(require_admin)):
    """Tallies, plus every claim ruled false — those are the bug reports."""
    rows = await db[COLLECTION].find({}, {"_id": 0}).to_list(length=None)
    by_detector: Dict[str, Counter] = {}
    for row in rows:
        by_detector.setdefault(row.get("detector"), Counter())[
            row.get("verdict")] += 1

    by_reviewer: Counter = Counter()
    for row in rows:
        by_reviewer[row.get("reviewer_name") or row.get("ruled_by") or "?"] += 1

    summary = {}
    for detector, counts in by_detector.items():
        judged = counts["true"] + counts["false"]
        summary[detector] = {
            "true": counts["true"],
            "false": counts["false"],
            "unsure": counts["unsure"],
            # The number a promotion packet needs. Unsure is excluded from the
            # denominator on purpose: it is a reviewer abstention, not evidence
            # either way.
            "precision": round(100 * counts["true"] / judged, 1) if judged else None,
            "judged": judged,
            # docs/detector_quality_threshold_lock_2026_08_27.md
            "caption_bar": {"fires": 50, "precision": 95},
            "plan_bar": {"fires": 200, "precision": 95, "recall": 60},
        }
    return {
        "summary": summary,
        "by_reviewer": dict(by_reviewer),
        "wrong_claims": [
            {k: r.get(k) for k in ("detector", "claim", "note", "claim_key")}
            for r in rows if r.get("verdict") == "false"
        ],
        "total_ruled": len(rows),
    }
