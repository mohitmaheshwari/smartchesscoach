"""
Verify Deployment — Run on production server.

Usage:
  docker exec -it chess-coach-backend python3 verify_deployment.py
"""

import os
import sys
import inspect

# Set up paths like the app does
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if os.path.exists(backend_dir):
    sys.path.insert(0, backend_dir)
    os.chdir(backend_dir)
else:
    # Already in backend dir
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Verify chess module
try:
    import chess
    print(f"chess module: OK (version {chess.__version__})")
except ImportError:
    print("❌ chess module NOT found — pip install python-chess")
    sys.exit(1)

checks = []

def check(name, result, detail=""):
    status = "✅" if result else "❌"
    checks.append((name, result))
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))

print("\n=== BACKEND CODE VERIFICATION ===\n")

# 1. Eval fix
try:
    from services.community_training_service import get_training_feed
    src = inspect.getsource(get_training_feed)
    check("Eval fix (solver_is_white)", "solver_is_white" in src)
except Exception as e:
    check("Eval fix", False, str(e))

# 2. Abandonment fix
try:
    from services.game_reason_classifier import _classify_game_reason_inner
    src = inspect.getsource(_classify_game_reason_inner)
    has_new = 'termination == "timeout"' in src
    check("Abandonment fix", has_new)
except Exception as e:
    check("Abandonment fix", False, str(e))

# 3. Problem lifecycle
try:
    from services.problem_lifecycle import update_problem_lifecycle
    check("Problem lifecycle", True)
except Exception as e:
    check("Problem lifecycle", False, str(e))

# 4. Game moments
try:
    from services.game_moments_service import extract_game_moments
    check("Game moments service", True)
except Exception as e:
    check("Game moments service", False, str(e))

# 5. Position intelligence
try:
    from services.position_intelligence import read_board_deep
    check("Position intelligence (LLM)", True)
except Exception as e:
    check("Position intelligence", False, str(e))

# 6. Coaching feedback
try:
    from services.community_training_service import _generate_coaching_feedback
    check("Coaching feedback generator", True)
except Exception as e:
    check("Coaching feedback generator", False, str(e))

# 7. Concrete explanation — pawn opens lines
try:
    from services.community_training_service import _build_concrete_explanation
    src = inspect.getsource(_build_concrete_explanation)
    check("Pawn opens lines fix", "Always check" in src or "if True" in src)
except Exception as e:
    check("Pawn opens lines fix", False, str(e))

# 8. Lab coaching
try:
    from routes.training_advanced import _build_lab_coaching
    src = inspect.getsource(_build_lab_coaching)
    check("Lab grouped_games", "grouped_games" in src)
    check("Lab strengths", "strengths" in src)
    check("Lab lifecycle", "lifecycle" in src)
except Exception as e:
    check("Lab coaching", False, str(e))

# 9. Coaching cache
try:
    from routes.training_advanced import get_lab_coach_pick
    src = inspect.getsource(get_lab_coach_pick)
    check("Coaching cache", "coaching_cache" in src)
except Exception as e:
    check("Coaching cache", False, str(e))

# 10. Replay endpoint
try:
    from routes.training_advanced import get_game_replay
    check("Replay endpoint", True)
except Exception as e:
    check("Replay endpoint", False, str(e))

# 11. Trap detection v2
try:
    from services.trap_detection_service import _is_punishable
    check("Trap detection v2", True)
except Exception as e:
    check("Trap detection v2", False, str(e))

# 12. Eval label — test Black perspective
try:
    from services.position_eval_label import get_eval_label
    result = get_eval_label(400, "black")
    is_correct = "losing" in result["label"].lower() or "worse" in result["label"].lower() or "pressure" in result["label"].lower()
    check("Eval label (Black +400 = losing)", is_correct, f"got: {result['label']} {result['short']}")
except Exception as e:
    check("Eval label", False, str(e))

# 13. Training progress
try:
    from services.community_training_service import get_training_progress
    check("Training progress (5 correct)", True)
except Exception as e:
    check("Training progress", False, str(e))

# 14. Post-game pattern verdict
try:
    from routes.coach_play import get_postgame_reflection
    src = inspect.getsource(get_postgame_reflection)
    check("Post-game pattern verdict", "pattern_verdict" in src)
except Exception as e:
    check("Post-game pattern verdict", False, str(e))

# 15. Game reason classifier — motifs
try:
    from services.game_reason_classifier import classify_game_reason
    src = inspect.getsource(classify_game_reason)
    check("Game reason motifs", "motifs" in src)
except Exception as e:
    check("Game reason motifs", False, str(e))

# 16. LLM coaching feedback prompt — max 20 words
try:
    src = inspect.getsource(_generate_coaching_feedback)
    check("LLM prompt (20 words)", "max 20 words" in src or "20 words" in src)
except Exception as e:
    check("LLM prompt check", False, str(e))

# 17. Coaching feedback cache
try:
    from services.community_training_service import record_solve_attempt
    src = inspect.getsource(record_solve_attempt)
    check("Feedback cache", "coaching_feedback_cache" in src)
except Exception as e:
    check("Feedback cache", False, str(e))

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
    print(f"\n  → Push latest code and run: docker compose up -d --build")
else:
    print(f"\n  ✅ All backend code is deployed correctly.")
