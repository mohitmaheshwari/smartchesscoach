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

from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
import logging
import re

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
    concept_type: str  # tactical/opening/endgame/long-term
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
    4. Long-term mistakes with clear lessons
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
    
    Prioritizes specific tactical/long-term descriptions over generic ones.
    """
    move_number = move_data.get("move_number", 0)
    move_san = move_data.get("move_san", "?")
    phase = move_data.get("phase", "middlegame")
    severity = move_data.get("severity", "mistake")
    
    plan = move_data.get("plan") or {}
    concept_type = plan.get("concept_type", "long-term")
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
    plan.get("goal", "")
    move_data.get("move_san", "")
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


_SCOREBOARD_FILLER = (
    "opening mistake", "opening blunder", "endgame slip", "endgame blunder",
    "blunder", "mistake", "inaccuracy", "needs review",
)


def _scoreboard_text(raw: str) -> Optional[str]:
    """Drop text that only restates what the row already shows.

    Every row prints the move number, the move and the severity badge.
    "Mistake on move 17" next to that is three repetitions and no
    information; _get_short_description falls back to it whenever no
    pattern matched. Live output read "Opening mistake (move 10)",
    "Mistake on move 17" -- filler that looks like coaching.

    Informative descriptions ("Left piece hanging", "Allowed a fork")
    are kept, minus their move-number suffix.
    """
    if not raw:
        return None
    text = re.sub(r"\s*\((?:move\s*)?\d+\)\s*$", "", str(raw)).strip()
    text = re.sub(r"\s+on move \d+\s*$", "", text).strip()
    if not text or text.lower().strip(" .") in _SCOREBOARD_FILLER:
        return None
    return text



#: The one template transferable_instruction is built from
#: (caption_pipeline.py: f"Next time, before you commit, look for a move that
#: {purpose}."). In a row the preamble is eleven identical words before the
#: only part that differs, and five rows running start the same way. Stripping
#: a KNOWN literal is safe in a way that parsing prose is not: if the template
#: is ever reworded this stops matching and the full sentence is kept.
_INSTRUCTION_PREAMBLE = "next time, before you commit, look for a move that"


def _strip_instruction_preamble(text: str) -> str:
    raw = str(text or "").strip()
    if raw.lower().startswith(_INSTRUCTION_PREAMBLE):
        rest = raw[len(_INSTRUCTION_PREAMBLE):].strip(" ,:;-—")
        if rest:
            return rest[0].upper() + rest[1:]
    return raw


def _reason_for_moment(move_data: Dict) -> Optional[str]:
    """One line of WHY, from the live caption pipeline.

    Mohit 2026-09-26, on a review whose "Where the game turned" section was
    thirteen rows of move + badge and nothing else: "this looks very very
    bad." Every row's text was None.

    The old source was _get_short_description(move_data, plan), and every
    field it reads -- plan.concept_id, plan.concept_type,
    plan.current_problem -- was emptied by the 2026-05-11 "legacy prose
    fields retired" migration. It has returned nothing since, so the section
    decayed into a tally of failures with no reasons, on games often won.

    Sources in order of how well they fit one row:

      1. caption_explanation.transferable_instruction -- purpose-built, one
         line, never restates the move. Present on 23% of moment rows.
      2. the caption's first sentence that is not pure verdict. Captions
         open with "Bb2 is a mistake." next to a MISTAKE badge on move Bb2,
         which is three repetitions of one fact; the sentence after it is
         the one that teaches. Captions are on 100% of cards.

    An earlier attempt stripped the verdict with a regex on the move name.
    It produced "Bb2 is a mistake." unchanged and "Bf6 is playable." -- the
    filler it was written to remove. Walking sentences and reusing
    _scoreboard_text, which already knows what filler looks like, needs no
    new pattern and cannot silently fail the way that one did.
    """
    explanation = move_data.get("caption_explanation") or {}
    instruction = str(explanation.get("transferable_instruction") or "").strip()
    if instruction:
        return _scoreboard_text(_strip_instruction_preamble(instruction))

    caption = str(move_data.get("caption") or "").strip()
    if not caption:
        return None
    for sentence in re.split(r"(?<=[.!?])\s+", caption):
        kept = _scoreboard_text(sentence.strip())
        if kept and not _is_bare_verdict(kept, move_data.get("move_san")):
            return kept
    return None


def _is_bare_verdict(sentence: str, move_san: Optional[str]) -> bool:
    """True when the sentence says only what the row already shows.

    "Bb2 is a mistake" beside a MISTAKE badge on move Bb2. Decided by
    counting the words that are NOT the move or a verdict word, so it does
    not depend on matching a phrasing.
    """
    words = [w.strip(".,;:—-").lower() for w in str(sentence).split()]
    san = str(move_san or "").strip().lower()
    ignorable = {
        "is", "isn't", "was", "a", "an", "the", "not", "but", "and", "quite",
        "blunder", "mistake", "inaccuracy", "playable", "fine", "okay",
        "good", "best", "serious", "major", "move", "you", "played",
        "opponent's", san,
    }
    return not [w for w in words if w and w not in ignorable]



def build_move_scoreboard(v5_data: List[Dict]) -> Dict:
    """Every mistake and blunder in the game, both sides, in move order.

    Deliberately NOT built on the stored GameSummary. That object keeps
    only the top 3 user errors and top 2 opponent ones -- right for a
    one-line Lab headline, wrong for a section whose whole point is that
    nothing is left out. It is also stored on 133 of 16,978 games, so
    reading it would mean a backfill and a second copy of a fact the
    review response already carries.

    v5_data is what the review page is already holding, so this derives
    from it at response time: no new collection, no backfill, and it
    cannot go stale against the captions shown beside it.
    """
    rows: List[Dict] = []
    if not v5_data:
        return {"moments": [], "you": {}, "opponent": {}}

    you = {"blunder": 0, "mistake": 0, "inaccuracy": 0}
    opp = {"blunder": 0, "mistake": 0}

    for move_data in v5_data:
        severity = move_data.get("severity", "good")
        is_user = bool(move_data.get("is_user_move"))

        if is_user:
            if severity not in ("blunder", "mistake", "inaccuracy"):
                continue
            you[severity] += 1
            plan = move_data.get("plan") or {}
            text = _reason_for_moment(move_data) or _scoreboard_text(
                _get_short_description(move_data, plan)
            )
            band = severity
        else:
            if severity not in ("opp_blunder", "opp_mistake"):
                continue
            band = "blunder" if severity == "opp_blunder" else "mistake"
            opp[band] += 1
            # Their slips get a reason too, now there is a real one. The old
            # objection was right -- "A chance for you here" on every
            # opponent error is a template -- but the caption on an opponent
            # card names the reply the player should have found, which is the
            # opposite of a template.
            text = _reason_for_moment(move_data)

        rows.append({
            "move_number": move_data.get("move_number", 0),
            "move_san": move_data.get("move_san", "?"),
            "side": "you" if is_user else "opponent",
            "severity": band,
            "phase": move_data.get("phase", "middlegame"),
            "text": text or None,
            "turned": bool(move_data.get("decisiveness_changed"))
            or band == "blunder",
        })

    # "Where the game turned" has to mean it. Every mistake and every
    # opponent slip put the median at SEVEN rows a game, with 24 of 150 games
    # showing fifteen or more -- a tally of failures down the side of a game
    # the player often won, which is the one thing this product does not do.
    #
    # A moment turned the game if the engine's read of who is winning moved,
    # or if it was a blunder. Median drops to two, and the fifteen-row walls
    # go from 24 games to 3.
    #
    # The counts in `you` and `opponent` are deliberately NOT filtered: those
    # are the honest totals the header shows, and hiding rows should not
    # quietly change the score.
    turning = [r for r in rows if r.get("turned")]
    for row in rows:
        row.pop("turned", None)
    for row in turning:
        row.pop("turned", None)
    turning.sort(key=lambda r: (r["move_number"], r["side"] != "you"))
    return {"moments": turning, "you": you, "opponent": opp}


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
