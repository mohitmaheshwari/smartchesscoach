"""
Pattern Quality Service
=======================

Monitors and improves the quality of smart_patterns.

Features:
1. Pattern quality scoring
2. Match rate tracking
3. Auto-diagnosis of low-performing patterns
4. Pattern optimization recommendations
"""

import logging
from typing import Dict, List
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


# Quality thresholds
MIN_MATCH_RATE = 0.01  # At least 1% of positions should match for active patterns
MIN_CRITERIA_FIELDS = 2  # Patterns should have at least 2 criteria fields


async def get_pattern_quality_report(db: AsyncIOMotorDatabase) -> Dict:
    """
    Generate a comprehensive quality report for all patterns.
    
    Returns:
        Dict with quality metrics and recommendations
    """
    patterns = await db.smart_patterns.find({}).to_list(1000)
    
    if not patterns:
        return {
            "total_patterns": 0,
            "quality_score": 0,
            "issues": [],
            "recommendations": ["No patterns found. Start adding patterns through feedback."]
        }
    
    total_patterns = len(patterns)
    total_matches = sum(p.get("match_count", 0) for p in patterns)
    
    # Categorize patterns by quality
    high_quality = []
    medium_quality = []
    low_quality = []
    issues = []
    
    for p in patterns:
        score, issue_list = _score_pattern(p)
        p_info = {
            "pattern_type": p.get("pattern_type"),
            "rule_id": p.get("rule_id"),
            "match_count": p.get("match_count", 0),
            "quality_score": score,
            "issues": issue_list
        }
        
        if score >= 0.7:
            high_quality.append(p_info)
        elif score >= 0.4:
            medium_quality.append(p_info)
        else:
            low_quality.append(p_info)
            issues.extend(issue_list)
    
    # Generate overall quality score
    if patterns:
        overall_score = sum(_score_pattern(p)[0] for p in patterns) / len(patterns)
    else:
        overall_score = 0
    
    # Generate recommendations
    recommendations = _generate_recommendations(high_quality, medium_quality, low_quality, total_matches)
    
    return {
        "total_patterns": total_patterns,
        "total_matches": total_matches,
        "quality_score": round(overall_score * 100, 1),
        "breakdown": {
            "high_quality": len(high_quality),
            "medium_quality": len(medium_quality),
            "low_quality": len(low_quality)
        },
        "pattern_types": _count_by_type(patterns),
        "issues": issues[:10],  # Top 10 issues
        "recommendations": recommendations,
        "high_quality_patterns": high_quality[:5],
        "low_quality_patterns": low_quality[:5]
    }


def _score_pattern(pattern: Dict) -> tuple:
    """Score a single pattern's quality (0-1) and return issues."""
    score = 1.0
    issues = []
    
    pattern_type = pattern.get("pattern_type", "unknown")
    rule_id = pattern.get("rule_id", "unknown")[:8] if pattern.get("rule_id") else "unknown"
    criteria = pattern.get("match_criteria", {})
    matches = pattern.get("match_count", 0)
    position_fen = pattern.get("position_fen", "")
    explanation = pattern.get("explanation_template", "") or pattern.get("user_insight", "")
    
    # Handle criteria being a list (legacy format)
    if isinstance(criteria, list):
        criteria = {}
    
    # Check criteria quality
    if not criteria:
        score -= 0.4
        issues.append(f"{pattern_type} ({rule_id}): No match criteria")
    elif len(criteria) < MIN_CRITERIA_FIELDS:
        score -= 0.2
        issues.append(f"{pattern_type} ({rule_id}): Insufficient criteria (only {len(criteria)} fields)")
    
    # Check for empty/None values in criteria
    if isinstance(criteria, dict):
        empty_criteria = sum(1 for v in criteria.values() if v is None or v == [] or v == "")
        if empty_criteria > 0:
            score -= 0.1 * empty_criteria
            issues.append(f"{pattern_type} ({rule_id}): {empty_criteria} empty criteria fields")
    
    # Check for position FEN
    if not position_fen:
        score -= 0.1
    
    # Check for explanation
    if not explanation:
        score -= 0.1
        issues.append(f"{pattern_type} ({rule_id}): No explanation template")
    
    # Bonus for matches (patterns that actually work)
    if matches > 0:
        score += 0.1
    if matches >= 5:
        score += 0.1
    
    # Clamp score
    score = max(0, min(1, score))
    
    return score, issues


def _count_by_type(patterns: List[Dict]) -> Dict:
    """Count patterns by type."""
    counts = {}
    for p in patterns:
        ptype = p.get("pattern_type", "unknown")
        counts[ptype] = counts.get(ptype, 0) + 1
    return counts


def _generate_recommendations(high: List, medium: List, low: List, total_matches: int) -> List[str]:
    """Generate actionable recommendations."""
    recommendations = []
    
    if len(low) > len(high):
        recommendations.append(
            f"Most patterns ({len(low)}/{len(high)+len(medium)+len(low)}) have quality issues. "
            "Consider reviewing and fixing match criteria."
        )
    
    if total_matches < 10:
        recommendations.append(
            "Very few pattern matches recorded. This could mean:\n"
            "  1. Patterns are too specific (criteria too strict)\n"
            "  2. Not enough positions analyzed\n"
            "  3. Pattern types don't match common user mistakes"
        )
    
    if len(high) > 0:
        recommendations.append(
            f"{len(high)} high-quality patterns are working well. "
            f"Use these as templates for new patterns."
        )
    
    if not recommendations:
        recommendations.append("Pattern collection looks healthy. Continue monitoring.")
    
    return recommendations


async def optimize_low_quality_patterns(db: AsyncIOMotorDatabase) -> Dict:
    """
    Attempt to fix common issues in low-quality patterns.
    
    Returns:
        Dict with optimization results
    """
    patterns = await db.smart_patterns.find({}).to_list(1000)
    
    fixed = 0
    skipped = 0
    
    for p in patterns:
        score, _ = _score_pattern(p)
        
        if score < 0.4:
            # Try to fix common issues
            updates = {}
            criteria = p.get("match_criteria", {})
            
            # Fix empty target_pieces arrays
            if criteria.get("target_pieces") == []:
                if p.get("pattern_type") == "fork":
                    updates["match_criteria.min_targets"] = 2
            
            # Fix None attacker_piece
            if criteria.get("attacker_piece") is None:
                # Try to infer from geometry
                geometry = p.get("geometry", "")
                if "knight" in geometry.lower():
                    updates["match_criteria.attacker_piece"] = "knight"
                elif "bishop" in geometry.lower():
                    updates["match_criteria.attacker_piece"] = "bishop"
                elif "queen" in geometry.lower():
                    updates["match_criteria.attacker_piece"] = "queen"
            
            if updates:
                await db.smart_patterns.update_one(
                    {"_id": p["_id"]},
                    {"$set": updates}
                )
                fixed += 1
            else:
                skipped += 1
    
    return {
        "patterns_fixed": fixed,
        "patterns_skipped": skipped,
        "message": f"Optimized {fixed} patterns, {skipped} need manual review"
    }


async def get_pattern_effectiveness(db: AsyncIOMotorDatabase) -> Dict:
    """
    Analyze pattern effectiveness based on match history.
    
    Returns:
        Dict with effectiveness metrics per pattern type
    """
    # Get match history
    history = await db.pattern_match_history.find({}).to_list(1000)
    
    # Group by pattern type
    by_type = {}
    for h in history:
        ptype = h.get("pattern_type", "unknown")
        if ptype not in by_type:
            by_type[ptype] = {"matches": 0, "unique_positions": set()}
        by_type[ptype]["matches"] += 1
        by_type[ptype]["unique_positions"].add(h.get("position_fen", ""))
    
    # Calculate effectiveness
    effectiveness = {}
    for ptype, data in by_type.items():
        effectiveness[ptype] = {
            "total_matches": data["matches"],
            "unique_positions": len(data["unique_positions"]),
            "reuse_rate": data["matches"] / len(data["unique_positions"]) if data["unique_positions"] else 0
        }
    
    return {
        "pattern_effectiveness": effectiveness,
        "total_match_events": len(history)
    }
