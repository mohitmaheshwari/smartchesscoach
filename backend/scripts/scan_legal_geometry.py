"""
Corpus scan: Legal's Trap geometry across all prod games.

Implements the geometric trigger spec from [[tac-legal-geometry-detector]]:
  Guard 1: knight pinned (relative pin) by enemy bishop to queen/rook along a diagonal
  Guard 2: pinned knight has a forcing jump that captures + opens the pin diagonal
  Guard 3: STM has a bishop already attacking opponent's f-square (f2 or f7)
  Guard 4: opponent king uncastled (on e1/e8 with castling rights still present)
  Guard 5: Stockfish validates the forcing continuation (run on candidates only)

NOT a V5 detector — this is a research audit per [[per-fire-audit-pattern]] to
confirm how many real games carry the geometry before we ship TAC_LEGAL_PATTERN.

Usage:
  MONGO_URL=mongodb://user:pass@host:27018/?authSource=admin \\
    docker exec -i chess-coach-backend python scripts/scan_legal_geometry.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import chess
import chess.engine
import chess.pgn
from pymongo import MongoClient

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
SF_DEPTH = int(os.environ.get("SF_DEPTH", "18"))
SF_MULTIPV = 3
MAX_GAMES = int(os.environ.get("MAX_GAMES", "0"))  # 0 = no cap

_VALUABLE_TARGETS = {chess.QUEEN, chess.ROOK}


def _find_diagonal_pin(board: chess.Board, knight_sq: int, bishop_sq: int, stm: bool) -> Optional[tuple]:
    """If knight at knight_sq is pinned by enemy bishop at bishop_sq to a queen/rook
    of `stm` along the SAME diagonal (bishop → knight → target, clear between),
    return (target_piece_type_name, target_sq). Otherwise None."""
    # Must be on same diagonal
    file_diff = chess.square_file(knight_sq) - chess.square_file(bishop_sq)
    rank_diff = chess.square_rank(knight_sq) - chess.square_rank(bishop_sq)
    if file_diff == 0 or rank_diff == 0 or abs(file_diff) != abs(rank_diff):
        return None

    step_file = 1 if file_diff > 0 else -1
    step_rank = 1 if rank_diff > 0 else -1

    # Verify clear path from bishop → knight (exclusive of both ends)
    f, r = chess.square_file(bishop_sq) + step_file, chess.square_rank(bishop_sq) + step_rank
    while (f, r) != (chess.square_file(knight_sq), chess.square_rank(knight_sq)):
        sq = chess.square(f, r)
        if board.piece_at(sq):
            return None
        f += step_file
        r += step_rank

    # Continue past knight and find first occupant
    f, r = chess.square_file(knight_sq) + step_file, chess.square_rank(knight_sq) + step_rank
    while 0 <= f < 8 and 0 <= r < 8:
        sq = chess.square(f, r)
        p = board.piece_at(sq)
        if p:
            if p.color == stm and p.piece_type in _VALUABLE_TARGETS:
                return (chess.piece_name(p.piece_type), sq)
            return None
        f += step_file
        r += step_rank
    return None


def _legal_jumps_opening_pin(
    board: chess.Board, knight_sq: int, bishop_sq: int, target_sq: int
) -> list[chess.Move]:
    """Return legal knight moves that capture AND remove knight from the
    bishop→target diagonal (so the target attacks the bishop after the move)."""
    out = []
    # The diagonal squares of the pin
    df = (chess.square_file(target_sq) - chess.square_file(bishop_sq))
    dr = (chess.square_rank(target_sq) - chess.square_rank(bishop_sq))
    sf = 1 if df > 0 else -1
    sr = 1 if dr > 0 else -1
    diag_squares = set()
    f, r = chess.square_file(bishop_sq), chess.square_rank(bishop_sq)
    while (f, r) != (chess.square_file(target_sq), chess.square_rank(target_sq)):
        diag_squares.add(chess.square(f, r))
        f += sf
        r += sr
    diag_squares.add(target_sq)

    for mv in board.legal_moves:
        if mv.from_square != knight_sq:
            continue
        if not board.is_capture(mv):
            continue
        if mv.to_square in diag_squares:
            continue  # didn't leave the diagonal
        out.append(mv)
    return out


def _stm_bishop_attacks_f_square(board: chess.Board, stm: bool) -> Optional[int]:
    """Returns square attacked (chess.F2 or chess.F7) if STM has a bishop that
    already attacks the opponent's f-square. None otherwise."""
    f_target = chess.F7 if stm == chess.WHITE else chess.F2
    for sq in board.pieces(chess.BISHOP, stm):
        if f_target in board.attacks(sq):
            return f_target
    return None


def _enemy_king_uncastled(board: chess.Board, enemy_color: bool) -> bool:
    king_sq = board.king(enemy_color)
    if king_sq is None:
        return False
    start_sq = chess.E1 if enemy_color == chess.WHITE else chess.E8
    if king_sq != start_sq:
        return False
    return board.has_kingside_castling_rights(enemy_color) or board.has_queenside_castling_rights(enemy_color)


def scan_position(board: chess.Board) -> list[dict]:
    """Return list of Legal-geometry candidates for the side-to-move."""
    stm = board.turn
    enemy = not stm
    candidates = []

    for knight_sq in list(board.pieces(chess.KNIGHT, stm)):
        for bishop_sq in list(board.pieces(chess.BISHOP, enemy)):
            pin_info = _find_diagonal_pin(board, knight_sq, bishop_sq, stm)
            if not pin_info:
                continue
            target_piece, target_sq = pin_info

            jumps = _legal_jumps_opening_pin(board, knight_sq, bishop_sq, target_sq)
            if not jumps:
                continue

            f_target = _stm_bishop_attacks_f_square(board, stm)
            if f_target is None:
                continue

            if not _enemy_king_uncastled(board, enemy):
                continue

            candidates.append({
                "stm": "white" if stm == chess.WHITE else "black",
                "knight_sq": chess.square_name(knight_sq),
                "pinning_bishop_sq": chess.square_name(bishop_sq),
                "target_piece": target_piece,
                "target_sq": chess.square_name(target_sq),
                "f_square_attacked": chess.square_name(f_target),
                "candidate_jumps_san": [board.san(j) for j in jumps],
                "candidate_jumps_uci": [j.uci() for j in jumps],
            })
    return candidates


def validate_with_stockfish(board: chess.Board, candidate: dict, engine: chess.engine.SimpleEngine) -> dict:
    """Guard 5: confirm the Legal jump is engine-approved (top-3 best for STM)
    AND that the greedy queen-grab response loses for the pinner."""
    info = engine.analyse(board, chess.engine.Limit(depth=SF_DEPTH), multipv=SF_MULTIPV)
    top_moves = []
    for line in info:
        pv = line.get("pv") or []
        if not pv:
            continue
        b2 = board.copy()
        try:
            san = b2.san(pv[0])
        except Exception:
            san = pv[0].uci()
        sc = line.get("score")
        cp = sc.pov(board.turn).score(mate_score=100000) if sc else None
        top_moves.append({"san": san, "uci": pv[0].uci(), "cp": cp})

    jump_in_top = any(j in [m["san"] for m in top_moves] for j in candidate["candidate_jumps_san"])

    # Greedy line: after the engine's #1 Legal jump, what does engine play for opponent?
    greedy_line_loses = None
    if jump_in_top:
        jump_san = next(j for j in candidate["candidate_jumps_san"] if j in [m["san"] for m in top_moves])
        b3 = board.copy()
        b3.push_san(jump_san)
        # Simulate the queen-grab by finding the bishop x target capture
        target_uci = candidate["pinning_bishop_sq"] + candidate["target_sq"]
        try:
            grab_move = chess.Move.from_uci(target_uci)
            if grab_move in b3.legal_moves:
                b4 = b3.copy()
                b4.push(grab_move)
                info2 = engine.analyse(b4, chess.engine.Limit(depth=SF_DEPTH))
                sc2 = info2.get("score")
                cp2 = sc2.pov(board.turn).score(mate_score=100000) if sc2 else None
                # After our jump and opponent grabs queen, eval should favor STM (the legal trapper)
                greedy_line_loses = cp2 is not None and cp2 > 200
        except Exception:
            greedy_line_loses = None

    return {
        "jump_in_top3": jump_in_top,
        "engine_top_moves": top_moves,
        "greedy_queen_grab_loses_for_pinner": greedy_line_loses,
    }


def replay_pgn_and_scan(pgn_text: str, game_id: str, engine: Optional[chess.engine.SimpleEngine]) -> list[dict]:
    """Walk the PGN, scan every position, return fires."""
    fires = []
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
    except Exception:
        return []
    if game is None:
        return []
    board = game.board()
    ply = 0
    for mv in game.mainline_moves():
        # Scan BEFORE the move is played (i.e. what the side-to-move could do)
        candidates = scan_position(board)
        if candidates:
            # Capture the actual SAN about to be played so we can classify
            # missed-vs-played teaching gold without a DB re-query.
            try:
                actual_san = board.san(mv)
            except Exception:
                actual_san = mv.uci()
            for c in candidates:
                played_correct = actual_san in c.get("candidate_jumps_san", [])
                fire = {
                    "game_id": game_id,
                    "ply": ply,
                    "move_number": (ply // 2) + 1,
                    "side_to_move": c["stm"],
                    "fen_before": board.fen(),
                    "candidate": c,
                    "actual_move_san": actual_san,
                    "legal_jump_played": played_correct,
                }
                if engine is not None:
                    try:
                        fire["stockfish"] = validate_with_stockfish(board, c, engine)
                    except Exception as e:
                        fire["stockfish_error"] = str(e)
                fires.append(fire)
        # Push and advance
        try:
            board.push(mv)
            ply += 1
        except Exception:
            break
    return fires


def main():
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("ERROR: MONGO_URL env var required.", file=sys.stderr)
        sys.exit(1)

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    use_engine = os.environ.get("SKIP_STOCKFISH", "0") != "1"
    engine = None
    if use_engine:
        try:
            engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        except Exception as e:
            print(f"WARN: stockfish unavailable ({e}); proceeding geometry-only.", file=sys.stderr)
            engine = None

    cursor = db.games.find({"pgn": {"$exists": True, "$ne": ""}}, {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "opponent_username": 1, "result": 1})
    if MAX_GAMES > 0:
        cursor = cursor.limit(MAX_GAMES)

    total_games = 0
    total_fires = 0
    games_with_fire = 0
    all_fires = []
    t0 = time.time()

    for g in cursor:
        total_games += 1
        fires = replay_pgn_and_scan(g.get("pgn") or "", g.get("game_id") or "", engine)
        if fires:
            games_with_fire += 1
            total_fires += len(fires)
            for f in fires:
                f["opponent_username"] = g.get("opponent_username")
                f["user_color"] = g.get("user_color")
                f["result"] = g.get("result")
            all_fires.extend(fires)

    if engine is not None:
        engine.quit()

    elapsed = time.time() - t0

    out_path = Path(os.environ.get("LEGAL_OUTPUT", "/tmp/legal_geometry_scan.json"))
    out_path.write_text(json.dumps({
        "elapsed_seconds": round(elapsed, 1),
        "games_scanned": total_games,
        "games_with_fire": games_with_fire,
        "total_fires": total_fires,
        "fires": all_fires,
    }, indent=2))

    # Summary to stdout
    print(f"Scanned {total_games} games in {elapsed:.1f}s")
    print(f"Games with Legal geometry: {games_with_fire}")
    print(f"Total fires: {total_fires}")
    if engine is not None and all_fires:
        sf_approved = sum(1 for f in all_fires if (f.get("stockfish") or {}).get("jump_in_top3"))
        print(f"Stockfish-approved (jump in top-3): {sf_approved}/{total_fires}")
        sf_punished = sum(1 for f in all_fires if (f.get("stockfish") or {}).get("greedy_queen_grab_loses_for_pinner"))
        print(f"Greedy queen-grab loses for pinner: {sf_punished}/{total_fires}")

        # Teaching-gold breakdown (the actual product output)
        confirmed = [f for f in all_fires if (f.get("stockfish") or {}).get("greedy_queen_grab_loses_for_pinner")]
        user_missed = [f for f in confirmed if f.get("user_color") == f["candidate"]["stm"] and not f.get("legal_jump_played")]
        user_played = [f for f in confirmed if f.get("user_color") == f["candidate"]["stm"] and f.get("legal_jump_played")]
        opp_missed = [f for f in confirmed if f.get("user_color") != f["candidate"]["stm"] and not f.get("legal_jump_played")]
        opp_played = [f for f in confirmed if f.get("user_color") != f["candidate"]["stm"] and f.get("legal_jump_played")]
        print(f"\n=== TEACHING-GOLD BREAKDOWN ===")
        print(f"  GOLD (user had Legal, missed it):       {len(user_missed)}")
        print(f"  CELEBRATION (user played Legal):        {len(user_played)}")
        print(f"  LUCKY (opponent had Legal, missed):     {len(opp_missed)}")
        print(f"  WARNING (opponent landed Legal on you): {len(opp_played)}")
    print(f"\nFull report: {out_path}")


if __name__ == "__main__":
    main()
