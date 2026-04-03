"""
Drill Helpers
=============

Pure utility functions for extracting drill/training positions.
Used by missions routes and training routes.
"""


def extract_drill_positions(analysis: dict, focus_pattern: str, limit: int = 5) -> list:
    """
    Extract drill-worthy positions from a game analysis based on focus pattern.
    """
    positions = []
    game_id = analysis.get("game_id")

    sf = analysis.get("stockfish_analysis", {})
    move_evals = sf.get("move_evaluations", [])

    pattern_eval_map = {
        "ignored_opponent_forcing": ["blunder", "mistake"],
        "missed_forcing_move": ["blunder", "mistake"],
        "phantom_threat": ["blunder", "mistake", "inaccuracy"],
        "advantage_mismanagement": ["blunder", "mistake"],
        "critical_moment_drift": ["blunder", "mistake"],
        "structural_misjudgment": ["blunder", "mistake", "inaccuracy"],
    }

    target_evals = pattern_eval_map.get(focus_pattern, ["blunder", "mistake"])

    for move_eval in move_evals:
        if len(positions) >= limit:
            break

        eval_type = move_eval.get("evaluation")
        if eval_type not in target_evals:
            continue

        fen = move_eval.get("fen_before")
        if not fen:
            continue

        pos = {
            "position_id": f"{game_id}_{move_eval.get('move_number', 0)}",
            "game_id": game_id,
            "fen": fen,
            "move_number": move_eval.get("move_number"),
            "user_move": move_eval.get("move"),
            "best_move": move_eval.get("best_move"),
            "eval_before": move_eval.get("eval_before"),
            "eval_after": move_eval.get("eval_after"),
            "eval_change": move_eval.get("cp_loss"),
            "category": focus_pattern,
            "explanation": f"You played {move_eval.get('move')}, but {move_eval.get('best_move')} was better. {move_eval.get('threat', '')}",
            "type": eval_type,
        }
        positions.append(pos)

    return positions


# Sample positions by pattern - real tactical puzzles
SAMPLE_POSITIONS = {
    "ignored_opponent_forcing": [
        {"fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
         "best_move": "Qxf7+", "explanation": "White can win material - what threat did Black ignore?"},
        {"fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3",
         "best_move": "Ng5", "explanation": "Look for forcing moves against f7."},
    ],
    "missed_forcing_move": [
        {"fen": "rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
         "best_move": "Nc6", "explanation": "Develop while defending - what threat must Black see?"},
    ],
    "critical_moment_drift": [
        {"fen": "r2qkb1r/ppp2ppp/2n1bn2/3pp3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 6",
         "best_move": "exd5", "explanation": "Critical position - find the strongest continuation."},
    ],
}


def get_sample_drill_positions(focus_pattern: str, count: int = 5) -> list:
    """
    Generate sample drill positions for training when no user-specific positions exist.
    These are common tactical patterns matching the focus area.
    """
    positions = SAMPLE_POSITIONS.get(focus_pattern, SAMPLE_POSITIONS.get("critical_moment_drift", []))

    result = []
    for i, pos in enumerate(positions[:count]):
        result.append({
            "position_id": f"sample_{focus_pattern}_{i}",
            "game_id": "sample",
            "fen": pos["fen"],
            "best_move": pos["best_move"],
            "explanation": pos["explanation"],
            "category": focus_pattern,
            "type": "sample",
        })

    return result
