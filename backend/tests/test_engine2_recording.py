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
    record_concept_applications_from_game,
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


def _move_rows(sans):
    import chess

    board = chess.Board()
    rows = []
    for san in sans:
        move = board.parse_san(san)
        rows.append({
            "fen_before": board.fen(),
            "move": san,
            "move_number": board.fullmove_number,
            "best_move_uci": move.uci(),
        })
        board.push(move)
    return rows


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
    assert skill.correct == 0
    assert skill.wrong == 0
    assert skill.outcomes == ["seen"]


def test_playing_opening_out_of_rating_range_still_records():
    """Exposure is a FACT and is recorded regardless of the node's band.

    Changed 2026-09-15 (was: out-of-band play recorded nothing). Recording
    answers "did they play it"; the rating band answers "should we teach it",
    and that gate still lives in find_ready_skills(). Gating the fact meant a
    correctly-rated 546 player could never accumulate exposure on an opening
    banded 1000-1499 that they play every single game - which is exactly the
    population the beginner content is for.
    """
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
    assert "opening_london_white" in recorded
    assert _find_skill(mem, "opening_london_white") is not None


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


def test_italian_in_intermediate_range_records_exposure_not_knowledge():
    """Result and broad accuracy cannot prove opening knowledge."""
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
    assert "opening_italian_white" in recorded
    skill = _find_skill(mem, "opening_italian_white")
    assert skill.seen == 1
    assert skill.correct == 0
    assert skill.wrong == 0
    assert skill.outcomes == ["seen"]


def test_exact_opening_application_maps_to_real_repertoire_skill(monkeypatch):
    monkeypatch.setattr(
        "services.concept_detectors._runner.is_authorized",
        lambda *args, **kwargs: True,
    )
    memory = _fresh_memory()
    rows = _move_rows(["d4", "d5", "Bf4"])
    rows[-1].update({
        "best_move_san": "Bf4",
        "cp_loss": 0,
        "evaluation": "best",
        "eval_before": 18,
        "eval_after": 18,
    })
    recorded = record_concept_applications_from_game(
        memory,
        rows,
        "white",
        game_id="game-london",
        opening_name="london_system",
    )
    assert ("opening_london_white", "applied") in recorded
    assert not any(skill.skill_id == "opening_play" for skill in memory.learning.skills)
    skill = _find_skill(memory, "opening_london_white")
    assert skill.applied == 1
    evidence = skill.evidence[-1]
    assert evidence["detector_quality_id"] == "concept:opening_play"
    assert evidence["truth_source"] == "stored_stockfish_analysis"
    assert evidence["stored_best_move_san"] == "Bf4"
    assert evidence["stored_best_move_uci"] == "c1f4"
    assert evidence["stored_cp_loss"] == 0
    assert evidence["stored_evaluation"] == "best"
    assert evidence["stored_eval_before"] == 18
    assert evidence["stored_eval_after"] == 18
    assert evidence["opening_name"] == "london_system"


def test_verbose_provider_opening_maps_to_exact_repertoire_skill(monkeypatch):
    monkeypatch.setattr(
        "services.concept_detectors._runner.is_authorized",
        lambda *args, **kwargs: True,
    )
    memory = _fresh_memory()
    recorded = record_concept_applications_from_game(
        memory,
        _move_rows(["d4", "d5", "Bf4"]),
        "white",
        game_id="game-london-provider-name",
        opening_name="Queens Pawn Opening Accelerated London System",
    )

    assert ("opening_london_white", "applied") in recorded


def test_exact_costly_opening_deviation_records_a_miss(monkeypatch):
    monkeypatch.setattr(
        "services.concept_detectors._runner.is_authorized",
        lambda *args, **kwargs: True,
    )
    rows = _move_rows(["d4", "d5", "Nf3"])
    rows[-1]["best_move_uci"] = "c1f4"
    memory = _fresh_memory()

    recorded = record_concept_applications_from_game(
        memory,
        rows,
        "white",
        game_id="game-london-deviation",
        opening_name="london_system",
    )

    assert ("opening_london_white", "wrong") in recorded


def test_exact_trap_defense_maps_to_canonical_trap_set(monkeypatch):
    monkeypatch.setattr(
        "services.concept_detectors._runner.is_authorized",
        lambda *args, **kwargs: True,
    )
    memory = _fresh_memory()
    recorded = record_concept_applications_from_game(
        memory,
        _move_rows(["e4", "e5", "Bc4", "Nc6", "Qh5", "Qe7"]),
        "black",
        game_id="game-scholar-defense",
        opening_name="italian_game",
    )
    assert ("trap_set_italian", "applied") in recorded
    assert not any(skill.skill_id == "trap_detection" for skill in memory.learning.skills)
    skill = _find_skill(memory, "trap_set_italian")
    assert skill.applied == 1
    assert skill.evidence[-1]["content_id"] == (
        "italian-game/scholar-s-mate-danger"
    )


def test_non_italian_trap_maps_by_exact_canonical_family(monkeypatch):
    monkeypatch.setattr(
        "services.concept_detectors._runner.is_authorized",
        lambda *args, **kwargs: True,
    )
    memory = _fresh_memory()
    moves = [
        "d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Nbd7",
        "cxd5", "exd5", "e3",
    ]
    recorded = record_concept_applications_from_game(
        memory,
        _move_rows(moves),
        "white",
        game_id="game-elephant-defense",
        opening_name="queens_gambit",
    )
    assert ("trap_set_queens_gambit", "applied") in recorded
    skill = _find_skill(memory, "trap_set_queens_gambit")
    assert skill.evidence[-1]["content_id"] == "queens-gambit/elephant-trap"


def test_exact_endgame_adapter_maps_to_real_curriculum_skill(monkeypatch):
    monkeypatch.setattr(
        "services.concept_detectors._runner.is_authorized",
        lambda *args, **kwargs: True,
    )
    from services.endgame_theory_service import get_verified_lesson_data

    position = get_verified_lesson_data(
        "king_and_pawn", "opposition"
    )["positions"][0]
    board_side = position["fen"].split()[1]
    row = {
        "fen_before": position["fen"],
        "move": position["correct_move_san"],
        "move_number": 40,
        "best_move_san": position["correct_move_san"],
        "best_move_uci": position["correct_move_uci"],
        "cp_loss": 0,
        "evaluation": "best",
    }
    memory = _fresh_memory()

    recorded = record_concept_applications_from_game(
        memory,
        [row],
        "black" if board_side == "b" else "white",
        game_id="game-opposition-transfer",
    )

    assert ("endgame_opposition", "applied") in recorded
    assert not any(
        skill.skill_id.startswith("endgame_curriculum__")
        for skill in memory.learning.skills
    )
    skill = _find_skill(memory, "endgame_opposition")
    assert skill.evidence[-1]["content_id"] == "king_and_pawn/opposition"
    assert skill.evidence[-1]["truth_source"] == "stored_stockfish_analysis"


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


def test_tier1_openings_no_longer_gated_on_coached_development():
    """Tier-1 openings are reachable without completing coached_development.

    Changed 2026-09-15. Nothing in the codebase ever calls
    record_skill_attempt for coached_development - measured 0 recorded
    attempts across all 69 production users - so it could not be completed
    even in principle, and the 7 openings behind it (London, Caro-Kann,
    Scandinavian, Four Knights, King's Gambit, Pirc, Alekhine) were
    permanently unreachable. It is a phantom gate until it has a real
    completion path.
    """
    mem = _fresh_memory()
    ready = find_ready_skills(mem, 1100)
    assert "opening_london_white" in ready
    assert "opening_caro_kann_black" in ready


def test_real_prerequisite_chains_still_enforced():
    """Removing the phantom root must NOT disable genuine prerequisites."""
    mem = _fresh_memory()
    # Italian (tier 2) still sits behind London (tier 1), which is unlearned.
    assert "opening_italian_white" not in find_ready_skills(mem, 1500)

    # Learn London, and Italian becomes reachable at an in-band rating.
    for _ in range(5):
        record_skill_attempt(mem, "opening_london_white", "opening", "correct")
    assert "opening_london_white" in mem.learning.openings_learned
    assert "opening_italian_white" in find_ready_skills(mem, 1500)



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


# ── OPENING ID BRIDGE (2026-09-15) ───────────────────────────────────
# Opening attempts used to be recorded under the recognizer's DISPLAY NAME
# ("Italian Game Two Knights Open") while the tree gates on ids
# ("opening_italian_white"). The namespaces never intersected, so learned_at
# stayed None on all 7,792 recorded opening attempts across 65 production
# users and no opening could ever graduate.

from services.engine2_skill_builder import resolve_opening_skill_ids  # noqa: E402


def test_bare_family_name_resolves():
    assert resolve_opening_skill_ids("Italian Game") == ["opening_italian_white"]
    assert resolve_opening_skill_ids("Scandinavian Defense") == [
        "opening_scandinavian_black"
    ]


def test_variation_with_move_text_resolves_to_its_family():
    """The shape the recognizer actually emits - this is what used to fail."""
    assert resolve_opening_skill_ids(
        "Caro Kann Defense Exchange Variation 3...cxd5 4.c3 Nf6"
    ) == ["opening_caro_kann_black"]
    assert resolve_opening_skill_ids(
        "Indian Game London System 3...b6 4.e3 Bb7 5.Nbd2"
    ) == ["opening_london_white"]


def test_punctuation_and_case_are_normalised():
    assert resolve_opening_skill_ids("caro-kann defense") == [
        "opening_caro_kann_black"
    ]


def test_unknown_opening_resolves_to_nothing():
    """Right-or-silent: never guess a skill_id."""
    assert resolve_opening_skill_ids("Total Nonsense Opening") == []
    assert resolve_opening_skill_ids("") == []
    assert resolve_opening_skill_ids(None) == []


def test_recording_uses_the_canonical_id_not_the_display_name():
    mem = _fresh_memory()
    recorded = record_engine2_skills_from_game(
        memory=mem,
        user_rating=1100,
        mistake_types=[],
        blunders=0,
        accuracy=60.0,
        game_result="draw",
        was_winning=False,
        endgame_reached=False,
        opening_played="Caro Kann Defense Exchange Variation 3...cxd5 4.c3 Nf6",
    )
    assert recorded == ["opening_caro_kann_black"]
    assert _find_skill(mem, "opening_caro_kann_black") is not None
    # the display name must NOT be recorded as its own skill any more
    assert _find_skill(
        mem, "Caro Kann Defense Exchange Variation 3...cxd5 4.c3 Nf6"
    ) is None


def test_repeated_exposure_accumulates_on_one_canonical_skill():
    """Five different Caro-Kann variations are five attempts at ONE skill.

    Previously they were five separate display-name skills, each stuck at
    seen=1, so the 5-seen graduation bar was unreachable by construction.
    """
    mem = _fresh_memory()
    for variation in [
        "Caro Kann Defense",
        "Caro Kann Defense Advance Variation",
        "Caro Kann Defense Exchange Variation 3...cxd5",
        "Caro Kann Defense 2.Nc3 d5",
        "Caro Kann Defense Classical Variation 4...Bf5",
    ]:
        record_engine2_skills_from_game(
            memory=mem,
            user_rating=1100,
            mistake_types=[],
            blunders=0,
            accuracy=60.0,
            game_result="draw",
            was_winning=False,
            endgame_reached=False,
            opening_played=variation,
        )
    skill = _find_skill(mem, "opening_caro_kann_black")
    assert skill is not None
    assert skill.seen == 5
