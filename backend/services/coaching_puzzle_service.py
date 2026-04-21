"""
Coaching Puzzle Service - Prescribe training based on diagnosed weaknesses

This is the IMPROVEMENT engine:
1. Take user's diagnosed weaknesses (from pattern detection)
2. Surface puzzles from REAL games — user's own first, then community
3. Present with COACHING context — not just "solve this" but "here's WHY"
4. Track solve rate and connect back to improvement

Puzzle sources (product vision: closed-loop coaching, no external curation):
1. User's OWN games (positions where THEY made mistakes)
2. Community patterns (OTHER users' mistakes, rating-filtered)

Note: external Lichess curated puzzles were used pre-2026-04-21 as a fallback
when the community pool was thin. That's been removed — every training
surface now uses real games only. The `_get_lichess_puzzles` method below is
deprecated but kept so its dependencies don't break on import.
"""

import random
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# aiohttp is only needed by the deprecated Lichess fetcher. Keep the import
# optional so removing the aiohttp dependency doesn't break this module.
try:
    import aiohttp  # noqa: F401
except ImportError:
    aiohttp = None

logger = logging.getLogger(__name__)

# Map our weakness patterns to Lichess puzzle themes
# Lichess themes: https://lichess.org/training/themes
WEAKNESS_TO_PUZZLE_THEMES = {
    # Our pattern -> Lichess themes
    "missed_threat": ["hangingPiece", "trappedPiece", "defensiveMove"],
    "poor_piece_safety": ["hangingPiece", "trappedPiece", "skewer", "pin"],
    "tactical_blindness": ["fork", "discoveredAttack", "doubleCheck", "xRayAttack"],
    "failed_conversion": ["endgame", "queenEndgame", "rookEndgame", "pawnEndgame"],
    "positional_drift": ["quietMove", "zugzwang", "deflection"],
    "opening_inaccuracy": ["opening", "advancedPawn"],
    "time_trouble": ["short", "oneMove", "veryLong"],  # Quick puzzles for time trouble
    "missed_fork": ["fork", "knightEndgame"],
    "missed_pin": ["pin", "skewer"],
    "missed_discovery": ["discoveredAttack", "doubleCheck"],
    "back_rank": ["backRankMate", "mateIn1", "mateIn2"],
    "king_safety": ["kingsideAttack", "queensideAttack", "attackingF2F7"],
    "material_blunder": ["hangingPiece", "equality", "advantage"],
    "calculation_error": ["long", "veryLong"],  # Longer calculation puzzles
}

# Coaching context for each theme
THEME_COACHING_CONTEXT = {
    "hangingPiece": {
        "lesson": "Piece Safety",
        "what_to_look_for": "Before each move, scan the board: is any of my pieces undefended?",
        "why_this_matters": "You've been leaving pieces hanging. This drill trains you to spot undefended pieces."
    },
    "fork": {
        "lesson": "Double Attacks",
        "what_to_look_for": "Knights are fork masters. Look for squares where one piece can attack two targets.",
        "why_this_matters": "You've missed forks in your games. This trains your pattern recognition."
    },
    "pin": {
        "lesson": "Pinned Pieces",
        "what_to_look_for": "A pinned piece can't move without exposing a more valuable piece behind it.",
        "why_this_matters": "You've missed pins. Learn to spot pieces lined up on diagonals and files."
    },
    "discoveredAttack": {
        "lesson": "Discovered Attacks",
        "what_to_look_for": "Moving one piece reveals an attack from another. Double trouble!",
        "why_this_matters": "These are sneaky. Training helps you see the hidden attacker."
    },
    "backRankMate": {
        "lesson": "Back Rank Safety",
        "what_to_look_for": "Is your king trapped on the back rank? Can a rook or queen deliver mate?",
        "why_this_matters": "You've been vulnerable to back rank threats. Always have an escape square."
    },
    "defensiveMove": {
        "lesson": "Defensive Awareness",
        "what_to_look_for": "Before attacking, ask: what is my opponent threatening RIGHT NOW?",
        "why_this_matters": "You've missed opponent threats. This trains defensive vision."
    },
    "trappedPiece": {
        "lesson": "Trapped Pieces",
        "what_to_look_for": "A piece with no escape squares is a target. Don't let your pieces get cornered.",
        "why_this_matters": "You've had pieces trapped. Learn to keep escape routes open."
    },
    "endgame": {
        "lesson": "Endgame Technique",
        "what_to_look_for": "In endgames, king activity and pawn promotion are everything.",
        "why_this_matters": "You've struggled to convert winning positions. Endgame training is key."
    },
    "mateIn1": {
        "lesson": "Checkmate Patterns",
        "what_to_look_for": "The king has no escape AND no piece can block. That's mate!",
        "why_this_matters": "Quick mate puzzles sharpen your tactical vision."
    },
    "mateIn2": {
        "lesson": "Two-Move Checkmates",
        "what_to_look_for": "Find the forcing move that leads to unavoidable mate.",
        "why_this_matters": "Calculating two moves ahead is essential for improvement."
    },
}

# Default coaching for themes without specific context
DEFAULT_COACHING = {
    "lesson": "Tactical Training",
    "what_to_look_for": "Look for forcing moves: checks, captures, threats.",
    "why_this_matters": "Regular puzzle practice builds pattern recognition."
}


class CoachingPuzzleService:
    """
    Service to fetch and present puzzles with coaching context.
    """
    
    def __init__(self, db):
        self.db = db
        self.lichess_api_base = "https://lichess.org/api"
        # We'll cache some puzzles locally for speed
        self.puzzle_cache = {}
    
    async def get_prescribed_training(
        self,
        user_id: str,
        weakness_pattern: str,
        num_puzzles: int = 5,
        rating_range: tuple = (800, 1400)
    ) -> Dict[str, Any]:
        """
        Get a set of puzzles prescribed for a specific weakness.
        
        Returns puzzles with coaching context explaining WHY each puzzle
        is relevant to the user's weakness.
        """
        # Map weakness to Lichess themes (still used for coaching-intro copy only)
        themes = WEAKNESS_TO_PUZZLE_THEMES.get(weakness_pattern, ["short"])

        # Product vision: training material comes from REAL games, not external
        # curated puzzles. Sources, in priority order:
        #   1. User's own mistakes (extracted from their analyzed games)
        #   2. Community puzzles — OTHER users' mistakes matching this weakness,
        #      rating-filtered to the user's band
        # No Lichess curated fallback. If the pool is thin, we surface less —
        # and the frontend can prompt for game import.
        puzzles = []

        # Source 1: User's own mistakes (most relevant!)
        user_puzzles = await self._get_puzzles_from_user_games(
            user_id, weakness_pattern, limit=2
        )
        puzzles.extend(user_puzzles)

        # Source 2: Community puzzles from other users' games, rating-filtered
        remaining = num_puzzles - len(puzzles)
        if remaining > 0:
            community_puzzles = await self._get_community_puzzles(
                user_id=user_id,
                weakness_pattern=weakness_pattern,
                rating_range=rating_range,
                limit=remaining,
            )
            puzzles.extend(community_puzzles)

        # Add coaching context to each puzzle
        for puzzle in puzzles:
            puzzle["coaching"] = self._get_coaching_context(
                puzzle, weakness_pattern
            )

        # Get the main theme coaching
        primary_theme = themes[0] if themes else "short"
        theme_coaching = THEME_COACHING_CONTEXT.get(primary_theme, DEFAULT_COACHING)

        return {
            "weakness": weakness_pattern,
            "theme": primary_theme,
            "coaching_intro": theme_coaching,
            "puzzles": puzzles,
            "total": len(puzzles),
            # Empty-state hint for the frontend: if pool is thin, show import prompt
            "pool_thin": len(puzzles) < num_puzzles,
            "prescription": {
                "daily_goal": num_puzzles,
                "focus": theme_coaching["what_to_look_for"],
                "duration": "Do these puzzles daily for 1 week"
            }
        }
    
    async def _get_puzzles_from_user_games(
        self,
        user_id: str,
        weakness_pattern: str,
        limit: int = 3
    ) -> List[Dict]:
        """
        Create puzzles from user's OWN games where they made this type of mistake.
        
        This is the most powerful training - solving positions from your own games!
        """
        puzzles = []
        
        # Find games where user had this weakness
        games = await self.db.game_analyses.find({
            "user_id": user_id,
            "stockfish_analysis.move_evaluations": {
                "$elemMatch": {
                    "cp_loss": {"$gte": 100}  # Significant mistakes
                }
            }
        }).sort("analyzed_at", -1).limit(20).to_list(length=20)
        
        for game in games:
            sf = game.get("stockfish_analysis", {})
            for move in sf.get("move_evaluations", []):
                cp_loss = abs(move.get("cp_loss", 0))
                threat = move.get("threat", "")
                
                # Check if this move matches the weakness pattern
                if cp_loss >= 100 and self._move_matches_weakness(move, weakness_pattern):
                    # Get UCI moves for arrows
                    your_move_uci = move.get("move_uci", "")
                    best_move_san = move.get("best_move", "")
                    best_move_uci = ""
                    
                    # Try to convert best move SAN to UCI
                    try:
                        import chess
                        fen = move.get("fen_before")
                        if fen and best_move_san:
                            board = chess.Board(fen)
                            chess_move = board.parse_san(best_move_san)
                            best_move_uci = chess_move.uci()
                    except Exception as e:
                        logger.warning(f"Could not convert {best_move_san} to UCI: {e}")
                    
                    puzzle = {
                        "source": "your_game",
                        "game_id": game.get("game_id"),
                        "fen": move.get("fen_before"),
                        "solution": [best_move_uci] if best_move_uci else [best_move_san],
                        "solution_san": best_move_san,
                        "your_move": move.get("move"),
                        "your_move_uci": your_move_uci,
                        "threat": threat,
                        "cp_loss": cp_loss,
                        "move_number": move.get("move_number"),
                        "rating": None,  # From your game, not rated
                        "themes": [weakness_pattern],
                        "context": f"From your game - you played {move.get('move')} but {best_move_san} was better"
                    }
                    puzzles.append(puzzle)
                    
                    if len(puzzles) >= limit:
                        break
            
            if len(puzzles) >= limit:
                break
        
        return puzzles
    
    async def _get_community_puzzles(
        self,
        user_id: str,
        weakness_pattern: str,
        rating_range: tuple,
        limit: int,
    ) -> List[Dict]:
        """Fetch puzzles extracted from OTHER users' games matching this weakness.

        Puzzles live in the `community_puzzles` collection (shared_by ≠ user_id).
        Filtered by the user's rating band so a 900-rated player doesn't get
        puzzles pulled from 1800-rated players' games.

        Also excludes puzzles this user already attempted correctly.
        """
        if limit <= 0:
            return []

        # Which puzzle ids has this user already solved?
        solved_ids: set = set()
        try:
            async for attempt in self.db.puzzle_attempts.find(
                {"user_id": user_id, "correct": True},
                {"_id": 0, "puzzle_id": 1},
            ):
                pid = attempt.get("puzzle_id")
                if pid:
                    solved_ids.add(pid)
        except Exception:
            pass

        # Query community_puzzles — other users' mistakes for this weakness.
        # `issue_type` is the stored cognitive-gap tag used by the extractor.
        query = {
            "issue_type": weakness_pattern,
            "shared_by": {"$ne": user_id},  # not this user's own puzzles
        }
        # Rating filter (puzzle's rating field = rating of the user whose game
        # it came from). Wide-ish net if rating_range is missing.
        if rating_range and len(rating_range) == 2:
            query["rating"] = {"$gte": rating_range[0], "$lte": rating_range[1]}

        puzzles: List[Dict] = []
        try:
            cursor = self.db.community_puzzles.find(query, {"_id": 0}).sort(
                "solve_rate", -1
            ).limit(limit * 3)  # overfetch — we'll drop already-solved
            async for p in cursor:
                if p.get("puzzle_id") in solved_ids:
                    continue
                puzzles.append(p)
                if len(puzzles) >= limit:
                    break
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"community puzzle fetch failed: {e}"
            )

        return puzzles

    def _move_matches_weakness(self, move: Dict, weakness_pattern: str) -> bool:
        """Check if a move's mistake type matches the weakness pattern."""
        threat = move.get("threat", "").lower()
        best_move = move.get("best_move", "")
        cp_loss = abs(move.get("cp_loss", 0))
        
        if weakness_pattern == "missed_threat":
            return bool(threat)  # Has a threat that was missed
        elif weakness_pattern == "poor_piece_safety":
            return "x" in best_move.lower()  # Best move was a capture (piece was hanging)
        elif weakness_pattern == "tactical_blindness":
            return cp_loss >= 200  # Big tactical miss
        elif weakness_pattern == "back_rank":
            return "+" in threat or "#" in threat  # Check threat
        
        return True  # Default: include
    
    async def _get_lichess_puzzles(
        self,
        themes: List[str],
        rating_range: tuple,
        limit: int
    ) -> List[Dict]:
        """
        Fetch puzzles from Lichess API or local cache.
        
        For now, we'll use the Lichess puzzle API to get daily puzzles
        and filter by theme from our local sample.
        """
        puzzles = []
        
        # Try to get puzzle of the day from Lichess
        try:
            async with aiohttp.ClientSession() as session:
                # Get daily puzzle
                async with session.get(f"{self.lichess_api_base}/puzzle/daily") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        puzzle = self._format_lichess_puzzle(data.get("puzzle", {}), data.get("game", {}))
                        if puzzle:
                            puzzles.append(puzzle)
        except Exception as e:
            logger.error(f"Error fetching Lichess puzzle: {e}")
        
        # Add from our curated puzzle samples
        # In production, we'd query a local copy of the Lichess puzzle DB
        sample_puzzles = self._get_sample_puzzles_by_theme(themes, rating_range, limit - len(puzzles))
        puzzles.extend(sample_puzzles)
        
        return puzzles
    
    def _format_lichess_puzzle(self, puzzle: Dict, game: Dict) -> Optional[Dict]:
        """Format a Lichess API puzzle response."""
        if not puzzle:
            return None
        
        # Lichess doesn't return FEN directly - we need to extract from PGN
        # For now, skip the daily puzzle if we can't get FEN
        # In production, we'd parse the PGN to get the position
        
        puzzle_id = puzzle.get("id")
        solution = puzzle.get("solution", [])
        rating = puzzle.get("rating", 1200)
        themes = puzzle.get("themes", [])
        
        # We'll use a placeholder for now - in production we'd parse PGN
        # The sample puzzles have FEN so they'll work
        return {
            "source": "lichess_daily",
            "puzzle_id": puzzle_id,
            "fen": None,  # Would need PGN parsing
            "solution": solution,
            "rating": rating,
            "themes": themes,
            "game_url": f"https://lichess.org/training/{puzzle_id}",
            "context": "Daily puzzle from Lichess - solve at lichess.org/training"
        }
    
    def _get_sample_puzzles_by_theme(
        self,
        themes: List[str],
        rating_range: tuple,
        limit: int
    ) -> List[Dict]:
        """
        Get sample puzzles by theme.
        
        In production, this would query a local SQLite/Postgres copy of 
        the Lichess puzzle database. For now, we'll return curated samples.
        """
        # Curated puzzle samples by theme
        # These are real Lichess puzzles that teach specific concepts
        SAMPLE_PUZZLES = {
            "hangingPiece": [
                {
                    "puzzle_id": "sample_hang_1",
                    "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
                    "solution": ["Qxf7"],
                    "rating": 800,
                    "themes": ["hangingPiece", "mateIn1"],
                    "context": "Black's f7 pawn is only defended by the king. Scholar's Mate pattern!"
                },
                {
                    "puzzle_id": "sample_hang_2",
                    "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
                    "solution": ["Nf6"],
                    "rating": 900,
                    "themes": ["hangingPiece", "development"],
                    "context": "Develop while defending. The knight on f6 defends the e4 threat."
                }
            ],
            "fork": [
                {
                    "puzzle_id": "sample_fork_1",
                    "fen": "r1bqkb1r/pppp1ppp/2n2n2/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                    "solution": ["Bxc6", "dxc6"],
                    "rating": 1000,
                    "themes": ["fork", "opening"],
                    "context": "After Bxc6, White gets a pawn and damages Black's structure."
                },
                {
                    "puzzle_id": "sample_fork_2",
                    "fen": "r1bqkbnr/ppp2ppp/2np4/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4",
                    "solution": ["Ng5"],
                    "rating": 1100,
                    "themes": ["fork", "attackingF2F7"],
                    "context": "Knight attacks f7 (weak square) and threatens fork patterns."
                }
            ],
            "pin": [
                {
                    "puzzle_id": "sample_pin_1",
                    "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 2 5",
                    "solution": ["Bg5"],
                    "rating": 1000,
                    "themes": ["pin"],
                    "context": "Pin the knight to the queen! It can't move without losing the queen."
                }
            ],
            "defensiveMove": [
                {
                    "puzzle_id": "sample_def_1",
                    "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 5 4",
                    "solution": ["g6"],
                    "rating": 900,
                    "themes": ["defensiveMove"],
                    "context": "Defend f7! The queen threatens mate. g6 blocks the attack."
                }
            ],
            "backRankMate": [
                {
                    "puzzle_id": "sample_back_1",
                    "fen": "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1",
                    "solution": ["Ra8"],
                    "rating": 800,
                    "themes": ["backRankMate", "mateIn1"],
                    "context": "Classic back rank mate! The king has no escape square."
                }
            ],
            "discoveredAttack": [
                {
                    "puzzle_id": "sample_disc_1",
                    "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3",
                    "solution": ["Ng5"],
                    "rating": 1100,
                    "themes": ["discoveredAttack"],
                    "context": "Moving the knight discovers an attack on e5 by the queen."
                }
            ]
        }
        
        # Collect puzzles matching the requested themes
        matching = []
        for theme in themes:
            if theme in SAMPLE_PUZZLES:
                for p in SAMPLE_PUZZLES[theme]:
                    if rating_range[0] <= p.get("rating", 1000) <= rating_range[1]:
                        p["source"] = "curated"
                        matching.append(p)
        
        # Shuffle and limit
        random.shuffle(matching)
        return matching[:limit]
    
    def _get_coaching_context(self, puzzle: Dict, weakness_pattern: str) -> Dict:
        """
        Add coaching context to a puzzle.
        
        This is what makes it COACHING, not just puzzles.
        """
        themes = puzzle.get("themes", [])
        
        # Get coaching for the primary theme
        for theme in themes:
            if theme in THEME_COACHING_CONTEXT:
                coaching = THEME_COACHING_CONTEXT[theme].copy()
                break
        else:
            coaching = DEFAULT_COACHING.copy()
        
        # Add puzzle-specific context
        if puzzle.get("source") == "your_game":
            coaching["personal_note"] = f"This is from YOUR game. You played {puzzle.get('your_move')} but the correct move was {puzzle.get('solution_san')}."
            if puzzle.get("threat"):
                coaching["what_you_missed"] = f"You missed the threat: {puzzle.get('threat')}"
        
        return coaching
    
    async def record_puzzle_attempt(
        self,
        user_id: str,
        puzzle_id: str,
        solved: bool,
        time_taken: int,
        weakness_pattern: str
    ) -> Dict:
        """
        Record a puzzle attempt and update user's progress.
        """
        attempt = {
            "user_id": user_id,
            "puzzle_id": puzzle_id,
            "weakness_pattern": weakness_pattern,
            "solved": solved,
            "time_taken": time_taken,
            "attempted_at": datetime.utcnow()
        }
        
        await self.db.puzzle_attempts.insert_one(attempt)
        
        # Update solve rate for this weakness
        stats = await self._get_weakness_solve_rate(user_id, weakness_pattern)
        
        return {
            "recorded": True,
            "stats": stats
        }
    
    async def _get_weakness_solve_rate(self, user_id: str, weakness_pattern: str) -> Dict:
        """Get solve rate for a specific weakness pattern."""
        pipeline = [
            {"$match": {"user_id": user_id, "weakness_pattern": weakness_pattern}},
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "solved": {"$sum": {"$cond": ["$solved", 1, 0]}},
                "avg_time": {"$avg": "$time_taken"}
            }}
        ]
        
        result = await self.db.puzzle_attempts.aggregate(pipeline).to_list(1)
        
        if result:
            r = result[0]
            return {
                "total_attempts": r["total"],
                "solved": r["solved"],
                "solve_rate": round(r["solved"] / r["total"] * 100, 1) if r["total"] > 0 else 0,
                "avg_time_seconds": round(r["avg_time"], 1) if r["avg_time"] else None
            }
        
        return {"total_attempts": 0, "solved": 0, "solve_rate": 0}
    
    async def get_weekly_training_plan(self, user_id: str) -> Dict:
        """
        Generate a weekly training plan based on user's top weaknesses.
        
        This is what a human coach does:
        "This week, focus on: piece safety (Mon-Wed) and forks (Thu-Sat)"
        """
        # Get user's top weaknesses from recent games
        # (We'd normally get this from the home-intelligence service)
        
        # For now, create a sample plan structure
        return {
            "week_of": datetime.utcnow().strftime("%Y-%m-%d"),
            "focus_areas": [
                {
                    "weakness": "missed_threat",
                    "days": ["Monday", "Tuesday", "Wednesday"],
                    "daily_puzzles": 5,
                    "theme": "defensiveMove"
                },
                {
                    "weakness": "tactical_blindness", 
                    "days": ["Thursday", "Friday", "Saturday"],
                    "daily_puzzles": 5,
                    "theme": "fork"
                }
            ],
            "rest_day": "Sunday",
            "goal": "Complete 30 puzzles this week with 70%+ accuracy"
        }
