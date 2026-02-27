# Chess Coach - Comprehensive Technical & Strategic Document

## Executive Summary

**Chess Coach** is an AI-powered chess improvement platform built on a fundamentally different philosophy than existing tools. While competitors focus on **WHAT went wrong** (you blundered on move 25), Chess Coach focuses on **WHY it went wrong** (you stopped calculating when you felt winning) and **HOW to fix the thinking pattern** (not the specific position).

### Core Philosophy: "Recovery-First" Coaching

Traditional chess apps treat mistakes as positions to memorize. Chess Coach treats mistakes as **cognitive patterns** to understand and rewire.

---

## Competitive Landscape Analysis

| Feature | Chess Coach | DecodeChess | Aimchess | SenseiChess | Chessvision.ai |
|---------|-------------|-------------|----------|-------------|----------------|
| **Price** | TBD | $15/mo | $9.99/mo | Free | Free (scanning) |
| **Core Focus** | Cognitive patterns | Move explanations | Weakness training | Game explanations | Diagram scanning |
| **Training Source** | YOUR blunders | Generic | YOUR games | Generic puzzles | N/A |
| **WHY Analysis** | Deep (18+ gap types) | Basic | No | Basic | No |
| **Behavioral Coaching** | Yes (psychological) | No | No | No | No |
| **Reflection System** | Yes (active recall) | No | No | No | No |
| **Player Identity** | Dynamic profile | No | Basic stats | No | No |
| **Mission System** | Gamified habits | No | Daily puzzles | No | No |
| **Post-Game Flow** | Reflection → Training | Analysis only | Analysis only | Analysis only | N/A |

### What Competitors Do Well
- **DecodeChess**: Excellent at explaining WHY a move is good (Idea-Problem-Solution)
- **Aimchess**: Good training exercises, nice UI, personalized puzzles
- **SenseiChess**: Clean interface, good explanations, free
- **Chessvision.ai**: Best-in-class diagram scanning technology

### Where They All Fall Short
1. **No cognitive diagnosis** - They say "you missed Nxf7" not "you stopped calculating when ahead"
2. **No behavioral patterns** - They don't track "relaxes when winning" across games
3. **No reflection loop** - No active recall of what you were thinking
4. **Generic training** - Puzzles are from databases, not your actual mistakes
5. **No psychological coaching** - No "overconfidence" or "panic pattern" detection

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CHESS COACH ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │   GAME IMPORT   │───▶│  STOCKFISH +    │───▶│  COGNITIVE GAP  │        │
│  │  Chess.com/     │    │  AI ANALYSIS    │    │    ANALYZER     │        │
│  │  Lichess API    │    │  (Depth 18)     │    │  (18 Gap Types) │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│           │                      │                      │                  │
│           ▼                      ▼                      ▼                  │
│  ┌─────────────────────────────────────────────────────────────────┐      │
│  │                    PLAYER PROFILE ENGINE                         │      │
│  │  - Decision Stability (stable/mixed/volatile)                    │      │
│  │  - Primary Leak (threat_blindness, calculation_depth, etc.)      │      │
│  │  - Behavioral Patterns (relaxes when winning, impulsive, etc.)   │      │
│  │  - Phase Weakness (opening/middlegame/endgame)                   │      │
│  │  - Rating Ceiling Model (stable vs peak rating)                  │      │
│  └─────────────────────────────────────────────────────────────────┘      │
│           │                      │                      │                  │
│           ▼                      ▼                      ▼                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │   REFLECTION    │    │    TRAINING     │    │    JOURNEY      │        │
│  │    ENGINE       │    │    PUZZLES      │    │   INTELLIGENCE  │        │
│  │  (What were you │    │  (From YOUR     │    │  (Progress over │        │
│  │   thinking?)    │    │   blunders)     │    │      time)      │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Differentiating Systems

### 1. Cognitive Gap Analyzer (UNIQUE)

**What it does**: Determines the PRECISE cognitive error, not just the chess mistake.

**18 Cognitive Gap Types:**

| Category | Gap Type | Description | Training Focus |
|----------|----------|-------------|----------------|
| **Calculation** | `calculation_depth` | Saw idea, didn't calculate far enough | "Calculate one move deeper" |
| **Calculation** | `calculation_error` | Made arithmetic mistake in line | Pattern recognition drills |
| **Awareness** | `threat_blindness` | Didn't see opponent's threat | "What can opponent do?" |
| **Awareness** | `hanging_piece_blindness` | Left piece undefended | Safety scan protocol |
| **Awareness** | `check_blindness` | Didn't see a check | CCT checklist |
| **Tactical** | `missed_fork` | Missed fork opportunity | Fork pattern training |
| **Tactical** | `missed_pin` | Missed pin opportunity | Pin pattern training |
| **Tactical** | `back_rank_blindness` | Missed back rank threat | Back rank awareness |
| **Positional** | `positional_misread` | Wrong assessment of needs | Positional evaluation |
| **Positional** | `wrong_plan` | Correct calc, wrong idea | Strategic thinking |
| **Defensive** | `defensive_lapse` | Forgot defense while attacking | Prophylaxis training |
| **Defensive** | `king_safety_neglect` | Ignored king safety | King safety protocols |
| **Psychological** | `overconfidence` | Assumed opponent would miss | "What's their best reply?" |
| **Psychological** | `desperation` | Hope chess when losing | Resilience training |
| **Time** | `time_pressure` | Rushed due to clock | Time management |
| **Time** | `rushed_move` | Moved too fast (not clock) | Discipline training |
| **Pattern** | `pattern_unfamiliarity` | Didn't recognize standard pattern | Pattern library |

**Pseudo-code:**
```python
def analyze_cognitive_gap(position, user_move, best_move, user_reflection):
    """
    Determine WHY the user made this mistake, not just WHAT was wrong.
    """
    facts = extract_board_facts(position)
    
    # Check for hanging pieces
    if facts.user_piece_left_hanging:
        if user_reflection.confidence == "very_sure":
            return CognitiveGap.CONFIDENCE_GAP  # Felt sure but piece was hanging
        else:
            return CognitiveGap.HANGING_PIECE_BLINDNESS
    
    # Check for missed threats
    if facts.opponent_had_forcing_move and not user_saw_threat:
        return CognitiveGap.THREAT_BLINDNESS
    
    # Check for calculation issues
    if user_saw_tactic but missed_response:
        return CognitiveGap.CALCULATION_DEPTH
    
    # Check for time pressure
    if move_time < 5_seconds and facts.complex_position:
        return CognitiveGap.TIME_PRESSURE
    
    # Check for psychological patterns
    if facts.user_was_winning and facts.accuracy_dropped:
        return CognitiveGap.OVERCONFIDENCE
```

### 2. Reflection Engine (UNIQUE)

**What it does**: Captures what the user was THINKING during the mistake (active recall).

**Why it matters**: You can't fix thinking patterns you don't understand. Other apps analyze positions; we analyze minds.

**Reflection Flow:**
```
┌──────────────────────────────────────────────────────────────────────┐
│                        REFLECTION FLOW                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   STEP 1: Position Display                                           │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  [Chess Board]  You played Nxf7 - What were you thinking? │       │
│   └─────────────────────────────────────────────────────────┘       │
│                              │                                        │
│                              ▼                                        │
│   STEP 2: Intent Capture                                             │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  What was your plan?                                      │       │
│   │  [ ] I saw a tactic                                       │       │
│   │  [ ] I wanted to attack                                   │       │
│   │  [ ] I was defending                                      │       │
│   │  [ ] I wasn't sure, made a guess                          │       │
│   └─────────────────────────────────────────────────────────┘       │
│                              │                                        │
│                              ▼                                        │
│   STEP 3: Confidence Rating                                          │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  How sure were you this was the best move?               │       │
│   │  [Very Sure] [Somewhat] [Unsure] [Guessing]              │       │
│   └─────────────────────────────────────────────────────────┘       │
│                              │                                        │
│                              ▼                                        │
│   STEP 4: Gap Diagnosis (shown to user)                              │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  "You were very sure, but there was a forcing reply     │       │
│   │   you missed. This is a CONFIDENCE GAP - a common       │       │
│   │   pattern where certainty outpaces threat scanning."    │       │
│   └─────────────────────────────────────────────────────────┘       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3. Player Identity Engine (UNIQUE)

**What it does**: Creates a dynamic, interpretive profile of the player's chess psychology.

**Identity Dimensions:**

| Dimension | Possible Values | What It Means |
|-----------|-----------------|---------------|
| **Decision Stability** | Stable, Mixed, Volatile | How consistent is accuracy game-to-game |
| **Primary Leak** | 18 cognitive gap types | The #1 recurring issue |
| **Risk Profile** | Low, Medium, High | Tendency toward risky play |
| **Phase Weakness** | Opening, Middlegame, Endgame | Where most mistakes happen |
| **Behavioral Pattern** | "Relaxes when winning", "Impulsive attacker", etc. | Psychological tendencies |

**Sample Identity Card:**
```
┌──────────────────────────────────────────────────────────┐
│  PLAYER IDENTITY: Mohit                                   │
├──────────────────────────────────────────────────────────┤
│  Decision Type: INCONSISTENT BUT CAPABLE                 │
│  "Your performance fluctuates between sessions."         │
│                                                          │
│  Primary Leak: THREAT BLINDNESS                          │
│  "Your errors often come from not seeing what your       │
│   opponent wants to do. The threat was there, but        │
│   you didn't check."                                     │
│                                                          │
│  Behavioral Pattern: RELAXES WHEN WINNING                │
│  "You lose focus immediately after gaining advantage.    │
│   56% of your blunders happen in + positions."           │
│                                                          │
│  Rating Gap: 150 ELO                                     │
│  "Fixing threat blindness alone could recover ~72        │
│   rating points based on your game data."                │
└──────────────────────────────────────────────────────────┘
```

### 4. Recovery-First Training (UNIQUE)

**What it does**: Training puzzles come from YOUR actual blunders, not generic databases.

**Training Flow:**
```
Traditional App:                    Chess Coach:
┌─────────────────┐                ┌─────────────────┐
│ Generic puzzle  │                │ Your game from  │
│ from database   │                │ yesterday       │
└────────┬────────┘                └────────┬────────┘
         │                                  │
         ▼                                  ▼
┌─────────────────┐                ┌─────────────────┐
│ "Find the best  │                │ "You played     │
│  move"          │                │  Nxf7 here.     │
│                 │                │  Why was it     │
│                 │                │  bad?"          │
└────────┬────────┘                └────────┬────────┘
         │                                  │
         ▼                                  ▼
┌─────────────────┐                ┌─────────────────┐
│ "Correct! The   │                │ "Show Why Bad"  │
│  answer was     │                │ [Animates the   │
│  Qxh7+"         │                │  opponent's     │
│                 │                │  refutation]    │
└─────────────────┘                └────────┬────────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │ "This was a     │
                                   │  THREAT         │
                                   │  BLINDNESS gap. │
                                   │  Let's train    │
                                   │  that pattern." │
                                   └─────────────────┘
```

### 5. Rich Coach Audit (UNIQUE)

**What it does**: Combines ALL user data to provide deep, personalized game analysis.

**Data Sources Combined:**
1. **Stockfish Analysis** - What happened tactically
2. **Cognitive Gap History** - User's thinking patterns from reflections
3. **Pattern Recurrence** - Recurring mistakes over time
4. **Skill Trends** - How user is progressing
5. **Historical Baseline** - How this game compares to typical performance
6. **Opening Repertoire** - User's opening choices and success rates
7. **Time Management** - Clock usage patterns

**Output Example:**
```
┌──────────────────────────────────────────────────────────────────┐
│  COACH AUDIT: Game vs kurapikagon00                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PERFORMANCE vs YOUR BASELINE:                                   │
│  • Accuracy: 74.8% (above your 68% average) ↑                   │
│  • Blunders: 1 (below your 1.9 average) ↑                       │
│  • This was a CLEAN GAME for you                                │
│                                                                  │
│  RECURRING PATTERN ALERT:                                        │
│  "You missed an opponent threat again - this is the 3rd         │
│   time this week. Before EVERY move, ask: 'What does my         │
│   opponent want to do?'"                                        │
│                                                                  │
│  WHAT'S IMPROVING:                                               │
│  • Opening accuracy is up 12% from last month                   │
│  • You're hanging fewer pieces (down from 2.1 to 0.8/game)      │
│                                                                  │
│  NEXT GAME PLAN:                                                 │
│  1. Before each move, scan opponent's threats                   │
│  2. When ahead by material, SIMPLIFY - don't attack             │
│  3. Take 10 extra seconds on moves 15-25 (your danger zone)     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Models

### Core Collections

```javascript
// player_profiles - Dynamic player psychology
{
  user_id: "user_123",
  
  // Identity dimensions
  decision_stability: "mixed",      // stable | mixed | volatile
  primary_leak: "threat_blindness", // Cognitive gap type
  behavioral_patterns: [
    { pattern: "relaxes_when_winning", occurrence_pct: 56 }
  ],
  
  // Weakness tracking with decay
  top_weaknesses: [
    {
      category: "tactical",
      subcategory: "one_move_blunder",
      occurrence_count: 100,
      decayed_score: 85.2,  // Time-decayed relevance
      last_occurrence: ISODate()
    }
  ],
  
  // Progress tracking
  games_analyzed_count: 135,
  total_blunders: 193,
  improvement_trend: "improving",  // improving | stuck | declining
  
  // Coaching preferences (learned)
  learning_style: "concise",
  coaching_tone: "direct"
}

// cognitive_gap_history - What users were thinking
{
  user_id: "user_123",
  game_id: "game_456",
  move_number: 25,
  
  // The mistake
  position_fen: "rnbqkb1r/...",
  user_move: "Nxf7",
  best_move: "Qd2",
  cp_loss: 345,
  
  // User's reflection
  intent: "saw_tactic",
  confidence: "very_sure",
  time_spent: 45,  // seconds
  
  // Diagnosed gap
  gap_type: "threat_blindness",
  evidence: "Opponent had Bxf2+ winning exchange",
  coaching_focus: "Opponent threat awareness"
}

// reflection_sessions - Active recall data
{
  user_id: "user_123",
  game_id: "game_456",
  
  moments_reflected: [
    {
      move_number: 25,
      user_response: {...},
      gap_diagnosed: "threat_blindness",
      aligned: false  // Did user's perception match reality?
    }
  ],
  
  session_insights: {
    confidence_calibration: "overconfident",  // User thought they knew but didn't
    primary_issue: "threat_awareness"
  }
}
```

---

## Unique Algorithms

### 1. Awareness Gap Detection

```python
# Deterministic rules for detecting perception-reality mismatch
GAP_RULES = [
    {
        "rule_id": "confidence_gap_forcing",
        "conditions": {
            "confidence": ["very_sure"],
            "facts": ["opponent_has_forcing_move", "user_ignored_forcing"]
        },
        "gap_type": "CONFIDENCE_GAP",
        "headline": "You were very sure, but there was a forcing reply you missed."
    },
    {
        "rule_id": "panic_pattern",
        "conditions": {
            "confidence": ["guessing"],
            "facts": ["time_pressure_detected"]
        },
        "gap_type": "PANIC_PATTERN",
        "headline": "This looks like a time-pressure decision, not a calculation miss."
    },
    # ... 20+ more rules
]
```

### 2. Rating Ceiling Model

```python
def compute_rating_ceiling(analyses):
    """
    Estimate player's 'true' rating if they fixed their primary leak.
    
    Model: Your peak performance represents your skill ceiling.
    Your average performance shows consistency.
    The gap between them is fixable through pattern correction.
    """
    accuracies = [a.accuracy for a in analyses]
    
    stable_rating = percentile(accuracies, 25)  # Consistent floor
    peak_rating = percentile(accuracies, 90)    # What you CAN do
    
    gap = peak_rating - stable_rating
    
    # Estimate rating points recoverable
    recoverable_elo = gap * ACCURACY_TO_ELO_MULTIPLIER
    
    return {
        "stable_rating": stable_rating,
        "peak_rating": peak_rating,
        "rating_gap": gap,
        "recoverable_elo": recoverable_elo,
        "primary_blocker": identify_primary_leak(analyses)
    }
```

### 3. Behavioral Pattern Detection

```python
BEHAVIORAL_PATTERNS = {
    "relaxes_when_winning": {
        "triggers": ["blunder_when_ahead", "failed_conversion"],
        "message": "You lose focus immediately after gaining advantage.",
        "short": "Relaxes when winning",
        "fix": "When ahead, play like you're still equal. Stay alert."
    },
    "attacks_before_checking_threats": {
        "triggers": ["hanging_piece", "ignored_threat", "walked_into_fork"],
        "message": "You attack before checking opponent threats.",
        "short": "Impulsive attacker",
        "fix": "Before each move, ask: What can my opponent do to me?"
    },
    # ... 15+ more patterns
}

def detect_behavioral_patterns(user_mistakes):
    """
    Aggregate mistake types into human-readable behavioral patterns.
    """
    pattern_counts = defaultdict(int)
    
    for mistake in user_mistakes:
        for pattern, config in BEHAVIORAL_PATTERNS.items():
            if mistake.type in config["triggers"]:
                pattern_counts[pattern] += 1
    
    # Return top patterns with occurrence %
    total = len(user_mistakes)
    return [
        {
            "pattern": p,
            "occurrence_pct": (count / total) * 100,
            **BEHAVIORAL_PATTERNS[p]
        }
        for p, count in sorted(pattern_counts.items(), key=lambda x: -x[1])
    ]
```

---

## MOAT Analysis

### Potential MOATs

| MOAT Type | Description | Defensibility | Your Position |
|-----------|-------------|---------------|---------------|
| **Data Network Effect** | More users → more cognitive patterns → better diagnosis | HIGH | ★★☆☆☆ (early) |
| **Reflection IP** | Proprietary taxonomy of 18+ cognitive gap types | MEDIUM | ★★★★☆ (unique) |
| **Behavioral Psychology** | Chess + psychology integration | MEDIUM-HIGH | ★★★★☆ (unique) |
| **Recovery-First Training** | Training from YOUR mistakes | MEDIUM | ★★★☆☆ (replicable) |
| **User Habit Lock-in** | Daily reflection ritual | HIGH | ★★☆☆☆ (needs time) |

### Recommended MOAT Strategy

#### Primary MOAT: "Cognitive Chess Intelligence"

**Thesis**: No competitor diagnoses WHY players make mistakes at the cognitive level. You don't just have better analysis - you have a fundamentally different MODEL of chess improvement.

**Defensibility Layers**:
1. **Taxonomy** - 18+ cognitive gap types, proprietary classification
2. **Reflection Data** - Only you have what users were THINKING during mistakes
3. **Behavioral Patterns** - Psychological chess profiles (unique data asset)
4. **Correlation Engine** - Links between gap types, improvement rates, training effectiveness

#### Secondary MOAT: "Recovery-First Training Paradigm"

**Thesis**: Training should start from YOUR failures, not generic positions. This creates emotional resonance and better retention.

**Defensibility**:
1. **UX Innovation** - "Show Why Bad" animation of your blunder + punishment
2. **Puzzle Generation** - Automated from user's actual games
3. **Feedback Loop** - Training → Games → Analysis → Training (closed loop)

---

## Competitive Positioning Statement

> **Chess Coach doesn't teach you chess moves. It teaches you how YOUR mind makes chess decisions - and how to upgrade your thinking patterns.**

### Tagline Options
- "Fix your thinking, not just your moves"
- "Chess coaching for your brain, not just the board"
- "The chess coach that knows WHY you blunder"
- "Recovery-first chess improvement"

---

## Technical Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18 + TailwindCSS + Shadcn/UI |
| **Backend** | FastAPI (Python 3.11) |
| **Database** | MongoDB |
| **Chess Engine** | Stockfish 16 (NNUE, Depth 18) |
| **AI** | GPT-4o-mini (via Emergent LLM Key) |
| **Chess APIs** | Chess.com API, Lichess API |
| **Auth** | Google OAuth (Emergent-managed) |

---

## Feature Roadmap

### Phase 1: Core Loop (COMPLETE)
- [x] Game import from Chess.com/Lichess
- [x] Stockfish + AI analysis
- [x] Cognitive gap detection
- [x] Reflection engine
- [x] Player identity profile
- [x] Recovery-first training

### Phase 2: Engagement (IN PROGRESS)
- [x] Mission system (gamified habits)
- [x] Rich coach audit
- [x] Journey intelligence page
- [ ] Focus lock mode
- [ ] Social sharing

### Phase 3: Network Effects (FUTURE)
- [ ] Community patterns library
- [ ] Anonymized gap benchmarks
- [ ] Opening recommendation engine
- [ ] Coach marketplace integration

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `cognitive_gap_service.py` | 18 cognitive gap types, detection logic |
| `reflect_service.py` | Reflection engine, active recall |
| `player_identity_engine.py` | Dynamic player psychology profile |
| `journey_intelligence_service.py` | 8-section journey page engine |
| `blunder_intelligence_service.py` | Behavioral pattern detection |
| `rich_coach_audit_service.py` | Comprehensive game audit |
| `focus_mastery_service.py` | Pattern mastery tracking |
| `awareness_gap_rules.py` | Deterministic gap detection rules |
| `training_profile_service.py` | Training recommendations |
| `home_intelligence_service.py` | Home page personalization |

---

## Appendix: Cognitive Gap Taxonomy

### Category: Calculation Errors
| Gap | Definition | Detection Signal | Training |
|-----|------------|------------------|----------|
| `calculation_depth` | Didn't calculate far enough | Missed move 2-3 in best line | "Calculate one deeper" |
| `calculation_error` | Wrong arithmetic in line | Miscounted material | Pattern drills |

### Category: Awareness Errors
| Gap | Definition | Detection Signal | Training |
|-----|------------|------------------|----------|
| `threat_blindness` | Didn't see opponent's threat | Forcing move ignored | "What can opponent do?" |
| `hanging_piece_blindness` | Left piece undefended | Piece attacked with no defender | Safety scan |
| `check_blindness` | Didn't see a check | Check available but not seen | CCT checklist |

### Category: Tactical Errors
| Gap | Definition | Detection Signal | Training |
|-----|------------|------------------|----------|
| `missed_fork` | Missed fork opportunity | Fork was available | Fork patterns |
| `missed_pin` | Missed pin opportunity | Pin was available | Pin patterns |
| `missed_skewer` | Missed skewer opportunity | Skewer was available | Skewer patterns |
| `back_rank_blindness` | Missed back rank threat | Back rank mate available | Back rank drills |

### Category: Positional Errors
| Gap | Definition | Detection Signal | Training |
|-----|------------|------------------|----------|
| `positional_misread` | Wrong position assessment | Chose wrong plan | Position evaluation |
| `wrong_plan` | Correct calc, wrong idea | Strategic error | Planning exercises |
| `premature_action` | Acted before ready | Development incomplete | Development rules |

### Category: Psychological Errors
| Gap | Definition | Detection Signal | Training |
|-----|------------|------------------|----------|
| `overconfidence` | Assumed opponent would miss | High confidence + miss | "What's their best reply?" |
| `desperation` | Hope chess when losing | Low eval + risky move | Resilience training |

### Category: Time Errors
| Gap | Definition | Detection Signal | Training |
|-----|------------|------------------|----------|
| `time_pressure` | Rushed due to clock | Low clock + mistake | Time management |
| `rushed_move` | Moved too fast | Fast move + mistake | Discipline training |

---

*Document Version: 1.0*  
*Last Updated: February 27, 2026*  
*For MOAT Analysis and Strategic Planning*
