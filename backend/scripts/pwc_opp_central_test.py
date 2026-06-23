"""pwc_opp_central_test.py — prove opponent moves now route through the central
door (review-quality + verified) when fed eval, instead of the shallow legacy
"Opponent plays X". Samples real opponent positions, computes eval at depth ~12
(client-WASM stand-in), feeds generate_move_coaching(is_user_move=False), and
shows central-vs-legacy + a per-FEN verify. docs/pwc_client_eval_scope.md."""
import sys; sys.path.insert(0, "/app/backend")
import os, io, asyncio
import chess, chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

MONGO = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@72.60.204.176:27017/?authSource=admin")
DB = "chess_coach"
N_OPP = 25


async def main():
    from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
    from services.narrator_claim_verifier import verify_caption
    from stockfish_service import get_position_evaluation
    db = AsyncIOMotorClient(MONGO, serverSelectionTimeoutMS=12000)[DB]

    games = await db.games.find({"is_analyzed": True}, {"_id": 0, "pgn": 1, "user_color": 1}).limit(12).to_list(12)
    rows = []
    for g in games:
        uc = (g.get("user_color") or "white").lower()
        try:
            pg = chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
        except Exception:
            continue
        if pg is None: continue
        board = pg.board(); hist = []; uw = (uc == "white")
        for mv in pg.mainline_moves():
            is_user = (board.turn == chess.WHITE) == uw
            try: san = board.san(mv)
            except Exception: break
            if not is_user and 6 <= board.fullmove_number <= 30 and len(rows) < N_OPP:
                # client-WASM stand-in: eval before + after (depth 12), opp best move
                try:
                    eb = get_position_evaluation(board.fen(), depth=12)
                    eb_cp = (eb.get("evaluation") or {}).get("centipawns")
                    best = (eb.get("best_move") or {}).get("san")
                    pv_best = (eb.get("info") or {}).get("pv_san") or []
                    after = board.copy(); after.push(mv)
                    ea = get_position_evaluation(after.fen(), depth=12)
                    ea_cp = (ea.get("evaluation") or {}).get("centipawns")
                    pv_played = (ea.get("info") or {}).get("pv_san") or []
                except Exception:
                    board.push(mv); hist.append(san); continue
                opp_cp_loss = max(0, (eb_cp or 0) - (-(ea_cp or 0))) if board.turn == chess.WHITE else max(0, (-(eb_cp or 0)) - (ea_cp or 0))
                rows.append((board.copy(), mv, san, uc, list(hist), best, eb_cp, ea_cp,
                             int(opp_cp_loss), pv_played, pv_best))
            board.push(mv); hist.append(san)
        if len(rows) >= N_OPP: break

    central = legacy = false_claim = 0
    print(f"testing {len(rows)} opponent moves (fed depth-12 eval)\n")
    for (b, mv, san, uc, hist, best, eb, ea, ocl, pvp, pvb) in rows:
        try:
            c = await generate_move_coaching(
                board_before=b, move=mv, best_move_san=best,
                pv_after_played=pvp, pv_after_best=pvb, cp_loss=ocl, phase="middlegame",
                is_user_move=False, context=CoachingContext.LIVE_AFTER_COACH, user_color=uc,
                move_history_san=hist, eval_before_cp=eb, eval_after_cp=ea,
            )
            narr = (getattr(c, "narrative", "") or "").strip()
        except Exception as e:
            narr = f"ERR {e}"
        is_legacy = narr.startswith("Opponent ") or narr.startswith("Check!") or narr.startswith("Watch out")
        tag = "LEGACY" if is_legacy else "CENTRAL"
        if is_legacy: legacy += 1
        else: central += 1
        # verify
        bad = ""
        if not is_legacy and narr and not narr.startswith("ERR"):
            ba = b.copy(); ba.push(mv)
            v = verify_caption(narr, {"move_san": san, "fen_before": b.fen(), "fen_after": ba.fen(),
                                      "is_user_move": False, "cp_loss": ocl, "best_move_san": best,
                                      "pv_after_played": pvp, "pv_after_best": pvb})
            if v: bad = "  <<FALSE-CLAIM>>"; false_claim += 1
        print(f"  [{tag}] {san}: {narr[:100]}{bad}")
    print(f"\ncentral={central}  legacy-fallback={legacy}  false-claims={false_claim}")


if __name__ == "__main__":
    asyncio.run(main())
    sys.stdout.flush()
    import os as _os; _os._exit(0)
