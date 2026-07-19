"""
Diagnostic V2 unit tests — grading, staircase, gating, scoring.

Run (inside the backend container or any env with python-chess):
    python3 tests/test_diagnostic_v2.py

Engine-free: DiagnosticGrader takes an injected eval_fn, so every case
is deterministic. The fork fixture is a real curated pool doc
(lichess_9kjoP) with its true depth-16 multipv baselines.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.diagnostic_service import (  # noqa: E402
    DiagnosticGrader,
    next_tier,
    concept_done,
    concept_level,
    estimate_rating_v2,
    score_diagnostic_v2,
    CONCEPT_PRIORITY,
)

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f" FAIL {name} {detail}")


# Real curated pool doc (fork @ mid): Qc5+ forks; 316cp vs 17cp 2nd-best.
FORK_PUZZLE = {
    "puzzle_id": "lichess_9kjoP",
    "concept": "fork",
    "fen": "2k2r1r/pbpnqpbp/1p4p1/1B1Pp3/4P3/2P2NQ1/PP1N2PP/R4RK1 b - - 7 15",
    "moves": ["e7c5", "f3d4", "e5d4"],
    "solution_san": "Qc5+",
    "user_move_idx": 0,
    "puzzle_rating": 1236,
    "tier": "mid",
    "multipv": [
        {"move_uci": "e7c5", "move_san": "Qc5+", "eval_cp": 316, "mate_in": None},
        {"move_uci": "f7f5", "move_san": "f5", "eval_cp": 17, "mate_in": None},
        {"move_uci": "c8b8", "move_san": "Kb8", "eval_cp": -9, "mate_in": None},
    ],
    "eval_before": 3.16,
}

# Mate-in-1 fixture: back-rank Ra8#.
MATE_PUZZLE = {
    "puzzle_id": "test_mate1",
    "concept": "mate_patterns",
    "fen": "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1",
    "moves": ["a1a8"],
    "solution_san": "Ra8#",
    "user_move_idx": 0,
    "puzzle_rating": 850,
    "tier": "low",
    "multipv": [
        {"move_uci": "a1a8", "move_san": "Ra8#", "eval_cp": 9990, "mate_in": 1},
    ],
    "eval_before": 99.9,
}


def eval_stub(value):
    """eval_fn that always returns `value` (records calls)."""
    calls = []

    def fn(fen, solver):
        calls.append(fen)
        return value

    fn.calls = calls
    return fn


def test_grading():
    print("\n_grade_move_consequence:")

    # 1. Exact solution → UNDERSTOOD, cp_loss 0, NO engine call
    fn = eval_stub(0)
    g = DiagnosticGrader(eval_fn=fn)
    r = g._grade_move_consequence("Qc5+", FORK_PUZZLE)
    check("exact solution = UNDERSTOOD", r["verdict"] == "UNDERSTOOD", r)
    check("exact solution cp_loss = 0", r["cp_loss"] == 0)
    check("exact solution is_exact", r["is_exact"])
    check("exact solution: no engine call", len(fn.calls) == 0)
    check("exact explanation mentions solution", "Qc5+" in r["explanation"], r["explanation"])
    check("exact explanation names the fork", "fork" in r["explanation"], r["explanation"])

    # UCI input accepted too
    r = g._grade_move_consequence("e7c5", FORK_PUZZLE)
    check("UCI input accepted", r["verdict"] == "UNDERSTOOD" and r["is_exact"])

    # 2. Equivalent-strength move (eval within 50cp of solution) → UNDERSTOOD
    g = DiagnosticGrader(eval_fn=eval_stub(280))
    r = g._grade_move_consequence("f5", FORK_PUZZLE)
    check("equivalent move = UNDERSTOOD", r["verdict"] == "UNDERSTOOD", r)
    check("equivalent not exact", not r["is_exact"])

    # 3. PARTIAL: sign unchanged, cp_loss between thresholds (75..200 @1236)
    g = DiagnosticGrader(eval_fn=eval_stub(200))  # cp_loss 116
    r = g._grade_move_consequence("f5", FORK_PUZZLE)
    check("mid cp_loss = PARTIAL", r["verdict"] == "PARTIAL", r)
    check("partial explanation has better move", "Qc5+" in r["explanation"], r["explanation"])

    # 4. MISSING: advantage gone (sign flips) — the puzzle's real 2nd-best
    g = DiagnosticGrader(eval_fn=eval_stub(17))
    r = g._grade_move_consequence("f5", FORK_PUZZLE)
    check("advantage-gone move = MISSING", r["verdict"] == "MISSING", r)

    # 5. MISSING: outright losing move
    g = DiagnosticGrader(eval_fn=eval_stub(-350))
    r = g._grade_move_consequence("Kb8", FORK_PUZZLE)
    check("losing move = MISSING", r["verdict"] == "MISSING", r)
    check("missing explanation shows the idea", "Qc5+" in r["explanation"], r["explanation"])

    # 6. Illegal move → ValueError
    try:
        g._grade_move_consequence("Qh1", FORK_PUZZLE)
        check("illegal move raises", False)
    except ValueError:
        check("illegal move raises", True)

    # 7. Mate puzzle: exact mate → UNDERSTOOD; checkmate branch skips engine
    fn = eval_stub(-999)
    g = DiagnosticGrader(eval_fn=fn)
    r = g._grade_move_consequence("Ra8#", MATE_PUZZLE)
    check("exact mate = UNDERSTOOD", r["verdict"] == "UNDERSTOOD", r)
    check("mate explanation says checkmate", "checkmate" in r["explanation"], r["explanation"])

    # 8. Mid-walk grading: pass a later fen + solution move explicitly.
    #    Position after 1...Qc5+ 2.Nd4: solution exd4 recaptures the knight.
    import chess
    b = chess.Board(FORK_PUZZLE["fen"])
    b.push(chess.Move.from_uci("e7c5"))
    b.push(chess.Move.from_uci("f3d4"))
    walk_fen = b.fen()
    fn = eval_stub(300)
    g = DiagnosticGrader(eval_fn=fn)
    r = g._grade_move_consequence("exd4", FORK_PUZZLE, walk_fen, "e5d4")
    check("mid-walk exact = UNDERSTOOD", r["verdict"] == "UNDERSTOOD" and r["is_exact"], r)


def test_staircase():
    print("\ntier staircase:")
    check("mid + UNDERSTOOD -> high", next_tier("mid", "UNDERSTOOD") == "high")
    check("mid + MISSING -> low", next_tier("mid", "MISSING") == "low")
    check("mid + PARTIAL -> mid", next_tier("mid", "PARTIAL") == "mid")
    check("high + UNDERSTOOD stays high", next_tier("high", "UNDERSTOOD") == "high")
    check("low + MISSING stays low", next_tier("low", "MISSING") == "low")


def test_gating():
    print("\nconsistency gating:")
    check("[U,U] done, no adaptive", concept_done(["UNDERSTOOD", "UNDERSTOOD"]) == (True, False))
    check("[M,M] done, no adaptive", concept_done(["MISSING", "MISSING"]) == (True, False))
    check("[U,M] adaptive 3rd", concept_done(["UNDERSTOOD", "MISSING"]) == (False, True))
    check("[P,P] adaptive 3rd", concept_done(["PARTIAL", "PARTIAL"]) == (False, True))
    check("one verdict = keep going", concept_done(["UNDERSTOOD"]) == (False, False))
    check("three verdicts = done", concept_done(["UNDERSTOOD", "MISSING", "PARTIAL"])[0])

    check("level [U,U] solid", concept_level(["UNDERSTOOD", "UNDERSTOOD"]) == "solid")
    check("level [M,M] missing", concept_level(["MISSING", "MISSING"]) == "missing")
    check("level [U,M,U] developing", concept_level(["UNDERSTOOD", "MISSING", "UNDERSTOOD"]) == "developing")
    check("level [U,M,M] missing", concept_level(["UNDERSTOOD", "MISSING", "MISSING"]) == "missing")
    check("level [P,P,P] developing", concept_level(["PARTIAL", "PARTIAL", "PARTIAL"]) == "developing")


def test_rating_estimate():
    print("\nrating estimate:")
    attempts = [
        {"verdict": "UNDERSTOOD", "puzzle_rating": 1200, "tier": "mid"},
        {"verdict": "MISSING", "puzzle_rating": 1600, "tier": "high"},
    ]
    r = estimate_rating_v2(attempts)  # midpoint 1400 → 1300-1500
    check("pass@1200 fail@1600 -> 1300-1500", r == {"low": 1300, "high": 1500}, r)

    r = estimate_rating_v2([{"verdict": "UNDERSTOOD", "puzzle_rating": 1600, "tier": "high"}])
    check("all passed -> above highest tier", r["low"] >= 1600, r)

    r = estimate_rating_v2([{"verdict": "MISSING", "puzzle_rating": 800, "tier": "low"}])
    check("all failed -> below lowest tier", r["high"] <= 800, r)

    r = estimate_rating_v2([])
    check("no attempts -> sane default", 600 <= r["low"] < r["high"] <= 1900, r)


def test_scoring():
    print("\nscore_diagnostic_v2:")
    session = {
        "attempts": [
            {"verdict": "UNDERSTOOD", "puzzle_rating": 1200, "tier": "mid", "concept": "fork"},
            {"verdict": "UNDERSTOOD", "puzzle_rating": 1600, "tier": "high", "concept": "fork"},
            {"verdict": "MISSING", "puzzle_rating": 1200, "tier": "mid", "concept": "threat_response"},
            {"verdict": "MISSING", "puzzle_rating": 800, "tier": "low", "concept": "threat_response"},
            {"verdict": "PARTIAL", "puzzle_rating": 1200, "tier": "mid", "concept": "pin"},
            {"verdict": "UNDERSTOOD", "puzzle_rating": 1200, "tier": "mid", "concept": "pin"},
            {"verdict": "MISSING", "puzzle_rating": 1600, "tier": "high", "concept": "pin"},
        ],
        "concept_progress": {
            "fork": {"verdicts": ["UNDERSTOOD", "UNDERSTOOD"], "tiers": ["mid", "high"], "done": True},
            "threat_response": {"verdicts": ["MISSING", "MISSING"], "tiers": ["mid", "low"], "done": True},
            "pin": {"verdicts": ["PARTIAL", "UNDERSTOOD", "MISSING"], "tiers": ["mid", "mid", "high"], "done": True},
        },
    }
    d = score_diagnostic_v2(session)
    pc = d["per_concept"]
    check("fork solid", pc["fork"]["level"] == "solid", pc.get("fork"))
    check("fork verdict symbols", pc["fork"]["verdicts"] == ["✓", "✓"])
    check("fork tier_passed 1600", pc["fork"]["tier_passed"] == 1600)
    check("threat_response missing", pc["threat_response"]["level"] == "missing")
    check("threat_response tier_passed None", pc["threat_response"]["tier_passed"] is None)
    check("pin developing", pc["pin"]["level"] == "developing", pc.get("pin"))
    check("headline gap = threat_response (priority)", d["headline_gap"] == "threat_response", d["headline_gap"])
    check("blunder_rate 3/7", d["blunder_rate"] == round(3 / 7, 2), d["blunder_rate"])
    check("rating estimate present", "low" in d["rating_estimate"] and "high" in d["rating_estimate"])
    check("summary mentions the gap", "threat" in d["summary"].lower(), d["summary"])

    # priority ordering sanity
    check("threat_response first in priority", CONCEPT_PRIORITY[0] == "threat_response")


def test_overall_verdict():
    print("\nmulti-move aggregation:")
    from routes.diagnostic import _v2_overall_verdict
    check("all U -> UNDERSTOOD", _v2_overall_verdict(["UNDERSTOOD", "UNDERSTOOD"]) == "UNDERSTOOD")
    check("any M -> MISSING", _v2_overall_verdict(["UNDERSTOOD", "MISSING"]) == "MISSING")
    check("U+P -> PARTIAL", _v2_overall_verdict(["UNDERSTOOD", "PARTIAL"]) == "PARTIAL")


if __name__ == "__main__":
    test_grading()
    test_staircase()
    test_gating()
    test_rating_estimate()
    test_scoring()
    try:
        test_overall_verdict()
    except ImportError as e:
        print(f"\nmulti-move aggregation: skipped (route deps unavailable: {e})")
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
