"""
Lichess Opening Explorer API Integration

Provides:
- Opening name detection from position
- Popular moves in positions
- Win/draw/loss statistics
"""

import httpx
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
import chess


@dataclass
class OpeningInfo:
    """Opening information from Lichess"""
    name: str
    eco: str
    moves: List[Dict]  # [{san, uci, white, draws, black, averageRating}]
    total_games: int


@dataclass
class MoveStats:
    """Statistics for a specific move"""
    san: str
    uci: str
    white_wins: int
    draws: int
    black_wins: int
    total: int
    win_rate: float  # From perspective of side to move
    average_rating: int


async def get_opening_info(fen: str, ratings: str = "1600,1800,2000") -> Optional[OpeningInfo]:
    """
    Get opening info from Lichess Explorer API.
    
    Args:
        fen: Position FEN
        ratings: Comma-separated rating ranges
        
    Returns:
        OpeningInfo or None if request fails
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://explorer.lichess.ovh/lichess",
                params={
                    "fen": fen,
                    "ratings": ratings,
                    "speeds": "blitz,rapid,classical",
                }
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            # Extract opening name if available
            opening_name = ""
            eco = ""
            if "opening" in data and data["opening"]:
                opening_name = data["opening"].get("name", "")
                eco = data["opening"].get("eco", "")
            
            # Calculate total games
            total = data.get("white", 0) + data.get("draws", 0) + data.get("black", 0)
            
            return OpeningInfo(
                name=opening_name,
                eco=eco,
                moves=data.get("moves", []),
                total_games=total
            )
    except Exception as e:
        print(f"Lichess API error: {e}")
        return None


async def get_popular_moves(fen: str, top_n: int = 5) -> List[MoveStats]:
    """
    Get most popular moves for a position.
    
    Returns list of moves sorted by popularity.
    """
    info = await get_opening_info(fen)
    if not info or not info.moves:
        return []
    
    # Determine who's to move
    board = chess.Board(fen)
    white_to_move = board.turn == chess.WHITE
    
    result = []
    for move_data in info.moves[:top_n]:
        white = move_data.get("white", 0)
        draws = move_data.get("draws", 0)
        black = move_data.get("black", 0)
        total = white + draws + black
        
        if total == 0:
            continue
        
        # Win rate from perspective of side to move
        if white_to_move:
            win_rate = (white + draws * 0.5) / total * 100
        else:
            win_rate = (black + draws * 0.5) / total * 100
        
        result.append(MoveStats(
            san=move_data.get("san", ""),
            uci=move_data.get("uci", ""),
            white_wins=white,
            draws=draws,
            black_wins=black,
            total=total,
            win_rate=round(win_rate, 1),
            average_rating=move_data.get("averageRating", 0)
        ))
    
    return result


async def get_opening_name(fen: str) -> str:
    """
    Get just the opening name for a position.
    Returns empty string if not found.
    """
    info = await get_opening_info(fen)
    if info and info.name:
        return info.name
    return ""


def format_move_stats_for_chat(moves: List[MoveStats], user_color: str) -> str:
    """
    Format move statistics for coach chat.
    Plain language, no jargon.
    """
    if not moves:
        return "This position doesn't appear often in the database."
    
    lines = ["Here's what strong players do in this position:"]
    for i, m in enumerate(moves[:3], 1):
        games_text = f"{m.total:,}" if m.total >= 1000 else str(m.total)
        lines.append(f"{i}. {m.san} - played in {games_text} games ({m.win_rate}% success rate)")
    
    return "\n".join(lines)


async def get_master_opening_info(fen: str) -> Optional[OpeningInfo]:
    """
    Get opening info from master games (higher quality but fewer games).
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://explorer.lichess.ovh/masters",
                params={"fen": fen}
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            opening_name = ""
            eco = ""
            if "opening" in data and data["opening"]:
                opening_name = data["opening"].get("name", "")
                eco = data["opening"].get("eco", "")
            
            total = data.get("white", 0) + data.get("draws", 0) + data.get("black", 0)
            
            return OpeningInfo(
                name=opening_name,
                eco=eco,
                moves=data.get("moves", []),
                total_games=total
            )
    except Exception as e:
        print(f"Lichess Masters API error: {e}")
        return None


# ==================== HELPER FUNCTIONS ====================

def is_opening_phase(move_number: int) -> bool:
    """Check if we're still in the opening phase"""
    return move_number <= 15


async def get_best_opening_move(fen: str) -> Optional[str]:
    """
    Get the most popular move for a position (good for coach to play).
    """
    moves = await get_popular_moves(fen, top_n=1)
    if moves:
        return moves[0].san
    return None


async def check_if_book_move(fen: str, move_san: str) -> bool:
    """
    Check if a move is a common book move.
    """
    moves = await get_popular_moves(fen, top_n=10)
    for m in moves:
        if m.san == move_san:
            return True
    return False


async def get_position_evaluation_hint(fen: str) -> Optional[str]:
    """
    Get a quick hint about what strong players do here.
    """
    info = await get_opening_info(fen)
    if not info or info.total_games < 100:
        return None
    
    if not info.moves:
        return None
    
    top_move = info.moves[0]
    return f"Strong players usually play {top_move.get('san', '?')} here."
