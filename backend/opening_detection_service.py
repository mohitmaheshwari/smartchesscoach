"""
Opening Detection Service

Extracts and detects opening names from chess games:
1. Parse ECO code from PGN headers
2. Map ECO to opening name using eco_openings.json
3. Detect opening from moves if ECO not available

Usage:
    python3 opening_detection_service.py --backfill  # Fix existing games
"""

import re
import json
import logging
import asyncio
from typing import Dict, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
import chess
import chess.pgn
import io

logger = logging.getLogger(__name__)

# Load ECO to opening name mapping
ECO_OPENINGS = {}
try:
    with open("data/eco_openings.json", "r") as f:
        ECO_OPENINGS = json.load(f)
    # Remove metadata keys
    ECO_OPENINGS = {k.upper(): v for k, v in ECO_OPENINGS.items() if not k.startswith("_")}
    logger.info(f"Loaded {len(ECO_OPENINGS)} ECO opening mappings")
except Exception as e:
    logger.warning(f"Could not load ECO openings: {e}")

# Common opening positions (FEN after moves) -> Opening name
# This is a fallback for when ECO is not available
OPENING_POSITIONS = {
    # Italian Game
    "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R": ("C50", "Italian Game"),
    # Sicilian Defense
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR": ("B20", "Sicilian Defense"),
    # French Defense
    "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR": ("C00", "French Defense"),
    # Caro-Kann
    "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR": ("B10", "Caro-Kann Defense"),
    # Scandinavian
    "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR": ("B01", "Scandinavian Defense"),
    # Queen's Gambit
    "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR": ("D06", "Queen's Gambit"),
    # King's Indian
    "rnbqkb1r/pppppp1p/5np1/8/2PP4/8/PP2PPPP/RNBQKBNR": ("E60", "King's Indian Defense"),
    # London System
    "rnbqkbnr/ppp1pppp/8/3p4/3P1B2/8/PPP1PPPP/RN1QKBNR": ("D00", "London System"),
}


def extract_eco_from_pgn(pgn_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract ECO code and opening name from PGN headers.
    
    Returns:
        (eco_code, opening_name) - either may be None
    """
    eco_code = None
    opening_name = None
    
    # Try to extract ECO code (case-insensitive for headers like [Eco "A00"])
    eco_match = re.search(r'\[ECO\s+"([A-E]\d{2})"\]', pgn_text, re.IGNORECASE)
    if eco_match:
        eco_code = eco_match.group(1).upper()
    
    # Try to extract opening name from ECOUrl (Chess.com specific, case-insensitive)
    url_match = re.search(r'\[ECOUrl\s+"[^"]*openings/([^"]+)"\]', pgn_text, re.IGNORECASE)
    if url_match:
        # Convert URL slug to name: "Scandinavian-Defense-Mieses-Kotrc" -> "Scandinavian Defense"
        url_slug = url_match.group(1)
        # Get the main opening name (before specific variation)
        parts = url_slug.split("-")
        # Find where the variation starts (usually after "Defense", "Game", "Opening", etc.)
        main_parts = []
        for part in parts:
            main_parts.append(part)
            if part.lower() in ["defense", "defence", "game", "opening", "gambit", "attack", "system"]:
                break
        opening_name = " ".join(main_parts)
    
    # Try to get opening name from Opening header (Lichess, case-insensitive)
    if not opening_name:
        opening_match = re.search(r'\[Opening\s+"([^"]+)"\]', pgn_text, re.IGNORECASE)
        if opening_match:
            opening_name = opening_match.group(1)
    
    # Map ECO to name if we have ECO but no name
    if eco_code and not opening_name:
        opening_name = ECO_OPENINGS.get(eco_code)
    
    return eco_code, opening_name


def detect_opening_from_moves(pgn_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Detect opening by analyzing the first few moves.
    Fallback when ECO is not in PGN.
    
    Returns:
        (eco_code, opening_name)
    """
    try:
        # Parse PGN
        pgn_io = io.StringIO(pgn_text)
        game = chess.pgn.read_game(pgn_io)
        if not game:
            return None, None
        
        board = game.board()
        
        # Play through first 6 moves and check positions
        for i, move in enumerate(game.mainline_moves()):
            if i >= 12:  # 6 full moves
                break
            board.push(move)
            
            # Check if position matches known opening
            # Normalize FEN (remove move counters)
            fen_key = " ".join(board.fen().split()[:4])
            for known_fen, (eco, name) in OPENING_POSITIONS.items():
                known_fen_normalized = " ".join(known_fen.split()[:4])
                if fen_key == known_fen_normalized:
                    return eco, name
        
        # If no match, try to classify by first moves
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        moves = list(game.mainline_moves())[:4]
        if len(moves) >= 1:
            first_move = game.board().san(moves[0])
            if first_move == "e4":
                if len(moves) >= 2:
                    board = game.board()
                    board.push(moves[0])
                    second_move = board.san(moves[1])
                    if second_move == "e5":
                        return "C20", "King's Pawn Game"
                    elif second_move == "c5":
                        return "B20", "Sicilian Defense"
                    elif second_move == "e6":
                        return "C00", "French Defense"
                    elif second_move == "c6":
                        return "B10", "Caro-Kann Defense"
                    elif second_move == "d5":
                        return "B01", "Scandinavian Defense"
                    elif second_move == "d6":
                        return "B06", "Modern Defense"
                    elif second_move == "Nf6":
                        return "B02", "Alekhine's Defense"
                    elif second_move == "g6":
                        return "B06", "Modern Defense"
                return "B00", "King's Pawn Opening"
            elif first_move == "d4":
                if len(moves) >= 2:
                    board = game.board()
                    board.push(moves[0])
                    second_move = board.san(moves[1])
                    if second_move == "d5":
                        return "D00", "Queen's Pawn Game"
                    elif second_move == "Nf6":
                        return "A45", "Indian Defense"
                    elif second_move == "f5":
                        return "A80", "Dutch Defense"
                return "D00", "Queen's Pawn Opening"
            elif first_move == "c4":
                return "A10", "English Opening"
            elif first_move == "Nf3":
                return "A04", "Reti Opening"
        
        return None, None
        
    except Exception as e:
        logger.error(f"Error detecting opening from moves: {e}")
        return None, None


def get_opening_for_game(pgn_text: str) -> Dict:
    """
    Get opening information for a game.
    
    Returns:
        {
            "eco": str or None,
            "opening_name": str or None,
            "detection_method": "pgn_header" | "move_detection" | "unknown"
        }
    """
    if not pgn_text:
        return {"eco": None, "opening_name": None, "detection_method": "no_pgn"}
    
    # First try to extract from PGN headers
    eco, name = extract_eco_from_pgn(pgn_text)
    if eco or name:
        # If we have ECO but no name, look up
        if eco and not name:
            name = ECO_OPENINGS.get(eco, f"Unknown ({eco})")
        return {
            "eco": eco,
            "opening_name": name,
            "detection_method": "pgn_header"
        }
    
    # Fallback to move detection
    eco, name = detect_opening_from_moves(pgn_text)
    if eco or name:
        return {
            "eco": eco,
            "opening_name": name or ECO_OPENINGS.get(eco, "Unknown"),
            "detection_method": "move_detection"
        }
    
    return {"eco": None, "opening_name": None, "detection_method": "unknown"}


async def backfill_openings(db_name: str = "test_database", dry_run: bool = False):
    """
    Backfill opening data for all games that don't have it.
    
    Args:
        db_name: MongoDB database name
        dry_run: If True, don't actually update, just report
    """
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client[db_name]
    
    # Find games without opening_name
    query = {"$or": [
        {"opening_name": None},
        {"opening_name": {"$exists": False}},
        {"opening_name": ""}
    ]}
    
    total = await db.games.count_documents(query)
    print(f"Found {total} games without opening data")
    
    if total == 0:
        print("All games have opening data!")
        return
    
    # Process in batches
    updated = 0
    failed = 0
    stats = {"pgn_header": 0, "move_detection": 0, "unknown": 0, "no_pgn": 0}
    
    cursor = db.games.find(query, {"_id": 1, "pgn": 1})
    
    async for game in cursor:
        pgn = game.get("pgn", "")
        result = get_opening_for_game(pgn)
        
        stats[result["detection_method"]] += 1
        
        if result["opening_name"]:
            if not dry_run:
                await db.games.update_one(
                    {"_id": game["_id"]},
                    {"$set": {
                        "opening_name": result["opening_name"],
                        "eco": result["eco"]
                    }}
                )
            updated += 1
        else:
            failed += 1
        
        if (updated + failed) % 50 == 0:
            print(f"Processed {updated + failed}/{total}...")
    
    print(f"\n=== Backfill Complete ===")
    print(f"Updated: {updated}")
    print(f"Could not detect: {failed}")
    print(f"\nDetection methods:")
    for method, count in stats.items():
        print(f"  {method}: {count}")


if __name__ == "__main__":
    import sys
    
    if "--backfill" in sys.argv:
        dry_run = "--dry-run" in sys.argv
        asyncio.run(backfill_openings(dry_run=dry_run))
    else:
        # Test with sample PGN
        test_pgn = '''[ECO "B01"]
[ECOUrl "https://www.chess.com/openings/Scandinavian-Defense"]

1. e4 d5 2. exd5 Qxd5'''
        
        result = get_opening_for_game(test_pgn)
        print(f"Test result: {result}")
