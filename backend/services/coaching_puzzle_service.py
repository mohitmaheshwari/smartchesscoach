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
# Includes BOTH legacy weakness names and the canonical CLAUDE.md
# cognitive_gap taxonomy so the picker can serve either.
WEAKNESS_TO_PUZZLE_THEMES = {
    # ── Canonical cognitive_gap names (what the Mirror produces) ──
    "piece_safety":       ["hangingPiece", "trappedPiece", "capturingDefender"],
    "king_safety":        ["kingsideAttack", "queensideAttack", "attackingF2F7",
                           "exposedKing", "defensiveMove"],
    "tactical_oversight": ["fork", "pin", "skewer", "discoveredAttack",
                           "deflection", "removeTheDefender", "xRayAttack",
                           "interference", "attraction"],
    "missed_tactic":      ["fork", "pin", "skewer", "discoveredAttack",
                           "deflection", "mateIn2", "mateIn3"],
    "calculation_depth":  ["long", "veryLong", "intermezzo", "quietMove",
                           "sacrifice", "mateIn3", "mateIn4"],
    "ignore_threat":      ["hangingPiece", "defensiveMove", "trappedPiece",
                           "attackingF2F7"],
    "endgame_technique":  ["endgame", "pawnEndgame", "rookEndgame",
                           "queenEndgame", "knightEndgame", "bishopEndgame",
                           "queenRookEndgame"],
    "opening_knowledge":  ["opening"],
    # piece_activity, pawn_structure, time_pressure — no clean Lichess
    # theme support, intentionally absent. Picker falls back to community
    # puzzles or own-game positions for these.

    # ── Legacy weakness names (kept for back-compat with older callers) ──
    "missed_threat": ["hangingPiece", "trappedPiece", "defensiveMove"],
    "poor_piece_safety": ["hangingPiece", "trappedPiece", "skewer", "pin"],
    "tactical_blindness": ["fork", "discoveredAttack", "doubleCheck", "xRayAttack"],
    "failed_conversion": ["endgame", "queenEndgame", "rookEndgame", "pawnEndgame"],
    "positional_drift": ["quietMove", "zugzwang", "deflection"],
    "opening_inaccuracy": ["opening", "advancedPawn"],
    "time_trouble": ["short", "oneMove", "veryLong"],
    "missed_fork": ["fork", "knightEndgame"],
    "missed_pin": ["pin", "skewer"],
    "missed_discovery": ["discoveredAttack", "doubleCheck"],
    "back_rank": ["backRankMate", "mateIn1", "mateIn2"],
    "material_blunder": ["hangingPiece", "equality", "advantage"],
    "calculation_error": ["long", "veryLong"],
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


# Map the weakness names used in the UI / decay model to the `pattern_type`
# tags stored on `community_training_positions` (the big V5-extracted pool,
# ~3.7k positions at time of writing). Prior loader queried `community_puzzles`
# which only held ~100 positions — a 30x smaller parallel pool.
WEAKNESS_TO_PATTERN_TYPES = {
    "calculation_depth":  ["calculation_depth", "short_calculation"],
    "tactical_oversight": ["tactical_miss", "fork", "pin", "skewer", "discovered_attack"],
    "missed_tactic":      ["fork", "pin", "skewer", "tactical_miss", "discovered_attack"],
    "piece_safety":       ["hanging_piece", "trapped_piece"],
    "king_safety":        ["checkmate_pattern", "back_rank"],
    "pawn_structure":     ["positional"],
    "piece_activity":     ["positional"],
    "opening_knowledge":  ["positional"],
    "endgame_technique":  ["positional"],
    "time_pressure":      ["tactical_miss", "hanging_piece"],
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
        num_puzzles: int = 10,
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
        #   2. Community positions — OTHER users' mistakes matching this
        #      weakness, rating-filtered to the user's band
        # Both sources share a single `puzzle_id`/`position_id` format
        # (`{game_id}_m{move_number}`) so the solved-filter works uniformly.
        puzzles = []

        # Pre-fetch ids the user has already solved (any source). Reused by
        # both fetchers below so a solved puzzle never re-appears regardless
        # of which path surfaces it.
        solved_ids = await self._get_solved_ids(user_id)

        # Source 1: user's own mistakes — cap at 40% of the session so other
        # sources still show up even when a user has many own-puzzles.
        own_limit = max(2, (num_puzzles * 2) // 5)
        user_puzzles = await self._get_puzzles_from_user_games(
            user_id, weakness_pattern, limit=own_limit, solved_ids=solved_ids
        )
        puzzles.extend(user_puzzles)

        # Source 2: community positions from other users' games — reserve
        # ~20% of the session for these. Same-rating-band peer mistakes
        # carry a social signal Lichess doesn't ("another 1200 missed
        # this") and connect users on the platform. When the community
        # pool is thin for this gap, unused slots cascade to Lichess
        # below — no wasted budget.
        community_limit = max(1, num_puzzles // 5)
        community_puzzles = await self._get_community_puzzles(
            user_id=user_id,
            weakness_pattern=weakness_pattern,
            rating_range=rating_range,
            limit=community_limit,
            solved_ids=solved_ids,
        )
        puzzles.extend(community_puzzles)

        # Source 3: Lichess puzzle DB — theme-matched, rating-banded,
        # 4M+ verified puzzles. Fills whatever own + community didn't
        # cover. Serves the bulk of the prescription.
        remaining = num_puzzles - len(puzzles)
        if remaining > 0:
            lichess_puzzles = await self._get_lichess_puzzles(
                user_id=user_id,
                weakness_pattern=weakness_pattern,
                rating_range=rating_range,
                limit=remaining,
                solved_ids=solved_ids,
            )
            puzzles.extend(lichess_puzzles)

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
    
    async def _get_solved_ids(self, user_id: str) -> set:
        """Puzzle ids the user has already solved correctly, across all sources.

        Reads `puzzle_attempts` — the collection the prescribed-training
        frontend writes on each correct solve (via /api/training/puzzle-attempt).
        """
        ids: set = set()
        try:
            async for a in self.db.puzzle_attempts.find(
                {"user_id": user_id, "correct": True},
                {"_id": 0, "puzzle_id": 1},
            ):
                pid = a.get("puzzle_id")
                if pid:
                    ids.add(pid)
        except Exception as e:
            logger.warning(f"solved-ids fetch failed for {user_id}: {e}")
        return ids

    async def _get_puzzles_from_user_games(
        self,
        user_id: str,
        weakness_pattern: str,
        limit: int = 3,
        solved_ids: Optional[set] = None,
    ) -> List[Dict]:
        """
        Create puzzles from user's OWN games where they made this type of mistake.

        This is the most powerful training - solving positions from your own games!
        """
        puzzles = []
        solved_ids = solved_ids if solved_ids is not None else await self._get_solved_ids(user_id)
        
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
                    # Stable id — same format as community_training_positions
                    # so the solved-filter works across both puzzle sources.
                    move_number = move.get("move_number")
                    puzzle_id = f"{game.get('game_id')}_m{move_number}" if move_number else None
                    if puzzle_id and puzzle_id in solved_ids:
                        continue

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
                    
                    # Provenance line — shown BEFORE the user solves, so it must
                    # NOT reveal the solution (which it previously did — "but
                    # Bxe4 was better" was a blatant spoiler). Instead: name
                    # the source game and hint that a better move existed,
                    # without naming it. The solution + your-move comparison
                    # lives in the post-solve feedback panel.
                    prefix = (
                        f"From your own game — move {move_number}"
                        if move_number
                        else "From your own game"
                    )
                    context_line = (
                        f"{prefix}, you had a sharper move available than the one you played."
                    )

                    puzzle = {
                        "puzzle_id": puzzle_id,
                        "source": "your_game",
                        "game_id": game.get("game_id"),
                        "fen": move.get("fen_before"),
                        "solution": [best_move_uci] if best_move_uci else [best_move_san],
                        "solution_san": best_move_san,
                        "your_move": move.get("move"),
                        "your_move_uci": your_move_uci,
                        "threat": threat,
                        "cp_loss": cp_loss,
                        "move_number": move_number,
                        "rating": None,  # From your game, not rated
                        "themes": [weakness_pattern],
                        "context": context_line,
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
        solved_ids: Optional[set] = None,
    ) -> List[Dict]:
        """Fetch positions extracted from OTHER users' games matching this weakness.

        Reads `community_training_positions` — the V5-decryption-driven pool
        (~3.7k rows in prod). Filters:
          - `source_user_id != user_id`
          - `pattern_type` ∈ mapped types for this weakness
          - `source_user_rating` within ±200 of the user's rating; widens to
            the full pool if the narrow band is thin
          - already-solved `position_id`s excluded
        """
        if limit <= 0:
            return []

        solved_ids = solved_ids if solved_ids is not None else await self._get_solved_ids(user_id)

        pattern_types = WEAKNESS_TO_PATTERN_TYPES.get(weakness_pattern, [weakness_pattern])
        user_rating = int((rating_range[0] + rating_range[1]) / 2) if rating_range and len(rating_range) == 2 else 1200
        narrow_low, narrow_high = user_rating - 200, user_rating + 200

        base_query = {
            "source_user_id": {"$ne": user_id},
            "pattern_type": {"$in": pattern_types},
        }
        if solved_ids:
            base_query["position_id"] = {"$nin": list(solved_ids)}

        collected: List[Dict] = []
        seen_ids: set = set()

        async def _collect(query: Dict, remaining: int) -> None:
            if remaining <= 0:
                return
            try:
                cursor = self.db.community_training_positions.find(
                    query, {"_id": 0}
                ).sort("solve_rate", -1).limit(remaining * 2)
                async for p in cursor:
                    pid = p.get("position_id")
                    if not pid or pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    collected.append(p)
                    if len(collected) >= limit:
                        return
            except Exception as e:
                logger.warning(f"community positions fetch failed: {e}")

        # Pass 1: rating-banded match
        narrow_query = dict(base_query)
        narrow_query["source_user_rating"] = {"$gte": narrow_low, "$lte": narrow_high}
        await _collect(narrow_query, limit - len(collected))

        # Pass 2: widen — drop the rating band if we came up short
        if len(collected) < limit:
            await _collect(base_query, limit - len(collected))

        # Normalize to the puzzle shape the frontend expects.
        return [self._normalize_community_position(p, weakness_pattern) for p in collected[:limit]]

    @staticmethod
    def _normalize_community_position(p: Dict, weakness_pattern: str) -> Dict:
        """Map a `community_training_positions` row → the frontend puzzle shape."""
        best_uci = p.get("best_move_uci") or ""
        best_san = p.get("best_move_san") or ""
        source_rating = p.get("source_user_rating")
        context = (
            f"From a {source_rating}-rated player's game — find the best move."
            if source_rating
            else "From another player's game — find the best move."
        )
        return {
            "puzzle_id": p.get("position_id"),
            "source": "community",
            "fen": p.get("fen"),
            "solution": [best_uci] if best_uci else [best_san],
            "solution_san": best_san,
            "your_move": p.get("user_move_san"),
            "your_move_uci": p.get("user_move_uci"),
            "cp_loss": p.get("cp_loss"),
            "move_number": p.get("move_number"),
            "rating": source_rating,
            "opening": p.get("opening_name") or "",
            "solve_rate": p.get("solve_rate"),
            "themes": [weakness_pattern],
            "context": context,
            "pattern_type": p.get("pattern_type"),
            "moment_tag": p.get("moment_tag"),
        }

    async def _get_lichess_puzzles(
        self,
        user_id: str,
        weakness_pattern: str,
        rating_range: tuple,
        limit: int,
        solved_ids: Optional[set] = None,
    ) -> List[Dict]:
        """Fetch theme-matched Lichess puzzles from `lichess_puzzles`.

        Lichess stores each puzzle with `fen` (the position before the
        opponent's setup move), `moves` (UCI list — first move is the
        opponent's, the rest are the user's solution). We advance the
        board by the opponent's move so the returned `fen` is the
        position the user actually solves from.

        Filters: themes ∈ mapped themes, rating within ±200 of user's
        band, popularity ordered, already-solved puzzles excluded.
        """
        if limit <= 0:
            return []
        themes = WEAKNESS_TO_PUZZLE_THEMES.get(weakness_pattern)
        if not themes:
            return []

        solved_ids = solved_ids if solved_ids is not None else await self._get_solved_ids(user_id)
        # Already-solved Lichess puzzle ids are stored as `lichess_<puzzle_id>`.
        already_solved_lichess = {
            sid.replace("lichess_", "")
            for sid in solved_ids
            if isinstance(sid, str) and sid.startswith("lichess_")
        }

        rating_low, rating_high = rating_range if rating_range and len(rating_range) == 2 else (600, 2200)

        query = {
            "themes": {"$in": themes},
            "rating": {"$gte": rating_low, "$lte": rating_high},
        }
        if already_solved_lichess:
            query["puzzle_id"] = {"$nin": list(already_solved_lichess)}

        # Pull a few extra to handle edge cases (illegal-move puzzles,
        # parse failures). Cap pull at limit*3 so we don't churn the DB.
        pull_n = max(limit * 3, limit + 5)
        try:
            cursor = self.db.lichess_puzzles.find(
                query, {"_id": 0}
            ).sort("popularity", -1).limit(pull_n)
        except Exception as e:
            logger.warning(f"lichess_puzzles fetch failed: {e}")
            return []

        import chess
        out: List[Dict] = []
        async for p in cursor:
            try:
                fen = p.get("fen", "")
                uci_moves = p.get("moves") or []
                if not fen or not uci_moves:
                    continue
                board = chess.Board(fen)
                opp = chess.Move.from_uci(uci_moves[0])
                if opp not in board.legal_moves:
                    continue
                board.push(opp)
                solution_moves = uci_moves[1:]
                if not solution_moves:
                    continue
                first_sol = chess.Move.from_uci(solution_moves[0])
                if first_sol not in board.legal_moves:
                    continue
                solution_san = board.san(first_sol)

                out.append({
                    "puzzle_id": f"lichess_{p['puzzle_id']}",
                    "source": "lichess",
                    "fen": board.fen(),
                    "solution": solution_moves,
                    "solution_san": solution_san,
                    "rating": p.get("rating"),
                    "themes": p.get("themes") or [],
                    "popularity": p.get("popularity"),
                    "opening": (p.get("opening_tags") or [None])[0] if p.get("opening_tags") else "",
                    "context": "Theme-matched from Lichess — find the best move.",
                    "game_url": p.get("game_url"),
                })
                if len(out) >= limit:
                    break
            except Exception as e:
                logger.debug(f"lichess puzzle parse failed for {p.get('puzzle_id')}: {e}")
                continue

        return out

    def _move_matches_weakness(self, move: Dict, weakness_pattern: str) -> bool:
        """Does this move's cognitive_gap match the target weakness?

        Uses the `cognitive_gap` tag written by `analysis_interpreter`
        (backfilled across all games). This is the canonical taxonomy —
        the same one used for pattern decay, training CTAs, and the
        coaching diagnosis map.

        Bug fix (2026-04-24): the previous version checked four legacy
        weakness names ("missed_threat", "poor_piece_safety",
        "tactical_blindness", "back_rank") and defaulted to `return True`
        — meaning for every canonical weakness (king_safety / opening_knowledge /
        tactical_oversight / etc.) EVERY critical move matched. Result:
        the same top puzzle was served for every weakness. Huge bug.
        """
        pattern = (weakness_pattern or "").lower().strip()
        move_gap = (move.get("cognitive_gap") or "").lower().strip()

        # Direct cognitive_gap match — the canonical path.
        if move_gap and move_gap == pattern:
            return True

        # Back-compat: callers still pass legacy names in a few places.
        # Map them to the canonical cognitive_gap before comparing.
        legacy_to_canonical = {
            "missed_threat":       "ignore_threat",
            "poor_piece_safety":   "piece_safety",
            "tactical_blindness":  "tactical_oversight",
            "failed_conversion":   "endgame_technique",
            "positional_drift":    "pawn_structure",
            "opening_inaccuracy":  "opening_knowledge",
            "calculation_error":   "calculation_depth",
            "material_blunder":    "piece_safety",
            "missed_fork":         "missed_tactic",
            "missed_pin":          "missed_tactic",
            "missed_discovery":    "missed_tactic",
            "back_rank":           "king_safety",
            "king_attack":         "king_safety",
            "hanging_piece":       "piece_safety",
        }
        mapped = legacy_to_canonical.get(pattern)
        if mapped and move_gap == mapped:
            return True

        # No match. Moves without a cognitive_gap tag (older analyses that
        # missed the backfill) do not match ANY specific weakness — they
        # fall through to community puzzles instead of being mis-served.
        return False
    
    
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
