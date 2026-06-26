"""Pull Mohit's real chess profile from prod and dump the raw intelligence a coach
would walk in knowing. We synthesize the 'coach's read' from this."""
from __future__ import annotations
import os, sys, asyncio, collections, datetime
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
MONGO=os.environ.get("MONGO_URL"); DB=os.environ.get("DB_NAME","chess_coach")
EMAIL=os.environ.get("EMAIL","bhutramohit@gmail.com")

async def main():
    db=AsyncIOMotorClient(MONGO,serverSelectionTimeoutMS=20000)[DB]
    # 1. find the account: by email, else the user_id with most analyzed games
    users=await db.users.find({}, {"_id":0,"user_id":1,"email":1,"rating":1,"chess_com_username":1,"lichess_username":1}).to_list(50)
    print("ACCOUNTS:")
    counts={}
    for u in users:
        n=await db.games.count_documents({"user_id":u["user_id"]})
        na=await db.games.count_documents({"user_id":u["user_id"],"is_analyzed":True})
        counts[u["user_id"]]=(n,na,u)
        print(f"  {u.get('email','?'):35} {u['user_id']:22} games={n} analyzed={na} rating={u.get('rating')} cc={u.get('chess_com_username')}")
    # choose
    uid=None
    for u in users:
        if (u.get("email") or "").lower()==EMAIL.lower() and counts[u["user_id"]][1]>0:
            uid=u["user_id"]; break
    if not uid:
        uid=max(counts, key=lambda k: counts[k][1])
    chosen=counts[uid][2]
    print(f"\n>>> READING: {chosen.get('email')} / {uid} (games={counts[uid][0]} analyzed={counts[uid][1]} rating={chosen.get('rating')})\n"+"="*70)

    # 2. player identity engine
    try:
        from player_identity_engine import compute_player_identity
        pid=compute_player_identity(db, uid)
        if asyncio.iscoroutine(pid): pid=await pid
        print("\n[PLAYER IDENTITY ENGINE]");
        import json
        print(json.dumps(pid, indent=2, default=str)[:2500])
    except Exception as e:
        print(f"[player_identity] ERR {e}")

    # 3. cognitive gap distribution + recency trend
    try:
        cg=await db.cognitive_gap_history.find({"user_id":uid},{"_id":0}).to_list(5000)
        print(f"\n[COGNITIVE GAPS]  total entries={len(cg)}")
        by=collections.Counter(); recent=collections.Counter()
        now=datetime.datetime.now(datetime.timezone.utc)
        for e in cg:
            t=e.get("gap_type") or e.get("type") or e.get("cognitive_gap") or "?"
            by[t]+=1
            d=e.get("created_at") or e.get("date")
            try:
                if isinstance(d,str): d=datetime.datetime.fromisoformat(d.replace("Z","+00:00"))
                if d and (now-d).days<=30: recent[t]+=1
            except Exception: pass
        print("  ALL-TIME by gap:", dict(by.most_common(12)))
        print("  LAST 30 DAYS  :", dict(recent.most_common(12)))
    except Exception as e:
        print(f"[cognitive_gap] ERR {e}")

    # 4. accuracy / blunders from analyses + recent results
    try:
        games=await db.games.find({"user_id":uid,"is_analyzed":True},{"_id":0,"game_id":1,"result":1,"user_color":1,"opening":1,"end_time":1,"pgn":1}).sort("end_time",-1).to_list(80)
        res=collections.Counter(g.get("result","?") for g in games)
        print(f"\n[RESULTS] last {len(games)} analyzed: {dict(res)}")
        accs=[]; bl=0; mi=0; nn=0
        op=collections.Counter()
        for g in games:
            op[(g.get('opening') or '?')[:30]]+=1
            a=await db.game_analyses.find_one({"game_id":g["game_id"]},{"_id":0,"stockfish_analysis":1})
            sa=(a or {}).get("stockfish_analysis") or {}
            acc=sa.get("accuracy_white") if g.get("user_color")=="white" else sa.get("accuracy_black")
            if isinstance(acc,(int,float)): accs.append(acc)
            mes=sa.get("move_evaluations") or []
            for m in mes:
                if m.get("is_user_move") is False: continue
                cl=m.get("cp_loss") or 0
                nn+=1
                if cl>=200: bl+=1
                elif cl>=100: mi+=1
        if accs: print(f"  avg accuracy={sum(accs)/len(accs):.1f}  (n={len(accs)})  range {min(accs):.0f}-{max(accs):.0f}")
        if nn: print(f"  user moves={nn}  blunders(>=200cp)={bl} ({100*bl/nn:.1f}%)  mistakes(100-200)={mi} ({100*mi/nn:.1f}%)")
        print("  top openings:", dict(op.most_common(6)))
    except Exception as e:
        print(f"[accuracy] ERR {e}")

    # 5. coach memory + identity doc
    try:
        cm=await db.coach_memory.find_one({"user_id":uid},{"_id":0})
        if cm:
            print("\n[COACH MEMORY]")
            print("  weaknesses:", cm.get("weaknesses"))
            print("  strengths :", cm.get("strengths"))
            print("  notes     :", (cm.get("coach_notes") or [])[:5])
        pi=await db.player_identities.find_one({"user_id":uid},{"_id":0})
        if pi:
            print("\n[player_identities doc] keys:", list(pi.keys())[:20])
            print("  style_profile:", str(pi.get("style_profile"))[:400])
            print("  blunder_taxonomy:", str(pi.get("blunder_taxonomy"))[:400])
    except Exception as e:
        print(f"[memory] ERR {e}")

if __name__=="__main__":
    asyncio.run(main()); sys.stdout.flush()
    import os as _o; _o._exit(0)
