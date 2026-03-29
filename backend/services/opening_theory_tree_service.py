"""
Opening Theory Tree Service
============================

Provides intelligent opening detection and theory matching using the tree structure.
Handles variations, sub-variations, and critical position detection.
"""

import json
import os
import logging
import chess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

THEORY_TREE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "coaching", "opening_theory_tree.json"
)

_THEORY_TREE_CACHE = None


def load_theory_tree() -> dict:
    """Load the opening theory tree from JSON."""
    global _THEORY_TREE_CACHE
    
    if _THEORY_TREE_CACHE is not None:
        return _THEORY_TREE_CACHE
    
    try:
        with open(THEORY_TREE_PATH, "r") as f:
            data = json.load(f)
            data.pop("_meta", None)
            _THEORY_TREE_CACHE = data
            return data
    except Exception as e:
        logger.warning(f"Could not load opening theory tree: {e}")
        return {}


@dataclass
class OpeningMatch:
    """Result of matching a position to an opening."""
    opening_name: str
    variation_name: Optional[str]
    eco_code: Optional[str]
    white_plan: str
    black_plan: str
    key_ideas: Dict[str, str]
    common_learnings: List[str]


@dataclass
class CriticalPositionMatch:
    """Result when a position matches a critical decision point."""
    position_name: str
    key_decision: str
    best_moves: Dict[str, Dict]
    mistake_moves: Dict[str, Dict]
    current_move_analysis: Optional[Dict] = None


def match_opening_by_eco(eco_code: str) -> Optional[Tuple[str, dict]]:
    """Match an opening by ECO code."""
    tree = load_theory_tree()
    
    if not eco_code:
        return None
    
    eco_prefix = eco_code[:3] if len(eco_code) >= 3 else eco_code
    eco_short = eco_code[:2] if len(eco_code) >= 2 else eco_code
    
    for opening_key, opening_data in tree.items():
        if not isinstance(opening_data, dict):
            continue
        
        prefixes = opening_data.get("eco_prefix", [])
        if eco_code in prefixes or eco_prefix in prefixes:
            return opening_key, opening_data
        
        # Check prefix matches
        for p in prefixes:
            if p.startswith(eco_short) or eco_code.startswith(p[:2]):
                return opening_key, opening_data
    
    return None


def match_opening_by_moves(move_list: List[str]) -> Optional[Tuple[str, dict, Optional[str]]]:
    """
    Match an opening by the moves played.
    Returns: (opening_key, opening_data, variation_key) or None
    """
    tree = load_theory_tree()
    
    if not move_list:
        return None
    
    best_match = None
    best_match_length = 0
    
    for opening_key, opening_data in tree.items():
        if not isinstance(opening_data, dict):
            continue
        
        main_line = opening_data.get("main_line", [])
        
        # Check how many moves match the main line
        match_length = 0
        for i, move in enumerate(main_line):
            if i < len(move_list) and move_list[i] == move:
                match_length += 1
            else:
                break
        
        if match_length > best_match_length:
            best_match_length = match_length
            best_match = (opening_key, opening_data, None)
        
        # Check variations
        variations = opening_data.get("variations", {})
        for var_key, var_data in variations.items():
            if not isinstance(var_data, dict):
                continue
            
            var_moves = var_data.get("moves_from_parent", [])
            full_var_moves = main_line + var_moves
            
            var_match_length = 0
            for i, move in enumerate(full_var_moves):
                if i < len(move_list) and move_list[i] == move:
                    var_match_length += 1
                else:
                    break
            
            if var_match_length > best_match_length:
                best_match_length = var_match_length
                best_match = (opening_key, opening_data, var_key)
    
    return best_match if best_match_length >= 3 else None


def check_critical_position(
    fen: str,
    move_san: str,
    eco_code: Optional[str] = None
) -> Optional[CriticalPositionMatch]:
    """
    Check if a position is a critical decision point in opening theory.
    
    Returns analysis of whether the played move is good/bad based on theory.
    """
    tree = load_theory_tree()
    
    # Normalize FEN for comparison (position part only)
    fen_parts = fen.split()
    fen_position = " ".join(fen_parts[:4]) if len(fen_parts) >= 4 else fen
    
    # Find relevant opening
    opening_match = match_opening_by_eco(eco_code) if eco_code else None
    
    if opening_match:
        opening_key, opening_data = opening_match
        
        # Check critical positions in main opening
        critical_positions = opening_data.get("critical_positions", {})
        for pos_name, pos_data in critical_positions.items():
            pattern = pos_data.get("fen_pattern", "")
            if _fen_matches(fen_position, pattern):
                return _analyze_critical_position(pos_name, pos_data, move_san)
        
        # Check variations
        variations = opening_data.get("variations", {})
        for var_key, var_data in variations.items():
            var_critical = var_data.get("critical_positions", {})
            for pos_name, pos_data in var_critical.items():
                pattern = pos_data.get("fen_pattern", "")
                if _fen_matches(fen_position, pattern):
                    return _analyze_critical_position(
                        f"{var_data.get('name', var_key)}: {pos_name}",
                        pos_data,
                        move_san
                    )
    
    # Search all openings if no ECO match
    for opening_key, opening_data in tree.items():
        if not isinstance(opening_data, dict):
            continue
        
        critical_positions = opening_data.get("critical_positions", {})
        for pos_name, pos_data in critical_positions.items():
            pattern = pos_data.get("fen_pattern", "")
            if _fen_matches(fen_position, pattern):
                return _analyze_critical_position(
                    f"{opening_data.get('name', opening_key)}: {pos_name}",
                    pos_data,
                    move_san
                )
        
        variations = opening_data.get("variations", {})
        for var_key, var_data in variations.items():
            if not isinstance(var_data, dict):
                continue
            var_critical = var_data.get("critical_positions", {})
            for pos_name, pos_data in var_critical.items():
                pattern = pos_data.get("fen_pattern", "")
                if _fen_matches(fen_position, pattern):
                    return _analyze_critical_position(
                        f"{var_data.get('name', var_key)}: {pos_name}",
                        pos_data,
                        move_san
                    )
    
    return None


def _fen_matches(fen1: str, fen2: str) -> bool:
    """Check if two FENs represent the same position (ignoring move counters)."""
    if not fen1 or not fen2:
        return False
    
    # Extract just the position part
    parts1 = fen1.split()[:4]
    parts2 = fen2.split()[:4]
    
    return " ".join(parts1) == " ".join(parts2)


def _analyze_critical_position(
    pos_name: str,
    pos_data: dict,
    move_san: str
) -> CriticalPositionMatch:
    """Analyze a move at a critical position."""
    move_clean = move_san.replace("+", "").replace("#", "").strip()
    
    best_moves = pos_data.get("best_moves", pos_data.get("best_moves_white", {}))
    mistake_moves = pos_data.get("mistake_moves", {})
    
    current_analysis = None
    
    # Check if move is a known best move
    if move_clean in best_moves:
        current_analysis = {
            "quality": "best",
            "info": best_moves[move_clean]
        }
    
    # Check if move is a known mistake
    elif move_clean in mistake_moves:
        current_analysis = {
            "quality": "mistake",
            "info": mistake_moves[move_clean]
        }
    
    return CriticalPositionMatch(
        position_name=pos_name,
        key_decision=pos_data.get("key_decision", ""),
        best_moves=best_moves,
        mistake_moves=mistake_moves,
        current_move_analysis=current_analysis
    )


def get_opening_learnings(
    eco_code: Optional[str],
    opening_name: Optional[str]
) -> List[str]:
    """Get common learnings for an opening."""
    tree = load_theory_tree()
    
    match = match_opening_by_eco(eco_code) if eco_code else None
    
    if match:
        _, opening_data = match
        return opening_data.get("common_learnings", [])
    
    # Try name matching
    if opening_name:
        name_lower = opening_name.lower()
        for opening_key, opening_data in tree.items():
            if not isinstance(opening_data, dict):
                continue
            if opening_key.replace("_", " ") in name_lower or opening_data.get("name", "").lower() in name_lower:
                return opening_data.get("common_learnings", [])
    
    return []


def get_opening_typical_ideas(
    eco_code: Optional[str],
    opening_name: Optional[str]
) -> Dict[str, str]:
    """Get typical move ideas for an opening."""
    tree = load_theory_tree()
    
    match = match_opening_by_eco(eco_code) if eco_code else None
    
    if match:
        _, opening_data = match
        return opening_data.get("typical_ideas", {})
    
    # Try name matching
    if opening_name:
        name_lower = opening_name.lower()
        for opening_key, opening_data in tree.items():
            if not isinstance(opening_data, dict):
                continue
            if opening_key.replace("_", " ") in name_lower or opening_data.get("name", "").lower() in name_lower:
                return opening_data.get("typical_ideas", {})
    
    return {}


def get_mistake_from_theory(
    eco_code: Optional[str],
    move_san: str,
    fen: str
) -> Optional[Dict]:
    """
    Check if a move is a known theoretical mistake.
    Returns the mistake info if found.
    """
    critical_match = check_critical_position(fen, move_san, eco_code)
    
    if critical_match and critical_match.current_move_analysis:
        if critical_match.current_move_analysis.get("quality") == "mistake":
            mistake_info = critical_match.current_move_analysis.get("info", {})
            return {
                "position_name": critical_match.position_name,
                "why_bad": mistake_info.get("why_bad", ""),
                "consequence": mistake_info.get("consequence", ""),
                "better_move": mistake_info.get("better_move", ""),
                "learning": mistake_info.get("learning", "")
            }
    
    return None


# Integration with V5 service
def enhance_v5_with_theory(
    move_data: dict,
    eco_code: Optional[str],
    fen_before: str,
    move_san: str
) -> dict:
    """
    Enhance V5 move data with opening theory insights.
    
    Returns updated move_data with theory information added.
    """
    # Check for critical position match
    critical_match = check_critical_position(fen_before, move_san, eco_code)
    
    if critical_match:
        move_data["theory_match"] = {
            "position_name": critical_match.position_name,
            "key_decision": critical_match.key_decision,
            "analysis": critical_match.current_move_analysis
        }
        
        # If it's a theoretical mistake, enhance the plan
        if critical_match.current_move_analysis:
            analysis = critical_match.current_move_analysis
            if analysis.get("quality") == "mistake":
                info = analysis.get("info", {})
                
                # Update plan with theory
                if move_data.get("plan"):
                    plan = move_data["plan"]
                    if info.get("learning"):
                        plan["transferable_learning"] = info["learning"]
                    if info.get("why_bad"):
                        plan["current_problem"] = info["why_bad"]
                    if info.get("consequence"):
                        plan["consequence"] = info["consequence"]
                    
                    # Add theory concept ID
                    plan["concept_id"] = f"theory_{critical_match.position_name.lower().replace(' ', '_').replace(':', '_')}"
                    plan["concept_type"] = "opening"
    
    return move_data
