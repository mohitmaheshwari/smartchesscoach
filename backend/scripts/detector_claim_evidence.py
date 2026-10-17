"""Second pass: corrected sentences, and a gate that might let the
corrections clear the bar.

What the diagnosis found, over 250 games:

  concept_rook_open_file       121 fires: 64% fully open, 36% half-open,
                               and ZERO with a friendly pawn on the file.
                               The detector was right; my sentence demanded
                               "no pawns at all" when the concept is "none of
                               YOUR pawns". Sentence fixed here.

  endgame_king_centralization   95 fires: 100% stepped towards the centre, but
                               only 62% had <=12 pieces left. Walking the king
                               to the middle with 15-21 pieces on is not
                               endgame technique, it is a way to get mated --
                               so this one is NOT a wording fix. It needs a
                               gate, and the gate is a promotion condition.

  concept_central_pawn_break   104 fires: 100% on the c-f files but only 37%
                               with pawns actually in contact. "Break" is
                               overclaiming for the rest. Tested both ways.

For the corrections, the first pass held 88% (bar is 95%). This re-tests them
under a tighter gate: the concept move must be the engine's TOP move at depth
18, not merely a clearly better one.

Read-only. Batched reads, projected fields -- nothing large stays resident.
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
ENDGAME_PIECES = 12


def _mover(board, move, colour, ptypes=None):
    p = board.piece_at(move.from_square)
    if p is None or p.color != colour:
        return None
    if ptypes and p.piece_type not in ptypes:
        return None
    return p


def c_rook_file_fixed(board, move, colour):
    """CORRECTED: a rook of yours moved to a file with none of YOUR pawns."""
    if not _mover(board, move, colour, (chess.ROOK,)):
        return False
    f = chess.square_file(move.to_square)
    after = board.copy()
    after.push(move)
    for r in range(8):
        pc = after.piece_at(chess.square(f, r))
        if pc is not None and pc.piece_type == chess.PAWN and pc.color == colour:
            return False
    return True


def _cdist(sq):
    return max(abs(chess.square_file(sq) - 3.5), abs(chess.square_rank(sq) - 3.5))


def c_king_centre_gated(board, move, colour):
    """GATED: few pieces left AND the king stepped towards the middle."""
    if not _mover(board, move, colour, (chess.KING,)):
        return False
    if board.is_castling(move):
        return False
    if len(board.piece_map()) > ENDGAME_PIECES:
        return False
    return _cdist(move.to_square) < _cdist(move.from_square)


def c_pawn_centre_plain(board, move, colour):
    """PLAINER: a pawn of yours moved in the middle files."""
    if not _mover(board, move, colour, (chess.PAWN,)):
        return False
    return chess.square_file(move.to_square) in (2, 3, 4, 5)


def c_pawn_break_contact(board, move, colour):
    """STRICTER: ...and enemy pawns are actually in contact with it."""
    if not c_pawn_centre_plain(board, move, colour):
        return False
    them = not colour
    after = board.copy()
    after.push(move)
    for sq in after.attackers(them, move.to_square):
        pc = after.piece_at(sq)
        if pc is not None and pc.piece_type == chess.PAWN:
            return True
    for sq in after.attacks(move.to_square):
        pc = after.piece_at(sq)
        if pc is not None and pc.color == them and pc.piece_type == chess.PAWN:
            return True
    return False


# detector -> list of (label, claim) variants to score
VARIANTS = {
    "concept_rook_open_file": [("none of YOUR pawns on the file", c_rook_file_fixed)],
    "endgame_king_centralization": [("<=12 pieces AND towards centre", c_king_centre_gated)],
    "concept_central_pawn_break": [
        ("a pawn move in the middle files", c_pawn_centre_plain),
        ("...with enemy pawns in contact", c_pawn_break_contact),
    ],
}
NEGATIVE_FOR = {
    "coached_development": None,
    "opening_center": None,
}


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d


def c_development(board, move, colour):
    if not _mover(board, move, colour, (chess.KNIGHT, chess.BISHOP)):
        return False
    home = ({chess.B1, chess.G1, chess.C1, chess.F1} if colour == chess.WHITE
            else {chess.B8, chess.G8, chess.C8, chess.F8})
    return move.from_square in home and move.to_square not in home


def c_centre(board, move, colour):
    if not _mover(board, move, colour, (chess.PAWN,)):
        return False
    return move.to_square in {chess.D4, chess.E4, chess.D5, chess.E5}


NEG_CLAIMS = {"coached_development": c_development, "opening_center": c_centre}

stats = collections.defaultdict(lambda: {"n": 0, "ok": 0, "bad": []})
gated_loss = collections.Counter()
neg_cases = collections.defaultdict(list)


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
            for det, variants in VARIANTS.items():
                if outs.get(det) != "applied":
                    continue
                for label, claim in variants:
                    key = (det, label)
                    stats[key]["n"] += 1
                    try:
                        ok = claim(board, mv, uc)
                    except Exception:
                        ok = False
                    if ok:
                        stats[key]["ok"] += 1
                    elif len(stats[key]["bad"]) < 4:
                        stats[key]["bad"].append("%s m%s %s" % (g["game_id"][:10], mn, san))
                if det == "endgame_king_centralization" and len(board.piece_map()) > ENDGAME_PIECES:
                    gated_loss["king fires dropped by the <=12 gate"] += 1
            for det in NEG_CLAIMS:
                if outs.get(det) == "wrong" and len(neg_cases[det]) < 45:
                    neg_cases[det].append((g["game_id"], mn, san, board.fen(), uc))
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

    print("games: %d\n" % len(games))
    print("=" * 104)
    print("CORRECTED SENTENCES  (board alone)")
    print("=" * 104)
    print("%-30s%-38s%7s%7s%8s%10s  %s" % ("detector", "sentence tested", "fires", "held", "%", "WilsonLB", "bar"))
    for (det, label), s in stats.items():
        if s["n"] == 0:
            continue
        pct = 100.0 * s["ok"] / s["n"]
        lb = wilson(s["ok"], s["n"])
        bar = pct >= 95 and lb >= 0.85 and s["n"] >= 50
        print("%-30s%-38s%7d%7d%8.1f%10.1f  %s" % (
            det, label, s["n"], s["ok"], pct, 100 * lb, "PASS" if bar else "FAIL"))
        if s["bad"]:
            print("%-68s did not hold: %s" % ("", ", ".join(s["bad"])))
    for k, v in gated_loss.items():
        print("\n   %s: %d" % (k, v))

    print("\n" + "=" * 104)
    print("CORRECTIONS under a TIGHTER gate (concept move must be the TOP move at depth %d)" % DEPTH)
    print("=" * 104)
    engine = chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish")
    for det, cases in neg_cases.items():
        claim = NEG_CLAIMS[det]
        loose_ok = tight_ok = checked = 0
        fails = []
        for gid, mn, san, fen, uc in cases[:40]:
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
            try:
                infos = engine.analyse(b, chess.engine.Limit(depth=DEPTH), multipv=3)
                pb = b.copy()
                pb.push(played)
                pe = engine.analyse(pb, chess.engine.Limit(depth=DEPTH))["score"].pov(uc).score(mate_score=1500)
            except Exception:
                continue
            checked += 1
            top = infos[0]["pv"][0]
            tight = top != played and claim(b, top, uc)
            loose = False
            for info in infos:
                cand = info["pv"][0]
                if cand == played or not claim(b, cand, uc):
                    continue
                cb = b.copy()
                cb.push(cand)
                try:
                    ce = engine.analyse(cb, chess.engine.Limit(depth=DEPTH))["score"].pov(uc).score(mate_score=1500)
                except Exception:
                    continue
                if ce is not None and pe is not None and ce - pe >= CLEARLY_BETTER:
                    loose = True
                    break
            if tight:
                tight_ok += 1
            elif len(fails) < 4:
                fails.append("%s m%s %s" % (gid[:10], mn, san))
            if loose:
                loose_ok += 1
        if checked:
            print("%-26s loose gate %2d/%2d = %3.0f%%   TIGHT gate %2d/%2d = %3.0f%%  (WilsonLB %.0f%%)" % (
                det, loose_ok, checked, 100.0 * loose_ok / checked,
                tight_ok, checked, 100.0 * tight_ok / checked, 100 * wilson(tight_ok, checked)))
            if fails:
                print("%-26s tight gate missed: %s" % ("", ", ".join(fails)))
    engine.quit()


asyncio.run(main())
