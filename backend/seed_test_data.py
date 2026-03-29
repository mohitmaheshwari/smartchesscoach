"""
Data Seeding Script - Create Test Users with Different Behavioral Archetypes

Creates 3 test users representing different behavioral profiles:
1. NOVICE_NINA: Struggles with basics, high repetition rate, low improvement
2. STEADY_SAM: Making progress, applying some corrections, moderate velocity
3. DISCIPLINED_DANA: High improvement velocity, stable CPR, applies coaching

This enables end-to-end testing of the coaching architecture.

Usage:
    python seed_test_data.py
    
    # Or with specific archetype:
    python seed_test_data.py --archetype novice
"""

import os
import sys
import uuid
import argparse
import random
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add parent directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_database():
    """Connect to MongoDB"""
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'chess_coach')
    
    if not mongo_url:
        raise ValueError("MONGO_URL environment variable not set")
    
    client = MongoClient(mongo_url)
    return client[db_name]


# ============================================================================
# ARCHETYPE DEFINITIONS
# ============================================================================

ARCHETYPES = {
    "novice": {
        "user_id": "test_novice_nina",
        "email": "novice.nina@test.chess",
        "name": "Novice Nina",
        "description": "Struggles with basics, high repetition rate, needs hand-holding",
        "maturity_level": "Novice",
        "coach_tone": "ExplainMore",
        "theme_confidence": 0.3,
        "improvement_velocity": -0.1,
        "theme_resistance": 0.7,
        "games_config": {
            "count": 15,
            "theme_issues_rate": 0.8,  # 80% of games have theme issues
            "same_issue_streak": True,  # Same issue repeats
            "accuracy_range": (40, 60),
            "blunder_rate": 0.4
        }
    },
    "steady": {
        "user_id": "test_steady_sam",
        "email": "steady.sam@test.chess",
        "name": "Steady Sam",
        "description": "Making progress, applying some corrections, moderate learner",
        "maturity_level": "Developing",
        "coach_tone": "Balanced",
        "theme_confidence": 0.5,
        "improvement_velocity": 0.3,
        "theme_resistance": 0.3,
        "games_config": {
            "count": 20,
            "theme_issues_rate": 0.4,  # 40% of games have theme issues
            "same_issue_streak": False,  # Varies
            "accuracy_range": (55, 75),
            "blunder_rate": 0.2
        }
    },
    "disciplined": {
        "user_id": "test_disciplined_dana",
        "email": "disciplined.dana@test.chess",
        "name": "Disciplined Dana",
        "description": "High improvement, applies coaching, approaching mastery",
        "maturity_level": "Disciplined",
        "coach_tone": "ChallengeMore",
        "theme_confidence": 0.8,
        "improvement_velocity": 0.7,
        "theme_resistance": 0.1,
        "games_config": {
            "count": 25,
            "theme_issues_rate": 0.2,  # 20% of games have theme issues
            "same_issue_streak": False,
            "accuracy_range": (70, 90),
            "blunder_rate": 0.05
        }
    }
}


# Sample PGNs for different game results
SAMPLE_PGNS = {
    "win": """[Event "Rated Blitz game"]
[Site "Chess.com"]
[Date "2026.03.01"]
[White "TestUser"]
[Black "Opponent"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 
8. c3 O-O 9. h3 Na5 10. Bc2 c5 11. d4 Qc7 12. Nbd2 Nc6 13. dxe5 dxe5 
14. Nf1 Be6 15. Ne3 Rad8 16. Qe2 Nd4 17. Nxd4 cxd4 18. Nd5 Bxd5 
19. exd5 Qd6 20. Bd3 Qxd5 21. Bf5 g6 22. Bh6 Rfe8 23. Bc4 Qd6 
24. Re4 dxc3 25. bxc3 Qc7 26. Rae1 Nd5 27. Rxe5 Bd6 28. Bxd5 Bxe5 
29. Rxe5 Rxe5 30. Qxe5 Qxe5 31. Bxe5 Rd1+ 32. Kh2 1-0""",
    
    "loss": """[Event "Rated Blitz game"]
[Site "Chess.com"]
[Date "2026.03.01"]
[White "Opponent"]
[Black "TestUser"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 O-O 
8. c3 d6 9. h3 Na5 10. Bc2 c5 11. d4 Qc7 12. Nbd2 cxd4 13. cxd4 Nc6 
14. Nb3 exd4 15. Nfxd4 Nxd4 16. Nxd4 Bd7 17. Bg5 Bc6 18. Nxc6 Qxc6 
19. Bxf6 Bxf6 20. Qg4 Be5 21. f4 Bd4+ 22. Kh1 Rae8 23. Rad1 Qxe4 
24. Bxe4 Rxe4 25. Qxd4 Rxf4 26. Qd3 Rf2 27. Re7 Rc8 28. Rf1 Rxf1+ 
29. Qxf1 Rc1 30. Qxc1 d5 31. Qc8# 1-0""",
    
    "draw": """[Event "Rated Rapid game"]
[Site "Chess.com"]
[Date "2026.03.01"]
[White "TestUser"]
[Black "Opponent"]
[Result "1/2-1/2"]

1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Bg5 Be7 5. e3 O-O 6. Nf3 h6 7. Bh4 b6 
8. cxd5 Nxd5 9. Bxe7 Qxe7 10. Nxd5 exd5 11. Rc1 Be6 12. Qa4 c5 13. Qa3 Rc8 
14. Bb5 a6 15. dxc5 bxc5 16. O-O Ra7 17. Be2 Nd7 18. Nd4 Rac7 19. Qa4 Qb4 
20. Qxb4 cxb4 21. f4 Nc5 22. Bf3 Rc7 23. Rc2 Rfc8 24. Rfc1 a5 25. b3 Na6 
26. Rxc7 Rxc7 27. Rxc7 Nxc7 1/2-1/2"""
}


# Primary issues for game coach summaries
PRIMARY_ISSUES = [
    "ThreatScanFailure",
    "RushedWhenAhead",
    "StoppedCalculationEarly",
    "PieceLeftUndefended",
    "MissedTactic",
    "DefensiveLapse"
]

THEMES = [
    "ThreatVerification",
    "CalculationDepth",
    "ConversionDiscipline",
    "PieceSafety"
]


def create_user(db, archetype_key: str) -> dict:
    """Create a test user"""
    config = ARCHETYPES[archetype_key]
    
    user = {
        "user_id": config["user_id"],
        "email": config["email"],
        "name": config["name"],
        "is_dev_account": True,
        "created_at": datetime.now(timezone.utc),
        "password_hash": "test_hash_not_real",
        "preferences": {}
    }
    
    # Upsert user
    db.users.update_one(
        {"user_id": config["user_id"]},
        {"$set": user},
        upsert=True
    )
    
    print(f"  Created user: {config['name']} ({config['user_id']})")
    return user


def create_coach_state(db, archetype_key: str):
    """Create coach state for user"""
    config = ARCHETYPES[archetype_key]
    
    active_theme = random.choice(THEMES)
    
    coach_state = {
        "user_id": config["user_id"],
        "active_theme": active_theme,
        "theme_started_at": (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),
        "theme_confidence": config["theme_confidence"],
        "theme_reason": f"Focus determined by behavioral analysis",
        "micro_rules": [
            "Before YOUR move, check what THEY are threatening",
            "Ask: Is anything of mine undefended right now?"
        ],
        "games_on_theme": config["games_config"]["count"],
        "behavioral_maturity_level": config["maturity_level"],
        "coach_tone_mode": config["coach_tone"],
        "theme_resistance_score": config["theme_resistance"],
        "improvement_velocity": config["improvement_velocity"],
        "last_deep_session_at": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "next_deep_session_due_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "recent_coach_sentences": []
    }
    
    db.coach_states.update_one(
        {"user_id": config["user_id"]},
        {"$set": coach_state},
        upsert=True
    )
    
    print(f"  Created coach state: {config['maturity_level']} ({active_theme})")
    return coach_state


def create_games_and_analyses(db, archetype_key: str):
    """Create games and game analyses"""
    config = ARCHETYPES[archetype_key]
    user_id = config["user_id"]
    games_config = config["games_config"]
    
    games_created = 0
    analyses_created = 0
    summaries_created = 0
    
    for i in range(games_config["count"]):
        game_id = f"{user_id}_game_{i+1:03d}"
        
        # Determine game outcome
        outcome = random.choices(
            ["win", "loss", "draw"],
            weights=[0.4, 0.4, 0.2]
        )[0]
        
        result = "1-0" if outcome == "win" else ("0-1" if outcome == "loss" else "1/2-1/2")
        played_date = datetime.now(timezone.utc) - timedelta(days=games_config["count"] - i)
        
        # Determine user color
        user_color = random.choice(["white", "black"])
        white_player = config["name"] if user_color == "white" else "Opponent"
        black_player = "Opponent" if user_color == "white" else config["name"]
        
        # Create game
        game = {
            "game_id": game_id,
            "user_id": user_id,
            "platform": "chess.com",
            "pgn": SAMPLE_PGNS.get(outcome, SAMPLE_PGNS["draw"]),
            "white_player": white_player,
            "black_player": black_player,
            "user_color": user_color,
            "result": result,
            "time_control": "300+5",
            "played_at": played_date,
            "imported_at": played_date,
            "is_analyzed": True,
            "analysis_status": "completed"
        }
        
        db.games.update_one(
            {"game_id": game_id},
            {"$set": game},
            upsert=True
        )
        games_created += 1
        
        # Create analysis
        accuracy = random.randint(*games_config["accuracy_range"])
        blunders = int(random.random() < games_config["blunder_rate"]) + int(random.random() < games_config["blunder_rate"])
        mistakes = random.randint(0, 3)
        
        # Generate move evaluations
        move_evaluations = []
        for move_num in range(1, 25):
            move_eval = {
                "move_number": move_num,
                "move": f"move{move_num}",
                "evaluation": random.choices(
                    ["good", "mistake", "blunder", "inaccuracy"],
                    weights=[0.7, 0.15, 0.05, 0.1]
                )[0],
                "cp_loss": random.randint(0, 50) if random.random() > 0.2 else random.randint(100, 400),
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            }
            move_evaluations.append(move_eval)
        
        analysis = {
            "game_id": game_id,
            "user_id": user_id,
            "stockfish_analysis": {
                "accuracy": accuracy,
                "blunders": blunders,
                "mistakes": mistakes,
                "inaccuracies": random.randint(0, 4),
                "best_moves": random.randint(5, 15),
                "excellent_moves": random.randint(2, 8),
                "avg_cp_loss": random.randint(20, 80),
                "move_evaluations": move_evaluations
            },
            "analysis_depth": 18,
            "analyzed_at": played_date,
            "created_at": played_date
        }
        
        db.game_analyses.update_one(
            {"game_id": game_id},
            {"$set": analysis},
            upsert=True
        )
        analyses_created += 1
        
        # Create game coach summary (for some games)
        if random.random() < 0.7:  # 70% of games have summaries
            ties_to_theme = random.random() < games_config["theme_issues_rate"]
            
            primary_issue = PRIMARY_ISSUES[i % len(PRIMARY_ISSUES)] if games_config.get("same_issue_streak") else random.choice(PRIMARY_ISSUES)
            
            summary = {
                "game_id": game_id,
                "user_id": user_id,
                "confidence": random.choice(["Low", "Medium", "High"]),
                "primary_moment": {
                    "move_number": random.randint(10, 30),
                    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    "label": f"Move {random.randint(10, 30)} - Mistake"
                },
                "primary_issue": primary_issue,
                "emotion_mirror_line": "You missed their threat here.",
                "coach_explain_line": "Before committing, checking their forcing moves would have saved the position.",
                "ties_to_active_theme": ties_to_theme,
                "theme_reinforcement_line": "This connects to your current focus." if ties_to_theme else None,
                "cta_type": "review_moment",
                "cta_text": "Review Critical Moment",
                "cta_target": f"/game/{game_id}?move=15",
                "generated_at": played_date.isoformat()
            }
            
            db.game_coach_summaries.update_one(
                {"game_id": game_id},
                {"$set": summary},
                upsert=True
            )
            summaries_created += 1
    
    print(f"  Created {games_created} games, {analyses_created} analyses, {summaries_created} summaries")


def create_deep_sessions(db, archetype_key: str):
    """Create deep session history"""
    config = ARCHETYPES[archetype_key]
    user_id = config["user_id"]
    
    # Create 2-3 completed deep sessions
    sessions_count = 2 if archetype_key == "novice" else 3
    
    for i in range(sessions_count):
        session_date = datetime.now(timezone.utc) - timedelta(days=(i + 1) * 7)
        
        session = {
            "session_id": f"{user_id}_session_{i+1}",
            "user_id": user_id,
            "theme": random.choice(THEMES),
            "triggered_by": random.choice(["scheduled", "game_threshold"]),
            "games_considered": random.randint(5, 10),
            "reflection_answer": "I think I rush when attacking",
            "summary_snapshot": {
                "games_analyzed": random.randint(5, 10),
                "theme_failures": random.randint(2, 5),
                "observations": ["Pattern detected in recent games"],
                "trend": "stable"
            },
            "assignment_type": "threat_scan_drill",
            "micro_rule_assigned": "Before committing, scan their forcing moves",
            "completed": True,
            "current_step": 6,
            "created_at": session_date.isoformat(),
            "completed_at": (session_date + timedelta(minutes=5)).isoformat()
        }
        
        db.deep_sessions.update_one(
            {"session_id": session["session_id"]},
            {"$set": session},
            upsert=True
        )
    
    print(f"  Created {sessions_count} deep sessions")


def create_player_profile(db, archetype_key: str):
    """Create player profile"""
    config = ARCHETYPES[archetype_key]
    
    profile = {
        "user_id": config["user_id"],
        "estimated_elo": 1200 if archetype_key == "novice" else (1500 if archetype_key == "steady" else 1800),
        "games_analyzed_count": config["games_config"]["count"],
        "total_blunders": int(config["games_config"]["count"] * config["games_config"]["blunder_rate"] * 2),
        "total_mistakes": config["games_config"]["count"],
        "total_best_moves": config["games_config"]["count"] * 8,
        "top_weaknesses": [
            {
                "category": "tactical",
                "subcategory": "one_move_blunder",
                "occurrence_count": 5,
                "decayed_score": 5.0
            }
        ],
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    
    db.player_profiles.update_one(
        {"user_id": config["user_id"]},
        {"$set": profile},
        upsert=True
    )
    
    print(f"  Created player profile (ELO: {profile['estimated_elo']})")


def seed_archetype(db, archetype_key: str):
    """Seed all data for a single archetype"""
    config = ARCHETYPES[archetype_key]
    
    print(f"\n{'='*60}")
    print(f"Seeding: {config['name']}")
    print(f"Description: {config['description']}")
    print(f"{'='*60}")
    
    create_user(db, archetype_key)
    create_coach_state(db, archetype_key)
    create_games_and_analyses(db, archetype_key)
    create_deep_sessions(db, archetype_key)
    create_player_profile(db, archetype_key)
    
    print(f"\nCompleted seeding for {config['name']}")


def seed_all(db):
    """Seed all archetypes"""
    print("\n" + "="*60)
    print("CHESS COACH DATA SEEDING - 3 BEHAVIORAL ARCHETYPES")
    print("="*60)
    
    for archetype_key in ARCHETYPES:
        seed_archetype(db, archetype_key)
    
    print("\n" + "="*60)
    print("DATA SEEDING COMPLETE")
    print("="*60)
    print("\nTest accounts created:")
    for key, config in ARCHETYPES.items():
        print(f"  - {config['name']}: {config['email']} ({config['maturity_level']})")
    
    print("\nYou can now test the coaching architecture with these users.")


def cleanup(db):
    """Remove all test data"""
    print("\nCleaning up test data...")
    
    for config in ARCHETYPES.values():
        user_id = config["user_id"]
        
        db.users.delete_many({"user_id": user_id})
        db.coach_states.delete_many({"user_id": user_id})
        db.games.delete_many({"user_id": user_id})
        db.game_analyses.delete_many({"user_id": user_id})
        db.game_coach_summaries.delete_many({"user_id": user_id})
        db.deep_sessions.delete_many({"user_id": user_id})
        db.player_profiles.delete_many({"user_id": user_id})
        
        print(f"  Cleaned up: {config['name']}")
    
    print("\nCleanup complete.")


def main():
    parser = argparse.ArgumentParser(description="Seed test data for Chess Coach")
    parser.add_argument(
        "--archetype",
        choices=["novice", "steady", "disciplined", "all"],
        default="all",
        help="Which archetype to seed (default: all)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove all test data instead of seeding"
    )
    
    args = parser.parse_args()
    
    db = get_database()
    print(f"Connected to database: {db.name}")
    
    if args.cleanup:
        cleanup(db)
    elif args.archetype == "all":
        seed_all(db)
    else:
        seed_archetype(db, args.archetype)


if __name__ == "__main__":
    main()
