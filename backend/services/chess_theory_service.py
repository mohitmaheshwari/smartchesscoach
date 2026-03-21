"""
Chess Theory Service — Enterprise Knowledge Base

Loads the split theory knowledge base from /data/theory/ directory:
  - opening_mistakes.json: FEN-based opening mistake patterns
  - endgame_principles.json: Material-based endgame patterns
  - tactical_patterns.json: Tactical motif patterns
  - positional_rules.json: Generic rules for PV classification fallback

Single source of truth for all chess theory matching.
"""

import json
import chess
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

THEORY_DIR = Path(__file__).parent.parent / "data" / "theory"

# Legacy path for backwards compatibility
LEGACY_THEORY_PATH = Path(__file__).parent.parent / "data" / "chess_theory.json"


class ChessTheoryService:
    """Service to match positions against the theory knowledge base."""

    def __init__(self):
        self.opening_patterns: Dict[str, Dict] = {}
        self.endgame_patterns: Dict[str, Dict] = {}
        self.tactical_patterns: Dict[str, Dict] = {}
        self.positional_rules: Dict[str, Dict] = {}
        self._load_theory()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_json(self, path: Path) -> Dict:
        """Load a single JSON file, stripping _meta / _description keys."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            data.pop("_meta", None)
            data.pop("_description", None)
            return {k: v for k, v in data.items() if isinstance(v, dict)}
        except Exception as e:
            logger.error(f"Error loading {path}: {e}")
            return {}

    def _load_theory(self):
        """Load theory from the split directory structure."""
        if THEORY_DIR.exists():
            self.opening_patterns = self._load_json(THEORY_DIR / "opening_mistakes.json")
            self.endgame_patterns = self._load_json(THEORY_DIR / "endgame_principles.json")
            self.tactical_patterns = self._load_json(THEORY_DIR / "tactical_patterns.json")
            self.positional_rules = self._load_json(THEORY_DIR / "positional_rules.json")
            logger.info(
                f"Theory loaded: {len(self.opening_patterns)} openings, "
                f"{len(self.endgame_patterns)} endgames, "
                f"{len(self.tactical_patterns)} tactics, "
                f"{len(self.positional_rules)} rules"
            )
        elif LEGACY_THEORY_PATH.exists():
            logger.warning("Using legacy chess_theory.json — migrate to data/theory/")
            self._load_legacy()
        else:
            logger.warning("No theory database found")

    def _load_legacy(self):
        """Fallback: load from single legacy chess_theory.json."""
        try:
            with open(LEGACY_THEORY_PATH, "r") as f:
                data = json.load(f)
            raw_open = data.get("opening_theory", {})
            raw_open.pop("_description", None)
            self.opening_patterns = {k: v for k, v in raw_open.items() if isinstance(v, dict)}

            raw_end = data.get("endgame_theory", {})
            raw_end.pop("_description", None)
            self.endgame_patterns = {k: v for k, v in raw_end.items() if isinstance(v, dict)}

            raw_tac = data.get("tactical_patterns", {})
            raw_tac.pop("_description", None)
            self.tactical_patterns = {k: v for k, v in raw_tac.items() if isinstance(v, dict)}
        except Exception as e:
            logger.error(f"Error loading legacy theory: {e}")

    def reload_theory(self):
        """Reload theory from disk (call after admin updates)."""
        self.opening_patterns = {}
        self.endgame_patterns = {}
        self.tactical_patterns = {}
        self.positional_rules = {}
        self._load_theory()

    # ------------------------------------------------------------------
    # Matching — Openings
    # ------------------------------------------------------------------

    def match_opening_theory(
        self, fen: str, played_move: str, best_move: str
    ) -> Optional[Dict[str, Any]]:
        """Check if position + moves match a known opening pattern."""
        played_clean = self._normalize_move(played_move)
        best_clean = self._normalize_move(best_move)

        try:
            board = chess.Board(fen)
            board_fen = board.board_fen()
        except (ValueError, chess.InvalidMoveError):
            return None

        for pattern_id, pattern in self.opening_patterns.items():
            if not isinstance(pattern, dict):
                continue

            # Skip heuristic patterns (no FEN)
            if pattern.get("match_type") == "heuristic" or not pattern.get("fen_pattern"):
                continue

            try:
                pattern_board = chess.Board(pattern["fen_pattern"])
                if board_fen != pattern_board.board_fen():
                    continue
            except (ValueError, chess.InvalidMoveError):
                continue

            pattern_bad = self._normalize_move(pattern.get("bad_move", ""))
            pattern_good = self._normalize_move(pattern.get("good_move", ""))

            if played_clean == pattern_bad and best_clean == pattern_good:
                return {
                    "pattern_id": pattern_id,
                    "name": pattern.get("name", "Opening Pattern"),
                    "eco": pattern.get("eco"),
                    "family": pattern.get("family"),
                    "explanation": pattern.get("explanation", ""),
                    "why_bad": pattern.get("why_bad", ""),
                    "why_good": pattern.get("why_good", ""),
                    "rule": pattern.get("rule", ""),
                    "category": "opening",
                    "difficulty": pattern.get("difficulty", "intermediate"),
                }

        return None

    # ------------------------------------------------------------------
    # Matching — Endgames
    # ------------------------------------------------------------------

    def match_endgame_theory(self, fen: str) -> Optional[Dict[str, Any]]:
        """Check if position matches a known endgame pattern by material."""
        try:
            board = chess.Board(fen)
        except (ValueError, chess.InvalidMoveError):
            return None

        pieces = self._count_material(board)
        total = pieces["total_non_king"]

        if total > 10:
            return None

        pattern_type = self._classify_endgame(board, pieces)
        if not pattern_type:
            return None

        for pattern_id, pattern in self.endgame_patterns.items():
            if not isinstance(pattern, dict):
                continue
            if pattern.get("pattern_type") == pattern_type:
                return {
                    "pattern_id": pattern_id,
                    "name": pattern.get("name", "Endgame Pattern"),
                    "key_rule": pattern.get("key_rule", ""),
                    "explanation": pattern.get("explanation", ""),
                    "common_mistake": pattern.get("common_mistake", ""),
                    "correct_technique": pattern.get("correct_technique", ""),
                    "rule": pattern.get("rule", "") or pattern.get("key_rule", ""),
                    "category": "endgame",
                    "difficulty": pattern.get("difficulty", "intermediate"),
                }

        return None

    # ------------------------------------------------------------------
    # Matching — Tactics
    # ------------------------------------------------------------------

    def match_tactical_pattern(self, pattern_type: str) -> Optional[Dict[str, Any]]:
        """Get tactical pattern info by type."""
        for pattern_id, pattern in self.tactical_patterns.items():
            if not isinstance(pattern, dict):
                continue
            if pattern.get("pattern_type") == pattern_type:
                return {
                    "pattern_id": pattern_id,
                    "name": pattern.get("name", "Tactical Pattern"),
                    "rule": pattern.get("rule", ""),
                    "explanation": pattern.get("explanation", ""),
                    "prevention": pattern.get("prevention", ""),
                    "category": "tactical",
                    "difficulty": pattern.get("difficulty", "beginner"),
                }
        return None

    # ------------------------------------------------------------------
    # Positional Rules (for line_parser fallback)
    # ------------------------------------------------------------------

    def get_positional_rule(self, pattern_key: str) -> Dict[str, str]:
        """Get the golden rule for a detected pattern (used by line_parser)."""
        rule = self.positional_rules.get(pattern_key)
        if rule and isinstance(rule, dict):
            return {
                "rule": rule.get("rule", ""),
                "short": rule.get("short", ""),
                "severity": rule.get("severity", "unknown"),
            }
        return {
            "rule": "Calculate your opponent's best response before moving.",
            "short": "This move has a tactical flaw.",
            "severity": "unknown",
        }

    # ------------------------------------------------------------------
    # Admin / Read endpoints
    # ------------------------------------------------------------------

    def get_all_opening_patterns(self) -> List[Dict[str, Any]]:
        return [{"id": k, **v} for k, v in self.opening_patterns.items() if isinstance(v, dict)]

    def get_all_endgame_patterns(self) -> List[Dict[str, Any]]:
        return [{"id": k, **v} for k, v in self.endgame_patterns.items() if isinstance(v, dict)]

    def get_all_tactical_patterns(self) -> List[Dict[str, Any]]:
        return [{"id": k, **v} for k, v in self.tactical_patterns.items() if isinstance(v, dict)]

    def get_all_positional_rules(self) -> List[Dict[str, Any]]:
        return [{"id": k, **v} for k, v in self.positional_rules.items() if isinstance(v, dict)]

    def get_theory_stats(self) -> Dict[str, int]:
        counts = {
            "opening_patterns": len(self.opening_patterns),
            "endgame_patterns": len(self.endgame_patterns),
            "tactical_patterns": len(self.tactical_patterns),
            "positional_rules": len(self.positional_rules),
        }
        counts["total"] = sum(counts.values())
        return counts

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_move(move: str) -> str:
        return move.lower().replace("+", "").replace("#", "").replace("x", "")

    @staticmethod
    def _count_material(board: chess.Board) -> Dict:
        result = {}
        for color_name, color in [("white", chess.WHITE), ("black", chess.BLACK)]:
            for piece_name, piece_type in [
                ("K", chess.KING), ("Q", chess.QUEEN), ("R", chess.ROOK),
                ("B", chess.BISHOP), ("N", chess.KNIGHT), ("P", chess.PAWN),
            ]:
                result[f"{color_name}_{piece_name}"] = len(board.pieces(piece_type, color))
        total = sum(v for k, v in result.items() if not k.endswith("_K"))
        result["total_non_king"] = total
        return result

    @staticmethod
    def _classify_endgame(board: chess.Board, pieces: Dict) -> Optional[str]:
        has_rook = (pieces["white_R"] + pieces["black_R"]) > 0
        has_queen = (pieces["white_Q"] + pieces["black_Q"]) > 0
        has_bishop = (pieces["white_B"] + pieces["black_B"]) > 0
        has_knight = (pieces["white_N"] + pieces["black_N"]) > 0
        has_pawn = (pieces["white_P"] + pieces["black_P"]) > 0

        # Queen endgame
        if has_queen and not has_rook and not has_bishop and not has_knight:
            return "queen_endgame"

        # Rook endgames
        if has_rook and not has_queen:
            return "rook_endgame"

        # Pure pawn endgame
        if pieces["total_non_king"] <= 3 and has_pawn and not has_rook and not has_queen and not has_bishop and not has_knight:
            return "KP_vs_K"

        # Bishop endgames
        if has_bishop and not has_rook and not has_queen:
            wb = list(board.pieces(chess.BISHOP, chess.WHITE))
            bb = list(board.pieces(chess.BISHOP, chess.BLACK))
            if wb and bb and chess.square_color(wb[0]) != chess.square_color(bb[0]):
                return "bishop_endgame"
            if wb and bb:
                return "bishop_endgame"
            if not has_knight:
                return "bishop_endgame"

        # Minor piece endgames
        if (has_bishop or has_knight) and not has_rook and not has_queen:
            return "minor_piece_endgame"

        # General endgame
        if pieces["total_non_king"] <= 6:
            return "general_endgame"

        return None


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_theory_service: Optional[ChessTheoryService] = None


def get_theory_service() -> ChessTheoryService:
    global _theory_service
    if _theory_service is None:
        _theory_service = ChessTheoryService()
    return _theory_service
