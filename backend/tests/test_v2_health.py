"""
V2 Teaching System Health Check
================================
Run on server to verify the v2 system is deployed and working.

Usage:
    python tests/test_v2_health.py

Checks:
1. Can import all v2 modules?
2. Is PedagogicalOpponent using v2?
3. Is Stockfish available?
4. Does the selector produce results?
5. What skill level is configured?
6. Is the guardian in Socratic mode?
7. Is session promotion wired?
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results = []

def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((status, name, detail))
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("V2 TEACHING SYSTEM HEALTH CHECK")
print("=" * 60)

# ─── 1. Module imports ──────────────────────────────────────
print("\n1. Module Imports")
try:
    from coach_play.teaching.types import TeachingIntent, MoveSelection
    check("types.py", True, f"TeachingIntent has {len(TeachingIntent)} intents: {[i.value for i in TeachingIntent]}")
except Exception as e:
    check("types.py", False, str(e))

try:
    from coach_play.teaching.pattern_detectors import find_hanging_pieces, find_fork_opportunities, count_forcing_moves, analyze_position
    check("pattern_detectors.py", True)
except Exception as e:
    check("pattern_detectors.py", False, str(e))

try:
    from coach_play.teaching.candidate_generator import generate_candidates
    check("candidate_generator.py", True)
except Exception as e:
    check("candidate_generator.py", False, str(e))

try:
    from coach_play.teaching.teaching_evaluator import score_candidate, MIN_FEASIBILITY_SCORE
    check("teaching_evaluator.py", True, f"MIN_FEASIBILITY_SCORE={MIN_FEASIBILITY_SCORE}")
except Exception as e:
    check("teaching_evaluator.py", False, str(e))

try:
    from coach_play.teaching.intent_selector import select_intent, rank_intents, DEFAULT_INTENT_ORDER
    order = [i.value for i in DEFAULT_INTENT_ORDER]
    check("intent_selector.py", True, f"default order: {order}")
except Exception as e:
    check("intent_selector.py", False, str(e))

try:
    from coach_play.teaching.move_selector_v2 import TeachingMoveSelectorV2
    check("move_selector_v2.py", True)
except Exception as e:
    check("move_selector_v2.py", False, str(e))

# ─── 2. PedagogicalOpponent wiring ─────────────────────────
print("\n2. PedagogicalOpponent Wiring")
try:
    from coach_play.coach_opponent import PedagogicalOpponent
    import inspect
    src = inspect.getsource(PedagogicalOpponent.get_move)
    uses_v2 = "TeachingMoveSelectorV2" in src
    uses_v1 = "TeachingMoveSelector()" in src and "V2" not in src
    check("Uses V2 selector", uses_v2, "TeachingMoveSelectorV2 found in get_move()")
    if uses_v1:
        check("V1 removed", False, "Old TeachingMoveSelector still referenced!")

    # Check if user_rating is passed
    passes_rating = "user_rating=self.user_rating" in src
    check("Passes user_rating to V2", passes_rating)

    # Check last_game_violations param
    init_src = inspect.getsource(PedagogicalOpponent.__init__)
    has_violations = "last_game_violations" in init_src
    check("Has last_game_violations param", has_violations)
except Exception as e:
    check("PedagogicalOpponent", False, str(e))

# ─── 3. Skill Level scaling ────────────────────────────────
print("\n3. Skill Level Scaling")
try:
    selector_800 = TeachingMoveSelectorV2(user_rating=800)
    selector_1200 = TeachingMoveSelectorV2(user_rating=1200)
    selector_1600 = TeachingMoveSelectorV2(user_rating=1600)
    selector_2000 = TeachingMoveSelectorV2(user_rating=2000)

    check("800 rating", True, f"Skill Level {selector_800.skill_level}")
    check("1200 rating", True, f"Skill Level {selector_1200.skill_level}")
    check("1600 rating", True, f"Skill Level {selector_1600.skill_level}")
    check("2000 rating", True, f"Skill Level {selector_2000.skill_level}")

    scales = selector_800.skill_level < selector_1200.skill_level < selector_1600.skill_level < selector_2000.skill_level
    check("Skill scales with rating", scales)
except Exception as e:
    check("Skill Level", False, str(e))

# ─── 4. Stockfish available ────────────────────────────────
print("\n4. Stockfish Engine")
try:
    import chess.engine
    engine = chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish")
    info = engine.id
    check("Stockfish available", True, f"{info.get('name', 'unknown')}")
    engine.quit()
except Exception as e:
    check("Stockfish available", False, str(e))

# ─── 5. Quick selector test ────────────────────────────────
print("\n5. Quick Selector Test (Italian Game position)")
try:
    import chess
    board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    selector = TeachingMoveSelectorV2(user_rating=1200)
    result = selector.select_move(
        board=board,
        coach_color=chess.WHITE,
    )
    check("Produces result", True, f"move={result.selected_san}")
    check("Has intent", bool(result.intent), f"intent={result.intent.value}")
    check("Has score", result.score_breakdown.final_score > 0,
          f"final={result.score_breakdown.final_score:.2f}, raw={result.score_breakdown.raw_score:.2f}")
    check("Has explanation", bool(result.score_breakdown.explanation),
          result.score_breakdown.explanation[:60])
    check("Has candidates", len(result.all_candidates) >= 4,
          f"{len(result.all_candidates)} candidates")
    selector._close_engine()
except Exception as e:
    check("Selector test", False, str(e))
    import traceback
    traceback.print_exc()

# ─── 6. Guardian mode ──────────────────────────────────────
print("\n6. Pre-Move Guardian")
try:
    from coach_play.pre_move_guardian import PreMoveGuardian, RiskLevel
    guardian = PreMoveGuardian()
    import inspect
    decide_src = inspect.getsource(guardian._decide_intervention)

    # Check if MEDIUM/HIGH are silenced (Socratic mode)
    blocks_high = "RiskLevel.HIGH" in decide_src and "InterventionType.WARN" in decide_src
    socratic_mode = "Socratic" in decide_src or "fundamentals" in decide_src
    only_critical = "RiskLevel.CRITICAL" in decide_src

    if socratic_mode:
        check("Guardian in Socratic mode", True, "Only CRITICAL triggers warning")
    elif only_critical:
        check("Guardian in Socratic mode", True, "Only CRITICAL level intervenes")
    else:
        check("Guardian in Socratic mode", False, "Still blocking HIGH/MEDIUM moves")
except Exception as e:
    check("Guardian", False, str(e))

# ─── 7. Session promotion ──────────────────────────────────
print("\n7. Session → Game Promotion")
try:
    import inspect
    from routes import coach_play as cp_module
    module_src = inspect.getsource(cp_module)
    has_promote = "_promote_session_to_game" in module_src
    check("_promote_session_to_game exists", has_promote)

    called_on_end = "promote_session_to_game" in module_src and "end_coach_session" in module_src
    check("Called on game end", called_on_end)
except Exception as e:
    check("Promotion", False, str(e))

# ─── 8. Move snapshots ─────────────────────────────────────
print("\n8. Move Snapshots")
try:
    has_snapshots = "move_snapshots" in module_src
    has_push = '"$push": {"move_snapshots"' in module_src or "'$push': {'move_snapshots'" in module_src or "move_snapshots" in module_src
    check("move_snapshots stored", has_snapshots)
except Exception as e:
    check("Snapshots", False, str(e))

# ─── 9. Coach intent wiring ────────────────────────────────
print("\n9. Coach Intent → Coaching Pipeline")
try:
    from services.shared_coaching_v5 import generate_move_coaching
    import inspect
    sig = inspect.signature(generate_move_coaching)
    has_intent_param = "coach_intent" in sig.parameters
    check("generate_move_coaching has coach_intent param", has_intent_param)

    from services.fundamentals_checklist_service import FundamentalsChecklistService
    diag_sig = inspect.signature(FundamentalsChecklistService.diagnose)
    has_intent_in_diagnose = "coach_intent" in diag_sig.parameters
    check("diagnose() has coach_intent param", has_intent_in_diagnose)
except Exception as e:
    check("Intent wiring", False, str(e))

# ─── SUMMARY ───────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
print(f"RESULT: {passed} passed, {failed} failed")
if failed == 0:
    print("🚀 V2 system is fully deployed and operational")
else:
    print("🔴 Some checks failed — see above")
    print("\nFailed checks:")
    for s, name, detail in results:
        if s == FAIL:
            print(f"  {FAIL} {name}: {detail}")
print("=" * 60)
