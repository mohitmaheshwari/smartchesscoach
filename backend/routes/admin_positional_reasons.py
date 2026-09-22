"""Admin workflow for reviewed positional teaching reasons.

Reasons saved here are candidate evidence only. They cannot affect captions or
mastery until a canonical detector and verifier are separately authorized.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from routes.admin import require_admin, require_geometry_reviewer
from routes.auth import User
from services.positional_reason_learning import (
    DISPOSITION_LABELS,
    PositionalReasonValidationError,
    canonical_concepts,
    normalize_submission,
    structural_features,
    structural_signature,
)


router = APIRouter(tags=["Admin"])
db = None
_INDEXES_ENSURED = False


def set_db(database) -> None:
    global db
    db = database


def _require_db() -> None:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")


async def _ensure_indexes() -> None:
    global _INDEXES_ENSURED
    if _INDEXES_ENSURED:
        return
    _require_db()
    await db.positional_reason_queue.create_index(
        [("status", 1), ("priority", 1), ("cp_loss", -1)],
        name="positional_reason_queue_review_order",
    )
    await db.positional_reason_submissions.create_index(
        "position_fingerprint",
        unique=True,
        sparse=True,
        name="positional_reason_submission_position",
    )
    await db.positional_reason_submissions.create_index(
        [("canonical_concept_id", 1), ("structural_signature", 1)],
        name="positional_reason_submission_grouping",
    )
    _INDEXES_ENSURED = True


async def _progress() -> Dict[str, Any]:
    rows = await db.positional_reason_queue.find(
        {}, {"_id": 0, "status": 1, "disposition": 1}
    ).to_list(length=None)
    dispositions = Counter(
        row.get("disposition")
        for row in rows
        if row.get("disposition") in DISPOSITION_LABELS
    )
    pending = sum(row.get("status", "pending") == "pending" for row in rows)
    return {
        "resolved": len(rows) - pending,
        "pending": pending,
        "total": len(rows),
        "by_disposition": dict(dispositions),
    }


@router.get("/admin/positional-reasons/next")
async def next_position(
    skip_resolved: bool = True,
    user: User = Depends(require_admin),
):
    _require_db()
    await _ensure_indexes()
    query: Dict[str, Any] = {"status": "pending"} if skip_resolved else {}
    row = await db.positional_reason_queue.find_one(
        query,
        {"_id": 0},
        sort=[("priority", 1), ("cp_loss", -1)],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Every queued position is resolved")
    try:
        row["structural_features"] = structural_features(
            row["fen"], row["played_uci"], row["best_uci"]
        )
        row["structural_signature"] = structural_signature(
            row["fen"], row["played_uci"], row["best_uci"]
        )
    except PositionalReasonValidationError as exc:
        row["structural_error"] = str(exc)
    row["progress"] = await _progress()
    return row


@router.get("/admin/positional-reasons/concepts")
async def list_concepts(user: User = Depends(require_admin)):
    concepts = sorted(canonical_concepts().values(), key=lambda item: item["name"])
    return {"concepts": concepts}


@router.get("/admin/positional-reasons/similar")
async def similar_reasons(
    structural_signature_value: str = Query("", alias="structural_signature"),
    canonical_concept_id: str = "",
    concept_label: str = "",
    exclude_fen: str = "",
    limit: int = 8,
    user: User = Depends(require_admin),
):
    _require_db()
    clauses = []
    if canonical_concept_id:
        clauses.append({"canonical_concept_id": canonical_concept_id})
    if concept_label:
        clauses.append({"concept_label": concept_label})
    if structural_signature_value:
        clauses.append({"structural_signature": structural_signature_value})
    if not clauses:
        return {"count": 0, "submissions": []}
    query: Dict[str, Any] = {"$or": clauses}
    if exclude_fen:
        query["fen"] = {"$ne": " ".join(exclude_fen.split()[:4])}
    rows = await db.positional_reason_submissions.find(
        query,
        {
            "_id": 0,
            "fen": 1,
            "played_san": 1,
            "best_san": 1,
            "concept_label": 1,
            "canonical_concept_id": 1,
            "reason": 1,
            "disposition": 1,
            "voice_warnings": 1,
            "promotion": 1,
        },
    ).sort("updated_at", -1).to_list(min(max(limit, 1), 20))
    return {"count": len(rows), "submissions": rows}


@router.post("/admin/positional-reasons")
async def submit_reason(
    payload: Dict[str, Any] = Body(...),
    user: User = Depends(require_admin),
):
    _require_db()
    await _ensure_indexes()
    fen = str(payload.get("fen") or "").strip()
    if not fen:
        raise HTTPException(status_code=400, detail="fen is required")
    row = await db.positional_reason_queue.find_one({"fen": fen}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Queued position not found")
    try:
        submission = normalize_submission(
            payload,
            row,
            submitted_by=user.user_id,
        )
    except PositionalReasonValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    created_at = submission.pop("created_at")
    await db.positional_reason_submissions.update_one(
        {"position_fingerprint": submission["position_fingerprint"]},
        {
            "$set": submission,
            "$setOnInsert": {"created_at": created_at},
        },
        upsert=True,
    )
    now = datetime.now(timezone.utc).isoformat()
    await db.positional_reason_queue.update_one(
        {"fen": fen},
        {
            "$set": {
                "status": "resolved",
                "disposition": submission["disposition"],
                "resolved_at": now,
                "resolved_by": user.user_id,
                "position_fingerprint": submission["position_fingerprint"],
                "structural_signature": submission["structural_signature"],
            }
        },
    )
    return {
        "ok": True,
        "saved": {
            "position_fingerprint": submission["position_fingerprint"],
            "disposition": submission["disposition"],
            "voice_warnings": submission["voice_warnings"],
            "promotion": submission["promotion"],
        },
        "progress": await _progress(),
    }


@router.post("/admin/positional-reasons/skip")
async def skip_position(
    payload: Dict[str, Any] = Body(...),
    user: User = Depends(require_admin),
):
    forwarded = dict(payload)
    forwarded["disposition"] = "insufficient_evidence"
    return await submit_reason(forwarded, user)


@router.get("/admin/positional-reasons/submissions")
async def list_submissions(
    limit: int = 100,
    disposition: Optional[str] = None,
    user: User = Depends(require_admin),
):
    _require_db()
    query = {"disposition": disposition} if disposition else {}
    rows = await db.positional_reason_submissions.find(
        query, {"_id": 0}
    ).sort("updated_at", -1).to_list(min(max(limit, 1), 500))
    labels = Counter(
        row.get("canonical_concept_id") or row.get("concept_label")
        for row in rows
        if row.get("canonical_concept_id") or row.get("concept_label")
    )
    return {
        "count": len(rows),
        "by_concept": labels.most_common(),
        "submissions": rows,
        "progress": await _progress(),
    }


# ---------------------------------------------------------------------------
# Blind judging of model explanations.
#
# The first comparison had Opus grading Fable, which Mohit rightly called out.
# The mechanical claim checks were run against a real board so those are safe,
# but "is this reason true and useful" was one model judging another. This
# adds a human judge, and shows the two answers anonymously so a prior about
# which model is which cannot decide the vote. The side each model occupies is
# fixed by hashing the position, so reloading never reveals it.
# ---------------------------------------------------------------------------


@router.get("/admin/reason-judge/next")
async def next_pair(user: User = Depends(require_admin)):
    """A position with two anonymous explanations, or 404 when done."""
    judged = await db.reason_judgements.distinct("fen")
    row = await db.model_reason_answers.find_one(
        {"fen": {"$nin": judged}}, {"_id": 0}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Every position has been judged")
    pair = await db.model_reason_answers.find(
        {"fen": row["fen"]}, {"_id": 0}
    ).to_list(2)
    if len(pair) != 2:
        raise HTTPException(status_code=409, detail="Position is missing an answer")

    def anon(entry):
        # model / model_id deliberately omitted — that is the whole point
        return {
            "slot": entry["slot"],
            "reason": entry.get("reason"),
            "concept_label": entry.get("concept_label"),
            "is_positional": entry.get("is_positional"),
            "checkable_claims": entry.get("checkable_claims") or [],
        }

    first = pair[0]
    total = len(await db.model_reason_answers.distinct("fen"))
    return {
        "fen": first["fen"],
        "played_san": first.get("played_san"),
        "best_san": first.get("best_san"),
        "cp_loss": first.get("cp_loss"),
        "men": first.get("men"),
        "bucket": first.get("bucket"),
        "side_to_move": first.get("side_to_move"),
        "answers": sorted((anon(p) for p in pair), key=lambda a: a["slot"]),
        "progress": {"judged": len(judged), "total": total},
    }


@router.post("/admin/reason-judge")
async def judge_pair(
    payload: Dict = Body(...),
    user: User = Depends(require_admin),
):
    """Record a human verdict, then reveal which side was which."""
    fen = str(payload.get("fen") or "").strip()
    better = str(payload.get("better") or "").strip().upper()
    if not fen or better not in {"A", "B", "TIE", "NEITHER"}:
        raise HTTPException(status_code=400, detail="fen and better (A/B/TIE/NEITHER) required")

    pair = await db.model_reason_answers.find({"fen": fen}, {"_id": 0}).to_list(2)
    if len(pair) != 2:
        raise HTTPException(status_code=404, detail="Position not found")
    by_slot = {p["slot"]: p for p in pair}

    await db.reason_judgements.insert_one({
        "fen": fen,
        "better": better,
        "a_is_true": payload.get("a_is_true"),
        "b_is_true": payload.get("b_is_true"),
        "notes": str(payload.get("notes") or "").strip() or None,
        "winning_model": by_slot[better]["model"] if better in ("A", "B") else None,
        "slot_models": {s: p["model"] for s, p in by_slot.items()},
        "judged_by": user.user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    judged = await db.reason_judgements.distinct("fen")
    total = len(await db.model_reason_answers.distinct("fen"))
    return {
        "ok": True,
        # revealed only after the vote is stored
        "reveal": {s: p["model"] for s, p in by_slot.items()},
        "progress": {"judged": len(judged), "total": total},
    }


@router.get("/admin/reason-judge/results")
async def judge_results(user: User = Depends(require_admin)):
    """Human verdicts so far, and whether they agree with the model grader."""
    rows = await db.reason_judgements.find({}, {"_id": 0}).to_list(500)
    wins: Dict[str, int] = {"opus": 0, "fable": 0, "tie": 0, "neither": 0}
    for r in rows:
        if r.get("better") in ("TIE", "NEITHER"):
            wins[r["better"].lower()] += 1
        elif r.get("winning_model"):
            wins[r["winning_model"]] = wins.get(r["winning_model"], 0) + 1
    return {"judged": len(rows), "wins": wins, "judgements": rows}


# ---------------------------------------------------------------------------
# Geometry gaps — mistakes the board cannot explain yet
#
# Mohit 2026-09-17: "if you find any puzzles you don't [know] the answer for in
# arrow and captions, send them to me and I will tell you if it is buildable."
#
# Two board pictures ship today: a check that adds a second attacker, and what
# a blunder gave away. Together they cover 58.3% of user mistakes (was 0%).
# The rest are listed here rather than guessed at, because inventing an arrow
# for a position with no tactical shape is how the clutter started.
# ---------------------------------------------------------------------------


def _classify_geometry_gap(board, played, best, eval_before) -> str:
    """Why no picture is drawable. Board facts only, no engine."""
    import chess as _chess

    after_best = board.copy()
    after_best.push(best)
    if after_best.is_checkmate():
        return "best_move_is_mate"
    if board.is_capture(best):
        return "best_move_capture_not_priceable"
    if after_best.is_check():
        return "best_move_checks_wins_nothing"
    if board.is_capture(played):
        return "played_capture_not_punished"
    if abs(int(eval_before or 0)) > 800:
        return "already_decided"
    return "quiet_positional_move"


@router.get("/admin/geometry-gaps/next")
async def next_geometry_gap(
    cluster: Optional[str] = Query(default=None),
    user: User = Depends(require_geometry_reviewer),
):
    """One mistake with no drawable picture, skipping anything already ruled on."""
    import chess as _chess

    from services.caption_pipeline import _check_attack_arrows, _punishment_arrows

    ruled = set(await db.geometry_gap_rulings.distinct("fen"))
    scanned = 0
    async for doc in db.game_analyses.find(
        {"stockfish_analysis.move_evaluations.0": {"$exists": True}},
        {"_id": 0, "game_id": 1, "stockfish_analysis": 1},
    ):
        for move in (doc.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            if move.get("is_opponent_move") or (move.get("cp_loss") or 0) < 150:
                continue
            fen = str(move.get("fen_before") or "")
            best_uci = str(move.get("best_move_uci") or "")
            played_uci = str(move.get("move_uci") or "")
            if not fen or not best_uci or not played_uci or fen in ruled:
                continue
            try:
                board = _chess.Board(fen)
                played = _chess.Move.from_uci(played_uci)
                best = _chess.Move.from_uci(best_uci)
                if played not in board.legal_moves or best not in board.legal_moves:
                    continue
            except ValueError:
                continue
            scanned += 1
            # Only the ones we genuinely cannot draw.
            if _check_attack_arrows(board, best_uci):
                continue
            if _punishment_arrows(
                board, played, mover_is_user=True, cp_loss=move.get("cp_loss") or 0
            ):
                continue
            kind = _classify_geometry_gap(board, played, best, move.get("eval_before"))
            if cluster and kind != cluster:
                continue
            return {
                "game_id": doc.get("game_id"),
                "fen": fen,
                "side_to_move": "white" if board.turn else "black",
                "move_number": move.get("move_number"),
                "played_san": board.san(played),
                "best_san": board.san(best),
                "cp_loss": move.get("cp_loss"),
                "eval_before": move.get("eval_before"),
                "eval_after": move.get("eval_after"),
                "cluster": kind,
                # The punishment line IS the lesson. Mohit 2026-09-17: "the
                # punishment line tells us the problem that we are missing."
                # On 5rk1/1ppq2p1/3Rp2p/... the caption can only say Qxd6 was
                # worse than cxd6; the line says why -- 24.Nc4 hits the queen
                # on d6 with tempo, which is a rule you can carry to the next
                # game. Stored by the analyser already, so no engine call.
                "pv_after_played": [str(x) for x in (move.get("pv_after_played") or [])],
                "pv_after_best": [str(x) for x in (move.get("pv_after_best") or [])],
                # Carried for the "Copy for Claude" prompt. The analyser
                # already wrote all four and the page passed none of them on,
                # so anyone asking "why was this a mistake" was re-deriving
                # facts we had already stored.
                "cognitive_gap": move.get("cognitive_gap"),
                "critical_reason": move.get("critical_reason"),
                "threat": move.get("threat"),
                "mate_info": move.get("mate_info"),
                "ruled_count": len(ruled),
            }
    raise HTTPException(
        status_code=404,
        detail=f"No undrawable mistake left to rule on (scanned {scanned})",
    )


@router.post("/admin/geometry-gaps")
async def rule_geometry_gap(
    payload: Dict = Body(...),
    user: User = Depends(require_geometry_reviewer),
):
    """Record whether a gap is buildable. The verdict is Mohit's, not a model's."""
    fen = str(payload.get("fen") or "").strip()
    verdict = str(payload.get("verdict") or "").strip().lower()
    if not fen:
        raise HTTPException(status_code=400, detail="fen is required")
    if verdict not in {"buildable", "not_buildable", "unsure"}:
        raise HTTPException(status_code=400, detail="unknown verdict")
    await db.geometry_gap_rulings.update_one(
        {"fen": fen},
        {
            "$set": {
                "fen": fen,
                "verdict": verdict,
                "cluster": payload.get("cluster"),
                "game_id": payload.get("game_id"),
                "played_san": payload.get("played_san"),
                "best_san": payload.get("best_san"),
                "cp_loss": payload.get("cp_loss"),
                "notes": str(payload.get("notes") or "")[:2000],
                "ruled_by": user.user_id,
                "ruled_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    return {"ok": True}


@router.get("/admin/geometry-gaps/results")
async def geometry_gap_results(user: User = Depends(require_geometry_reviewer)):
    """What has been ruled so far, by cluster."""
    rows = await db.geometry_gap_rulings.find({}, {"_id": 0}).to_list(length=None)
    by_cluster: Dict[str, Dict[str, int]] = {}
    for row in rows:
        bucket = by_cluster.setdefault(str(row.get("cluster") or "unknown"), {})
        key = str(row.get("verdict") or "unsure")
        bucket[key] = bucket.get(key, 0) + 1
    return {
        "total": len(rows),
        "by_cluster": by_cluster,
        "buildable": [
            {
                "fen": r.get("fen"),
                "cluster": r.get("cluster"),
                "played_san": r.get("played_san"),
                "best_san": r.get("best_san"),
                "notes": r.get("notes"),
            }
            for r in rows
            if r.get("verdict") == "buildable"
        ],
    }


# ---------------------------------------------------------------------------
# Missing-why queue
#
# Mohit, 2026-09-22: "each blunder or mistake each side should explain the why
# and if you don't have the why, we will help, but each blunder should have
# the why." Then: "add those positions in geometry-gaps page so i or farhan
# can help you out."
#
# It lives here rather than on one of the caption-authoring pages for a
# concrete reason: GEOMETRY_REVIEWER_EMAILS is farhan.engineer07@gmail.com and
# that gate grants exactly these endpoints and nothing else. Farhan cannot
# reach /admin/captions at all, so this is the only surface he can help on.
#
# Measured before building (500 games, both sides): 697 of 5,683 mistake and
# blunder captions carry no why -- 7.7% of the player's own moves and 16.8% of
# the opponent's. The audit script that reports that number had "only audit
# USER moves" hard-coded, which is why the opponent side was free to drift.
# ---------------------------------------------------------------------------

WHY_SEVERITIES = {
    "mistake", "blunder", "serious",
    "opp_mistake", "opp_blunder", "opp_serious",
}


@router.get("/admin/geometry-gaps/no-why/next")
async def next_missing_why(
    side: Optional[str] = Query(default=None, pattern="^(user|opponent)$"),
    user: User = Depends(require_geometry_reviewer),
):
    """One mistake/blunder whose caption never says why, either side."""
    from services.caption_why_heuristics import has_why

    done = set(await db.caption_why_authoring.distinct("key"))
    scanned = 0
    async for doc in db.game_analyses.find(
        {"decryption_v5_data.0": {"$exists": True}},
        {"_id": 0, "game_id": 1, "decryption_v5_data": 1},
    ):
        gid = doc.get("game_id")
        for rec in doc.get("decryption_v5_data") or []:
            if not isinstance(rec, dict):
                continue
            sev = str(rec.get("severity") or "")
            if sev not in WHY_SEVERITIES:
                continue
            is_user = bool(rec.get("is_user_move"))
            this_side = "user" if is_user else "opponent"
            if side and side != this_side:
                continue
            caption = str(rec.get("caption") or "").strip()
            if not caption:
                continue
            played = str(rec.get("move_san") or "")
            best = rec.get("best_move_san")
            scanned += 1
            if has_why(caption, played, best):
                continue
            key = f"{gid}:{rec.get('move_number')}:{played}"
            if key in done:
                continue
            return {
                "key": key,
                "game_id": gid,
                "fen": rec.get("fen_before") or rec.get("fen"),
                "move_number": rec.get("move_number"),
                "played_san": played,
                "best_san": best,
                "side": this_side,
                "severity": sev,
                "cp_loss": rec.get("cp_loss"),
                "caption": caption,
                # The punishment line is where the why usually is, and it is
                # already stored, so the author does not have to find it.
                "pv_after_played": [str(x) for x in (rec.get("pv_after_played") or [])],
                "pv_after_best": [str(x) for x in (rec.get("pv_after_best") or [])],
                "done_count": len(done),
                "scanned": scanned,
            }
    raise HTTPException(
        status_code=404,
        detail=f"No caption left without a why (scanned {scanned})",
    )


@router.post("/admin/geometry-gaps/no-why")
async def author_missing_why(
    payload: Dict = Body(...),
    user: User = Depends(require_geometry_reviewer),
):
    """Record a hand-written why, or say this one does not need coaching."""
    key = str(payload.get("key") or "").strip()
    action = str(payload.get("action") or "").strip().lower()
    why = str(payload.get("why") or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    if action not in {"authored", "no_why_needed", "skip"}:
        raise HTTPException(
            status_code=400,
            detail="action must be authored, no_why_needed or skip")
    if action == "authored" and not why:
        raise HTTPException(
            status_code=400, detail="authored needs the why text")
    row = {
        "key": key,
        "action": action,
        "why": why or None,
        "game_id": payload.get("game_id"),
        "fen": payload.get("fen"),
        "move_number": payload.get("move_number"),
        "played_san": payload.get("played_san"),
        "best_san": payload.get("best_san"),
        "side": payload.get("side"),
        "severity": payload.get("severity"),
        "original_caption": payload.get("caption"),
        "author_email": (getattr(user, "email", "") or "").lower(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.caption_why_authoring.update_one(
        {"key": key}, {"$set": row}, upsert=True)
    return {"ok": True, "key": key, "action": action}


@router.get("/admin/geometry-gaps/no-why/results")
async def missing_why_results(user: User = Depends(require_geometry_reviewer)):
    """What has been authored so far."""
    rows = await db.caption_why_authoring.find({}, {"_id": 0}).to_list(length=None)
    by_action: Dict[str, int] = {}
    by_author: Dict[str, int] = {}
    for r in rows:
        a = str(r.get("action") or "skip")
        by_action[a] = by_action.get(a, 0) + 1
        who = str(r.get("author_email") or "unknown")
        by_author[who] = by_author.get(who, 0) + 1
    return {
        "total": len(rows),
        "by_action": by_action,
        "by_author": by_author,
        "recent": [
            {k: r.get(k) for k in
             ("key", "side", "severity", "played_san", "why", "created_at")}
            for r in sorted(rows, key=lambda x: str(x.get("created_at") or ""),
                            reverse=True)[:10]
        ],
    }
