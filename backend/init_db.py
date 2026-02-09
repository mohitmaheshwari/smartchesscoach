"""
Database Initialization Script for Chess Coach AI
Run this script to set up the MongoDB schema and indexes on a fresh database.

Usage:
    python init_db.py

Environment Variables Required:
    MONGO_URL - MongoDB connection string (e.g., mongodb+srv://user:pass@cluster.mongodb.net/)
    DB_NAME - Database name (e.g., chess_coach)
"""

import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

# Configuration
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


async def init_database():
    """Initialize the database with collections and indexes."""
    
    print(f"Connecting to MongoDB: {MONGO_URL}")
    print(f"Database: {DB_NAME}")
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # ==================== COLLECTIONS ====================
    
    collections_to_create = [
        "users",
        "user_sessions", 
        "games",
        "game_analyses",
        "mistake_patterns",
        "player_profiles",
        "puzzles",
        "puzzle_attempts",
        "game_embeddings",
        "analysis_embeddings",
        "pattern_embeddings",
        "analysis_queue",
        "notifications",
        "reflection_results"
    ]
    
    existing = await db.list_collection_names()
    
    for coll in collections_to_create:
        if coll not in existing:
            await db.create_collection(coll)
            print(f"  ✓ Created collection: {coll}")
        else:
            print(f"  - Collection exists: {coll}")
    
    # ==================== INDEXES ====================
    
    print("\nCreating indexes...")
    
    # Users indexes
    await db.users.create_index("user_id", unique=True)
    await db.users.create_index("email", unique=True)
    print("  ✓ users indexes")
    
    # User sessions indexes
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("user_id")
    await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)  # TTL index
    print("  ✓ user_sessions indexes")
    
    # Games indexes
    await db.games.create_index("game_id", unique=True)
    await db.games.create_index("user_id")
    await db.games.create_index([("user_id", 1), ("platform", 1)])
    await db.games.create_index([("user_id", 1), ("is_analyzed", 1)])
    print("  ✓ games indexes")
    
    # Game analyses indexes
    await db.game_analyses.create_index("analysis_id", unique=True)
    await db.game_analyses.create_index("game_id", unique=True)
    await db.game_analyses.create_index("user_id")
    print("  ✓ game_analyses indexes")
    
    # Mistake patterns indexes
    await db.mistake_patterns.create_index("pattern_id", unique=True)
    await db.mistake_patterns.create_index("user_id")
    await db.mistake_patterns.create_index([("user_id", 1), ("category", 1), ("subcategory", 1)])
    print("  ✓ mistake_patterns indexes")
    
    # Player profiles indexes
    await db.player_profiles.create_index("profile_id", unique=True)
    await db.player_profiles.create_index("user_id", unique=True)
    print("  ✓ player_profiles indexes")
    
    # Puzzles indexes
    await db.puzzles.create_index("puzzle_id", unique=True)
    await db.puzzles.create_index("user_id")
    await db.puzzles.create_index([("user_id", 1), ("pattern_id", 1)])
    print("  ✓ puzzles indexes")
    
    # Puzzle attempts indexes
    await db.puzzle_attempts.create_index("attempt_id", unique=True)
    await db.puzzle_attempts.create_index("user_id")
    await db.puzzle_attempts.create_index("puzzle_id")
    await db.puzzle_attempts.create_index([("user_id", 1), ("puzzle_id", 1)])
    print("  ✓ puzzle_attempts indexes")
    
    # Analysis queue indexes
    await db.analysis_queue.create_index("queue_id", unique=True)
    await db.analysis_queue.create_index("user_id")
    await db.analysis_queue.create_index("status")
    await db.analysis_queue.create_index([("user_id", 1), ("status", 1)])
    print("  ✓ analysis_queue indexes")
    
    # Notifications indexes
    await db.notifications.create_index("notification_id", unique=True)
    await db.notifications.create_index("user_id")
    await db.notifications.create_index([("user_id", 1), ("read", 1)])
    await db.notifications.create_index("created_at")
    print("  ✓ notifications indexes")
    
    # Reflection results indexes
    await db.reflection_results.create_index("reflection_id", unique=True)
    await db.reflection_results.create_index("user_id")
    await db.reflection_results.create_index("game_id")
    print("  ✓ reflection_results indexes")
    
    # Embedding collections indexes (for RAG)
    await db.game_embeddings.create_index("embedding_id", unique=True)
    await db.game_embeddings.create_index("user_id")
    await db.game_embeddings.create_index("game_id")
    print("  ✓ game_embeddings indexes")
    
    await db.analysis_embeddings.create_index("embedding_id", unique=True)
    await db.analysis_embeddings.create_index("user_id")
    await db.analysis_embeddings.create_index("analysis_id")
    print("  ✓ analysis_embeddings indexes")
    
    await db.pattern_embeddings.create_index("embedding_id", unique=True)
    await db.pattern_embeddings.create_index("user_id")
    await db.pattern_embeddings.create_index("pattern_id")
    print("  ✓ pattern_embeddings indexes")
    
    # ==================== SCHEMA DOCUMENTATION ====================
    
    print("\n" + "=" * 60)
    print("DATABASE SCHEMA REFERENCE")
    print("=" * 60)
    
    schemas = {
        "users": {
            "user_id": "str (unique) - UUID",
            "email": "str (unique) - User email from OAuth",
            "name": "str - Display name",
            "picture": "str - Profile picture URL",
            "created_at": "datetime",
            "chess_com_username": "str | null - Linked Chess.com username",
            "lichess_username": "str | null - Linked Lichess username",
            "last_game_sync": "str | null - ISO timestamp of last sync",
            "email_notifications": "dict - {game_analyzed: bool, weekly_summary: bool, weakness_alert: bool}"
        },
        "user_sessions": {
            "user_id": "str - Reference to users.user_id",
            "session_token": "str (unique) - Session cookie value",
            "expires_at": "datetime - TTL indexed",
            "created_at": "datetime"
        },
        "games": {
            "game_id": "str (unique) - UUID",
            "user_id": "str - Reference to users.user_id",
            "platform": "str - 'chess.com' or 'lichess'",
            "pgn": "str - Full PGN of the game",
            "white_player": "str",
            "black_player": "str",
            "result": "str - e.g., '1-0', '0-1', '1/2-1/2'",
            "time_control": "str - e.g., 'rapid', 'blitz'",
            "date_played": "str - ISO date",
            "opening": "str - Opening name",
            "user_color": "str - 'white' or 'black'",
            "imported_at": "str - ISO timestamp",
            "is_analyzed": "bool - Whether AI analysis exists",
            "auto_synced": "bool - Whether auto-imported"
        },
        "game_analyses": {
            "analysis_id": "str (unique)",
            "game_id": "str (unique) - Reference to games.game_id",
            "user_id": "str",
            "commentary": "list[dict] - Legacy field",
            "move_by_move": "list[dict] - [{move_number, move, evaluation, thinking_pattern, lesson, consider}]",
            "blunders": "int",
            "mistakes": "int", 
            "inaccuracies": "int",
            "best_moves": "int",
            "game_summary": "str",
            "overall_summary": "str - Legacy field",
            "identified_patterns": "list[str] - Pattern IDs",
            "weaknesses": "list[dict] - [{category, subcategory, habit_description, practice_tip}]",
            "identified_weaknesses": "list[dict] - Same as weaknesses",
            "strengths": "list[dict] - [{category, subcategory, description}]",
            "best_move_suggestions": "list[dict] - [{move_number, best_move, reason}]",
            "focus_this_week": "str",
            "key_lesson": "str - Legacy field",
            "voice_script_summary": "str - Text for TTS",
            "summary_p1": "str",
            "summary_p2": "str",
            "improvement_note": "str",
            "created_at": "str - ISO timestamp",
            "auto_analyzed": "bool - Whether auto-analyzed",
            "_cqs_internal": "dict - Internal quality score (excluded from API)"
        },
        "mistake_patterns": {
            "pattern_id": "str (unique) - UUID",
            "user_id": "str",
            "category": "str - e.g., 'tactical', 'strategic', 'opening_principles'",
            "subcategory": "str - e.g., 'fork_blindness', 'poor_piece_activity'",
            "description": "str",
            "occurrences": "int - Times this pattern appeared",
            "game_ids": "list[str] - Games where this occurred",
            "first_seen": "str - ISO timestamp",
            "last_seen": "str - ISO timestamp"
        },
        "player_profiles": {
            "profile_id": "str (unique)",
            "user_id": "str (unique)",
            "user_name": "str",
            "estimated_level": "str - 'beginner', 'intermediate', 'advanced'",
            "estimated_elo": "int",
            "top_weaknesses": "list[dict] - [{category, subcategory, occurrence_count, last_seen, decayed_score}]",
            "strengths": "list[dict] - [{category, subcategory, evidence_count}]",
            "learning_style": "str - 'concise' or 'detailed'",
            "coaching_tone": "str - 'encouraging', 'strict', 'balanced'",
            "improvement_trend": "str - 'improving', 'regressing', 'stuck'",
            "games_analyzed_count": "int",
            "total_blunders": "int",
            "total_mistakes": "int",
            "total_best_moves": "int",
            "recent_performance": "list[dict] - Last 10 games performance",
            "historical_performance": "list[dict]",
            "challenges_attempted": "int",
            "challenges_solved": "int",
            "weakness_challenge_success": "dict",
            "created_at": "str - ISO timestamp",
            "last_updated": "str - ISO timestamp"
        },
        "puzzles": {
            "puzzle_id": "str (unique)",
            "user_id": "str",
            "pattern_id": "str - Reference to mistake_patterns",
            "title": "str",
            "description": "str",
            "fen": "str - Chess position in FEN notation",
            "player_color": "str - 'white' or 'black'",
            "solution_san": "str - Solution in SAN notation",
            "solution": "list[dict] - [{move, explanation}]",
            "hint": "str",
            "theme": "str",
            "created_at": "str - ISO timestamp"
        },
        "game_embeddings": {
            "embedding_id": "str (unique)",
            "user_id": "str",
            "game_id": "str",
            "chunk_id": "str",
            "chunk_type": "str",
            "content": "str - Text content",
            "move_range": "str",
            "metadata": "dict",
            "embedding": "list[float] - 1536-dim vector",
            "created_at": "str"
        },
        "analysis_embeddings": {
            "embedding_id": "str (unique)",
            "user_id": "str",
            "analysis_id": "str",
            "game_id": "str",
            "content": "str",
            "embedding": "list[float] - 1536-dim vector",
            "created_at": "str"
        },
        "pattern_embeddings": {
            "embedding_id": "str (unique)",
            "user_id": "str",
            "pattern_id": "str",
            "content": "str",
            "embedding": "list[float] - 1536-dim vector",
            "created_at": "str"
        }
    }
    
    for coll_name, schema in schemas.items():
        print(f"\n{coll_name}:")
        for field, desc in schema.items():
            print(f"  {field}: {desc}")
    
    print("\n" + "=" * 60)
    print("✅ Database initialization complete!")
    print("=" * 60)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(init_database())
