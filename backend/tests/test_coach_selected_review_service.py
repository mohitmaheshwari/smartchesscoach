from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import services.coach_selected_review_service as service


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _length):
        return [dict(row) for row in self.rows]


def _matches(row, query):
    for key, expected in query.items():
        actual = row.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$nin" in expected and actual in expected["$nin"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
        elif actual != expected:
            return False
    return True


class Collection:
    def __init__(self, rows=None):
        self.rows = [dict(row) for row in (rows or [])]
        self.indexes = []

    async def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    async def find_one(self, query, _projection=None, **_kwargs):
        return next((dict(row) for row in self.rows if _matches(row, query)), None)

    def find(self, query, _projection=None):
        return Cursor([row for row in self.rows if _matches(row, query)])

    async def insert_one(self, document):
        self.rows.append(dict(document))

    async def update_one(self, query, update):
        for row in self.rows:
            if not _matches(row, query):
                continue
            for key, value in update.get("$set", {}).items():
                if "." not in key:
                    row[key] = value
                    continue
                parent, child = key.split(".", 1)
                row.setdefault(parent, {})[child] = value
            return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


class Database:
    def __init__(self):
        self.collections = {
            service.COLLECTION: Collection(),
            "user_active_focus": Collection(),
        }

    def __getitem__(self, name):
        return self.collections.setdefault(name, Collection())

    def __getattr__(self, name):
        return self[name]


def _event(event_id="e1", concept_id="piece_safety.simple_hang"):
    return {
        "event_id": event_id,
        "move": {"number": 14, "san": "Rd2"},
        "concept": {
            "concept_id": concept_id,
            "content_ref": concept_id,
        },
        "evidence": {
            "quality_id": "gap:piece_safety:destination_safety_exact",
        },
        "teaching": {
            "headline": "The rook needed one more check.",
            "caption": "Rd2 left the rook where the queen could take it.",
            "principle": "Before moving, check the destination square.",
        },
    }


def _candidate(game_id, *, focus=False, chapters=1, recency=1):
    return {
        "game_id": game_id,
        "game": {
            "game_id": game_id,
            "opponent_name": "Opponent",
            "result": "0-1",
            "user_color": "white",
        },
        "plan_id": f"plan-{game_id}",
        "plan_fingerprint": f"fingerprint-{game_id}",
        "game_arc": "I found one moment worth studying in this game.",
        "takeaway": "Check the destination square.",
        "chapters": [
            {
                "event_id": f"{game_id}-{index}",
                "role": "missed_opportunity",
                "label": "What was possible here",
                "headline": "The rook needed one more check.",
                "explanation": "The queen could take it.",
                "principle": "Check the destination square.",
                "move_number": 14,
                "move_san": "Rd2",
            }
            for index in range(chapters)
        ],
        "focus_match": focus,
        "focus_key": "piece_safety" if focus else "",
        "authorized_chapter_count": chapters,
        "recency": recency,
    }


def test_formula_locks_focus_then_richness_then_recency():
    ranked = service.rank_candidates(
        [
            _candidate("new-rich", chapters=3, recency=300),
            _candidate("focus-old", focus=True, chapters=1, recency=1),
            _candidate("rich-old", chapters=2, recency=1),
            _candidate("rich-new", chapters=2, recency=2),
        ]
    )
    assert [item["game_id"] for item in ranked] == [
        "focus-old",
        "new-rich",
        "rich-new",
        "rich-old",
    ]


def test_candidate_uses_only_projected_event_text_and_fails_closed():
    event = _event()
    projection = {
        "game_teaching_plan": {
            "plan_id": "plan-1",
            "game_arc": "One real decision is worth revisiting.",
            "takeaway": "Check the destination square.",
            "chapters": [{"event_id": "e1", "role": "missed_opportunity"}],
        },
        "teachable_events": [event],
    }
    raw_plan = {"plan": {"input_fingerprint": "f" * 64}}
    candidate = service.candidate_from_projection(
        game={"game_id": "g1"},
        raw_plan=raw_plan,
        projection=projection,
        focus_key="piece_safety",
    )
    assert candidate["focus_match"] is True
    assert candidate["chapters"][0]["explanation"].startswith("Rd2")

    projection["game_teaching_plan"]["chapters"][0]["event_id"] = "missing"
    assert service.candidate_from_projection(
        game={"game_id": "g1"},
        raw_plan=raw_plan,
        projection=projection,
    ) is None


def test_focus_matching_does_not_confuse_king_safety_with_piece_safety():
    projection = {
        "game_teaching_plan": {
            "plan_id": "plan-1",
            "game_arc": "One moment.",
            "takeaway": "Check it.",
            "chapters": [{"event_id": "e1", "role": "knowledge_gap"}],
        },
        "teachable_events": [_event()],
    }
    candidate = service.candidate_from_projection(
        game={"game_id": "g1"},
        raw_plan={"plan": {"input_fingerprint": "f" * 64}},
        projection=projection,
        focus_key="king_safety",
    )
    assert candidate["focus_match"] is False
    assert candidate["chapters"][0]["label"] == "The idea to learn here"


def test_public_contract_excludes_identity_private_selector_evidence():
    candidate = _candidate("g1", focus=True)
    document = {
        "prescription_id": "p1",
        "user_id": "private-user",
        "game_id": "g1",
        "state": "started",
        "selector_version": service.SELECTOR_VERSION,
        "plan_fingerprint": "private-fingerprint",
        "focus_key": "piece_safety",
        "resume": {"move_index": 9},
    }
    public = service.public_prescription(document, candidate)
    assert public["review_url"].endswith("prescription=p1&resume=9")
    serialized = repr(public)
    assert "private-user" not in serialized
    assert "private-fingerprint" not in serialized
    assert service.SELECTOR_VERSION not in serialized


@pytest.mark.asyncio
async def test_lifecycle_is_stable_resumable_and_rotates(monkeypatch):
    db = Database()
    candidates = [_candidate("g1", focus=True), _candidate("g2")]

    async def access(*_args, **_kwargs):
        return SimpleNamespace(enabled=True, paused=False, reason="enabled")

    async def focus(*_args, **_kwargs):
        return "piece_safety"

    async def load(_db, _user, *, excluded_game_ids, **_kwargs):
        return [
            item for item in candidates if item["game_id"] not in excluded_game_ids
        ]

    async def candidate_for(_db, _user, document, **_kwargs):
        return next(
            (
                item
                for item in candidates
                if item["game_id"] == document.get("game_id")
                and item["plan_id"] == document.get("plan_id")
            ),
            None,
        )

    monkeypatch.setattr(service, "get_complete_coaching_access", access)
    monkeypatch.setattr(service, "_focus_key", focus)
    monkeypatch.setattr(service, "_load_candidates", load)
    monkeypatch.setattr(service, "_candidate_for_document", candidate_for)

    first = await service.get_recommendation(db, "u1")
    again = await service.get_recommendation(db, "u1")
    assert first["prescription"]["prescription_id"] == again["prescription"]["prescription_id"]
    assert first["prescription"]["game"]["game_id"] == "g1"

    prescription_id = first["prescription"]["prescription_id"]
    started = await service.start_prescription(db, "u1", prescription_id)
    assert started["status"] == "started"
    await service.save_progress(db, "u1", prescription_id, 17)
    resumed = await service.get_recommendation(db, "u1")
    assert resumed["prescription"]["resume"]["move_index"] == 17

    rotated = await service.dismiss_prescription(db, "u1", prescription_id)
    assert rotated["prescription"]["game"]["game_id"] == "g2"
    assert db[service.COLLECTION].rows[0]["state"] == "dismissed"
    retried_dismiss = await service.dismiss_prescription(
        db, "u1", prescription_id
    )
    assert retried_dismiss["prescription"]["game"]["game_id"] == "g2"

    second_id = rotated["prescription"]["prescription_id"]
    await service.start_prescription(db, "u1", second_id)
    completed = await service.complete_prescription(
        db, "u1", second_id, game_id="g2"
    )
    assert completed["status"] == "empty"
    assert db[service.COLLECTION].rows[1]["state"] == "completed"
    retried_complete = await service.complete_prescription(
        db, "u1", second_id, game_id="g2"
    )
    assert retried_complete["status"] == "empty"
    assert completed["review_states"] == retried_complete["review_states"]


@pytest.mark.asyncio
async def test_mutation_fails_when_rollout_is_pulled(monkeypatch):
    db = Database()
    db[service.COLLECTION].rows.append(
        {
            "prescription_id": "p1",
            "user_id": "u1",
            "game_id": "g1",
            "state": "recommended",
            "is_active": True,
        }
    )

    async def disabled(*_args, **_kwargs):
        return SimpleNamespace(enabled=False, paused=True, reason="paused")

    monkeypatch.setattr(service, "get_complete_coaching_access", disabled)
    with pytest.raises(service.ReviewPrescriptionError, match="not enabled"):
        await service.start_prescription(db, "u1", "p1")
    assert db[service.COLLECTION].rows[0]["state"] == "recommended"


def test_selector_has_no_chess_engine_detector_caption_or_llm_import():
    source = inspect.getsource(service).lower()
    forbidden = (
        "import chess",
        "stockfish",
        "caption_pipeline",
        "concept_detector",
        "llm_service",
    )
    assert all(item not in source for item in forbidden)


def test_routes_and_startup_keep_one_lifecycle_source_of_truth():
    backend = Path(__file__).parents[1]
    routes = (backend / "routes" / "training_advanced.py").read_text(
        encoding="utf-8"
    )
    server = (backend / "server.py").read_text(encoding="utf-8")
    for endpoint in (
        '@router.get("/game-review/recommendation")',
        '@router.post("/game-review/recommendation/{prescription_id}/start")',
        '@router.post("/game-review/recommendation/{prescription_id}/progress")',
        '@router.post("/game-review/recommendation/{prescription_id}/dismiss")',
    ):
        assert endpoint in routes
    assert "complete_prescription(" in routes
    assert "ensure_review_prescription_indexes(db)" in server
