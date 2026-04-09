"""
Test fast eval engine on production.
Diagnoses Stockfish availability and eval quality.

Usage:
  docker cp scripts/test_fast_eval.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/test_fast_eval.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

print("=" * 50)
print("FAST EVAL ENGINE DIAGNOSTIC")
print("=" * 50)

# Step 1: Check Stockfish binary
from config import STOCKFISH_PATH
print(f"\n1. Stockfish path: {STOCKFISH_PATH}")
print(f"   Exists: {os.path.exists(STOCKFISH_PATH)}")

if not os.path.exists(STOCKFISH_PATH):
    print("   FATAL: Stockfish not found!")
    # Try to find it
    import shutil
    found = shutil.which("stockfish")
    print(f"   shutil.which: {found}")
    sys.exit(1)

# Step 2: Test raw engine
print("\n2. Testing raw Stockfish engine...")
try:
    import chess.engine
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({"Threads": 1, "Hash": 64})
    print("   Engine started OK")

    board = chess.Board()
    info = engine.analyse(board, chess.engine.Limit(nodes=30000))
    score = info["score"].white()
    cp = score.score() if not score.is_mate() else 9999
    best = board.san(info["pv"][0]) if info.get("pv") else "?"
    print(f"   Starting position: eval={cp}cp, best={best}, depth={info.get('depth', '?')}")

    engine.quit()
    print("   Engine quit OK")
except Exception as e:
    print(f"   FATAL: {e}")
    sys.exit(1)

# Step 3: Test fast_eval function
print("\n3. Testing fast_eval function...")
from services.fast_eval_service import fast_eval

tests = [
    ("e2e4 (good)", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e2e4"),
    ("d7d5 vs e4 (good)", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "d7d5"),
    ("f2f3 (bad)", "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "f2f3"),
    ("Qh5 (dubious)", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1", "d1h5"),
]

all_ok = True
for desc, fen, uci in tests:
    start = time.monotonic()
    r = fast_eval(fen, uci)
    elapsed = (time.monotonic() - start) * 1000
    depth = r["depth"]
    cp_loss = r["cp_loss"]
    quality = r["move_quality"]
    best = r["best_move"]
    eval_b = r["eval_before"]
    eval_a = r["eval_after"]

    ok = depth > 0
    status = "OK" if ok else "FAIL"
    if not ok:
        all_ok = False

    print(f"   [{status}] {desc}")
    print(f"         depth={depth}, eval={eval_b:.2f}->{eval_a:.2f}, cp_loss={cp_loss}, quality={quality}, best={best}, {elapsed:.0f}ms")

# Step 4: Test signal detection
print("\n4. Testing signal detection...")
import chess
from services.fast_eval_service import detect_signals_fast

board_before = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
board_after = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/5P2/PPPP2PP/RNBQKBNR b KQkq - 0 2")
eval_r = {"cp_loss": 80, "move_quality": "inaccuracy", "best_move": "Nf3"}
signals = detect_signals_fast(board_before, board_after, chess.WHITE, eval_r)
print(f"   f3 signals: {signals}")

# Step 5: Performance
print("\n5. Performance test (10 calls)...")
times = []
for _ in range(10):
    start = time.monotonic()
    fast_eval("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "d7d5")
    times.append((time.monotonic() - start) * 1000)
avg = sum(times) / len(times)
p95 = sorted(times)[8]
print(f"   Avg: {avg:.0f}ms, P95: {p95:.0f}ms, Max: {max(times):.0f}ms")
print(f"   Target: P95 < 400ms -> {'PASS' if p95 < 400 else 'FAIL'}")

print("\n" + "=" * 50)
if all_ok:
    print("ALL TESTS PASSED - Engine is working")
else:
    print("TESTS FAILED - Engine has issues")
print("=" * 50)
