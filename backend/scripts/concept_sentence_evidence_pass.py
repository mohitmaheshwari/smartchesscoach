"""Evidence pass for the five concept detectors drafted on 2026-10-18.

They hold sentences and predicates already and say nothing, because
permission comes from the quality table and not from the words existing.
This is the measurement that decides whether they earn it.

Board-verifier adjudication, which the threshold lock permits and where it
refuses a model by name. For each detector the sentence is stated as a
proposition about the board, and that proposition is checked on the positions
the detector fired on. It is allowed to disagree in both directions -- the
positions where the concept is present and the detector stayed silent are
what show it is not merely echoing the detector.

Caption bar: >= 95% precision, 95% Wilson lower bound >= 85%, >= 50 reviewed
fires, >= 20 true negatives.

Sample size is chosen from the measured fire rates so the rarest clears the
floor: endgame_opposition fires about 0.024 per game.

Read-only. Batched reads, projected fields.
"""
import asyncio
import collections
import io
import math
import os
import sys

import chess
import chess.pgn

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient

from services.caption_concept_sentences import CONCEPT_PREDICATES, CONCEPT_SENTENCES
from services.concept_detectors._runner import run_detectors_for_move

N_GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 2500
BATCH = 25
CANDIDATES = (
    "concept_rook_seventh",
    "opening_development_with_tempo",
    "endgame_create_passed_pawn",
    "concept_knight_outpost",
    "endgame_opposition",
)


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d


fires = collections.Counter()
held = collections.Counter()
bad = collections.defaultdict(list)
true_neg = collections.Counter()
silent_but_true = collections.Counter()


def walk(game_doc, evs):
    uc = chess.WHITE if (game_doc.get("user_color") or "white").lower() == "white" else chess.BLACK
    try:
        game = chess.pgn.read_game(io.StringIO(game_doc.get("pgn") or ""))
    except Exception:
        return
    if game is None:
        return
    board = game.board()
    history = []
    for mv in game.mainline_moves():
        try:
            san = board.san(mv)
        except Exception:
            break
        if board.turn == uc:
            mn = board.fullmove_number
            row = evs.get((mn, san)) or {}
            try:
                outs = dict(run_detectors_for_move(
                    board, mv, uc, move_number=mn,
                    opening_name=game_doc.get("opening_name"),
                    move_history_san=list(history),
                    best_move_san=row.get("best_move"),
                    best_move_uci=row.get("best_move_uci"),
                    cp_loss=row.get("cp_loss"),
                    mate_info=row.get("mate_info"),
                    include_shadow=True))
            except Exception:
                outs = {}
            for name in CANDIDATES:
                predicate = CONCEPT_PREDICATES.get(name)
                if predicate is None:
                    continue
                try:
                    holds = predicate(board, mv, uc)
                except Exception:
                    holds = False
                verdict = outs.get(name)
                if verdict == "applied":
                    fires[name] += 1
                    if holds:
                        held[name] += 1
                    elif len(bad[name]) < 5:
                        bad[name].append("%s m%s %s" % (game_doc["game_id"][:10], mn, san))
                elif verdict is None:
                    if holds:
                        silent_but_true[name] += 1
                    else:
                        true_neg[name] += 1
        history.append(san)
        board.push(mv)


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    games = []
    async for g in db.games.aggregate([
        {"$match": {"is_analyzed": True, "pgn": {"$nin": [None, ""]}}},
        {"$sample": {"size": N_GAMES}},
        {"$project": {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "opening_name": 1}},
    ]):
        games.append(g)

    for i in range(0, len(games), BATCH):
        batch = games[i:i + BATCH]
        ids = [g["game_id"] for g in batch]
        store = collections.defaultdict(dict)
        async for a in db.game_analyses.find(
            {"game_id": {"$in": ids}},
            {"_id": 0, "game_id": 1,
             "stockfish_analysis.move_evaluations.move_number": 1,
             "stockfish_analysis.move_evaluations.move": 1,
             "stockfish_analysis.move_evaluations.cp_loss": 1,
             "stockfish_analysis.move_evaluations.best_move": 1,
             "stockfish_analysis.move_evaluations.best_move_uci": 1,
             "stockfish_analysis.move_evaluations.mate_info": 1,
             "stockfish_analysis.move_evaluations.is_opponent_move": 1},
        ):
            for m in ((a.get("stockfish_analysis") or {}).get("move_evaluations") or []):
                if not m.get("is_opponent_move"):
                    store[a["game_id"]][(m.get("move_number"), m.get("move"))] = m
        for g in batch:
            walk(g, store.get(g["game_id"], {}))
        store.clear()
        if (i + BATCH) % 500 == 0:
            print("   ...%d games" % min(i + BATCH, len(games)), flush=True)

    print("\ngames: %d\n" % len(games))
    print("%-34s%7s%7s%8s%10s%9s  %s" % (
        "detector", "fires", "held", "%", "WilsonLB", "trueNeg", "caption bar"))
    print("-" * 94)
    for name in CANDIDATES:
        n, k = fires[name], held[name]
        if n == 0:
            print("%-34s%7d   never fired" % (name, 0))
            continue
        pct = 100.0 * k / n
        lb = wilson(k, n)
        ok = pct >= 95 and lb >= 0.85 and n >= 50 and true_neg[name] >= 20
        print("%-34s%7d%7d%8.1f%10.1f%9d  %s" % (
            name, n, k, pct, 100 * lb, true_neg[name], "PASS" if ok else "FAIL"))
        if bad[name]:
            print("%-34s  did not hold: %s" % ("", ", ".join(bad[name])))

    print("\nverifier independence (concept present, detector silent):")
    for name in CANDIDATES:
        print("   %-34s%d" % (name, silent_but_true[name]))

    print("\nthe sentence each would say:")
    for name in CANDIDATES:
        bank = CONCEPT_SENTENCES.get(name) or {}
        said = (bank.get("applied") or ("", ""))[0]
        print("   %-34s%s" % (name, said))


asyncio.run(main())
