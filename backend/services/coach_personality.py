"""
Coach Personality Service - Personalized Language System
==========================================================

This service adapts coaching language based on player level and understanding.
No generic coaching - everything is tailored to who the player IS.

PLAYER LEVELS:
- Rookie (0-800): Just learning the rules, needs basic explanations
- Beginner (800-1000): Knows rules, learning basic tactics
- Casual (1000-1200): Plays for fun, understands fundamentals
- Amateur (1200-1400): Takes chess seriously, knows patterns
- Intermediate (1400-1600): Good tactical eye, needs strategic depth
- Advanced (1600-1800): Strong player, needs nuanced advice
- Expert (1800-2000): Very strong, needs master-level insights
- Master (2000+): Elite player, peer-level discussion

LANGUAGE ADAPTATION:
- Rookies: Simple words, basic concepts, lots of encouragement
- Beginners: Still simple, introduce chess terms gradually
- Casuals: Friendly tone, practical tips
- Amateurs: Can handle chess terminology, specific advice
- Intermediate+: Technical language, deeper analysis

Author: Built for hyper-personalized coaching
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class PlayerLevel(str, Enum):
    """Player skill levels based on rating and understanding"""
    ROOKIE = "rookie"          # 0-800: Just starting
    BEGINNER = "beginner"      # 800-1000: Learning basics
    CASUAL = "casual"          # 1000-1200: Plays for fun
    AMATEUR = "amateur"        # 1200-1400: Getting serious
    INTERMEDIATE = "intermediate"  # 1400-1600: Solid player
    ADVANCED = "advanced"      # 1600-1800: Strong player
    EXPERT = "expert"          # 1800-2000: Very strong
    MASTER = "master"          # 2000+: Elite


@dataclass
class PlayerProfile:
    """Complete player profile for personalized coaching"""
    level: PlayerLevel
    rating: int
    games_played: int
    
    # Understanding indicators
    knows_notation: bool = False
    knows_basic_tactics: bool = False
    knows_openings: bool = False
    knows_endgames: bool = False
    
    # Style preferences
    prefers_simple: bool = True
    prefers_hindi_english: bool = True  # Indian-English style


def get_player_level(rating: int, games_played: int = 0) -> PlayerLevel:
    """Determine player level from rating and experience"""
    
    # Very new players might not have accurate rating yet
    if games_played < 10 and rating < 1000:
        return PlayerLevel.ROOKIE
    
    if rating < 800:
        return PlayerLevel.ROOKIE
    elif rating < 1000:
        return PlayerLevel.BEGINNER
    elif rating < 1200:
        return PlayerLevel.CASUAL
    elif rating < 1400:
        return PlayerLevel.AMATEUR
    elif rating < 1600:
        return PlayerLevel.INTERMEDIATE
    elif rating < 1800:
        return PlayerLevel.ADVANCED
    elif rating < 2000:
        return PlayerLevel.EXPERT
    else:
        return PlayerLevel.MASTER


def get_level_display_name(level: PlayerLevel) -> str:
    """Get friendly display name for player level"""
    names = {
        PlayerLevel.ROOKIE: "Rookie",
        PlayerLevel.BEGINNER: "Beginner",
        PlayerLevel.CASUAL: "Casual Player",
        PlayerLevel.AMATEUR: "Amateur",
        PlayerLevel.INTERMEDIATE: "Intermediate",
        PlayerLevel.ADVANCED: "Advanced",
        PlayerLevel.EXPERT: "Expert",
        PlayerLevel.MASTER: "Master"
    }
    return names.get(level, "Player")


def get_level_emoji(level: PlayerLevel) -> str:
    """Get emoji badge for player level"""
    emojis = {
        PlayerLevel.ROOKIE: "🌱",
        PlayerLevel.BEGINNER: "🎮",
        PlayerLevel.CASUAL: "♟️",
        PlayerLevel.AMATEUR: "⭐",
        PlayerLevel.INTERMEDIATE: "🏆",
        PlayerLevel.ADVANCED: "💎",
        PlayerLevel.EXPERT: "🔥",
        PlayerLevel.MASTER: "👑"
    }
    return emojis.get(level, "♟️")


# =============================================================================
# LANGUAGE TEMPLATES BY LEVEL
# =============================================================================

class CoachLanguage:
    """
    Adapts coaching language to player level.
    
    Philosophy:
    - Rookies need hand-holding, simple words
    - Beginners need encouragement + basic terms
    - Amateurs can handle chess jargon
    - Advanced players get peer-level discussion
    """
    
    # =========================================================================
    # MISTAKE FEEDBACK (When player makes wrong move)
    # =========================================================================
    
    MISTAKE_TEMPLATES = {
        PlayerLevel.ROOKIE: {
            "gentle": "Not that one — let me show you a better move.",
            "encouragement": "Chess is tough. The mistakes start fading once you slow down.",
            "explanation_prefix": "When you moved there, ",
            "try_again": "Want to try again? No rush."
        },
        PlayerLevel.BEGINNER: {
            "gentle": "Close, but there's a better option here.",
            "encouragement": "Good thinking, but let's look closer at the board.",
            "explanation_prefix": "That move has a problem - ",
            "try_again": "Give it another shot."
        },
        PlayerLevel.CASUAL: {
            "gentle": "Not quite. The position had a better opportunity.",
            "encouragement": "I see what you were going for, but...",
            "explanation_prefix": "The issue is ",
            "try_again": "Try again - look for the threat."
        },
        PlayerLevel.AMATEUR: {
            "gentle": "Missed it. There was a stronger continuation.",
            "encouragement": "You're on the right track thinking-wise.",
            "explanation_prefix": "The tactical flaw here: ",
            "try_again": "Retry - check all captures and checks first."
        },
        PlayerLevel.INTERMEDIATE: {
            "gentle": "Not the best. The position demanded more precision.",
            "encouragement": "Reasonable idea, but calculation needed.",
            "explanation_prefix": "Critical issue: ",
            "try_again": "Again - calculate the forcing sequence."
        },
        PlayerLevel.ADVANCED: {
            "gentle": "Inaccurate. There's a more forcing line.",
            "encouragement": "The concept is fine, execution needs work.",
            "explanation_prefix": "Evaluation error: ",
            "try_again": "Recalculate - what's the refutation?"
        },
        PlayerLevel.EXPERT: {
            "gentle": "Second-best. The sharper line wins material.",
            "encouragement": "Practical choice — objectively there's better.",
            "explanation_prefix": "The improvement: ",
            "try_again": "Find the sharpest move."
        },
        PlayerLevel.MASTER: {
            "gentle": "Interesting but suboptimal.",
            "encouragement": "Creative, though the principled approach wins.",
            "explanation_prefix": "Analysis shows: ",
            "try_again": "What does the position really demand?"
        }
    }
    
    # =========================================================================
    # CORRECT MOVE FEEDBACK
    # =========================================================================
    
    CORRECT_TEMPLATES = {
        PlayerLevel.ROOKIE: {
            "praise": "Perfect — you found it.",
            "explanation": "Exactly right.",
            "next_step": "Let's see what happens next."
        },
        PlayerLevel.BEGINNER: {
            "praise": "Great find! That's the move!",
            "explanation": "You spotted the key idea.",
            "next_step": "Now watch how the game continues."
        },
        PlayerLevel.CASUAL: {
            "praise": "Nice! That's the best move.",
            "explanation": "Good calculation there.",
            "next_step": "Let's see the follow-up."
        },
        PlayerLevel.AMATEUR: {
            "praise": "Excellent! Precisely right.",
            "explanation": "You evaluated the position correctly.",
            "next_step": "The continuation is instructive."
        },
        PlayerLevel.INTERMEDIATE: {
            "praise": "Correct. Clean calculation.",
            "explanation": "You found the critical continuation.",
            "next_step": "Note the technique here."
        },
        PlayerLevel.ADVANCED: {
            "praise": "Accurate. Well calculated.",
            "explanation": "Correct assessment.",
            "next_step": "Execution follows."
        },
        PlayerLevel.EXPERT: {
            "praise": "Precise.",
            "explanation": "Optimal choice.",
            "next_step": "The winning technique:"
        },
        PlayerLevel.MASTER: {
            "praise": "Indeed.",
            "explanation": "As expected.",
            "next_step": "The technical phase:"
        }
    }
    
    # =========================================================================
    # TACTICAL CONCEPT EXPLANATIONS
    # =========================================================================
    
    TACTIC_EXPLANATIONS = {
        "fork": {
            PlayerLevel.ROOKIE: "A fork is when one piece attacks TWO enemy pieces at once. Like magic - they can only save one!",
            PlayerLevel.BEGINNER: "Fork! One piece threatening two targets. The enemy can only defend one.",
            PlayerLevel.CASUAL: "Classic fork pattern - attacking two pieces simultaneously.",
            PlayerLevel.AMATEUR: "Fork opportunity - exploiting the alignment of enemy pieces.",
            PlayerLevel.INTERMEDIATE: "Forking attack wins material by tempo.",
            PlayerLevel.ADVANCED: "Fork motif - standard pattern recognition.",
            PlayerLevel.EXPERT: "Standard fork.",
            PlayerLevel.MASTER: "Fork."
        },
        "pin": {
            PlayerLevel.ROOKIE: "A pin is when a piece is 'stuck' - it can't move because a more valuable piece is behind it!",
            PlayerLevel.BEGINNER: "Pin! The piece can't move without exposing the piece behind it.",
            PlayerLevel.CASUAL: "Pinned piece - can't move or the king/queen gets taken.",
            PlayerLevel.AMATEUR: "Absolute/relative pin restricting the piece's mobility.",
            PlayerLevel.INTERMEDIATE: "Pin exploits the geometric relationship.",
            PlayerLevel.ADVANCED: "Pin along the file/diagonal.",
            PlayerLevel.EXPERT: "Pin.",
            PlayerLevel.MASTER: "Pin."
        },
        "discovery": {
            PlayerLevel.ROOKIE: "A discovered attack is sneaky - you move one piece to REVEAL an attack from another piece hiding behind!",
            PlayerLevel.BEGINNER: "Discovered attack! Moving one piece unveils another's attack.",
            PlayerLevel.CASUAL: "Discovery - the moved piece reveals the real threat.",
            PlayerLevel.AMATEUR: "Discovered attack pattern - dual threats.",
            PlayerLevel.INTERMEDIATE: "Discovery creates multiple threats.",
            PlayerLevel.ADVANCED: "Discovered attack mechanism.",
            PlayerLevel.EXPERT: "Discovery.",
            PlayerLevel.MASTER: "Discovery."
        },
        "back_rank": {
            PlayerLevel.ROOKIE: "Back rank mate! The king is trapped by his own pieces and the rook/queen delivers checkmate!",
            PlayerLevel.BEGINNER: "Back rank weakness - king trapped with no escape squares.",
            PlayerLevel.CASUAL: "Back rank mate threat - need to make a luft (escape square).",
            PlayerLevel.AMATEUR: "Back rank vulnerability - h6/h3 was needed earlier.",
            PlayerLevel.INTERMEDIATE: "Exploiting the weak back rank.",
            PlayerLevel.ADVANCED: "Back rank motif.",
            PlayerLevel.EXPERT: "Back rank.",
            PlayerLevel.MASTER: "Mate pattern."
        },
        "hanging_piece": {
            PlayerLevel.ROOKIE: "Oh no! That piece has no protection - it's just hanging there waiting to be taken!",
            PlayerLevel.BEGINNER: "Undefended piece alert! Always check if your pieces are protected.",
            PlayerLevel.CASUAL: "Hanging piece - wasn't defended.",
            PlayerLevel.AMATEUR: "Piece left en prise.",
            PlayerLevel.INTERMEDIATE: "Undefended piece oversight.",
            PlayerLevel.ADVANCED: "Loose piece.",
            PlayerLevel.EXPERT: "Hanging.",
            PlayerLevel.MASTER: "En prise."
        }
    }
    
    # =========================================================================
    # OPENING EXPLANATIONS
    # =========================================================================
    
    OPENING_TIPS = {
        PlayerLevel.ROOKIE: [
            "Try to control the center with your pawns (d4, e4)",
            "Get your knights and bishops out early",
            "Castle your king to keep it safe",
            "Don't move the same piece twice in the opening",
            "Connect your rooks by developing all pieces"
        ],
        PlayerLevel.BEGINNER: [
            "Central control is key - e4/d4 pawns fight for the middle",
            "Develop knights before bishops usually",
            "Castle early, preferably before move 10",
            "Don't bring your queen out too early",
            "Complete development before attacking"
        ],
        PlayerLevel.CASUAL: [
            "Fight for central squares with pawns and pieces",
            "Piece development > pawn grabbing",
            "King safety through timely castling",
            "Create a harmonious piece setup",
            "Look for tactical opportunities while developing"
        ],
        PlayerLevel.AMATEUR: [
            "Central pawn structure determines the middlegame",
            "Develop with a plan - know your typical setups",
            "Castle to the safer side based on pawn structure",
            "Piece coordination over individual piece activity",
            "Don't fall for opening traps - know the main lines"
        ],
        PlayerLevel.INTERMEDIATE: [
            "Opening theory provides optimal piece placement",
            "Understand the ideas, not just the moves",
            "Pawn structure commits you to certain plans",
            "Know when to deviate from theory",
            "Recognize transpositions between openings"
        ],
        PlayerLevel.ADVANCED: [
            "Opening preparation is crucial at this level",
            "Understand typical middlegame plans from each opening",
            "Study model games in your repertoire",
            "Have sidelines ready for critical variations",
            "Opening novelties can give practical chances"
        ],
        PlayerLevel.EXPERT: [
            "Deep theoretical knowledge expected",
            "Prepare concrete lines against opponents",
            "Understand pawn structure nuances",
            "Opening edges can last into endgames",
            "Psychology in opening choice matters"
        ],
        PlayerLevel.MASTER: [
            "Opening is about reaching playable middlegames",
            "Novelty preparation is part of the game",
            "Opening choice reflects playing style",
            "Practical considerations often trump theory",
            "Model games inform understanding"
        ]
    }
    
    # =========================================================================
    # MILESTONE MESSAGES
    # =========================================================================
    
    MILESTONES = {
        "first_game": {
            PlayerLevel.ROOKIE: "Welcome to your chess journey! I'm your coach. Let's learn together, one move at a time.",
            PlayerLevel.BEGINNER: "Let's review your game! I'll help you spot the key moments.",
            PlayerLevel.CASUAL: "Ready to analyze? Let's find what went right and where to improve.",
            PlayerLevel.AMATEUR: "Game review time. Let's dig into the critical positions.",
            PlayerLevel.INTERMEDIATE: "Let's analyze. I'll highlight the key decisions.",
            PlayerLevel.ADVANCED: "Let's examine the key moments.",
            PlayerLevel.EXPERT: "Analysis time.",
            PlayerLevel.MASTER: "Shall we review?"
        },
        "games_10": {
            PlayerLevel.ROOKIE: "10 games together! You're really getting the hang of chess basics!",
            PlayerLevel.BEGINNER: "10 games! Your tactical awareness is improving!",
            PlayerLevel.CASUAL: "10 games analyzed! I'm seeing your style develop.",
            PlayerLevel.AMATEUR: "10 games in. Your patterns are becoming clearer.",
            PlayerLevel.INTERMEDIATE: "10 games of data. Your profile is taking shape.",
            PlayerLevel.ADVANCED: "10-game milestone. Trends are emerging.",
            PlayerLevel.EXPERT: "10 games analyzed.",
            PlayerLevel.MASTER: "10 games in the database."
        },
        "games_50": {
            PlayerLevel.ROOKIE: "50 games! From not knowing the rules to playing real chess - proud of you!",
            PlayerLevel.BEGINNER: "50 games! You've come so far from the beginning!",
            PlayerLevel.CASUAL: "50 games! I know your game pretty well now.",
            PlayerLevel.AMATEUR: "50 games analyzed. I understand your strengths and weaknesses.",
            PlayerLevel.INTERMEDIATE: "50 games. We have solid data on your tendencies.",
            PlayerLevel.ADVANCED: "50 games. Your profile is well-established.",
            PlayerLevel.EXPERT: "50-game benchmark reached.",
            PlayerLevel.MASTER: "50 games catalogued."
        },
        "improvement": {
            PlayerLevel.ROOKIE: "You're making fewer big mistakes! The basics are clicking!",
            PlayerLevel.BEGINNER: "Nice progress! Your blunders are going down!",
            PlayerLevel.CASUAL: "Good trend - your accuracy is improving!",
            PlayerLevel.AMATEUR: "Solid improvement in your recent games.",
            PlayerLevel.INTERMEDIATE: "Your metrics are trending positive.",
            PlayerLevel.ADVANCED: "Performance indicators improving.",
            PlayerLevel.EXPERT: "Positive trend in accuracy.",
            PlayerLevel.MASTER: "Marginal gains accumulating."
        },
        "decline": {
            PlayerLevel.ROOKIE: "Hey, we all have tough days. Let's focus on the basics again.",
            PlayerLevel.BEGINNER: "Not your best stretch. Let's slow down and refocus.",
            PlayerLevel.CASUAL: "Bit of a rough patch. Maybe take a break?",
            PlayerLevel.AMATEUR: "Results dipping. Time to revisit fundamentals.",
            PlayerLevel.INTERMEDIATE: "Form dropping. Consider your approach.",
            PlayerLevel.ADVANCED: "Negative trend. Reassess your preparation.",
            PlayerLevel.EXPERT: "Performance dip noted.",
            PlayerLevel.MASTER: "Results not matching expectations."
        }
    }
    
    # =========================================================================
    # POSITION HINTS (For Critical Moments)
    # =========================================================================
    
    POSITION_HINT_TEMPLATES = {
        PlayerLevel.ROOKIE: "Look carefully: {hint}. What piece can help here?",
        PlayerLevel.BEGINNER: "Hint: {hint}. Find the right piece to move.",
        PlayerLevel.CASUAL: "{hint}. What's the best response?",
        PlayerLevel.AMATEUR: "{hint}",
        PlayerLevel.INTERMEDIATE: "{hint}",
        PlayerLevel.ADVANCED: "{hint}",
        PlayerLevel.EXPERT: "{hint}",
        PlayerLevel.MASTER: "{hint}"
    }
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    @classmethod
    def get_mistake_feedback(cls, level: PlayerLevel, mistake_type: str = "general") -> Dict[str, str]:
        """Get appropriate mistake feedback for player level"""
        return cls.MISTAKE_TEMPLATES.get(level, cls.MISTAKE_TEMPLATES[PlayerLevel.CASUAL])
    
    @classmethod
    def get_correct_feedback(cls, level: PlayerLevel) -> Dict[str, str]:
        """Get appropriate praise for player level"""
        return cls.CORRECT_TEMPLATES.get(level, cls.CORRECT_TEMPLATES[PlayerLevel.CASUAL])
    
    @classmethod
    def explain_tactic(cls, tactic: str, level: PlayerLevel) -> str:
        """Get tactic explanation appropriate for player level"""
        tactic_lower = tactic.lower().replace("_", "").replace("-", "").replace(" ", "")
        
        # Map variations to standard names
        tactic_map = {
            "fork": "fork",
            "missedtork": "fork",
            "missedfork": "fork",
            "pin": "pin",
            "missedpin": "pin",
            "discovery": "discovery",
            "discoveredattack": "discovery",
            "misseddiscovery": "discovery",
            "backrank": "back_rank",
            "backrankmate": "back_rank",
            "missedbackrank": "back_rank",
            "hanging": "hanging_piece",
            "hangingpiece": "hanging_piece",
            "loose": "hanging_piece",
            "enprise": "hanging_piece"
        }
        
        tactic_key = tactic_map.get(tactic_lower, "hanging_piece")
        explanations = cls.TACTIC_EXPLANATIONS.get(tactic_key, cls.TACTIC_EXPLANATIONS["hanging_piece"])
        
        return explanations.get(level, explanations[PlayerLevel.CASUAL])
    
    @classmethod
    def get_opening_tip(cls, level: PlayerLevel, tip_index: int = 0) -> str:
        """Get an opening tip appropriate for player level"""
        tips = cls.OPENING_TIPS.get(level, cls.OPENING_TIPS[PlayerLevel.CASUAL])
        return tips[tip_index % len(tips)]
    
    @classmethod
    def get_milestone_message(cls, milestone: str, level: PlayerLevel) -> str:
        """Get milestone message for player level"""
        messages = cls.MILESTONES.get(milestone, {})
        return messages.get(level, "Milestone reached!")
    
    @classmethod
    def format_position_hint(cls, hint: str, level: PlayerLevel) -> str:
        """Format position hint for player level"""
        template = cls.POSITION_HINT_TEMPLATES.get(level, "{hint}")
        return template.format(hint=hint)


# =============================================================================
# COACHING VOICE ADAPTER
# =============================================================================

class CoachVoice:
    """
    Adapts the overall coaching voice/personality to player level.
    
    - Rookies: Warm, patient, encouraging, simple words
    - Beginners: Supportive, teaching, gradual complexity
    - Casuals: Friendly, practical, balanced
    - Amateurs: Professional, direct, chess-focused
    - Intermediate+: Peer-level, technical, efficient
    """
    
    @staticmethod
    def get_voice_style(level: PlayerLevel) -> Dict[str, Any]:
        """Get coaching voice characteristics for a player level"""
        
        styles = {
            PlayerLevel.ROOKIE: {
                "tone": "warm_encouraging",
                "complexity": "very_simple",
                "use_jargon": False,
                "explanation_depth": "basic",
                "patience_level": "high",
                "encouragement_frequency": "high",
                "example_usage": "many",
                "assume_knowledge": False,
                "formality": "casual",
                "personality": "Like a friendly teacher explaining to a kid"
            },
            PlayerLevel.BEGINNER: {
                "tone": "supportive_teaching",
                "complexity": "simple",
                "use_jargon": False,
                "explanation_depth": "moderate",
                "patience_level": "high",
                "encouragement_frequency": "moderate",
                "example_usage": "some",
                "assume_knowledge": False,
                "formality": "casual",
                "personality": "Patient tutor building confidence"
            },
            PlayerLevel.CASUAL: {
                "tone": "friendly_helpful",
                "complexity": "moderate",
                "use_jargon": True,  # With explanations
                "explanation_depth": "moderate",
                "patience_level": "moderate",
                "encouragement_frequency": "moderate",
                "example_usage": "when_needed",
                "assume_knowledge": True,  # Basic rules
                "formality": "casual",
                "personality": "Chess buddy who knows a bit more"
            },
            PlayerLevel.AMATEUR: {
                "tone": "professional_friendly",
                "complexity": "moderate_high",
                "use_jargon": True,
                "explanation_depth": "detailed",
                "patience_level": "moderate",
                "encouragement_frequency": "low",
                "example_usage": "when_relevant",
                "assume_knowledge": True,  # Tactics, basic strategy
                "formality": "semi_formal",
                "personality": "Club player sharing insights"
            },
            PlayerLevel.INTERMEDIATE: {
                "tone": "direct_analytical",
                "complexity": "high",
                "use_jargon": True,
                "explanation_depth": "detailed",
                "patience_level": "low",
                "encouragement_frequency": "low",
                "example_usage": "reference_only",
                "assume_knowledge": True,  # Significant chess knowledge
                "formality": "semi_formal",
                "personality": "Experienced coach, no fluff"
            },
            PlayerLevel.ADVANCED: {
                "tone": "technical_precise",
                "complexity": "high",
                "use_jargon": True,
                "explanation_depth": "concise",
                "patience_level": "low",
                "encouragement_frequency": "minimal",
                "example_usage": "minimal",
                "assume_knowledge": True,  # Deep chess understanding
                "formality": "formal",
                "personality": "IM/FM level peer discussion"
            },
            PlayerLevel.EXPERT: {
                "tone": "analytical_efficient",
                "complexity": "very_high",
                "use_jargon": True,
                "explanation_depth": "minimal",
                "patience_level": "minimal",
                "encouragement_frequency": "none",
                "example_usage": "none",
                "assume_knowledge": True,
                "formality": "formal",
                "personality": "Grandmaster analysis style"
            },
            PlayerLevel.MASTER: {
                "tone": "peer_level",
                "complexity": "expert",
                "use_jargon": True,
                "explanation_depth": "minimal",
                "patience_level": "minimal",
                "encouragement_frequency": "none",
                "example_usage": "none",
                "assume_knowledge": True,
                "formality": "professional",
                "personality": "Elite peer discussion"
            }
        }
        
        return styles.get(level, styles[PlayerLevel.CASUAL])
    
    @staticmethod
    def get_prompt_prefix(level: PlayerLevel, player_name: Optional[str] = None) -> str:
        """Get the prompt prefix that sets the coaching voice"""
        
        name = player_name or "the player"
        # Note: voice style is implicitly embedded in the prefixes below
        
        prefixes = {
            PlayerLevel.ROOKIE: f"""You are a warm, patient chess coach for {name}, a complete beginner (rookie level).

VOICE GUIDELINES:
- Use SIMPLE words. No chess jargon without explanation.
- Be very encouraging. Celebrate small wins.
- Explain concepts like you would to a kid.
- Use analogies and simple examples.
- Never assume they know chess terms.
- Be patient with mistakes - they're learning.
- Keep sentences short and clear.

Example tone: "Great try! See that knight? It's attacking two pieces at once - that's called a fork! Like a fork at dinner picking up two things!"
""",
            
            PlayerLevel.BEGINNER: f"""You are a supportive chess coach for {name}, a beginner player.

VOICE GUIDELINES:
- Use simple language, introduce chess terms gradually.
- Be encouraging but start building proper habits.
- Explain the 'why' behind moves.
- Reference basic tactical patterns by name.
- Assume they know how pieces move.
- Patient with mistakes, but point them out clearly.

Example tone: "Nice thinking! But look - when you moved there, you left your bishop unprotected. That's called a 'hanging piece'. Let's find a safer move."
""",
            
            PlayerLevel.CASUAL: f"""You are a friendly chess coach for {name}, a casual player (~1000-1200).

VOICE GUIDELINES:
- Conversational but informative.
- Use chess terms naturally (fork, pin, etc.).
- Balance encouragement with honest feedback.
- Give practical, actionable advice.
- Assume basic tactical knowledge.
- Keep it fun but educational.

Example tone: "Ah, you missed the fork there. Knight to f3 would've hit both the queen and rook. It happens - let's see what we can learn from this."
""",
            
            PlayerLevel.AMATEUR: f"""You are a professional chess coach for {name}, an amateur player (~1200-1400).

VOICE GUIDELINES:
- Direct and analytical.
- Full use of chess terminology.
- Focus on concrete improvements.
- Point out both good and bad without sugar-coating.
- Assume solid understanding of tactics.
- Reference standard patterns and ideas.

Example tone: "The knight retreat loses a tempo. Na4 maintains pressure on c5 while keeping d5 control. Standard Italian setup - you should know this pattern."
""",
            
            PlayerLevel.INTERMEDIATE: f"""You are a chess coach for {name}, an intermediate player (~1400-1600).

VOICE GUIDELINES:
- Technical and efficient.
- Assume strong tactical foundation.
- Focus on strategic and positional concepts.
- Be direct - no hand-holding needed.
- Reference typical plans and structures.
- Expect them to calculate basic tactics.

Example tone: "Positional error. With the pawn structure fixed, knights outperform bishops here. Nd7-f8-g6 is the standard maneuver. Your move weakened the light squares unnecessarily."
""",
            
            PlayerLevel.ADVANCED: f"""You are coaching {name}, an advanced player (~1600-1800).

VOICE GUIDELINES:
- Precise and technical.
- Assume deep chess understanding.
- Focus on nuances and subtle improvements.
- Reference typical GM/IM level ideas.
- Be concise - no obvious explanations.
- Discuss evaluation differences directly.

Example tone: "Rd1 is sharper but your move is playable. You're trading a touch of precision for practical chances. Fine for rapid, questionable for classical."
""",
            
            PlayerLevel.EXPERT: f"""Analyzing with {name}, an expert player (~1800-2000).

VOICE GUIDELINES:
- Peer-level analysis.
- Assume comprehensive chess knowledge.
- Focus on critical nuances only.
- Reference advanced concepts directly.
- Be efficient with words.
- Discuss concrete variations.

Example tone: "The queenside expansion idea is correct but timing is off. After a4-a5, b6 creates a protected passed pawn. The prophylactic h3 first prevents back-rank issues in the resulting endgame."
""",
            
            PlayerLevel.MASTER: f"""Analysis with {name}, master-level player (2000+).

VOICE GUIDELINES:
- Peer discussion at highest level.
- No explanations needed for standard concepts.
- Focus only on critical decisions.
- Reference modern theory when relevant.
- Discuss practical considerations alongside objective analysis.

Example tone: "This structure favors the d5-push idea but the position after exd5 Nxd5 is double-edged. Caruana faced this against Ding - the exchange sacrifice on e3 gives Black counterplay."
"""
        }
        
        return prefixes.get(level, prefixes[PlayerLevel.CASUAL])


# =============================================================================
# API FUNCTIONS FOR USE IN SERVER
# =============================================================================

def get_personalized_coaching_context(rating: int, games_played: int) -> Dict[str, Any]:
    """
    Get complete personalized coaching context.
    
    Call this when preparing any coaching response.
    """
    level = get_player_level(rating, games_played)
    voice_style = CoachVoice.get_voice_style(level)
    
    return {
        "level": level.value,
        "level_display": get_level_display_name(level),
        "level_emoji": get_level_emoji(level),
        "voice_style": voice_style,
        "prompt_prefix": CoachVoice.get_prompt_prefix(level),
        "mistake_templates": CoachLanguage.get_mistake_feedback(level),
        "correct_templates": CoachLanguage.get_correct_feedback(level),
        "rating": rating,
        "games_played": games_played
    }


def adapt_message_to_level(message: str, level: PlayerLevel) -> str:
    """
    Adapt a generic message to player level.
    
    For when you have pre-written content that needs level adjustment.
    """
    # This is a placeholder for more sophisticated NLP-based adaptation
    # For now, it returns the message as-is
    # In production, you might use an LLM to rephrase
    return message


async def get_player_level_from_identity(player_identity) -> PlayerLevel:
    """Get player level from a player identity object"""
    return get_player_level(
        rating=player_identity.current_rating,
        games_played=player_identity.games_analyzed
    )
