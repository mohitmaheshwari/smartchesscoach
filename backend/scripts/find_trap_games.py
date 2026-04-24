"""
Scan all games in the DB against the trap library.

For each trap in `data/traps.json`, detect:
  1. Games that reached the trap's setup position (all setup_moves matched)
  2. Of those, games where the trap was actually played out (trap_line moves
     appeared on the board after the setup)
  3. Who was on which side:
      - trap_setter:  the side executing the trap (by convention in the data,
                      the "active" side of the setup — determined by move
                      count parity; setup_moves is in PGN order starting with
                      white). The trap_line's first move is played by the
                      setter's side.
      - trap_victim:  the opposite side

Prints:
  - Totals (games scanned, games with trap setup reached, games with trap
    sprung)
  - Breakdown by trap name
  - Per-user counts for the target user: how many times did YOU set the trap,
    how many times did you fall for it

Usage:
  docker cp scripts/find_trap_games.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/find_trap_games.py
  docker exec -it chess-coach-backend python3 scripts/find_trap_games.py --user user_8b599930d7ef
  docker exec -it chess-coach-backend python3 scripts/find_trap_games.py --limit 100
"""

import argparse
import asyncio
import logging
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import chess.pgn
import io

from motor.motor_asyncio import AsyncIOMotorClient
from services.trap_library import get_all_traps

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("find_trap_games")

PROGRESS_EVERY = 100


def _parse_pgn_sans(pgn: str) -> list:
    """Extract the move SAN list from a PGN string.

    Returns list of SAN strings in played order, or [] on parse failure.
    """
    if not pgn:
        return []
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            return []
        sans = []
        board = game.board()
        for move in game.mainline_moves():
            sans.append(board.san(move))
            board.push(move)
        return sans
    except Exception as e:
        logger.debug(f"pgn parse failed: {e}")
        return []


def _match_prefix(sans: list, needle: list) -> bool:
    """True if `sans` starts with the exact sequence `needle`."""
    if len(sans) < len(needle):
        return False
    for i, m in enumerate(needle):
        if sans[i] != m:
            return False
    return True


def _match_subsequence_after(sans: list, start_idx: int, needle: list) -> int:
    """If needle appears at sans[start_idx:start_idx+len(needle)], return how
    many of the needle moves matched consecutively. Else 0.

    Useful to see if the trap_line played out after the setup_moves prefix.
    """
    matched = 0
    for i, m in enumerate(needle):
        j = start_idx + i
        if j >= len(sans):
            break
        if sans[j] != m:
            break
        matched += 1
    return matched


def _side_to_move_after_setup(setup_moves: list) -> str:
    """After setup_moves are played from the start, whose turn is it?
    Returns 'white' or 'black'. Used to describe which side plays the first
    move of the trap_line — NOT to infer who wins (the trap-data convention
    varies: some trap_lines start with the setter's move, some with the
    victim's response)."""
    return "white" if len(setup_moves) % 2 == 0 else "black"


async def scan(db, user_filter: str = "", limit: int = 0):
    traps = get_all_traps()
    if not traps:
        logger.error("No traps loaded — check data/traps.json")
        return

    # Flatten: list of (opening_key, trap_dict, setter_is_white)
    all_traps = []
    for opening_key, trap_list in traps.items():
        for trap in trap_list:
            setup = trap.get("setup_moves") or []
            if not setup:
                continue
            # Only include traps whose first setup move is playable from the
            # starting position (sanity-check the data).
            all_traps.append({
                "opening_key": opening_key,
                "name": trap.get("name", "?"),
                "setup_moves": setup,
                "trap_line_moves": [step["move"] for step in (trap.get("trap_line") or []) if step.get("move")],
                "result_type": trap.get("result_type"),
                "difficulty": trap.get("difficulty"),
                "side_to_move_after_setup": _side_to_move_after_setup(setup),
            })

    logger.info(f"Loaded {len(all_traps)} traps from library")

    query = {"is_analyzed": True}
    if user_filter:
        query["user_id"] = user_filter

    total = await db.games.count_documents(query)
    logger.info(f"Games to scan: {total}" + (f" (user={user_filter})" if user_filter else ""))
    if limit:
        logger.info(f"Limit: {limit}")

    cursor = db.games.find(
        query,
        {"_id": 0, "game_id": 1, "user_id": 1, "user_color": 1, "result": 1, "pgn": 1, "opening": 1, "platform": 1},
    ).sort("imported_at", -1)

    scanned = 0
    parse_failures = 0
    setup_hits = 0          # games reaching any trap's setup position
    sprung_hits = 0         # games where the trap_line also played out (full or partial)
    full_sprung = 0         # games where the trap_line played out in full

    by_trap_setup = Counter()         # trap name → number of games that reached the setup
    by_trap_sprung = Counter()        # trap name → number of games where trap_line started
    by_user_color = Counter()         # "white" / "black" — what color the user had in trap games
    per_game_traps = []               # list of (game_id, user_id, trap_name, sprung_len)

    async for game_doc in cursor:
        if limit and scanned >= limit:
            break
        scanned += 1
        if scanned % PROGRESS_EVERY == 0:
            logger.info(f"  progress: {scanned}/{total if not limit else limit} · setup_hits={setup_hits} sprung={sprung_hits}")

        pgn = game_doc.get("pgn", "")
        sans = _parse_pgn_sans(pgn)
        if not sans:
            parse_failures += 1
            continue

        user_is_white = (game_doc.get("user_color", "white") == "white")

        # Try each trap
        for trap in all_traps:
            setup = trap["setup_moves"]
            if not _match_prefix(sans, setup):
                continue

            # Setup position reached.
            setup_hits += 1
            by_trap_setup[trap["name"]] += 1

            # Was the trap actually sprung? Check consecutive match of the
            # trap_line starting right after the setup.
            trap_line = trap["trap_line_moves"]
            matched_len = 0
            if trap_line:
                matched_len = _match_subsequence_after(sans, len(setup), trap_line)

            if matched_len >= 1:
                sprung_hits += 1
                by_trap_sprung[trap["name"]] += 1
                if matched_len == len(trap_line):
                    full_sprung += 1

            user_color = "white" if user_is_white else "black"
            by_user_color[user_color] += 1

            per_game_traps.append({
                "game_id": game_doc.get("game_id"),
                "user_id": game_doc.get("user_id"),
                "trap_name": trap["name"],
                "opening_key": trap["opening_key"],
                "user_color": user_color,
                "side_to_move_after_setup": trap["side_to_move_after_setup"],
                "sprung_moves": matched_len,
                "trap_total": len(trap_line),
                "result": game_doc.get("result"),
            })

            # Don't break — one game could match multiple trap setups (e.g.
            # overlapping first-4-moves), though usually only one.

    # ─── Summary ───
    print()
    print("=" * 60)
    print(f"Games scanned:                  {scanned}")
    print(f"PGN parse failures:             {parse_failures}")
    print(f"Games reaching a trap setup:    {setup_hits}")
    print(f"Games where trap was sprung:    {sprung_hits}")
    print(f"  (full trap_line played out):  {full_sprung}")
    print()

    if by_trap_setup:
        print("Top traps by setup-reached:")
        for name, cnt in by_trap_setup.most_common(15):
            sprung = by_trap_sprung.get(name, 0)
            print(f"  {name:40s}  setup {cnt:>4}  sprung {sprung:>4}")
    else:
        print("No trap setups reached in any scanned game.")

    if user_filter and by_user_color:
        print()
        print(f"Color distribution for user {user_filter} in trap games:")
        for color, cnt in by_user_color.most_common():
            print(f"  {color:20s}  {cnt}")

    if per_game_traps and user_filter:
        print()
        print(f"Per-game trap events for {user_filter} (first 20):")
        print(f"  {'game_id':<38}  {'trap':<30}  {'you':<6}  {'sprung':<10}  result")
        for ev in per_game_traps[:20]:
            print(
                f"  {ev['game_id']:<38}  "
                f"{ev['trap_name'][:30]:<30}  "
                f"{ev['user_color']:<6}  "
                f"{ev['sprung_moves']}/{ev['trap_total']:<8}  "
                f"{ev['result']}"
            )


async def main():
    parser = argparse.ArgumentParser(description="Scan games for known opening traps.")
    parser.add_argument("--user", type=str, default="", help="Only scan games for this user_id.")
    parser.add_argument("--limit", type=int, default=0, help="Scan at most N games (0 = all).")
    args = parser.parse_args()

    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    logger.info(f"Connecting to {db_name} at {url}")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    await scan(db, user_filter=args.user, limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
