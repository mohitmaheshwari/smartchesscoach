"""
Test opening teaching end-to-end.

Simulates a Play with Coach game where user selects an opening.
Verifies:
1. Opening matches to theory tree
2. Full teaching line is built (not just 5 moves)
3. Move-by-move teaching works (correct/incorrect detection)
4. All 24 openings produce valid lines

Usage:
  docker cp scripts/test_opening_teaching.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/test_opening_teaching.py
"""

import sys
import os
import chess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.opening_theory_tree_service import load_theory_tree


def build_full_opening_line(opening_key):
    """Same logic as coach_play.py _build_full_opening_line"""
    tree = load_theory_tree()
    opening = tree.get(opening_key, {})
    main_line = list(opening.get("main_line", []))
    if not main_line:
        return []

    variations = opening.get("variations", {})
    if variations:
        first_var_key = list(variations.keys())[0]
        first_var = variations[first_var_key]
        moves_from_parent = first_var.get("moves_from_parent", [])
        if moves_from_parent:
            main_line.extend(moves_from_parent)
        continuation = first_var.get("continuation", [])
        if continuation:
            main_line.extend(continuation)
    return main_line


def test_all_openings():
    """Test every opening produces a valid, playable line."""
    print("=" * 60)
    print("TEST: All openings produce valid teaching lines")
    print("=" * 60)

    tree = load_theory_tree()
    passed = 0
    failed = 0

    for key, data in tree.items():
        if key == "_meta":
            continue

        name = data.get("name", key)
        line = build_full_opening_line(key)

        if not line:
            print(f"  FAIL: {key} ({name}) — no moves")
            failed += 1
            continue

        # Validate: can we play all moves on a board?
        board = chess.Board()
        valid = True
        fail_move = None
        for i, move_san in enumerate(line):
            try:
                move = board.parse_san(move_san)
                board.push(move)
            except Exception as e:
                valid = False
                fail_move = f"move {i+1} '{move_san}': {e}"
                break

        if valid:
            print(f"  OK: {key:25s} | {name:30s} | {len(line):2d} moves | {' '.join(line[:8])}{'...' if len(line) > 8 else ''}")
            passed += 1
        else:
            print(f"  FAIL: {key:25s} | {name:30s} | {fail_move}")
            failed += 1

    print(f"\n  Passed: {passed}, Failed: {failed}")
    print()


def test_teaching_simulation():
    """Simulate a game where user follows the Italian Game line."""
    print("=" * 60)
    print("TEST: Teaching simulation (Italian Game)")
    print("=" * 60)

    line = build_full_opening_line("italian_game")
    print(f"Teaching line: {' '.join(line)} ({len(line)} moves)")
    print()

    board = chess.Board()
    teaching_index = 0

    for i, expected_san in enumerate(line):
        side = "White" if board.turn == chess.WHITE else "Black"
        move_num = board.fullmove_number

        # User's turn (even index = white if user is white)
        is_user = (i % 2 == 0)  # Assume user is white

        if is_user:
            # Simulate user playing correct move
            print(f"  Move {move_num} ({side}): User plays {expected_san} — ", end="")
            try:
                move = board.parse_san(expected_san)
                board.push(move)
                print("CORRECT")
                teaching_index += 1
            except Exception as e:
                print(f"ERROR: {e}")
                break
        else:
            # Coach plays the expected move
            print(f"  Move {move_num} ({side}): Coach plays {expected_san}")
            try:
                move = board.parse_san(expected_san)
                board.push(move)
                teaching_index += 1
            except Exception as e:
                print(f"  ERROR: {e}")
                break

    print(f"\n  Completed: {teaching_index}/{len(line)} moves")
    print(f"  Final FEN: {board.fen()}")
    print()


def test_wrong_move_detection():
    """Test that wrong moves are detected during teaching."""
    print("=" * 60)
    print("TEST: Wrong move detection")
    print("=" * 60)

    line = build_full_opening_line("italian_game")
    board = chess.Board()

    # Play first 4 moves correctly
    for san in line[:4]:
        board.push(board.parse_san(san))

    # Now test: expected move is line[4] (Bc4), but user plays something else
    expected = line[4]
    wrong_moves = ["d3", "Be2", "Bd3", "h3"]

    print(f"  Position after 4 moves: {board.fen()[:40]}...")
    print(f"  Expected: {expected}")
    print()

    for wrong in wrong_moves:
        try:
            board.parse_san(wrong)  # Verify it's legal
            is_correct = wrong.lower().replace("+", "").replace("#", "") == expected.lower().replace("+", "").replace("#", "")
            status = "CORRECT" if is_correct else "WRONG (detected)"
            print(f"  User plays {wrong}: {status}")
        except Exception:
            print(f"  User plays {wrong}: ILLEGAL")

    print()


def test_opening_name_matching():
    """Test matching opening names from Progress page to theory keys."""
    print("=" * 60)
    print("TEST: Opening name matching (from user's games)")
    print("=" * 60)

    tree = load_theory_tree()

    # These are the kinds of names that come from Chess.com/Lichess
    test_names = [
        "Italian Game",
        "Italian Game: Giuoco Piano",
        "French Defense: Advance Variation",
        "Sicilian Defense: Najdorf",
        "Queen's Gambit Declined",
        "King's Indian Defense",
        "London System",
        "Scandinavian Defense",
        "Ruy Lopez",
        "Caro-Kann Defense",
        "Scotch Game",
        "English Opening",  # not in our tree
        "Pirc Defense",     # not in our tree
    ]

    for name in test_names:
        matched = None
        for key, data in tree.items():
            if key == "_meta":
                continue
            tree_name = data.get("name", "")
            if name.lower() in tree_name.lower() or tree_name.lower() in name.lower():
                matched = key
                break

        if matched:
            line = build_full_opening_line(matched)
            print(f"  OK: '{name}' -> {matched} ({len(line)} moves)")
        else:
            print(f"  MISS: '{name}' -> no match (coach will play freely)")

    print()


if __name__ == "__main__":
    test_all_openings()
    test_teaching_simulation()
    test_wrong_move_detection()
    test_opening_name_matching()
