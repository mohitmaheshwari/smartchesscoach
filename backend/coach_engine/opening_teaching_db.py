"""
Opening Teaching Database - Manual Curation

Since live Lichess API access is restricted in this environment,
we build our opening knowledge database with manually curated content.

This approach has advantages:
1. Higher quality teaching (written by humans, not auto-generated)
2. No external dependencies
3. Consistent, pedagogically sound content
4. Can be expanded over time

Structure:
- Each position has teaching content for common moves
- Teaching is question-based and collaborative (human coach style)
- Statistics can be added later from offline Lichess data exports
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
import chess


# Curated opening teaching database
# Format: FEN -> {opening_name, moves: [{san, teaching, explanation}]}
CURATED_OPENINGS = {
    # Starting position
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1": {
        "opening_name": "Starting Position",
        "eco": "",
        "teaching": "The game begins! White moves first. What's your plan?",
        "moves": [
            {
                "san": "e4",
                "teaching": "1.e4 - the King's Pawn opening! This controls the center and opens lines for your bishop and queen. Bobby Fischer called it 'best by test'. Ready for an open, tactical game?",
                "explanation": "Controls d5 and f5, opens diagonal for Bf1",
            },
            {
                "san": "d4",
                "teaching": "1.d4 - the Queen's Pawn! This also fights for the center but leads to slower, more strategic games. The pawn is protected by the queen. Prefer positional chess?",
                "explanation": "Controls c5 and e5, supported by Qd1",
            },
            {
                "san": "Nf3",
                "teaching": "1.Nf3 - the Reti Opening! Flexible and sneaky. You're not committing your pawns yet. What do you think this knight is eyeing?",
                "explanation": "Develops knight, controls e5 and d4 without committing pawns",
            },
            {
                "san": "c4",
                "teaching": "1.c4 - the English Opening! You're fighting for the center with a flank pawn. This often transposes to other openings. Patient and flexible!",
                "explanation": "Controls d5, prepares Nc3",
            },
        ]
    },
    
    # After 1.e4
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1": {
        "opening_name": "King's Pawn Opening",
        "eco": "B00",
        "teaching": "White played e4, grabbing the center. How will you respond?",
        "moves": [
            {
                "san": "e5",
                "teaching": "1...e5 - Fighting fire with fire! You're challenging white's center directly. This leads to open, tactical games like the Italian or Ruy Lopez. Ready for battle?",
                "explanation": "Symmetric center, leads to Open Games",
            },
            {
                "san": "c5",
                "teaching": "1...c5 - The Sicilian Defense! The most popular and aggressive response. You fight for the d4 square from the side. Black often sacrifices pawn structure for counterplay. Combative!",
                "explanation": "Fights for d4, asymmetric play, Black's sharpest weapon",
            },
            {
                "san": "e6",
                "teaching": "1...e6 - The French Defense! Solid like a fortress. You'll play d5 next and create a strong pawn chain. Your light bishop gets blocked, but your position is rock solid. Patience is key!",
                "explanation": "Prepares d5, solid structure, strategic play",
            },
            {
                "san": "c6",
                "teaching": "1...c6 - The Caro-Kann! Similar idea to the French but your bishop won't get trapped. After d5, you'll have a solid position with good piece play. Reliable and steady!",
                "explanation": "Prepares d5 with c6 support, bishop stays active",
            },
            {
                "san": "d5",
                "teaching": "1...d5 - The Scandinavian! Bold and direct - you immediately challenge the center. After exd5 Qxd5, your queen comes out early. Risky but fun!",
                "explanation": "Immediate center challenge, early queen development",
            },
            {
                "san": "Nf6",
                "teaching": "1...Nf6 - Alekhine's Defense! You're inviting white to chase your knight with pawns. As they advance, their center becomes overextended. Provocative!",
                "explanation": "Provokes e5, hypermodern approach",
            },
        ]
    },
    
    # After 1.e4 e5
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2": {
        "opening_name": "Open Game",
        "eco": "C20",
        "teaching": "Symmetric center! Both sides claim equal space. What's next?",
        "moves": [
            {
                "san": "Nf3",
                "teaching": "2.Nf3 - The most natural move! Your knight develops toward the center and attacks the e5 pawn. 'Knights before bishops' is a good principle. Where should Black defend?",
                "explanation": "Develops knight, attacks e5, most common",
            },
            {
                "san": "Nc3",
                "teaching": "2.Nc3 - The Vienna Game! You develop but don't attack e5 yet. This keeps more options open. Flexible but less forcing.",
                "explanation": "Development without attacking e5, Vienna Game",
            },
            {
                "san": "Bc4",
                "teaching": "2.Bc4 - The Bishop's Opening! Your bishop immediately eyes the f7 square - Black's weakest point. Direct and aggressive!",
                "explanation": "Targets f7, early bishop development",
            },
            {
                "san": "f4",
                "teaching": "2.f4 - The King's Gambit! You sacrifice a pawn for rapid development and attack. Bold and romantic chess! Do you dare?",
                "explanation": "Pawn sacrifice for initiative, romantic chess",
            },
        ]
    },
    
    # After 1.e4 e5 2.Nf3
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2": {
        "opening_name": "King's Knight Opening",
        "eco": "C40",
        "teaching": "The knight attacks your e5 pawn. How will you defend?",
        "moves": [
            {
                "san": "Nc6",
                "teaching": "2...Nc6 - Perfect! The knight defends e5 and develops toward the center. This is the most solid response. Now white chooses between the Italian (Bc4) or Spanish (Bb5). What's the difference?",
                "explanation": "Defends e5, develops knight, main line",
            },
            {
                "san": "Nf6",
                "teaching": "2...Nf6 - The Petrov Defense! Instead of defending e5, you counter-attack e4. If white takes your pawn, you'll take theirs. Symmetrical and solid, but a bit passive. Equal but drawish.",
                "explanation": "Counter-attack e4 instead of defending e5, Petrov",
            },
            {
                "san": "d6",
                "teaching": "2...d6 - The Philidor Defense! You defend e5 with a pawn, keeping the knight flexible. Solid but slightly passive. Named after the great 18th century master Philidor!",
                "explanation": "Pawn defense of e5, solid but passive",
            },
            {
                "san": "f5",
                "teaching": "2...f5 - The Latvian Gambit! Extremely risky! You ignore the attack on e5 and counter in the center. Most masters consider this dubious, but it's fun for blitz!",
                "explanation": "Risky gambit, ignores e5 attack",
            },
        ]
    },
    
    # After 1.e4 e5 2.Nf3 Nc6
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3": {
        "opening_name": "King's Knight Game",
        "eco": "C44",
        "teaching": "Black defended well! Now you choose your path. Italian or Spanish?",
        "moves": [
            {
                "san": "Bc4",
                "teaching": "3.Bc4 - The Italian Game! Your bishop aims at f7 - the weakest point in Black's camp (only the king guards it). Classic and direct. After Black plays Bc5 or Nf6, you'll castle and build your attack.",
                "explanation": "Italian Game, targets f7",
            },
            {
                "san": "Bb5",
                "teaching": "3.Bb5 - The Ruy Lopez (Spanish Game)! Instead of aiming at f7, you pressure the knight that defends e5. This is more sophisticated - you're playing for long-term positional advantage. The world champions' favorite!",
                "explanation": "Ruy Lopez, pressures Nc6 defender",
            },
            {
                "san": "d4",
                "teaching": "3.d4 - The Scotch Game! You immediately break open the center. After exd4 Nxd4, the position becomes very open. Direct and tactical!",
                "explanation": "Scotch Game, immediate center break",
            },
            {
                "san": "Nc3",
                "teaching": "3.Nc3 - The Three Knights or Four Knights Game! Solid development. This often leads to the Four Knights (after 3...Nf6 4.Bb5) - a solid but somewhat drawish line.",
                "explanation": "Three/Four Knights, solid development",
            },
        ]
    },
    
    # Italian Game
    "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3": {
        "opening_name": "Italian Game",
        "eco": "C50",
        "teaching": "The Italian Game! White's bishop eyes f7. How will you respond?",
        "moves": [
            {
                "san": "Bc5",
                "teaching": "3...Bc5 - The Giuoco Piano (Quiet Game)! Your bishop mirrors white's, aiming at f2. Now both sides have 'Italian bishops' pointing at weak pawns. This leads to rich middlegame play. Symmetrical but sharp!",
                "explanation": "Giuoco Piano, mirror position, rich play",
            },
            {
                "san": "Nf6",
                "teaching": "3...Nf6 - The Two Knights Defense! You develop and attack e4. This is more aggressive than Bc5. White might try the dangerous Ng5 attack or the solid d3. Ready for tactics?",
                "explanation": "Two Knights, attacks e4, aggressive",
            },
            {
                "san": "Be7",
                "teaching": "3...Be7 - The Hungarian Defense! Very solid but passive. You prepare to castle safely. Not as popular at high levels but perfectly playable.",
                "explanation": "Hungarian Defense, solid but passive",
            },
        ]
    },
    
    # Sicilian Defense
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2": {
        "opening_name": "Sicilian Defense",
        "eco": "B20",
        "teaching": "The Sicilian! Black fights for d4 from the side. The most complex opening in chess.",
        "moves": [
            {
                "san": "Nf3",
                "teaching": "2.Nf3 - The Open Sicilian begins! You develop naturally before committing to d4. This is the main line, leading to incredibly rich positions. The Najdorf, Dragon, and Scheveningen await!",
                "explanation": "Open Sicilian, natural development before d4",
            },
            {
                "san": "Nc3",
                "teaching": "2.Nc3 - The Closed Sicilian! You avoid the complications of d4. This leads to slower, more strategic games. Good if you don't want to study tons of Sicilian theory!",
                "explanation": "Closed Sicilian, avoids Open Sicilian theory",
            },
            {
                "san": "c3",
                "teaching": "2.c3 - The Alapin! You prepare d4 with pawn support. This sidesteps main line Sicilian theory but gives Black an easy game with ...d5. Simple and solid.",
                "explanation": "Alapin, prepares d4 with c3 support",
            },
            {
                "san": "d4",
                "teaching": "2.d4 - Immediate central break! After cxd4, white usually plays c3 (Smith-Morra Gambit) sacrificing a pawn for development. Aggressive!",
                "explanation": "Smith-Morra if c3 follows, immediate center break",
            },
        ]
    },
    
    # French Defense
    "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2": {
        "opening_name": "French Defense",
        "eco": "C00",
        "teaching": "The French! Black prepares d5 with a solid pawn chain.",
        "moves": [
            {
                "san": "d4",
                "teaching": "2.d4 - The main line! You establish a strong center. After 2...d5, the tension begins. Will you advance with e5 or exchange?",
                "explanation": "Main line, establishes center, prepares for d5",
            },
            {
                "san": "d3",
                "teaching": "2.d3 - The King's Indian Attack setup! You'll fianchetto your bishop and play a slower game. Avoids main line French theory.",
                "explanation": "KIA setup, avoids main line theory",
            },
        ]
    },
    
    # After 1.e4 e6 2.d4 d5
    "rnbqkbnr/ppp2ppp/4p3/3p4/3PP3/8/PPP2PPP/RNBQKBNR w KQkq - 0 3": {
        "opening_name": "French Defense",
        "eco": "C00",
        "teaching": "Classic French tension! Pawns face off in the center. What's white's plan?",
        "moves": [
            {
                "san": "e5",
                "teaching": "3.e5 - The Advance Variation! You grab space and lock the center. This leads to a strategic battle - you'll attack kingside, Black attacks queenside. A battle of plans!",
                "explanation": "Advance Variation, locks center, kingside vs queenside",
            },
            {
                "san": "Nc3",
                "teaching": "3.Nc3 - Classical French! You develop and put the question to Black's d5 pawn. Black must decide: exchange on e4 (Rubinstein), or defend with Nf6 (Classical)?",
                "explanation": "Classical French, develops and pressures d5",
            },
            {
                "san": "Nd2",
                "teaching": "3.Nd2 - The Tarrasch Variation! The knight goes to d2 instead of c3. This avoids the Winawer pin (Bb4). Solid but slightly passive.",
                "explanation": "Tarrasch, avoids Bb4 pin",
            },
            {
                "san": "exd5",
                "teaching": "3.exd5 - The Exchange Variation! You release the tension immediately. This leads to symmetric positions that can be drawish. Simple but not ambitious.",
                "explanation": "Exchange Variation, symmetric, often drawish",
            },
        ]
    },
    
    # Caro-Kann
    "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2": {
        "opening_name": "Caro-Kann Defense",
        "eco": "B10",
        "teaching": "The Caro-Kann! Black prepares d5 with c6 support. Solid as a rock!",
        "moves": [
            {
                "san": "d4",
                "teaching": "2.d4 - Main line! After d5, you have a choice: advance (e5), exchange (exd5), or develop (Nc3/Nd2). Each leads to completely different games!",
                "explanation": "Main line, prepares for d5",
            },
            {
                "san": "Nc3",
                "teaching": "2.Nc3 - The Two Knights variation! You develop before committing pawns. After d5, you might play d4 or even f4 for a sharper game.",
                "explanation": "Two Knights, flexible development",
            },
        ]
    },
    
    # Queen's Gambit
    "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2": {
        "opening_name": "Queen's Gambit",
        "eco": "D06",
        "teaching": "The Queen's Gambit! White offers a pawn. Will you accept?",
        "moves": [
            {
                "san": "dxc4",
                "teaching": "2...dxc4 - Queen's Gambit Accepted! You take the pawn but give up the center. White will easily regain the pawn. The idea is to develop quickly and hold on. Practical!",
                "explanation": "QGA, takes pawn but gives center",
            },
            {
                "san": "e6",
                "teaching": "2...e6 - Queen's Gambit Declined! You reinforce d5 with e6. Solid and classical. Your light bishop gets blocked but your position is rock solid.",
                "explanation": "QGD, solid, classical approach",
            },
            {
                "san": "c6",
                "teaching": "2...c6 - The Slav Defense! You defend d5 with c6 instead of e6. This keeps your light bishop free! Very popular at all levels.",
                "explanation": "Slav, defends d5 keeping bishop active",
            },
            {
                "san": "Nf6",
                "teaching": "2...Nf6 - Developing move! After 3.cxd5, you can recapture with the knight. This leads to various systems.",
                "explanation": "Development, flexible",
            },
        ]
    },
    
    # London System
    "rnbqkbnr/ppp1pppp/8/3p4/3P1B2/8/PPP1PPPP/RN1QKBNR b KQkq - 1 2": {
        "opening_name": "London System",
        "eco": "D02",
        "teaching": "The London System! White develops the bishop before blocking it with e3. Simple but effective.",
        "moves": [
            {
                "san": "Nf6",
                "teaching": "2...Nf6 - Natural development! You attack the empty e4 square. The London leads to solid positions for both sides.",
                "explanation": "Natural development, eyes e4",
            },
            {
                "san": "c5",
                "teaching": "2...c5 - Challenging the center immediately! You fight for d4 in Sicilian style. Active approach!",
                "explanation": "Fights for d4, Sicilian-style challenge",
            },
            {
                "san": "Bf5",
                "teaching": "2...Bf5 - Mirror image! You also develop your bishop actively before e6. This is the most popular response.",
                "explanation": "Mirror development, keeps bishop active",
            },
        ]
    },
}


class OpeningTeachingDB:
    """Our own opening teaching database - no external API needed!"""
    
    def __init__(self, mongo_url: str, db_name: str):
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[db_name]
        self.collection = self.db.opening_knowledge
    
    async def seed_database(self):
        """Seed the database with curated opening knowledge"""
        print("Seeding opening teaching database...")
        
        for fen, data in CURATED_OPENINGS.items():
            # Check if exists
            existing = await self.collection.find_one({"fen": fen})
            if existing:
                print(f"  [skip] {data['opening_name']}")
                continue
            
            # Insert
            doc = {
                "fen": fen,
                "opening_name": data["opening_name"],
                "eco": data.get("eco", ""),
                "position_teaching": data.get("teaching", ""),
                "moves": data["moves"],
                "created_at": datetime.now(timezone.utc),
                "source": "curated",
            }
            await self.collection.insert_one(doc)
            print(f"  [new] {data['opening_name']} ({len(data['moves'])} moves)")
        
        # Create indexes
        await self.collection.create_index("fen", unique=True)
        await self.collection.create_index("opening_name")
        
        count = await self.collection.count_documents({})
        print(f"\nTotal positions in database: {count}")
    
    async def get_teaching(self, fen: str, move_san: str = None) -> Dict[str, Any]:
        """
        Get teaching for a position or specific move.
        
        Returns:
            {
                "opening_name": str,
                "position_teaching": str,
                "move_teaching": str (if move_san provided),
                "move_explanation": str,
                "found": bool
            }
        """
        doc = await self.collection.find_one({"fen": fen})
        
        if not doc:
            return {
                "opening_name": "",
                "position_teaching": "",
                "move_teaching": "",
                "move_explanation": "",
                "popular_moves": [],
                "found": False,
            }
        
        result = {
            "opening_name": doc.get("opening_name", ""),
            "position_teaching": doc.get("position_teaching", ""),
            "move_teaching": "",
            "move_explanation": "",
            "popular_moves": [m["san"] for m in doc.get("moves", [])],
            "found": True,
        }
        
        # Find specific move teaching if requested
        if move_san:
            for move in doc.get("moves", []):
                if move["san"] == move_san:
                    result["move_teaching"] = move.get("teaching", "")
                    result["move_explanation"] = move.get("explanation", "")
                    break
        
        return result
    
    async def get_all_moves_teaching(self, fen: str) -> List[Dict]:
        """Get teaching for all moves in a position"""
        doc = await self.collection.find_one({"fen": fen})
        if not doc:
            return []
        return doc.get("moves", [])


# Function to use in the coach
async def get_curated_teaching(fen: str, move_san: str = None) -> Dict[str, Any]:
    """
    Get curated teaching from our database.
    Use this in the coach instead of live Lichess calls.
    """
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "test_database")
    
    db = OpeningTeachingDB(mongo_url, db_name)
    return await db.get_teaching(fen, move_san)


# Seed on import (first run only)
async def ensure_database_seeded():
    """Make sure the database is seeded"""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "test_database")
    
    db = OpeningTeachingDB(mongo_url, db_name)
    count = await db.collection.count_documents({})
    
    if count == 0:
        await db.seed_database()


if __name__ == "__main__":
    async def main():
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME", "test_database")
        
        db = OpeningTeachingDB(mongo_url, db_name)
        await db.seed_database()
        
        # Test
        print("\n=== Testing ===")
        result = await db.get_teaching(
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "c5"
        )
        print(f"Opening: {result['opening_name']}")
        print(f"Move teaching for c5: {result['move_teaching']}")
    
    asyncio.run(main())
