"""Caption authoring routes — backs the AdminCaptionAuthoring web UI
(/admin/captions). Lets Mohit + Parth see the coverage audit + LOW
positions WITH BOARDS rendered, then edit JSON templates inline.

Three endpoints:

  GET  /admin/captions/audit?sample=N
       Runs the coverage audit logic (same classifiers as
       backend/scripts/caption_coverage_v5.py) and returns a structured
       payload the frontend can render. Force-regen is on by default
       so the data measures CURRENT shipped code.

  POST /admin/captions/preview
       Body: {"fen": "...", "facts": {...}, "template": "..."}
       Returns: {"rendered": "..."}
       Renders the candidate template string against a supplied
       facts dict + FEN. Lets the author preview a caption edit
       before committing.

  POST /admin/captions/commit
       Body: {"file": "R12_blunder.json", "variant": "why_user_reply",
              "template": "..."}
       Writes the new template into the JSON file at variants.<variant>.
       Returns: {"ok": true, "previous": "...", "current": "..."}

  Auth: all gated on require_admin (same pattern as routes/admin.py).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Caption Authoring"])

db = None


def set_db(database):
    global db
    db = database


from routes.auth import User
from routes.admin import require_admin


# ── Classifier (shared with scripts/caption_coverage_v5.py) ──────────

CLASSIFIERS: List[Tuple[str, str, "re.Pattern", Optional[str]]] = [
    ("HIGH", "missed_mate",               re.compile(r"would have led to mate in \d+ moves?", re.I),
     "R12_blunder.json → variants.why_user_missed_mate"),
    ("HIGH", "missed_piece",              re.compile(r"wins the (pawn|knight|bishop|rook|queen) on [a-h][1-8]", re.I),
     "R12_blunder.json → variants.why_user_missed_piece"),
    ("HIGH", "missed_clearance_attack",   re.compile(r"clears the line", re.I),
     "R12_blunder.json → variants.why_user_missed_clearance_attack"),
    ("HIGH", "missed_king_pawn_pressure", re.compile(r"keeps the pressure on [a-h][1-8]", re.I),
     "R12_blunder.json → variants.why_user_missed_king_pawn_pressure"),
    ("MID",  "attacks_played",            re.compile(r"has no safe square", re.I),
     "R12_blunder.json → variants.why_user_attacks_played"),
    ("MID",  "exchange_losing",           re.compile(r"falls\.|can't be defended", re.I),
     "R12_blunder.json → variants.why_user_exchange_losing_*"),
    ("MID",  "hanging",                   re.compile(r"is now undefended", re.I),
     "R12_blunder.json → variants.why_user_hanging"),
    ("MID",  "capture",                   re.compile(r"winning your (pawn|knight|bishop|rook|queen)", re.I),
     "R12_blunder.json → variants.why_user_capture"),
    ("MID",  "check",                     re.compile(r"forcing your king", re.I),
     "R12_blunder.json → variants.why_user_check"),
    ("LOW",  "missed_material",           re.compile(r"wins material in the resulting line", re.I),
     "R12_blunder.json → variants.why_user_missed_material"),
    ("LOW",  "reply",                     re.compile(r"Opponent's strongest reply:", re.I),
     "R12_blunder.json → variants.why_user_reply"),
]


def classify(caption: str) -> Tuple[str, str, Optional[str]]:
    if not caption:
        return ("NONE", "empty", None)
    for tier, key, pat, jp in CLASSIFIERS:
        if pat.search(caption):
            return (tier, key, jp)
    return ("NONE", "bare_severity", "R12_blunder.json → why_clauses_user (add new variant)")


# ── /audit endpoint ──────────────────────────────────────────────────

@router.get("/admin/captions/audit")
async def audit_endpoint(sample: int = 50, user: User = Depends(require_admin)):
    """Audit a sample of analyzed games. Force-regens any below current
    V5 version so the data measures shipped code."""
    if db is None:
        raise HTTPException(500, "Database not initialized")

    from services.game_decryption_v5_service import (
        generate_game_decryption_v5, V5_COACHING_VERSION,
    )
    from datetime import datetime, timezone
    from collections import Counter

    cursor = db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True, "$ne": None}},
        {"_id": 0, "game_id": 1, "user_id": 1, "decryption_v5_data": 1,
         "decryption_v5_version": 1},
    ).sort("created_at", -1).limit(sample)
    games = await cursor.to_list(length=sample)

    # Force-regen stale games
    for g in games:
        if (g.get("decryption_v5_version") or 0) >= V5_COACHING_VERSION:
            continue
        gid = g["game_id"]
        full_game = await db.games.find_one(
            {"game_id": gid},
            {"_id": 0, "pgn": 1, "user_color": 1, "user_id": 1},
        )
        full_analysis = await db.game_analyses.find_one(
            {"game_id": gid}, {"_id": 0, "stockfish_analysis": 1},
        )
        if not full_game or not full_analysis:
            continue
        sa = full_analysis.get("stockfish_analysis") or {}
        move_evals = sa.get("move_evaluations") or sa.get("moves") or []
        if not full_game.get("pgn") or not move_evals:
            continue
        try:
            new_v5 = await generate_game_decryption_v5(
                full_game["pgn"], full_game.get("user_color", "white"),
                move_evals, full_game.get("user_id") or "", db,
            )
        except Exception as exc:
            logger.warning(f"[audit] regen failed for {gid}: {exc}")
            continue
        if not new_v5:
            continue
        await db.game_analyses.update_one(
            {"game_id": gid},
            {"$set": {
                "decryption_v5_data": new_v5,
                "decryption_v5_version": V5_COACHING_VERSION,
                "decryption_v5_generated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        g["decryption_v5_data"] = new_v5
        g["decryption_v5_version"] = V5_COACHING_VERSION

    # Classify
    by_tier = Counter()
    by_template: Dict[Tuple[str, str], Dict[str, Any]] = {}
    positions: List[Dict[str, Any]] = []
    total = 0

    for game in games:
        gid = game["game_id"]
        for m in game.get("decryption_v5_data") or []:
            if not m.get("is_user_move"):
                continue
            cpl = m.get("cp_loss") or 0
            if cpl < 100:
                continue
            total += 1
            cap = m.get("caption") or ""
            tier, key, jp = classify(cap)
            by_tier[tier] += 1
            entry = by_template.setdefault((tier, key), {
                "tier": tier, "key": key, "json_path": jp,
                "count": 0, "sample_positions": [],
            })
            entry["count"] += 1
            if tier in ("LOW", "NONE") and len(entry["sample_positions"]) < 12:
                entry["sample_positions"].append({
                    "game_id": gid,
                    "move_number": m.get("move_number"),
                    "move_san": m.get("move_san"),
                    "cp_loss": cpl,
                    "fen_before": m.get("fen_before"),
                    "fen_after": m.get("fen_after"),
                    "caption": cap,
                    "best_move_san": m.get("best_move_san"),
                    "is_white": m.get("is_white"),
                })

    templates_list = sorted(by_template.values(), key=lambda e: -e["count"])

    return {
        "games_scanned": len(games),
        "v5_version": V5_COACHING_VERSION,
        "total_blunder_moves": total,
        "tier_counts": dict(by_tier),
        "tier_pct": {
            t: (100.0 * by_tier[t] / total if total else 0.0)
            for t in ("HIGH", "MID", "LOW", "NONE")
        },
        "high_pct": (100.0 * by_tier["HIGH"] / total) if total else 0.0,
        "fallback_pct": (
            100.0 * (by_tier["LOW"] + by_tier["NONE"]) / total
        ) if total else 0.0,
        "templates": templates_list,
    }


# ── /preview endpoint ────────────────────────────────────────────────

class PreviewRequest(BaseModel):
    template: str
    facts: Dict[str, Any]


@router.post("/admin/captions/preview")
async def preview_endpoint(req: PreviewRequest = Body(...), user: User = Depends(require_admin)):
    """Substitute the candidate template against the supplied facts.
    Same .format() rules as the production renderer. Returns the
    rendered string or an error message."""
    try:
        rendered = req.template.format(**req.facts)
        return {"ok": True, "rendered": rendered}
    except KeyError as exc:
        return {"ok": False, "error": f"Missing fact: {exc}", "rendered": None}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rendered": None}


# ── /commit endpoint ─────────────────────────────────────────────────

_CAPTIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "captions",
)
_ALLOWED_FILES = {
    fn for fn in os.listdir(_CAPTIONS_DIR) if fn.endswith(".json")
} if os.path.isdir(_CAPTIONS_DIR) else set()


# ── Drafts queue (Mohit 2026-05-20) ──────────────────────────────────
# Authors don't write directly to JSON anymore. Submissions land in
# `caption_drafts` for Claude to review (chess accuracy, placeholder
# validity, voice), then Mohit/Parth approve in the UI — only then
# does the template hit the JSON file.

class SubmitRequest(BaseModel):
    file: str
    variant: str
    template: str
    position_context: Optional[Dict[str, Any]] = None  # FEN, move, caption


def _read_current_template(file: str, variant: str) -> Optional[str]:
    if file not in _ALLOWED_FILES:
        return None
    path = os.path.join(_CAPTIONS_DIR, file)
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    return (data.get("variants") or {}).get(variant)


@router.post("/admin/captions/submit")
async def submit_endpoint(req: SubmitRequest = Body(...), user: User = Depends(require_admin)):
    """Queue a new template for review. Does NOT touch the JSON file.

    Path safety:
      - Filename must be in backend/data/captions/.
      - Variant must already exist (creating new variants needs
        predicate wiring — not exposed via this endpoint).
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    if req.file not in _ALLOWED_FILES:
        raise HTTPException(400, f"Unknown file: {req.file}")
    current = _read_current_template(req.file, req.variant)
    if current is None:
        raise HTTPException(
            400, f"Variant '{req.variant}' does not exist in {req.file}.",
        )
    if req.template == current:
        raise HTTPException(400, "Proposed template is identical to current.")
    import uuid
    from datetime import datetime, timezone
    draft = {
        "draft_id": str(uuid.uuid4()),
        "file": req.file,
        "variant": req.variant,
        "current_template": current,
        "proposed_template": req.template,
        "position_context": req.position_context or {},
        "author_email": getattr(user, "email", None),
        "author_name": getattr(user, "name", None),
        "status": "pending",
        "claude_review": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_at": None,
        "approved_at": None,
    }
    await db.caption_drafts.insert_one(draft)
    return {"ok": True, "draft_id": draft["draft_id"]}


@router.get("/admin/captions/drafts")
async def drafts_endpoint(status: str = "pending", user: User = Depends(require_admin)):
    """List drafts, default to pending only."""
    if db is None:
        raise HTTPException(500, "Database not initialized")
    cursor = db.caption_drafts.find(
        {"status": status},
        {"_id": 0},
    ).sort("created_at", -1).limit(100)
    return {"drafts": await cursor.to_list(length=100)}


class ReviewRequest(BaseModel):
    claude_review: str  # text review from Claude


@router.post("/admin/captions/drafts/{draft_id}/review")
async def review_endpoint(draft_id: str, req: ReviewRequest = Body(...), user: User = Depends(require_admin)):
    """Attach Claude's review text to a draft. Doesn't change status —
    Mohit/Parth still need to approve/reject explicitly."""
    if db is None:
        raise HTTPException(500, "Database not initialized")
    from datetime import datetime, timezone
    result = await db.caption_drafts.update_one(
        {"draft_id": draft_id},
        {"$set": {
            "claude_review": req.claude_review,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Draft not found")
    return {"ok": True}


@router.post("/admin/captions/drafts/{draft_id}/approve")
async def approve_endpoint(draft_id: str, user: User = Depends(require_admin)):
    """Approve a draft — THIS is what writes the new template to the
    JSON file. Mohit/Parth click this only after reviewing Claude's
    feedback (if any)."""
    if db is None:
        raise HTTPException(500, "Database not initialized")
    draft = await db.caption_drafts.find_one({"draft_id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft["status"] != "pending":
        raise HTTPException(400, f"Draft already {draft['status']}")
    if draft["file"] not in _ALLOWED_FILES:
        raise HTTPException(400, f"Unknown file: {draft['file']}")

    path = os.path.join(_CAPTIONS_DIR, draft["file"])
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    variants = data.get("variants") or {}
    if draft["variant"] not in variants:
        raise HTTPException(400, f"Variant '{draft['variant']}' missing from {draft['file']}.")
    previous = variants[draft["variant"]]
    variants[draft["variant"]] = draft["proposed_template"]
    data["variants"] = variants
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)
        fp.write("\n")

    try:
        from services.caption_templates import reload_templates
        reload_templates()
    except Exception:
        pass

    from datetime import datetime, timezone
    await db.caption_drafts.update_one(
        {"draft_id": draft_id},
        {"$set": {
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approver_email": getattr(user, "email", None),
            "previous_template_at_approve": previous,
        }},
    )
    return {"ok": True, "previous": previous, "current": draft["proposed_template"]}


@router.post("/admin/captions/drafts/{draft_id}/reject")
async def reject_endpoint(draft_id: str, user: User = Depends(require_admin)):
    """Reject a draft — marks it dropped, no JSON changes."""
    if db is None:
        raise HTTPException(500, "Database not initialized")
    from datetime import datetime, timezone
    result = await db.caption_drafts.update_one(
        {"draft_id": draft_id, "status": "pending"},
        {"$set": {
            "status": "rejected",
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "approver_email": getattr(user, "email", None),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Draft not found or already finalized")
    return {"ok": True}
