"""What the stored punishment line can and cannot claim.

I originally asserted "the stored reply is the runner-up, the real best is X".
That was wrong, and the way it was wrong is the point:

  position 1, after 6.Qd2, depth 18
      MCP engine      : h6 +494, Bxc4 +438   -> h6 best by 56cp
      production engine: Bxc4 279, h6 271    -> Bxc4 best by 8cp

Two engines, same depth, opposite orderings. So "the stored move is wrong" was
never a safe claim. The safe claim is that these two replies are TIED, and
which one surfaces depends on the engine and the depth - which is exactly why
storing one move and presenting it as "what the opponent does" is the bug.

These cases assert the honest property: when the top two are close, the tie
flag must say so; when there is a real gap, it must say that instead.
"""
import sys
sys.path.insert(0, "/app/backend")
import chess
from stockfish_service import StockfishEngine, PUNISHMENT_DEPTH, REPLY_TIE_CP

CASES = [
    # (name, fen after the played move, expect_clear)
    ("pos 1 - after 6.Qd2  (Bxc4 vs h6, teaches different lessons)",
     "rn2kbnr/ppp2ppp/3pb1q1/4p1B1/2B1P3/3P1N2/PPPQ1PPP/RN2K2R b KQkq - 4 6",
     False),
    ("pos 2 - after 24.Nxa7 (Qd7 vs Qd5)",
     "1k1r1b1r/N5p1/1p3p1p/2p2q2/2Q5/1P6/2P2PPP/R4RK1 b - - 0 24",
     True),
]

FAILS = []
print("PUNISHMENT_DEPTH=%d  REPLY_TIE_CP=%d\n" % (PUNISHMENT_DEPTH, REPLY_TIE_CP))

with StockfishEngine() as eng:
    for name, fen, expect_clear in CASES:
        b = chess.Board(fen)
        old = eng.get_top_replies(b, num=3, depth=12)
        new = eng.get_top_replies(b, num=3, depth=PUNISHMENT_DEPTH)
        print("=== %s ===" % name)
        print("  depth 12 : %s" % ", ".join("%s %s" % (r["move_san"], r["eval_cp"]) for r in old))
        print("  depth %d : %s" % (PUNISHMENT_DEPTH,
              ", ".join("%s %s" % (r["move_san"], r["eval_cp"]) for r in new)))

        # the helper must return several replies, not one
        if len(new) < 2:
            print("  FAIL returned %d replies, need >= 2" % len(new))
            FAILS.append(name + " [too few replies]")
            continue

        gap = abs(new[0]["eval_cp"] - new[1]["eval_cp"])
        clear = gap > REPLY_TIE_CP
        print("  top=%s  2nd=%s  gap=%dcp  is_clear=%s (expected %s)"
              % (new[0]["move_san"], new[1]["move_san"], gap, clear, expect_clear))
        if clear != expect_clear:
            FAILS.append(name)
            print("  FAIL")
        else:
            print("  PASS")
            if not clear:
                print("       -> caption and arrows must NOT name one of these as"
                      " 'what the opponent does'")
        # ordering must be honest: best first
        if new[0]["eval_cp"] < new[1]["eval_cp"]:
            FAILS.append(name + " [not sorted best-first]")
            print("  FAIL replies are not sorted best-first")
        print()

print("%s (%d failures)" % ("ALL PASS" if not FAILS else "FAILURES: " + "; ".join(FAILS), len(FAILS)))
sys.exit(1 if FAILS else 0)
