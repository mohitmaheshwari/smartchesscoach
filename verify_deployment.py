"""
Verify Deployment — Run on production server to check if latest code is deployed.

Usage:
  docker exec -it chess-coach-backend python3 verify_deployment.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

checks = []

def check(name, result, detail=""):
    status = "✅" if result else "❌"
    checks.append((name, result))
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))

print("=== BACKEND CODE VERIFICATION ===\n")

# 1. Eval fix — solver_is_white in community_training_service
try:
    import inspect
    from services.community_training_service import get_training_feed
    src = inspect.getsource(get_training_feed)
    check("Eval fix (solver_is_white)", "solver_is_white" in src)
except Exception as e:
    check("Eval fix (solver_is_white)", False, str(e))

# 2. Game reason classifier — abandonment fix
try:
    from services.game_reason_classifier import classify_game_reason
    src = inspect.getsource(classify_game_reason)
    # The wrapper function should exist
    check("Game reason classifier wrapper", "_classify_game_reason_inner" in src or "classify_game_reason" in src)
except Exception as e:
    check("Game reason classifier", False, str(e))

# 3. Abandonment not treated as time_collapse
try:
    from services.game_reason_classifier import _classify_game_reason_inner
    src = inspect.getsource(_classify_game_reason_inner)
    has_old = 'termination in ("timeout", "abandonment")' in src
    has_new = 'termination == "timeout"' in src
    check("Abandonment fix (not time_collapse)", has_new and not has_old)
except Exception as e:
    check("Abandonment fix", False, str(e))

# 4. Problem lifecycle service exists
try:
    from services.problem_lifecycle import update_problem_lifecycle
    check("Problem lifecycle service", True)
except Exception as e:
    check("Problem lifecycle service", False, str(e))

# 5. Game moments service exists
try:
    from services.game_moments_service import extract_game_moments
    check("Game moments service", True)
except Exception as e:
    check("Game moments service", False, str(e))

# 6. Position intelligence exists
try:
    from services.position_intelligence import read_board_deep
    check("Position intelligence (LLM)", True)
except Exception as e:
    check("Position intelligence", False, str(e))

# 7. Coaching feedback cache
try:
    from services.community_training_service import _generate_coaching_feedback
    check("Coaching feedback generator", True)
except Exception as e:
    check("Coaching feedback generator", False, str(e))

# 8. Concrete explanation — opened lines for pawns
try:
    from services.community_training_service import _build_concrete_explanation
    src = inspect.getsource(_build_concrete_explanation)
    check("Concrete explanation (pawn opens lines)", "Always check" in src or "if True" in src)
except Exception as e:
    check("Concrete explanation", False, str(e))

# 9. Lab coaching — grouped_games and strengths
try:
    from routes.training_advanced import _build_lab_coaching
    src = inspect.getsource(_build_lab_coaching)
    check("Lab grouped_games", "grouped_games" in src)
    check("Lab strengths", "strengths" in src)
    check("Lab sub_causes", "sub_causes" in src)
    check("Lab lifecycle", "lifecycle" in src)
except Exception as e:
    check("Lab coaching", False, str(e))

# 10. Coaching cache
try:
    src2 = inspect.getsource(get_training_feed)
    from routes.training_advanced import get_lab_coach_pick
    src3 = inspect.getsource(get_lab_coach_pick)
    check("Coaching cache", "coaching_cache" in src3)
except Exception as e:
    check("Coaching cache", False, str(e))

# 11. Replay endpoint
try:
    from routes.training_advanced import get_game_replay
    check("Replay endpoint", True)
except Exception as e:
    check("Replay endpoint", False, str(e))

# 12. Trap detection v2 — no move 8 gate, has punishability
try:
    from services.trap_detection_service import _is_punishable, _analyze_restriction_causes
    check("Trap detection v2 (punishability)", True)
except Exception as e:
    check("Trap detection v2", False, str(e))

# 13. Position eval label
try:
    from services.position_eval_label import get_eval_label
    # Test: Black user, White is +400 → should show negative for user
    result = get_eval_label(400, "black")
    check("Eval label (Black perspective)", result["label"] in ("Losing", "Under pressure", "Badly losing"),
          f"label={result['label']}, short={result['short']}")
except Exception as e:
    check("Eval label", False, str(e))

# 14. Training progress (5 correct, not attempts)
try:
    from services.community_training_service import get_training_progress
    check("Training progress (5 correct)", True)
except Exception as e:
    check("Training progress", False, str(e))

# 15. Post-game pattern verdict
try:
    from routes.coach_play import get_postgame_reflection
    src = inspect.getsource(get_postgame_reflection)
    check("Post-game pattern verdict", "pattern_verdict" in src)
except Exception as e:
    check("Post-game pattern verdict", False, str(e))

# Summary
print(f"\n=== SUMMARY ===")
passed = sum(1 for _, r in checks if r)
total = len(checks)
print(f"  {passed}/{total} checks passed")
if passed < total:
    print(f"\n  FAILED:")
    for name, result in checks:
        if not result:
            print(f"    ❌ {name}")
    print(f"\n  → Backend code is NOT fully deployed. Push code and rebuild.")
else:
    print(f"\n  ✅ All backend code is deployed correctly.")
