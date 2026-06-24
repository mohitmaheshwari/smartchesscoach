"""Regenerate all user motif profiles with the opp_creates_motif field."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from services.motif_profile_service import (
    compute_game_motifs, _verdict, MOTIFS
)

async def main():
    mongo_url = "mongodb://admin_user_mii_s_c:Mii123$44$@72.60.204.176:27017"
    db = AsyncIOMotorClient(mongo_url)['chess_coach']
    
    users = await db.users.find({}, {"_id": 0, "user_id": 1}).to_list(1000)
    print(f"Regenerating motif profiles for {len(users)} users...")
    
    updated = 0
    for idx, user in enumerate(users, 1):
        user_id = user["user_id"]
        
        # Recompute from scratch
        totals = {m: {"made_sound": 0, "made_tunnel": 0, "got": 0, "got_positions": []} for m in MOTIFS}
        n_games = 0
        
        games = await db.games.find(
            {"user_id": user_id, "is_analyzed": True},
            {"_id": 0, "game_id": 1}
        ).to_list(1000)
        
        for g in games:
            a = await db.game_analyses.find_one(
                {"game_id": g["game_id"]},
                {"_id": 0, "stockfish_analysis": 1}
            )
            mevals = (a or {}).get("stockfish_analysis", {}).get("move_evaluations") or []
            if not mevals:
                continue
            
            n_games += 1
            per = compute_game_motifs(mevals, "white")
            
            for mt in MOTIFS:
                for k in ("made_sound", "made_tunnel", "got"):
                    totals[mt][k] += per[mt][k]
                totals[mt]["got_positions"].extend(per[mt]["got_positions"])
        
        if n_games > 0:
            # Apply verdict
            profile = {mt: _verdict(totals[mt], n_games, mt) for mt in MOTIFS}
            
            # Update DB
            result = await db.player_profiles.update_one(
                {"user_id": user_id},
                {"$set": {"motif_profile": profile}}
            )
            
            if result.modified_count > 0:
                updated += 1
            
            if idx % 10 == 0:
                print(f"  {idx}/{len(users)}: updated {updated} so far")
    
    print(f"\nDone! Updated {updated}/{len(users)} profiles")

if __name__ == "__main__":
    asyncio.run(main())
