import os, sys, asyncio, json, collections
sys.path.insert(0,"/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
MONGO=os.environ["MONGO_URL"]; DB=os.environ.get("DB_NAME","chess_coach")
UID="user_8b599930d7ef"
async def main():
    db=AsyncIOMotorClient(MONGO,serverSelectionTimeoutMS=20000)[DB]
    from services.coach_conductor import player_motif_threads, compute_motif_thread
    prof=await db.player_profiles.find_one({"user_id":UID},{"_id":0,"motif_profile":1,"motif_recognition":1,"games_analyzed_count":1}) or {}
    digest=player_motif_threads(prof.get("motif_profile"), prof.get("motif_recognition"), prof.get("games_analyzed_count") or 0)
    games=await db.games.find({"user_id":UID,"is_analyzed":True},{"_id":0,"game_id":1,"user_color":1}).limit(60).to_list(60)
    fires=collections.Counter(); samples=[]; restraint_ok=True; quiz_ok=True; total=0
    for g in games:
        uw=(g.get("user_color") or "white").lower()=="white"
        a=await db.game_analyses.find_one({"game_id":g["game_id"]},{"_id":0,"stockfish_analysis":1})
        mes=((a or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []
        pulled=set(); per=[]
        for ev in mes:
            if ev.get("is_opponent_move"): continue
            total+=1
            eb,ea=ev.get("eval_before"),ev.get("eval_after")
            th=compute_motif_thread(fen_before=ev.get("fen_before"), played_san=ev.get("move"),
                best_move_san=ev.get("best_move"), pv_after_played=ev.get("pv_after_played") or [],
                pv_after_best=ev.get("pv_after_best") or [], cp_loss=ev.get("cp_loss") or 0,
                is_user_move=True, threads=digest, threads_pulled=pulled,
                eval_before_cp=int(eb) if isinstance(eb,(int,float)) else None,
                eval_after_cp=int(ea) if isinstance(ea,(int,float)) else None, mover_is_white=uw)
            if th:
                fires[(th["side"],th["motif"],th["kind"])]+=1; per.append(f"{th['side']}:{th['motif']}")
                if "?" in th["text"]: quiz_ok=False
                if len(samples)<18: samples.append(f"  [{th['kind']:9}] {th['text']}")
        if any(c>1 for c in collections.Counter(per).values()): restraint_ok=False
    print(f"replayed {len(games)} games, {total} user moves")
    print(f"THREADS: {dict(fires)}  (total {sum(fires.values())}, ~{sum(fires.values())/len(games):.1f}/game)")
    print(f"no-quiz: {'PASS' if quiz_ok else 'FAIL'}   restraint: {'PASS' if restraint_ok else 'FAIL'}")
    print("--- samples ---")
    for s in samples: print(s)
    sys.stdout.flush()
asyncio.run(main())
