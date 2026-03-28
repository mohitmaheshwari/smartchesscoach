"""
Opening Knowledge Base Builder

Uses Lichess as a SOURCE to build our own opening teaching database.
This runs periodically (not live) to populate MongoDB with:
- Opening names and ECO codes
- Common moves and their purposes
- Teaching moments for each variation
- Statistics (win rates, popularity)

Once built, all users read from OUR database - no rate limits!
"""

import asyncio
import httpx
import chess
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
import time


# Common opening positions to seed the database
SEED_POSITIONS = [
    # Starting position
    {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "name": "Starting Position"},
    
    # After 1.e4
    {"fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "name": "After 1.e4"},
    
    # After 1.d4
    {"fen": "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1", "name": "After 1.d4"},
    
    # After 1.e4 e5
    {"fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "name": "Open Game"},
    
    # After 1.e4 c5 (Sicilian)
    {"fen": "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "name": "Sicilian Defense"},
    
    # After 1.e4 e6 (French)
    {"fen": "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "name": "French Defense"},
    
    # After 1.e4 c6 (Caro-Kann)
    {"fen": "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "name": "Caro-Kann Defense"},
    
    # After 1.e4 e5 2.Nf3 (King's Knight)
    {"fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2", "name": "King's Knight Opening"},
    
    # After 1.e4 e5 2.Nf3 Nc6 (preparing Italian/Ruy Lopez)
    {"fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3", "name": "Before Italian/Spanish"},
    
    # Italian Game position
    {"fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3", "name": "Italian Game"},
    
    # Ruy Lopez position
    {"fen": "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3", "name": "Ruy Lopez"},
    
    # Sicilian Najdorf setup
    {"fen": "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6", "name": "Sicilian Najdorf"},
    
    # Queen's Gambit
    {"fen": "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2", "name": "Queen's Gambit"},
    
    # London System
    {"fen": "rnbqkbnr/ppp1pppp/8/3p4/3P1B2/8/PPP1PPPP/RN1QKBNR b KQkq - 1 2", "name": "London System"},
]


class OpeningDatabaseBuilder:
    """Builds our opening teaching database from Lichess data"""
    
    def __init__(self, mongo_url: str, db_name: str):
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[db_name]
        self.collection = self.db.opening_knowledge
        self.rate_limit_delay = 0.5  # 500ms between requests to be safe
    
    async def fetch_from_lichess(self, fen: str) -> Optional[Dict]:
        """Fetch opening data from Lichess (with rate limiting)"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://explorer.lichess.ovh/lichess",
                    params={
                        "fen": fen,
                        "ratings": "1600,1800,2000,2200",
                        "speeds": "blitz,rapid,classical",
                    }
                )
                
                if response.status_code == 429:  # Rate limited
                    print(f"Rate limited, waiting 5 seconds...")
                    await asyncio.sleep(5)
                    return await self.fetch_from_lichess(fen)  # Retry
                
                if response.status_code != 200:
                    print(f"Lichess API error: {response.status_code}")
                    return None
                
                return response.json()
                
        except Exception as e:
            print(f"Error fetching from Lichess: {e}")
            return None
    
    def generate_teaching_for_move(
        self, 
        move_san: str, 
        move_data: Dict, 
        opening_name: str,
        fen_before: str
    ) -> str:
        """Generate teaching content for a move based on statistics"""
        
        white = move_data.get("white", 0)
        draws = move_data.get("draws", 0)
        black = move_data.get("black", 0)
        total = white + draws + black
        
        if total == 0:
            return f"{move_san} is a playable move here."
        
        # Calculate win rate
        board = chess.Board(fen_before)
        if board.turn == chess.WHITE:
            win_rate = (white + draws * 0.5) / total * 100
        else:
            win_rate = (black + draws * 0.5) / total * 100
        
        # Generate teaching based on move type and stats
        piece_moved = self._get_piece_from_move(move_san)
        
        # Popularity-based teaching
        if total > 100000:
            popularity = "This is the main line - "
        elif total > 10000:
            popularity = "A popular choice - "
        elif total > 1000:
            popularity = "A solid option - "
        else:
            popularity = ""
        
        # Piece-specific teaching
        teaching_templates = {
            "N": [
                f"{popularity}the knight heads toward the center. Knights need active squares!",
                f"{popularity}developing the knight early is key. Where do you think it's aiming?",
                f"{popularity}knights before bishops is a good principle. See how it controls the center?",
            ],
            "B": [
                f"{popularity}the bishop takes a strong diagonal. Bishops love open lines!",
                f"{popularity}developing the bishop to an active square. What does it aim at?",
                f"{popularity}bishops are strongest on long diagonals. Can you see its targets?",
            ],
            "P": [
                f"{popularity}this pawn move fights for key squares. Every pawn move is permanent!",
                f"{popularity}pawns define the structure. Think about what squares this controls.",
                f"{popularity}central pawns are powerful. This one eyes important squares.",
            ],
            "O-O": [
                f"{popularity}castling! King safety first, then attack. The rook is now connected.",
                f"{popularity}getting the king safe. Now all pieces can coordinate for battle!",
            ],
            "O-O-O": [
                f"{popularity}queenside castling - more aggressive! The rook immediately eyes the center.",
                f"{popularity}long castle! This often leads to opposite-side attacks. Exciting!",
            ],
            "Q": [
                f"{popularity}the queen enters the game. Be careful - it's powerful but can be targeted!",
                f"{popularity}early queen moves can be risky. Does this one have a good reason?",
            ],
            "R": [
                f"{popularity}rooks love open files! This one is looking for action.",
                f"{popularity}connecting the rooks or seizing a file. Rooks are endgame monsters!",
            ],
        }
        
        # Get appropriate template
        templates = teaching_templates.get(piece_moved, [
            f"{popularity}an interesting move. What do you think it's preparing?",
        ])
        
        # Use hash of move to consistently pick a template
        template_idx = hash(move_san + fen_before) % len(templates)
        base_teaching = templates[template_idx]
        
        # Add statistics insight for popular moves
        if total > 5000 and win_rate > 50:
            return f"{base_teaching} Strong players score {win_rate:.0f}% with this!"
        
        return base_teaching
    
    def _get_piece_from_move(self, san: str) -> str:
        """Extract piece type from SAN notation"""
        if san.startswith("O-O-O"):
            return "O-O-O"
        if san.startswith("O-O"):
            return "O-O"
        if san[0].isupper() and san[0] in "NBRQK":
            return san[0]
        return "P"  # Pawn move
    
    async def process_position(self, fen: str, depth: int = 0, max_depth: int = 6) -> int:
        """
        Process a position and its continuations recursively.
        Returns number of positions processed.
        """
        if depth > max_depth:
            return 0
        
        # Check if already in database
        existing = await self.collection.find_one({"fen": fen})
        if existing:
            print(f"  [skip] Already have: {existing.get('opening_name', 'Unknown')}")
            return 0
        
        # Fetch from Lichess
        await asyncio.sleep(self.rate_limit_delay)
        data = await self.fetch_from_lichess(fen)
        
        if not data:
            return 0
        
        # Extract opening info
        opening_name = ""
        eco = ""
        if data.get("opening"):
            opening_name = data["opening"].get("name", "")
            eco = data["opening"].get("eco", "")
        
        total_games = data.get("white", 0) + data.get("draws", 0) + data.get("black", 0)
        
        if total_games < 100:  # Skip rare positions
            return 0
        
        # Process moves and generate teaching
        moves_with_teaching = []
        for move_data in data.get("moves", [])[:10]:  # Top 10 moves
            san = move_data.get("san", "")
            if not san:
                continue
            
            teaching = self.generate_teaching_for_move(san, move_data, opening_name, fen)
            
            moves_with_teaching.append({
                "san": san,
                "uci": move_data.get("uci", ""),
                "white_wins": move_data.get("white", 0),
                "draws": move_data.get("draws", 0),
                "black_wins": move_data.get("black", 0),
                "total_games": move_data.get("white", 0) + move_data.get("draws", 0) + move_data.get("black", 0),
                "average_rating": move_data.get("averageRating", 0),
                "teaching": teaching,
            })
        
        # Store in database
        doc = {
            "fen": fen,
            "opening_name": opening_name,
            "eco": eco,
            "total_games": total_games,
            "moves": moves_with_teaching,
            "created_at": datetime.now(timezone.utc),
            "source": "lichess",
            "depth": depth,
        }
        
        await self.collection.insert_one(doc)
        print(f"  [new] {opening_name or 'Unknown'} ({total_games} games)")
        
        positions_processed = 1
        
        # Recursively process top continuations
        board = chess.Board(fen)
        for move_data in moves_with_teaching[:3]:  # Top 3 moves only
            try:
                move = board.parse_san(move_data["san"])
                board.push(move)
                new_fen = board.fen()
                board.pop()
                
                positions_processed += await self.process_position(new_fen, depth + 1, max_depth)
                
            except Exception as e:
                continue
        
        return positions_processed
    
    async def build_database(self, max_depth: int = 6):
        """Build the opening database from seed positions"""
        print("=" * 50)
        print("Building Opening Knowledge Database")
        print("=" * 50)
        
        total_processed = 0
        
        for seed in SEED_POSITIONS:
            print(f"\nProcessing: {seed['name']}")
            processed = await self.process_position(seed["fen"], depth=0, max_depth=max_depth)
            total_processed += processed
            print(f"  Added {processed} positions from this branch")
        
        print("\n" + "=" * 50)
        print(f"Total positions in database: {total_processed}")
        print("=" * 50)
        
        # Create index for fast lookups
        await self.collection.create_index("fen", unique=True)
        await self.collection.create_index("opening_name")
        await self.collection.create_index("eco")
    
    async def get_teaching_for_position(self, fen: str) -> Optional[Dict]:
        """Get teaching content for a position from our database"""
        return await self.collection.find_one({"fen": fen}, {"_id": 0})
    
    async def get_teaching_for_move(self, fen: str, move_san: str) -> Optional[str]:
        """Get teaching content for a specific move in a position"""
        doc = await self.collection.find_one({"fen": fen})
        if not doc:
            return None
        
        for move in doc.get("moves", []):
            if move["san"] == move_san:
                return move.get("teaching")
        
        return None


# API function to get teaching from our database
async def get_opening_teaching(fen: str, move_san: str = None) -> Dict[str, Any]:
    """
    Get opening teaching from our database.
    Falls back to basic generation if not in database.
    
    Returns:
        {
            "opening_name": str,
            "teaching": str,  # For the move or position
            "popular_moves": List[Dict],
            "from_database": bool
        }
    """
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "test_database")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    doc = await db.opening_knowledge.find_one({"fen": fen})
    
    if doc:
        result = {
            "opening_name": doc.get("opening_name", ""),
            "eco": doc.get("eco", ""),
            "total_games": doc.get("total_games", 0),
            "popular_moves": doc.get("moves", [])[:5],
            "from_database": True,
        }
        
        if move_san:
            for move in doc.get("moves", []):
                if move["san"] == move_san:
                    result["teaching"] = move.get("teaching", "")
                    break
        
        return result
    
    # Not in database - return empty
    return {
        "opening_name": "",
        "teaching": "",
        "popular_moves": [],
        "from_database": False,
    }


# CLI to build the database
if __name__ == "__main__":
    import sys
    
    async def main():
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME", "test_database")
        
        if not mongo_url:
            print("ERROR: MONGO_URL not set")
            sys.exit(1)
        
        builder = OpeningDatabaseBuilder(mongo_url, db_name)
        
        # Build with depth 6 (covers most common openings)
        await builder.build_database(max_depth=6)
    
    asyncio.run(main())
