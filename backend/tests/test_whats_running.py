"""
What's Actually Running — checks the LIVE code on the server.

Run: python tests/test_whats_running.py
"""

import sys, os, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

P = "✅"
F = "❌"

print("=" * 60)
print("WHAT IS ACTUALLY RUNNING ON THIS SERVER?")
print("=" * 60)

# 1. Which get_move is PedagogicalOpponent using?
print("\n1. PedagogicalOpponent.get_move() source check")
from coach_play.coach_opponent import PedagogicalOpponent
src = inspect.getsource(PedagogicalOpponent.get_move)

if "TeachingMoveSelectorV2" in src:
    print(f"  {P} Uses TeachingMoveSelectorV2")
else:
    print(f"  {F} Does NOT use V2 — uses old selector or fallback")

if "user_rating=self.user_rating" in src:
    print(f"  {P} Passes user_rating")
else:
    print(f"  {F} Does NOT pass user_rating (hardcoded skill level)")

if "last_game_violations" in src:
    print(f"  {P} Has learning loop")
else:
    print(f"  {F} No learning loop")

# 2. What skill level for 1172 rating?
print("\n2. Skill Level for rating 1172")
from coach_play.teaching.move_selector_v2 import TeachingMoveSelectorV2
s = TeachingMoveSelectorV2(user_rating=1172)
print(f"  V2 selector skill level: {s.skill_level}")

from coach_play.coach_opponent import rating_to_skill_level
old_skill = rating_to_skill_level(1172)
print(f"  Old fallback skill level: {old_skill}")

if s.skill_level != old_skill:
    print(f"  {P} They're different — can distinguish v2 from fallback")
else:
    print(f"  {F} Same — can't distinguish")

# 3. Is fetchInteractiveCoaching enabled in frontend?
print("\n3. Frontend: fetchInteractiveCoaching call")
frontend_file = "/app/frontend/src/pages/CoachPlay.jsx"
if os.path.exists(frontend_file):
    with open(frontend_file, 'r') as f:
        fe_src = f.read()

    # Check if the call after coach thinking is enabled
    if "fetchInteractiveCoaching(session" in fe_src and "No need for the separate V5" not in fe_src:
        print(f"  {P} fetchInteractiveCoaching is called after coach moves")
    elif "fetchInteractiveCoaching(session" in fe_src:
        # Check if the old "No need" comment is still there disabling it
        lines = fe_src.split('\n')
        for i, line in enumerate(lines):
            if "No need for the separate V5" in line:
                print(f"  {F} fetchInteractiveCoaching is DISABLED at line {i+1}")
                print(f"     → '{line.strip()}'")
                break
        else:
            print(f"  {P} fetchInteractiveCoaching is called")
    else:
        print(f"  {F} fetchInteractiveCoaching not found in source")

    # Check for V2 debug logs
    if "[V2-DEBUG]" in fe_src:
        print(f"  {P} V2 debug console.logs present")
    else:
        print(f"  {F} No V2 debug logs")

    # Check for v2_label rendering
    if "v2_label" in fe_src:
        print(f"  {P} v2_label badge rendering present")
    else:
        print(f"  {F} v2_label NOT in frontend source")
else:
    print(f"  {F} Frontend source not found at {frontend_file}")

# 4. Is frontend BUILT with latest changes?
print("\n4. Frontend build check")
build_dir = "/app/frontend/build/static/js"
if os.path.exists(build_dir):
    js_files = [f for f in os.listdir(build_dir) if f.endswith('.js') and 'main' in f]
    if js_files:
        main_js_path = os.path.join(build_dir, js_files[0])
        with open(main_js_path, 'r', errors='ignore') as f:
            bundle = f.read()

        checks = {
            "V2-DEBUG": "[V2-DEBUG]" in bundle,
            "v2_label": "v2_label" in bundle,
            "v2_explanation": "v2_explanation" in bundle,
            "fetchInteractiveCoaching": "fetchInteractiveCoaching" in bundle,
            "SocraticCoaching": "SocraticCoaching" in bundle or "socratic_question" in bundle,
        }

        import time
        build_age = (time.time() - os.path.getmtime(main_js_path)) / 3600
        print(f"  Bundle: {js_files[0]} (age: {build_age:.1f} hours)")

        for term, found in checks.items():
            print(f"  {P if found else F} Bundle contains '{term}'")

        if not all(checks.values()):
            print(f"\n  ⚠️  Frontend needs rebuild: cd /app/frontend && npm run build")
    else:
        print(f"  {F} No main JS bundle found")
else:
    print(f"  {F} Build directory not found")

# 5. Coach move explanation — central layer
# Updated 2026-05-26 (PR-5): generate_coach_move_explanation deleted.
# Now: services/live_v5_teaching.coach_move_narration_for_live_move via
# the central caption_pipeline. Per [[one-source-of-truth-for-coaching]].
print("\n5. Coach move explanation function (central layer)")
try:
    from services.live_v5_teaching import coach_move_narration_for_live_move
    sig = inspect.signature(coach_move_narration_for_live_move)
    if "v2_context" in sig.parameters:
        print(f"  {P} Central layer wired — v2_context-aware, R17 templates")
    else:
        print(f"  {F} Central layer present but missing v2_context parameter")
except Exception as e:
    print(f"  {F} Central layer import failed: {e}")

# 6. Evaluate-pending layer thresholds
print("\n6. Evaluate-pending coaching layers")
from routes.coach_play import evaluate_pending_move
ep_src = inspect.getsource(evaluate_pending_move)

if "cp_loss_val >= 400" in ep_src:
    print(f"  {P} Critical only for 400cp+ (Socratic mode)")
elif "mistake" in ep_src and "critical_interrupt" in ep_src:
    # Check if ALL mistakes are critical
    lines = ep_src.split('\n')
    for line in lines:
        if 'mistake' in line and 'critical_interrupt' in line:
            print(f"  {F} All mistakes trigger critical_interrupt (old mode)")
            print(f"     → '{line.strip()}'")
            break
else:
    print(f"  ? Can't determine threshold")

# 7. Guardian mode
print("\n7. Pre-move guardian")
from coach_play.pre_move_guardian import PreMoveGuardian
g = PreMoveGuardian()
g_src = inspect.getsource(g._decide_intervention)
if "Socratic" in g_src or ("CRITICAL" in g_src and "NONE" in g_src and "HIGH" not in g_src.split("CRITICAL")[0]):
    print(f"  {P} Socratic mode — only CRITICAL blocks")
else:
    print(f"  {F} Old mode — HIGH/MEDIUM also block")

# 8. Move snapshots in interactive-feedback
print("\n8. Move snapshot storage")
try:
    from routes.coach_play import get_v5_interactive_feedback
    fb_src = inspect.getsource(get_v5_interactive_feedback)
    if "move_snapshots" in fb_src:
        print(f"  {P} Snapshots stored in interactive-feedback")
    else:
        print(f"  {F} No snapshot code in interactive-feedback")
except:
    print(f"  {F} Could not inspect interactive-feedback function")

# 9. Session promotion
print("\n9. Session → Game promotion")
try:
    from routes.coach_play import _promote_session_to_game
    print(f"  {P} _promote_session_to_game function exists")
except ImportError:
    print(f"  {F} _promote_session_to_game NOT found")

# 10. Quick live test — does v2 actually produce a move?
print("\n10. Live V2 selector test")
try:
    import chess
    board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    selector = TeachingMoveSelectorV2(user_rating=1172)
    result = selector.select_move(board=board, coach_color=chess.WHITE)
    print(f"  {P} V2 produced: {result.selected_san} (intent={result.intent.value}, rank={result.eval_rank})")
    selector._close_engine()
except Exception as e:
    print(f"  {F} V2 selector failed: {e}")

print("\n" + "=" * 60)
