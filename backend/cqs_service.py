"""
Coach Quality Score (CQS) System

Internal quality evaluation for AI coaching explanations.
NEVER expose to users - this is for internal monitoring only.

Scores explanations on 6 dimensions:
1. Habit Focus (0-25)
2. Coach Memory Usage (0-20)
3. Clarity & Simplicity (0-20)
4. Consistency with Past Advice (0-15)
5. Emotional Tone (0-10)
6. Actionability (0-10)

Total: 0-100
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Quality thresholds
ACCEPT_THRESHOLD = 80
WARNING_THRESHOLD = 70
REJECT_THRESHOLD = 70
CRITICAL_THRESHOLD = 60
MAX_REGENERATIONS = 2

# Predefined weakness categories for validation
VALID_HABIT_CATEGORIES = {
    "rushing", "tunnel_vision", "hope_chess", "fear_based", 
    "lazy_calculation", "pattern_blindness", "impulsive",
    "overconfidence", "solid_thinking"
}

VALID_WEAKNESS_SUBCATEGORIES = {
    "one_move_blunders", "pin_blindness", "fork_misses", "back_rank_weakness",
    "center_control_neglect", "poor_piece_activity", "lack_of_plan",
    "delayed_castling", "exposing_own_king", "premature_queen_moves",
    "neglecting_development", "not_castling_early", "king_activity_neglect",
    "pawn_race_errors", "impulsive_moves", "tunnel_vision", "hope_chess",
    "time_trouble_blunders", "skewer_blindness", "discovered_attack_misses"
}

# Penalty patterns
VAGUE_ADVICE_PATTERNS = [
    r"\bbe careful\b", r"\bplay better\b", r"\bthink more\b",
    r"\btry harder\b", r"\bpay attention\b", r"\bfocus more\b",
    r"\bwatch out\b", r"\bbe aware\b"
]

ENGINE_LANGUAGE_PATTERNS = [
    r"stockfish", r"centipawn", r"\+\d+\.\d+", r"-\d+\.\d+",
    r"\beval\b", r"\bengine\b", r"\bcp\s*=", r"\bbest move\b"
]

HYPE_PATTERNS = [
    r"\bamazing\b", r"\bbrilliant\b", r"\bfantastic\b", r"\bawesome\b",
    r"\bincredible\b", r"\bwow\b", r"\bunbelievable\b"
]

SHAME_PATTERNS = [
    r"\bterrible\b", r"\bawful\b", r"\bdisaster\b", r"\bhow could you\b",
    r"\bwhat were you thinking\b", r"\bunacceptable\b"
]

EXAGGERATION_PATTERNS = [
    r"\balways\b", r"\bnever\b", r"\bevery time\b", r"\byou always\b",
    r"\byou never\b"
]


def evaluate_habit_focus(commentary: List[Dict], weaknesses: List[Dict]) -> Tuple[int, List[str]]:
    """
    Dimension 1: Habit Focus Score (0-25)
    
    Checks:
    - Exactly ONE thinking habit per mistake
    - Habit maps to predefined taxonomy
    - Focus on thinking, not moves
    """
    score = 25
    penalties = []
    
    for item in commentary:
        eval_type = item.get("evaluation", "")
        if eval_type not in ["blunder", "mistake", "inaccuracy"]:
            continue
        
        details = item.get("details", item.get("explanation", {}))
        
        # Check for valid habit category
        thinking_pattern = details.get("thinking_pattern", details.get("habit_category", ""))
        if thinking_pattern:
            pattern_lower = thinking_pattern.lower().replace(" ", "_")
            if pattern_lower not in VALID_HABIT_CATEGORIES:
                score -= 3
                penalties.append(f"Invalid habit category: {thinking_pattern}")
        else:
            score -= 5
            penalties.append("Missing thinking pattern for mistake")
        
        # Check for multiple habits (penalty)
        feedback = item.get("feedback", item.get("coach_response", ""))
        habit_mentions = sum(1 for h in VALID_HABIT_CATEGORIES if h.replace("_", " ") in feedback.lower())
        if habit_mentions > 1:
            score -= 4
            penalties.append("Multiple habits mentioned in single explanation")
        
        # Check for vague advice
        for pattern in VAGUE_ADVICE_PATTERNS:
            if re.search(pattern, feedback, re.IGNORECASE):
                score -= 3
                penalties.append(f"Vague advice detected: {pattern}")
                break
    
    # Check weaknesses mapping
    for w in weaknesses:
        subcat = w.get("subcategory", "").lower().replace(" ", "_")
        if subcat and subcat not in VALID_WEAKNESS_SUBCATEGORIES:
            score -= 2
            penalties.append(f"Invalid weakness subcategory: {subcat}")
    
    return max(0, score), penalties


def evaluate_memory_usage(
    commentary: List[Dict],
    has_memory: bool,
    memory_callouts: List[str]
) -> Tuple[int, List[str]]:
    """
    Dimension 2: Coach Memory Usage (0-20)
    
    Checks:
    - If past memory exists → it is referenced
    - Memory reference is factual and calm
    - No exaggeration or shaming
    """
    score = 20
    penalties = []
    
    # Check if memory exists but not referenced
    if has_memory:
        memory_referenced = False
        for item in commentary:
            memory_note = item.get("memory_note", item.get("memory_reference", ""))
            if memory_note:
                memory_referenced = True
                
                # Check for exaggeration
                for pattern in EXAGGERATION_PATTERNS:
                    if re.search(pattern, memory_note, re.IGNORECASE):
                        score -= 5
                        penalties.append(f"Exaggeration in memory reference: {pattern}")
                        break
                
                # Check for shaming
                for pattern in SHAME_PATTERNS:
                    if re.search(pattern, memory_note, re.IGNORECASE):
                        score -= 5
                        penalties.append("Shaming language in memory reference")
                        break
        
        if not memory_referenced and memory_callouts:
            score -= 8
            penalties.append("Memory exists but not referenced in any explanation")
    
    return max(0, score), penalties


def evaluate_clarity_simplicity(
    commentary: List[Dict],
    summary_p1: str,
    summary_p2: str
) -> Tuple[int, List[str]]:
    """
    Dimension 3: Clarity & Simplicity (0-20)
    
    Checks:
    - Short sentences
    - Simple English
    - No engine or academic language
    """
    score = 20
    penalties = []
    
    all_text = []
    for item in commentary:
        all_text.append(item.get("feedback", item.get("coach_response", "")))
        all_text.append(item.get("intent", item.get("player_intention", "")))
    all_text.append(summary_p1)
    all_text.append(summary_p2)
    
    combined_text = " ".join(all_text)
    
    # Check for engine language
    for pattern in ENGINE_LANGUAGE_PATTERNS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            score -= 5
            penalties.append(f"Engine language detected: {pattern}")
    
    # Check sentence length (average)
    sentences = re.split(r'[.!?]+', combined_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if sentences:
        avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_words > 25:
            score -= 5
            penalties.append(f"Sentences too long (avg {avg_words:.1f} words)")
        elif avg_words > 20:
            score -= 2
            penalties.append(f"Sentences slightly long (avg {avg_words:.1f} words)")
    
    # Check for complex vocabulary (basic heuristic: long words)
    words = combined_text.split()
    long_words = [w for w in words if len(w) > 12]
    if len(long_words) > 5:
        score -= 3
        penalties.append(f"Too many complex words: {len(long_words)}")
    
    return max(0, score), penalties


def evaluate_consistency(
    commentary: List[Dict],
    weaknesses: List[Dict],
    past_rules: List[str]
) -> Tuple[int, List[str]]:
    """
    Dimension 4: Consistency with Past Advice (0-15)
    
    Checks:
    - Advice aligns with past rules
    - No contradiction
    - Intentional repetition
    """
    score = 15
    penalties = []
    
    # Extract current rules
    current_rules = []
    for item in commentary:
        details = item.get("details", item.get("explanation", {}))
        rule = details.get("rule", details.get("one_repeatable_rule", ""))
        if rule:
            current_rules.append(rule.lower())
    
    # For now, we check that rules are not contradictory in the same game
    # This is a simplified check - full consistency would require storing past rules
    
    # Check for wildly different advice for same weakness type
    weakness_rules = {}
    for item in commentary:
        details = item.get("details", item.get("explanation", {}))
        pattern = details.get("thinking_pattern", "")
        rule = details.get("rule", "")
        
        if pattern and rule:
            if pattern in weakness_rules:
                # Same pattern should have similar rule
                existing_rule = weakness_rules[pattern]
                # Very basic similarity check - if completely different length, flag it
                if abs(len(existing_rule) - len(rule)) > 50:
                    score -= 3
                    penalties.append(f"Inconsistent rules for {pattern}")
            else:
                weakness_rules[pattern] = rule
    
    return max(0, score), penalties


def evaluate_emotional_tone(
    commentary: List[Dict],
    summary_p1: str,
    summary_p2: str
) -> Tuple[int, List[str]]:
    """
    Dimension 5: Emotional Tone (0-10)
    
    Checks:
    - Firm but supportive
    - Calm authority
    - No hype, no shaming
    """
    score = 10
    penalties = []
    
    all_text = []
    for item in commentary:
        all_text.append(item.get("feedback", item.get("coach_response", "")))
    all_text.append(summary_p1)
    all_text.append(summary_p2)
    
    combined_text = " ".join(all_text)
    
    # Check for hype
    for pattern in HYPE_PATTERNS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            score -= 3
            penalties.append(f"Hype language detected: {pattern}")
    
    # Check for shaming
    for pattern in SHAME_PATTERNS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            score -= 4
            penalties.append(f"Shaming language detected: {pattern}")
    
    # Check for excessive exclamation marks (sign of hype)
    exclamation_count = combined_text.count("!")
    if exclamation_count > 3:
        score -= 2
        penalties.append(f"Too many exclamation marks: {exclamation_count}")
    
    return max(0, score), penalties


def evaluate_actionability(commentary: List[Dict]) -> Tuple[int, List[str]]:
    """
    Dimension 6: Actionability (0-10)
    
    Checks:
    - Clear "what to do next time"
    - One repeatable rule exists
    - Advice applies beyond this position
    """
    score = 10
    penalties = []
    
    mistake_count = 0
    rules_count = 0
    
    for item in commentary:
        eval_type = item.get("evaluation", "")
        if eval_type in ["blunder", "mistake", "inaccuracy"]:
            mistake_count += 1
            
            details = item.get("details", item.get("explanation", {}))
            rule = details.get("rule", details.get("one_repeatable_rule", ""))
            
            if rule and len(rule) > 10:
                rules_count += 1
                
                # Check if rule is position-specific (mentions specific squares/pieces)
                if re.search(r'\b[a-h][1-8]\b', rule):
                    score -= 2
                    penalties.append("Rule mentions specific squares (position-specific)")
            else:
                score -= 3
                penalties.append("Missing or too short rule for mistake")
    
    # Should have rule for majority of mistakes
    if mistake_count > 0 and rules_count < mistake_count * 0.7:
        score -= 2
        penalties.append(f"Only {rules_count}/{mistake_count} mistakes have rules")
    
    return max(0, score), penalties


def calculate_cqs(
    analysis_data: Dict[str, Any],
    has_memory: bool = False,
    memory_callouts: List[str] = None,
    past_rules: List[str] = None
) -> Dict[str, Any]:
    """
    Calculate the full Coach Quality Score.
    
    Returns:
    {
        "total_score": 0-100,
        "breakdown": {
            "habit_focus": {"score": 0-25, "penalties": []},
            "memory_usage": {"score": 0-20, "penalties": []},
            "clarity": {"score": 0-20, "penalties": []},
            "consistency": {"score": 0-15, "penalties": []},
            "tone": {"score": 0-10, "penalties": []},
            "actionability": {"score": 0-10, "penalties": []}
        },
        "quality_level": "accept" | "warning" | "reject",
        "should_regenerate": bool
    }
    """
    if memory_callouts is None:
        memory_callouts = []
    if past_rules is None:
        past_rules = []
    
    commentary = analysis_data.get("commentary", [])
    weaknesses = analysis_data.get("identified_weaknesses", [])
    summary_p1 = analysis_data.get("summary_p1", analysis_data.get("overall_summary", ""))
    summary_p2 = analysis_data.get("summary_p2", "")
    
    # Calculate each dimension
    habit_score, habit_penalties = evaluate_habit_focus(commentary, weaknesses)
    memory_score, memory_penalties = evaluate_memory_usage(commentary, has_memory, memory_callouts)
    clarity_score, clarity_penalties = evaluate_clarity_simplicity(commentary, summary_p1, summary_p2)
    consistency_score, consistency_penalties = evaluate_consistency(commentary, weaknesses, past_rules)
    tone_score, tone_penalties = evaluate_emotional_tone(commentary, summary_p1, summary_p2)
    action_score, action_penalties = evaluate_actionability(commentary)
    
    total_score = habit_score + memory_score + clarity_score + consistency_score + tone_score + action_score
    
    # Determine quality level
    if total_score >= ACCEPT_THRESHOLD:
        quality_level = "accept"
        should_regenerate = False
    elif total_score >= WARNING_THRESHOLD:
        quality_level = "warning"
        should_regenerate = False
    else:
        quality_level = "reject"
        should_regenerate = True
    
    return {
        "total_score": total_score,
        "breakdown": {
            "habit_focus": {"score": habit_score, "max": 25, "penalties": habit_penalties},
            "memory_usage": {"score": memory_score, "max": 20, "penalties": memory_penalties},
            "clarity": {"score": clarity_score, "max": 20, "penalties": clarity_penalties},
            "consistency": {"score": consistency_score, "max": 15, "penalties": consistency_penalties},
            "tone": {"score": tone_score, "max": 10, "penalties": tone_penalties},
            "actionability": {"score": action_score, "max": 10, "penalties": action_penalties}
        },
        "quality_level": quality_level,
        "should_regenerate": should_regenerate
    }


def get_stricter_prompt_constraints(attempt: int) -> str:
    """
    Generate stricter constraints for regeneration attempts.
    """
    if attempt == 1:
        return """
REGENERATION ATTEMPT - STRICTER RULES:
- Keep ALL explanations under 2 sentences
- ONE habit per mistake, no exceptions
- Simple words only (no words over 10 letters)
- Rule must be under 15 words
- No exclamation marks
"""
    else:
        return """
FINAL REGENERATION - MAXIMUM STRICTNESS:
- ONE sentence per explanation
- Only use these words: good, solid, focus, think, habit, practice, improve
- Rule must be under 10 words
- Zero embellishment
- Direct instruction only
"""


def should_accept_after_regenerations(
    scores: List[int],
    max_attempts: int = MAX_REGENERATIONS
) -> Tuple[bool, int]:
    """
    Determine if we should accept after multiple regeneration attempts.
    
    Returns: (should_accept, best_score_index)
    """
    if not scores:
        return False, -1
    
    best_score = max(scores)
    best_index = scores.index(best_score)
    
    # If any score is acceptable, accept
    if best_score >= WARNING_THRESHOLD:
        return True, best_index
    
    # If we've exhausted regenerations and best is above critical, accept with logging
    if len(scores) >= max_attempts and best_score >= CRITICAL_THRESHOLD:
        logger.warning(f"Accepting sub-optimal explanation after {len(scores)} attempts. Best score: {best_score}")
        return True, best_index
    
    # If below critical after all attempts, still accept best but flag
    if len(scores) >= max_attempts:
        logger.error(f"CRITICAL: All regeneration attempts failed. Best score: {best_score}")
        return True, best_index
    
    return False, best_index


def log_cqs_result(
    game_id: str,
    cqs_result: Dict[str, Any],
    attempt: int,
    accepted: bool
):
    """
    Log CQS result for internal monitoring.
    """
    score = cqs_result["total_score"]
    level = cqs_result["quality_level"]
    
    log_msg = f"CQS [{game_id}] Attempt {attempt}: Score={score} Level={level} Accepted={accepted}"
    
    if level == "accept":
        logger.info(log_msg)
    elif level == "warning":
        logger.warning(log_msg)
    else:
        penalties = []
        for dim, data in cqs_result["breakdown"].items():
            if data["penalties"]:
                penalties.extend(data["penalties"][:2])  # First 2 penalties per dimension
        logger.warning(f"{log_msg} Penalties: {penalties[:5]}")
