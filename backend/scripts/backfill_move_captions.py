#!/usr/bin/env python3
"""
Backfill Move Teaching Captions
Regenerates Stockfish-based teaching captions for all existing training data
"""

import os
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from services.move_teaching_template import build_move_caption
import chess
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = None


def get_stockfish_analysis(position_fen: str, depth: int = 20) -> dict:
    """Query Stockfish for analysis"""
    try:
        result = subprocess.run(
            ['/usr/games/stockfish'],
            input=f"position fen {position_fen}\ngo depth {depth}\n",
            capture_output=True,
            text=True,
            timeout=10
        )

        output = result.stdout
        best_move = None
        evaluation = None
        best_line = None

        for line in output.split('\n'):
            if 'bestmove ' in line:
                parts = line.split('bestmove ')
                if len(parts) > 1:
                    best_move = parts[1].split()[0]

            if 'depth 20' in line and 'score cp' in line:
                if 'pv ' in line:
                    pv_parts = line.split('pv ')
                    if len(pv_parts) > 1:
                        best_line = pv_parts[1].strip()

                if 'cp ' in line:
                    cp_parts = line.split('cp ')
                    if len(cp_parts) > 1:
                        try:
                            evaluation = int(cp_parts[1].split()[0])
                        except:
                            pass

        return {
            'best_move': best_move,
            'evaluation': evaluation,
            'best_line': best_line
        }

    except Exception as e:
        logger.error(f"Stockfish error: {e}")
        return {'best_move': None, 'evaluation': None, 'best_line': None}


async def backfill_community_puzzles():
    """
    Backfill captions for all community puzzles.
    For each puzzle, regenerate the teaching caption based on Stockfish analysis.
    """
    logger.info("Starting backfill of community puzzle captions...")

    puzzles = await db.community_puzzles.find({}).to_list(None)
    logger.info(f"Found {len(puzzles)} community puzzles")

    for idx, puzzle in enumerate(puzzles, 1):
        try:
            puzzle_id = puzzle.get('_id')
            fen = puzzle.get('fen')
            best_move_san = puzzle.get('best_move_san')

            if not fen or not best_move_san:
                logger.warning(f"Puzzle {idx}: Missing FEN or best_move_san, skipping")
                continue

            # Analyze the position
            board = chess.Board(fen)

            # Get analysis for best move position
            try:
                board.push_san(best_move_san)
            except:
                logger.warning(f"Puzzle {idx}: Invalid best_move_san '{best_move_san}'")
                continue

            best_eval = get_stockfish_analysis(board.fen())

            # Get analysis for current position (any move)
            board = chess.Board(fen)
            current_eval = get_stockfish_analysis(board.fen())

            # Build caption for the best move
            caption = build_move_caption(
                user_move="?",  # Unknown what user played
                best_move=best_move_san,
                your_eval=current_eval['evaluation'] or 0,
                best_eval=best_eval['evaluation'] or 0,
                best_line=best_eval['best_line'],
                user_rating=1500  # Default rating
            )

            # Store teaching caption in puzzle
            await db.community_puzzles.update_one(
                {'_id': puzzle_id},
                {
                    '$set': {
                        'teaching_caption': caption['analysis'],
                        'teaching_headline': caption['headline'],
                        'cp_loss': caption['cp_loss'],
                        'best_plan': caption['best_plan'],
                        'backfilled_at': asyncio.get_event_loop().time()
                    }
                }
            )

            if idx % 20 == 0:
                logger.info(f"Backfilled {idx}/{len(puzzles)} puzzles")

        except Exception as e:
            logger.error(f"Error backfilling puzzle {idx}: {e}")
            continue

    logger.info(f"Backfill complete! Processed {len(puzzles)} puzzles")


async def backfill_training_modules():
    """
    Backfill captions for all training modules.
    Similar to puzzles but for structured modules.
    """
    logger.info("Starting backfill of training module captions...")

    modules = await db.training_plans.find({}).to_list(None)
    logger.info(f"Found {len(modules)} training modules")

    # This is a placeholder - implement based on your training module structure
    logger.info("Training module backfill not yet implemented")


async def main():
    """Run all backfill operations"""
    global db

    # Connect to MongoDB
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'test_database')

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    logger.info(f"Connected to {db_name}")

    # Run backfill operations
    await backfill_community_puzzles()
    await backfill_training_modules()

    logger.info("All backfill operations complete")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
