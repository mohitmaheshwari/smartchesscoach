"""
Test the opening selection flow for Play with Coach.

Verifies:
1. Opening name matches to theory tree key
2. Teaching moves are loaded
3. Session is configured correctly

Usage:
  docker cp scripts/test_opening_flow.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/test_opening_flow.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_opening_matching():
    """Test that opening names match to theory tree keys."""
    print("=== Test 1: Opening Name Matching ===")

    from services.opening_theory_tree_service import load_theory_tree
    tree = load_theory_tree()

    test_names = [
        "Italian Game",
        "French Defense",
        "Sicilian Defense",
        "Queen's Gambit",
        "London System",
        "Caro-Kann",
        "Ruy Lopez",
        "King's Indian",
        "Scotch Game",
        "Queens Pawn",  # shorter name
    ]

    for name in test_names:
        matched_key = None
        for key, data in tree.items():
            if key == "_meta":
                continue
            tree_name = data.get("name", "")
            if name.lower() in tree_name.lower() or tree_name.lower() in name.lower():
                matched_key = key
                break

        if matched_key:
            opening_data = tree[matched_key]
            main_line = opening_data.get("main_line", [])
            print(f"  OK: '{name}' -> {matched_key} ({len(main_line)} moves: {' '.join(main_line[:5])})")
        else:
            print(f"  MISS: '{name}' -> no match")

    print()


def test_teaching_setup():
    """Test that teaching moves are correctly loaded."""
    print("=== Test 2: Teaching Setup ===")

    from services.opening_theory_tree_service import load_theory_tree
    tree = load_theory_tree()

    # Simulate what the start endpoint does
    opening_name = "Italian Game"
    matched_key = None

    for key, data in tree.items():
        if key == "_meta":
            continue
        name = data.get("name", "")
        if opening_name.lower() in name.lower() or name.lower() in opening_name.lower():
            matched_key = key
            break

    if not matched_key:
        print(f"  FAIL: Could not match '{opening_name}'")
        return

    opening_data = tree[matched_key]
    main_line = opening_data.get("main_line", [])

    print(f"  Opening: {opening_data.get('name')}")
    print(f"  Key: {matched_key}")
    print(f"  Main line: {' '.join(main_line)}")
    print(f"  White plan: {opening_data.get('white_plan', 'N/A')}")
    print(f"  Black plan: {opening_data.get('black_plan', 'N/A')}")

    # Check critical positions
    critical = opening_data.get("critical_positions", {})
    print(f"  Critical positions: {len(critical)}")
    for key, pos in list(critical.items())[:2]:
        print(f"    {key}: {pos.get('key_decision', 'N/A')[:60]}")

    # Simulate session update
    session_update = {
        "opening_key": matched_key,
        "opening_name": opening_name,
        "opening_to_teach": matched_key,
        "opening_teaching_moves": main_line,
        "opening_teaching_index": 0,
        "opening_teaching_active": True,
    }
    print(f"\n  Session would be updated with:")
    for k, v in session_update.items():
        if isinstance(v, list):
            print(f"    {k}: [{', '.join(v[:5])}{'...' if len(v) > 5 else ''}]")
        else:
            print(f"    {k}: {v}")

    print()


def test_all_openings():
    """List all available openings with their main lines."""
    print("=== Test 3: All Available Openings ===")

    from services.opening_theory_tree_service import load_theory_tree
    tree = load_theory_tree()

    count = 0
    for key, data in tree.items():
        if key == "_meta":
            continue
        count += 1
        name = data.get("name", key)
        main_line = data.get("main_line", [])
        critical = len(data.get("critical_positions", {}))
        print(f"  {key:25s} | {name:30s} | {len(main_line)} moves | {critical} critical positions")

    print(f"\n  Total: {count} openings")


if __name__ == "__main__":
    test_opening_matching()
    test_teaching_setup()
    test_all_openings()
