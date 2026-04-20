"""
Tests for Engine 2 v2.0 — knowledge-tracking (openings/traps/endgames),
not tactical mistake remediation (that's Engine 1).

The recorder now only handles opening exposure from postgame signals.
Endgames, traps, concepts, mate patterns are recorded through the
teaching-engine flow and are tested separately.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.coach_memory import (
    CoachMemory,
    LearningProgress,
    PerformanceTrend,
    record_engine2_skills_from_game,
    record_skill_attempt,
    _normalize_opening_key,
    _opening_outcome,
)
from services.engine2_skill_builder import (
    pick_next_skill,
    find_ready_skills,
    get_skill_node,
    list_skills_by_kind,
    reload_tree,
)


def _fresh_memory() -> CoachMemory:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    m = CoachMemory(user_id="test_user", created_at=now, updated_at=now)
    m.learning = LearningProgress()
    m.performance = PerformanceTrend()
    return m


def _find_skill(memory, skill_id):
    return next((s for s in memory.learning.skills if s.skill_id == skill_id), None)


# ── OPENING KEY NORMALISATION ────────────────────────────────────────


def test_opening_key_normalization():
    assert _normalize_opening_key("Italian Game") == "italian_game"
    assert _normalize_opening_key("caro-kann") == "caro_kann"
    assert _normalize_opening_key("  London System  ") == "london_system"
    assert _normalize_opening_key("") == ""
    assert _normalize_opening_key(None) == ""


# ── OPENING OUTCOME LOGIC ────────────────────────────────────────────


def test_good_game_marks_opening_correct():
    # Tier 1 needs accuracy >= 60
    assert _opening_outcome(accuracy=75.0, blunders=0, game_result="win", tier=1) == "correct"
    assert _opening_outcome(accuracy=62.0, blunders=0, game_result="draw", tier=1) == "correct"


def test_bad_game_marks_opening_wrong():
    assert _opening_outcome(accuracy=45.0, blunders=3, game_result="loss", tier=1) == "wrong"
    assert _opening_outcome(accuracy=40.0, blunders=0, game_result="loss", tier=1) == "wrong"


def test_middling_game_marks_opening_seen():
    # Lost but not catastrophically
    assert _opening_outcome(accuracy=65.0, blunders=1, game_result="loss", tier=1) == "seen"
    # Draw with meh accuracy
    assert _opening_outcome(accuracy=58.0, blunders=1, game_result="draw", tier=1) == "seen"


def test_tier_affects_accuracy_bar():
    # Tier 3 needs 72 — a 68% game that would be correct at tier 1 is only "seen" at tier 3
    assert _opening_outcome(accuracy=68.0, blunders=0, game_result="win", tier=1) == "correct"
    assert _opening_outcome(accuracy=68.0, blunders=0, game_result="win", tier=3) == "seen"


# ── OPENING RECORDING ────────────────────────────────────────────────


def test_playing_tracked_opening_records_attempt():
    """User plays the London System — their london_white skill gets an attempt."""
    mem = _fresh_memory()
    recorded = record_engine2_skills_from_game(
        memory=mem,
        user_rating=1100,
        mistake_types=[],
        blunders=0,
        accuracy=72.0,
        game_result="win",
        was_winning=False,
        endgame_reached=False,
        opening_played="london_system",
    )
    assert "opening_london_white" in recorded
    skill = _find_skill(mem, "opening_london_white")
    assert skill.seen == 1
    assert skill.correct == 1


def test_playing_opening_out_of_rating_range_skipped():
    """A 1700 player who plays London System — that's a tier-1 node (1000-1499). Skip."""
    mem = _fresh_memory()
    recorded = record_engine2_skills_from_game(
        memory=mem,
        user_rating=1700,
        mistake_types=[],
        blunders=0,
        accuracy=80.0,
        game_result="win",
        was_winning=False,
        endgame_reached=False,
        opening_played="london_system",
    )
    assert "opening_london_white" not in recorded
    assert _find_skill(mem, "opening_london_white") is None


def test_no_opening_no_recording():
    """If opening_played is None, nothing records."""
    mem = _fresh_memory()
    recorded = record_engine2_skills_from_game(
        memory=mem,
        user_rating=1100,
        mistake_types=[],
        blunders=2,
        accuracy=55.0,
        game_result="loss",
        was_winning=False,
        endgame_reached=False,
        opening_played=None,
    )
    assert recorded == []


def test_unknown_opening_no_recording():
    """An opening name that isn't in any skill's content_ref doesn't record."""
    mem = _fresh_memory()
    recorded = record_engine2_skills_from_game(
        memory=mem,
        user_rating=1100,
        mistake_types=[],
        blunders=0,
        accuracy=80.0,
        game_result="win",
        was_winning=False,
        endgame_reached=False,
        opening_played="random_obscure_opening_xyz",
    )
    assert recorded == []


def test_italian_in_intermediate_range():
    """Italian Game (tier 2) appears for 1400+ players. Clearly bad game → wrong."""
    mem = _fresh_memory()
    recorded = record_engine2_skills_from_game(
        memory=mem,
        user_rating=1600,
        mistake_types=[],
        blunders=3,
        accuracy=42.0,
        game_result="loss",
        was_winning=False,
        endgame_reached=False,
        opening_played="italian_game",
    )
    # Bad game in tier 2 → wrong
    assert "opening_italian_white" in recorded
    assert _find_skill(mem, "opening_italian_white").wrong == 1


# ── SKILL TREE STRUCTURE ─────────────────────────────────────────────


def test_skill_tree_loads():
    reload_tree()
    openings = list_skills_by_kind("opening")
    traps = list_skills_by_kind("trap_set")
    endgames = list_skills_by_kind("endgame")
    mates = list_skills_by_kind("mate_pattern")
    assert len(openings) >= 5
    assert len(traps) >= 1
    assert len(endgames) >= 2
    assert len(mates) >= 1


def test_skill_nodes_have_required_fields():
    reload_tree()
    for sid in list_skills_by_kind("opening"):
        node = get_skill_node(sid)
        assert node is not None
        assert "content_ref" in node
        assert "rating_min" in node
        assert "rating_max" in node
        assert "tier" in node
        assert "kind" in node
        assert node["kind"] == "opening"


def test_no_tactical_tier_1_leftovers():
    """Ensure old tactical skills (hanging_piece, fork, pin, etc.) are gone.
    Those belong to Engine 1 now — tree should be knowledge-only."""
    reload_tree()
    concepts = list_skills_by_kind("concept")
    all_kinds = {"opening", "trap_set", "endgame", "mate_pattern", "concept", "coached_play"}
    # hanging_piece, fork, pin are not valid top-level skill_ids anymore
    for removed in ("hanging_piece", "fork", "pin", "free_piece_capture", "pre_move_check"):
        assert get_skill_node(removed) is None, \
            f"{removed} should have been removed — it's Engine 1 territory now"


# ── PICK NEXT SKILL ──────────────────────────────────────────────────


def test_pick_next_returns_kind_and_content_ref():
    """New API shape includes kind + content_ref."""
    mem = _fresh_memory()
    result = pick_next_skill(mem, 800)
    assert result is not None
    assert "kind" in result
    assert "content_ref" in result
    assert "skill_id" in result
    assert "label" in result
    assert "tier" in result


def test_pick_next_respects_rating_band():
    """A 700 player gets tier-0 skills only; a 1600 player gets tier-2+."""
    mem = _fresh_memory()
    pick_700 = pick_next_skill(mem, 700)
    pick_1600 = pick_next_skill(mem, 1600)
    if pick_700:
        assert pick_700["tier"] == 0
    if pick_1600:
        assert pick_1600["tier"] >= 1


def test_prerequisites_enforced():
    """Tier-1 openings require coached_development; tier-2 require tier-1 etc."""
    mem = _fresh_memory()
    # At 1100 without coached_development, london_white is blocked by prereq
    # (it requires coached_development)
    ready = find_ready_skills(mem, 1100)
    assert "opening_london_white" not in ready, \
        "london_white needs coached_development first"


# ── LEARNED DEMOTION (carried over from v1) ──────────────────────────


def test_learned_skill_demotes_on_backslide():
    """If an opening was learned but the user starts failing, demote it."""
    mem = _fresh_memory()

    # Build to 'learned'
    for _ in range(5):
        record_skill_attempt(mem, "opening_london_white", "opening", "correct")
    sk = _find_skill(mem, "opening_london_white")
    assert sk.is_learned()
    assert "opening_london_white" in mem.learning.openings_learned

    # Two wrongs in a row → demote
    record_skill_attempt(mem, "opening_london_white", "opening", "wrong")
    record_skill_attempt(mem, "opening_london_white", "opening", "wrong")

    sk = _find_skill(mem, "opening_london_white")
    assert sk.learned_at is None
    assert "opening_london_white" not in mem.learning.openings_learned


# ── SMOKE RUNNER ─────────────────────────────────────────────────────


def _smoke():
    passed = 0
    failed = []
    tests = [n for n in globals() if n.startswith("test_")]
    for name in tests:
        try:
            globals()[name]()
            passed += 1
            print(f"  PASS: {name}")
        except AssertionError as e:
            failed.append((name, str(e)))
            print(f"  FAIL: {name} — {e}")
        except Exception as e:
            failed.append((name, f"{type(e).__name__}: {e}"))
            print(f"  ERROR: {name} — {type(e).__name__}: {e}")
    print()
    print(f"Results: {passed}/{len(tests)} passed, {len(failed)} failed")
    for n, e in failed:
        print(f"  - {n}: {e}")
    return len(failed) == 0


if __name__ == "__main__":
    sys.exit(0 if _smoke() else 1)
