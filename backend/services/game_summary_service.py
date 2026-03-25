"""
Game Summary Service
====================

Extracts rich, human-readable summaries from V5 decryption data.
Used to show meaningful context on the Lab list page instead of "Multiple blunders".

Example outputs:
- "Missed knight fork on move 23"
- "Allowed back-rank mate threat"  
- "Pushed d5 too early in the Caro-Kann"
- "Lost the exchange to a discovered attack"
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class MistakeSummary:
    """A single mistake summary for display."""
    move_number: int
    move_san: str
    phase: str  # opening/middlegame/endgame
    severity: str  # blunder/mistake/inaccuracy
    
    # The rich description
    short_description: str  # e.g., "Missed knight fork"
    concept_type: str  # tactical/opening/endgame/positional
    concept_id: Optional[str]  # For tracking patterns
    
    # Optional deeper context
    consequence: Optional[str]  # What happened after
    learning: Optional[str]  # The transferable lesson


@dataclass 
class GameSummary:
    """Complete summary of a game's learning opportunities."""
    game_id: str
    
    # Key mistakes (1-3 most important)
    key_mistakes: List[Dict]
    
    # Aggregate stats
    total_blunders: int
    total_mistakes: int
    total_inaccuracies: int
    
    # What phase had the most issues
    problem_phase: Optional[str]  # "opening" | "middlegame" | "endgame"
    
    # Primary lesson from this game
    primary_lesson: Optional[str]
    
    # Tags for filtering
    tags: List[str]  # ["tactical", "opening_theory", "time_trouble", etc.]
    
    # Opponent mistakes (opportunities)
    opportunities: List[Dict] = field(default_factory=list)  # Opponent blunders/mistakes
    total_opp_mistakes: int = 0


def extract_game_summary(game_id: str, v5_data: List[Dict]) -> GameSummary:
    """
    Extract a rich summary from V5 decryption data.
    
    Prioritizes:
    1. Blunders with specific tactical patterns (fork, pin, back-rank)
    2. Opening theory violations
    3. Endgame technique failures
    4. Positional mistakes with clear lessons
    5. Opponent blunders (opportunities missed or taken)
    """
    if not v5_data:
        return GameSummary(
            game_id=game_id,
            key_mistakes=[],
            total_blunders=0,
            total_mistakes=0,
            total_inaccuracies=0,
            problem_phase=None,
            primary_lesson=None,
            tags=[]
        )
    
    # Collect all user mistakes AND opponent blunders
    blunders = []
    mistakes = []
    inaccuracies = []
    opp_blunders = []  # Opportunities!
    phase_issues = {"opening": 0, "middlegame": 0, "endgame": 0}
    tags = set()
    
    for move_data in v5_data:
        severity = move_data.get("severity", "good")
        phase = move_data.get("phase", "middlegame")
        
        if move_data.get("is_user_move"):
            # User mistakes
            if severity == "blunder":
                blunders.append(move_data)
                phase_issues[phase] += 3
            elif severity == "mistake":
                mistakes.append(move_data)
                phase_issues[phase] += 2
            elif severity == "inaccuracy":
                inaccuracies.append(move_data)
                phase_issues[phase] += 1
        else:
            # Opponent mistakes = your opportunities!
            if severity in ("opp_blunder", "opp_mistake"):
                opp_blunders.append(move_data)
    
    # Extract key mistakes (prioritize blunders, then mistakes)
    key_mistakes = []
    all_errors = blunders + mistakes
    
    for move_data in all_errors[:3]:  # Top 3 errors
        summary = _extract_mistake_summary(move_data)
        if summary:
            key_mistakes.append(asdict(summary))
            
            # Add tags based on concept type
            if summary.concept_type:
                tags.add(summary.concept_type)
            if summary.concept_id:
                # Extract tag from concept_id (e.g., "knight_fork" -> "fork")
                if "fork" in summary.concept_id:
                    tags.add("tactics_fork")
                elif "back_rank" in summary.concept_id:
                    tags.add("tactics_back_rank")
                elif "pin" in summary.concept_id:
                    tags.add("tactics_pin")
                elif "discovery" in summary.concept_id or "discovered" in summary.concept_id:
                    tags.add("tactics_discovery")
    
    # Extract opponent blunders as opportunities
    opportunities = []
    for opp_move in opp_blunders[:2]:  # Top 2 opportunities
        move_num = opp_move.get("move_number", 0)
        move_san = opp_move.get("move_san", "")
        cp_loss = opp_move.get("cp_loss", 0)
        severity = opp_move.get("severity", "")
        
        if severity == "opp_blunder":
            desc = f"Opponent blundered with {move_san} (move {move_num})"
        else:
            desc = f"Opponent slipped with {move_san} (move {move_num})"
        
        opportunities.append({
            "move_number": move_num,
            "move_san": move_san,
            "cp_swing": cp_loss,
            "description": desc
        })
        tags.add("had_opportunities")
    
    # Determine problem phase
    problem_phase = None
    if phase_issues:
        max_phase = max(phase_issues, key=phase_issues.get)
        if phase_issues[max_phase] > 0:
            problem_phase = max_phase
            tags.add(f"weak_{max_phase}")
    
    # Extract primary lesson from the worst mistake
    primary_lesson = None
    if key_mistakes:
        first_mistake = key_mistakes[0]
        primary_lesson = first_mistake.get("learning") or first_mistake.get("short_description")
    
    return GameSummary(
        game_id=game_id,
        key_mistakes=key_mistakes,
        total_blunders=len(blunders),
        total_mistakes=len(mistakes),
        total_inaccuracies=len(inaccuracies),
        problem_phase=problem_phase,
        primary_lesson=primary_lesson,
        tags=list(tags),
        opportunities=opportunities,  # NEW: opponent mistakes
        total_opp_mistakes=len(opp_blunders)
    )


def _extract_mistake_summary(move_data: Dict) -> Optional[MistakeSummary]:
    """
    Extract a human-readable summary from a single move's V5 data.
    
    Prioritizes specific tactical/strategic descriptions over generic ones.
    """
    move_number = move_data.get("move_number", 0)
    move_san = move_data.get("move_san", "?")
    phase = move_data.get("phase", "middlegame")
    severity = move_data.get("severity", "mistake")
    
    plan = move_data.get("plan") or {}
    concept_type = plan.get("concept_type", "positional")
    concept_id = plan.get("concept_id")
    
    # Try to get a specific description
    short_description = _get_short_description(move_data, plan)
    consequence = plan.get("consequence")
    learning = plan.get("transferable_learning")
    
    # Clean up learning text (remove fun language for list view)
    if learning:
        learning = _clean_for_list(learning)
    
    return MistakeSummary(
        move_number=move_number,
        move_san=move_san,
        phase=phase,
        severity=severity,
        short_description=short_description,
        concept_type=concept_type,
        concept_id=concept_id,
        consequence=consequence,
        learning=learning
    )


def _get_short_description(move_data: Dict, plan: Dict) -> str:
    """
    Generate a concise, specific description of the mistake.
    
    Priority order:
    1. Tactical patterns (fork, pin, back-rank)
    2. Opening theory violations  
    3. Endgame technique
    4. Plan goal
    5. Fallback to severity-based description
    """
    concept_id = plan.get("concept_id", "")
    concept_type = plan.get("concept_type", "")
    current_problem = plan.get("current_problem", "")
    goal = plan.get("goal", "")
    move_san = move_data.get("move_san", "")
    move_number = move_data.get("move_number", 0)
    severity = move_data.get("severity", "mistake")
    phase = move_data.get("phase", "middlegame")
    
    # 1. TACTICAL PATTERNS - Most specific
    if concept_id:
        concept_lower = concept_id.lower()
        
        # Forks
        if "fork" in concept_lower:
            if "knight" in concept_lower:
                return f"Allowed knight fork (move {move_number})"
            return f"Missed fork defense (move {move_number})"
        
        # Back rank
        if "back_rank" in concept_lower:
            return f"Back rank weakness (move {move_number})"
        
        # Pins
        if "pin" in concept_lower:
            return f"Fell into a pin (move {move_number})"
        
        # Discovered attacks
        if "discover" in concept_lower:
            return f"Missed discovered attack (move {move_number})"
        
        # Knight on rim
        if "knight_on_rim" in concept_lower:
            return f"Knight sidelined (move {move_number})"
        
        # Premature pawn push
        if "premature_pawn" in concept_lower:
            return f"Premature pawn push (move {move_number})"
        
        # Blocked bishop
        if "blocked_bishop" in concept_lower or "bishop" in concept_lower:
            return f"Bishop blocked (move {move_number})"
        
        # Opening theory
        if concept_type == "opening" or "theory" in concept_lower:
            return f"Opening inaccuracy (move {move_number})"
        
        # Endgame
        if concept_type == "endgame":
            return f"Endgame technique (move {move_number})"
    
    # 2. EXTRACT FROM CURRENT_PROBLEM (often has good info)
    if current_problem:
        problem_lower = current_problem.lower()
        
        # Look for tactical keywords
        if "fork" in problem_lower:
            return f"Allowed a fork (move {move_number})"
        if "back rank" in problem_lower or "backrank" in problem_lower:
            return f"Back rank exposed (move {move_number})"
        if "pin" in problem_lower:
            return f"Got pinned (move {move_number})"
        if "hanging" in problem_lower or "undefended" in problem_lower:
            return f"Left piece hanging (move {move_number})"
        if "check" in problem_lower:
            return f"Missed check threat (move {move_number})"
        if "mate" in problem_lower:
            return f"Missed mate threat (move {move_number})"
        if "trap" in problem_lower:
            return f"Fell into a trap (move {move_number})"
        
        # Opening keywords
        if "develop" in problem_lower:
            return f"Development issue (move {move_number})"
        if "castle" in problem_lower:
            return f"Castling delayed (move {move_number})"
        if "center" in problem_lower or "centre" in problem_lower:
            return f"Lost central control (move {move_number})"
    
    # 3. PHASE-BASED FALLBACK
    if phase == "opening":
        if severity == "blunder":
            return f"Opening blunder (move {move_number})"
        return f"Opening mistake (move {move_number})"
    elif phase == "endgame":
        if severity == "blunder":
            return f"Endgame blunder (move {move_number})"
        return f"Endgame slip (move {move_number})"
    
    # 4. SEVERITY-BASED FALLBACK
    if severity == "blunder":
        return f"Blunder on move {move_number}"
    return f"Mistake on move {move_number}"


def _clean_for_list(text: str) -> str:
    """
    Clean text for display in a list (remove fun language, keep it concise).
    """
    if not text:
        return ""
    
    # Remove exclamation marks and overly casual language
    text = text.replace("!", ".")
    
    # Truncate if too long
    if len(text) > 100:
        text = text[:97] + "..."
    
    return text.strip()


def get_display_summary(game_summary: GameSummary) -> Dict:
    """
    Get the display-friendly version for the Lab list.
    
    Returns:
    {
        "headline": "Missed knight fork",  # The main thing to show
        "subtext": "Opening blunder cost the game",  # Optional context
        "severity_label": "2 blunders",
        "phase_tag": "opening",
        "learning": "Watch for knight forks when pieces align"
    }
    """
    if not game_summary.key_mistakes:
        return {
            "headline": "Clean game",
            "subtext": None,
            "severity_label": None,
            "phase_tag": None,
            "learning": None
        }
    
    first_mistake = game_summary.key_mistakes[0]
    
    # Build headline from first mistake
    headline = first_mistake.get("short_description", "Needs review")
    
    # Build subtext if there are more mistakes
    subtext = None
    if len(game_summary.key_mistakes) > 1:
        second = game_summary.key_mistakes[1]
        subtext = second.get("short_description")
    
    # Severity label
    severity_label = None
    if game_summary.total_blunders > 0:
        severity_label = f"{game_summary.total_blunders} blunder{'s' if game_summary.total_blunders > 1 else ''}"
    elif game_summary.total_mistakes > 0:
        severity_label = f"{game_summary.total_mistakes} mistake{'s' if game_summary.total_mistakes > 1 else ''}"
    
    # Learning
    learning = first_mistake.get("learning") or game_summary.primary_lesson
    
    return {
        "headline": headline,
        "subtext": subtext,
        "severity_label": severity_label,
        "phase_tag": game_summary.problem_phase,
        "learning": learning
    }


async def compute_and_store_summary(db, game_id: str, user_id: str) -> Optional[Dict]:
    """
    Compute game summary from existing V5 data and store it.
    
    Called after V5 decryption is generated.
    """
    try:
        # Get the V5 data
        analysis = await db.game_analyses.find_one(
            {"game_id": game_id, "user_id": user_id},
            {"_id": 0, "decryption_v5_data": 1}
        )
        
        if not analysis or not analysis.get("decryption_v5_data"):
            logger.warning(f"No V5 data found for game {game_id}")
            return None
        
        v5_data = analysis.get("decryption_v5_data", [])
        
        # Extract summary
        summary = extract_game_summary(game_id, v5_data)
        summary_dict = asdict(summary)
        
        # Also compute display version
        display = get_display_summary(summary)
        summary_dict["display"] = display
        
        # Store it
        await db.game_analyses.update_one(
            {"game_id": game_id, "user_id": user_id},
            {"$set": {"game_summary": summary_dict}}
        )
        
        logger.info(f"Stored game summary for {game_id}: {display.get('headline')}")
        return summary_dict
        
    except Exception as e:
        logger.error(f"Failed to compute summary for {game_id}: {e}")
        return None


async def migrate_existing_summaries(db, user_id: str, limit: int = 100) -> Dict:
    """
    Migrate existing games that have V5 data but no summary.
    
    Returns stats about the migration.
    """
    stats = {"processed": 0, "updated": 0, "errors": 0}
    
    try:
        # Find games with V5 data but no summary
        cursor = db.game_analyses.find(
            {
                "user_id": user_id,
                "decryption_v5_data": {"$exists": True, "$ne": []},
                "game_summary": {"$exists": False}
            },
            {"_id": 0, "game_id": 1, "decryption_v5_data": 1}
        ).limit(limit)
        
        async for doc in cursor:
            stats["processed"] += 1
            game_id = doc.get("game_id")
            v5_data = doc.get("decryption_v5_data", [])
            
            try:
                summary = extract_game_summary(game_id, v5_data)
                summary_dict = asdict(summary)
                display = get_display_summary(summary)
                summary_dict["display"] = display
                
                await db.game_analyses.update_one(
                    {"game_id": game_id, "user_id": user_id},
                    {"$set": {"game_summary": summary_dict}}
                )
                stats["updated"] += 1
                
            except Exception as e:
                logger.error(f"Error migrating {game_id}: {e}")
                stats["errors"] += 1
        
        logger.info(f"Migration complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        stats["errors"] += 1
        return stats
