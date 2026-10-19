"""Put the real positions into the tree that actually reaches a player.

There are two endgame libraries. `data/endgames.json` feeds coaching text and
a lesson page that is not routed; `data/coaching/endgame_theory_tree.json`
feeds teaching_engine, which is what /endgames/:category/:lesson renders. I
wrote the mined positions into the first one. This puts them in the second.

The live node already has the right shape, so each mined case becomes one
position:

    fen                 the position from the real game
    side_to_move        whose move it was
    expected_result     what the position was worth before the mistake
    correct_move_san    a move that held it, verified against the tablebase
    wrong_example_san   what he actually played
    prompt              what the player is asked

APPENDS, never replaces: the authored positions that are already there were
written by a person and are not mine to drop.

Every position is verified against the tablebase before it is written, and
any that fails is skipped rather than written with a warning.
"""
import collections
import json
import os

import chess
import chess.syzygy

SYZYGY = os.environ.get("SYZYGY_PATH", "E:/syzygy")
MATERIAL = os.environ["MATERIAL"]
TREE = "data/coaching/endgame_theory_tree.json"
PER_LESSON = 4
ORDER = {"loss": 0, "draw": 1, "win": 2}

# mined family -> where it lives in the live tree
ROUTE = {
    "opposition": ("king_and_pawn", "opposition"),
    "rule_of_square": ("king_and_pawn", "square_rule"),
    "lucena_position": ("rook_endgames", "lucena"),
    "philidor_position": ("rook_endgames", "philidor"),
    "queen_checkmate": ("basic_mates", "queen_mate"),
    "stalemate_trap": ("queen_vs_pawn", "stalemate_tricks"),
}


def outcome(tables, board):
    if len(board.piece_map()) > 5 or not board.is_valid():
        return None
    if board.is_checkmate():
        return "loss"
    if board.is_stalemate() or board.is_insufficient_material():
        return "draw"
    try:
        wdl = tables.probe_wdl(board)
    except Exception:
        return None
    return "win" if wdl > 0 else ("loss" if wdl < 0 else "draw")


def after(tables, board, move):
    nxt = board.copy()
    nxt.push(move)
    theirs = outcome(tables, nxt)
    if theirs is None:
        return None
    return {"win": "loss", "loss": "win", "draw": "draw"}[theirs]


def family(case):
    end = case["ending"]
    board = chess.Board(case["fen"])
    if case["stalemate"]:
        return "stalemate_trap"
    if end.startswith("pawn ending"):
        kings = [sq for sq, p in board.piece_map().items() if p.piece_type == chess.KING]
        if len(kings) == 2 and chess.square_distance(kings[0], kings[1]) <= 2:
            return "opposition"
        return "rule_of_square"
    if "Q" in end:
        return "queen_checkmate"
    if "R" in end:
        return "lucena_position" if "P" in end.split(" v ")[0] else "philidor_position"
    return None


def main():
    tables = chess.syzygy.open_tablebase(SYZYGY)
    cases = json.load(open(MATERIAL, encoding="utf-8"))
    tree = json.load(open(TREE, encoding="utf-8"),
                     object_pairs_hook=collections.OrderedDict)

    grouped = collections.defaultdict(list)
    for case in cases:
        key = family(case)
        if key in ROUTE:
            grouped[key].append(case)

    added = collections.Counter()
    skipped = collections.Counter()

    for key, rows in grouped.items():
        section, lesson = ROUTE[key]
        node = tree.get(section, {}).get("lessons", {}).get(lesson)
        if node is None:
            skipped["no live lesson node for %s" % key] += len(rows)
            continue
        existing = node.setdefault("positions", [])
        have = {p.get("fen") for p in existing}

        rows.sort(key=lambda c: (c["held"], c["move_number"]))
        seen_games = set()
        for case in rows:
            if added[key] >= PER_LESSON:
                break
            if case["fen"] in have:
                continue
            if case["game_id"] in seen_games and added[key] >= 2:
                continue
            board = chess.Board(case["fen"])
            if not board.is_valid():
                skipped["illegal"] += 1
                continue
            try:
                played = board.parse_san(case["played"])
            except Exception:
                skipped["move will not parse"] += 1
                continue
            before = outcome(tables, board)
            got = after(tables, board, played)
            if before is None or got is None or ORDER[got] >= ORDER[before]:
                skipped["no longer changes the result"] += 1
                continue
            save = None
            for san in case["held_moves"]:
                try:
                    mv = board.parse_san(san)
                except Exception:
                    continue
                if after(tables, board, mv) == before:
                    save = (san, mv.uci())
                    break
            if save is None:
                skipped["no verified saving move"] += 1
                continue

            if before == "win":
                prompt = ("You are winning. %d of your %d moves keep the win -- find one."
                          % (case["held"], case["legal"]))
            else:
                prompt = ("This is a draw if you find it. %s of your %d moves hold it."
                          % ("Only one" if case["held"] == 1 else str(case["held"]),
                             case["legal"]))

            existing.append(collections.OrderedDict([
                ("fen", case["fen"]),
                ("side_to_move", "white" if board.turn else "black"),
                ("expected_result", before),
                ("correct_move_san", save[0]),
                ("correct_move_uci", save[1]),
                ("wrong_example_san", case["played"]),
                ("prompt", prompt),
                ("source", "real game, verified against the 5-piece tablebase"),
            ]))
            seen_games.add(case["game_id"])
            added[key] += 1

    tables.close()
    for key in sorted(ROUTE):
        section, lesson = ROUTE[key]
        node = tree.get(section, {}).get("lessons", {}).get(lesson, {})
        print("%-18s -> %-28s now %d positions (+%d real)" % (
            key, "%s/%s" % (section, lesson), len(node.get("positions", [])), added[key]))
    if skipped:
        print("\nskipped:")
        for reason, n in skipped.most_common():
            print("   %-40s %d" % (reason, n))

    with open(TREE, "w", encoding="utf-8") as fh:
        json.dump(tree, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("\nwritten to %s" % TREE)


main()
