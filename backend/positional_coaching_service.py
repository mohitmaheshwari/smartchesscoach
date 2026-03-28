"""
Positional Coaching Service - RAG-Backed Deep Positional Insights

This service connects the knowledge base to the strategic analysis system.
When a pawn structure or strategic theme is detected, it retrieves 
structured knowledge and generates coach-level explanations.

Architecture:
1. Detection: Deterministic detection of pawn structure/theme (from blunder_intelligence_service)
2. Retrieval: Fetch relevant knowledge from knowledge_base/
3. Synthesis: Generate contextual explanation (constrained LLM or template)

NO HALLUCINATION - All insights grounded in knowledge base.
"""

import logging
from typing import Dict, List, Optional, Any

# Import knowledge base
from knowledge_base import (
    match_structure_from_analysis,
    detect_imbalances_from_themes,
    get_structure_by_id,
    PAWN_STRUCTURES,
    STRATEGIC_IMBALANCES
)

logger = logging.getLogger(__name__)


def get_positional_insight(
    structure_type: str,
    user_color: str,
    strategic_themes: List[str] = None,
    execution_data: Dict = None
) -> Optional[Dict]:
    """
    Generate positional insight based on detected structure and themes.
    
    This is the main entry point for the RAG-backed coaching layer.
    
    Args:
        structure_type: Detected pawn structure (e.g., "Isolated Queen's Pawn")
        user_color: "white" or "black"
        strategic_themes: List of detected themes from analysis
        execution_data: How well user executed the structure-specific plans
    
    Returns:
        Structured positional insight with plans, errors, and advice
    """
    insight = {
        "has_insight": False,
        "structure_insight": None,
        "theme_insights": [],
        "synthesis": None
    }
    
    # 1. RETRIEVE PAWN STRUCTURE KNOWLEDGE
    if structure_type:
        structure_knowledge = match_structure_from_analysis(structure_type)
        
        if structure_knowledge:
            insight["has_insight"] = True
            insight["structure_insight"] = _format_structure_insight(
                structure_knowledge, 
                user_color,
                execution_data
            )
    
    # 2. RETRIEVE STRATEGIC THEME KNOWLEDGE
    if strategic_themes:
        theme_insights = detect_imbalances_from_themes(strategic_themes)
        
        for theme_kb in theme_insights:
            if theme_kb:
                insight["has_insight"] = True
                insight["theme_insights"].append(
                    _format_theme_insight(theme_kb, user_color)
                )
    
    # 3. SYNTHESIZE COACHING MESSAGE
    if insight["has_insight"]:
        insight["synthesis"] = _synthesize_coaching_message(
            insight["structure_insight"],
            insight["theme_insights"],
            user_color,
            execution_data
        )
    
    return insight if insight["has_insight"] else None


def _format_structure_insight(
    structure_kb: Dict,
    user_color: str,
    execution_data: Dict = None
) -> Dict:
    """Format pawn structure knowledge for display"""
    
    # Determine if user has the structure or is playing against it
    # This would typically come from execution_data
    has_structure = True  # Default assumption
    if execution_data:
        has_structure = execution_data.get("user_has_structure", True)
    
    if has_structure:
        goal_key = "strategic_goal_with"
        error_key = "with_" + structure_kb.get("structure_id", "iqp").split("_")[0]
    else:
        goal_key = "strategic_goal_against"
        error_key = "against_" + structure_kb.get("structure_id", "iqp").split("_")[0]
    
    goal_data = structure_kb.get(goal_key, {})
    
    # Handle different error key formats in knowledge base
    errors = structure_kb.get("amateur_errors", {})
    if error_key in errors:
        amateur_errors = errors[error_key]
    elif has_structure:
        # Try alternative keys
        amateur_errors = errors.get("with_iqp", errors.get("with_hanging", errors.get("with_doubled", [])))
    else:
        amateur_errors = errors.get("against_iqp", errors.get("against_hanging", errors.get("against_doubled", [])))
    
    return {
        "structure_name": structure_kb.get("name", "Unknown Structure"),
        "structure_id": structure_kb.get("structure_id"),
        "summary": goal_data.get("summary", ""),
        "your_plans": goal_data.get("plans", [])[:4],  # Top 4 plans
        "key_moves": goal_data.get("key_moves", []),
        "amateur_errors": amateur_errors[:3] if isinstance(amateur_errors, list) else [],
        "conversion": structure_kb.get("conversion_pattern", {}).get(
            "with_" + structure_kb.get("structure_id", "").split("_")[0] if has_structure else "against_" + structure_kb.get("structure_id", "").split("_")[0],
            structure_kb.get("conversion_pattern", {}).get("summary", "")
        ),
        "key_squares": structure_kb.get("key_squares", []),
        "has_structure": has_structure
    }


def _format_theme_insight(theme_kb: Dict, user_color: str) -> Dict:
    """Format strategic theme knowledge for display"""
    
    goal_data = theme_kb.get("strategic_goal_with", {})
    
    return {
        "theme_name": theme_kb.get("name", "Unknown Theme"),
        "concept_id": theme_kb.get("concept_id"),
        "summary": goal_data.get("summary", ""),
        "plans": goal_data.get("plans", [])[:3],
        "key_moves": goal_data.get("key_moves", []),
        "amateur_errors": theme_kb.get("amateur_errors", {}).get("with_" + theme_kb.get("concept_id", "").split("_")[0], [])[:2]
    }


def _synthesize_coaching_message(
    structure_insight: Optional[Dict],
    theme_insights: List[Dict],
    user_color: str,
    execution_data: Dict = None
) -> str:
    """
    Synthesize a coaching message from retrieved knowledge.
    
    This is CONSTRAINED synthesis - only uses facts from knowledge base.
    No hallucination. No invented variations.
    """
    parts = []
    
    if structure_insight:
        name = structure_insight.get("structure_name", "This structure")
        summary = structure_insight.get("summary", "")
        
        parts.append(f"**{name}**")
        parts.append(f"Your strategic goal: {summary}")
        
        plans = structure_insight.get("your_plans", [])
        if plans:
            parts.append("\n**Key Plans:**")
            for plan in plans[:3]:
                parts.append(f"- {plan}")
        
        errors = structure_insight.get("amateur_errors", [])
        if errors:
            parts.append("\n**Watch out for:**")
            for error in errors[:2]:
                parts.append(f"- {error}")
    
    if theme_insights:
        parts.append("\n**Additional Strategic Themes:**")
        for theme in theme_insights[:2]:
            theme_name = theme.get("theme_name", "")
            theme_summary = theme.get("summary", "")
            if theme_name and theme_summary:
                parts.append(f"- **{theme_name}**: {theme_summary}")
    
    if execution_data and execution_data.get("verdict"):
        verdict = execution_data.get("verdict", "")
        if "Good" in verdict or "Excellent" in verdict:
            parts.append("\n**Your Execution:** Well done following the strategic principles!")
        elif "Partial" in verdict:
            parts.append("\n**Your Execution:** You had the right ideas but execution could improve.")
        else:
            parts.append("\n**Your Execution:** Review the plans above for future games.")
    
    return "\n".join(parts)


def get_structure_deep_dive(structure_id: str, user_color: str) -> Optional[Dict]:
    """
    Get complete deep-dive information for a specific structure.
    
    Used when user clicks to expand the positional insight section.
    """
    structure_kb = get_structure_by_id(structure_id)
    
    if not structure_kb:
        return None
    
    return {
        "structure_id": structure_id,
        "name": structure_kb.get("name"),
        "trigger_conditions": structure_kb.get("trigger_conditions", []),
        "with_structure": structure_kb.get("strategic_goal_with", {}),
        "against_structure": structure_kb.get("strategic_goal_against", {}),
        "typical_plans": structure_kb.get("typical_plans", {}),
        "amateur_errors": structure_kb.get("amateur_errors", {}),
        "conversion": structure_kb.get("conversion_pattern", {}),
        "key_squares": structure_kb.get("key_squares", []),
        "piece_placement": structure_kb.get("piece_placement", {}),
        "model_games": structure_kb.get("model_games", [])
    }


def get_all_structures_summary() -> List[Dict]:
    """Get summary of all pawn structures for reference"""
    summaries = []
    
    for struct_id, struct_data in PAWN_STRUCTURES.items():
        summaries.append({
            "structure_id": struct_id,
            "name": struct_data.get("name"),
            "key_point": struct_data.get("strategic_goal_with", {}).get("summary", "")
        })
    
    return summaries


def get_all_imbalances_summary() -> List[Dict]:
    """Get summary of all strategic imbalances for reference"""
    summaries = []
    
    for concept_id, concept_data in STRATEGIC_IMBALANCES.items():
        summaries.append({
            "concept_id": concept_id,
            "name": concept_data.get("name"),
            "key_point": concept_data.get("strategic_goal_with", {}).get("summary", "")
        })
    
    return summaries
