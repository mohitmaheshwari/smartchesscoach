import sys, asyncio
sys.path.insert(0,"/app/backend")
import chess
FAKE={"kind":"miss","motif":"skewer","side":"offense","text":"FAKE THREAD STATEMENT"}
digest={"defense":{},"offense":{"skewer":{"rate":32,"trend":"down","tier":"Developing"}}}
GOOD="r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"  # fast (good move)

# TEST A — door override: force compute_motif_thread to fire, confirm caption overridden
import services.coach_conductor as cc
cc.compute_motif_thread = lambda **kw: dict(FAKE)
from services.caption_pipeline import build_move_teaching_decision, MoveInputs, CrossMoveState
inp=MoveInputs(fen_before=GOOD,played_san="Bc4",mover_is_user=True,mover_is_white=True,user_color="white",
    full_move_number=3,move_history_san=["e4","e5","Nf3","Nc6"],best_move_san="Bc4",eval_before_cp=30,eval_after_cp=28,
    cp_loss=0,pv_after_played=[],pv_after_best=[],player_motif_threads=digest)
dec=build_move_teaching_decision(inp,CrossMoveState())
A = dec.conductor_thread is not None and dec.text.caption=="FAKE THREAD STATEMENT" and dec.text.rule_name=="R_CONDUCTOR_thread"
print(f"TEST A (door override):           {'PASS' if A else 'FAIL'}  caption={dec.text.caption!r}",flush=True)

# TEST B — generate_move_coaching short-circuit: thread WINS over policy gate
async def b():
    import services.shared_coaching_v5 as scv
    scv._central_narrative_for_move = lambda **kw: ("FAKE THREAD STATEMENT","mistake",dict(FAKE))
    from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
    bd=chess.Board(GOOD); mv=bd.parse_san("Bc4")
    c=await generate_move_coaching(board_before=bd,move=mv,best_move_san="Bc4",pv_after_played=[],pv_after_best=[],
        cp_loss=0,phase="opening",is_user_move=True,context=CoachingContext.LIVE_AFTER_USER,user_color="white",
        move_history_san=[],eval_before_cp=30,eval_after_cp=28,player_motif_threads=digest,session_conductor_threads_pulled=set())
    B = getattr(c,"conductor_thread",None) is not None and c.narrative=="FAKE THREAD STATEMENT" and not c.suppress and "?" not in c.narrative
    print(f"TEST B (live short-circuit wins): {'PASS' if B else 'FAIL'}  narrative={c.narrative!r} suppress={c.suppress}",flush=True)
asyncio.run(b())
