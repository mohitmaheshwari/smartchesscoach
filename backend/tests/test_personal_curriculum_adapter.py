import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.personal_curriculum import (
    CurriculumOutcome,
    _repair_candidate,
    build_player_curriculum,
    personal_curriculum_eligible,
)


NOW = datetime(2026, 8, 29, 9, 0, tzinfo=timezone.utc)
ENABLED = {
    "PERSONAL_CURRICULUM_ENABLED": "true",
    "PERSONAL_CURRICULUM_ROLES": "admin,super_admin",
}


class FakeCollection:
    def __init__(self, docs=None, count=0):
        self.docs = list(docs or [])
        self.count = count

    async def find_one(self, query, projection=None, **kwargs):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None

    async def count_documents(self, query):
        return self.count

    async def insert_one(self, doc):
        self.docs.append(doc)

    async def update_one(self, query, update, upsert=False):
        doc = await self.find_one(query)
        if doc is None:
            if not upsert:
                return
            doc = dict(query)
            self.docs.append(doc)
        for path, value in (update.get("$set") or {}).items():
            cursor = doc
            parts = path.split(".")
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = value


class FakeDB:
    def __init__(self, *, analyzed_games, role="admin"):
        self.users = FakeCollection([{"user_id": "u1", "role": role}])
        self.games = FakeCollection(count=analyzed_games)
        self.coach_memory = FakeCollection()
        self.player_profiles = FakeCollection()
        self.chess_understanding = FakeCollection()
        self.user_opening_progress = FakeCollection()
        self.learning_sessions = FakeCollection()


def test_rollout_requires_both_flag_and_allowed_role():
    assert personal_curriculum_eligible("admin", ENABLED) is True
    assert personal_curriculum_eligible("user", ENABLED) is False
    assert personal_curriculum_eligible("admin", {}) is False


def test_curriculum_route_is_authenticated_and_uses_the_canonical_adapter():
    route_source = (
        Path(__file__).parents[1] / "routes" / "coach.py"
    ).read_text(encoding="utf-8")

    assert '@router.get("/personal-curriculum")' in route_source
    assert "user: User = Depends(get_current_user)" in route_source
    assert "return await build_player_curriculum(db, user.user_id)" in route_source


def test_less_than_five_games_produces_honest_observe_plan():
    db = FakeDB(analyzed_games=3)

    result = asyncio.run(
        build_player_curriculum(
            db,
            "u1",
            generated_at=NOW,
            env=ENABLED,
        )
    )

    assert result["enabled"] is True
    assert result["decision"]["primary"]["outcome"] == "observe"
    assert result["decision"]["primary"]["destination"]["href"] == "/play-with-coach"
    stored = db.coach_memory.docs[0]["learning"]["active_curriculum"]
    assert set(stored) == {
        "decision_id",
        "outcome",
        "content_kind",
        "content_id",
        "selected_at",
        "evidence_watermark",
        "resume_destination",
    }
    assert "title" not in stored
    assert "evidence" not in stored


def test_expand_uses_canonical_knowledge_pick_and_endgame_route(monkeypatch):
    db = FakeDB(analyzed_games=7)

    async def no_focus(_db, _user_id):
        return None

    async def knowledge_pick(_db, _user_id):
        return {
            "_src": "engine2",
            "skill_id": "endgame_rule_of_square",
            "label": "Rule of the Square",
            "stats": {"seen": 1, "correct": 0, "failed": 1},
            "e2_kind": "endgame",
            "kind": "endgame",
            "content_ref": "rule_of_square",
        }

    async def rating_band(_db, _user_id):
        return "beginner_high"

    import services.focus_bridge as focus_bridge
    import services.today_composer as today_composer

    monkeypatch.setattr(focus_bridge, "get_active_focus_bundle", no_focus)
    monkeypatch.setattr(today_composer, "pick_knowledge_focus", knowledge_pick)
    monkeypatch.setattr(today_composer, "_detect_band", rating_band)

    result = asyncio.run(
        build_player_curriculum(
            db,
            "u1",
            generated_at=NOW,
            env=ENABLED,
        )
    )

    primary = result["decision"]["primary"]
    assert primary["outcome"] == "expand"
    assert primary["title"] == "Rule of the Square"
    assert primary["destination"]["href"] == "/endgames/king_and_pawn/square_rule"
    assert primary["destination"]["lesson_id"] == "king_and_pawn/square_rule"


def test_repair_requires_named_topic_to_recur_three_times():
    focus = {
        "focus_id": "f1",
        "topic_key": "piece_safety",
        "topic_label": "Piece safety (53% critical)",
        "coaching_narrative": (
            "797 events across 624 games are tactical-sequence losses."
        ),
        "detector_quality_id": "gap:piece_safety:simple_hang",
        "baseline_metric": {"occurrence_count": 2},
    }
    assert _repair_candidate(focus) is None

    focus["baseline_metric"]["occurrence_count"] = 3
    candidate = _repair_candidate(focus)
    assert candidate is not None
    assert candidate.outcome == CurriculumOutcome.REPAIR
    assert candidate.title == "Piece safety"
    assert "What changed after their last move?" in candidate.reason
    assert "%" not in candidate.title
    assert "797" not in candidate.reason
    assert "tactical-sequence" not in candidate.reason


def test_approved_personalized_flag_routes_supported_lesson_through_workspace(
    monkeypatch,
):
    db = FakeDB(analyzed_games=7)
    enabled = {
        **ENABLED,
        "PERSONALIZED_TEACHING_ENABLED": "true",
    }

    async def focus(_db, _user_id):
        return {
            "focus_id": "f1",
            "topic_key": "piece_safety",
            "baseline_metric": {"occurrence_count": 3},
        }

    async def no_knowledge(_db, _user_id):
        return None

    async def no_active_focus(_db, _user_id):
        return None

    import services.focus_bridge as focus_bridge
    import services.today_composer as today_composer

    monkeypatch.setattr(focus_bridge, "get_active_focus_bundle", focus)
    monkeypatch.setattr(today_composer, "pick_knowledge_focus", no_knowledge)

    result = asyncio.run(build_player_curriculum(
        db,
        "u1",
        generated_at=NOW,
        env=enabled,
    ))

    primary = result["decision"]["primary"]
    assert primary["destination"]["href"] == (
        "/training?personalized=1&kind=concept&lesson=piece_safety"
    )
    assert result["personalized_teaching"]["enabled"] is True
    assert result["personalized_teaching"]["profile"]["mode"] in {
        "personalized",
        "diagnostic_required",
    }


def test_verified_trap_family_routes_through_personalized_workspace(monkeypatch):
    db = FakeDB(analyzed_games=7)
    enabled = {
        **ENABLED,
        "PERSONALIZED_TEACHING_ENABLED": "true",
    }

    async def no_focus(_db, _user_id):
        return None

    async def knowledge_pick(_db, _user_id):
        return {
            "_src": "engine2",
            "skill_id": "trap_set_italian",
            "label": "Italian Game traps",
            "stats": {"seen": 0, "correct": 0, "failed": 0},
            "e2_kind": "trap_set",
            "kind": "trap_set",
            "content_ref": "italian-game",
        }

    async def rating_band(_db, _user_id):
        return "intermediate"

    import services.focus_bridge as focus_bridge
    import services.today_composer as today_composer

    monkeypatch.setattr(focus_bridge, "get_active_focus_bundle", no_focus)
    monkeypatch.setattr(today_composer, "pick_knowledge_focus", knowledge_pick)
    monkeypatch.setattr(today_composer, "_detect_band", rating_band)

    result = asyncio.run(build_player_curriculum(
        db,
        "u1",
        generated_at=NOW,
        env=enabled,
    ))

    destination = result["decision"]["primary"]["destination"]
    assert destination["href"] == (
        "/training?personalized=1&kind=trap_set&lesson=italian-game"
    )
    assert destination["lesson_kind"] == "trap_set"
    assert destination["lesson_id"] == "italian-game"


def test_curriculum_reuses_highest_state_proved_by_the_exact_lesson(monkeypatch):
    db = FakeDB(analyzed_games=7)
    db.learning_sessions.docs.append({
        "user_id": "u1",
        "lesson_type": "personalized_curriculum",
        "content_kind": "concept",
        "content_id": "piece_safety",
        "highest_earned_state": "can_do_alone",
        "updated_at": NOW,
    })
    enabled = {**ENABLED, "PERSONALIZED_TEACHING_ENABLED": "true"}

    async def focus(_db, _user_id):
        return {
            "focus_id": "f1",
            "topic_key": "piece_safety",
            "baseline_metric": {"occurrence_count": 3},
        }

    async def no_knowledge(_db, _user_id):
        return None

    import services.focus_bridge as focus_bridge
    import services.today_composer as today_composer

    monkeypatch.setattr(focus_bridge, "get_active_focus_bundle", focus)
    monkeypatch.setattr(today_composer, "pick_knowledge_focus", no_knowledge)

    result = asyncio.run(build_player_curriculum(
        db,
        "u1",
        generated_at=NOW,
        env=enabled,
    ))

    assert result["decision"]["primary"]["state"] == "can_do_alone"


def test_review_becomes_due_after_three_more_analyzed_games(monkeypatch):
    db = FakeDB(analyzed_games=7)
    db.learning_sessions.docs.append({
        "user_id": "u1",
        "lesson_type": "personalized_curriculum",
        "status": "completed",
        "content_kind": "concept",
        "content_id": "piece_safety",
        "skill_id": "piece_safety",
        "highest_earned_state": "can_do_alone",
        "analyzed_games_at_completion": 4,
        "completed_at": NOW - timedelta(days=2),
        "descriptor": {
            "kind": "concept",
            "id": "piece_safety",
            "title": "Piece safety",
            "canonical_source": "backend/data/theory/tactical_patterns.json",
        },
    })
    enabled = {**ENABLED, "PERSONALIZED_TEACHING_ENABLED": "true"}

    async def focus(_db, _user_id):
        return {
            "focus_id": "f1",
            "topic_key": "piece_safety",
            "baseline_metric": {"occurrence_count": 3},
        }

    async def no_knowledge(_db, _user_id):
        return None

    import services.focus_bridge as focus_bridge
    import services.today_composer as today_composer
    monkeypatch.setattr(focus_bridge, "get_active_focus_bundle", focus)
    monkeypatch.setattr(today_composer, "pick_knowledge_focus", no_knowledge)

    result = asyncio.run(build_player_curriculum(
        db, "u1", generated_at=NOW, env=enabled
    ))

    primary = result["decision"]["primary"]
    assert primary["outcome"] == "review"
    assert primary["state"] == "can_do_alone"
    assert "review=1" in primary["destination"]["href"]
    assert "3 analyzed games" in primary["reason"]


def test_calendar_backstop_is_honest_about_missing_new_game_evidence(monkeypatch):
    db = FakeDB(analyzed_games=7)
    db.learning_sessions.docs.append({
        "user_id": "u1",
        "lesson_type": "personalized_curriculum",
        "status": "completed",
        "content_kind": "concept",
        "content_id": "piece_safety",
        "skill_id": "piece_safety",
        "highest_earned_state": "can_do_with_help",
        "analyzed_games_at_completion": 7,
        "completed_at": NOW - timedelta(days=22),
        "descriptor": {
            "kind": "concept",
            "id": "piece_safety",
            "title": "Piece safety",
            "canonical_source": "backend/data/theory/tactical_patterns.json",
        },
    })
    enabled = {**ENABLED, "PERSONALIZED_TEACHING_ENABLED": "true"}

    async def focus(_db, _user_id):
        return {
            "focus_id": "f1",
            "topic_key": "piece_safety",
            "baseline_metric": {"occurrence_count": 3},
        }

    async def no_knowledge(_db, _user_id):
        return None

    import services.focus_bridge as focus_bridge
    import services.today_composer as today_composer
    monkeypatch.setattr(focus_bridge, "get_active_focus_bundle", focus)
    monkeypatch.setattr(today_composer, "pick_knowledge_focus", no_knowledge)

    result = asyncio.run(build_player_curriculum(
        db, "u1", generated_at=NOW, env=enabled
    ))

    primary = result["decision"]["primary"]
    assert primary["outcome"] == "review"
    assert "check-in, not proof from new games" in primary["reason"]
    assert primary["evidence"] == (
        "No new game evidence is being claimed for this check-in."
    )
