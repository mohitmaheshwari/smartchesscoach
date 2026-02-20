"""
Lichess Opening Explorer Integration

Fetches real opening data from Lichess including:
- Opening names and ECO codes
- Win/draw/loss statistics from millions of games
- Most popular continuations
- Master game database support
"""

import logging
import httpx
from typing import Dict, List, Optional, Tuple
from functools import lru_cache
import asyncio

logger = logging.getLogger(__name__)

# Lichess Opening Explorer endpoints
LICHESS_MASTERS_URL = "https://explorer.lichess.ovh/masters"
LICHESS_LICHESS_URL = "https://explorer.lichess.ovh/lichess"
LICHESS_PLAYER_URL = "https://explorer.lichess.ovh/player"

# Cache for opening data (to avoid hitting API too frequently)
_opening_cache = {}


def san_to_uci(san_moves: List[str]) -> str:
    """
    Convert SAN moves to UCI format for Lichess API.
    e.g., ["e4", "e5", "Nf3"] -> "e2e4,e7e5,g1f3"
    
    Note: This is a simplified conversion. For accurate conversion,
    we'd need to track the board state.
    """
    import chess
    board = chess.Board()
    uci_moves = []
    
    for san in san_moves:
        try:
            move = board.parse_san(san)
            uci_moves.append(move.uci())
            board.push(move)
        except Exception as e:
            logger.warning(f"Could not parse move {san}: {e}")
            break
    
    return ",".join(uci_moves)


def fen_to_uci_moves(fen: str) -> Optional[str]:
    """
    If we have a FEN, we can query directly with it.
    Returns None if it's the starting position.
    """
    import chess
    start_fen = chess.STARTING_FEN
    if fen == start_fen or not fen:
        return None
    return None  # For non-starting positions, use the FEN parameter directly


async def fetch_lichess_opening(
    moves: List[str] = None,
    fen: str = None,
    source: str = "lichess",  # "lichess" or "masters"
    speeds: List[str] = None,
    ratings: List[int] = None,
    timeout: float = 10.0
) -> Optional[Dict]:
    """
    Fetch opening data from Lichess Opening Explorer.
    
    Args:
        moves: List of SAN moves (e.g., ["e4", "e5", "Nf3"])
        fen: FEN position (alternative to moves)
        source: "lichess" for Lichess games, "masters" for master games
        speeds: Filter by time controls (e.g., ["blitz", "rapid"])
        ratings: Filter by rating ranges (e.g., [1600, 1800, 2000])
        timeout: Request timeout in seconds
    
    Returns:
        Dict with opening info, statistics, and top moves
    """
    # Build the URL
    if source == "masters":
        url = LICHESS_MASTERS_URL
    else:
        url = LICHESS_LICHESS_URL
    
    # Build query parameters
    params = {}
    
    if moves:
        uci = san_to_uci(moves)
        if uci:
            params["play"] = uci
    
    if fen:
        params["fen"] = fen
    
    if speeds:
        params["speeds"] = ",".join(speeds)
    
    if ratings:
        params["ratings"] = ",".join(str(r) for r in ratings)
    
    # Cache key
    cache_key = f"{source}:{params.get('play', '')}:{params.get('fen', '')}"
    if cache_key in _opening_cache:
        return _opening_cache[cache_key]
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Cache the result
                _opening_cache[cache_key] = data
                
                return data
            else:
                logger.warning(f"Lichess API returned {response.status_code}")
                return None
                
    except httpx.TimeoutException:
        logger.warning("Lichess API request timed out")
        return None
    except Exception as e:
        logger.error(f"Error fetching from Lichess: {e}")
        return None


async def get_opening_info(moves: List[str], source: str = "lichess") -> Dict:
    """
    Get comprehensive opening information for a move sequence.
    
    Returns:
        {
            "opening": {"eco": "C50", "name": "Italian Game"},
            "white_wins": 35.2,
            "draws": 32.1,
            "black_wins": 32.7,
            "total_games": 1234567,
            "top_moves": [
                {"san": "Bc5", "uci": "f8c5", "white": 35, "draws": 33, "black": 32, "games": 500000},
                ...
            ],
            "top_games": [...],  # Sample master games if available
        }
    """
    data = await fetch_lichess_opening(moves=moves, source=source)
    
    if not data:
        return {
            "opening": None,
            "white_wins": 0,
            "draws": 0,
            "black_wins": 0,
            "total_games": 0,
            "top_moves": [],
            "error": "Could not fetch data from Lichess"
        }
    
    # Calculate percentages
    white = data.get("white", 0)
    draws = data.get("draws", 0)
    black = data.get("black", 0)
    total = white + draws + black
    
    result = {
        "opening": data.get("opening"),  # {"eco": "C50", "name": "Italian Game"}
        "white_wins": round(white / total * 100, 1) if total > 0 else 0,
        "draws": round(draws / total * 100, 1) if total > 0 else 0,
        "black_wins": round(black / total * 100, 1) if total > 0 else 0,
        "total_games": total,
        "top_moves": [],
        "top_games": data.get("topGames", [])[:5],  # Limit to 5 sample games
        "recent_games": data.get("recentGames", [])[:3]
    }
    
    # Process top moves
    for move_data in data.get("moves", [])[:10]:  # Top 10 moves
        move_white = move_data.get("white", 0)
        move_draws = move_data.get("draws", 0)
        move_black = move_data.get("black", 0)
        move_total = move_white + move_draws + move_black
        
        result["top_moves"].append({
            "san": move_data.get("san"),
            "uci": move_data.get("uci"),
            "white_percent": round(move_white / move_total * 100, 1) if move_total > 0 else 0,
            "draw_percent": round(move_draws / move_total * 100, 1) if move_total > 0 else 0,
            "black_percent": round(move_black / move_total * 100, 1) if move_total > 0 else 0,
            "games": move_total,
            "average_rating": move_data.get("averageRating", 0)
        })
    
    return result


async def get_opening_variations(moves: List[str], depth: int = 3) -> List[Dict]:
    """
    Get the most popular variations from a position.
    Recursively explores the top moves up to a certain depth.
    
    Args:
        moves: Starting position as a list of SAN moves
        depth: How many half-moves deep to explore
    
    Returns:
        List of variations with their statistics
    """
    variations = []
    
    async def explore(current_moves: List[str], current_depth: int, variation_name: str = ""):
        if current_depth <= 0:
            return
        
        data = await fetch_lichess_opening(moves=current_moves)
        if not data or not data.get("moves"):
            return
        
        # Get top 3 moves at this depth
        top_moves = data.get("moves", [])[:3]
        
        for move_data in top_moves:
            san = move_data.get("san")
            if not san:
                continue
            
            new_moves = current_moves + [san]
            games = move_data.get("white", 0) + move_data.get("draws", 0) + move_data.get("black", 0)
            
            # Only explore if there are enough games
            if games < 100:
                continue
            
            var_name = f"{variation_name} {san}".strip()
            
            variations.append({
                "moves": new_moves,
                "name": var_name,
                "games": games,
                "white_percent": round(move_data.get("white", 0) / games * 100, 1) if games > 0 else 0
            })
            
            # Explore deeper (but limit concurrency)
            if current_depth > 1:
                await explore(new_moves, current_depth - 1, var_name)
    
    await explore(moves, depth)
    
    # Sort by popularity and return top variations
    variations.sort(key=lambda x: -x["games"])
    return variations[:10]


async def get_player_opening_stats(
    username: str,
    color: str = "white",
    moves: List[str] = None,
    speeds: List[str] = None
) -> Optional[Dict]:
    """
    Get opening statistics for a specific player.
    
    Args:
        username: Lichess username
        color: "white" or "black"
        moves: Optional move sequence to filter
        speeds: Time controls to include
    
    Returns:
        Player's statistics for this opening position
    """
    params = {
        "player": username,
        "color": color
    }
    
    if moves:
        uci = san_to_uci(moves)
        if uci:
            params["play"] = uci
    
    if speeds:
        params["speeds"] = ",".join(speeds)
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(LICHESS_PLAYER_URL, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Lichess player API returned {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"Error fetching player data: {e}")
        return None


# ============================================================================
# HIGH-LEVEL FUNCTIONS FOR OPENING TRAINER
# ============================================================================

async def get_full_opening_data(moves: List[str]) -> Dict:
    """
    Get comprehensive opening data combining Lichess stats with our curated content.
    
    This is the main function to call from the API endpoint.
    """
    # Fetch from both masters and Lichess databases in parallel
    masters_task = get_opening_info(moves, source="masters")
    lichess_task = get_opening_info(moves, source="lichess")
    
    masters_data, lichess_data = await asyncio.gather(masters_task, lichess_task)
    
    # Use masters data for opening name if available, fall back to lichess
    opening_info = masters_data.get("opening") or lichess_data.get("opening") or {}
    
    # Combine statistics (prefer Lichess for more data, but include masters for reference)
    result = {
        "opening": {
            "name": opening_info.get("name", "Unknown Opening"),
            "eco": opening_info.get("eco", ""),
            "main_line": moves
        },
        "statistics": {
            "lichess": {
                "total_games": lichess_data.get("total_games", 0),
                "white_wins": lichess_data.get("white_wins", 0),
                "draws": lichess_data.get("draws", 0),
                "black_wins": lichess_data.get("black_wins", 0)
            },
            "masters": {
                "total_games": masters_data.get("total_games", 0),
                "white_wins": masters_data.get("white_wins", 0),
                "draws": masters_data.get("draws", 0),
                "black_wins": masters_data.get("black_wins", 0)
            }
        },
        "top_moves": lichess_data.get("top_moves", []),
        "master_games": masters_data.get("top_games", []),
        "variations": []  # Will be populated by get_opening_variations if needed
    }
    
    return result


async def search_opening_by_name(name: str) -> Optional[Dict]:
    """
    Search for an opening by name and return its data.
    
    This maps common opening names to their typical move sequences,
    then fetches data from Lichess.
    """
    # Common opening name to moves mapping
    OPENING_MOVES = {
        "italian game": ["e4", "e5", "Nf3", "Nc6", "Bc4"],
        "sicilian defense": ["e4", "c5"],
        "sicilian najdorf": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"],
        "french defense": ["e4", "e6"],
        "caro-kann defense": ["e4", "c6"],
        "scandinavian defense": ["e4", "d5"],
        "queens gambit": ["d4", "d5", "c4"],
        "queens gambit declined": ["d4", "d5", "c4", "e6"],
        "kings indian defense": ["d4", "Nf6", "c4", "g6"],
        "london system": ["d4", "d5", "Bf4"],
        "ruy lopez": ["e4", "e5", "Nf3", "Nc6", "Bb5"],
        "english opening": ["c4"],
        "dutch defense": ["d4", "f5"],
        "grunfeld defense": ["d4", "Nf6", "c4", "g6", "Nc3", "d5"],
        "slav defense": ["d4", "d5", "c4", "c6"],
        "pirc defense": ["e4", "d6", "d4", "Nf6"],
        "alekhine defense": ["e4", "Nf6"],
        "nimzo indian": ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"],
        "queens indian": ["d4", "Nf6", "c4", "e6", "Nf3", "b6"],
        "catalan": ["d4", "Nf6", "c4", "e6", "g3"],
        "vienna game": ["e4", "e5", "Nc3"],
        "scotch game": ["e4", "e5", "Nf3", "Nc6", "d4"],
        "petroff defense": ["e4", "e5", "Nf3", "Nf6"],
        "philidor defense": ["e4", "e5", "Nf3", "d6"],
        "modern defense": ["e4", "g6"],
    }
    
    # Normalize the search name
    search_key = name.lower().strip()
    
    # Find matching opening
    moves = None
    for key, move_list in OPENING_MOVES.items():
        if search_key in key or key in search_key:
            moves = move_list
            break
    
    if not moves:
        return None
    
    return await get_full_opening_data(moves)


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

def clear_opening_cache():
    """Clear the opening data cache."""
    global _opening_cache
    _opening_cache = {}
    logger.info("Opening cache cleared")


def get_cache_stats() -> Dict:
    """Get cache statistics."""
    return {
        "cached_positions": len(_opening_cache),
        "cache_keys": list(_opening_cache.keys())[:10]  # Show first 10 keys
    }
