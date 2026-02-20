"""
Position Analysis Service (Stockfish + Cache)

Simple, fast, reliable position analysis:
1. Check cache first (instant)
2. Run local Stockfish if not cached
3. Cache result for future use

No external API dependencies. No rate limits.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import chess

logger = logging.getLogger(__name__)

# In-memory cache for current session
_memory_cache = {}
MAX_MEMORY_CACHE = 2000


class PositionAnalysisService:
    """
    Fast position analysis using Stockfish with intelligent caching.
    """
    
    def __init__(self, db):
        """
        Initialize with database for persistent cache.
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
    
    async def get_position_eval(
        self,
        fen: str,
        depth: int = 18,
        use_cache: bool = True
    ) -> Dict:
        """
        Get evaluation for a position.
        
        Args:
            fen: FEN string of position
            depth: Stockfish analysis depth (18 is good for teaching)
            use_cache: Whether to use/update cache
        
        Returns:
            {
                "fen": str,
                "source": "memory_cache" | "db_cache" | "stockfish",
                "depth": int,
                "eval_cp": int,  # centipawns (positive = white better)
                "eval_mate": int | None,  # moves to mate if applicable
                "best_move": str,  # UCI format
                "best_move_san": str,  # SAN format
                "pv": [str],  # principal variation in UCI
                "pv_san": [str],  # principal variation in SAN
            }
        """
        # Normalize FEN for cache key
        cache_key = self._normalize_fen(fen)
        
        # 1. Check memory cache (fastest)
        if use_cache and cache_key in _memory_cache:
            cached = _memory_cache[cache_key]
            if cached.get("depth", 0) >= depth:
                logger.debug(f"Memory cache hit")
                return {**cached, "source": "memory_cache"}
        
        # 2. Check MongoDB cache
        if use_cache:
            cached = await self._get_from_db_cache(cache_key, depth)
            if cached:
                logger.debug(f"DB cache hit (depth {cached.get('depth')})")
                self._add_to_memory_cache(cache_key, cached)
                return {**cached, "source": "db_cache"}
        
        # 3. Run Stockfish
        logger.info(f"Running Stockfish analysis (depth {depth})")
        result = await self._run_stockfish(fen, depth)
        
        if result:
            result["source"] = "stockfish"
            if use_cache:
                await self._save_to_cache(cache_key, result)
            return result
        
        # 4. Error fallback
        return {
            "fen": fen,
            "source": "error",
            "error": "Analysis failed",
            "depth": 0,
            "eval_cp": 0,
            "best_move": None
        }
    
    async def get_best_move(self, fen: str, depth: int = 18) -> Optional[str]:
        """Get just the best move for a position (SAN format)."""
        result = await self.get_position_eval(fen, depth=depth)
        return result.get("best_move_san")
    
    async def get_eval_score(self, fen: str, depth: int = 18) -> Tuple[int, Optional[int]]:
        """Get evaluation score: (centipawns, mate_in)."""
        result = await self.get_position_eval(fen, depth=depth)
        return result.get("eval_cp", 0), result.get("eval_mate")
    
    async def analyze_move(
        self,
        fen_before: str,
        move: str,
        depth: int = 18
    ) -> Dict:
        """
        Analyze a specific move - compare to best move.
        
        Returns:
            {
                "move": str (SAN),
                "eval_before": int,
                "eval_after": int,
                "cp_loss": int,
                "best_move": str,
                "is_best": bool,
                "classification": "best"|"excellent"|"good"|"inaccuracy"|"mistake"|"blunder"
            }
        """
        board = chess.Board(fen_before)
        
        # Get eval before move
        eval_before = await self.get_position_eval(fen_before, depth=depth)
        before_cp = eval_before.get("eval_cp", 0)
        best_move_san = eval_before.get("best_move_san", "")
        
        # Parse and make the move
        try:
            if len(move) >= 4 and move[1].isdigit():  # UCI format
                chess_move = board.parse_uci(move)
            else:  # SAN format
                chess_move = board.parse_san(move)
            move_san = board.san(chess_move)
            board.push(chess_move)
        except Exception as e:
            return {"error": f"Invalid move: {move}"}
        
        # Get eval after move
        eval_after = await self.get_position_eval(board.fen(), depth=depth)
        after_cp = -eval_after.get("eval_cp", 0)  # Negate (turn changed)
        
        # Calculate loss
        cp_loss = max(0, before_cp - after_cp)
        is_best = move_san == best_move_san
        
        return {
            "move": move_san,
            "eval_before": before_cp,
            "eval_after": after_cp,
            "cp_loss": cp_loss,
            "best_move": best_move_san,
            "is_best": is_best,
            "classification": self._classify_move(cp_loss, is_best)
        }
    
    async def batch_analyze(self, positions: List[str], depth: int = 18) -> List[Dict]:
        """Analyze multiple positions efficiently."""
        results = []
        for fen in positions:
            result = await self.get_position_eval(fen, depth=depth)
            results.append(result)
        return results
    
    def _classify_move(self, cp_loss: int, is_best: bool) -> str:
        """Classify move quality based on centipawn loss."""
        if is_best or cp_loss <= 0:
            return "best"
        elif cp_loss <= 10:
            return "excellent"
        elif cp_loss <= 25:
            return "good"
        elif cp_loss <= 50:
            return "inaccuracy"
        elif cp_loss <= 100:
            return "mistake"
        else:
            return "blunder"
    
    def _normalize_fen(self, fen: str) -> str:
        """Normalize FEN for cache (remove move counters)."""
        parts = fen.split()
        if len(parts) >= 4:
            return " ".join(parts[:4])
        return fen
    
    async def _get_from_db_cache(self, fen: str, min_depth: int) -> Optional[Dict]:
        """Get cached evaluation from MongoDB."""
        try:
            result = await self.db.position_evals.find_one(
                {"fen": fen, "depth": {"$gte": min_depth}},
                {"_id": 0}
            )
            return result
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None
    
    async def _save_to_cache(self, fen: str, result: Dict):
        """Save to both memory and MongoDB cache."""
        self._add_to_memory_cache(fen, result)
        
        try:
            cache_doc = {
                "fen": fen,
                **{k: v for k, v in result.items() if k != "source"},
                "cached_at": datetime.now(timezone.utc)
            }
            await self.db.position_evals.update_one(
                {"fen": fen},
                {"$set": cache_doc},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Cache write error: {e}")
    
    def _add_to_memory_cache(self, fen: str, result: Dict):
        """Add to memory cache with size limit."""
        global _memory_cache
        if len(_memory_cache) >= MAX_MEMORY_CACHE:
            # Remove oldest 10%
            keys_to_remove = list(_memory_cache.keys())[:200]
            for key in keys_to_remove:
                del _memory_cache[key]
        _memory_cache[fen] = result
    
    async def _run_stockfish(self, fen: str, depth: int) -> Optional[Dict]:
        """Run Stockfish analysis."""
        try:
            from stockfish_service import get_position_evaluation
            
            # Run in thread pool since stockfish_service is synchronous
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: get_position_evaluation(fen, depth=depth)
            )
            
            if not result or not result.get("success"):
                logger.error(f"Stockfish returned error: {result}")
                return None
            
            # Extract data from nested structure
            evaluation = result.get("evaluation", {})
            best_move_data = result.get("best_move", {})
            
            eval_cp = evaluation.get("centipawns", 0)
            eval_mate = evaluation.get("mate_in")
            best_move_uci = best_move_data.get("uci", "")
            best_move_san = best_move_data.get("san", "")
            
            return {
                "fen": fen,
                "depth": depth,
                "eval_cp": eval_cp,
                "eval_mate": eval_mate,
                "best_move": best_move_uci,
                "best_move_san": best_move_san,
                "pv": [best_move_uci] if best_move_uci else [],
                "pv_san": [best_move_san] if best_move_san else []
            }
            
        except Exception as e:
            logger.error(f"Stockfish error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        try:
            db_count = await self.db.position_evals.count_documents({})
            return {
                "memory_cache_size": len(_memory_cache),
                "db_cache_size": db_count
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def clear_cache(self):
        """Clear all caches."""
        global _memory_cache
        _memory_cache = {}
        await self.db.position_evals.delete_many({})
        return {"status": "cleared"}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_service_instance = None

def get_service(db) -> PositionAnalysisService:
    """Get or create service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = PositionAnalysisService(db)
    return _service_instance


async def quick_eval(db, fen: str, depth: int = 18) -> Dict:
    """Quick evaluation."""
    return await get_service(db).get_position_eval(fen, depth)


async def quick_best_move(db, fen: str) -> Optional[str]:
    """Quick best move lookup."""
    return await get_service(db).get_best_move(fen)
