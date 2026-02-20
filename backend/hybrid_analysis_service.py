"""
Hybrid Analysis Service

Combines Lichess Cloud Eval (fast, free) with local Stockfish (reliable fallback).

Flow:
1. Check local cache first
2. Try Lichess Cloud Eval (instant if position exists)
3. Fallback to local Stockfish
4. Cache result for future use

Benefits:
- Faster responses (cloud = pre-computed)
- Lower server load (less Stockfish CPU)
- Always works (Stockfish fallback)
- Better depth (cloud often 30-40+)
"""

import logging
import httpx
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import chess

logger = logging.getLogger(__name__)

# Lichess Cloud Eval endpoint
LICHESS_CLOUD_EVAL_URL = "https://lichess.org/api/cloud-eval"

# Rate limiting: track last request time
_last_lichess_request = 0
LICHESS_MIN_INTERVAL = 1.0  # 1 second between requests

# In-memory cache for session (MongoDB cache is persistent)
_memory_cache = {}
MAX_MEMORY_CACHE = 1000


class HybridAnalysisService:
    """
    Hybrid position analysis using Lichess Cloud + Local Stockfish.
    """
    
    def __init__(self, db, stockfish_service=None):
        """
        Initialize with database and optional stockfish service.
        
        Args:
            db: MongoDB database instance
            stockfish_service: Local Stockfish service for fallback
        """
        self.db = db
        self.stockfish = stockfish_service
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Ensure the cache collection exists with proper indexes."""
        # Collection will be created on first insert
        # Index on fen for fast lookups
        pass
    
    async def get_position_eval(
        self,
        fen: str,
        depth: int = 20,
        multi_pv: int = 1,
        use_cache: bool = True
    ) -> Dict:
        """
        Get evaluation for a position using hybrid approach.
        
        Args:
            fen: FEN string of position
            depth: Minimum acceptable depth (for Stockfish fallback)
            multi_pv: Number of principal variations to return
            use_cache: Whether to use/update cache
        
        Returns:
            {
                "fen": str,
                "source": "cache" | "lichess_cloud" | "local_stockfish",
                "depth": int,
                "eval_cp": int,  # centipawns (positive = white better)
                "eval_mate": int | None,  # moves to mate (if applicable)
                "best_move": str,  # UCI format
                "best_move_san": str,  # SAN format
                "pv": [str],  # principal variation in UCI
                "pv_san": [str],  # principal variation in SAN
            }
        """
        # Normalize FEN (remove move counters for better cache hits)
        normalized_fen = self._normalize_fen(fen)
        
        # 1. Check memory cache first (fastest)
        if use_cache and normalized_fen in _memory_cache:
            logger.debug(f"Memory cache hit for position")
            return {**_memory_cache[normalized_fen], "source": "memory_cache"}
        
        # 2. Check MongoDB cache
        if use_cache:
            cached = await self._get_from_db_cache(normalized_fen)
            if cached and cached.get("depth", 0) >= depth:
                logger.debug(f"DB cache hit for position (depth {cached.get('depth')})")
                self._add_to_memory_cache(normalized_fen, cached)
                return {**cached, "source": "db_cache"}
        
        # 3. Try Lichess Cloud Eval
        lichess_result = await self._fetch_lichess_cloud(fen, multi_pv)
        if lichess_result and lichess_result.get("depth", 0) >= depth:
            logger.info(f"Lichess cloud hit (depth {lichess_result.get('depth')})")
            result = self._format_lichess_result(fen, lichess_result)
            if use_cache:
                await self._save_to_cache(normalized_fen, result)
            return result
        
        # 4. Fallback to local Stockfish
        logger.info(f"Falling back to local Stockfish (depth {depth})")
        stockfish_result = await self._run_local_stockfish(fen, depth, multi_pv)
        if stockfish_result:
            if use_cache:
                await self._save_to_cache(normalized_fen, stockfish_result)
            return stockfish_result
        
        # 5. If all else fails, return error
        logger.error(f"All analysis methods failed for position")
        return {
            "fen": fen,
            "source": "error",
            "error": "Could not analyze position",
            "depth": 0,
            "eval_cp": 0,
            "best_move": None
        }
    
    async def get_best_move(self, fen: str, depth: int = 18) -> Optional[str]:
        """
        Quick method to just get the best move for a position.
        
        Returns:
            Best move in SAN format, or None if analysis fails
        """
        result = await self.get_position_eval(fen, depth=depth)
        return result.get("best_move_san")
    
    async def get_eval_score(self, fen: str) -> Tuple[int, Optional[int]]:
        """
        Quick method to get evaluation score.
        
        Returns:
            (centipawns, mate_in) - mate_in is None if not a mate position
        """
        result = await self.get_position_eval(fen, depth=18)
        return result.get("eval_cp", 0), result.get("eval_mate")
    
    async def analyze_move(
        self,
        fen_before: str,
        move: str,
        depth: int = 18
    ) -> Dict:
        """
        Analyze a specific move - get eval before, after, and centipawn loss.
        
        Args:
            fen_before: Position before the move
            move: The move played (SAN or UCI)
            depth: Analysis depth
        
        Returns:
            {
                "move": str,
                "eval_before": int,
                "eval_after": int,
                "cp_loss": int,
                "best_move": str,
                "best_eval": int,
                "is_best": bool,
                "classification": "best" | "excellent" | "good" | "inaccuracy" | "mistake" | "blunder"
            }
        """
        # Get position before
        board = chess.Board(fen_before)
        eval_before = await self.get_position_eval(fen_before, depth=depth)
        
        # Make the move
        try:
            if len(move) > 3 and move[1].isdigit():  # UCI format
                chess_move = board.parse_uci(move)
            else:  # SAN format
                chess_move = board.parse_san(move)
            board.push(chess_move)
        except Exception as e:
            logger.error(f"Invalid move {move}: {e}")
            return {"error": f"Invalid move: {move}"}
        
        fen_after = board.fen()
        
        # Get position after
        eval_after = await self.get_position_eval(fen_after, depth=depth)
        
        # Calculate centipawn loss (from perspective of side that moved)
        # Note: After the move, it's opponent's turn, so we negate
        before_cp = eval_before.get("eval_cp", 0)
        after_cp = -eval_after.get("eval_cp", 0)  # Negate because turn changed
        
        best_cp = before_cp  # Best possible was to maintain eval
        if eval_before.get("best_move"):
            # The best move's resulting eval
            best_cp = before_cp
        
        cp_loss = max(0, before_cp - after_cp)
        
        # Check if this was the best move
        best_move = eval_before.get("best_move_san", "")
        move_san = chess_move.uci()
        try:
            board_temp = chess.Board(fen_before)
            move_san = board_temp.san(chess_move)
        except:
            pass
        
        is_best = best_move and move_san == best_move
        
        # Classify the move
        classification = self._classify_move(cp_loss, is_best)
        
        return {
            "move": move_san,
            "eval_before": before_cp,
            "eval_after": after_cp,
            "cp_loss": cp_loss,
            "best_move": best_move,
            "is_best": is_best,
            "classification": classification
        }
    
    def _classify_move(self, cp_loss: int, is_best: bool) -> str:
        """Classify a move based on centipawn loss."""
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
        """
        Normalize FEN for better cache hits.
        Remove halfmove and fullmove counters.
        """
        parts = fen.split()
        if len(parts) >= 4:
            # Keep position, turn, castling, en passant
            return " ".join(parts[:4])
        return fen
    
    async def _get_from_db_cache(self, fen: str) -> Optional[Dict]:
        """Get cached evaluation from MongoDB."""
        try:
            result = await self.db.position_evals.find_one(
                {"fen": fen},
                {"_id": 0}
            )
            return result
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None
    
    async def _save_to_cache(self, fen: str, result: Dict):
        """Save evaluation to both memory and MongoDB cache."""
        # Memory cache
        self._add_to_memory_cache(fen, result)
        
        # MongoDB cache
        try:
            cache_doc = {
                "fen": fen,
                **result,
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
            # Remove oldest entries (simple FIFO)
            keys_to_remove = list(_memory_cache.keys())[:100]
            for key in keys_to_remove:
                del _memory_cache[key]
        _memory_cache[fen] = result
    
    async def _fetch_lichess_cloud(self, fen: str, multi_pv: int = 1) -> Optional[Dict]:
        """
        Fetch evaluation from Lichess Cloud Eval API.
        
        Rate limited to 1 request per second.
        """
        global _last_lichess_request
        
        # Rate limiting
        now = asyncio.get_event_loop().time()
        time_since_last = now - _last_lichess_request
        if time_since_last < LICHESS_MIN_INTERVAL:
            await asyncio.sleep(LICHESS_MIN_INTERVAL - time_since_last)
        
        try:
            params = {
                "fen": fen,
                "multiPv": multi_pv
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(LICHESS_CLOUD_EVAL_URL, params=params)
                _last_lichess_request = asyncio.get_event_loop().time()
                
                if response.status_code == 200:
                    data = response.json()
                    if data and data.get("pvs"):
                        return data
                    logger.debug("Lichess cloud: position not in database")
                    return None
                elif response.status_code == 404:
                    logger.debug("Lichess cloud: position not found")
                    return None
                elif response.status_code == 429:
                    logger.warning("Lichess cloud: rate limited, waiting 60s")
                    await asyncio.sleep(60)
                    return None
                else:
                    logger.warning(f"Lichess cloud: unexpected status {response.status_code}")
                    return None
                    
        except httpx.TimeoutException:
            logger.warning("Lichess cloud: request timed out")
            return None
        except Exception as e:
            logger.error(f"Lichess cloud error: {e}")
            return None
    
    def _format_lichess_result(self, fen: str, data: Dict) -> Dict:
        """Format Lichess Cloud Eval response to our standard format."""
        pvs = data.get("pvs", [])
        if not pvs:
            return None
        
        first_pv = pvs[0]
        moves_uci = first_pv.get("moves", "").split()
        
        # Convert UCI to SAN
        board = chess.Board(fen)
        moves_san = []
        best_move_san = None
        
        for i, uci_move in enumerate(moves_uci):
            try:
                move = board.parse_uci(uci_move)
                san = board.san(move)
                moves_san.append(san)
                if i == 0:
                    best_move_san = san
                board.push(move)
            except:
                break
        
        # Get evaluation
        eval_cp = first_pv.get("cp")
        eval_mate = first_pv.get("mate")
        
        return {
            "fen": fen,
            "source": "lichess_cloud",
            "depth": data.get("depth", 0),
            "knodes": data.get("knodes", 0),
            "eval_cp": eval_cp if eval_cp is not None else 0,
            "eval_mate": eval_mate,
            "best_move": moves_uci[0] if moves_uci else None,
            "best_move_san": best_move_san,
            "pv": moves_uci[:10],  # Limit to 10 moves
            "pv_san": moves_san[:10]
        }
    
    async def _run_local_stockfish(
        self,
        fen: str,
        depth: int,
        multi_pv: int = 1
    ) -> Optional[Dict]:
        """
        Run local Stockfish analysis as fallback.
        """
        if not self.stockfish:
            logger.warning("No Stockfish service available for fallback")
            return None
        
        try:
            # Use existing stockfish service
            from stockfish_service import analyze_position
            
            result = await analyze_position(fen, depth=depth)
            
            if not result:
                return None
            
            # Convert to our standard format
            board = chess.Board(fen)
            best_move_uci = result.get("best_move", "")
            best_move_san = None
            
            if best_move_uci:
                try:
                    move = board.parse_uci(best_move_uci)
                    best_move_san = board.san(move)
                except:
                    pass
            
            # Parse PV
            pv_uci = result.get("pv", [])
            pv_san = []
            temp_board = chess.Board(fen)
            for uci in pv_uci[:10]:
                try:
                    move = temp_board.parse_uci(uci)
                    pv_san.append(temp_board.san(move))
                    temp_board.push(move)
                except:
                    break
            
            return {
                "fen": fen,
                "source": "local_stockfish",
                "depth": depth,
                "eval_cp": result.get("score_cp", 0),
                "eval_mate": result.get("mate_in"),
                "best_move": best_move_uci,
                "best_move_san": best_move_san,
                "pv": pv_uci[:10],
                "pv_san": pv_san
            }
            
        except Exception as e:
            logger.error(f"Local Stockfish error: {e}")
            return None
    
    async def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        try:
            db_count = await self.db.position_evals.count_documents({})
            
            # Sample to check sources
            pipeline = [
                {"$group": {"_id": "$source", "count": {"$sum": 1}}}
            ]
            sources = await self.db.position_evals.aggregate(pipeline).to_list(10)
            
            return {
                "memory_cache_size": len(_memory_cache),
                "db_cache_size": db_count,
                "sources": {s["_id"]: s["count"] for s in sources}
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
    
    async def clear_cache(self, older_than_days: int = None):
        """
        Clear cache.
        
        Args:
            older_than_days: If set, only clear entries older than this
        """
        global _memory_cache
        _memory_cache = {}
        
        if older_than_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            result = await self.db.position_evals.delete_many(
                {"cached_at": {"$lt": cutoff}}
            )
            return {"deleted": result.deleted_count}
        else:
            result = await self.db.position_evals.delete_many({})
            return {"deleted": result.deleted_count}


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

# Global instance (initialized on first use)
_hybrid_service = None


async def get_hybrid_service(db) -> HybridAnalysisService:
    """Get or create the global hybrid analysis service."""
    global _hybrid_service
    if _hybrid_service is None:
        _hybrid_service = HybridAnalysisService(db)
    return _hybrid_service


async def quick_eval(db, fen: str) -> Dict:
    """Quick evaluation using hybrid approach."""
    service = await get_hybrid_service(db)
    return await service.get_position_eval(fen)


async def quick_best_move(db, fen: str) -> Optional[str]:
    """Quick best move lookup."""
    service = await get_hybrid_service(db)
    return await service.get_best_move(fen)
