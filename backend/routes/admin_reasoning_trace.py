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

# How many analysed games to sample for a random pick.
#
# This was a 400-document skip/limit window and it broke the page the moment
# decryption_v5_data joined the projection: 400 docs went from 9.4 MB to
# 87 MB and the request took 34 seconds, so nginx timed out and handed the
# browser an HTML error page, which arrived as
# "Unexpected token '<', "<html> <h"... is not valid JSON".
#
# $sample picks randomly inside the server and ships only what it picks. A
# handful rather than one because a sampled game need not contain a move the
# engine faulted, and asking again is cheaper than widening the net.
RANDOM_SAMPLE = 8


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


def _shipped_card(analysis: Optional[Dict[str, Any]],
                  fen: str, played: str) -> Dict[str, Any]:
    """The card the PLAYER actually sees, read from the stored V5 render.

    This exists because of the first card Mohit opened on this page. It read
    `returns_home` -- a SYMPTOM about a piece going back -- on a move whose
    whole story was a free pawn on g7, and he reasonably concluded the product
    was broken. It is not. The shipped caption for that exact card says:

        "Opponent's Qg3 is a mistake -- they had Qxg7, grabbing your pawn on  # allow-noncentral-caption
         g7 for free. Play O-O -- it tucks your king away from the middle."

    The page was showing a parallel engine that reaches no player, next to a
    note saying it reaches no player, and that note was nowhere near enough.
    So the shipped caption leads now and the framework trace is explicitly
    secondary. The scope doc asked this exact question and V1 answered it
    wrongly; one real card settled it in minutes.

    Matched on fen_before, which identifies a ply uniquely, with move_san as
    the tie-break.
    """
    out: Dict[str, Any] = {"found": False, "why": "", "caption": None}
    cards = (analysis or {}).get("decryption_v5_data") or []
    if not isinstance(cards, list) or not cards:
        out["why"] = ("This game has no stored V5 render, so there is no "
                      "shipped card to compare against.")
        return out
    hit = next((c for c in cards if c.get("fen_before") == fen), None) \
        or next((c for c in cards if str(c.get("move_san") or "") == played),
                None)
    if hit is None:
        out["why"] = ("The game is rendered but this ply has no card -- the "
                      "V5 pass does not card every move.")
        return out
    expl = hit.get("caption_explanation") or {}
    ver = hit.get("caption_verification") or {}
    out.update({
        "found": True,
        "caption": hit.get("caption"),
        "tier": hit.get("caption_tier"),
        "provenance": list(expl.get("provenance") or []),
        "confidence": expl.get("confidence"),
        "verified": ver.get("verdict"),
        "rollout_mode": expl.get("rollout_mode"),
        "primary_reason": hit.get("caption_facts_primary_reason"),
        "concept_sentence": hit.get("concept_sentence"),
    })
    return out


def _trace_payload(fen: str, played: str, best: Optional[str],
                   pv_played: List[str], pv_best: List[str],
                   cp_loss: int, mover_is_user: bool,
                   where: Dict[str, Any],
                   analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        # What the player actually sees. FIRST, because the alternative misled
        # the first person to open this page.
        "shipped": _shipped_card(analysis, fen, played),
        # And what the experimental framework would build from, kept clearly
        # apart. It reaches no player; a reader must never be able to mistake
        # one for the other.
        "framework": {
            "reaches_a_player": False,
            # Standing down is a RESULT, not an absence of one. A reader must
            # be able to tell "a detector owns this card" from "I looked and
            # found nothing".
            "declined": report.declined,
            "why": ("The reasoning framework feeds no caption surface. "
                    "Everything in the trace below is an experiment running "
                    "beside the shipped card above, not instead of it."),
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
    # decryption_v5_data carries the SHIPPED caption, which is the thing this
    # page must lead with.
    projection = {"stockfish_analysis": 1, "game_id": 1, "_id": 0,
                  "decryption_v5_data": 1}

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
        # Random: let the server pick, and ship only what it picked.
        pool: List[Any] = []
        for _ in range(3):           # a sampled game may carry no faulted move
            batch = await db.game_analyses.aggregate([
                {"$sample": {"size": RANDOM_SAMPLE}},
                {"$project": projection},
            ]).to_list(RANDOM_SAMPLE)
            pool = [(d, c) for d in batch for c in _faulted_moves(d)]
            if pool:
                break
        if not pool:
            raise HTTPException(
                status_code=404,
                detail="sampled games held no move the engine faulted")
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
        analysis=doc,
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
