"""Read the reasoning engine's own account of its work.

Mohit, 2026-10-21:

    "i need a documentation from claude on the steps it took to find out why a
     move was a mistake on inaccuracy, and then tell the steps it took to get
     to those steps"

    "I would like to create a page on admin chessguru, where it will put all
     the samples thre, it used and the caption it generated and teh steps it
     took"

Two endpoints, for the two halves of that:

  /admin/reasoning-trace       one faulted move, every step, every question
                               asked, and what became of each answer
  /admin/reasoning-provenance  where each question came from, the positions
                               that produced it, and the defects it shipped

The one design rule, from docs/reasoning_trace_admin_scope.md: **the steps are
emitted by the engine, never described by this file or by the page.** A page
that holds its own copy of the procedure is correct the day it is written and
silently wrong the first time a question is added. So this route serialises
`Report.steps()` and `Report.asked` and adds nothing of its own.

Read-only on purpose. /admin/detector-review and /admin/reason-judge already
record verdicts; nothing here changes what any player sees.
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import chess
from fastapi import APIRouter, Depends, HTTPException, Query

from routes.admin import require_admin
from routes.auth import User
from services.move_reasoning import (
    REGISTRY,
    MoveUnderStudy,
    reason_about,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin"])
db = None

PROVENANCE_PATH = Path(__file__).resolve().parents[1] / "data" / \
    "question_provenance.json"

# Only cards the engine actually faulted. Same bar the scans use, so a number
# read here is comparable with a number measured there.
MIN_CP_LOSS = 100

# How many analysed games to reach into for a random pick. The corpus is ~19k
# documents and pulling all of them to choose one is a connection closed
# halfway, which is how the first full-corpus scan died.
RANDOM_WINDOW = 400


def set_db(database) -> None:
    global db
    db = database


def _require_db() -> None:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")


def _arrow(fen: str, san: str, color: str) -> Optional[List[str]]:
    """One arrow, built by pushing the move -- never by parsing a sentence.

    `[from, to, colour]`, which is the shape LichessBoard takes. Checked
    against a real caller (AdminDetectorReview) rather than assumed: the first
    version of this returned objects and would have drawn nothing, silently,
    which is how a correct sentence shipped with an empty arrow list once
    before.
    """
    try:
        board = chess.Board(fen)
        mv = board.parse_san(str(san))
    except (ValueError, AssertionError, TypeError, KeyError):
        return None
    return [chess.square_name(mv.from_square),
            chess.square_name(mv.to_square), color]


def _ask_the_engine(fen: str, played: str) -> Dict[str, Any]:
    """Best move, both lines and the cp loss for a position nobody analysed.

    Only for the pasted-position mode: a card from the corpus already carries
    all of this. Depth matches what the stored analysis uses, so a number read
    here is comparable with a number on a card.

    Returns empty lines and says so on failure, rather than raising -- a trace
    without engine lines is still worth reading, and the caller marks it.
    """
    out: Dict[str, Any] = {"best_san": None, "pv_played": [], "pv_best": [],
                           "cp_loss": 0, "how": "not asked"}
    try:
        from stockfish_service import DEFAULT_DEPTH, StockfishEngine
    except Exception:
        out["how"] = "stockfish unavailable"
        return out
    board = chess.Board(fen)
    try:
        with StockfishEngine() as eng:
            best_mv, best_cp, _ = eng.get_best_move(board, DEFAULT_DEPTH)
            out["best_san"] = board.san(best_mv)
            after_best = board.copy()
            after_best.push(best_mv)
            out["pv_best"] = eng.get_principal_variation(
                after_best, DEFAULT_DEPTH, pv_length=8)

            after_played = board.copy()
            after_played.push(board.parse_san(played))
            out["pv_played"] = eng.get_principal_variation(
                after_played, DEFAULT_DEPTH, pv_length=8)
            played_cp, _ = eng.evaluate_position(after_played, DEFAULT_DEPTH)
            # evaluate_position is from the side to move, which after our move
            # is THEIRS. Flip it so both numbers are from the mover's view.
            out["cp_loss"] = max(0, int(best_cp) - int(-played_cp))
            out["how"] = f"asked at depth {DEFAULT_DEPTH}"
    except Exception:
        logger.exception("engine probe failed for a pasted position")
        out["how"] = "the engine could not be reached"
    return out


def _trace_payload(fen: str, played: str, best: Optional[str],
                   pv_played: List[str], pv_best: List[str],
                   cp_loss: int, mover_is_user: bool,
                   where: Dict[str, Any]) -> Dict[str, Any]:
    """Everything the page needs for one move, from one reason_about call."""
    move = MoveUnderStudy(
        fen_before=fen, played_san=played, best_san=best or None,
        pv_played=list(pv_played or []), pv_best=list(pv_best or []),
        cp_loss=int(cp_loss), mover_is_user=bool(mover_is_user))
    report = reason_about(move)

    primary = report.primary
    board = chess.Board(fen)

    return {
        "where": where,
        "position": {
            "fen": fen,
            "side_to_move": "white" if board.turn == chess.WHITE else "black",
            "played_san": played,
            "best_san": best,
            "cp_loss": int(cp_loss),
            "mover_is_user": bool(mover_is_user),
            "pv_played": list(pv_played or [])[:8],
            "pv_best": list(pv_best or [])[:8],
            "arrows": [a for a in (_arrow(fen, played, "red"),
                                   _arrow(fen, best or "", "green")) if a],
        },
        # The engine's own record. Serialised, not re-derived.
        "steps": report.steps(),
        "asked": [
            {"concept": a.concept, "tier": a.tier, "answered": a.answered,
             "verdict": a.verdict, "subject": a.subject, "reason": a.reason,
             "facts": a.facts}
            for a in report.asked
        ],
        "outcome": {
            "resolved": report.resolved,
            "primary_concept": primary.concept if primary else None,
            "primary_tier": primary.tier if primary else None,
            "confidence": primary.confidence if primary else None,
            "differential": primary.differential if primary else None,
            "stability": report.stability,
            "schema_version": report.schema_version,
        },
        # Said plainly rather than hidden: the framework feeds no caption
        # surface yet, so there is no player-facing sentence to show. Printing
        # a mock one here would be the exact failure this page exists to
        # expose.
        "caption": {
            "available": False,
            "why": ("The reasoning framework is not wired to a caption "
                    "surface yet, so no player sees a sentence from it. The "
                    "finding below is what a caption would be built from."),
            "slots": dict(primary.facts) if primary else {},
        },
    }


def _faulted_moves(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every card in one analysis the engine faulted, both sides.

    Opponent moves live in their own array -- move_evaluations holds zero of
    them -- so a reader of only the first array sees half the game.
    """
    sa = doc.get("stockfish_analysis") or {}
    out: List[Dict[str, Any]] = []
    for key, is_user in (("move_evaluations", True),
                         ("opponent_move_evaluations", False)):
        for idx, m in enumerate(sa.get(key) or []):
            if (m.get("cp_loss") or 0) < MIN_CP_LOSS:
                continue
            if not m.get("fen_before") or not m.get("pv_after_played"):
                continue
            out.append({"m": m, "is_user": is_user, "array": key, "idx": idx})
    return out


@router.get("/admin/reasoning-trace")
async def reasoning_trace(
    game_id: Optional[str] = Query(None),
    ply: Optional[int] = Query(None),
    fen: Optional[str] = Query(None),
    played: Optional[str] = Query(None),
    best: Optional[str] = Query(None),
    cp_loss: int = Query(0),
    user: User = Depends(require_admin),
):
    """One faulted move with the engine's full account of it.

    Three ways in: a specific game (plus an optional ply), a pasted position,
    or nothing at all for a random faulted move.
    """
    # A pasted position: no database needed, and the most useful mode when
    # Mohit has a screenshot and wants to know what the engine thinks.
    if fen and played:
        try:
            chess.Board(fen).parse_san(played)
        except (ValueError, AssertionError, TypeError, KeyError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"{played} is not legal in that position") from exc
        # Ask the engine for the lines rather than handing the framework empty
        # ones. Four of six questions need a line, so an empty pv makes every
        # one of them answer "no answer" -- six silent rows that look like a
        # broken engine and are really a missing input. An empty move history
        # has already produced one false bug report in this repo; this is the
        # same trap with a different field.
        got = _ask_the_engine(fen, played)
        return _trace_payload(
            fen, played, best or got["best_san"],
            got["pv_played"], got["pv_best"],
            cp_loss or got["cp_loss"], True,
            {"source": "pasted position", "engine": got["how"]})

    _require_db()
    query: Dict[str, Any] = {"game_id": game_id} if game_id else {}
    projection = {"stockfish_analysis": 1, "game_id": 1, "_id": 0}

    if game_id:
        doc = await db.game_analyses.find_one(query, projection)
        if not doc:
            raise HTTPException(status_code=404,
                                detail=f"no analysis for game {game_id}")
        cards = _faulted_moves(doc)
        if not cards:
            raise HTTPException(
                status_code=404,
                detail=f"game {game_id} has no move the engine faulted")
        card = next((c for c in cards if c["idx"] == ply), cards[0]) \
            if ply is not None else cards[0]
        docs_game_id = doc.get("game_id")
    else:
        # Random: skip into the corpus rather than reading it all.
        total = await db.game_analyses.count_documents({})
        if not total:
            raise HTTPException(status_code=404, detail="no analysed games")
        start = random.randrange(max(1, total - RANDOM_WINDOW + 1))
        batch = await db.game_analyses.find({}, projection) \
                        .skip(start).limit(RANDOM_WINDOW).to_list(RANDOM_WINDOW)
        pool = [(d, c) for d in batch for c in _faulted_moves(d)]
        if not pool:
            raise HTTPException(status_code=404,
                                detail="no faulted move in that window")
        doc, card = random.choice(pool)
        docs_game_id = doc.get("game_id")

    m = card["m"]
    return _trace_payload(
        fen=m["fen_before"],
        played=str(m.get("move") or ""),
        best=str(m.get("best_move") or "") or None,
        pv_played=list(m.get("pv_after_played") or []),
        pv_best=list(m.get("pv_after_best") or []),
        cp_loss=int(m.get("cp_loss") or 0),
        mover_is_user=bool(card["is_user"]),
        where={"source": "corpus", "game_id": docs_game_id,
               "array": card["array"], "ply": card["idx"],
               "side": "the player" if card["is_user"] else "the opponent"},
    )


@router.get("/admin/reasoning-provenance")
async def reasoning_provenance(user: User = Depends(require_admin)):
    """Where each question came from, in registry order.

    Registry order, not file order, so the page shows them the way the engine
    asks them -- CAUSE before EVIDENCE before SYMPTOM.
    """
    try:
        raw = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.exception("provenance file unreadable")
        raise HTTPException(status_code=500,
                            detail="provenance file unreadable") from exc

    out: List[Dict[str, Any]] = []
    for q in REGISTRY:
        entry = raw.get(q.concept)
        if entry is None:
            # Visible rather than skipped: a question with no recorded origin
            # is the thing a test here is meant to prevent, so say so on the
            # page instead of quietly showing one row fewer.
            out.append({"concept": q.concept, "tier": q.tier,
                        "missing": True,
                        "title": "(no provenance recorded)"})
            continue
        row = dict(entry)
        row["concept"] = q.concept
        row["tier"] = q.tier
        row["names_material"] = q.claim_cp is not None
        row["has_own_challenge"] = q.challenge is not None
        for s in list(row.get("discovery_samples") or []) + \
                list(row.get("defect_samples") or []):
            if s.get("fen") and s.get("played"):
                s["arrows"] = [a for a in (
                    _arrow(s["fen"], s["played"], "red"),
                    _arrow(s["fen"], s.get("best") or "", "green")) if a]
        out.append(row)

    return {"questions": out,
            "step_count": 8,
            "doc": "docs/how_claude_finds_the_mistake.md"}
