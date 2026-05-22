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

# Shared classifier — auto-loads every variant from data/captions/
# JSON files. See services/caption_classifier.py for the tier mapping.
from services.caption_classifier import classifier


def classify(caption: str, rule_name: str = "") -> Tuple[str, str, Optional[str]]:
    """Adapter to the shared CaptionClassifier. Returns
    (tier, variant_key, json_path). Pass rule_name from the move
    record for precise file routing."""
    result = classifier.classify(caption, rule_name=rule_name)
    return (result["tier"], result["variant_key"], result["json_path"])


# ── /audit endpoint ──────────────────────────────────────────────────

@router.get("/admin/captions/audit")
async def audit_endpoint(
    sample: int = 50,
    sample_tiers: str = "LOW,NONE",
    samples_per_variant: int = 50,
    force_regen: bool = False,
    user: User = Depends(require_admin),
):
    """Audit a sample of analyzed games.

    sample_tiers: comma-separated list of tiers to retain board-level
    sample positions for (default LOW,NONE — the authoring backlog).
    Pass "HIGH,MID,LOW,NONE" to retain samples for every tier when
    pedagogical-review of higher tiers is needed.
    samples_per_variant: how many positions to keep per template variant.
    force_regen: when true, force-regen any game whose stored V5 version
    is below the current V5_COACHING_VERSION before classifying. Slow
    after a version bump (every game is stale → seconds per game). When
    false (default), classify whatever's stored — fast page load but
    captions may reflect an older v5 version (shown in the page header
    as `v{auditData.v5_version}`). Use the toggle in the UI to opt into
    regen when you want freshest captions.
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")

    sample_tier_set = {
        t.strip().upper() for t in (sample_tiers or "").split(",") if t.strip()
    }

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

    # Force-regen stale games (opt-in via ?force_regen=true). Skipped by
    # default — after a V5_COACHING_VERSION bump, regenerating 50+ games
    # each blows past the host nginx 60s timeout and gives the user an
    # HTTP 504. Without regen we classify whatever's stored, which is
    # fast and lets the page load instantly; the page header shows the
    # version of the stored captions so the user knows what they're
    # looking at.
    if force_regen:
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

    # Classify EVERY user move with a caption (no cp_loss filter —
    # full coverage across all caption surfaces, not just blunders).
    by_tier = Counter()
    by_file: Dict[str, Dict[str, Any]] = {}
    by_template: Dict[Tuple[str, str], Dict[str, Any]] = {}
    total = 0
    silent = 0  # moves with no caption at all (R_FALLBACK)

    for game in games:
        gid = game["game_id"]
        for m in game.get("decryption_v5_data") or []:
            if not m.get("is_user_move"):
                continue
            cap = m.get("caption") or ""
            if not cap:
                silent += 1
                continue
            total += 1
            tier, key, jp = classify(cap, rule_name=m.get("rule_name", ""))
            by_tier[tier] += 1

            # Derive file name from json_path if present
            file_name = None
            if jp:
                file_name = jp.split(" ")[0]

            file_key = file_name or "(no JSON file — bare severity)"
            file_entry = by_file.setdefault(file_key, {
                "file": file_key,
                "count": 0,
                "tier_counts": {"HIGH": 0, "MID": 0, "LOW": 0, "NONE": 0},
                "variants": {},
            })
            file_entry["count"] += 1
            file_entry["tier_counts"][tier] = file_entry["tier_counts"].get(tier, 0) + 1

            variant_entry = file_entry["variants"].setdefault(key, {
                "variant_key": key,
                "tier": tier,
                "json_path": jp,
                "count": 0,
                "sample_positions": [],
            })
            variant_entry["count"] += 1

            # Retain board-level samples for tiers the caller asked for.
            # Default keeps LOW/NONE (authoring backlog). Pass
            # sample_tiers=HIGH,MID,LOW,NONE for full pedagogical review.
            if tier in sample_tier_set and len(variant_entry["sample_positions"]) < samples_per_variant:
                variant_entry["sample_positions"].append({
                    "game_id": gid,
                    "move_number": m.get("move_number"),
                    "move_san": m.get("move_san"),
                    "cp_loss": m.get("cp_loss") or 0,
                    "fen_before": m.get("fen_before"),
                    "fen_after": m.get("fen_after"),
                    "caption": cap,
                    "best_move_san": m.get("best_move_san"),
                    "is_white": m.get("is_white"),
                })

            # Flat per-template list (legacy, kept for backward compat)
            t_entry = by_template.setdefault((tier, key), {
                "tier": tier, "key": key, "json_path": jp,
                "count": 0, "sample_positions": [],
            })
            t_entry["count"] += 1
            # Same tier filter for the legacy flat list.
            if tier in sample_tier_set and len(t_entry["sample_positions"]) < max(samples_per_variant, 12):
                t_entry["sample_positions"].append({
                    "game_id": gid,
                    "move_number": m.get("move_number"),
                    "move_san": m.get("move_san"),
                    "cp_loss": m.get("cp_loss") or 0,
                    "fen_before": m.get("fen_before"),
                    "fen_after": m.get("fen_after"),
                    "caption": cap,
                    "best_move_san": m.get("best_move_san"),
                    "is_white": m.get("is_white"),
                })

    # Convert by_file variants dict → list, sorted by count desc.
    files_list: List[Dict[str, Any]] = []
    for fkey, fentry in sorted(by_file.items(), key=lambda kv: -kv[1]["count"]):
        fentry["variants"] = sorted(
            fentry["variants"].values(), key=lambda v: -v["count"]
        )
        files_list.append(fentry)
    templates_list = sorted(by_template.values(), key=lambda e: -e["count"])

    return {
        "games_scanned": len(games),
        "v5_version": V5_COACHING_VERSION,
        "total_caption_moves": total,
        "silent_moves": silent,
        "tier_counts": dict(by_tier),
        "tier_pct": {
            t: (100.0 * by_tier[t] / total if total else 0.0)
            for t in ("HIGH", "MID", "LOW", "NONE")
        },
        "high_pct": (100.0 * by_tier["HIGH"] / total) if total else 0.0,
        "fallback_pct": (
            100.0 * (by_tier["LOW"] + by_tier["NONE"]) / total
        ) if total else 0.0,
        "files": files_list,
        "templates": templates_list,
        "sample_tiers": sorted(sample_tier_set),
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
