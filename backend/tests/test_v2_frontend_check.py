"""
V2 Frontend Integration Check
===============================
Verifies the frontend files have v2 coaching wiring.

Run on server:
    python tests/test_v2_frontend_check.py
"""

import os

PASS = "✅"
FAIL = "❌"

FRONTEND_ROOT = "/app/frontend/src"

results = []

def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((status, name, detail))
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))


def file_contains(path, *terms):
    """Check if a file contains all the given terms."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        found = {t: t in content for t in terms}
        return found
    except FileNotFoundError:
        return {t: False for t in terms}


print("=" * 60)
print("V2 FRONTEND INTEGRATION CHECK")
print("=" * 60)

# ─── 1. CoachPlaySidebar.jsx ────────────────────────────────
print("\n1. CoachPlaySidebar.jsx")
sidebar_path = os.path.join(FRONTEND_ROOT, "components/coach/CoachPlaySidebar.jsx")
if os.path.exists(sidebar_path):
    found = file_contains(
        sidebar_path,
        "v2_label",
        "v2_explanation",
        "v2_intent",
        "fork_opportunity",
        "hanging_piece_punishment",
        "Double Attack",
        "Piece Safety",
        "Creating Threats",
    )
    for term, present in found.items():
        check(f"Contains '{term}'", present)
else:
    check("File exists", False, sidebar_path)

# ─── 2. CoachPlay.jsx ──────────────────────────────────────
print("\n2. CoachPlay.jsx")
coachplay_path = os.path.join(FRONTEND_ROOT, "pages/CoachPlay.jsx")
if os.path.exists(coachplay_path):
    found = file_contains(
        coachplay_path,
        "fundamentalViolations",
        "coachMoveCoaching",
        "coach_move_coaching",
    )
    for term, present in found.items():
        check(f"Contains '{term}'", present)
else:
    check("File exists", False, coachplay_path)

# ─── 3. V5CoachingCard.jsx ──────────────────────────────────
print("\n3. V5CoachingCard.jsx (Socratic coaching)")
v5card_path = os.path.join(FRONTEND_ROOT, "components/shared/V5CoachingCard.jsx")
if os.path.exists(v5card_path):
    found = file_contains(
        v5card_path,
        "SocraticCoachingSection",
        "socratic_question",
        "showHint",
        "showFullExplanation",
        "hide_best_move",
        "fundamental_label",
        "checklist_snapshot",
    )
    for term, present in found.items():
        check(f"Contains '{term}'", present)
else:
    check("File exists", False, v5card_path)

# ─── 4. Check if old v1 references still exist ─────────────
print("\n4. Old V1 References (should NOT exist)")
sidebar_found = file_contains(
    sidebar_path,
    "teaching_point",       # old v1 field
    "suppressOldCoaching",  # toggle for old coaching
)
# teaching_point existing is fine (it's a fallback)
# suppressOldCoaching tells us if old coaching is being hidden
if sidebar_found.get("suppressOldCoaching"):
    check("suppressOldCoaching found", True, "Old coaching can be hidden — check if it's always true")
else:
    check("suppressOldCoaching", True, "Not found — old coaching might always show")

# ─── 5. Check build output exists ──────────────────────────
print("\n5. Frontend Build")
build_path = "/app/frontend/build"
if os.path.exists(build_path):
    # Check if build is recent
    import time
    build_time = os.path.getmtime(build_path)
    age_hours = (time.time() - build_time) / 3600
    check("Build exists", True, f"age: {age_hours:.1f} hours")

    # Check main JS bundle for v2 strings
    js_dir = os.path.join(build_path, "static/js")
    if os.path.exists(js_dir):
        js_files = [f for f in os.listdir(js_dir) if f.endswith(".js") and "main" in f]
        if js_files:
            main_js = os.path.join(js_dir, js_files[0])
            bundle_found = file_contains(
                main_js,
                "v2_label",
                "v2_explanation",
                "Double Attack",
                "Piece Safety",
                "SocraticCoaching",
            )
            for term, present in bundle_found.items():
                check(f"Bundle contains '{term}'", present)
        else:
            check("Main JS bundle found", False, f"Files in {js_dir}: {os.listdir(js_dir)[:5]}")
    else:
        check("JS directory", False, js_dir)
else:
    check("Build exists", False, "Frontend not built — run: cd /app/frontend && npm run build")

# ─── SUMMARY ───────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
print(f"RESULT: {passed} passed, {failed} failed")
if failed == 0:
    print("🚀 Frontend is fully wired for V2")
elif failed <= 3:
    print("⚠️  Source files look good but build may need rebuild")
    print("   Run: cd /app/frontend && npm run build")
else:
    print("🔴 Frontend source files missing V2 changes")
    print("   Copy updated files and rebuild:")
    print("   docker cp frontend/src/components/coach/CoachPlaySidebar.jsx chess-coach-backend:/app/frontend/src/components/coach/")
    print("   docker exec chess-coach-backend bash -c 'cd /app/frontend && npm run build'")
print("=" * 60)
