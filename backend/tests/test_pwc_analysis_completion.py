import asyncio
from datetime import datetime, timezone

import config
from routes import coach_play
from services import analysis_completion_evidence
from services import opening_mastery_tracker, pattern_decay_service


HANG_FEN = "4k3/8/4p2p/8/8/5N2/8/4K3 w - - 0 1"


def _matches(row, query):
    return all(row.get(key) == value for key, value in query.items())


class _Write:
    upserted_id = None


class _Collection:
    def __init__(self, rows=()):
        self.rows = [dict(row) for row in rows]
        self.calls = []

    async def find_one(self, query, projection=None):
        for row in self.rows:
            if _matches(row, query):
                return dict(row)
        return None

    async def update_one(self, query, update, upsert=False):
        self.calls.append((query, update, upsert))
        if isinstance(update, list):
            return _Write()
        row = next((item for item in self.rows if _matches(item, query)), None)
        if row is None and upsert:
            row = {
                key: value
                for key, value in query.items()
                if not isinstance(value, dict)
            }
            row.update(update.get("$setOnInsert") or {})
            self.rows.append(row)
        if row is not None:
            row.update(update.get("$set") or {})
        return _Write()


class _Db:
    def __init__(self, session):
        self.coach_sessions = _Collection((session,))
        self.games = _Collection()
        self.game_analyses = _Collection()
        self.move_observations = _Collection()
        self.learning_sessions = _Collection()


def _session():
    moves = (
        ("e4", "e2e4", "player"),
        ("e5", "e7e5", "coach"),
        ("Nf3", "g1f3", "player"),
        ("Nc6", "b8c6", "coach"),
    )
    return {
        "session_id": "session-1234567890",
        "user_id": "user-1",
        "user_color": "white",
        "status": "completed",
        "result": "draw",
        "game_mode": "coach",
        "evidence_mode": "practice_assisted",
        "created_at": datetime(2026, 9, 9, tzinfo=timezone.utc),
        "move_history": [
            {"move": san, "uci": uci, "by": side}
            for san, uci, side in moves
        ],
        "coaching_context": {
            "primary_focus": {
                "focus_id": "focus-1",
                "instruction_id": "instruction-1",
                "detector_quality_id": (
                    "gap:piece_safety:destination_safety_exact"
                ),
            },
        },
    }


def _evaluations(*_args):
    return (
        [{
            "fen_before": HANG_FEN,
            "move_uci": "f3g5",
            "move_number": 1,
            "move": "Ng5",
            "cp_loss": 200,
            "evaluation": "mistake",
            "cognitive_gap": "piece_safety",
            "is_user_move": True,
            "is_opponent_move": False,
        }],
        80.0,
        0,
        1,
    )


def test_enriched_pwc_moves_mark_opponent_plies_explicitly():
    history = [
        {
            "by": "player",
            "move": "e4",
            "uci": "e2e4",
            "fen_before": (
                "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/"
                "RNBQKBNR w KQkq - 0 1"
            ),
            "fen_after": (
                "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/"
                "RNBQKBNR b KQkq - 0 1"
            ),
            "eval_before": 0,
            "eval_after": 0,
        },
        {
            "by": "coach",
            "move": "e5",
            "uci": "e7e5",
            "fen_before": (
                "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/"
                "RNBQKBNR b KQkq - 0 1"
            ),
            "fen_after": (
                "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/"
                "RNBQKBNR w KQkq - 0 2"
            ),
        },
    ]

    evaluations, *_ = coach_play._build_enriched_coach_move_evaluations(
        history, "white"
    )

    assert [
        (row["is_user_move"], row["is_opponent_move"])
        for row in evaluations
    ] == [(True, False), (False, True)]


def test_completed_pwc_game_reconciles_analysis_observations_and_evidence_once(
    monkeypatch,
):
    db = _Db(_session())
    monkeypatch.setattr(config, "PWC_GAP_ENRICHMENT", True)
    monkeypatch.setattr(
        coach_play,
        "_build_enriched_coach_move_evaluations",
        _evaluations,
    )
    monkeypatch.setattr(
        analysis_completion_evidence,
        "complete_coaching_system_enabled",
        lambda: True,
    )

    async def _no_decay(*_args, **_kwargs):
        return {}

    async def _no_opening(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        pattern_decay_service,
        "refresh_user_pattern_decay",
        _no_decay,
    )
    monkeypatch.setattr(
        opening_mastery_tracker,
        "update_mastery_from_analyzed_game",
        _no_opening,
    )

    asyncio.run(
        coach_play._promote_session_to_game(
            db, "session-1234567890", "user-1"
        )
    )
    asyncio.run(
        coach_play._promote_session_to_game(
            db, "session-1234567890", "user-1"
        )
    )

    assert len(db.games.rows) == 1
    assert len(db.game_analyses.rows) == 1
    assert len(db.move_observations.rows) == 1
    stored_session = db.coach_sessions.rows[0]
    assert stored_session["analysis_evidence_status"] == "completed"
    assert stored_session["pic_evidence"]["evidence_mode"] == (
        "practice_assisted"
    )
    assert stored_session["pic_evidence"]["assisted"] is True
    assert stored_session["pic_evidence"]["resolution_eligible"] is False
