#!/usr/bin/env python3
"""Analyze the puzzle position with Stockfish"""
import chess
import subprocess
import os

# FEN from the board image:
# Rank 8: r1bqkbnr (Ra8, Bc8, Qd8, Ke8, Bf8, Ng8, Rh8)
# Rank 7: ppp3pp (Pa7, Pb7, Pc7, Pf7, Pg7, Ph7)
# Rank 6: 2n5 (Nc6)
# Rank 5: 4P3 (Pe5 white)
# Rank 4: 2Pp3 (Pc4 white, Pd4 black)
# Rank 3: 5N2 (Nf3 white)
# Rank 2: PP2PPPP (Pa2, Pb2, Pe2, Pf2, Pg2, Ph2)
# Rank 1: RNBQKB1R (Ra1, Nb1, Bc1, Qd1, Ke1, Bf1, Rh1)

fen = "r1bqkbnr/ppp3pp/2n5/4P3/2Pp4/5N2/PP2PPPP/RNBQKB1R w - - 0 1"

print("Analyzing puzzle position with Stockfish...")
print(f"FEN: {fen}")
print()

board = chess.Board(fen)
print("Board state:")
print(board)
print()

# Run Stockfish analysis
try:
    result = subprocess.run(
        ['/usr/games/stockfish'],
        input=f"position fen {fen}\ngo depth 20\n",
        capture_output=True,
        text=True,
        timeout=10
    )

    output = result.stdout + result.stderr

    # Extract bestmove from output
    for line in output.split('\n'):
        if 'info depth' in line and 'score' in line:
            print(f"Analysis: {line}")
        if 'bestmove' in line:
            print(f"\nBest move: {line}")

except Exception as e:
    print(f"Error running Stockfish: {e}")

print("\n" + "="*60)
print("EVALUATING THE MOVES:")
print("="*60)

# Check Nxd4 (user's move)
if 'Nxd4' in board.san(chess.Move.from_uci('f3d4')):
    move_nxd4 = chess.Move.from_uci('f3d4')
    board_after = board.copy()
    board_after.push(move_nxd4)
    print(f"\nUser played: Nxd4")
    print(f"Position after Nxd4:")
    print(board_after)

# Check a3 (suggested best move)
move_a3 = chess.Move.from_uci('a2a3')
if move_a3 in board.legal_moves:
    board_after_a3 = board.copy()
    board_after_a3.push(move_a3)
    print(f"\nSuggested best move: a3")
    print(f"Position after a3:")
    print(board_after_a3)
else:
    print("\na3 is NOT a legal move in this position")

print("\n" + "="*60)
print("REAL ANSWER:")
print("="*60)
print("Query Stockfish to get:")
print("1. Is a3 really the best move?")
print("2. What is the evaluation of Nxd4 vs a3?")
print("3. WHY is one better than the other?")
print("\nThis is what the caption pipeline must show.")
