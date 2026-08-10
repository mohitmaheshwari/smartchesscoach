"""
Unit tests for Sprint 2 — One Surviving Instruction
(docs/one_surviving_instruction_scope.md).

Covers the pieces the scope's own §5/§7 named as ship requirements:
  - Gate-effectiveness test (a real user must be byte-identical with the
    flag ON vs OFF -- proving the gate actually gates, not just that
    it's documented to).
  - Rebuild-path preservation (the exact regression Correction #3
    identified: rebuild_scoreboard_from_history used to silently drop
    any field not in its fixed 7-key dict).
  - Subtype-aware matching for simple_hang (the one piece_safety subtype
    genuinely board-verifiable from a single move, per the real-data
    decision to ship it despite narrow coverage).

Uses a minimal hand-rolled fake DB (no live MongoDB) so these run fast
and hermetically in CI -- get_active_focus_bundle only ever calls two
find_one()s, both easy to fake directly.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.focus_bridge import get_active_focus_bundle  # noqa: E402
from services.mission_scoreboard import (  # noqa: E402
    is_focus_moment,
    rebuild_scoreboard_from_history,
)


class _FakeCollection:
    def __init__(self, doc):
        self._doc = doc

    async def find_one(self, query, projection=None):
        return dict(self._doc) if self._doc is not None else None


class _FakeDB:
    """Only implements what get_active_focus_bundle actually touches:
    db[COLLECTION] (subscript access) and db.users (attribute access)."""

    def __init__(self, focus_doc, user_doc):
        self._collections = {"user_active_focus": _FakeCollection(focus_doc)}
        self.users = _FakeCollection(user_doc)

    def __getitem__(self, name):
        return self._collections[name]


REAL_FOCUS_DOC = {
    "user_id": "user_real_123",
    "type": "weakness",
    "status": "active",
    "topic_key": "piece_safety",
    "coaching_label": "Piece Safety",
    "coaching_narrative": "Piece safety is your top pattern.",
    "subtype_histogram": {"simple_hang": {"count": 10, "dominant_severity": "critical"}},
    "started_at": "2026-08-01T00:00:00+00:00",
    "locked_until": "2026-08-15T00:00:00+00:00",
    "moments_page_topic": "piece_safety",
    "runners_up": [],
    "rating_band": "intermediate",
    "instruction_id": "inst_abc123",
    "instruction_text": "Before every move, ask: can this piece be taken?",
    "instruction_version": 1,
}


@pytest.fixture(autouse=True)
def _clean_flag_env(monkeypatch):
    monkeypatch.delenv("PWC_SURVIVING_INSTRUCTION_ENABLED", raising=False)
    yield


class TestGateEffectiveness:
    """The scope's own required ship-blocking test (§5, §7)."""

    @pytest.mark.asyncio
    async def test_real_user_flag_off_gets_no_instruction_fields(self, monkeypatch):
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "false")
        db = _FakeDB(REAL_FOCUS_DOC, {"role": "user"})
        bundle = await get_active_focus_bundle(db, "user_real_123")
        assert bundle["instruction_id"] is None
        assert bundle["instruction_text"] is None
        assert bundle["instruction_version"] is None

    @pytest.mark.asyncio
    async def test_real_user_flag_on_still_gets_no_instruction_fields(self, monkeypatch):
        # THE gate-effectiveness test: flag ON must not matter for a real user.
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
        db = _FakeDB(REAL_FOCUS_DOC, {"role": "user"})
        bundle = await get_active_focus_bundle(db, "user_real_123")
        assert bundle["instruction_id"] is None
        assert bundle["instruction_text"] is None
        assert bundle["instruction_version"] is None

    @pytest.mark.asyncio
    async def test_real_user_byte_identical_flag_on_vs_off(self, monkeypatch):
        """The literal claim from the scope: flag ON == flag OFF for a
        real user, not just 'both happen to be None' by coincidence --
        the ENTIRE bundle must match, proving nothing else leaks."""
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "false")
        db_off = _FakeDB(REAL_FOCUS_DOC, {"role": "user"})
        bundle_off = await get_active_focus_bundle(db_off, "user_real_123")

        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
        db_on = _FakeDB(REAL_FOCUS_DOC, {"role": "user"})
        bundle_on = await get_active_focus_bundle(db_on, "user_real_123")

        assert bundle_off == bundle_on

    @pytest.mark.asyncio
    async def test_admin_role_flag_on_gets_real_instruction_fields(self, monkeypatch):
        # Confirms the gate actually distinguishes eligible users --
        # otherwise the "always None" tests above would pass vacuously
        # even if the gate were simply broken/always-off.
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
        db = _FakeDB(REAL_FOCUS_DOC, {"role": "admin"})
        bundle = await get_active_focus_bundle(db, "user_admin_1")
        assert bundle["instruction_id"] == "inst_abc123"
        assert bundle["instruction_text"] == "Before every move, ask: can this piece be taken?"
        assert bundle["instruction_version"] == 1

    @pytest.mark.asyncio
    async def test_super_admin_role_eligible(self, monkeypatch):
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
        db = _FakeDB(REAL_FOCUS_DOC, {"role": "super_admin"})
        bundle = await get_active_focus_bundle(db, "user_super_1")
        assert bundle["instruction_id"] == "inst_abc123"

    @pytest.mark.asyncio
    async def test_admin_role_flag_off_still_gated(self, monkeypatch):
        # Default-off must win even for an eligible role -- the flag is
        # the master switch, role alone isn't enough.
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "false")
        db = _FakeDB(REAL_FOCUS_DOC, {"role": "admin"})
        bundle = await get_active_focus_bundle(db, "user_admin_1")
        assert bundle["instruction_id"] is None

    @pytest.mark.asyncio
    async def test_missing_user_doc_defaults_to_ineligible(self, monkeypatch):
        # No users doc found -- must fail closed (ineligible), not open.
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
        db = _FakeDB(REAL_FOCUS_DOC, None)
        bundle = await get_active_focus_bundle(db, "user_unknown")
        assert bundle["instruction_id"] is None

    @pytest.mark.asyncio
    async def test_non_instruction_fields_unaffected_by_gate(self, monkeypatch):
        # The gate must be scoped to ONLY the 3 instruction fields --
        # topic_key/coaching_narrative/etc. must reach everyone regardless.
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "false")
        db = _FakeDB(REAL_FOCUS_DOC, {"role": "user"})
        bundle = await get_active_focus_bundle(db, "user_real_123")
        assert bundle["topic_key"] == "piece_safety"
        assert bundle["coaching_narrative"] == "Piece safety is your top pattern."


class TestRebuildPathPreservation:
    """The exact regression Correction #3 identified."""

    def test_instruction_fields_survive_rebuild_with_no_moves(self):
        base = {
            "focus_topic": "piece_safety",
            "focus_subtype": "simple_hang",
            "focus_label": "Piece Safety",
            "instruction_id": "inst_xyz",
            "instruction_text": "Before every move, ask: can this piece be taken?",
            "instruction_version": 1,
        }
        rebuilt = rebuild_scoreboard_from_history(base, [], "white")
        assert rebuilt["instruction_id"] == "inst_xyz"
        assert rebuilt["instruction_text"] == "Before every move, ask: can this piece be taken?"
        assert rebuilt["instruction_version"] == 1

    def test_instruction_fields_survive_rebuild_with_real_moves(self):
        base = {
            "focus_topic": "piece_safety",
            "focus_subtype": "simple_hang",
            "focus_label": "Piece Safety",
            "instruction_id": "inst_xyz",
            "instruction_text": "Before every move, ask: can this piece be taken?",
            "instruction_version": 1,
        }
        move_history = [
            {"by": "player", "move": "e4", "uci": "e2e4",
             "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
             "eval_before": 0.2, "eval_after": 0.3},
        ]
        rebuilt = rebuild_scoreboard_from_history(base, move_history, "white")
        assert rebuilt["instruction_id"] == "inst_xyz"

    def test_missing_instruction_fields_on_base_stay_none_not_crash(self):
        # Legacy/pre-Sprint-2 scoreboard -- no instruction_* keys at all.
        base = {"focus_topic": "king_safety", "focus_subtype": None, "focus_label": "King Safety"}
        rebuilt = rebuild_scoreboard_from_history(base, [], "white")
        assert rebuilt["instruction_id"] is None
        assert rebuilt["instruction_text"] is None
        assert rebuilt["instruction_version"] is None

    def test_none_base_scoreboard_returns_none(self):
        assert rebuild_scoreboard_from_history(None, [], "white") is None

    def test_no_focus_topic_returns_base_unchanged(self):
        base = {"focus_topic": None}
        assert rebuild_scoreboard_from_history(base, [], "white") == base


class TestSubtypeAwareMatching:
    """simple_hang -- the one board-verifiable-from-a-single-move subtype,
    per the real-distribution decision to ship it despite narrow coverage."""

    # A real hung queen: white queen on d1 can be taken by a black rook on d8
    # with nothing defending d1 -- Qd1-d5 walks it into an undefended attack.
    HUNG_QUEEN_FEN = "3r1k2/8/8/8/8/8/8/3Q1K2 w - - 0 1"

    def test_simple_hang_subtype_matches_a_real_hang(self):
        # Qd1-d5: queen still on the d-file, black rook on d8 attacks it,
        # nothing defends d5 for white.
        matched = is_focus_moment(
            "piece_safety", self.HUNG_QUEEN_FEN, "d1d5", "white",
            focus_subtype="simple_hang",
        )
        assert matched is True

    def test_simple_hang_subtype_does_not_match_a_safe_move(self):
        # Kf1-e2: no piece-safety-relevant move at all.
        matched = is_focus_moment(
            "piece_safety", self.HUNG_QUEEN_FEN, "f1e2", "white",
            focus_subtype="simple_hang",
        )
        assert matched is False

    def test_no_subtype_keeps_topic_level_behavior_unchanged(self):
        # focus_subtype=None must behave exactly as before this change --
        # zero regression risk claim from the scope, directly tested.
        matched_with_none = is_focus_moment(
            "piece_safety", self.HUNG_QUEEN_FEN, "d1d5", "white",
            focus_subtype=None,
        )
        matched_no_kwarg = is_focus_moment(
            "piece_safety", self.HUNG_QUEEN_FEN, "d1d5", "white",
        )
        assert matched_with_none == matched_no_kwarg

    def test_other_subtype_values_fall_through_to_topic_level(self):
        # threat_ignored/tactical_seq_loss etc. deliberately NOT board-
        # verified in this call path (needs opponent-threat context this
        # path doesn't have) -- must behave like topic-only matching, not
        # silently return False for every move.
        matched = is_focus_moment(
            "piece_safety", self.HUNG_QUEEN_FEN, "d1d5", "white",
            focus_subtype="tactical_seq_loss",
        )
        assert matched is True  # topic-level: this IS piece-safety-relevant

    def test_king_safety_topic_unaffected_by_subtype_param(self):
        board_fen = "rnbqk2r/pppp1ppp/5n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        result_with_subtype = is_focus_moment(
            "king_safety", board_fen, "e1g1", "white", focus_subtype="simple_hang",
        )
        result_without = is_focus_moment("king_safety", board_fen, "e1g1", "white")
        assert result_with_subtype == result_without
