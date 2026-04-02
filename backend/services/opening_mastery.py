"""
Opening Mastery System
======================

A complete opening teaching system that:
1. Identifies openings from current position
2. Offers to teach main lines, traps, plans
3. Remembers what user has learned
4. Tracks if user applies learnings in real games
5. Builds progressive mastery

Philosophy:
- Coach is NOT trying to win, coach is trying to TEACH
- Each opening has: main line, traps, key ideas, common mistakes
- User progresses: Learn → Practice → Apply in real games → Master
- Once mastered, move to next opening

Collections:
- opening_knowledge: Database of openings with teaching content
- user_opening_progress: What each user knows, has practiced, mastered
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone
import logging

from services.verified_opening_traps import get_verified_traps_for_opening

logger = logging.getLogger(__name__)


def _trap_moves(trap) -> List[str]:
    return getattr(trap, "moves", None) or getattr(trap, "full_line", []) or []


def _trap_fen_before(trap) -> Optional[str]:
    return getattr(trap, "fen_before_trap", None)


def _trap_fen_after(trap) -> Optional[str]:
    return getattr(trap, "fen_after_trap", None)


class MasteryLevel(str, Enum):
    """User's mastery level for an opening."""
    UNKNOWN = "unknown"          # Never seen this opening
    INTRODUCED = "introduced"    # Coach showed it once
    LEARNING = "learning"        # Currently learning
    PRACTICED = "practiced"      # Practiced in Play with Coach
    APPLIED = "applied"          # Used in a real game
    MASTERED = "mastered"        # Consistently applies correctly


class TeachingMode(str, Enum):
    """What the coach is teaching right now."""
    NONE = "none"
    MAIN_LINE = "main_line"
    TRAP = "trap"
    KEY_IDEAS = "key_ideas"
    QUIZ = "quiz"


@dataclass
class OpeningTrap:
    """A tactical trap within an opening."""
    name: str                    # "Fried Liver Attack"
    moves: List[str]             # ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"]
    trap_move: str               # "Nxf7" - the trap move
    explanation: str             # Why it works
    refutation: Optional[str]    # How to avoid if you're the victim
    fen_before_trap: str         # Position before the trap
    fen_after_trap: str          # Position after the trap lands
    victim_color: str            # "black" - who falls for the trap
    difficulty: str              # "beginner", "intermediate", "advanced"


@dataclass
class OpeningVariation:
    """A variation within an opening."""
    name: str                    # "Giuoco Piano"
    eco: str                     # "C53"
    moves: List[str]             # Main line moves
    key_ideas: List[str]         # Strategic ideas
    plans_for_white: List[str]   # What white wants
    plans_for_black: List[str]   # What black wants
    common_mistakes: List[str]   # What to avoid
    traps: List[OpeningTrap]     # Traps in this variation
    model_games: List[str]       # Famous games to study (optional)


@dataclass
class OpeningFamily:
    """A family of openings (e.g., Italian Game)."""
    name: str                    # "Italian Game"
    eco_range: str               # "C50-C59"
    first_moves: List[str]       # ["e4", "e5", "Nf3", "Nc6", "Bc4"]
    description: str             # Brief description
    character: str               # "open", "closed", "semi-open"
    suitable_for: List[str]      # ["beginners", "tactical players"]
    variations: List[OpeningVariation]
    introduction_message: str    # What coach says when entering this opening
    mastery_criteria: Dict       # What defines mastery


@dataclass
class UserOpeningProgress:
    """Track user's progress in learning an opening."""
    user_id: str
    opening_name: str
    mastery_level: MasteryLevel
    introduced_at: Optional[datetime]
    last_practiced_at: Optional[datetime]
    times_practiced: int
    times_applied_in_games: int
    correct_applications: int    # Times they played it correctly in real games
    traps_learned: List[str]     # Names of traps they've learned
    variations_learned: List[str]  # Variations they know
    quiz_scores: List[Dict]      # History of quiz attempts
    notes: str                   # Coach's notes about this user's progress


# ============================================
# OPENING KNOWLEDGE DATABASE
# ============================================

# This is the teaching content - each opening with its traps and lines
OPENING_DATABASE: Dict[str, OpeningFamily] = {}


def _build_opening_database():
    """Build the opening knowledge database from the JSON theory file."""
    global OPENING_DATABASE
    
    from services.opening_theory_json_service import get_all_opening_keys, get_opening_theory, get_available_variations, get_variation_lesson_moves
    
    json_keys = get_all_opening_keys()
    
    for opening_key in json_keys:
        theory = get_opening_theory(opening_key)
        if not theory:
            continue
        
        # Build variations from JSON (deep lines!)
        variations = []
        for var_info in get_available_variations(opening_key):
            lesson = get_variation_lesson_moves(opening_key, var_info["key"])
            if not lesson:
                continue
            variations.append(OpeningVariation(
                name=lesson["variation_name"],
                eco=", ".join(theory.get("eco_prefix", [])),
                moves=lesson["moves"],  # Full deep line (10-15+ moves)
                key_ideas=lesson.get("common_learnings", [])[:5],
                plans_for_white=[lesson.get("white_plan", "")] if lesson.get("white_plan") else [],
                plans_for_black=[lesson.get("black_plan", "")] if lesson.get("black_plan") else [],
                common_mistakes=[],
                traps=[],
                model_games=[],
            ))
        
        # If no variations were built, create one from the main line
        if not variations:
            variations.append(OpeningVariation(
                name="Main Line",
                eco=", ".join(theory.get("eco_prefix", [])),
                moves=theory.get("main_line", []),
                key_ideas=theory.get("common_learnings", [])[:5],
                plans_for_white=[theory.get("white_plan", "")] if theory.get("white_plan") else [],
                plans_for_black=[theory.get("black_plan", "")] if theory.get("black_plan") else [],
                common_mistakes=[],
                traps=[],
                model_games=[],
            ))
        
        OPENING_DATABASE[opening_key] = OpeningFamily(
            name=theory.get("name", opening_key.replace("_", " ").title()),
            eco_range=", ".join(theory.get("eco_prefix", [])),
            first_moves=theory.get("main_line", []),
            description=theory.get("white_plan", "") + " / " + theory.get("black_plan", ""),
            character="open" if any(m in theory.get("main_line", []) for m in ["e4", "e5"]) else "closed",
            suitable_for=["all levels"],
            variations=variations,
            introduction_message=f"Let's learn the {theory.get('name', opening_key)}! {theory.get('white_plan', '')}",
            mastery_criteria={"know_main_line": True, "applied_in_games": 3, "correct_applications": 2},
        )
    
    # Stub entries for openings not yet in the JSON (needed for detect_opening_from_moves)
    _stubs = {
        "sicilian_defense": ("Sicilian Defense", ["e4", "c5"], "The most popular response to e4.", "semi-open"),
        "philidor_defense": ("Philidor Defense", ["e4", "e5", "Nf3", "d6"], "Solid but passive defense.", "semi-open"),
        "vienna_game": ("Vienna Game", ["e4", "e5", "Nc3"], "White delays Nf3 for f4 ideas.", "open"),
        "scotch_game": ("Scotch Game", ["e4", "e5", "Nf3", "Nc6", "d4"], "Direct center challenge.", "open"),
        "petrov_defense": ("Petrov Defense", ["e4", "e5", "Nf3", "Nf6"], "Symmetrical and solid.", "open"),
        "kings_indian_defense": ("King's Indian Defense", ["d4", "Nf6", "c4", "g6"], "Hypermodern fianchetto.", "closed"),
        "grunfeld_defense": ("Grunfeld Defense", ["d4", "Nf6", "c4", "g6", "Nc3", "d5"], "Counter-attack the center.", "closed"),
        "nimzo_indian": ("Nimzo-Indian Defense", ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"], "Pin the knight.", "closed"),
        "queens_indian": ("Queen's Indian Defense", ["d4", "Nf6", "c4", "e6", "Nf3", "b6"], "Fianchetto approach.", "closed"),
        "slav_defense": ("Slav Defense", ["d4", "d5", "c4", "c6"], "Support d5 with c6.", "closed"),
        "qgd": ("Queen's Gambit Declined", ["d4", "d5", "c4", "e6"], "Classical defense.", "closed"),
        "benoni_defense": ("Benoni Defense", ["d4", "Nf6", "c4", "c5", "d5"], "Dynamic counter-attack.", "semi-open"),
        "budapest_gambit": ("Budapest Gambit", ["d4", "Nf6", "c4", "e5"], "Surprise gambit.", "open"),
        "dutch_defense": ("Dutch Defense", ["d4", "f5"], "Aggressive kingside setup.", "semi-open"),
        "scandinavian_defense": ("Scandinavian Defense", ["e4", "d5"], "Immediate central challenge.", "open"),
        "nimzowitsch_defense": ("Nimzowitsch Defense", ["e4", "Nc6"], "Unusual and flexible.", "semi-open"),
    }
    
    for key, (name, first_moves, desc, character) in _stubs.items():
        if key not in OPENING_DATABASE:
            OPENING_DATABASE[key] = OpeningFamily(
                name=name,
                eco_range="",
                first_moves=first_moves,
                description=desc,
                character=character,
                suitable_for=["all levels"],
                variations=[],
                introduction_message=f"Let's learn the {name}!",
                mastery_criteria={"know_main_line": True, "applied_in_games": 3},
            )


# Initialize the database
_build_opening_database()


# ============================================
# OPENING DETECTION
# ============================================

def detect_opening_from_moves(moves: List[str]) -> Optional[Dict]:
    """
    Detect which opening family we're in based on moves played.
    
    UNIFIED DETECTION: Uses both OPENING_DATABASE and LIBRARY_DATABASE
    to detect openings. Supports 23+ openings from the admin system.
    
    Returns:
        Dict with opening info or None if not recognized yet
    """
    if not moves:
        return None
    
    # Minimum moves to start detection
    if len(moves) < 2:
        return None
    
    moves_lower = [m.lower() for m in moves]
    
    # === PRIORITY DETECTION (most specific first) ===
    
    # Ruy Lopez: e4 e5 Nf3 Nc6 Bb5 (5 moves)
    if len(moves_lower) >= 5:
        if moves_lower[:5] == ["e4", "e5", "nf3", "nc6", "bb5"]:
            return _build_opening_result("ruy_lopez", moves)
    
    # Italian Game: e4 e5 Nf3 Nc6 Bc4 (5 moves)
    if len(moves_lower) >= 5:
        if moves_lower[:5] == ["e4", "e5", "nf3", "nc6", "bc4"]:
            return _build_opening_result("italian_game", moves)
        # Two Knights: e4 e5 Nf3 Nc6 Bc4 Nf6
        if len(moves_lower) >= 6 and moves_lower[:6] == ["e4", "e5", "nf3", "nc6", "bc4", "nf6"]:
            return _build_opening_result("italian_game", moves, "Two Knights Defense")
    
    # Scotch Game: e4 e5 Nf3 Nc6 d4 (5 moves)
    if len(moves_lower) >= 5:
        if moves_lower[:5] == ["e4", "e5", "nf3", "nc6", "d4"]:
            return _build_opening_result("scotch_game", moves)
    
    # Vienna Game: e4 e5 Nc3 (3 moves)
    if len(moves_lower) >= 3:
        if moves_lower[:3] == ["e4", "e5", "nc3"]:
            return _build_opening_result("vienna_game", moves)
    
    # Petrov Defense: e4 e5 Nf3 Nf6 (4 moves)
    if len(moves_lower) >= 4:
        if moves_lower[:4] == ["e4", "e5", "nf3", "nf6"]:
            return _build_opening_result("petrov_defense", moves)
    
    # Philidor Defense: e4 e5 Nf3 d6 (4 moves)
    if len(moves_lower) >= 4:
        if moves_lower[:4] == ["e4", "e5", "nf3", "d6"]:
            return _build_opening_result("philidor_defense", moves)
    
    # King's Indian Defense: d4 Nf6 c4 g6 (4 moves)
    if len(moves_lower) >= 4:
        if moves_lower[:4] == ["d4", "nf6", "c4", "g6"]:
            return _build_opening_result("kings_indian_defense", moves)
    
    # Grünfeld Defense: d4 Nf6 c4 g6 Nc3 d5 (6 moves)
    if len(moves_lower) >= 6:
        if moves_lower[:6] == ["d4", "nf6", "c4", "g6", "nc3", "d5"]:
            return _build_opening_result("grunfeld_defense", moves)
    
    # Nimzo-Indian: d4 Nf6 c4 e6 Nc3 Bb4 (6 moves)
    if len(moves_lower) >= 6:
        if moves_lower[:6] == ["d4", "nf6", "c4", "e6", "nc3", "bb4"]:
            return _build_opening_result("nimzo_indian", moves)
    
    # Queen's Indian: d4 Nf6 c4 e6 Nf3 b6 (6 moves)
    if len(moves_lower) >= 6:
        if moves_lower[:6] == ["d4", "nf6", "c4", "e6", "nf3", "b6"]:
            return _build_opening_result("queens_indian", moves)
    
    # Slav Defense: d4 d5 c4 c6 (4 moves)
    if len(moves_lower) >= 4:
        if moves_lower[:4] == ["d4", "d5", "c4", "c6"]:
            return _build_opening_result("slav_defense", moves)
    
    # Queen's Gambit Declined: d4 d5 c4 e6 (4 moves)
    if len(moves_lower) >= 4:
        if moves_lower[:4] == ["d4", "d5", "c4", "e6"]:
            return _build_opening_result("qgd", moves, "Queen's Gambit Declined")
    
    # Benoni Defense: d4 Nf6 c4 c5 d5 (5 moves)
    if len(moves_lower) >= 5:
        if moves_lower[:5] == ["d4", "nf6", "c4", "c5", "d5"]:
            return _build_opening_result("benoni_defense", moves)
    
    # Budapest Gambit: d4 Nf6 c4 e5 (4 moves)
    if len(moves_lower) >= 4:
        if moves_lower[:4] == ["d4", "nf6", "c4", "e5"]:
            return _build_opening_result("budapest_gambit", moves)
    
    # Dutch Defense: d4 f5 (2 moves)
    if len(moves_lower) >= 2:
        if moves_lower[:2] == ["d4", "f5"]:
            return _build_opening_result("dutch_defense", moves)
    
    # === STANDARD DETECTION ===
    
    # Queen's Gambit: d4 d5 c4 (3 moves)
    if len(moves_lower) >= 3:
        if moves_lower[:3] == ["d4", "d5", "c4"]:
            return _build_opening_result("queens_gambit", moves)
    
    # London System: d4 [any] Bf4 (White's 2nd move must be Bf4)
    if len(moves_lower) >= 3:
        if moves_lower[0] == "d4" and moves_lower[2].lower() == "bf4":
            return _build_opening_result("london_system", moves)
    
    # Sicilian Defense: e4 c5 (2 moves)
    if len(moves_lower) >= 2:
        if moves_lower[:2] == ["e4", "c5"]:
            return _build_opening_result("sicilian_defense", moves)
    
    # Caro-Kann: e4 c6 (2 moves)
    if len(moves_lower) >= 2:
        if moves_lower[:2] == ["e4", "c6"]:
            return _build_opening_result("caro_kann", moves)
    
    # French Defense: e4 e6 (2 moves)
    if len(moves_lower) >= 2:
        if moves_lower[:2] == ["e4", "e6"]:
            return _build_opening_result("french_defense", moves)
    
    # Scandinavian Defense: e4 d5 (2 moves)
    if len(moves_lower) >= 2:
        if moves_lower[:2] == ["e4", "d5"]:
            return _build_opening_result("scandinavian_defense", moves)
    
    # Nimzowitsch Defense: e4 Nc6 (2 moves)
    if len(moves_lower) >= 2:
        if moves_lower[:2] == ["e4", "nc6"]:
            return _build_opening_result("nimzowitsch_defense", moves)
    
    return None


def _build_opening_result(opening_key: str, moves: List[str], override_variation: str = None) -> Optional[Dict]:
    """Build the opening detection result dict."""
    opening = OPENING_DATABASE.get(opening_key)
    if not opening:
        return None
    
    variation = _find_variation(moves, opening) if not override_variation else None
    variation_name = override_variation or (variation.name if variation else None)
    
    # Use verified traps registry (the single source for traps)
    verified_traps = get_verified_traps_for_opening(opening_key)
    
    return {
        "opening_key": opening_key,
        "opening_name": opening.name,
        "variation": variation_name,
        "description": opening.description,
        "character": opening.character,
        "introduction": opening.introduction_message,
        "has_traps": len(verified_traps) > 0,
        "trap_names": [t.name for t in verified_traps],
    }


def _moves_match_opening(game_moves: List[str], opening: OpeningFamily) -> bool:
    """
    Check if game moves match an opening's characteristic moves.
    
    IMPORTANT: Only returns True if we have ALL the defining moves.
    We don't want to say "Queen's Gambit" after just d4.
    """
    if not game_moves:
        return False
    
    game_moves_lower = [m.lower() for m in game_moves]
    opening_moves_lower = [m.lower() for m in opening.first_moves]
    
    # We need AT LEAST all the opening's first moves to be played
    # to confidently identify the opening
    min_required_moves = len(opening_moves_lower)
    
    if len(game_moves_lower) < min_required_moves:
        # Not enough moves yet to identify this opening
        return False
    
    # Check if the game moves contain all the opening's characteristic moves
    # in the correct order
    game_prefix = game_moves_lower[:min_required_moves]
    if game_prefix == opening_moves_lower:
        return True
    
    # Also check variations - they might have different move orders
    for variation in opening.variations:
        var_moves_lower = [m.lower() for m in variation.moves]
        var_min_moves = min(len(var_moves_lower), min_required_moves)
        
        if len(game_moves_lower) >= var_min_moves:
            if game_moves_lower[:var_min_moves] == var_moves_lower[:var_min_moves]:
                return True
    
    return False


def _find_variation(game_moves: List[str], opening: OpeningFamily) -> Optional[OpeningVariation]:
    """Find the specific variation within an opening family."""
    game_moves_lower = [m.lower() for m in game_moves]
    
    best_match = None
    best_match_length = 0
    
    for variation in opening.variations:
        var_moves_lower = [m.lower() for m in variation.moves]
        match_length = 0
        
        for i, (gm, vm) in enumerate(zip(game_moves_lower, var_moves_lower)):
            if gm == vm:
                match_length = i + 1
            else:
                break
        
        if match_length > best_match_length:
            best_match = variation
            best_match_length = match_length
    
    return best_match


def detect_opening_from_fen(fen: str) -> Optional[Dict]:
    """
    Detect opening from a FEN position.
    
    This is harder - we'd need a position database.
    For now, returns None (use move-based detection).
    """
    # TODO: Implement position-based opening detection
    return None


# ============================================
# TEACHING FLOW
# ============================================

class OpeningTeacher:
    """
    Manages the teaching flow for an opening.
    
    Can:
    - Introduce an opening
    - Teach the main line move by move
    - Show traps interactively
    - Quiz the user
    """
    
    def __init__(self, opening_key: str, user_progress: Optional[UserOpeningProgress] = None):
        self.opening = OPENING_DATABASE.get(opening_key)
        self.user_progress = user_progress
        self.current_mode = TeachingMode.NONE
        self.current_variation = None
        self.current_trap = None
        self.teaching_move_index = 0
    
    def get_introduction(self) -> Dict:
        """Get the introduction message for this opening."""
        if not self.opening:
            return {"error": "Opening not found"}
        
        # Build teaching options
        options = ["Learn the main line"]

        verified_traps = get_verified_traps_for_opening(self._opening_key()) if self.opening else []
        if verified_traps:
            options.append(f"See a trap ({verified_traps[0].name})")
        
        options.append("Just play - I'll figure it out")
        
        return {
            "opening_name": self.opening.name,
            "message": self.opening.introduction_message,
            "options": options,
            "character": self.opening.character,
            "suitable_for": self.opening.suitable_for,
            "has_learned_before": self.user_progress is not None and self.user_progress.mastery_level != MasteryLevel.UNKNOWN
        }

    def _opening_key(self) -> str:
        for key, opening in OPENING_DATABASE.items():
            if opening == self.opening:
                return key
        return ""
    
    def start_main_line_teaching(self, variation_index: int = 0) -> Dict:
        """Start teaching the main line."""
        if not self.opening or not self.opening.variations:
            return {"error": "No variations available"}
        
        self.current_mode = TeachingMode.MAIN_LINE
        self.current_variation = self.opening.variations[min(variation_index, len(self.opening.variations) - 1)]
        self.teaching_move_index = 0
        
        return {
            "mode": "main_line",
            "variation_name": self.current_variation.name,
            "total_moves": len(self.current_variation.moves),
            "key_ideas": self.current_variation.key_ideas,
            "first_instruction": self._get_next_teaching_move()
        }
    
    def start_trap_teaching(self, trap_index: int = 0) -> Dict:
        """Start teaching a trap."""
        if not self.opening:
            return {"error": "Opening not found"}
        
        # Find traps across all variations
        all_traps = []
        for var in self.opening.variations:
            all_traps.extend(var.traps)
        
        if not all_traps:
            return {"error": "No traps available for this opening"}
        
        self.current_mode = TeachingMode.TRAP
        self.current_trap = all_traps[min(trap_index, len(all_traps) - 1)]
        self.teaching_move_index = 0
        
        return {
            "mode": "trap",
            "trap_name": self.current_trap.name,
            "explanation": self.current_trap.explanation,
            "victim_color": self.current_trap.victim_color,
            "difficulty": self.current_trap.difficulty,
            "setup_fen": self.current_trap.fen_before_trap,
            "total_moves": len(self.current_trap.moves),
            "first_instruction": self._get_next_trap_move()
        }
    
    def _get_next_teaching_move(self) -> Optional[Dict]:
        """Get the next move to teach in main line."""
        if not self.current_variation:
            return None
        
        if self.teaching_move_index >= len(self.current_variation.moves):
            return {
                "complete": True,
                "message": f"Well done! You've learned the main line of the {self.current_variation.name}!",
                "key_ideas": self.current_variation.key_ideas
            }
        
        move = self.current_variation.moves[self.teaching_move_index]
        is_white_move = self.teaching_move_index % 2 == 0
        move_number = (self.teaching_move_index // 2) + 1
        
        instruction = {
            "move": move,
            "move_number": move_number,
            "is_white_move": is_white_move,
            "instruction": f"{'White' if is_white_move else 'Black'} plays {move}",
            "remaining": len(self.current_variation.moves) - self.teaching_move_index - 1
        }
        
        self.teaching_move_index += 1
        return instruction
    
    def _get_next_trap_move(self) -> Optional[Dict]:
        """Get the next move in the trap sequence."""
        if not self.current_trap:
            return None
        
        if self.teaching_move_index >= len(self.current_trap.moves):
            return {
                "complete": True,
                "trap_move": self.current_trap.trap_move,
                "message": f"The trap move is {self.current_trap.trap_move}! {self.current_trap.explanation}",
                "refutation": self.current_trap.refutation
            }
        
        move = self.current_trap.moves[self.teaching_move_index]
        is_trap_move = move == self.current_trap.trap_move
        is_white_move = self.teaching_move_index % 2 == 0
        
        instruction = {
            "move": move,
            "is_white_move": is_white_move,
            "is_trap_move": is_trap_move,
            "instruction": f"Play {move}" if not is_trap_move else f"NOW! {move} - the trap!",
            "remaining": len(self.current_trap.moves) - self.teaching_move_index - 1
        }
        
        self.teaching_move_index += 1
        return instruction
    
    def get_quiz_question(self) -> Dict:
        """Generate a quiz question about this opening."""
        if not self.opening:
            return {"error": "Opening not found"}
        
        self.current_mode = TeachingMode.QUIZ
        
        # Quiz types: main line moves, trap moves, key ideas
        import random
        quiz_type = random.choice(["move", "trap", "idea"])
        
        if quiz_type == "move" and self.opening.variations:
            var = random.choice(self.opening.variations)
            if len(var.moves) >= 3:
                move_idx = random.randint(0, min(4, len(var.moves) - 1))
                return {
                    "type": "move",
                    "question": f"In the {var.name}, what is move {(move_idx // 2) + 1} for {'White' if move_idx % 2 == 0 else 'Black'}?",
                    "answer": var.moves[move_idx],
                    "hint": f"Previous move was {var.moves[move_idx - 1]}" if move_idx > 0 else "First move"
                }
        
        if quiz_type == "trap":
            all_traps = [t for v in self.opening.variations for t in v.traps]
            if all_traps:
                trap = random.choice(all_traps)
                return {
                    "type": "trap",
                    "question": f"What is the key move in the {trap.name}?",
                    "answer": trap.trap_move,
                    "hint": trap.explanation[:50] + "..."
                }
        
        # Default to key idea quiz
        if self.opening.variations:
            var = self.opening.variations[0]
            if var.key_ideas:
                return {
                    "type": "idea",
                    "question": f"Name a key idea in the {self.opening.name}",
                    "answers": var.key_ideas,
                    "hint": f"Think about what {self.opening.character} positions need"
                }
        
        return {"error": "Could not generate quiz question"}


# ============================================
# USER PROGRESS MANAGEMENT
# ============================================

async def get_user_opening_progress(db, user_id: str, opening_name: str) -> Optional[UserOpeningProgress]:
    """Get user's progress for a specific opening."""
    doc = await db.user_opening_progress.find_one({
        "user_id": user_id,
        "opening_name": opening_name
    })
    
    if not doc:
        return None
    
    return UserOpeningProgress(
        user_id=doc["user_id"],
        opening_name=doc["opening_name"],
        mastery_level=MasteryLevel(doc.get("mastery_level", "unknown")),
        introduced_at=doc.get("introduced_at"),
        last_practiced_at=doc.get("last_practiced_at"),
        times_practiced=doc.get("times_practiced", 0),
        times_applied_in_games=doc.get("times_applied_in_games", 0),
        correct_applications=doc.get("correct_applications", 0),
        traps_learned=doc.get("traps_learned", []),
        variations_learned=doc.get("variations_learned", []),
        quiz_scores=doc.get("quiz_scores", []),
        notes=doc.get("notes", "")
    )


async def update_user_opening_progress(db, progress: UserOpeningProgress):
    """Update user's progress for an opening."""
    await db.user_opening_progress.update_one(
        {"user_id": progress.user_id, "opening_name": progress.opening_name},
        {"$set": {
            "mastery_level": progress.mastery_level.value,
            "introduced_at": progress.introduced_at,
            "last_practiced_at": progress.last_practiced_at,
            "times_practiced": progress.times_practiced,
            "times_applied_in_games": progress.times_applied_in_games,
            "correct_applications": progress.correct_applications,
            "traps_learned": progress.traps_learned,
            "variations_learned": progress.variations_learned,
            "quiz_scores": progress.quiz_scores,
            "notes": progress.notes
        }},
        upsert=True
    )


async def get_all_user_openings(db, user_id: str) -> List[Dict]:
    """Get all openings a user has learned or started learning."""
    cursor = db.user_opening_progress.find({"user_id": user_id})
    openings = []
    
    async for doc in cursor:
        opening_key = doc["opening_name"].lower().replace(" ", "_")
        opening_data = OPENING_DATABASE.get(opening_key)
        
        openings.append({
            "opening_name": doc["opening_name"],
            "mastery_level": doc.get("mastery_level", "unknown"),
            "times_practiced": doc.get("times_practiced", 0),
            "times_applied": doc.get("times_applied_in_games", 0),
            "traps_learned": doc.get("traps_learned", []),
            "character": opening_data.character if opening_data else "unknown"
        })
    
    return openings


async def check_opening_in_real_game(db, user_id: str, game_moves: List[str]) -> Optional[Dict]:
    """
    Check if the user applied a learned opening in a real game.
    
    This is called during game analysis to track if the user
    is applying what they learned.
    """
    # Detect what opening was played
    opening_info = detect_opening_from_moves(game_moves)
    if not opening_info:
        return None
    
    # Check if user has learned this opening
    progress = await get_user_opening_progress(db, user_id, opening_info["opening_name"])
    if not progress or progress.mastery_level == MasteryLevel.UNKNOWN:
        return None  # User hasn't learned this opening yet
    
    # User played an opening they've learned!
    # Update their progress
    progress.times_applied_in_games += 1
    progress.last_practiced_at = datetime.now(timezone.utc)
    
    # Check if they played it correctly (simplified check)
    opening_data = OPENING_DATABASE.get(opening_info["opening_key"])
    if opening_data:
        expected_moves = opening_data.first_moves
        played_correct = all(
            gm.lower() == em.lower() 
            for gm, em in zip(game_moves[:len(expected_moves)], expected_moves)
        )
        
        if played_correct:
            progress.correct_applications += 1
            
            # Check if they've mastered it
            criteria = opening_data.mastery_criteria
            if (progress.correct_applications >= criteria.get("correct_applications", 2) and
                progress.times_applied_in_games >= criteria.get("applied_in_games", 3)):
                progress.mastery_level = MasteryLevel.MASTERED
    
    await update_user_opening_progress(db, progress)
    
    return {
        "opening_detected": opening_info["opening_name"],
        "was_learned": True,
        "played_correctly": played_correct,
        "new_mastery_level": progress.mastery_level.value,
        "times_applied": progress.times_applied_in_games,
        "correct_applications": progress.correct_applications
    }


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def get_available_openings() -> List[Dict]:
    """Get list of all available openings to learn."""
    return [
        {
            "key": key,
            "name": opening.name,
            "description": opening.description,
            "character": opening.character,
            "suitable_for": opening.suitable_for,
            "num_traps": sum(len(v.traps) for v in opening.variations),
            "num_variations": len(opening.variations)
        }
        for key, opening in OPENING_DATABASE.items()
    ]


def get_opening_details(opening_key: str) -> Optional[Dict]:
    """Get full details of an opening."""
    opening = OPENING_DATABASE.get(opening_key)
    if not opening:
        return None
    
    return {
        "name": opening.name,
        "eco_range": opening.eco_range,
        "description": opening.description,
        "character": opening.character,
        "suitable_for": opening.suitable_for,
        "first_moves": opening.first_moves,
        "variations": [
            {
                "name": v.name,
                "eco": v.eco,
                "moves": v.moves,
                "key_ideas": v.key_ideas,
                "traps": [{"name": t.name, "difficulty": t.difficulty} for t in v.traps]
            }
            for v in opening.variations
        ],
        "introduction": opening.introduction_message
    }



async def suggest_opening_for_session(db, user_id: str, user_color: str, user_rating: int) -> Dict:
    """
    INTELLIGENT opening suggestion based on:
    1. User's chosen color (white/black)
    2. What was recently taught (avoid repetition)
    3. Real game performance (from user's actual games)
    4. Mastery progress from coach lessons
    5. Prioritize weak areas, not random selection
    
    Returns:
        - opening_key: Key of the suggested opening
        - opening_name: Display name
        - why: Why this opening was chosen (personalized)
        - first_moves: The moves to guide the player through
        - teaching_message: What to tell the player
        - traps: List of available traps in this opening
        - suggested_trap: The trap we recommend learning (if any)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # ============================================
    # STEP 1: Gather all data sources
    # ============================================
    
    # Get user's lesson progress (what coach has taught)
    progress_list = await db.user_opening_progress.find({"user_id": user_id}).to_list(50)
    progress_by_name = {p["opening_name"]: p for p in progress_list}
    
    # Get user's trap progress
    trap_progress_list = await db.user_trap_stats.find({"user_id": user_id}).to_list(50)
    learned_traps = {t["trap_name"]: t for t in trap_progress_list if t.get("success_rate", 0) >= 0.5}
    
    # Get recently taught openings (last 5 coach sessions)
    recent_sessions = await db.coach_sessions.find(
        {"user_id": user_id, "opening_to_teach": {"$exists": True, "$ne": None}},
        {"_id": 0, "opening_to_teach": 1, "created_at": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    recently_taught = [s.get("opening_to_teach") for s in recent_sessions if s.get("opening_to_teach")]
    
    # Get real game statistics (win/loss by opening from actual games)
    real_game_stats = {}
    try:
        from opening_trainer_service import get_user_opening_stats
        stats_list = await get_user_opening_stats(db, user_id)
        for stat in stats_list:
            # Normalize name for matching
            name_key = stat.get("name", "").lower().replace(" ", "_").replace("-", "_")
            real_game_stats[name_key] = {
                "games": stat.get("games", 0),
                "wins": stat.get("wins", 0),
                "losses": stat.get("losses", 0),
                "win_rate": stat.get("win_rate", 0),
                "as_white": stat.get("as_white", 0),
                "as_black": stat.get("as_black", 0),
                "avg_accuracy": stat.get("avg_accuracy", 0)
            }
    except Exception as e:
        logger.warning(f"Could not get real game stats: {e}")
    
    # ============================================
    # STEP 2: Filter openings by user's color
    # ============================================
    
    suitable_openings = []
    for key, opening in OPENING_DATABASE.items():
        # Determine if this opening is for white or black
        first_move = opening.first_moves[0] if opening.first_moves else ""
        
        # White starts with e4, d4, c4, Nf3, etc.
        # Black responds to white's moves (e.g., Sicilian starts with e4, c5)
        is_white_opening = first_move in ["e4", "d4", "c4", "Nf3", "g3", "b3", "f4"]
        
        # For black openings, we look at the SECOND move or opening name
        # Sicilian, French, Caro-Kann are black responses to e4
        black_openings = ["sicilian", "french", "caro_kann", "scandinavian", "pirc", "alekhine", 
                         "kings_indian", "queens_gambit_declined", "nimzo_indian", "grunfeld", "dutch"]
        is_black_opening = any(b in key.lower() for b in black_openings)
        
        # Match to user's chosen color
        if user_color == "white" and is_black_opening:
            continue
        if user_color == "black" and is_white_opening and not is_black_opening:
            continue
        
        # Check rating suitability
        suitable = opening.suitable_for
        rating_ok = True
        if user_rating < 1000 and "advanced" in str(suitable).lower():
            rating_ok = False
        if user_rating > 1800 and "beginner" in str(suitable).lower() and "intermediate" not in str(suitable).lower():
            rating_ok = False
        
        if not rating_ok:
            continue
        
        # ============================================
        # STEP 3: Calculate priority score for each opening
        # ============================================
        
        # Get lesson progress
        progress = progress_by_name.get(opening.name)
        mastery = progress.get("mastery_level", "unknown") if progress else "unknown"
        times_practiced = progress.get("times_practiced", 0) if progress else 0
        times_applied = progress.get("times_applied_in_games", 0) if progress else 0
        correct_applications = progress.get("correct_applications", 0) if progress else 0
        _ = progress.get("last_practiced_at") if progress else None  # Reserved for future use
        
        # Get real game stats for this opening
        name_key = opening.name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
        real_stats = real_game_stats.get(name_key, {})
        real_games = real_stats.get("games", 0)
        real_win_rate = real_stats.get("win_rate", 0)
        real_accuracy = real_stats.get("avg_accuracy", 0)
        
        # Count unlearned traps
        all_traps = []
        for var in opening.variations:
            all_traps.extend(var.traps)
        unlearned_traps = [t for t in all_traps if t.name not in learned_traps]
        
        # ============================================
        # STEP 4: Calculate smart priority score
        # ============================================
        
        priority_score = 0
        suggestion_reason = ""
        
        # PENALTY: Recently taught (avoid repetition)
        if key in recently_taught:
            # Strong penalty - skip unless it's the only option
            priority_score -= 100
            # Even stronger if it was taught in the last session
            if recently_taught and key == recently_taught[0]:
                priority_score -= 200
        
        # BONUS: Never learned this opening
        if mastery == "unknown":
            priority_score += 50
            suggestion_reason = "Let's learn something new"
        
        # BONUS: Introduced but not practiced enough
        elif mastery == "introduced" and times_practiced < 3:
            priority_score += 40
            suggestion_reason = "We started this - let's continue"
        
        # BONUS: Learning but struggling in real games
        elif mastery == "learning":
            if real_games > 0 and real_win_rate < 40:
                priority_score += 60  # High priority - needs help!
                suggestion_reason = f"You're struggling with this in real games ({int(real_win_rate)}% win rate)"
            elif real_games == 0:
                priority_score += 30
                suggestion_reason = "You haven't tried this in real games yet"
            else:
                priority_score += 20
                suggestion_reason = "Keep practicing"
        
        # BONUS: Practiced but low win rate in real games
        elif mastery == "practiced":
            if real_games >= 3 and real_win_rate < 50:
                priority_score += 45  # Needs reinforcement
                suggestion_reason = f"Your win rate is {int(real_win_rate)}% - let's improve this"
            elif real_accuracy > 0 and real_accuracy < 70:
                priority_score += 35
                suggestion_reason = f"Your accuracy is {int(real_accuracy)}% - room for improvement"
            else:
                priority_score += 5  # Low priority, doing fine
                suggestion_reason = "Quick review"
        
        # BONUS: Has unlearned traps (always valuable)
        if len(unlearned_traps) > 0:
            priority_score += 15
        
        # BONUS: User hasn't applied in real games despite lessons
        if times_practiced >= 2 and times_applied == 0:
            priority_score += 25
            suggestion_reason = "You've practiced this but haven't used it in real games"
        
        # BONUS: Applied but with poor success rate
        if times_applied > 0 and correct_applications == 0:
            priority_score += 35
            suggestion_reason = "You've tried this but it hasn't worked out - let's fix that"
        
        suitable_openings.append({
            "key": key,
            "opening": opening,
            "mastery": mastery,
            "times_practiced": times_practiced,
            "real_games": real_games,
            "real_win_rate": real_win_rate,
            "real_accuracy": real_accuracy,
            "priority_score": priority_score,
            "suggestion_reason": suggestion_reason,
            "all_traps": all_traps,
            "unlearned_traps": unlearned_traps
        })
    
    # ============================================
    # STEP 5: Select the best opening
    # ============================================
    
    if not suitable_openings:
        logger.warning(f"No suitable openings for {user_color} at rating {user_rating}")
        return None
    
    # Sort by priority score (highest first)
    suitable_openings.sort(key=lambda x: x["priority_score"], reverse=True)
    
    # Select the top priority opening
    selected = suitable_openings[0]
    
    # If top choice was recently taught and there are alternatives, pick the next best
    if selected["priority_score"] < 0 and len(suitable_openings) > 1:
        for candidate in suitable_openings[1:]:
            if candidate["priority_score"] >= 0:
                selected = candidate
                break
    
    opening = selected["opening"]
    mastery = selected["mastery"]
    all_traps = selected.get("all_traps", [])
    unlearned_traps = selected.get("unlearned_traps", [])
    suggestion_reason = selected.get("suggestion_reason", "")
    real_win_rate = selected.get("real_win_rate", 0)
    real_games = selected.get("real_games", 0)

    verified_traps = get_verified_traps_for_opening(selected["key"])
    
    # ============================================
    # STEP 6: Select trap to suggest
    # ============================================
    
    suggested_trap = None
    if verified_traps:
        difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        suggested_trap = sorted(verified_traps, key=lambda t: difficulty_order.get(t.difficulty, 1))[0]
    elif unlearned_traps:
        # Sort by difficulty: beginner < intermediate < advanced
        difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        sorted_traps = sorted(unlearned_traps, key=lambda t: difficulty_order.get(t.difficulty, 1))
        suggested_trap = sorted_traps[0]
    
    # ============================================
    # STEP 7: Build personalized teaching message
    # ============================================
    
    if mastery == "unknown":
        why = suggestion_reason or "I noticed you haven't tried this opening yet"
        teaching_message = (
            f"Today let's learn the {opening.name}! "
            f"{opening.introduction_message}"
        )
    elif mastery == "introduced":
        why = suggestion_reason or "We started learning this but need more practice"
        teaching_message = (
            f"Let's continue learning the {opening.name}. "
            f"Follow my guidance for each move."
        )
    elif mastery == "learning":
        why = suggestion_reason or "You're learning this opening"
        if real_games > 0 and real_win_rate < 40:
            teaching_message = (
                f"I see you've been struggling with the {opening.name} in your real games "
                f"({int(real_win_rate)}% win rate). Let's work on that together!"
            )
        else:
            teaching_message = (
                f"Good! Let's practice the {opening.name} again. "
                f"Try to remember the main moves."
            )
    elif mastery == "practiced":
        why = suggestion_reason or "Time to reinforce what you've learned"
        if real_games > 0 and real_win_rate < 50:
            teaching_message = (
                f"Your {opening.name} could use some work - you're at {int(real_win_rate)}% win rate. "
                f"Let's sharpen it up!"
            )
        else:
            teaching_message = (
                f"Let's review the {opening.name}. "
                f"Show me what you remember!"
            )
    else:
        why = suggestion_reason or "Keeping your skills sharp"
        teaching_message = f"Let's play the {opening.name} - you know this one well!"
    
    # Add trap mention if available
    if suggested_trap:
        teaching_message += (
            f"\n\nThere's a famous trap here: the **{suggested_trap.name}**. "
            f"Want to learn it?"
        )
    
    # Get moves for teaching
    first_moves = opening.first_moves
    if opening.variations:
        main_variation = opening.variations[0]
        full_moves = main_variation.moves
        key_ideas = main_variation.key_ideas[:3] if main_variation.key_ideas else []
    else:
        full_moves = first_moves
        key_ideas = []
    
    # Build trap info for response
    trap_list = []
    source_traps = verified_traps or all_traps
    for trap in source_traps:
        trap_list.append({
            "name": trap.name,
            "difficulty": trap.difficulty,
            "moves": _trap_moves(trap),
            "trap_move": trap.trap_move,
            "explanation": trap.explanation,
            "refutation": trap.refutation,
            "victim_color": trap.victim_color,
            "learned": trap.name in learned_traps,
            "fen_before": _trap_fen_before(trap),
            "fen_after": _trap_fen_after(trap)
        })
    
    logger.info(f"Selected opening '{opening.name}' for {user_color} (priority: {selected['priority_score']}, reason: {why})")
    
    return {
        "opening_key": selected["key"],
        "opening_name": opening.name,
        "why": why,
        "first_moves": first_moves,
        "full_moves": full_moves,
        "teaching_message": teaching_message,
        "key_ideas": key_ideas,
        "mastery_level": mastery,
        "traps": trap_list,
        "suggested_trap": {
            "name": suggested_trap.name,
            "difficulty": suggested_trap.difficulty,
            "moves": _trap_moves(suggested_trap),
            "trap_move": suggested_trap.trap_move,
            "explanation": suggested_trap.explanation,
            "refutation": suggested_trap.refutation,
            "victim_color": suggested_trap.victim_color
        } if suggested_trap else None,
        # Additional context for UI
        "real_game_stats": {
            "games_played": real_games,
            "win_rate": real_win_rate
        } if real_games > 0 else None
    }


def get_move_guidance(opening_key: str, move_index: int, user_color: str) -> Optional[Dict]:
    """
    Get guidance for what move the user should play next in the opening.
    
    Returns instruction for the user's next move in the opening sequence.
    """
    opening = OPENING_DATABASE.get(opening_key)
    if not opening or not opening.variations:
        return None
    
    # Get main variation
    main_var = opening.variations[0]
    moves = main_var.moves
    
    if move_index >= len(moves):
        return {
            "complete": True,
            "message": f"Excellent! You've completed the main line of the {opening.name}. Now let's play!"
        }
    
    move = moves[move_index]
    is_white_move = (move_index % 2 == 0)
    
    # Check if this is the user's move
    is_user_move = (is_white_move and user_color == "white") or (not is_white_move and user_color == "black")
    
    move_number = (move_index // 2) + 1
    
    if is_user_move:
        # User should play this move - give guidance
        explanation = ""
        if move_index == 0 and main_var.key_ideas:
            explanation = main_var.key_ideas[0]
        elif move_index < len(main_var.key_ideas or []):
            explanation = main_var.key_ideas[move_index] if main_var.key_ideas else ""
        
        return {
            "complete": False,
            "your_turn": True,
            "suggested_move": move,
            "move_number": move_number,
            "message": f"Play {move}. {explanation}".strip(),
            "hint": f"The main line continues with {move}"
        }
    else:
        # This is the coach's move
        return {
            "complete": False,
            "your_turn": False,
            "coach_move": move,
            "move_number": move_number,
            "message": f"I'll play {move}."
        }
