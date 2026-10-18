"""Before verifying the next five detectors, ask the cheaper question:
would each one be saying something the card already says?

The distilled caption layer authors its own text for several of these ideas
-- good_develop, good_castle, good_centralize, good_rook_open_file,
good_rook_activity, good_luft, good_pawn -- and each fires on 0.4-1.0% of
cards. Three of the six promoted this morning turned out to overlap one.

So: run each candidate detector over real games, and for every move it fires
on, read the rule that ALREADY wrote that card's caption. No rendering and no
engine -- stored cards joined to a replay of the PGN.
"""
import asyncio
import collections
import io
import os
import sys

import chess
import chess.pgn

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from services.concept_detectors._runner import run_detectors_for_move

N = int(sys.argv[1]) if len(sys.argv) > 1 else 250
BATCH = 25
CANDIDATES = (
    "concept_rook_seventh",
    "opening_development_with_tempo",
    "endgame_create_passed_pawn",
    "concept_knight_outpost",
    "endgame_opposition",
)
# The ideas the caption corpus already authors.
CORPUS_IDEAS = (
    "good_develop", "good_castle", "good_centralize", "good_rook_open_file",
    "good_rook_activity", "good_luft", "good_pawn", "good_space",
    "good_capture_free", "good_queen_safety", "good_trade",
)

rules = collections.defaultdict(collections.Counter)
fires = collections.Counter()


def walk(pgn, user_color, cards, evs):
    uc = chess.WHITE if (user_color or "white").lower() == "white" else chess.BLACK
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return
    if game is None:
        return
    board = game.board()
    for mv in game.mainline_moves():
        try:
            san = board.san(mv)
        except Exception:
            break
        if board.turn == uc:
            mn = board.fullmove_number
            row = evs.get((mn, san)) or {}
            try:
                outs = run_detectors_for_move(
                    board, mv, uc, move_number=mn,
                    best_move_san=row.get("best_move"),
                    best_move_uci=row.get("best_move_uci"),
                    cp_loss=row.get("cp_loss"), mate_info=row.get("mate_info"),
                    include_shadow=True)
            except Exception:
                outs = []
            card = cards.get((mn, san)) or {}
            rule = str(card.get("rule_name") or "(no card)")
            for skill_id, outcome in outs:
                if skill_id in CANDIDATES and outcome == "applied":
                    fires[skill_id] += 1
                    rules[skill_id][rule] += 1
        board.push(mv)


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    games = []
    async for g in db.games.aggregate([
        {"$match": {"is_analyzed": True, "pgn": {"$nin": [None, ""]}}},
        {"$sample": {"size": N}},
        {"$project": {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1}},
    ]):
        games.append(g)

    for i in range(0, len(games), BATCH):
        batch = games[i:i + BATCH]
        ids = [g["game_id"] for g in batch]
        store = {}
        async for a in db.game_analyses.find(
            {"game_id": {"$in": ids}},
            {"_id": 0, "game_id": 1, "decryption_v5_data": 1,
             "stockfish_analysis.move_evaluations": 1},
        ):
            cards = {}
            for m in (a.get("decryption_v5_data") or []):
                if isinstance(m, dict):
                    cards[(m.get("move_number"), m.get("move_san") or m.get("move"))] = m
            evs = {}
            for m in ((a.get("stockfish_analysis") or {}).get("move_evaluations") or []):
                if not m.get("is_opponent_move"):
                    evs[(m.get("move_number"), m.get("move"))] = m
            store[a["game_id"]] = (cards, evs)
        for g in batch:
            cards, evs = store.get(g["game_id"], ({}, {}))
            walk(g["pgn"], g.get("user_color"), cards, evs)
        store.clear()

    print("over %d games\n" % len(games))
    for skill_id in CANDIDATES:
        n = fires[skill_id]
        print("=" * 72)
        print("%s -- %d fires" % (skill_id, n))
        if not n:
            print("   (never fired in this sample)")
            continue
        dup = sum(v for r, v in rules[skill_id].items()
                  if any(idea in r.lower() for idea in CORPUS_IDEAS))
        print("   already covered by an authored caption: %d of %d = %d%%" % (
            dup, n, round(100 * dup / n)))
        for r, v in rules[skill_id].most_common(6):
            mark = "  <-- same idea" if any(i in r.lower() for i in CORPUS_IDEAS) else ""
            print("      %-52s%4d%s" % (r[:52], v, mark))


asyncio.run(main())
