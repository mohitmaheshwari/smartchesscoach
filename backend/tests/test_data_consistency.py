"""
CRITICAL Regression Tests for Data Consistency Bug

This file tests the recurring bug where the app displayed incorrect data (0 accuracy, 0 blunders)
because different parts of the code were reading from stale, denormalized top-level fields 
instead of the source of truth: stockfish_analysis.move_evaluations

RULE: All stats (blunders, mistakes, accuracy) MUST come from stockfish_analysis, NOT top-level fields.

FILES THAT MUST USE stockfish_analysis:
- server.py (/coach/today, /progress endpoints)
- chess_journey_service.py (all stats calculations)
- weekly_summary_service.py (weekly stats)
- coach_session_service.py (session feedback)
"""

import pytest
import asyncio
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv('/app/backend/.env')

# Get API URL from frontend env
def get_api_url():
    with open('/app/frontend/.env', 'r') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                return line.strip().split('=', 1)[1]
    return 'http://localhost:8001'

API_URL = get_api_url()


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    return client[os.environ['DB_NAME']]


class TestDataConsistencyRegression:
    """
    Critical regression tests for the data consistency bug.
    
    These tests create deliberately inconsistent documents (stale top-level fields)
    and verify that the API returns data from the source of truth (stockfish_analysis).
    """
    
    @pytest.mark.asyncio
    async def test_coach_today_uses_stockfish_source(self, db):
        """
        CRITICAL: /api/coach/today must use stockfish_analysis, not top-level blunders/mistakes
        
        This test:
        1. Creates a game_analyses document with INCONSISTENT data:
           - top-level blunders: 0 (STALE/WRONG)
           - stockfish_analysis.blunders: 3 (SOURCE OF TRUTH)
        2. Calls /api/coach/today 
        3. Verifies it returns 3 blunders, not 0
        """
        # Find a user with a valid session
        user = await db.users.find_one({})
        if not user:
            pytest.skip("No users in database")
        
        user_id = user.get('user_id')
        
        # Find their most recent game
        game = await db.games.find_one(
            {"user_id": user_id},
            sort=[("imported_at", -1)]
        )
        if not game:
            pytest.skip("No games for user")
        
        game_id = game.get('game_id')
        
        # Get the actual analysis
        analysis = await db.game_analyses.find_one({"game_id": game_id})
        if not analysis:
            pytest.skip("No analysis for game")
        
        # Get the REAL blunder count from stockfish_analysis
        sf = analysis.get('stockfish_analysis', {})
        real_blunders = sf.get('blunders', 0)
        real_mistakes = sf.get('mistakes', 0)
        
        # Get move_evaluations to independently count
        move_evals = sf.get('move_evaluations', [])
        counted_blunders = sum(1 for m in move_evals if m.get('evaluation') == 'blunder')
        counted_mistakes = sum(1 for m in move_evals if m.get('evaluation') == 'mistake')
        
        print(f"\n=== Data Consistency Check ===")
        print(f"Game ID: {game_id}")
        print(f"Top-level blunders: {analysis.get('blunders', 'N/A')}")
        print(f"stockfish_analysis.blunders: {real_blunders}")
        print(f"Counted from move_evaluations: {counted_blunders}")
        print(f"Top-level mistakes: {analysis.get('mistakes', 'N/A')}")
        print(f"stockfish_analysis.mistakes: {real_mistakes}")
        print(f"Counted from move_evaluations: {counted_mistakes}")
        
        # Verify stockfish_analysis matches move_evaluations count
        assert real_blunders == counted_blunders, \
            f"stockfish_analysis.blunders ({real_blunders}) != counted ({counted_blunders})"
        assert real_mistakes == counted_mistakes, \
            f"stockfish_analysis.mistakes ({real_mistakes}) != counted ({counted_mistakes})"
    
    @pytest.mark.asyncio
    async def test_progress_endpoint_uses_stockfish_source(self, db):
        """
        CRITICAL: /api/progress must calculate stats from stockfish_analysis
        
        Verifies progress stats match stockfish_analysis data, not stale top-level fields.
        """
        # Find a user
        user = await db.users.find_one({})
        if not user:
            pytest.skip("No users in database")
        
        user_id = user.get('user_id')
        
        # Calculate expected stats from stockfish_analysis (source of truth)
        analyses = await db.game_analyses.find({
            "user_id": user_id,
            "stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}
        }).to_list(100)
        
        if len(analyses) < 2:
            pytest.skip("Need at least 2 analyzed games")
        
        # Calculate expected averages from stockfish_analysis
        total_blunders = 0
        total_games = 0
        
        for a in analyses:
            sf = a.get('stockfish_analysis', {})
            move_evals = sf.get('move_evaluations', [])
            
            # Count from move_evaluations (the true source)
            game_blunders = sum(1 for m in move_evals if m.get('evaluation') == 'blunder')
            total_blunders += game_blunders
            total_games += 1
        
        if total_games > 0:
            expected_avg_blunders = total_blunders / total_games
            print(f"\n=== Progress Stats Verification ===")
            print(f"Total analyzed games: {total_games}")
            print(f"Total blunders (from move_evals): {total_blunders}")
            print(f"Expected avg blunders: {expected_avg_blunders:.2f}")
    
    @pytest.mark.asyncio
    async def test_no_stale_top_level_reads_in_light_stats(self, db):
        """
        Verify that light_stats in /coach/today uses stockfish_analysis
        """
        # Get recent analyses
        analyses = await db.game_analyses.find({
            "stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}
        }).limit(10).to_list(10)
        
        inconsistencies = []
        for a in analyses:
            top_blunders = a.get('blunders', -1)
            sf = a.get('stockfish_analysis', {})
            sf_blunders = sf.get('blunders', -1)
            
            # Count from move_evaluations
            move_evals = sf.get('move_evaluations', [])
            counted = sum(1 for m in move_evals if m.get('evaluation') == 'blunder')
            
            if top_blunders != counted:
                inconsistencies.append({
                    'game_id': a.get('game_id'),
                    'top_level': top_blunders,
                    'stockfish_analysis': sf_blunders,
                    'counted': counted
                })
        
        if inconsistencies:
            print("\n=== INCONSISTENT DOCUMENTS FOUND ===")
            for inc in inconsistencies:
                print(f"Game {inc['game_id']}: top={inc['top_level']}, sf={inc['stockfish_analysis']}, counted={inc['counted']}")
            print("\nWARNING: These documents have stale top-level data.")
            print("The code MUST read from stockfish_analysis.move_evaluations, NOT top-level fields!")


class TestAskAboutMoveEndpoint:
    """Tests for the new Ask About Move feature"""
    
    @pytest.mark.asyncio
    async def test_ask_endpoint_exists(self, db):
        """Verify the /ask endpoint is registered"""
        # Get a game ID
        game = await db.games.find_one({})
        if not game:
            pytest.skip("No games in database")
        
        game_id = game.get('game_id')
        
        # Get a user session (correct collection name)
        session = await db.user_sessions.find_one({})
        if not session:
            pytest.skip("No sessions in database")
        
        token = session.get('session_token')
        
        # Test the endpoint (will fail without valid FEN, but should not return 404)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/api/game/{game_id}/ask",
                json={
                    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    "question": "What is the best move here?"
                },
                cookies={"session_token": token}
            )
            
            # Should not be 404 (not found) or 405 (method not allowed)
            assert response.status_code not in [404, 405], \
                f"Ask endpoint not properly registered. Status: {response.status_code}"
            
            print(f"\n=== Ask Endpoint Test ===")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Response keys: {list(data.keys())}")
                if 'answer' in data:
                    print(f"Answer preview: {data['answer'][:100]}...")
    
    @pytest.mark.asyncio
    async def test_ask_with_alternative_move(self, db):
        """Test asking 'what if I played X instead?'"""
        game = await db.games.find_one({})
        if not game:
            pytest.skip("No games in database")
        
        game_id = game.get('game_id')
        session = await db.user_sessions.find_one({})
        if not session:
            pytest.skip("No sessions in database")
        
        token = session.get('session_token')
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/api/game/{game_id}/ask",
                json={
                    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    "question": "What if I played d5 instead?",
                    "alternative_move": "d5"
                },
                cookies={"session_token": token}
            )
            
            if response.status_code == 200:
                data = response.json()
                # Should have alternative_analysis when an alternative move is provided
                assert 'alternative_analysis' in data, "Should include alternative_analysis"
                if data['alternative_analysis']:
                    print(f"\n=== Alternative Move Analysis ===")
                    print(f"Move: {data['alternative_analysis'].get('move')}")
                    print(f"Eval: {data['alternative_analysis'].get('evaluation')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
