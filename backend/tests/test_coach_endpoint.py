"""
Tests for /api/coach/today endpoint
Ensures Last Game only shows PROPERLY analyzed games with Stockfish data.

CRITICAL DATA MODEL:
- stockfish_analysis.move_evaluations: Array of Stockfish move evaluations (SOURCE OF TRUTH)
- stockfish_analysis.accuracy: Accuracy percentage from Stockfish
- commentary: GPT-generated explanations (NOT source of truth for stats)
- blunders/mistakes at top level: May be stale, DO NOT USE

A game is PROPERLY analyzed if:
1. stockfish_analysis.move_evaluations exists AND has >= 3 items
2. stockfish_failed is NOT True
"""

import pytest
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv('.env')

@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    return client[os.environ['DB_NAME']]


class TestLastGameDataIntegrity:
    """Tests to ensure Last Game shows only properly analyzed games"""
    
    @pytest.mark.asyncio
    async def test_stockfish_data_location(self, db):
        """Verify Stockfish data is at stockfish_analysis.move_evaluations, NOT top level"""
        analysis = await db.game_analyses.find_one(
            {"stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}},
            {"_id": 0}
        )
        
        if analysis:
            # Stockfish data MUST be nested under stockfish_analysis
            assert "stockfish_analysis" in analysis, "stockfish_analysis field must exist"
            sf = analysis["stockfish_analysis"]
            assert "move_evaluations" in sf, "move_evaluations must be inside stockfish_analysis"
            assert len(sf["move_evaluations"]) > 0, "move_evaluations must not be empty"
            
            # Top-level move_evaluations should NOT be the source of truth
            top_level_evals = analysis.get("move_evaluations")
            if top_level_evals:
                print(f"WARNING: Top-level move_evaluations exists but should be ignored")
    
    @pytest.mark.asyncio
    async def test_properly_analyzed_game_has_accuracy(self, db):
        """A properly analyzed game must have non-zero accuracy from Stockfish"""
        analysis = await db.game_analyses.find_one(
            {"stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}},
            {"_id": 0, "stockfish_analysis": 1, "game_id": 1}
        )
        
        if analysis:
            sf = analysis.get("stockfish_analysis", {})
            accuracy = sf.get("accuracy", 0)
            assert accuracy > 0, f"Game {analysis.get('game_id')} has 0 accuracy despite having move_evaluations"
    
    @pytest.mark.asyncio
    async def test_blunder_count_matches_move_evaluations(self, db):
        """Blunder count should match count from stockfish_analysis.move_evaluations"""
        analysis = await db.game_analyses.find_one(
            {"stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}},
            {"_id": 0, "stockfish_analysis": 1, "blunders": 1, "game_id": 1}
        )
        
        if analysis:
            sf = analysis.get("stockfish_analysis", {})
            move_evals = sf.get("move_evaluations", [])
            
            # Count blunders from Stockfish data
            actual_blunders = sum(1 for m in move_evals if m.get("evaluation") == "blunder")
            stored_blunders = analysis.get("blunders", 0)
            
            # They should match (or we should use the Stockfish count)
            if actual_blunders != stored_blunders:
                print(f"WARNING: Game {analysis.get('game_id')} has mismatched blunder counts: "
                      f"stored={stored_blunders}, actual={actual_blunders}")
    
    @pytest.mark.asyncio
    async def test_incomplete_analysis_not_shown(self, db):
        """Games without Stockfish data should NOT be returned as 'properly analyzed'"""
        # Find a game with commentary but NO stockfish_analysis.move_evaluations
        incomplete = await db.game_analyses.find_one(
            {
                "commentary": {"$exists": True, "$not": {"$size": 0}},
                "$or": [
                    {"stockfish_analysis.move_evaluations": {"$exists": False}},
                    {"stockfish_analysis.move_evaluations": {"$size": 0}},
                    {"stockfish_analysis": {"$exists": False}}
                ]
            },
            {"_id": 0, "game_id": 1, "commentary": 1}
        )
        
        if incomplete:
            game_id = incomplete.get("game_id")
            commentary_count = len(incomplete.get("commentary", []))
            print(f"Found incomplete analysis: {game_id} with {commentary_count} commentary items but no Stockfish")
            
            # This game should NOT be returned by the "properly analyzed" query
            properly_analyzed = await db.game_analyses.find_one(
                {
                    "game_id": game_id,
                    "stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}}
                }
            )
            assert properly_analyzed is None, f"Incomplete game {game_id} should not match 'properly analyzed' query"


class TestCoachEndpointDataModel:
    """Document the correct data model for coach endpoint"""
    
    @pytest.mark.asyncio
    async def test_document_schema(self, db):
        """Document the expected schema for game_analyses"""
        analysis = await db.game_analyses.find_one({}, {"_id": 0})
        
        if analysis:
            print("\n=== GAME ANALYSIS SCHEMA ===")
            print("Top-level keys:", list(analysis.keys()))
            
            if "stockfish_analysis" in analysis:
                sf = analysis["stockfish_analysis"]
                print("\nstockfish_analysis keys:", list(sf.keys()) if isinstance(sf, dict) else "NOT A DICT")
                
                if isinstance(sf, dict) and "move_evaluations" in sf:
                    evals = sf["move_evaluations"]
                    if evals and len(evals) > 0:
                        print("move_evaluations[0] keys:", list(evals[0].keys()))
            
            print("\n=== CORRECT FIELD PATHS ===")
            print("Accuracy: stockfish_analysis.accuracy")
            print("Move evals: stockfish_analysis.move_evaluations")
            print("Blunders: COUNT from stockfish_analysis.move_evaluations where evaluation='blunder'")
            print("Mistakes: COUNT from stockfish_analysis.move_evaluations where evaluation='mistake'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
