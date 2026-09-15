"""Evidence-gated selector and lifecycle for player Game Review.

This module selects games only from already-authorized GameTeachingPlan
projections. It does not parse boards, call an engine, or infer chess facts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from pymongo.errors import DuplicateKeyError

from services.complete_coaching_access import get_complete_coaching_access
from services.community_game_study_service import (
    CommunityGameStudyError,
    candidate_from_study as community_candidate_from_study,
    load_admitted_selection,
    load_admitted_study,
    load_shadow_selection,
    project_visible_study,
    record_shadow_evidence,
    reveal_study_chapter,
    shadow_enabled as community_shadow_enabled,
    visible_enabled as community_visible_enabled,
    visible_for_operability_role as community_visible_for_operability_role,
    verify_guided_replay_move,
)
from services.game_review_contracts import (
    FEATURE_FLAG,
    QUALITY_V2_FEATURE_FLAG,
    personalized_review_quality_v2_enabled,
)
from services.game_review_event_adapter import maybe_attach_phase5_review_fields
from services.phase8_release_evidence import record_phase8_reach_event
from services.rating_resolver import get_coaching_rating, get_rating_band


COLLECTION = "game_review_prescriptions"
SCHEMA_VERSION = "coach_selected_game_review.v1"
SELECTOR_VERSION = "focus_then_authorized_richness.v1"
ACTIVE_STATES = ("recommended", "started")
FINAL_STATES = ("completed", "dismissed", "superseded")
TRUSTED_NEXT_ACTION_PREFIXES = (
    "/game/",
    "/games",
    "/home",
    "/import",
    "/play-with-coach",
    "/training",
)


class ReviewPrescriptionError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _trusted_next_action_href(value: Any) -> Optional[str]:
    """Accept only relative routes owned by the ChessGuru application."""
    href = str(value or "").strip()
    if not href.startswith("/") or href.startswith("//"):
        return None
    path = href.split("?", 1)[0].split("#", 1)[0]
    if not any(
        path == prefix
        or (prefix.endswith("/") and path.startswith(prefix))
        or (not prefix.endswith("/") and path.startswith(f"{prefix}/"))
        for prefix in TRUSTED_NEXT_ACTION_PREFIXES
    ):
        return None
    return href


def _iso(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        value = value.replace(tzinfo=value.tzinfo or timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return value.strip() if isinstance(value, str) and value.strip() else None


def _timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp()
        except ValueError:
            pass
    return 0.0


def _tokens(value: Any) -> set[str]:
    return {part for part in re.split(r"[^a-z0-9]+", str(value or "").lower()) if part}


def _focus_matches(focus_key: str, event: Mapping[str, Any]) -> bool:
    focus = _tokens(focus_key)
    if not focus:
        return False
    concept = event.get("concept") or {}
    evidence = event.get("evidence") or {}
    observed: set[str] = set()
    for value in (
        concept.get("concept_id"),
        concept.get("content_ref"),
        evidence.get("quality_id"),
    ):
        observed.update(_tokens(value))
    return focus.issubset(observed)


def _event_preview(event: Mapping[str, Any], role: str) -> Optional[Dict[str, Any]]:
    teaching = event.get("teaching") or {}
    move = event.get("move") or {}
    explanation = str(
        teaching.get("caption")
        or teaching.get("practical_lead")
        or teaching.get("principle")
        or ""
    ).strip()
    if not explanation:
        return None
    labels = {
        "turning_point": "The decision that changed the game",
        "missed_opportunity": "What was possible here",
        "recurring_connection": "How this connects to your chess",
        "demonstrated_knowledge": "What you understood well",
        "opponent_plan": "What your opponent was trying",
        "knowledge_gap": "The idea to learn here",
        "reflection": "A decision worth revisiting",
    }
    return {
        "event_id": str(event.get("event_id") or ""),
        "role": role,
        "label": labels.get(role, "A moment worth understanding"),
        "headline": str(teaching.get("headline") or "").strip(),
        "explanation": explanation,
        "principle": str(teaching.get("principle") or "").strip(),
        "move_number": move.get("number"),
        "move_san": str(move.get("san") or ""),
    }


def candidate_from_projection(
    *,
    game: Mapping[str, Any],
    raw_plan: Mapping[str, Any],
    projection: Mapping[str, Any],
    focus_key: str = "",
) -> Optional[Dict[str, Any]]:
    """Convert a safe plan projection into a candidate; fail closed on drift."""
    plan = projection.get("game_teaching_plan")
    if not isinstance(plan, Mapping):
        return None
    events = {
        str(item.get("event_id") or ""): item
        for item in projection.get("teachable_events") or []
        if isinstance(item, Mapping) and item.get("event_id")
    }
    chapters = []
    focus_match = False
    focus_event_id = ""
    for chapter in plan.get("chapters") or []:
        if not isinstance(chapter, Mapping):
            return None
        event = events.get(str(chapter.get("event_id") or ""))
        preview = _event_preview(event, str(chapter.get("role") or "")) if event else None
        if preview is None:
            return None
        event_matches_focus = _focus_matches(focus_key, event)
        focus_match = focus_match or event_matches_focus
        if event_matches_focus and not focus_event_id:
            focus_event_id = str(event.get("event_id") or "")
        chapters.append(preview)
    if not chapters:
        return None
    envelope_plan = raw_plan.get("plan") if isinstance(raw_plan, Mapping) else {}
    fingerprint = (
        str(envelope_plan.get("input_fingerprint") or "")
        if isinstance(envelope_plan, Mapping)
        else ""
    )
    return {
        "game_id": str(game.get("game_id") or ""),
        "game": dict(game),
        "plan_id": str(plan.get("plan_id") or ""),
        "plan_fingerprint": fingerprint,
        "game_arc": str(plan.get("game_arc") or ""),
        "takeaway": str(plan.get("takeaway") or ""),
        "chapters": chapters,
        "focus_match": focus_match,
        "focus_event_id": focus_event_id,
        "focus_key": focus_key if focus_match else "",
        "authorized_chapter_count": len(chapters),
        "recency": max(
            _timestamp(game.get("date_played")),
            _timestamp(game.get("imported_at")),
            _timestamp(game.get("analyzed_at")),
            _timestamp(game.get("created_at")),
        ),
    }


def rank_candidates(candidates: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    """Measured formula: current focus, authorized richness, then recency."""
    return sorted(
        (dict(item) for item in candidates),
        key=lambda item: (
            int(bool(item.get("focus_match"))),
            int(item.get("authorized_chapter_count") or 0),
            float(item.get("recency") or 0),
            str(item.get("game_id") or ""),
        ),
        reverse=True,
    )


def _public_game(game: Mapping[str, Any]) -> Dict[str, Any]:
    raw = str(game.get("result") or "").strip().lower()
    color = str(game.get("user_color") or "").strip().lower()
    if raw in {"win", "w"} or (raw == "1-0" and color == "white") or (raw == "0-1" and color == "black"):
        result = "Won"
    elif raw in {"loss", "l"} or (raw == "1-0" and color == "black") or (raw == "0-1" and color == "white"):
        result = "Lost"
    elif raw in {"draw", "d", "1/2-1/2", "½-½"}:
        result = "Drew"
    else:
        result = "Finished"
    return {
        "game_id": str(game.get("game_id") or ""),
        "opponent": str(
            game.get("opponent_name")
            or game.get("opponent")
            or ("Coach" if game.get("platform") == "coach" else "Opponent")
        ).strip(),
        "result": result,
        "opening": str(game.get("opening") or game.get("opening_name") or "").strip(),
        "platform": str(game.get("platform") or "").strip(),
        "played_at": _iso(game.get("date_played") or game.get("imported_at") or game.get("analyzed_at")),
    }


def public_prescription(document: Mapping[str, Any], candidate: Mapping[str, Any]) -> Dict[str, Any]:
    if candidate.get("source_kind") == "community":
        resume = document.get("resume") or {}
        move_index = int(resume.get("move_index", -1))
        prescription_id = str(document.get("prescription_id") or "")
        study_id = str(candidate.get("study_id") or "")
        return {
            "prescription_id": prescription_id,
            "state": str(document.get("state") or "recommended"),
            "source_kind": "community",
            "study_id": study_id,
            "game": {
                "game_id": study_id,
                "opponent": "A player near your level",
                "result": "Study",
                "opening": "",
                "platform": "community",
                "played_at": None,
            },
            "reason": {
                "headline": "A complete game for your current lesson",
                "body": (
                    "Someone near your level faced the same kind of decisions. "
                    "I chose the moments that are worth understanding."
                ),
            },
            "chapters": list(candidate.get("chapters") or []),
            "takeaway": "Predict each moment, watch the idea, then replay it.",
            "resume": {
                "move_index": move_index,
                "updated_at": _iso(resume.get("updated_at")),
            },
            "review_url": (
                f"/game/{study_id}?prescription={prescription_id}"
                f"&resume={move_index}&community=1"
            ),
        }
    focus_match = bool(candidate.get("focus_match"))
    chapters = list(candidate.get("chapters") or [])
    focus_event_id = str(candidate.get("focus_event_id") or "")
    first_chapter = next(
        (
            chapter
            for chapter in chapters
            if focus_event_id
            and str(chapter.get("event_id") or "") == focus_event_id
        ),
        chapters[0] if chapters else {},
    )
    pattern_headline = str(
        first_chapter.get("headline")
        or first_chapter.get("principle")
        or candidate.get("takeaway")
        or candidate.get("game_arc")
        or first_chapter.get("explanation")
    ).strip()
    reason = {
        # The safe GameTeachingPlan already owns the chess idea. Reuse it as
        # the memorable headline instead of hiding it behind generic product
        # copy such as "I picked this game".
        "headline": pattern_headline,
        "body": (
            "This is where your current lesson shows up in a real game."
            if focus_match
            else str(candidate.get("game_arc") or "").strip()
        ),
    }
    resume = document.get("resume") or {}
    move_index = int(resume.get("move_index", -1))
    prescription_id = str(document.get("prescription_id") or "")
    game_id = str(candidate.get("game_id") or "")
    return {
        "prescription_id": prescription_id,
        "state": str(document.get("state") or "recommended"),
        "game": _public_game(candidate.get("game") or {}),
        "reason": reason,
        "chapters": chapters,
        "takeaway": str(candidate.get("takeaway") or ""),
        "resume": {"move_index": move_index, "updated_at": _iso(resume.get("updated_at"))},
        "review_url": f"/game/{game_id}?prescription={prescription_id}&resume={move_index}",
    }


async def ensure_review_prescription_indexes(db) -> None:
    collection = db[COLLECTION]
    await collection.create_index("prescription_id", unique=True)
    await collection.create_index(
        [("user_id", 1), ("is_active", 1)],
        unique=True,
        partialFilterExpression={"is_active": True},
        name="one_active_game_review_per_user",
    )
    await collection.create_index([("user_id", 1), ("state", 1), ("updated_at", -1)])
    await collection.create_index([("user_id", 1), ("game_id", 1)])


def _projection_env(env: Optional[Mapping[str, str]]) -> Dict[str, str]:
    source = os.environ if env is None else env
    return {
        FEATURE_FLAG: "true",
        QUALITY_V2_FEATURE_FLAG: (
            "true" if personalized_review_quality_v2_enabled(source) else "false"
        ),
    }


async def _load_candidates(
    db,
    user_id: str,
    *,
    focus_key: str,
    excluded_game_ids: Sequence[str],
    included_game_ids: Sequence[str] = (),
    env: Optional[Mapping[str, str]] = None,
) -> list[Dict[str, Any]]:
    query: Dict[str, Any] = {
        "user_id": user_id,
        "is_analyzed": True,
        "reviewed": {"$ne": True},
    }
    if excluded_game_ids:
        query["game_id"] = {"$nin": list(excluded_game_ids)}
    if included_game_ids:
        query["game_id"] = {"$in": list(included_game_ids)}
    game_projection = {
        "_id": 0,
        "game_id": 1,
        "opponent": 1,
        "opponent_name": 1,
        "result": 1,
        "user_color": 1,
        "opening": 1,
        "opening_name": 1,
        "platform": 1,
        "date_played": 1,
        "imported_at": 1,
        "analyzed_at": 1,
        "created_at": 1,
    }
    games = await db.games.find(query, game_projection).to_list(None)
    by_id = {str(game["game_id"]): game for game in games if game.get("game_id")}
    if not by_id:
        return []
    analyses = await db.game_analyses.find(
        {
            "game_id": {"$in": list(by_id)},
            "game_teaching_plan.plan.chapters.0": {"$exists": True},
        },
        {
            "_id": 0,
            "game_id": 1,
            "decryption_v5_data": 1,
            "game_teaching_plan": 1,
        },
    ).to_list(None)
    result = []
    projection_env = _projection_env(env)
    for analysis in analyses:
        game = by_id.get(str(analysis.get("game_id") or ""))
        raw_plan = analysis.get("game_teaching_plan")
        moves = analysis.get("decryption_v5_data")
        if (
            game is None
            or not isinstance(raw_plan, Mapping)
            or not isinstance(moves, list)
        ):
            continue
        projected = maybe_attach_phase5_review_fields(
            {"decryption_data": []},
            stored_moves=tuple(moves),
            stored_plan=raw_plan,
            env=projection_env,
        )
        candidate = candidate_from_projection(
            game=game,
            raw_plan=raw_plan,
            projection=projected,
            focus_key=focus_key,
        )
        if candidate:
            result.append(candidate)
    return rank_candidates(result)


async def _focus_key(db, user_id: str) -> str:
    """The topic the player is working on, or "" when there isn't one.

    user_active_focus holds strengths as well as weaknesses. Selecting on
    status alone returned a STRENGTH for 39 of the 54 production users with an
    active focus, and focus_match is the first sort key in rank_candidates --
    so the coach would have picked a game, and explained why it mattered, on
    the strength of something the player is already good at.

    The filter is owned by focus_bridge, which owns this collection.
    """
    from services.focus_bridge import ACTIVE_WEAKNESS_FILTER

    focus = await db.user_active_focus.find_one(
        {"user_id": user_id, **ACTIVE_WEAKNESS_FILTER},
        {
            "_id": 0,
            "topic_key": 1,
            "focus_kind": 1,
            "detector_quality_id": 1,
        },
    )
    if not isinstance(focus, Mapping):
        return ""
    return str(
        focus.get("topic_key")
        or focus.get("focus_kind")
        or focus.get("detector_quality_id")
        or ""
    ).strip()


async def _focus_identity(db, user_id: str) -> Dict[str, str]:
    from services.focus_bridge import ACTIVE_WEAKNESS_FILTER

    focus = await db.user_active_focus.find_one(
        {"user_id": user_id, **ACTIVE_WEAKNESS_FILTER},
        {
            "_id": 0,
            "topic_key": 1,
            "focus_kind": 1,
            "detector_quality_id": 1,
        },
    )
    if not isinstance(focus, Mapping):
        return {"key": "", "concept_id": "", "quality_id": ""}
    kind = str(focus.get("focus_kind") or "").strip()
    return {
        "key": str(
            focus.get("topic_key")
            or kind
            or focus.get("detector_quality_id")
            or ""
        ).strip(),
        "concept_id": kind.replace("/", "."),
        "quality_id": str(focus.get("detector_quality_id") or "").strip(),
    }


async def _community_operability_visible(
    db,
    user_id: str,
    env: Optional[Mapping[str, str]],
) -> bool:
    """Apply the first-cohort role restriction after canonical access.

    Admin status only narrows the global visibility switch. It never replaces
    personalized-review enrollment, the locked target, or the user's baseline.
    """
    if not community_visible_enabled(env):
        return False
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "role": 1},
    )
    return community_visible_for_operability_role(
        (user or {}).get("role"),
        env,
    )


async def _terminal_game_ids(db, user_id: str) -> list[str]:
    rows = await db[COLLECTION].find(
        {"user_id": user_id, "state": {"$in": list(FINAL_STATES)}},
        {"_id": 0, "game_id": 1},
    ).to_list(None)
    return [str(row["game_id"]) for row in rows if row.get("game_id")]


async def _candidate_for_document(
    db,
    user_id: str,
    document: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]],
) -> Optional[Dict[str, Any]]:
    if document.get("source_kind") == "community":
        if not await _community_operability_visible(db, user_id, env):
            return None
        study = await load_admitted_study(
            db, str(document.get("study_id") or "")
        )
        if study is None:
            return None
        candidate = community_candidate_from_study(
            study,
            focus_concept_id=str(document.get("focus_concept_id") or ""),
            focus_quality_id=str(document.get("focus_quality_id") or ""),
            rating_band=str(document.get("rating_band") or ""),
        )
        if candidate is None:
            return None
        if (
            str(study["plan"]["plan_id"]) != str(document.get("plan_id") or "")
            or str(study["plan"]["input_fingerprint"])
            != str(document.get("plan_fingerprint") or "")
        ):
            return None
        public = project_visible_study(study)
        return {
            **candidate,
            "game_id": study["study_id"],
            "plan_id": study["plan"]["plan_id"],
            "plan_fingerprint": study["plan"]["input_fingerprint"],
            "chapters": public["chapters"],
        }
    candidates = await _load_candidates(
        db,
        user_id,
        focus_key=str(document.get("focus_key") or ""),
        excluded_game_ids=(),
        included_game_ids=(str(document.get("game_id") or ""),),
        env=env,
    )
    for item in candidates:
        if (
            item["game_id"] == document.get("game_id")
            and item["plan_id"] == document.get("plan_id")
            and item["plan_fingerprint"]
            == str(document.get("plan_fingerprint") or "")
        ):
            return item
    return None


def _response(
    document: Mapping[str, Any], candidate: Mapping[str, Any]
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": True,
        "paused": False,
        "status": document.get("state"),
        "prescription": public_prescription(document, candidate),
    }


async def _with_review_states(
    db, user_id: str, response: Mapping[str, Any]
) -> Dict[str, Any]:
    rows = await db[COLLECTION].find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "state": 1, "updated_at": 1},
    ).to_list(None)
    rows.sort(key=lambda row: _timestamp(row.get("updated_at")), reverse=True)
    states: Dict[str, str] = {}
    for row in rows:
        game_id = str(row.get("game_id") or "")
        state = str(row.get("state") or "")
        if game_id and state and game_id not in states:
            states[game_id] = state
    return {**dict(response), "review_states": states}


async def get_recommendation(
    db,
    user_id: str,
    *,
    user_doc: Optional[Mapping[str, Any]] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    access = await get_complete_coaching_access(
        db, user_id, user_doc=user_doc, env=env
    )
    if not access.enabled:
        return {
            "schema_version": SCHEMA_VERSION,
            "enabled": False,
            "paused": access.paused,
            "status": "disabled",
            "reason": access.reason,
            "prescription": None,
        }

    collection = db[COLLECTION]
    active = await collection.find_one(
        {"user_id": user_id, "is_active": True}, {"_id": 0}
    )
    if active:
        candidate = await _candidate_for_document(db, user_id, active, env=env)
        if candidate is not None:
            return await _with_review_states(
                db, user_id, _response(active, candidate)
            )
        now = _now()
        await collection.update_one(
            {
                "prescription_id": active.get("prescription_id"),
                "user_id": user_id,
                "is_active": True,
            },
            {
                "$set": {
                    "state": "superseded",
                    "is_active": False,
                    "superseded_at": now,
                    "updated_at": now,
                    "superseded_reason": "verified_plan_no_longer_current",
                }
            },
        )

    focus_identity = await _focus_identity(db, user_id)
    focus_key = focus_identity["key"]
    candidates = await _load_candidates(
        db,
        user_id,
        focus_key=focus_key,
        excluded_game_ids=await _terminal_game_ids(db, user_id),
        env=env,
    )
    community_selection = None
    if community_shadow_enabled(env):
        rating_band = get_rating_band(await get_coaching_rating(db, user_id))
        terminal_studies = await db[COLLECTION].find(
            {
                "user_id": user_id,
                "source_kind": "community",
                "state": {"$in": list(FINAL_STATES)},
            },
            {"_id": 0, "study_id": 1},
        ).to_list(None)
        community_selection = await load_shadow_selection(
            db,
            focus_concept_id=focus_identity["concept_id"],
            focus_quality_id=focus_identity["quality_id"],
            rating_band=rating_band,
            terminal_study_ids=[
                str(item.get("study_id") or "") for item in terminal_studies
            ],
        )
        await record_shadow_evidence(
            db,
            community_selection,
            focus_concept_id=focus_identity["concept_id"],
            focus_quality_id=focus_identity["quality_id"],
            rating_band=rating_band,
        )
        if (
            not candidates
            and await _community_operability_visible(db, user_id, env)
        ):
            admitted_selection = await load_admitted_selection(
                db,
                focus_concept_id=focus_identity["concept_id"],
                focus_quality_id=focus_identity["quality_id"],
                rating_band=rating_band,
                terminal_study_ids=[
                    str(item.get("study_id") or "")
                    for item in terminal_studies
                ],
            )
            selected = admitted_selection.get("candidate")
            if isinstance(selected, Mapping):
                study = await load_admitted_study(
                    db, str(selected.get("study_id") or "")
                )
                if study is not None:
                    public = project_visible_study(study)
                    candidates = [{
                        **dict(selected),
                        "game_id": study["study_id"],
                        "plan_id": study["plan"]["plan_id"],
                        "plan_fingerprint": study["plan"]["input_fingerprint"],
                        "chapters": public["chapters"],
                    }]
    if not candidates:
        return await _with_review_states(db, user_id, {
            "schema_version": SCHEMA_VERSION,
            "enabled": True,
            "paused": False,
            "status": "empty",
            "prescription": None,
            "empty": {
                "headline": "I have not found the right game to teach from yet.",
                "body": (
                    "Your analyzed games stay below. I will choose one when "
                    "its lesson is fully verified."
                ),
                "primary_action": {
                    "label": "Play with Coach",
                    "href": "/play-with-coach",
                },
                "secondary_action": {
                    "label": "Import recent games",
                    "href": "/import",
                },
            },
        })

    chosen = candidates[0]
    seed = (
        f"{user_id}:{chosen['game_id']}:{chosen['plan_id']}:"
        f"{chosen['plan_fingerprint']}:{SELECTOR_VERSION}"
    )
    now = _now()
    document = {
        "prescription_id": (
            f"grp_{hashlib.sha256(seed.encode()).hexdigest()[:24]}"
        ),
        "user_id": user_id,
        "game_id": chosen["game_id"],
        "state": "recommended",
        "is_active": True,
        "selector_version": SELECTOR_VERSION,
        "plan_id": chosen["plan_id"],
        "plan_fingerprint": chosen["plan_fingerprint"],
        "focus_key": focus_key,
        "focus_match": bool(chosen["focus_match"]),
        "resume": {"move_index": -1, "updated_at": now},
        "recommended_at": now,
        "created_at": now,
        "updated_at": now,
    }
    if chosen.get("source_kind") == "community":
        document.update({
            "source_kind": "community",
            "study_id": chosen["study_id"],
            "focus_concept_id": focus_identity["concept_id"],
            "focus_quality_id": focus_identity["quality_id"],
            "rating_band": chosen["rating_band"],
            "interaction_progress": {},
        })
    try:
        await collection.insert_one(document)
    except DuplicateKeyError:
        document = await collection.find_one(
            {"user_id": user_id, "is_active": True}, {"_id": 0}
        )
        if not document:
            raise
        chosen = await _candidate_for_document(
            db, user_id, document, env=env
        )
        if chosen is None:
            raise ReviewPrescriptionError(
                "active prescription is no longer valid"
            )
    return await _with_review_states(
        db, user_id, _response(document, chosen)
    )


async def _owned_active(
    db, user_id: str, prescription_id: str
) -> Dict[str, Any]:
    document = await db[COLLECTION].find_one(
        {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "is_active": True,
        },
        {"_id": 0},
    )
    if not document:
        raise ReviewPrescriptionError(
            "active review recommendation not found"
        )
    return document


async def _require_access(
    db, user_id: str, env: Optional[Mapping[str, str]]
) -> None:
    access = await get_complete_coaching_access(db, user_id, env=env)
    if not access.enabled:
        raise ReviewPrescriptionError("game review coaching is not enabled")


async def start_prescription(
    db,
    user_id: str,
    prescription_id: str,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    await _require_access(db, user_id, env)
    document = await _owned_active(db, user_id, prescription_id)
    if document.get("state") not in ACTIVE_STATES:
        raise ReviewPrescriptionError(
            "review cannot be started from this state"
        )
    if (
        document.get("source_kind") == "community"
        and not await _community_operability_visible(db, user_id, env)
    ):
        raise ReviewPrescriptionError(
            "community study visibility is disabled"
        )
    now = _now()
    fields = {"state": "started", "updated_at": now}
    if not document.get("started_at"):
        fields["started_at"] = now
    await db[COLLECTION].update_one(
        {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "is_active": True,
        },
        {"$set": fields},
    )
    if document.get("source_kind") == "community":
        await record_phase8_reach_event(
            db,
            user_id,
            step="community_review_started",
            source_id=prescription_id,
            metadata={"study_id": str(document.get("study_id") or "")},
        )
    return await get_recommendation(db, user_id, env=env)


async def save_progress(
    db,
    user_id: str,
    prescription_id: str,
    move_index: int,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    await _require_access(db, user_id, env)
    if (
        isinstance(move_index, bool)
        or not isinstance(move_index, int)
        or move_index < -1
    ):
        raise ReviewPrescriptionError(
            "move_index must be an integer of -1 or greater"
        )
    document = await _owned_active(db, user_id, prescription_id)
    if document.get("state") != "started":
        raise ReviewPrescriptionError(
            "start the review before saving progress"
        )
    now = _now()
    await db[COLLECTION].update_one(
        {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "is_active": True,
        },
        {
            "$set": {
                "resume.move_index": move_index,
                "resume.updated_at": now,
                "updated_at": now,
            }
        },
    )
    return {
        "saved": True,
        "move_index": move_index,
        "updated_at": now.isoformat(),
    }


async def dismiss_prescription(
    db,
    user_id: str,
    prescription_id: str,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    await _require_access(db, user_id, env)
    existing = await db[COLLECTION].find_one(
        {"prescription_id": prescription_id, "user_id": user_id},
        {"_id": 0},
    )
    if existing and existing.get("state") == "dismissed":
        return await get_recommendation(db, user_id, env=env)
    await _owned_active(db, user_id, prescription_id)
    now = _now()
    await db[COLLECTION].update_one(
        {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "is_active": True,
        },
        {
            "$set": {
                "state": "dismissed",
                "is_active": False,
                "dismissed_at": now,
                "updated_at": now,
            }
        },
    )
    return await get_recommendation(db, user_id, env=env)


async def complete_prescription(
    db,
    user_id: str,
    prescription_id: str,
    *,
    game_id: str,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    await _require_access(db, user_id, env)
    existing = await db[COLLECTION].find_one(
        {"prescription_id": prescription_id, "user_id": user_id},
        {"_id": 0},
    )
    if (
        existing
        and existing.get("state") == "completed"
        and existing.get("game_id") == game_id
    ):
        next_review = await get_recommendation(db, user_id, env=env)
        if existing.get("source_kind") == "community":
            learning = existing.get("completion_learning")
            if not isinstance(learning, Mapping):
                raise ReviewPrescriptionError(
                    "completed community study is missing its learning receipt"
                )
            action = existing.get("completion_next_action")
            next_review = {
                **next_review,
                "next_action": dict(action) if isinstance(action, Mapping) else None,
                "learning": dict(learning),
            }
        return next_review
    document = await _owned_active(db, user_id, prescription_id)
    if document.get("game_id") != game_id:
        raise ReviewPrescriptionError(
            "prescription does not belong to this game"
        )
    if document.get("state") != "started":
        raise ReviewPrescriptionError(
            "review must be started before completion"
        )
    learning_receipt = None
    if document.get("source_kind") == "community":
        if not await _community_operability_visible(db, user_id, env):
            raise ReviewPrescriptionError(
                "community study visibility is disabled"
            )
        study = await load_admitted_study(
            db, str(document.get("study_id") or "")
        )
        if study is None:
            raise ReviewPrescriptionError("community study is no longer current")
        progress = document.get("interaction_progress") or {}
        for chapter in study["plan"]["chapters"]:
            key = hashlib.sha256(chapter["event_id"].encode()).hexdigest()[:20]
            state = progress.get(key) if isinstance(progress, Mapping) else None
            if not isinstance(state, Mapping) or not all(
                state.get(field) is True
                for field in ("predicted", "revealed", "watched", "replayed")
            ):
                raise ReviewPrescriptionError(
                    "finish each predict, watch and replay step before completion"
                )
    now = _now()
    if document.get("source_kind") == "community":
        from services.review_learning_adapter import (
            store_community_walkthrough_results,
        )

        learning_receipt = await store_community_walkthrough_results(
            db.learning_sessions,
            user_id=user_id,
            prescription_id=prescription_id,
            study=study,
            progress=progress,
            occurred_at=now,
        )
    completion_learning = (
        {
            "assisted_learning_recorded": True,
            "chapter_results": learning_receipt["chapter_results"],
            "real_game_application": "not_measured",
            "retention": "not_measured",
        }
        if learning_receipt is not None
        else None
    )
    completion_fields = {
        "state": "completed",
        "is_active": False,
        "completed_at": now,
        "updated_at": now,
    }
    if completion_learning is not None:
        completion_fields["completion_learning"] = completion_learning
    await db[COLLECTION].update_one(
        {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "is_active": True,
        },
        {
            "$set": completion_fields
        },
    )
    next_review = await get_recommendation(db, user_id, env=env)
    if learning_receipt is not None:
        await record_phase8_reach_event(
            db,
            user_id,
            step="community_review_completed",
            source_id=prescription_id,
            metadata={
                "study_id": str(document.get("study_id") or ""),
                "chapter_results": int(
                    learning_receipt.get("chapter_results") or 0
                ),
                "changes_transfer_verdict": False,
            },
        )
        next_prescription = next_review.get("prescription")
        next_action = None
        next_review_href = (
            _trusted_next_action_href(next_prescription.get("review_url"))
            if isinstance(next_prescription, Mapping)
            else None
        )
        if next_review_href:
            next_action = {
                "kind": "review",
                "label": "Review the next game with me",
                "href": next_review_href,
                "prescription_id": str(
                    next_prescription.get("prescription_id") or ""
                ),
            }
        else:
            empty = next_review.get("empty")
            primary = (
                empty.get("primary_action")
                if isinstance(empty, Mapping)
                else None
            )
            primary_href = (
                _trusted_next_action_href(primary.get("href"))
                if isinstance(primary, Mapping)
                else None
            )
            if primary_href:
                next_action = {
                    "kind": "coach_action",
                    "label": str(primary.get("label") or "Continue with me"),
                    "href": primary_href,
                }
        if next_action is not None:
            await db[COLLECTION].update_one(
                {
                    "prescription_id": prescription_id,
                    "user_id": user_id,
                    "state": "completed",
                },
                {
                    "$set": {
                        "completion_next_action": next_action,
                        "updated_at": _now(),
                    }
                },
            )
            await record_phase8_reach_event(
                db,
                user_id,
                step="community_review_next_action_linked",
                source_id=prescription_id,
                metadata={
                    "next_action_kind": next_action["kind"],
                    "next_prescription_id": next_action.get(
                        "prescription_id", ""
                    ),
                },
            )
        next_review = {
            **next_review,
            "next_action": next_action,
            "learning": completion_learning,
        }
    return next_review


async def get_community_study(
    db,
    user_id: str,
    prescription_id: str,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    await _require_access(db, user_id, env)
    document = await _owned_active(db, user_id, prescription_id)
    if document.get("source_kind") != "community":
        raise ReviewPrescriptionError("prescription is not a community study")
    if document.get("state") != "started":
        raise ReviewPrescriptionError("start the study before opening it")
    if not await _community_operability_visible(db, user_id, env):
        raise ReviewPrescriptionError("community study visibility is disabled")
    study = await load_admitted_study(
        db, str(document.get("study_id") or "")
    )
    if study is None:
        raise ReviewPrescriptionError("community study is no longer current")
    public = project_visible_study(study)
    progress = document.get("interaction_progress") or {}
    visible_progress: Dict[str, Dict[str, bool]] = {}
    restored_hints: Dict[str, Dict[str, Any]] = {}
    restored_reveals: Dict[str, Dict[str, Any]] = {}
    chapter_ids = {
        chapter["event_id"] for chapter in study["plan"]["chapters"]
    }
    for item in progress.values() if isinstance(progress, Mapping) else ():
        if not isinstance(item, Mapping):
            continue
        event_id = str(item.get("event_id") or "")
        if event_id not in chapter_ids:
            continue
        visible_progress[event_id] = {
            name: item.get(name) is True
            for name in ("hinted", "predicted", "revealed", "watched", "replayed")
        }
        if item.get("hinted") is True:
            restored_hints[event_id] = reveal_study_chapter(
                study,
                event_id=event_id,
                include_hint=True,
            )
        if item.get("revealed") is True:
            restored_reveals[event_id] = reveal_study_chapter(
                study,
                event_id=event_id,
                selected_option_id=str(item.get("selected_option_id") or ""),
            )
    public["progress"] = visible_progress
    public["hints"] = restored_hints
    public["reveals"] = restored_reveals
    public["prescription_id"] = prescription_id
    return public


async def record_community_chapter_action(
    db,
    user_id: str,
    prescription_id: str,
    *,
    event_id: str,
    action: str,
    selected_option_id: Optional[str] = None,
    played_move_uci: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Grade and record one bounded interaction on the server."""
    if action not in {"hint", "predict", "watch", "replay"}:
        raise ReviewPrescriptionError("unknown community study action")
    await _require_access(db, user_id, env)
    document = await _owned_active(db, user_id, prescription_id)
    if document.get("source_kind") != "community" or document.get("state") != "started":
        raise ReviewPrescriptionError("community study is not active")
    if not await _community_operability_visible(db, user_id, env):
        raise ReviewPrescriptionError("community study visibility is disabled")
    study = await load_admitted_study(
        db, str(document.get("study_id") or "")
    )
    if study is None:
        raise ReviewPrescriptionError("community study is no longer current")
    if event_id not in {
        chapter["event_id"] for chapter in study["plan"]["chapters"]
    }:
        raise ReviewPrescriptionError("chapter does not belong to this study")

    progress = document.get("interaction_progress") or {}
    key = hashlib.sha256(event_id.encode()).hexdigest()[:20]
    current = dict(progress.get(key) or {}) if isinstance(progress, Mapping) else {}
    now = _now()
    response: Dict[str, Any] = {"event_id": event_id, "action": action}
    if action == "hint":
        response.update(reveal_study_chapter(
            study, event_id=event_id, include_hint=True
        ))
        current["hinted"] = True
        current.setdefault("hinted_at", now)
    elif action == "predict":
        first_prediction = current.get("predicted") is not True
        answer = (
            selected_option_id
            if first_prediction
            else current.get("selected_option_id")
        )
        try:
            response.update(reveal_study_chapter(
                study,
                event_id=event_id,
                selected_option_id=answer,
            ))
        except CommunityGameStudyError as exc:
            raise ReviewPrescriptionError(str(exc)) from exc
        if first_prediction:
            current.update({
                "predicted": True,
                "revealed": True,
                "correct": bool(response["correct"]),
                "selected_option_id": str(answer),
            })
            current.setdefault("predicted_at", now)
    elif action == "watch":
        if current.get("revealed") is not True:
            raise ReviewPrescriptionError("predict before watching the line")
        current["watched"] = True
        current.setdefault("watched_at", now)
    else:
        if current.get("watched") is not True:
            raise ReviewPrescriptionError("watch the line before replaying it")
        try:
            replay_result = verify_guided_replay_move(
                study,
                event_id=event_id,
                played_move_uci=str(played_move_uci or ""),
            )
        except CommunityGameStudyError as exc:
            raise ReviewPrescriptionError(str(exc)) from exc
        current["replayed"] = True
        current["replayed_move_uci"] = replay_result["played_move_uci"]
        current.setdefault("replayed_at", now)
        response.update(replay_result)
    current["event_id"] = event_id
    await db[COLLECTION].update_one(
        {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "is_active": True,
            "state": "started",
        },
        {"$set": {f"interaction_progress.{key}": current, "updated_at": now}},
    )
    reach_source_id = f"{prescription_id}:{event_id}"
    reach_steps = {
        "hint": ("community_review_hint_used",),
        "predict": (
            "community_review_predicted",
            "community_review_revealed",
        ),
        "watch": ("community_review_line_watched",),
        "replay": ("community_review_key_move_replayed",),
    }
    steps_to_record = reach_steps[action]
    if action == "predict" and not first_prediction:
        steps_to_record = ()
    for reach_step in steps_to_record:
        await record_phase8_reach_event(
            db,
            user_id,
            step=reach_step,
            source_id=reach_source_id,
            metadata={
                "prescription_id": prescription_id,
                "study_id": str(document.get("study_id") or ""),
                "event_id": event_id,
            },
        )
    response["progress"] = {
        name: current.get(name) is True
        for name in ("hinted", "predicted", "revealed", "watched", "replayed")
    }
    return response


async def follow_community_next_action(
    db,
    user_id: str,
    prescription_id: str,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Record and return the server-authored action after a completed study."""
    await _require_access(db, user_id, env)
    document = await db[COLLECTION].find_one(
        {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "source_kind": "community",
            "state": "completed",
        },
        {"_id": 0, "completion_next_action": 1},
    )
    action = (
        document.get("completion_next_action")
        if isinstance(document, Mapping)
        else None
    )
    href = (
        _trusted_next_action_href(action.get("href"))
        if isinstance(action, Mapping)
        else None
    )
    if not href:
        raise ReviewPrescriptionError("no linked next action is available")
    await record_phase8_reach_event(
        db,
        user_id,
        step="community_review_next_action_followed",
        source_id=prescription_id,
        metadata={"next_action_kind": str(action.get("kind") or "")},
    )
    return {
        "label": str(action.get("label") or "Continue with me"),
        "href": href,
        "kind": str(action.get("kind") or "coach_action"),
    }


__all__ = [
    "COLLECTION",
    "SCHEMA_VERSION",
    "SELECTOR_VERSION",
    "ReviewPrescriptionError",
    "candidate_from_projection",
    "complete_prescription",
    "dismiss_prescription",
    "ensure_review_prescription_indexes",
    "follow_community_next_action",
    "get_recommendation",
    "get_community_study",
    "public_prescription",
    "rank_candidates",
    "record_community_chapter_action",
    "save_progress",
    "start_prescription",
]
