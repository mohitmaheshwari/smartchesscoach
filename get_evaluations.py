#!/usr/bin/env python3
"""Get evaluations for both moves"""
import chess
import subprocess

fen = "r1bqkbnr/ppp3pp/2n5/4P3/2Pp4/5N2/PP2PPPP/RNBQKB1R w - - 0 1"
board = chess.Board(fen)

print("STOCKFISH EVALUATION ANALYSIS")
print("="*60)
print()

def analyze_move(move_uci, move_name):
    """Analyze a position after a move"""
    board_copy = board.copy()
    move = chess.Move.from_uci(move_uci)
    board_copy.push(move)

    # Run stockfish to get evaluation of position after move
    result = subprocess.run(
        ['/usr/games/stockfish'],
        input=f"position fen {board_copy.fen()}\ngo depth 20\n",
        capture_output=True,
        text=True,
        timeout=10
    )

    output = result.stdout

    # Extract score
    score = None
    for line in output.split('\n'):
        if 'info depth 20' in line and 'score' in line:
            # Extract cp value
            if 'cp ' in line:
                parts = line.split('cp ')
                if len(parts) > 1:
                    score_str = parts[1].split()[0]
                    try:
                        score = int(score_str)
                    except:
                        pass

    print(f"Move: {move_name}")
    print(f"  UCI: {move_uci}")
    print(f"  Position FEN: {board_copy.fen()}")
    if score is not None:
        print(f"  Engine evaluation (white perspective): +{score}cp" if score > 0 else f"  Engine evaluation (white perspective): {score}cp")
    else:
        print(f"  Engine evaluation: Could not parse")
    print()

    return score

# Analyze both moves
score_a3 = analyze_move('a2a3', 'a3 (pawn move)')
score_nxd4 = analyze_move('f3d4', 'Nxd4 (knight captures)')

# Compare
print("="*60)
print("COMPARISON:")
print("="*60)
print()

if score_a3 is not None and score_nxd4 is not None:
    diff = score_a3 - score_nxd4
    if diff > 0:
        print(f"a3 is better by: +{diff}cp")
        print(f"Classification of Nxd4: MISTAKE/BLUNDER (worse by {diff}cp)")
    else:
        print(f"Nxd4 is better by: +{-diff}cp")
else:
    print("Could not parse evaluations")

print()
print("="*60)
print("WHAT THE CAPTION SHOULD SAY:")
print("="*60)
print()
print("Move: Nxd4")
print("Classification: [DETERMINED BY cp_loss]")
print("Best Move: a3")
print("Why: [MUST EXPLAIN THE REAL POSITION REASON]")
print()
print("To get the real 'why', we need to analyze:")
print("  - What threats does a3 create?")
print("  - What weaknesses does a3 exploit?")
print("  - Why is Nxd4 inferior?")
print()
print("This requires POSITION ANALYSIS, not just cp scores.")
