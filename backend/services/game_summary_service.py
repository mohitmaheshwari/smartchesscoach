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


#: A SAN at the very start of a sentence, optionally behind "Opponent's" or
#: "You played". Used to tell "this sentence is about THIS row's move" from
#: "this sentence is about some other move".
_LEADING_SAN_RE = re.compile(
    r"^(?:opponent's\s+|you\s+played\s+|their\s+)?"
    r"(O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b",
    re.IGNORECASE)

#: Any square reference. A row line that names no square and states no
#: consequence is a general remark, not something about this position.
_SQUARE_RE = re.compile(r"(?<![a-h])[a-h][1-8](?![0-9])")


#: "<move> was better / was stronger / is the stronger move ..." -- a
#: recommendation, not a claim about what that move did in this position.
_RECOMMENDS_RE = re.compile(
    r"^(?:was|is)\s+(?:the\s+)?(?:better|stronger|best|strongest|stronger\s+move)",
    re.IGNORECASE)


def _is_about_another_move(sentence: str, move_san: Optional[str]) -> bool:
    """True when the sentence opens by naming a move that is not this row's.

    Live on 2026-10-02: row "38. d3+  THEIR SLIP" carried the text "Bc5 leaves
    the bishop on c5 hanging -- you can win it with bxc5", which is about Bc5.
    Nothing checked that the borrowed sentence was about the move in the row.

    Only the LEADING move name is checked. A true consequence names the
    opponent's reply inside it ("d3+ runs into Qxh4, taking your rook") and
    must not be rejected for that.
    """
    text = str(sentence or "").strip()
    m = _LEADING_SAN_RE.match(text)
    if not m:
        return False
    lead = m.group(1).rstrip("+#").lower()
    san = str(move_san or "").strip().rstrip("+#").lower()
    if not san or lead == san:
        return False
    # Naming another move is fine when the sentence RECOMMENDS it -- "h4 was
    # better." on a Bb2 row is the point of the section, not a mistake. What is
    # wrong is a sentence that attributes an EFFECT to another move, which is
    # how "Bc5 leaves the bishop on c5 hanging" ended up on a d3+ row.
    rest = text[m.end():].lstrip()
    return not _RECOMMENDS_RE.match(rest)


def _starts_with_a_dangling_pronoun(sentence: str) -> bool:
    """True when the sentence opens with a pronoun whose referent is elsewhere.

    Live on 2026-10-02: "7. Ne4  MISTAKE  It wins the rook on a8." The "it" is
    the move the player SHOULD have made, named in the sentence before -- which
    the row does not show. Pulled out alone it reads as a claim about Ne4.
    """
    return bool(re.match(r"^(it|this|that|they|these|those)\b",
                         str(sentence or "").strip(), re.IGNORECASE))


def _is_position_specific(sentence: str) -> bool:
    """True when the line says something about THIS position.

    Either it states a consequence (the shared caption vocabulary, so there is
    no second list to drift) or it names a square. "A rook needs an open file
    or rank. Parked behind its own pawns it has almost nowhere to run." is a
    true remark about rooks in general and tells the reader nothing about the
    move beside it, so it does not qualify.
    """
    text = str(sentence or "")
    try:
        from services.caption_why_heuristics import CONSEQUENCE_RE
        if CONSEQUENCE_RE.search(text):
            return True
    except Exception:
        pass
    # "Their move leaves mate next move for you." names no square and matches
    # no consequence verb, and it is one of the most useful lines in the
    # section. A mate or a check is about this position by definition.
    if re.search(r"\b(mate|checkmate|check)\b", text, re.IGNORECASE):
        return True
    return bool(_SQUARE_RE.search(text))


#: Wordings that deny the fault the row's badge asserts. Live on 2026-10-02:
#: "39. Kf1  BLUNDER   Kf1 isn't a blunder, but bxc5 wins the bishop ...".
#: The caption is hedging its own verdict; the row cannot carry both.
#: NOTE the apostrophe class. The stored captions use U+2019, so a pattern
#: written with a plain ' matched nothing and the contradiction shipped.
_APOS = "['’]"
_DENIES_FAULT_RE = re.compile(
    rf"\b(isn{_APOS}t a (?:blunder|mistake)|is not a (?:blunder|mistake)|"
    rf"is playable|is fine|is okay|doesn{_APOS}t change much)\b", re.IGNORECASE)

#: "Bd5 isn't a blunder, but bxc5 wins the bishop on c5 for nothing" under a
#: MISTAKE badge. The hedge contradicts the badge; the clause AFTER it is the
#: real content. Removing the hedge keeps the row informative where dropping
#: the whole sentence would leave it blank.
_HEDGE_PREFIX_RE = re.compile(
    rf"^.*?\b(?:isn{_APOS}t|is not) a (?:blunder|mistake),\s*but\s+",
    re.IGNORECASE)


def _drop_hedge_prefix(sentence: str) -> str:
    """Remove the hedge, and do NOT blindly capitalise what is left.

    "Kf1 isn't a blunder, but bxc5 wins the bishop" strips to "bxc5 wins the
    bishop", and upper-casing the first letter turns bxc5 -- a pawn capture --
    into Bxc5, a bishop capture. A different move, stated as fact. The
    sentence only gets a capital when it does not start with a move.
    """
    out = _HEDGE_PREFIX_RE.sub("", str(sentence or "").strip())
    if not out:
        return out
    if _LEADING_SAN_RE.match(out):
        return out
    return out[0].upper() + out[1:]


def _contradicts_badge(sentence: str, severity: Optional[str]) -> bool:
    """True when the line denies the fault the badge already states."""
    if str(severity or "") not in ("blunder", "mistake", "serious",
                                   "opp_blunder", "opp_mistake", "opp_serious"):
        return False
    return bool(_DENIES_FAULT_RE.search(str(sentence or "")))


def _reason_for_moment(move_data: Dict) -> Optional[str]:
    """One line about the move IN THIS ROW, or nothing.

    Mohit 2026-09-26, on a section that was thirteen rows of move + badge and
    nothing else: "this looks very very bad." The fix then was to borrow a line
    from the caption pipeline. Mohit 2026-10-02, on what that produced: "this
    gives no value, without context, zero value."

    He was right, and the reason is mechanical. The first source used to be
    `caption_explanation.transferable_instruction`, which caption_pipeline
    builds as

        f"Next time, before you commit, look for a move that {best_move_why}."

    and `_strip_instruction_preamble` removes everything before
    `{best_move_why}`. What is left describes the move the player SHOULD have
    played -- printed beside the move they DID play, under a MISTAKE badge:

        7.  Ne4   MISTAKE   Attacks the rook on a8.
        24. O-O   BLUNDER   Attacks the rook on h8.
        27. b4    MISTAKE   Attacks the rook on h8.

    Ne4 does not attack the rook on a8; the recommended move does. Six of the
    fourteen rows in that screenshot read that way, and two pairs repeated
    verbatim because two positions shared a best_move_why. That source is gone.

    What is left is the caption's own sentences, filtered three ways: not a
    bare verdict (the badge already says it), not about a different move, and
    position-specific. A sentence that states what the played move let happen
    is preferred over one that merely mentions a square.

    Nothing is printed when nothing qualifies. A blank row says "no note here";
    a borrowed line says something false about the move next to it.
    """
    # The instruction is usable EXCEPT when it is the best_move_why template.
    # caption_pipeline builds that one as "Next time, before you commit, look
    # for a move that {best_move_why}." -- a property of the move NOT played,
    # which is the whole defect. Every other instruction is a real transferable
    # line and is the best single sentence available: dropping the field
    # outright cost the opponent row "Their move leaves mate next move for
    # you.", which is one of the most useful lines in the section. Matching the
    # known literal is exact; if the template is ever reworded this stops
    # matching and the line is kept, which is the safe direction.
    explanation = move_data.get("caption_explanation") or {}
    instruction = str(explanation.get("transferable_instruction") or "").strip()

    # When the instruction IS the best_move_why template, the sentence inside it
    # is true -- it is just true of the move that was NOT played. Discarding it
    # cost 28 points of coverage over 600 games (99.1% -> 70.8%), and empty rows
    # are the complaint this section started with. So attribute it instead of
    # dropping it: name the move it belongs to. "Attacks the rook on a8" beside
    # Ne4 under a MISTAKE badge was a false claim; "Qf3 was stronger -- it
    # attacks the rook on a8" is the same fact, correctly owned.
    #
    # This is the weakest of the three sources on purpose and sits below the
    # played-move consequence, which is what the reader actually asked for.
    attributed: Optional[str] = None
    if instruction.lower().startswith(_INSTRUCTION_PREAMBLE):
        why = _strip_instruction_preamble(instruction).rstrip(".")
        best = str(move_data.get("best_move_san") or "").strip()
        if why and best:
            attributed = f"{best} was stronger — it {why[0].lower() + why[1:]}."

    if instruction and not instruction.lower().startswith(_INSTRUCTION_PREAMBLE):
        kept = _scoreboard_text(instruction)
        # The instruction is NOT automatically about this position. "A rook
        # needs an open file or rank. Parked behind its own pawns it has almost
        # nowhere to run." is a true remark about rooks that told the reader
        # nothing about Bd5 under a BLUNDER badge, live on 2026-10-02. It earns
        # the row on the same terms as any caption sentence.
        if (kept and _is_position_specific(kept)
                and not _starts_with_a_dangling_pronoun(kept)
                and not _contradicts_badge(kept, move_data.get("severity"))):
            return kept

    caption = str(move_data.get("caption") or "").strip()
    if not caption:
        return attributed
    san = move_data.get("move_san")
    fallback: Optional[str] = None
    weak: Optional[str] = None
    for sentence in re.split(r"(?<=[.!?])\s+", caption):
        kept = _scoreboard_text(sentence.strip())
        if not kept or _is_bare_verdict(kept, san):
            continue
        if _is_about_another_move(kept, san):
            continue
        if _starts_with_a_dangling_pronoun(kept):
            continue
        # NOT a rejection. Position-specificity decides ORDER, not admission:
        # the filters above remove lines that are FALSE about this row, and
        # being vague is not being false. Rejecting the vague ones emptied 28%
        # of rows over 600 games -- "The bishop becomes less active here." and
        # "f5 was better." are thin, and thin beats blank. Only the instruction
        # path, where the generic principles live, still demands specificity.
        if not _is_position_specific(kept):
            if weak is None:
                weak = kept
            continue
        kept = _scoreboard_text(_drop_hedge_prefix(kept)) or kept
        if _contradicts_badge(kept, move_data.get("severity")):
            continue
        try:
            from services.caption_why_heuristics import CONSEQUENCE_RE
            if CONSEQUENCE_RE.search(kept):
                return kept
        except Exception:
            return kept
        if fallback is None:
            fallback = kept
    # Order: what the played move let happen, then anything else true about
    # this position, then the correctly-attributed better move, then the vague
    # line, then nothing.
    return fallback or attributed or weak


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

    # One sentence, one row. The reason is lifted from each card's caption, and
    # a caption still talking about an earlier opportunity repeats it: live on
    # 2026-10-02, rows 33, 34 and 39 of one game all read "bxc5 wins the bishop
    # on c5 for nothing". Three identical lines read as a bug, and only the
    # first is anchored to its own move. The later rows keep their place -- they
    # are still real moments -- they just have nothing of their own to add.
    seen: set = set()
    for row in turning:
        key = (row.get("text") or "").strip().lower()
        if not key:
            continue
        if key in seen:
            row["text"] = None
        else:
            seen.add(key)

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
