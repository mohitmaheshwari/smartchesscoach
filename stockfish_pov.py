#!/usr/bin/env python3
"""Show Stockfish's perspective on both moves"""
import chess
import subprocess

fen = "r1bqkbnr/ppp3pp/2n5/4P3/2Pp4/5N2/PP2PPPP/RNBQKB1R w - - 0 1"

def get_stockfish_analysis(position_fen, depth=20):
    """Get Stockfish's analysis: evaluation + best line"""

    result = subprocess.run(
        ['/usr/games/stockfish'],
        input=f"position fen {position_fen}\ngo depth {depth}\n",
        capture_output=True,
        text=True,
        timeout=15
    )

    output = result.stdout

    best_move = None
    best_line = None
    evaluation = None

    for line in output.split('\n'):
        # Get principal variation (best line Stockfish wants to play)
        if 'pv ' in line and 'info depth' in line:
            parts = line.split('pv ')
            if len(parts) > 1:
                best_line = parts[1].strip()

        # Get score (evaluation)
        if 'info depth' in line and 'score' in line:
            if 'cp ' in line:
                parts = line.split('cp ')
                if len(parts) > 1:
                    try:
                        score_str = parts[1].split()[0]
                        evaluation = int(score_str)
                    except:
                        pass

        # Get best move
        if 'bestmove ' in line:
            parts = line.split('bestmove ')
            if len(parts) > 1:
                best_move = parts[1].split()[0]

    return {
        'best_move': best_move,
        'best_line': best_line,
        'evaluation': evaluation
    }

print("="*70)
print("STOCKFISH'S PERSPECTIVE ON BOTH MOVES")
print("="*70)
print()

# Analyze current position
board = chess.Board(fen)

print("CURRENT POSITION:")
print(board)
print()

# Move 1: a3
print("-"*70)
print("IF WHITE PLAYS: a3")
print("-"*70)
board_a3 = board.copy()
board_a3.push(chess.Move.from_uci('a2a3'))
analysis_a3 = get_stockfish_analysis(board_a3.fen())
print(f"Position after a3: {board_a3.fen()}")
print()
print("Stockfish sees:")
if analysis_a3['evaluation'] is not None:
    eval_str = f"+{analysis_a3['evaluation']}" if analysis_a3['evaluation'] > 0 else str(analysis_a3['evaluation'])
    print(f"  Evaluation: {eval_str} centipawns (white)")
else:
    print(f"  Evaluation: Could not parse")

if analysis_a3['best_line']:
    print(f"  Best continuation: {analysis_a3['best_line']}")
print()

# Move 2: Nxd4
print("-"*70)
print("IF WHITE PLAYS: Nxd4")
print("-"*70)
board_nxd4 = board.copy()
board_nxd4.push(chess.Move.from_uci('f3d4'))
analysis_nxd4 = get_stockfish_analysis(board_nxd4.fen())
print(f"Position after Nxd4: {board_nxd4.fen()}")
print()
print("Stockfish sees:")
if analysis_nxd4['evaluation'] is not None:
    eval_str = f"+{analysis_nxd4['evaluation']}" if analysis_nxd4['evaluation'] > 0 else str(analysis_nxd4['evaluation'])
    print(f"  Evaluation: {eval_str} centipawns (white)")
else:
    print(f"  Evaluation: Could not parse")

if analysis_nxd4['best_line']:
    print(f"  Best continuation: {analysis_nxd4['best_line']}")
print()

# Comparison
print("="*70)
print("STOCKFISH'S VERDICT:")
print("="*70)
print()

if analysis_a3['evaluation'] is not None and analysis_nxd4['evaluation'] is not None:
    diff = analysis_a3['evaluation'] - analysis_nxd4['evaluation']
    print(f"After a3:    +{analysis_a3['evaluation']}cp")
    print(f"After Nxd4:  +{analysis_nxd4['evaluation']}cp")
    print()
    print(f"Difference: {diff}cp (a3 is better by {diff}cp)")
    print()

    # Determine classification based on cp_loss
    cp_loss = diff
    if cp_loss >= 300:
        classification = "BLUNDER"
    elif cp_loss >= 150:
        classification = "MISTAKE"
    elif cp_loss >= 50:
        classification = "INACCURACY"
    else:
        classification = "IMPRECISE"

    print(f"Classification of Nxd4: {classification} (loses {cp_loss}cp)")
else:
    print("Could not get evaluations")

print()
print("="*70)
print("WHAT THE TRAINING PAGE SHOULD SHOW:")
print("="*70)
print()
print("Move: Nxd4")
print(f"Classification: {classification}")
print("Best: a3")
print()
print("Stockfish's analysis:")
print(f"  After Nxd4: White is at +{analysis_nxd4['evaluation']}cp")
print(f"  After a3: White is at +{analysis_a3['evaluation']}cp")
print()
print("Conclusion: a3 is stronger by giving White a bigger advantage.")
print("Stockfish wants to play: " + (analysis_a3['best_line'] if analysis_a3['best_line'] else "[best line]"))
