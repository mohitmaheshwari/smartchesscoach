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

External Lichess curated puzzles were removed on 2026-04-21 — the closed-loop
vision means every training surface pulls from real games only.
"""

import random
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

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
        # We'll cache some puzzles locally for speed
        self.puzzle_cache = {}
    
    async def get_prescribed_training(
        self,
        user_id: str,
        weakness_pattern: str,
        num_puzzles: int = 5,
        rating_range: tuple = (800, 1400),
        *,
        strong_openings: Optional[set] = None,
        player_style: Optional[Dict] = None,
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

        # Enrich with personalization signals and social proof
        puzzles = self._enrich_puzzles(
            puzzles,
            weakness_pattern=weakness_pattern,
            strong_openings=strong_openings or set(),
            player_style=player_style or {},
        )

        # Difficulty ramp: obvious (big cp_loss) first, subtle last.
        # Beginners need confidence wins; advanced still benefits from ordering
        # since they'll solve the pattern recognition before the calculation.
        # Primary sort: solve_rate descending (widely-solved = well-understood = easier).
        # Secondary: cp_loss descending (obvious mistakes first within same solve rate).
        # Own puzzles (marked from_user_game=True) stay at top regardless —
        # they're the highest-priority training material.
        def _sort_key(p):
            from_own = 0 if p.get("from_user_game") else 1
            solve_rate = p.get("solve_rate") or 0.0
            cp_loss = p.get("cp_loss") or 0
            return (from_own, -solve_rate, -cp_loss)
        puzzles.sort(key=_sort_key)

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

    def _enrich_puzzles(
        self,
        puzzles: List[Dict],
        *,
        weakness_pattern: str,
        strong_openings: set,
        player_style: Dict,
    ) -> List[Dict]:
        """Annotate each puzzle with personalization + social signals.

        Adds (in-place + returned):
          - `miss_rate_text`: "40% of players at your level miss this"
          - `miss_rate_pct`: 40 (integer percent)
          - `framing_hint`: UI tag like "strong_opening" / "style_match" / None
          - `framing_text`: human-readable intro line when a hint applies

        Does NOT filter anything — these signals only tune framing/display, not
        selection (that design choice was intentional per product discussion on
        2026-04-21).
        """
        from services.player_performance import is_strong_opening

        for p in puzzles:
            # Social signal: % of players who MISS this (1 - solve_rate)
            solve_rate = p.get("solve_rate")
            if solve_rate is not None:
                miss_pct = int(round((1.0 - float(solve_rate)) * 100))
                # Cap at plausible range for display
                miss_pct = max(5, min(95, miss_pct))
                p["miss_rate_pct"] = miss_pct
                p["miss_rate_text"] = f"{miss_pct}% of players at your level miss this"

            # Framing hint: puzzle from a strong opening → acknowledge the weapon
            opening_name = p.get("opening") or p.get("opening_name") or ""
            if opening_name and is_strong_opening(opening_name, strong_openings):
                p["framing_hint"] = "strong_opening"
                p["framing_text"] = f"You know the {opening_name} well — but look at this position. What broke?"
            # Style match: attacking player's tactical puzzle → validate their strength
            elif player_style.get("is_attacking") and weakness_pattern in (
                "missed_tactic", "tactical_oversight", "calculation_depth",
            ):
                p["framing_hint"] = "style_match"
                p["framing_text"] = "Playing to your strengths — but this one's tricky. Find the best move."
            elif player_style.get("is_positional") and weakness_pattern in (
                "piece_safety", "pawn_structure", "piece_activity",
            ):
                p["framing_hint"] = "style_match"
                p["framing_text"] = "Right in your wheelhouse. What's the strongest continuation?"

        return puzzles
    
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

        # Rating-aware match: pre-2026-04-21 this filtered by a `rating` field
        # that extraction never actually stores — excluded every puzzle
        # (3,517 of them), leaving the user with at most 2 own-puzzles.
        # Fix: match by the `difficulty` field that extraction DOES store,
        # mapped to the user's rating band.
        #
        # difficulty mapping (set in puzzle_extraction_service.py based on cp_loss):
        #   cp_loss >= 400 -> "beginner"     (obvious blunders, easier to spot)
        #   cp_loss >= 200 -> "intermediate"
        #   cp_loss <  200 -> "advanced"     (subtle mistakes)
        #
        # rating-band mapping (wider nets for beginners, subtler for advanced):
        user_rating = int((rating_range[0] + rating_range[1]) / 2) if rating_range and len(rating_range) == 2 else 1200
        if user_rating < 1000:
            allowed_difficulties = ["beginner"]
        elif user_rating < 1400:
            allowed_difficulties = ["beginner", "intermediate"]
        elif user_rating < 1800:
            allowed_difficulties = ["intermediate", "advanced"]
        else:
            allowed_difficulties = ["advanced"]
        query["difficulty"] = {"$in": allowed_difficulties}

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
