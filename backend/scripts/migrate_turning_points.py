"""
Migration Script: Calculate and store turning points for all analyzed games.

This enables the Blind Spots feature on the homepage by backfilling
turning_point data into existing game_analyses documents.
"""

import asyncio
import os
import sys
import logging

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from services.turning_point_explainer import get_turning_point_explainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_turning_points")


async def calculate_turning_point_for_analysis(analysis, game, explainer):
    """Calculate turning point for a single game analysis."""
    
    sf = analysis.get("stockfish_analysis", {})
    move_evals = sf.get("move_evaluations", [])
    user_color = game.get("user_color", "white") if game else "white"
    
    # Get user rating
    user_rating = 1200
    if game:
        if user_color == "white":
            user_rating = game.get("white_rating") or 1200
        else:
            user_rating = game.get("black_rating") or 1200
    
    if not move_evals:
        return None
    
    def user_eval(eval_val, color):
        if eval_val is None:
            return 0
        return eval_val if color == "white" else -eval_val
    
    turning_point_candidates = []
    
    for i, m in enumerate(move_evals):
        move_num = m.get("move_number", i + 1)
        eval_before = user_eval(m.get("eval_before"), user_color)
        eval_after = user_eval(m.get("eval_after"), user_color)
        cp_loss = abs(m.get("cp_loss", 0))
        eval_drop = eval_before - eval_after
        
        if cp_loss < 150:
            continue
        
        remaining_moves = move_evals[i + 1:]
        if not remaining_moves:
            continue
        
        max_user_recovery = eval_after
        opponent_gave_back = 0
        
        for j, future_m in enumerate(remaining_moves[:5]):
            future_eval_before = user_eval(future_m.get("eval_before"), user_color)
            future_eval_after = user_eval(future_m.get("eval_after"), user_color)
            
            if future_eval_before > max_user_recovery:
                max_user_recovery = future_eval_before
            if future_eval_after > max_user_recovery:
                max_user_recovery = future_eval_after
            
            if j == 0:
                if future_eval_before - eval_after > 100:
                    opponent_gave_back += 1
            else:
                prev_eval_after = user_eval(remaining_moves[j-1].get("eval_after"), user_color)
                if future_eval_before - prev_eval_after > 100:
                    opponent_gave_back += 1
        
        never_recovered = max_user_recovery < -150
        opponent_played_well_after = opponent_gave_back <= 1
        
        if never_recovered and opponent_played_well_after:
            turning_point_candidates.append({
                "move_number": move_num,
                "move": m.get("move"),
                "best_move": m.get("best_move"),
                "move_uci": m.get("move_uci"),
                "best_move_uci": m.get("best_move_uci"),
                "eval_before": m.get("eval_before"),
                "eval_after": m.get("eval_after"),
                "cp_loss": cp_loss,
                "eval_drop": eval_drop,
                "fen_before": m.get("fen_before"),
                "threat": m.get("threat"),
            })
    
    if not turning_point_candidates:
        return None
    
    # Pick earliest significant drop
    significant = [c for c in turning_point_candidates if c["eval_drop"] >= 200]
    if significant:
        tp_data = min(significant, key=lambda x: x["move_number"])
    else:
        tp_data = min(turning_point_candidates, key=lambda x: x["move_number"])
    
    # Generate rich explanation
    try:
        explanation = await explainer.explain(
            fen=tp_data.get("fen_before", ""),
            user_move=tp_data.get("move", ""),
            best_move=tp_data.get("best_move", ""),
            cp_loss=int(tp_data.get("eval_drop", 0)),
            user_rating=user_rating,
            threat=tp_data.get("threat"),
            eval_before=tp_data.get("eval_before"),
            eval_after=tp_data.get("eval_after")
        )
        
        return {
            "move_number": tp_data["move_number"],
            "move": tp_data.get("move", ""),
            "best_move": tp_data.get("best_move", ""),
            "move_uci": tp_data.get("move_uci", ""),
            "best_move_uci": tp_data.get("best_move_uci", ""),
            "eval_drop": tp_data["eval_drop"],
            "type": "true_turning_point",
            "description": explanation.main_text,
            "missed_idea": explanation.missed_idea,
            "category": explanation.category,
            "category_label": explanation.category_label,
            "pattern_name": explanation.pattern_name,
            "how_to_spot": explanation.how_to_spot,
            "training_focus": explanation.training_focus
        }
    except Exception as e:
        logger.warning(f"Explainer failed for game {tp_data.get('move')}: {e}")
        return {
            "move_number": tp_data["move_number"],
            "move": tp_data.get("move", ""),
            "best_move": tp_data.get("best_move", ""),
            "eval_drop": tp_data["eval_drop"],
            "type": "true_turning_point",
            "category": "unknown",
            "category_label": "Unknown",
            "pattern_name": "Unclassified"
        }


async def migrate():
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
    db_name = os.environ.get("DB_NAME", "test_database")
    db = client[db_name]
    
    logger.info(f"Connected to database: {db_name}")
    
    # Get all analyses
    analyses = await db.game_analyses.find(
        {},
        {"_id": 1, "game_id": 1, "user_id": 1, "stockfish_analysis": 1, "turning_point": 1}
    ).to_list(200)
    
    logger.info(f"Found {len(analyses)} game analyses")
    
    explainer = get_turning_point_explainer()
    
    updated = 0
    skipped = 0
    no_tp = 0
    
    for analysis in analyses:
        game_id = analysis.get("game_id")
        
        # Skip if already has turning point
        if analysis.get("turning_point"):
            skipped += 1
            continue
        
        # Get game data
        game = await db.games.find_one(
            {"game_id": game_id, "user_id": analysis.get("user_id")},
            {"_id": 0, "user_color": 1, "white_rating": 1, "black_rating": 1}
        )
        
        tp = await calculate_turning_point_for_analysis(analysis, game, explainer)
        
        if tp:
            await db.game_analyses.update_one(
                {"_id": analysis["_id"]},
                {"$set": {"turning_point": tp}}
            )
            updated += 1
            logger.info(f"  [{updated}] {game_id}: Move {tp['move_number']} {tp['move']} -> {tp.get('category_label', 'N/A')}")
        else:
            no_tp += 1
    
    logger.info(f"Migration complete: {updated} updated, {skipped} already had TP, {no_tp} no turning point found")


if __name__ == "__main__":
    asyncio.run(migrate())
