"""The progress aggregator must survive unmeasured habits.

Habits we could not observe now store score=None instead of a fake 100.
`.get("score", 0)` does not protect against that - the default only applies
when the key is ABSENT, so a stored null passed straight into sum() and raised
TypeError. /thinking-score would have 500'd for any user whose recent games
contained an unmeasured habit. It had no frontend caller, so nothing broke in
production, but mounting the card would have exposed it immediately.
"""
import sys

sys.path.insert(0, "/app/backend")

from services.thinking_score import calculate_thinking_progress  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  -- " + detail) if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def game(ts, overall, **habits):
    """habits: name=score, where None means 'not measured this game'."""
    hs = {}
    for k, v in habits.items():
        hs[k] = {"score": v, "measured": v is not None,
                 "mistakes": 0, "opportunities": 20, "examples": []}
    return {"calculated_at": ts, "overall_score": overall, "habit_scores": hs,
            "total_moves": 20}


print("=== A. a null habit score must not crash the aggregate ===")
games = [
    game("2026-09-20T10:00:00", 80, threat_awareness=80, patience=None),
    game("2026-09-21T10:00:00", 70, threat_awareness=70, patience=None),
    game("2026-09-22T10:00:00", 60, threat_awareness=60, patience=50),
    game("2026-09-23T10:00:00", 90, threat_awareness=90, patience=None),
]
try:
    p = calculate_thinking_progress(games)
    check("A1 no exception", True)
    check("A2 reports data", p.get("has_enough_data") is True, str(p)[:120])
    check("A3 overall is a number", isinstance(p.get("overall_score"), (int, float)),
          str(p.get("overall_score")))
    pat = (p.get("habit_progress") or {}).get("patience")
    print("     patience entry:", pat)
except Exception as e:
    check("A1 no exception", False, "%s: %s" % (type(e).__name__, e))

print("\n=== B. a habit never measured is absent or null, never 0 ===")
games_b = [
    game("2026-09-20T10:00:00", 80, threat_awareness=80, tactical_vision=None),
    game("2026-09-21T10:00:00", 70, threat_awareness=70, tactical_vision=None),
    game("2026-09-22T10:00:00", 60, threat_awareness=60, tactical_vision=None),
    game("2026-09-23T10:00:00", 90, threat_awareness=90, tactical_vision=None),
]
try:
    p2 = calculate_thinking_progress(games_b)
    tv = (p2.get("habit_progress") or {}).get("tactical_vision")
    cur = (tv or {}).get("current_score") if isinstance(tv, dict) else None
    check("B1 no exception", True)
    check("B2 never-measured habit does not report 0", cur is None, "current_score=%s" % (cur,))
    check("B3 marked unmeasured", (tv or {}).get("measured") is False, str(tv))
    print("     tactical_vision entry:", tv)
except Exception as e:
    check("B1 no exception", False, "%s: %s" % (type(e).__name__, e))

print("\n=== C. every overall_score null -> honest 'not enough data' ===")
games_c = [game("2026-09-2%dT10:00:00" % i, None, threat_awareness=None) for i in range(4)]
try:
    p3 = calculate_thinking_progress(games_c)
    check("C1 no exception", True)
    check("C2 says not enough data", p3.get("has_enough_data") is False, str(p3)[:120])
except Exception as e:
    check("C1 no exception", False, "%s: %s" % (type(e).__name__, e))

print("\n%s (%d failures)" % ("ALL PASS" if not FAILS else "FAILURES: " + ", ".join(FAILS), len(FAILS)))
sys.exit(1 if FAILS else 0)
