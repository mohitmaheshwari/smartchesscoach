"""probe_endgame_goodmove.py — fresh-render probe: do GOOD endgame user moves
render a real teaching caption, or fall to silence / a wrong "tidy up the king"?

Fast-testing rule: re-render from the pipeline (NEVER read stored captions).
Calls build_move_teaching_decision per move on REAL analyzed games, filters to
endgame-phase USER moves with cp_loss < 30, and buckets the rendered rule_name.

Run inside chess-coach-backend-dev (direct prod DB).
"""
from __future__ import annotations
import os, sys, io, collections
sys.path.insert(0, "/app/backend")
import chess, chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@72.60.204.176:27017/?authSource=admin")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _fen4(fen: str) -> str:
    return " ".join(fen.split()[:4])


async def main(limit_games: int = 60):
    from services.caption_pipeline import build_move_teaching_decision, MoveInputs, CrossMoveState
    try:
        from services.game_decryption_v5_service import detect_phase
    except Exception:
        detect_phase = None

    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=12000)[DB_NAME]

    buckets = collections.Counter()
    samples = collections.defaultdict(list)
    silent_fens = []
    n_eg_good = 0

    cursor = db.games.find({"is_analyzed": True}, {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1}).limit(limit_games)
    games = await cursor.to_list(length=limit_games)
    print(f"[probe] scanning {len(games)} analyzed games")

    for g in games:
        gid = g.get("game_id")
        pgn = g.get("pgn") or ""
        user_color = (g.get("user_color") or "white").lower()
        analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not analysis:
            continue
        mes = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        by_fen = {_fen4(m.get("fen_before", "")): m for m in mes if m.get("fen_before")}

        try:
            pgn_game = chess.pgn.read_game(io.StringIO(pgn))
        except Exception:
            continue
        if pgn_game is None:
            continue

        board = pgn_game.board()
        history = []
        user_is_white = (user_color == "white")
        state = CrossMoveState()
        for mv in pgn_game.mainline_moves():
            is_user = (board.turn == chess.WHITE) == user_is_white
            try:
                san = board.san(mv)
            except Exception:
                break
            if not is_user:
                board.push(mv); history.append(san); continue
            me = by_fen.get(_fen4(board.fen()))
            if me is None:
                board.push(mv); history.append(san); continue
            cp_loss = int(me.get("cp_loss") or 0)
            fmn = board.fullmove_number
            phase = "opening"
            if detect_phase is not None:
                try:
                    phase = detect_phase(board, fmn)
                except Exception:
                    pass
            if phase != "endgame" or cp_loss >= 30:
                board.push(mv); history.append(san); continue

            n_eg_good += 1
            inp = MoveInputs(
                fen_before=board.fen(), played_san=san, mover_is_user=True,
                mover_is_white=(board.turn == chess.WHITE), user_color=user_color,
                full_move_number=fmn, move_history_san=list(history),
                best_move_san=me.get("best_move"), cp_loss=cp_loss,
                pv_after_played=me.get("pv_after_played") or [],
                pv_after_best=me.get("pv_after_best") or [],
                eval_before_cp=me.get("eval_before"), eval_after_cp=me.get("eval_after"),
                user_rating=1200,
            )
            try:
                dec = build_move_teaching_decision(inp, state)
                _txt = getattr(dec, "text", None)
                cap = ((getattr(_txt, "caption", "") if _txt else "") or "").strip()
                rule = (getattr(_txt, "rule_name", "") if _txt else "") or ""
                if getattr(dec, "should_skip", False):
                    rule = f"SKIP:{getattr(dec, 'skip_reason', '')[:40]}"
                if not cap and len(silent_fens) < 25:
                    silent_fens.append((gid, fmn, san, cp_loss, board.fen(),
                                        me.get("best_move"), me.get("pv_after_played") or [],
                                        me.get("pv_after_best") or [], phase, user_color,
                                        list(history)))
            except Exception as e:
                cap, rule = "", f"ERROR:{repr(e)[:80]}"
            key = rule if cap else (rule + " [SILENT]" if rule else "[SILENT]")
            buckets[key] += 1
            if len(samples[key]) < 4:
                samples[key].append(f"  {gid} m{fmn} {san} (cp{cp_loss}): {cap!r}")
            board.push(mv); history.append(san)

    n_silent = sum(c for k, c in buckets.items() if "[SILENT]" in k)
    print(f"\n[probe] endgame good user moves (cp<30): {n_eg_good} | SILENT: {n_silent}\n")
    for key, cnt in buckets.most_common():
        print(f"{cnt:4d}  {key}")
        for s in samples[key]:
            print(s)
    print()
    if n_silent:
        print(f"[probe] FAIL — {n_silent} endgame good moves render silent (never-silence violation)")
    else:
        print("[probe] PASS — every endgame good move renders a caption")


if __name__ == "__main__":
    asyncio.run(main())
