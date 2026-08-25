"""Tests for the piece-safety rep generator.

Positions are hand-constructed so the expected answer is verifiable by eye:

    8/8/4p3/8/8/8/8/3QK2k w - - 0 1

White queen d1, white king e1, black pawn e6, black king h1.
The e6 pawn covers d5 and f5 only.

  Qd5  -> exd5 wins the queen outright. A hang, no defender.

A second position supplies the contested-but-safe case; see FEN_SAFE below.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.rep_generator import (  # noqa: E402
    AMBIGUOUS_SEE_LOW,
    _evaluate_candidate,
    _is_clean,
    _is_miss,
    build_rep,
    build_safe_alternatives,
    generate_reps_from_candidates,
)

FEN = "8/8/4p3/8/8/8/8/3QK2k w - - 0 1"
HANG = "d1d5"   # queen walks onto the pawn's square

# A "safe" rep must still be a REAL decision: the piece has to move somewhere
# contested and survive. Qd4 above is not contested at all (nothing attacks d4),
# so the generator correctly refuses it — that is not a piece-safety decision.
#
#     1b5k/8/8/8/3P4/3N4/8/4K3 w - - 0 1
#
# White knight d3, white pawn d4, black bishop b8.
#   Ne5 -> the bishop attacks e5, but the d4 pawn defends it.
#          Bxe5 dxe5 loses a bishop for a knight, so SEE is 0. Contested, safe.
FEN_SAFE = "1b5k/8/8/8/3P4/3N4/8/4K3 w - - 0 1"
SAFE = "d3e5"

failures = []


def check(name, cond):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}")
        failures.append(name)


print("rep_generator")

# ── board facts ───────────────────────────────────────────────────────────────
facts_hang = _evaluate_candidate(FEN, HANG, cp_loss=900)
check("hang: candidate evaluates", facts_hang is not None)
check("hang: SEE wins the queen", facts_hang and facts_hang["see_cp"] >= 900)
check("hang: attacker square is e6", facts_hang and facts_hang["attacker_square"] == "e6")
check("hang: destination is attacked", facts_hang and facts_hang["destination_attacked"])
check("hang: counts as a miss", facts_hang and _is_miss(facts_hang))

facts_safe = _evaluate_candidate(FEN_SAFE, SAFE, cp_loss=10)
check("safe: candidate evaluates", facts_safe is not None)
check("safe: destination is contested", facts_safe and facts_safe["destination_attacked"])
check("safe: counts as clean", facts_safe and _is_clean(facts_safe))
check("safe: nothing hangs", facts_safe and facts_safe["see_cp"] < AMBIGUOUS_SEE_LOW)
check("safe: not a miss", facts_safe and not _is_miss(facts_safe))

# ── both gates are required, never one alone ─────────────────────────────────
# A real hang by SEE that the engine says costs nothing is a compensated
# sacrifice, not a piece-safety error. 48% of raw SEE hangs in the corpus were
# exactly this.
compensated = dict(facts_hang or {}, cp_loss=20)
check("compensated sacrifice is NOT a miss", not _is_miss(compensated))
check("missing cp_loss is NOT a miss", not _is_miss(dict(facts_hang or {}, cp_loss=None)))

# ── rejection gates ───────────────────────────────────────────────────────────
# d1d8 IS legal here (the d-file is empty) - use a move that is not a queen line.
check("illegal move rejected", _evaluate_candidate(FEN, "d1a8", 900) is None)
check("garbage uci rejected", _evaluate_candidate(FEN, "zz", 900) is None)
check("bad fen rejected", _evaluate_candidate("not-a-fen", HANG, 900) is None)
check(
    "pawn move rejected (ineligible piece)",
    _evaluate_candidate("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1", "e2e4", 900) is None,
)

# ── reps ──────────────────────────────────────────────────────────────────────
rep = build_rep(facts_hang, "is_safe", "test")
check("is_safe rep built", rep is not None)
check("is_safe answer is not_safe", rep and rep["answer"] == "not_safe")
check("is_safe prompt names the move", rep and "Qd5" in rep["prompt"])
check(
    "is_safe prompt does not leak the answer",
    rep and not any(w in rep["prompt"].lower() for w in ("hang", "unsafe", "blunder", "e6")),
)
check("rep carries the fact version", rep and rep["fact_version"] == "piece_safety.d_live.v1")
check(
    "demonstration shows the capture",
    rep and rep["demonstration"].get("capture_uci", "").startswith("e6"),
)

safe_rep = build_rep(facts_safe, "is_safe", "test")
check("safe rep answer is safe", safe_rep and safe_rep["answer"] == "safe")

who = build_rep(facts_hang, "who_takes", "test")
check("who_takes answers e6", who and who["answer"] == "e6")
check("who_takes on a safe move is refused", build_rep(facts_safe, "who_takes", "test") is None)

loose = build_rep(facts_hang, "find_loose", "test")
check("find_loose answers d5", loose and loose["answer"] == "d5")

check("unknown rep type refused", build_rep(facts_hang, "nonsense", "test") is None)

# ── safe alternatives ─────────────────────────────────────────────────────────
alts = build_safe_alternatives(FEN, HANG, limit=3)
check("safe alternatives found", len(alts) > 0)
check("alternatives exclude the played move", all(a["uci"] != HANG for a in alts))
check("alternatives are all queen moves", all(a["uci"].startswith("d1") for a in alts))

# ── balance ───────────────────────────────────────────────────────────────────
cands = [{"fen": FEN, "move_uci": HANG, "cp_loss": 900}] * 8 + [
    {"fen": FEN_SAFE, "move_uci": SAFE, "cp_loss": 10}
] * 8
reps = generate_reps_from_candidates(cands, rep_types=("is_safe",), count=8, seed=1)
answers = [r["answer"] for r in reps]
check("balanced set returns 8", len(reps) == 8)
check("balanced set contains both answers", "safe" in answers and "not_safe" in answers)
check("no answer dominates", 2 <= answers.count("not_safe") <= 6)

reps_b = generate_reps_from_candidates(cands, rep_types=("is_safe",), count=8, seed=1)
check("same seed is deterministic", [r["answer"] for r in reps_b] == answers)

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("all rep_generator tests passed")
