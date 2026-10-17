"""Re-measure the corrections with the engine isolated per position.

The first run reported 90-92%. Spot-checking three of its failures by hand,
two of them HELD -- so the batch number was not trustworthy. The cause is
that one engine process analysed several hundred unrelated positions in a
row, so Stockfish's transposition table carried over between boards and the
depth-18 answers were not the answers those positions would get on their own.

python-chess sends `ucinewgame` whenever the `game` argument changes, which
clears that state. Every analysis below passes a fresh object, so each
position is judged on its own.

A correction is the detector saying "a move of this kind was better than what
you played". It is scored two ways:

  LOOSE  some move of this kind is clearly better (>= 100cp) than his
  TIGHT  a move of this kind IS the engine's top move

Read-only. Batched reads, projected fields.
"""
import asyncio
import collections
import io
import math
import os
import sys

import chess
import chess.engine
import chess.pgn

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from services.concept_detectors._runner import run_detectors_for_move

N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
BATCH = 25
DEPTH = 18
CLEARLY_BETTER = 100
HOME = {chess.WHITE: {chess.B1, chess.G1, chess.C1, chess.F1},
        chess.BLACK: {chess.B8, chess.G8, chess.C8, chess.F8}}


def c_development(board, move, colour):
    p = board.piece_at(move.from_square)
    if p is None or p.color != colour:
        return False
    if p.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return False
    return move.from_square in HOME[colour] and move.to_square not in HOME[colour]


def c_centre(board, move, colour):
    p = board.piece_at(move.from_square)
    if p is None or p.color != colour or p.piece_type != chess.PAWN:
        return False
    return move.to_square in {chess.D4, chess.E4, chess.D5, chess.E5}


CLAIMS = {"coached_development": c_development, "opening_center": c_centre}
cases = collections.defaultdict(list)


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d


def walk(g, ev):
    uc = chess.WHITE if (g.get("user_color") or "white").lower() == "white" else chess.BLACK
    try:
        game = chess.pgn.read_game(io.StringIO(g["pgn"]))
    except Exception:
        return
    if game is None:
        return
    board = game.board()
    hist = []
    for mv in game.mainline_moves():
        try:
            san = board.san(mv)
        except Exception:
            break
        if board.turn == uc:
            mn = board.fullmove_number
            row = ev.get((mn, san)) or {}
            try:
                outs = dict(run_detectors_for_move(
                    board, mv, uc, move_number=mn,
                    opening_name=g.get("opening_name"),
                    move_history_san=list(hist),
                    best_move_san=row.get("best_move"),
                    best_move_uci=row.get("best_move_uci"),
                    cp_loss=row.get("cp_loss"), mate_info=row.get("mate_info"),
                    include_shadow=True))
            except Exception:
                outs = {}
            for det in CLAIMS:
                if outs.get(det) == "wrong" and len(cases[det]) < 70:
                    cases[det].append((g["game_id"], mn, san, board.fen(), uc))
        hist.append(san)
        board.push(mv)


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    games = []
    async for g in db.games.aggregate([
        {"$match": {"is_analyzed": True, "pgn": {"$nin": [None, ""]}}},
        {"$sample": {"size": N}},
        {"$project": {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "opening_name": 1}},
    ]):
        games.append(g)

    for i in range(0, len(games), BATCH):
        batch = games[i:i + BATCH]
        ids = [g["game_id"] for g in batch]
        ev = collections.defaultdict(dict)
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
                    ev[a["game_id"]][(m.get("move_number"), m.get("move"))] = m
        for g in batch:
            walk(g, ev.get(g["game_id"], {}))
        ev.clear()

    engine = chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish")
    for det, rows in cases.items():
        claim = CLAIMS[det]
        loose = tight = checked = 0
        fails = []
        for gid, mn, san, fen, uc in rows[:60]:
            b = chess.Board(fen)
            played = None
            for m in b.legal_moves:
                try:
                    if b.san(m) == san:
                        played = m
                        break
                except Exception:
                    continue
            if played is None:
                continue
            token = object()          # forces ucinewgame -> clean hash
            try:
                infos = engine.analyse(b, chess.engine.Limit(depth=DEPTH), multipv=3, game=token)
                pb = b.copy()
                pb.push(played)
                pe = engine.analyse(pb, chess.engine.Limit(depth=DEPTH),
                                    game=object())["score"].pov(uc).score(mate_score=1500)
            except Exception:
                continue
            checked += 1
            top = infos[0]["pv"][0]
            if top != played and claim(b, top, uc):
                tight += 1
            ok = False
            for info in infos:
                cand = info["pv"][0]
                if cand == played or not claim(b, cand, uc):
                    continue
                cb = b.copy()
                cb.push(cand)
                try:
                    ce = engine.analyse(cb, chess.engine.Limit(depth=DEPTH),
                                        game=object())["score"].pov(uc).score(mate_score=1500)
                except Exception:
                    continue
                if ce is not None and pe is not None and ce - pe >= CLEARLY_BETTER:
                    ok = True
                    break
            if ok:
                loose += 1
            elif len(fails) < 5:
                fails.append("%s m%s %s" % (gid[:10], mn, san))
        if checked:
            print("%-24s LOOSE %2d/%2d = %3.0f%% (LB %2.0f%%)   TIGHT %2d/%2d = %3.0f%% (LB %2.0f%%)" % (
                det, loose, checked, 100.0 * loose / checked, 100 * wilson(loose, checked),
                tight, checked, 100.0 * tight / checked, 100 * wilson(tight, checked)))
            if fails:
                print("%-24s loose gate missed: %s" % ("", ", ".join(fails)))
    engine.quit()


asyncio.run(main())
