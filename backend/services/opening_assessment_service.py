"""
Opening Assessment Service
============================

Looks at the user's ACTUAL games and figures out:
1. Which openings they play
2. How well they know each one (which moves they get right/wrong)
3. Where exactly they go off-book or make mistakes
4. What specific variation to train next

This feeds into Play with Coach to create STRUCTURED training.
"""

import chess
import chess.pgn
import io
import logging
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


async def assess_opening_knowledge(db, user_id: str, opening_key: str = "london_system") -> Dict:
    """
    Analyze user's past games in a specific opening.
    
    Returns:
    {
        "games_played": 8,
        "moves_mastered": ["d4", "Bf4", "e3"],  — they always get these right
        "weak_moves": [{"after": "Bg4", "expected": "Nf3", "user_played": ["Be2", "h3"], "times_wrong": 3}],
        "never_seen": ["c5 early", "Bf5 mirror"],  — variations they haven't faced
        "overall_score": 72,  — % of opening moves correct
        "focus_variation": "Bg4 pin response",  — what to train next
        "ready_for_middlegame": False,  — do they need more opening work?
    }
    """
    from services.opening_curriculum_engine import _load_curriculum

    curriculum = _load_curriculum()
    opening = curriculum.get(opening_key)
    if not opening:
        return {"error": "Opening not found", "games_played": 0}

    # Get user's games
    user_color = opening.get("color", "white")
    games = await db.games.find(
        {"user_id": user_id, "user_color": user_color},
        {"_id": 0, "game_id": 1, "pgn": 1, "opening_name": 1, "opening": 1, "result": 1}
    ).sort("imported_at", -1).limit(50).to_list(50)

    if not games:
        return {
            "games_played": 0,
            "moves_mastered": [],
            "weak_moves": [],
            "never_seen": [],
            "overall_score": 0,
            "focus_variation": None,
            "ready_for_middlegame": False,
            "message": "No games found. Play some games first.",
        }

    # Parse the curriculum tree to get all expected move sequences
    tree = opening.get("tree", {})

    # Analyze each game against the curriculum
    move_accuracy = defaultdict(lambda: {"correct": 0, "wrong": 0, "wrong_moves": []})
    opponent_responses_seen = set()
    games_in_opening = 0

    for game in games:
        pgn = game.get("pgn", "")
        if not pgn:
            continue

        game_moves = _parse_pgn_moves(pgn)
        if not game_moves:
            continue

        # Check if this game started with our opening
        first_move = game_moves[0] if game_moves else ""
        opening_first = list(tree.keys())[0] if tree else ""

        if user_color == "white" and first_move != opening_first:
            continue  # User didn't play this opening
        
        games_in_opening += 1

        # Walk the curriculum tree and compare with actual moves
        _analyze_game_against_curriculum(
            game_moves, tree, user_color,
            move_accuracy, opponent_responses_seen,
        )

    if games_in_opening == 0:
        return {
            "games_played": 0,
            "games_total": len(games),
            "moves_mastered": [],
            "weak_moves": [],
            "never_seen": [],
            "overall_score": 0,
            "focus_variation": None,
            "ready_for_middlegame": False,
            "message": f"You have {len(games)} games but none in the {opening.get('name', 'opening')}. Let's start learning it!",
        }

    # Build results
    mastered = []
    weak = []
    for position_key, stats in move_accuracy.items():
        total = stats["correct"] + stats["wrong"]
        if total == 0:
            continue
        accuracy = stats["correct"] / total
        if accuracy >= 0.8:
            mastered.append(position_key)
        elif stats["wrong"] > 0:
            weak.append({
                "position": position_key,
                "expected": stats.get("expected_move", "?"),
                "user_played": list(set(stats["wrong_moves"]))[:3],
                "times_wrong": stats["wrong"],
                "times_right": stats["correct"],
                "accuracy": round(accuracy * 100),
            })

    # Sort weak by most mistakes
    weak.sort(key=lambda x: x["times_wrong"], reverse=True)

    # Find variations never seen
    all_opponent_responses = set()
    _collect_opponent_responses(tree, all_opponent_responses)
    never_seen = list(all_opponent_responses - opponent_responses_seen)

    # Overall score
    total_decisions = sum(s["correct"] + s["wrong"] for s in move_accuracy.values())
    total_correct = sum(s["correct"] for s in move_accuracy.values())
    overall_score = round((total_correct / total_decisions * 100)) if total_decisions > 0 else 0

    # Focus variation — the weakest area
    focus = None
    if weak:
        focus = weak[0]["position"]

    ready = overall_score >= 80 and len(weak) <= 1

    return {
        "games_played": games_in_opening,
        "games_total": len(games),
        "moves_mastered": mastered,
        "weak_moves": weak[:5],
        "never_seen": never_seen[:5],
        "overall_score": overall_score,
        "focus_variation": focus,
        "ready_for_middlegame": ready,
        "message": _build_assessment_message(games_in_opening, overall_score, mastered, weak, focus, opening.get("name", "opening")),
    }


def _parse_pgn_moves(pgn: str) -> List[str]:
    """Parse PGN string to list of SAN moves."""
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if not game:
            return []
        return [move.uci() for move in game.mainline_moves()]
    except Exception:
        pass

    # Fallback: try to parse move text directly
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game:
            board = game.board()
            moves = []
            for move in game.mainline_moves():
                moves.append(board.san(move))
                board.push(move)
            return moves
    except Exception:
        pass
    return []


def _analyze_game_against_curriculum(
    game_moves: List[str],
    tree: Dict,
    user_color: str,
    move_accuracy: Dict,
    opponent_responses_seen: set,
):
    """Walk through a game and compare each move against the curriculum tree."""
    # Convert UCI moves to SAN using a board
    board = chess.Board()
    san_moves = []
    for uci in game_moves:
        try:
            move = chess.Move.from_uci(uci) if len(uci) >= 4 else board.parse_san(uci)
            san = board.san(move)
            san_moves.append(san)
            board.push(move)
        except Exception:
            try:
                move = board.parse_san(uci)
                san_moves.append(uci)
                board.push(move)
            except Exception:
                break

    # Walk the tree
    node = None
    first_move = list(tree.keys())[0] if tree else None
    if not first_move or not san_moves:
        return

    # Check first move
    if san_moves[0] == first_move:
        node = tree[first_move]
        pos_key = "move_1"
        move_accuracy[pos_key]["correct"] += 1
        move_accuracy[pos_key]["expected_move"] = first_move
    else:
        return  # Not this opening

    for i in range(1, min(len(san_moves), 20)):  # First 20 moves max
        move = san_moves[i]
        is_our_move = (i % 2 == 0 and user_color == "white") or (i % 2 == 1 and user_color == "black")

        if not is_our_move:
            # Opponent's move — track what they played
            opponent_responses_seen.add(move)
            responses = node.get("responses", {}) if node else {}
            if move in responses:
                node = responses[move]
            else:
                break  # Off-book opponent response
        else:
            # Our move — check against expected
            if node is None:
                break
            expected = node.get("next")
            pos_key = f"move_{(i // 2) + 1}_after_{san_moves[i-1]}"

            if expected and move == expected:
                move_accuracy[pos_key]["correct"] += 1
                move_accuracy[pos_key]["expected_move"] = expected
            elif expected:
                move_accuracy[pos_key]["wrong"] += 1
                move_accuracy[pos_key]["wrong_moves"].append(move)
                move_accuracy[pos_key]["expected_move"] = expected
                break  # Stop after first wrong move in this game
            else:
                break  # No expected move — tree ended


def _extract_all_paths(tree: Dict, user_color: str) -> List[List[str]]:
    """Extract all possible correct move sequences from the tree."""
    paths = []
    first_move = list(tree.keys())[0] if tree else None
    if not first_move:
        return paths

    def _walk(node, current_path):
        responses = node.get("responses", {})
        if not responses:
            paths.append(current_path[:])
            return
        for resp, resp_node in responses.items():
            next_move = resp_node.get("next")
            if next_move:
                _walk(resp_node, current_path + [resp, next_move])
            else:
                paths.append(current_path + [resp])

    _walk(tree[first_move], [first_move])
    return paths


def _collect_opponent_responses(tree: Dict, responses_set: set):
    """Collect all possible opponent responses from the tree."""
    first_key = list(tree.keys())[0] if tree else None
    if not first_key:
        return

    def _walk(node):
        for resp_key, resp_node in node.get("responses", {}).items():
            responses_set.add(resp_key)
            if isinstance(resp_node, dict):
                _walk(resp_node)

    _walk(tree[first_key])


def _build_assessment_message(games_played, score, mastered, weak, focus, opening_name):
    """Build a simple assessment message."""
    if games_played == 0:
        return f"You haven't played the {opening_name} yet. Let's learn it from scratch."

    if score >= 90:
        return f"You know the {opening_name} well ({score}% accuracy). Let's work on the middlegame plans."
    elif score >= 70:
        msg = f"You're getting the hang of the {opening_name} ({score}% accuracy)."
        if focus:
            msg += f" Your weak spot: how to respond after {focus}."
        return msg
    elif score >= 50:
        msg = f"You know the basics of the {opening_name} ({score}% accuracy), but there are gaps."
        if weak:
            msg += f" Let's fix: {weak[0]['position']}."
        return msg
    else:
        return f"The {opening_name} needs work ({score}% accuracy). Let's drill the key moves."



async def get_pregame_intro(db, user_id: str, opening_key: str = "london_system") -> Dict:
    """
    Build the pre-game intro for structured training.
    
    Checks:
    1. Has user played this opening in real games?
    2. Has user practiced this with the coach before?
    3. If practiced before, how did they do?
    4. What should this session focus on?
    
    Returns a structured intro the frontend can display.
    """
    from services.opening_curriculum_engine import _load_curriculum, get_opening_summary

    curriculum = _load_curriculum()
    opening = curriculum.get(opening_key)
    if not opening:
        return {"error": "Opening not found"}

    opening_name = opening.get("name", "Opening")
    summary_data = get_opening_summary(opening_key) or {}

    # 1. Get real game assessment
    assessment = await assess_opening_knowledge(db, user_id, opening_key)

    # 2. Check coach session history for this opening
    past_sessions = await db.coach_sessions.find(
        {"user_id": user_id, "teaching_opening": opening_key},
        {"_id": 0, "session_id": 1, "created_at": 1, "status": 1, "result": 1}
    ).sort("created_at", -1).limit(10).to_list(10)

    sessions_played = len(past_sessions)

    # 3. Build the intro
    real_games = assessment.get("games_played", 0)
    score = assessment.get("overall_score", 0)
    weak = assessment.get("weak_moves", [])
    mastered = assessment.get("moves_mastered", [])
    never_seen = assessment.get("never_seen", [])

    # Determine experience level
    if real_games == 0 and sessions_played == 0:
        level = "brand_new"
    elif sessions_played > 0 and real_games == 0:
        level = "practiced_only"
    elif real_games > 0 and score >= 80:
        level = "knows_well"
    elif real_games > 0 and score >= 50:
        level = "knows_basics"
    else:
        level = "needs_work"

    # Build intro message
    intro_lines = []
    focus_area = None

    if level == "brand_new":
        intro_lines = [
            f"Today we're learning the {opening_name}.",
            summary_data.get("summary", "A great opening to add to your game."),
        ]
        rules = opening.get("golden_rules", [])
        if rules:
            intro_lines.append(f"The #1 rule: {rules[0]}")
        focus_area = "Learn the basic setup"

    elif level == "practiced_only":
        intro_lines = [
            f"We've practiced the {opening_name} {sessions_played} time{'s' if sessions_played > 1 else ''} together.",
            "Let's keep drilling it until it feels natural.",
        ]
        focus_area = "Repetition — make the moves automatic"

    elif level == "knows_well":
        intro_lines = [
            f"You know the {opening_name} well — {score}% accuracy from {real_games} games.",
        ]
        if never_seen:
            intro_lines.append(f"But you haven't faced: {', '.join(never_seen[:2])}. Let's prepare for that.")
            focus_area = f"New variation: {never_seen[0]}"
        else:
            intro_lines.append("Let's work on the middlegame plans that come from this opening.")
            focus_area = "Middlegame plans"

    elif level == "knows_basics":
        intro_lines = [
            f"You've played the {opening_name} {real_games} times — {score}% accuracy.",
        ]
        if weak:
            w = weak[0]
            intro_lines.append(f"You keep getting {w['position']} wrong. You played {', '.join(w.get('user_played', [])[:2])} but should play {w.get('expected', '?')}.")
            intro_lines.append("Let's fix that today.")
            focus_area = w["position"]
        else:
            intro_lines.append("Let's sharpen the moves you're unsure about.")
            focus_area = "Consistency"

    else:  # needs_work
        intro_lines = [
            f"The {opening_name} needs work — {score}% accuracy.",
        ]
        if sessions_played > 0:
            intro_lines.append(f"We've practiced {sessions_played} times. Let's try a different approach today.")
        else:
            intro_lines.append("Let's go move by move and build it up.")
        if weak:
            focus_area = weak[0]["position"]
        else:
            focus_area = "Basic setup"

    return {
        "opening_key": opening_key,
        "opening_name": opening_name,
        "level": level,
        "intro": " ".join(intro_lines),
        "focus_area": focus_area,
        "stats": {
            "real_games": real_games,
            "coach_sessions": sessions_played,
            "score": score,
            "mastered_count": len(mastered),
            "weak_count": len(weak),
        },
        "golden_rules": opening.get("golden_rules", []),
        "setup_order": opening.get("setup_order", []),
        "assessment": assessment,
    }
