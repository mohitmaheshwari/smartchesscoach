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
    build_instruction_verdict,
    is_focus_moment,
    rebuild_scoreboard_from_history,
)
from services.session_greeting_service import build_session_greeting  # noqa: E402


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
    "detector_quality_id": "gap:piece_safety:simple_hang",
    "instruction_id": "inst_abc123",
    "instruction_text": "Before every move, ask: can this piece be taken?",
    "instruction_version": 1,
}


@pytest.fixture(autouse=True)
def _clean_flag_env(monkeypatch):
    monkeypatch.delenv("PWC_SURVIVING_INSTRUCTION_ENABLED", raising=False)
    # Exercise the rollout contract with a synthetic promoted detector while
    # production simple_hang remains Shadow pending its sealed blind packet.
    import services.detector_quality as quality
    real_is_authorized = quality.is_authorized
    real_can_influence = quality.can_influence
    test_quality_id = "gap:piece_safety:simple_hang"
    monkeypatch.setattr(
        quality,
        "is_authorized",
        lambda quality_id, surface: (
            True if quality_id == test_quality_id
            else real_is_authorized(quality_id, surface)
        ),
    )
    monkeypatch.setattr(
        quality,
        "can_influence",
        lambda quality_id, surface: (
            True if quality_id == test_quality_id
            else real_can_influence(quality_id, surface)
        ),
    )
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


class TestBuildInstructionVerdict:
    """The actual VISIBLE postgame verdict (2026-08-08, external review
    of b0105f21 -- v1 computed instruction_id/text but only ever sent
    them to analytics, never rendered them). Honest-framing tests are
    the load-bearing ones here: the reviewer's exact concern was that
    'no hang detected' must never be phrased as 'instruction followed.'"""

    def test_no_instruction_id_returns_none(self):
        assert build_instruction_verdict({"instruction_text": "x"}) is None

    def test_no_instruction_text_returns_none(self):
        assert build_instruction_verdict({"instruction_id": "x"}) is None

    def test_none_scoreboard_returns_none(self):
        assert build_instruction_verdict(None) is None

    def test_non_simple_hang_subtype_gets_no_behavioral_claim(self):
        sb = {
            "instruction_id": "inst_1", "instruction_text": "Walk every capture to the end.",
            "focus_subtype": "tactical_seq_loss", "matched_moments": 3,
        }
        verdict = build_instruction_verdict(sb)
        assert verdict["has_measured_outcome"] is False
        assert verdict["message"] == "Walk every capture to the end."
        # Must NOT claim anything about matched_moments for an unverified subtype.
        assert "outcome" not in verdict

    def test_simple_hang_with_a_real_hang_reports_the_miss(self):
        sb = {
            "instruction_id": "inst_1",
            "instruction_text": "Before every move, ask: can this piece be taken?",
            "focus_subtype": "simple_hang",
            "matched_moments": 1,
            "events": [{"move_number": 14, "move": "Qd5", "outcome": "missed"}],
        }
        verdict = build_instruction_verdict(sb)
        assert verdict["outcome"] == "missed"
        assert "hanging on move 14" in verdict["message"]
        assert "Same instruction next game" in verdict["message"]

    def test_simple_hang_zero_matches_says_no_hang_detected_not_followed(self):
        sb = {
            "instruction_id": "inst_1",
            "instruction_text": "Before every move, ask: can this piece be taken?",
            "focus_subtype": "simple_hang",
            "matched_moments": 0,
            "events": [],
        }
        verdict = build_instruction_verdict(sb)
        assert verdict["outcome"] == "no_hang_detected"
        # The exact honesty bar the review set: must say "detected," never "followed."
        assert "no hang detected" in verdict["message"].lower()
        assert "followed" not in verdict["message"].lower()
        assert "checked" not in verdict["message"].lower()

    def test_simple_hang_missing_move_number_omits_clause_gracefully(self):
        sb = {
            "instruction_id": "inst_1", "instruction_text": "x",
            "focus_subtype": "simple_hang", "matched_moments": 1,
            "events": [{"move": "Qd5"}],  # no move_number key
        }
        verdict = build_instruction_verdict(sb)
        assert "on move" not in verdict["message"]


class _FakeSessionsCollection:
    """Fakes just enough of coach_sessions for
    session_greeting_service._last_session_summary: find_one with a
    status-$in filter and a sort-by-field-descending, over a real list
    of session docs (not a single fixed doc, unlike _FakeCollection)."""

    def __init__(self, docs):
        self._docs = docs

    async def find_one(self, query, sort=None):
        matches = [d for d in self._docs if self._matches(d, query)]
        if not matches:
            return None
        if sort:
            field, direction = sort[0]
            matches.sort(key=lambda d: d.get(field) or "", reverse=(direction == -1))
        return dict(matches[0])

    @staticmethod
    def _matches(doc, query):
        for k, v in query.items():
            if isinstance(v, dict) and "$in" in v:
                if doc.get(k) not in v["$in"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True


class _TwoSessionFakeDB:
    """A fuller fake DB for the two-consecutive-sessions integration
    test: real user_active_focus + users (single doc, matches
    _FakeCollection) plus a real coach_sessions list."""

    def __init__(self, focus_doc, user_doc, session_docs):
        self._collections = {"user_active_focus": _FakeCollection(focus_doc)}
        self.users = _FakeCollection(user_doc)
        self.coach_sessions = _FakeSessionsCollection(session_docs)

    def __getitem__(self, name):
        return self._collections[name]


class TestTwoConsecutiveSessionsIntegration:
    """The scope's own required coverage (§7): two consecutive sessions,
    confirming the instruction survives session N -> session N+1 by
    reading focus_bridge fresh each time (Correction #6), NOT by
    chaining off session N's own document -- and that outcome-context
    phrasing ('same instruction as last time') only changes the
    framing, never the instruction identity itself.
    """

    FOCUS = dict(REAL_FOCUS_DOC)  # same instruction_id across both sessions

    @pytest.mark.asyncio
    async def test_session_two_greeting_is_carried_forward_when_same_instruction(self, monkeypatch):
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
        session_one = {
            "user_id": "user_real_123",
            "status": "completed",
            "ended_at": "2026-08-07T10:00:00+00:00",
            "result": "user_won",
            "mission_scoreboard": {
                "instruction_id": self.FOCUS["instruction_id"],
                "matched_moments": 2, "handled_correctly": 2, "handled_incorrectly": 0,
            },
        }
        db = _TwoSessionFakeDB(self.FOCUS, {"role": "admin"}, [session_one])

        greeting = await build_session_greeting(db, "user_real_123")

        assert greeting is not None
        assert greeting["instruction_id"] == "inst_abc123"
        assert greeting["is_carried_forward"] is True
        assert "Same instruction as last time" in greeting["text"]

    @pytest.mark.asyncio
    async def test_session_two_greeting_not_carried_forward_when_instruction_differs(self, monkeypatch):
        # Session one was under a DIFFERENT (now-resolved) instruction --
        # the current one must NOT be framed as carried forward.
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
        session_one = {
            "user_id": "user_real_123",
            "status": "completed",
            "ended_at": "2026-08-01T10:00:00+00:00",
            "result": "user_won",
            "mission_scoreboard": {"instruction_id": "inst_some_other_old_one"},
        }
        db = _TwoSessionFakeDB(self.FOCUS, {"role": "admin"}, [session_one])

        greeting = await build_session_greeting(db, "user_real_123")

        assert greeting["instruction_id"] == "inst_abc123"
        assert greeting["is_carried_forward"] is False
        assert "Same instruction as last time" not in greeting["text"]

    @pytest.mark.asyncio
    async def test_session_one_no_prior_session_not_carried_forward(self, monkeypatch):
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
        db = _TwoSessionFakeDB(self.FOCUS, {"role": "admin"}, [])  # no prior sessions at all

        greeting = await build_session_greeting(db, "user_real_123")

        assert greeting["instruction_id"] == "inst_abc123"
        assert greeting["is_carried_forward"] is False

    @pytest.mark.asyncio
    async def test_abandoned_malformed_prior_session_degrades_gracefully(self, monkeypatch):
        # Correction #6's core promise: an abandoned/malformed session N
        # must not break session N+1's ability to get its instruction.
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
        malformed_prior = {
            "user_id": "user_real_123",
            "status": "abandoned",
            "ended_at": "2026-08-07T09:00:00+00:00",
            # no mission_scoreboard at all -- e.g. abandoned before any move
        }
        db = _TwoSessionFakeDB(self.FOCUS, {"role": "admin"}, [malformed_prior])

        greeting = await build_session_greeting(db, "user_real_123")

        # Still gets a real instruction from focus_bridge -- unaffected
        # by the prior session being malformed.
        assert greeting["instruction_id"] == "inst_abc123"
        assert greeting["instruction_text"] == "Before every move, ask: can this piece be taken?"
        assert greeting["is_carried_forward"] is False  # no outcome-context available, degrades cleanly

    @pytest.mark.asyncio
    async def test_ineligible_user_gets_no_instruction_across_both_sessions(self, monkeypatch):
        # The rollout gate must hold across the whole two-session flow,
        # not just session one.
        monkeypatch.setenv("PWC_SURVIVING_INSTRUCTION_ENABLED", "true")
        session_one = {
            "user_id": "user_real_123", "status": "completed",
            "ended_at": "2026-08-07T10:00:00+00:00", "result": "user_won",
            "mission_scoreboard": {"instruction_id": None},
        }
        db = _TwoSessionFakeDB(self.FOCUS, {"role": "user"}, [session_one])

        greeting = await build_session_greeting(db, "user_real_123")

        assert greeting["instruction_id"] is None
        assert greeting["instruction_text"] is None
        assert greeting["is_carried_forward"] is False
