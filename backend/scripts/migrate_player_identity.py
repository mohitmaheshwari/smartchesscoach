"""
Migration Script: Populate PlayerIdentity from Existing Data
============================================================

This script analyzes existing coach sessions and game analyses
to populate the new PlayerIdentity system with historical data.

Run this once to bootstrap the memory system.
"""

import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our services
import sys
sys.path.insert(0, '/app/backend')

from services.player_identity import (
    PlayerIdentityService,
    BlunderType,
    BlunderRecord,
    PatternHistoryEntry,
    GamePhase
)


async def migrate_user_data(db, user_id: str):
    """Migrate existing data for a single user"""
    service = PlayerIdentityService(db)
    identity = await service.get_or_create(user_id)
    
    logger.info(f"Migrating data for user: {user_id}")
    
    # 1. Get coach sessions
    sessions = await db.coach_sessions.find(
        {"user_id": user_id, "moves": {"$exists": True}}
    ).sort("created_at", -1).to_list(100)
    
    logger.info(f"  Found {len(sessions)} coach sessions")
    
    for session in reversed(sessions):  # Process oldest first
        result = session.get("result", "draw")
        moves = session.get("moves", [])
        opponent = session.get("opponent", "Coach")
        created_at = session.get("created_at", datetime.now(timezone.utc))
        
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                created_at = datetime.now(timezone.utc)
        
        # Update basic stats
        identity.games_analyzed += 1
        
        if result == "win":
            identity.total_wins += 1
            identity.consecutive_wins += 1
            identity.consecutive_losses = 0
        elif result == "loss":
            identity.total_losses += 1
            identity.consecutive_losses += 1
            identity.consecutive_wins = 0
        else:
            identity.total_draws += 1
            identity.consecutive_wins = 0
            identity.consecutive_losses = 0
        
        identity.last_game_result = result
        
        # Process moves for blunders
        player_moves = [m for m in moves if m.get("by") == "player"]
        
        for move in player_moves:
            cp_loss = move.get("cp_loss", 0)
            
            if cp_loss < 100:
                continue  # Not a significant mistake
            
            # Classify blunder
            move_num = move.get("move_number", 0)
            fen = move.get("fen_before", "")
            
            # Determine phase
            if move_num <= 15:
                phase = GamePhase.OPENING
            elif move_num <= 40:
                phase = GamePhase.MIDDLEGAME
            else:
                phase = GamePhase.ENDGAME
            
            # Simple blunder type classification
            blunder_type = BlunderType.CALCULATION_ERROR
            if cp_loss >= 300:
                blunder_type = BlunderType.HANGING_PIECE
            elif move.get("time_spent", 10) < 2:
                blunder_type = BlunderType.IMPULSE_MOVE
            
            # Update taxonomy
            identity.blunder_taxonomy.total_blunders += 1
            
            type_key = blunder_type.value
            identity.blunder_taxonomy.by_type[type_key] = \
                identity.blunder_taxonomy.by_type.get(type_key, 0) + 1
            
            phase_key = phase.value
            identity.blunder_taxonomy.by_phase[phase_key] = \
                identity.blunder_taxonomy.by_phase.get(phase_key, 0) + 1
            
            # Add to pattern history
            entry = PatternHistoryEntry(
                pattern_type=blunder_type.value,
                game_id=session.get("session_id", "unknown"),
                move_number=move_num,
                opponent=opponent,
                date=created_at,
                description=f"Blunder on move {move_num}"
            )
            identity.pattern_history.append(entry)
    
    # 2. Get game analyses for more detailed info
    analyses = await db.game_analyses.find(
        {"user_id": user_id}
    ).sort("analyzed_at", -1).to_list(50)
    
    logger.info(f"  Found {len(analyses)} game analyses")
    
    # Process game analyses
    for analysis in analyses:
        # Each analysis is a game
        identity.games_analyzed += 1
        
        # Extract result if available
        result = analysis.get("result", "draw")
        if "white_wins" in str(analysis.get("game_id", "")).lower() or \
           analysis.get("user_won"):
            result = "win"
        elif "black_wins" in str(analysis.get("game_id", "")).lower() or \
             analysis.get("user_lost"):
            result = "loss"
        
        if result == "win":
            identity.total_wins += 1
        elif result == "loss":
            identity.total_losses += 1
        else:
            identity.total_draws += 1
        
        # Extract learning moments as patterns
        moments = analysis.get("learning_moments", [])
        stockfish = analysis.get("stockfish_analysis", {})
        
        # Process stockfish analysis for blunders
        move_analyses = stockfish.get("move_analyses", [])
        for ma in move_analyses:
            cp_loss = ma.get("cp_loss", 0)
            if cp_loss >= 100:
                move_num = ma.get("move_number", 0)
                
                # Determine phase
                if move_num <= 15:
                    phase = GamePhase.OPENING
                elif move_num <= 40:
                    phase = GamePhase.MIDDLEGAME
                else:
                    phase = GamePhase.ENDGAME
                
                # Classify
                blunder_type = BlunderType.CALCULATION_ERROR
                if cp_loss >= 300:
                    blunder_type = BlunderType.HANGING_PIECE
                elif "fork" in str(ma.get("best_move_reason", "")).lower():
                    blunder_type = BlunderType.MISSED_FORK
                elif "pin" in str(ma.get("best_move_reason", "")).lower():
                    blunder_type = BlunderType.MISSED_PIN
                
                identity.blunder_taxonomy.total_blunders += 1
                
                type_key = blunder_type.value
                identity.blunder_taxonomy.by_type[type_key] = \
                    identity.blunder_taxonomy.by_type.get(type_key, 0) + 1
                
                phase_key = phase.value
                identity.blunder_taxonomy.by_phase[phase_key] = \
                    identity.blunder_taxonomy.by_phase.get(phase_key, 0) + 1
                
                # Add pattern
                entry = PatternHistoryEntry(
                    pattern_type=blunder_type.value,
                    game_id=analysis.get("game_id", "unknown"),
                    move_number=move_num,
                    opponent=analysis.get("opponent", "unknown"),
                    date=analysis.get("analyzed_at", datetime.now(timezone.utc)),
                    description=f"Missed {blunder_type.value} on move {move_num}"
                )
                identity.pattern_history.append(entry)
        
        # Also process learning moments
        for moment in moments:
            if moment.get("type") in ["blunder", "mistake"]:
                entry = PatternHistoryEntry(
                    pattern_type=BlunderType.CALCULATION_ERROR.value,
                    game_id=analysis.get("game_id", "unknown"),
                    move_number=moment.get("move_number", 0),
                    opponent=analysis.get("opponent", "unknown"),
                    date=analysis.get("analyzed_at", datetime.now(timezone.utc)),
                    description=moment.get("explanation", "Mistake")[:100]
                )
                identity.pattern_history.append(entry)
    
    # Trim pattern history
    if len(identity.pattern_history) > 100:
        identity.pattern_history = identity.pattern_history[-100:]
    
    # Calculate most common type
    if identity.blunder_taxonomy.by_type:
        most_common = max(identity.blunder_taxonomy.by_type, 
                         key=identity.blunder_taxonomy.by_type.get)
        identity.blunder_taxonomy.most_common_type = BlunderType(most_common)
    
    # Calculate worst phase
    if identity.blunder_taxonomy.by_phase:
        worst = max(identity.blunder_taxonomy.by_phase,
                   key=identity.blunder_taxonomy.by_phase.get)
        identity.blunder_taxonomy.worst_phase = GamePhase(worst)
    
    # Set style based on games played
    if identity.games_analyzed >= 10:
        identity.style_profile.confidence = min(0.7, identity.games_analyzed / 30)
    
    # Generate coach notes
    identity.coach_notes = []
    if identity.blunder_taxonomy.most_common_type:
        identity.coach_notes.append(
            f"Most common issue: {identity.blunder_taxonomy.most_common_type.value}"
        )
    if identity.blunder_taxonomy.worst_phase:
        identity.coach_notes.append(
            f"Needs work in: {identity.blunder_taxonomy.worst_phase.value}"
        )
    
    identity.priority_focus = identity.blunder_taxonomy.most_common_type.value \
        if identity.blunder_taxonomy.most_common_type else None
    
    # Save
    await service.save(identity)
    
    logger.info(f"  Migrated: {identity.games_analyzed} games, "
                f"{identity.blunder_taxonomy.total_blunders} blunders, "
                f"{len(identity.pattern_history)} patterns")
    
    return identity


async def run_migration():
    """Run migration for all users"""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Get all users from multiple sources
    user_ids = set()
    
    # From coach_sessions
    session_users = await db.coach_sessions.distinct("user_id")
    user_ids.update(session_users)
    
    # From game_analyses
    analysis_users = await db.game_analyses.distinct("user_id")
    user_ids.update(analysis_users)
    
    # From coach_memory
    memory_users = await db.coach_memory.distinct("user_id")
    user_ids.update(memory_users)
    
    # From users collection
    users_cursor = db.users.find({}, {"user_id": 1})
    async for u in users_cursor:
        if u.get("user_id"):
            user_ids.add(u["user_id"])
    
    logger.info(f"Found {len(user_ids)} users to migrate")
    
    for user_id in user_ids:
        try:
            await migrate_user_data(db, user_id)
        except Exception as e:
            logger.error(f"Error migrating {user_id}: {e}")
    
    logger.info("Migration complete!")
    client.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
