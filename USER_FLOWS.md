# Chess Coach AI - Practical User Flows

> Practical, non-technical answers for investors and product people.

---

## 1. Complete User Journey: Login → Finish Game Review

### Step-by-Step (5 minutes total)

```
LANDING PAGE
├── User sees: "Your Personal Grandmaster Coach"
├── Shows preview: AI saying "Remember the pinning issue we discussed? This is your 3rd missed pin in 5 games"
└── Clicks: "Start Training Free"

     ↓

ONBOARDING (30 seconds)
├── Enter Chess.com username
├── System fetches last 10 games automatically
└── User waits ~2 mins for first 5 games to analyze

     ↓

DASHBOARD (what user sees first)
├── "YOUR BIGGEST WEAKNESS: Positional Mistake"
├── "Your progress: 3.3 → 3 errors/game (+10%)"
├── "Coach Tip: Focus on one improvement at a time"
├── "YOUR BLIND SPOTS: Positional Mistake (7% of games)"
├── "GAMES TO REFLECT: 2 games waiting"
├── "Thinking Score: 93" (with trend arrow)
└── Clicks: Game vs puz2010 → "0 blunders to understand"

     ↓

GAME REVIEW - SUMMARY TAB (first thing they see)
├── "GAME STORY: An interesting battle that ended in a draw. Let's see if there were missed opportunities."
├── "Your accuracy: 69%"
├── "TURNING POINT (Move 33): Miscalculation - Qg6 allowed g4. Qf8 was needed."
│   ├── "You played: Qg6"
│   ├── "Better: Qf8"
│   └── Button: "Explain this move" / "View position"
├── "BIGGEST BLUNDER (Move 42): You played Qf6, but this allowed Bf3."
└── "KEY LESSON: Before every move, ask: What is my opponent threatening?"

     ↓

MOMENTS TAB (user clicks to dig deeper)
├── "Training Session: 1 of 5 critical positions"
├── Shows position at Move 26 - "Inaccuracy"
├── Coach asks: "Your opponent just created a threat. Can you spot it?"
├── "KEY MOMENT: Pause and study the position. Something important is happening."
└── Button: "Start Thinking" ← User must engage

     ↓

USER CLICKS "START THINKING"
├── "What were you thinking at this moment?"
├── Shows their move vs better move
├── Reveals: WHY it was wrong + behavioral tag
└── "Lesson: Check for threats before every move"

     ↓

MEMORY TAB (the personalization)
├── "Coach Memory: 15 games analyzed"
├── "Playing Style: Positional Player (Confident classification)"
├── "Blunder Profile: Worst phase = Middlegame, Most common = tactical error"
├── "🏆 15-game winning streak!"
├── "Your Mistake History: 43 total"
│   └── Clickable list: "Tactical Error - Move 57 (2 days ago)" ← each links to that position
└── "Mistakes by Type: tactical error (30)"

     ↓

REVIEW COMPLETE
└── User returns to Dashboard with updated recommendations
```

---

## 2. Three Real Sample Outputs by Rating

### 1200-Rated Player Sample

**Dashboard shows:**
```
YOUR BIGGEST WEAKNESS: Hanging Pieces
Your progress: 4.5 → 4.2 errors/game (+7%)
Coach Tip: Before every move, ask "Is this piece safe?"

YOUR BLIND SPOTS:
• Hanging Pieces - 5 of 12 games (42%) ← MAJOR ISSUE
• Missed Fork - 3 of 12 games (25%)

THINKING SCORE: 52
↓ Threat Awareness: 35 (poor)
↓ Tactical Vision: 45 (below average)
```

**Game Analysis shows:**
```
TURNING POINT (Move 18):
"You left your knight on d4 undefended. Your opponent took it for free."

WHY THIS HAPPENED: [Hope Chess]
"You moved without checking if your pieces were safe."

LESSON FOR 1200:
"Simple rule: Before EVERY move, count attackers vs defenders on each piece."
```

**Memory Tab shows:**
```
Playing Style: Tactical Player (but makes many tactical errors)
Worst Phase: Opening (loses material early)
Pattern: "You've hung a piece in 5 of your last 12 games"

Mistake History:
- Hung Knight (Move 18) - yesterday
- Hung Bishop (Move 12) - 2 days ago
- Missed Fork (Move 24) - 2 days ago
```

---

### 1400-Rated Player Sample

**Dashboard shows:**
```
YOUR BIGGEST WEAKNESS: Time Trouble Blunders
Your progress: 2.8 → 2.5 errors/game (+11%)
Coach Tip: Take 10 seconds before critical moves

YOUR BLIND SPOTS:
• Time Trouble Blunders - 4 of 15 games (27%)
• Pawn Structure Mistakes - 3 of 15 games (20%)

THINKING SCORE: 68
↓ Time Management: 45 (needs work)
→ Tactical Vision: 72 (good)
```

**Game Analysis shows:**
```
TURNING POINT (Move 35):
"With 30 seconds left, you played Qxd4?? allowing back rank mate."

WHY THIS HAPPENED: [Time Pressure]
"You had 45 seconds at move 30 but spent only 2 seconds here."

LESSON FOR 1400:
"When under 1 minute: Simplify the position. Trade pieces. Don't calculate complicated lines."
```

**Memory Tab shows:**
```
Playing Style: Universal (mixes tactics and positional play)
Worst Phase: Endgame (collapses under time pressure)
Pattern: "4 of your last 6 losses came with <1 minute on clock"

Mistake History:
- Time Trouble Blunder (Move 35) - yesterday
- Time Trouble Blunder (Move 42) - 3 days ago
- Positional Error (Move 28) - 4 days ago
```

---

### 1600-Rated Player Sample

**Dashboard shows:**
```
YOUR BIGGEST WEAKNESS: Strategic Planning
Your progress: 1.8 → 1.6 errors/game (+11%)
Coach Tip: Ask "What's my plan for the next 5 moves?"

YOUR BLIND SPOTS:
• Strategic Drift - 5 of 20 games (25%)
• Prophylaxis Misses - 4 of 20 games (20%)

THINKING SCORE: 78
↓ Positional Understanding: 65 (room to grow)
→ Tactical Vision: 85 (strong)
```

**Game Analysis shows:**
```
TURNING POINT (Move 23):
"You played h3?! - a waiting move with no plan. This gave Black time to organize counterplay."

WHY THIS HAPPENED: [Planless Play]
"The position required a concrete plan. You made a move because it was 'safe' not because it achieved something."

LESSON FOR 1600:
"In quiet positions, ask: What is my opponent's plan? What should I be preventing?"

HOW A STRONGER PLAYER THINKS HERE:
Step 1: Black wants to play ...b5-b4 attacking my c3 knight
Step 2: I should prevent this with a4
Step 3: Then I can prepare f4-f5 attacking their king
→ Better plan: a4 stopping ...b5, then prepare kingside attack
```

**Memory Tab shows:**
```
Playing Style: Positional Player (high confidence)
Worst Phase: Middlegame (loses direction after opening)
Pattern: "In 5 games you made 'safe' moves when you had a winning plan available"

Mistake History:
- Strategic Drift (Move 23) - yesterday
- Missed Prophylaxis (Move 19) - 3 days ago
- Ignored Opponent's Plan (Move 31) - 5 days ago
```

---

## 3. What User is FORCED to Do After Analysis

### Current Flow (Soft Nudges)

```
After game analysis completes:
├── Dashboard shows "GAMES TO REFLECT" card
│   └── "Game vs opponent - X blunders to understand" (clickable)
├── "TODAY'S TRAINING" card shows
│   └── "You had 1 mistakes recently. Solve 1 positions from your games"
│   └── "Start Training" button
└── Thinking Score may have dropped (visible trend)
```

### What's NOT Forced Yet (Gap)
```
❌ No paywall blocking features
❌ No "complete review before playing" lock
❌ No streak that breaks if they skip
❌ No email/push reminding them
```

### Recommended "Forced" Loop (Future)
```
After analysis:
1. MUST click through each "Key Moment" (can't skip)
2. MUST answer "What was your plan?" before seeing answer
3. MUST solve 1 puzzle from that game before leaving
4. If they leave early → "Incomplete Review" badge on game
```

---

## 4. What Happens After One Game (The Loop)

### Current Loop

```
PLAY GAME (on Chess.com)
        ↓
IMPORT GAME (automatic or manual)
        ↓
ANALYSIS RUNS (1-2 minutes)
        ↓
DASHBOARD UPDATES:
├── Biggest Weakness recalculated
├── Blind Spots updated with new patterns
├── Thinking Score recalculated
├── New game appears in "Games to Reflect"
└── Training recommendations update
        ↓
USER REVIEWS GAME
├── Sees mistakes + explanations
├── Memory Tab shows pattern ("This is your Xth time...")
└── Lessons extracted
        ↓
TRAINING OFFERED
├── "Solve positions from YOUR games"
├── Puzzles generated from YOUR mistakes
└── Opening trainer if opening was weak
        ↓
NEXT GAME
└── Pre-Move Checklist in "Play with Coach" now includes 
    reminders based on THIS game's mistakes
```

### Data That Updates After Each Game

| Data Point | What Updates |
|------------|--------------|
| `player_identity.style` | May change if playing style shifts |
| `player_identity.blunder_taxonomy` | New mistake added to counts |
| `player_identity.pattern_history` | New mistake entry with clickable link |
| `player_identity.streaks` | Win/loss streak recalculated |
| `thinking_scores` | New score calculated for this game |
| `weakness_tracking` | Blind spots recalculated |

---

## 5. What Player Data is Reused in Next Game

### In "Play with Coach" Mode

When user starts a new practice game, we pull from their profile:

```python
# What we know about this player
{
  "style": "Positional Player",
  "weakest_phase": "Middlegame", 
  "most_common_mistake": "tactical_error",
  "recent_patterns": [
    "missed_fork (3 times)",
    "hung_piece (2 times)"
  ],
  "opening_history": {
    "italian": {"games": 5, "accuracy": 72%},
    "caro_kann": {"games": 3, "accuracy": 68%}
  }
}
```

### How It's Used During the Game

**Pre-Move Checklist customizes based on this:**
```
OPENING PHASE (moves 1-10):
If player has poor opening_fundamentals_score:
  ☐ "Is there a piece I haven't developed yet?"
  ☐ "Have I castled or is my king safe?"

MIDDLEGAME (moves 11-30):
If player.most_common_mistake == "tactical_error":
  ☐ "What is my opponent threatening?"
  ☐ "Are any of my pieces undefended?"
  ☐ "Can I give a check, capture, or create a threat?"

If player.recent_patterns includes "missed_fork":
  ☐ "Look for knight forks!"

ENDGAME (moves 31+):
If player.weakest_phase == "endgame":
  ☐ "Activate your king!"
  ☐ "Push passed pawns!"
```

**Opening Guidance customizes:**
```
If player played Italian 5 times with 72% accuracy:
  Coach says: "You know this opening well. Look for the f7 weakness."

If player never played Caro-Kann:
  Coach says: "New opening! Key idea: Develop bishop before playing e6."
```

**Post-Move Feedback customizes:**
```
If player just hung a piece AND hung_piece in recent_patterns:
  Coach says: "This is the 3rd time you've left a piece undefended. 
              Remember: Count attackers vs defenders BEFORE moving."
```

---

## 6. Play with Coach - Real Flow (What Appears During Game)

### Before Game Starts

```
┌─────────────────────────────────────────┐
│  Coach (Lvl 20)          ⏱ 15:00       │
├─────────────────────────────────────────┤
│                                         │
│     [Chess Board - Starting Position]   │
│                                         │
├─────────────────────────────────────────┤
│  You                     ⏱ 15:00       │
│  Your turn                              │
│                                         │
│  ┌─ Pre-Move Checklist ──────────────┐  │
│  │ ☐ Is there a piece I haven't      │  │
│  │   developed yet?                   │  │
│  │ ☐ Have I castled?                  │  │
│  └───────────────────────────────────┘  │
│                                         │
│  [Flip] [Resign]                        │
└─────────────────────────────────────────┘

RIGHT PANEL:
┌─────────────────────────────────────────┐
│  🎯 Your Coach                          │
│                                         │
│  "Make a move. I'll share my thoughts." │
│                                         │
│  Quick questions:                       │
│  [Explain my position]                  │
│  [Why was that better?]                 │
│  [What's my plan?]                      │
│  [Did I miss a tactic?]                 │
│                                         │
│  Type a question...                     │
└─────────────────────────────────────────┘
```

### After User Plays 1.e4

```
COACH RESPONSE:
"Good! You're fighting for the center. The most common responses 
are e5 (Open Game), c5 (Sicilian), or e6 (French). Let's see 
what your opponent chooses."

EVAL BAR: +0.4 (slight white advantage)
```

### When Opening is Detected (e.g., 1.e4 e5 2.Nf3 Nc6 3.Bc4 - Italian)

```
OPENING GUIDE PANEL APPEARS:
┌─────────────────────────────────────────┐
│  📖 Italian Game Detected               │
│                                         │
│  Key Ideas:                             │
│  ✓ Your bishop aims at f7 (weak spot)  │
│  ✓ Castle quickly, then attack          │
│  ✓ Control center, prepare d4           │
│                                         │
│  [Learn More] [Dismiss]                 │
└─────────────────────────────────────────┘
```

### When User Makes a Mistake

```
USER PLAYS: Nxd4?? (hangs the knight)

COACH RESPONSE:
"Careful! Your knight on d4 is now undefended. Your opponent 
can simply take it with their queen. 

Remember: Before every capture, check if YOUR piece will be 
safe after the trade."

PRE-MOVE CHECKLIST NOW SHOWS:
☑ Is my knight safe after this move? ← HIGHLIGHTED
```

### When User Has a Tactical Opportunity

```
POSITION: User has Nf6+ winning the queen

IF USER MISSES IT:
Coach says (after they move something else):
"Wait - did you see Nf6+? That's a fork winning the queen!

Looking for forks is something we've talked about before. 
You've missed 3 forks in your last 10 games. Before moving, 
always ask: Can my knights attack two pieces at once?"
```

### During Middlegame (Moves 15-30)

```
PRE-MOVE CHECKLIST ADAPTS:
┌─ Before You Move ─────────────────────┐
│ Based on YOUR patterns:               │
│                                       │
│ ☐ What is opponent threatening?       │
│ ☐ Are any pieces undefended?          │
│ ☐ Can I give check, capture, threat?  │
│                                       │
│ 💡 You tend to miss tactics here.     │
│    Take an extra 10 seconds.          │
└───────────────────────────────────────┘
```

### User Clicks "Explain My Position"

```
USER: "Explain my position"

COACH RESPONSE:
"Let me break this down:

MATERIAL: Equal
PAWN STRUCTURE: You have an isolated d-pawn (weakness)
KING SAFETY: Both kings are castled
PIECE ACTIVITY: Your rooks aren't connected yet

ASSESSMENT: Roughly equal (+0.2)

SUGGESTED PLAN: 
1. Connect your rooks (Rfe1 or Rfd1)
2. Put a rook on the d-file to support your d-pawn
3. Look for tactical opportunities with your active knight

What would you like to explore?"
```

### Game Ends - Summary Appears

```
┌─────────────────────────────────────────┐
│  Game Complete - You Won!               │
│                                         │
│  Accuracy: 74%                          │
│  Mistakes: 2                            │
│  Blunders: 0                            │
│                                         │
│  KEY MOMENT: Move 23                    │
│  You found the winning tactic! Nf6+    │
│  winning material.                      │
│                                         │
│  AREAS TO REVIEW:                       │
│  • Move 15: Missed faster win           │
│  • Move 31: Inaccurate endgame tech     │
│                                         │
│  [Full Analysis] [Play Again]           │
└─────────────────────────────────────────┘
```

---

## Summary: The Coaching Loop

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  PLAY → ANALYZE → LEARN → PRACTICE → PLAY                  │
│    │        │        │         │        │                   │
│    │        │        │         │        └── Checklist uses  │
│    │        │        │         │            learned patterns │
│    │        │        │         │                            │
│    │        │        │         └── Puzzles from YOUR        │
│    │        │        │             mistakes                 │
│    │        │        │                                      │
│    │        │        └── "How to Think" walkthroughs        │
│    │        │            Rating-adaptive explanations       │
│    │        │                                               │
│    │        └── Pattern detection                           │
│    │            "This is your Xth time..."                  │
│    │            Behavioral tags (impatience, hope chess)    │
│    │                                                        │
│    └── Game imported from Chess.com                         │
│                                                             │
│  DATA FLOWS FORWARD ─────────────────────────────────────── │
│  Every game feeds the next coaching experience              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## What's Missing (Honest Gaps)

| Feature | Status | Impact |
|---------|--------|--------|
| Paywall | ❌ Not built | No revenue |
| Force review completion | ❌ Soft nudge only | Users skip learning |
| Streak/gamification | ❌ Not built | Low retention |
| Push notifications | ❌ Not built | Users forget to return |
| Mobile app | ❌ Web only | Misses 50% of users |
| Spaced repetition | ❌ Not built | Mistakes not memorized |

---

*This document shows actual user-facing flows, not technical implementation.*
