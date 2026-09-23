"""The five thinking habits must be reachable, and an unmeasured habit must
never score.

Before 2026-09-23 three of the five had never fired once in 4,000 games:
_categorize_mistake read `move_eval["category"]` and `move_eval["insight"]`,
neither of which any move evaluation carries (measured 0 of 12,365 user moves
for both; `cognitive_gap` was present on 2,154). Only two branches were
reachable, so tactical_vision, king_safety and patience scored a constant 100
and together carried 55% of overall_score.
"""
import sys

sys.path.insert(0, "/app/backend")

from services.thinking_score import (  # noqa: E402
    ThinkingHabit, _categorize_mistake, calculate_game_thinking_scores,
)

FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  -- " + detail) if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def moves(n, gap=None, cp=0, seconds=None):
    out = []
    for i in range(n):
        m = {"move_number": i + 1, "move": "Nf3", "cp_loss": cp}
        if gap:
            m["cognitive_gap"] = gap
        if seconds is not None:
            m["time_spent_seconds"] = seconds
        out.append(m)
    return out


print("=== A. every habit is reachable from a real cognitive_gap ===")
for gap, want in (("missed_tactic", ThinkingHabit.TACTICAL_VISION),
                  ("tactical_oversight", ThinkingHabit.TACTICAL_VISION),
                  ("piece_safety", ThinkingHabit.THREAT_AWARENESS),
                  ("king_safety", ThinkingHabit.KING_SAFETY),
                  ("calculation_depth", ThinkingHabit.MOVE_VERIFICATION)):
    got = _categorize_mistake({"cognitive_gap": gap, "cp_loss": 150}, {})
    check("A %-20s -> %s" % (gap, want.value), got == want, str(got))

print("\n=== B. knowledge gaps are NOT forced into a thinking habit ===")
for gap in ("opening_knowledge", "endgame_technique", "pawn_structure"):
    got = _categorize_mistake({"cognitive_gap": gap, "cp_loss": 120}, {})
    # falls through to the legacy heuristics, must not claim tactical/king
    check("B %-20s not mis-assigned" % gap,
          got not in (ThinkingHabit.TACTICAL_VISION, ThinkingHabit.KING_SAFETY),
          str(got))

print("\n=== C. an unmeasured habit scores None, never 100 ===")
res = calculate_game_thinking_scores(
    {"game_id": "g", "move_evaluations": moves(20, cp=0), "critical_moments": []}, "white")
pat = res["habit_scores"]["patience"]
check("C1 patience unmeasured without clocks", pat["measured"] is False, str(pat))
check("C2 patience score is None, not 100", pat["score"] is None, str(pat["score"]))
check("C3 patience excluded from measured_habits",
      "patience" not in res["measured_habits"], str(res["measured_habits"]))

print("\n=== D. patience is measured when clocks exist, and fires on fast errors ===")
mv = moves(10, cp=0, seconds=10.0) + moves(4, gap="missed_tactic", cp=200, seconds=0.5)
res2 = calculate_game_thinking_scores(
    {"game_id": "g2", "move_evaluations": mv, "critical_moments": []}, "white")
p2 = res2["habit_scores"]["patience"]
check("D1 patience now measured", p2["measured"] is True, str(p2))
check("D2 fast blunders counted against patience", (p2["mistakes"] or 0) > 0, str(p2))
check("D3 patience in measured_habits", "patience" in res2["measured_habits"])

print("\n=== E. slow errors do NOT count against patience ===")
mv3 = moves(10, cp=0, seconds=10.0) + moves(4, gap="missed_tactic", cp=200, seconds=30.0)
res3 = calculate_game_thinking_scores(
    {"game_id": "g3", "move_evaluations": mv3, "critical_moments": []}, "white")
p3 = res3["habit_scores"]["patience"]
check("E1 thinking long is not impatience", (p3["mistakes"] or 0) == 0, str(p3))

print("\n=== F. overall_score ignores unmeasured habits (no free 100s) ===")
res4 = calculate_game_thinking_scores(
    {"game_id": "g4", "move_evaluations": moves(20, gap="piece_safety", cp=400),
     "critical_moments": []}, "white")
check("F1 overall is not inflated toward 100",
      res4["overall_score"] is not None and res4["overall_score"] < 60,
      str(res4["overall_score"]))
check("F2 patience not silently averaged in",
      "patience" not in res4["measured_habits"], str(res4["measured_habits"]))

print("\n%s (%d failures)" % ("ALL PASS" if not FAILS else "FAILURES: " + ", ".join(FAILS), len(FAILS)))
sys.exit(1 if FAILS else 0)
