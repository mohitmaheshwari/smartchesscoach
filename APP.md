# Chess Coach - Complete Application Documentation

## Overview

Chess Coach is a sophisticated chess coaching application that provides personalized analysis, training, and improvement recommendations. Unlike traditional chess apps that simply show engine evaluations, Chess Coach focuses on **human-improvable errors** and **thinking patterns** to help players genuinely improve.

**Core Philosophy:** Surface human-improvable errors, not engine disagreements.

---

## Complete User Experience Guide

This section explains EVERYTHING a user can do in the app, from their perspective.

### The Coaching Philosophy (How the App "Thinks")

Traditional chess apps show you every place the engine disagrees with you. This is noise. Chess Coach is different:

**We only surface moves where you can actually improve your thinking:**
1. **Missed forcing tactics** - You had a check/capture/threat you didn't see
2. **Allowed forcing tactics** - You let opponent have a strong reply
3. **Violated decision rules** - Left a piece hanging, ignored king safety
4. **Repeated personal patterns** - You keep making the same type of error
5. **No plan when needed** - Critical position but you played randomly

**What we DON'T show (in Coach Mode):**
- "Engine prefers Bc4 over Be2" when both are fine
- Minor positional preferences (50-99 cp)
- Prophylactic moves that address real threats (h6 to stop Ng5)

---

### Complete User Journey

#### Phase 1: Onboarding (First Visit)

1. **Landing Page**
   - User sees marketing page explaining the app
   - "Sign in with Google" button (or Dev Login for testing)
   
2. **First Login**
   - Account created automatically
   - Redirected to Dashboard
   - Prompted to connect Chess.com or Lichess account
   
3. **Account Linking**
   - Enter Chess.com/Lichess username
   - App verifies account exists
   - Background sync starts importing recent games (last 30 days)
   - User sees "Syncing X games..." progress

4. **Initial State**
   - Dashboard shows first imported games
   - Games queue for Stockfish analysis
   - Within minutes, first analyses are ready

---

#### Phase 2: Daily Usage Loop

**The typical user session:**

```
1. Open app → See Dashboard
2. Check if new games were synced
3. Go to Lab → Review recent game
4. See mistakes → Read explanations
5. Go to Training → Solve puzzles from mistakes
6. (Optional) Go to Reflect → Record thoughts on critical moments
7. Check Journey → See progress over time
```

---

### Feature-by-Feature User Guide

#### 1. DASHBOARD (`/dashboard`)

**What the user sees:**
- **Recent Games** - Last 5-10 games with results (Win/Loss/Draw)
- **Accuracy Trend** - Graph showing accuracy over recent games
- **Quick Stats** - Games played, average accuracy, blunders this week
- **Top Weakness** - "You're struggling with: Piece Activity"
- **Training Recommendation** - "Focus on: Tactical puzzles"
- **Notifications** - New analysis ready, achievements unlocked

**User actions:**
- Click a game → Goes to Lab for that game
- Click "Start Training" → Goes to Training page
- Click notification → Goes to relevant page

---

#### 2. LAB (`/game/{game_id}`)

**What it is:** Deep analysis of a single chess game.

**What the user sees:**

**Header:**
- Opponent name, rating, result (Win/Loss/Draw)
- Accuracy percentage
- Mistake counts: "8 Blunders, 4 Tactical" (Coach Mode)
- **Coach/Engine Toggle** - Switch between modes
- Core insight: "You lose focus after gaining advantage"
- "Practice Critical Moments" button

**Left Panel (Board Area):**
- Interactive chessboard showing position
- Move-by-move navigation (arrows, click moves)
- Move list: 1. e4 e5 2. Nf3 Nc6...
- "Critical Only" toggle - Show only mistake moves
- Play/Pause for auto-replay

**Right Panel (Tabs):**

**Summary Tab:**
- Game overview
- Opening name (e.g., "Italian Game: Classical Variation")
- Key moments timeline
- AI-generated game summary

**Strategy Tab:**
- Position evaluation graph over time
- Critical moments marked
- Phase breakdown (opening/middlegame/endgame accuracy)

**Milestones Tab:**
- **Brilliant Moves** (green) - Your best moves with "Brilliant!" badge
  - "Move 7: Be3 - Solid choice"
  - "Move 37: Ra1 - Found a winning shot!"
- **Great Decisions** (yellow) - Good moves
  - "Move 3: Nc3 - Kept the pressure"
- **Learning Moments** (red/orange) - Mistakes to learn from
  - "Move 16: Bxa7 - Tactical Mistake"
  - Click to expand → Shows explanation

**When user clicks a Learning Moment:**
- Board updates to that position
- Shows: "You played: Bxa7" vs "Better was: a3"
- Shows centipawn loss
- "What can I learn here?" button → Generates AI explanation:
  - "Playing Bxa7 diverted your bishop from the center..."
  - Includes principle: "Always check if your pieces stay coordinated"

**Coach Mode vs Engine Mode:**
- **Coach Mode (default):** Only shows human-improvable errors
  - Hides 50-99cp "engine preferences"
  - Shows tactical mistakes, blunders, strategic slips
- **Engine Mode:** Shows EVERYTHING the engine disagrees with
  - Includes all minor inaccuracies
  - For advanced users who want full detail

---

#### 3. TRAINING (`/training`)

**What it is:** Practice positions from your own mistakes + community puzzles.

**Main Training Page:**

**Header:**
- "Training - Improve your chess with personalized training"
- Session stats: "0/0 correct" in current session

**Tabs:**
- **Puzzles** - Tactical training
- **Opening Trainer** - Openings & traps

**PUZZLES TAB:**

**Left Panel:**
- **Filter dropdown:** "All Puzzles" / "My Games" / "Community"
- **Puzzle list:** "Puzzle 1 of 11"
- Current puzzle card showing:
  - Difficulty badge (easy/medium/hard)
  - Source: "Your Game" or "Community: from player_name"
  - Opponent name, move number
  - "Playing as White/Black"

**Center (Board):**
- Interactive puzzle position
- "Your turn - Find the best move"
- User makes a move by dragging/clicking

**After making a move:**

*If CORRECT:*
- Green success message
- "+29" rating change badge (green)
- Explanation: "Excellent! You found the forcing continuation..."
- Principle: "Always look for checks and captures first"
- Streak indicator: "3 puzzle streak!"
- "Next Puzzle" button

*If INCORRECT:*
- Red error message
- "-5" rating change badge (red)
- Shows: "You played: Nf3" vs "Best was: Nd5"
- Explanation: "This move misses the tactical opportunity..."
- "Try Again" or "Next Puzzle" buttons

**Right Sidebar:**

**Puzzle Context:**
- "This Position" - From your game vs [opponent]
- "You played: [move]" - Your original mistake
- "Severity: Mistake (~1 pawn)"

**What Went Wrong:**
- Category badge: "Piece Activity"
- Explanation of the original mistake

**Puzzle Rating Card:** ⭐
- Current rating: **1290** (big number)
- Level badge: "Intermediate"
- Progress bar: "310 points to Advanced"
- Stats grid:
  - Streak: 0 (with flame icon)
  - Solve Rate: 53.8%
- Best Streak: 5 (with trophy)
- Recent (last 20): 53.8%
- Total: "X puzzles attempted • Y solved"
- Achievements: "On Fire!" "5-Streak" badges

**Level-Up Celebration:**
When user reaches new level:
- Full-screen modal with animation
- "Level Up! You've reached Advanced!"
- Shows old level → new level
- New rating displayed
- "Continue" button

---

**OPENING TRAINER TAB:**

**What it is:** Learn chess openings and traps.

**Sub-tabs:**
- Openings - Browse opening lines
- Trick Library - Learn common traps

**TRICK LIBRARY:**

**Trap Categories:**
- Italian Game Traps (5)
- Sicilian Traps (4)
- French Defense Traps (3)
- Caro-Kann Traps (2)
- Queen's Gambit Traps (3)
- Scandinavian Traps (2)
- Other Traps (10+)

**Each Trap Card Shows:**
- Trap name: "Blackburne Shilling Gambit"
- Opening: "Italian Game"
- Difficulty: Beginner/Intermediate/Advanced
- Your stats: "Practiced 3 times, 67% success"
- "Practice" button

**Practice Modes (user chooses):**

1. **Execution Mode** - "Learn to SET UP this trap"
   - You play the trapping side
   - Board shows position
   - You must play the correct trap moves
   - Hints if you get stuck
   - "You successfully executed the trap!"

2. **Avoidance Mode** - "Learn to AVOID this trap"
   - You play the side that could fall for it
   - Must find the move that avoids the trap
   - "Correct! You avoided the trap by playing..."

3. **Recognition Mode** - "Can you SPOT the trap?"
   - Given a position
   - Asked: "Is there a trap here? What is it?"
   - Multiple choice or move input
   - "Yes! This is the Legal's Mate trap"

**Trap Statistics Dashboard:**
- Overall success rate
- Traps mastered vs in progress
- Recommended traps to study (based on your openings)
- Leaderboard for trap mastery

---

#### 4. JOURNEY (`/journey`)

**What it is:** Track your chess improvement over time.

**What the user sees:**

**Header:**
- "Your Chess Journey"
- Current rating (if available from Chess.com/Lichess)
- Linked accounts indicator

**Stats Overview:**
- Games played (total, this week, this month)
- Average accuracy (overall, trending)
- Win/Loss/Draw percentages
- Blunder rate over time

**Rating Trajectory Graph:**
- Line chart showing rating over time
- Marks for significant games
- Trend line

**Game History:**
- List of all analyzed games
- Each shows: Date, Opponent, Result, Accuracy, Opening
- Click to go to Lab

**Weakness Trends:**
- "Your top weaknesses this month:"
  1. Piece Activity (appears in 40% of mistakes)
  2. King Safety (appears in 25% of mistakes)
  3. Pawn Structure (appears in 20% of mistakes)
- Progress indicator: "Improving" or "Needs work"

**Weekly Assessment (AI-generated):**
- "This week you played 12 games..."
- Highlights and lowlights
- Specific recommendations
- Pattern observations

**Linked Accounts:**
- Chess.com: username (linked)
- Lichess: username (linked)
- "Sync Now" button
- Last sync time

---

#### 5. REFLECT (`/reflect`)

**What it is:** Build self-awareness through post-game reflection.

**Why it exists:** Research shows that reflecting on your thought process during games significantly accelerates improvement.

**Pending Reflections:**
- List of games you haven't reflected on yet
- Badge: "3 games pending"
- Games sorted by importance (bigger mistakes first)

**Reflection Interface (for a specific game):**

**Critical Moments:**
- AI identifies 3-5 key decision points
- Each shows:
  - Position
  - What you played
  - "What were you thinking?"
  - Text input for your reflection

**Reflection Prompts:**
- "What was your plan here?"
- "Did you consider your opponent's threats?"
- "What would you do differently?"

**Tagging System:**
- After writing, user tags their thinking error:
  - "Didn't check for threats"
  - "Calculated wrong"
  - "Time pressure"
  - "Didn't have a plan"
  - "Overconfident"

**Intent vs Reality (coming soon):**
- User writes: "I played h6 to prevent Ng5"
- System validates: "Was Ng5 actually a threat?"
- Shows: ✅ Correct read / ⚠️ Phantom threat / ❌ Missed real threat

**Reflection History:**
- Past reflections searchable
- Pattern analysis: "You often miss threats on the kingside"

---

#### 6. IMPORT (`/import`)

**What it is:** Manually import games.

**Options:**
1. **Paste PGN** - Copy/paste a PGN string
2. **Upload PGN file** - Upload .pgn file
3. **Link accounts** - Connect Chess.com/Lichess for auto-sync

**After import:**
- Game appears in list
- Queued for Stockfish analysis
- Ready for Lab view within minutes

---

#### 7. SETTINGS (`/settings`)

**What the user can configure:**

**Profile:**
- Display name
- Profile picture (from Google)

**Notifications:**
- Email notifications (weekly summary, new analysis)
- Push notifications (enable/disable)

**Preferences:**
- Default board theme
- Coach Mode default on/off
- Preferred analysis depth

**Connected Accounts:**
- Chess.com: Connected/Disconnect
- Lichess: Connected/Disconnect

---

### The Complete Coaching Loop

This is how all features work together:

```
┌─────────────────────────────────────────────────────────────┐
│          COGNITIVE DIAGNOSIS → PRESCRIPTION → AUDIT         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   1. PLAY GAMES (external)                                  │
│        ↓                                                    │
│   2. SYNC → Games imported automatically                    │
│        ↓                                                    │
│   3. ANALYZE → Stockfish + Cognitive Classification         │
│        ↓                                                    │
│   4. DIAGNOSE → Aggregate into cognitive patterns           │
│      • Missed Forcing Moves                                 │
│      • Ignored Opponent Threats                             │
│      • Phantom Threat Reactions                             │
│      • Advantage Mismanagement                              │
│      • Structural Misjudgments                              │
│      • Random Moves in Critical Positions                   │
│        ↓                                                    │
│   5. PRESCRIBE → Training prioritized by weakness           │
│      • Primary focus shown in Training header               │
│      • Puzzles reordered by relevance                       │
│      • Traps filtered by category                           │
│        ↓                                                    │
│   6. TRAIN → Practice your specific weaknesses              │
│        ↓                                                    │
│   7. AUDIT → Next 5 games evaluated vs baseline             │
│      • Compare frequency before/after                       │
│      • Show improvement trend                               │
│        ↓                                                    │
│   8. UPDATE → TSI recalculated, loop continues              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### Cognitive Pattern System (NEW)

The app now operates as a **Cognitive Diagnosis → Prescription → Audit** loop.

#### Diagnosis Layer

**What it does:** Aggregates move-level mistakes into recurring cognitive patterns.

**Cognitive Categories:**
| Category | Triggers | Example |
|----------|----------|---------|
| Missed Forcing Move | cp_loss >= 150 AND best_move was check/capture | Missed Qxf7+ fork |
| Ignored Opponent Forcing | Opponent's best reply was forcing, ignored | Allowed Ng5 threat |
| Phantom Threat Reaction | Defensive move vs non-existent threat | h6 when Ng5 wasn't coming |
| Advantage Mismanagement | Winning → equal, equal → losing | Relaxed after gaining material |
| Structural Misjudgment | Pawn structure damage, piece coordination | Created weak d4 square |
| Random Move Critical | Blunder in critical position, no plan | Moved randomly when calculation needed |

**Metrics per category:**
- `frequency` - How often this pattern appears (last 20 games)
- `avg_severity` - Average centipawn loss (0-1 scale)
- `weighted_score` - frequency × severity
- `trend` - Comparing last 5 vs previous 5 games (improving/worsening/stable)

**Thinking Stability Index (TSI):**
```
TSI = 100 - normalized_sum(category_scores)
```
Range: 0-100 (higher = better)
Displayed with trend direction.

#### Prescription Layer

**What it does:** Prioritizes training content based on diagnosed weaknesses.

**Behavior:**
1. IF cognitive pattern frequency > threshold → prioritize related drills
2. Puzzles **reordered** (not filtered) by relevance
3. Sort order: Leak-related → Secondary weakness → General
4. Toggle: **Recommended** (default) / **Browse All**

**Training Focus Card (UI):**
- Shows primary focus area with message
- Shows TSI score
- Shows secondary weaknesses
- Recommended/Browse All toggle

#### Audit Layer

**What it does:** Evaluates improvement after focus module activation.

**Behavior:**
1. User activates focus on a category
2. System records `module_activation_timestamp`
3. Baseline = last 10 games BEFORE activation
4. Audit window = 5 most recent games AFTER activation
5. Compare frequency/severity → show improvement %

**No complex scoring model. Simple before/after comparison.**

#### API Endpoints

```
GET  /api/cognitive/patterns         # Full pattern aggregation
GET  /api/cognitive/weaknesses       # Prioritized weakness list
GET  /api/cognitive/training-priority # What to show in Training
GET  /api/cognitive/tsi              # Just the TSI score
POST /api/cognitive/focus/activate   # Start focus module
GET  /api/cognitive/focus/status     # Current focus status
GET  /api/cognitive/focus/progress   # Evaluate improvement
```

#### Storage (Minimal)

Only two fields persisted per user:
- `focus_module.active_category`
- `focus_module.activated_at`

Everything else computed dynamically from existing `game_analyses` documents.
│        ↓                                                    │
│   (Repeat)                                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### Gamification Elements

**XP System:**
- Earn XP for: Analyzing games, solving puzzles, reflecting, daily login
- Level up with enough XP
- Levels unlock features/badges

**Achievements:**
- "First Analysis" - Analyze your first game
- "Puzzle Streak" - 5, 10, 25 puzzles in a row
- "Deep Thinker" - Reflect on 10 games
- "Trap Master" - Master 5 traps
- "Accuracy King" - 90%+ accuracy game

**Badges:**
- Skill-based badges (Tactics, Endgame, Opening knowledge)
- Progress indicators
- Evidence from your games

**Daily Rewards:**
- Login streak bonuses
- Daily puzzle challenge

**Leaderboard:**
- Puzzle rating rankings
- Trap mastery rankings
- Weekly most improved

---

### Notification System

**In-App Notifications (Bell icon):**
- "Game analysis complete: vs opponent123"
- "New achievement: Puzzle Streak!"
- "Weekly summary ready"
- "Your game was synced"

**Push Notifications (mobile):**
- Same as above, delivered to device

**Email Notifications:**
- Weekly summary email
- Monthly progress report
- Re-engagement ("You haven't played in a week")

---

### Error Handling (What Users See)

**When something goes wrong:**
- Toast notifications with error message
- "Could not generate explanation. Try re-analyzing the game."
- "Sync failed. Check your username."
- Retry buttons where appropriate

**Loading States:**
- Skeleton loaders for content
- "Analyzing position..." spinners
- Progress bars for long operations

---

### Mobile Responsiveness

The app is fully responsive:
- **Desktop:** Full three-column layout
- **Tablet:** Two-column, collapsible panels
- **Mobile:** Single column, bottom navigation

---

## Summary: What Can a User Do?

| Feature | User Action | Outcome |
|---------|-------------|---------|
| **Dashboard** | View overview | See recent games, stats, recommendations |
| **Lab** | Analyze a game | See mistakes, explanations, practice positions |
| **Training** | Solve puzzles | Practice your weaknesses, improve rating |
| **Trick Library** | Learn traps | Execute, avoid, recognize common traps |
| **Journey** | Track progress | See improvement over time, weakness trends |
| **Reflect** | Record thoughts | Build self-awareness, identify patterns |
| **Import** | Add games | Manually import PGN or connect accounts |
| **Settings** | Configure app | Notifications, preferences, accounts |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + Vite, TailwindCSS, Shadcn/UI |
| Backend | FastAPI (Python 3.11) |
| Database | MongoDB (Motor async driver) |
| Chess Engine | Stockfish 16 (python-chess) |
| AI/LLM | OpenAI GPT-4o-mini via Emergent LLM Key |
| Chess Data | Lichess Opening Explorer API, Chess.com API |
| Auth | Google OAuth + Session-based |
| Deployment | Kubernetes (Emergent Platform) |

---

## Architecture

```
/app
├── backend/
│   ├── server.py                 # Main FastAPI app, 200+ API endpoints
│   ├── services/                 # (services are at root level)
│   │   ├── stockfish_service.py  # Stockfish engine wrapper
│   │   ├── coaching_classifier_service.py  # Move classification for coaching
│   │   ├── mistake_explanation_service.py  # LLM-powered explanations
│   │   ├── interactive_training_service.py # Puzzle generation & validation
│   │   ├── trick_library_service.py        # Chess traps database
│   │   ├── journey_service.py              # Game sync & progress tracking
│   │   └── ... (40+ service files)
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/                # Main app pages
│       ├── components/           # Reusable components
│       └── components/ui/        # Shadcn components
└── memory/
    └── PRD.md                    # Product requirements
```

---

## Core Features

### 1. Game Analysis (Lab)

**Purpose:** Deep analysis of chess games with focus on learning, not just evaluation.

**Key Components:**
- `Lab.jsx` - Main game analysis page
- `GameAnalysis.jsx` - Alternative analysis view
- `CoachBoard.jsx` - Interactive chessboard with move exploration

**Features:**
- **Coach Mode vs Engine Mode Toggle**
  - Coach Mode: Shows only human-improvable errors (tactics, repeated patterns, threat-check failures)
  - Engine Mode: Shows all engine disagreements
- **Move Categories:**
  - Blunder (300+ cp loss)
  - Tactical Mistake (150+ cp OR missed tactic)
  - Strategic Slip (100-149 cp)
  - Engine Preference (50-99 cp, hidden in Coach Mode)
- **Brilliant Moves Detection** - Highlights your best moves
- **Learning Moments** - Mistakes reframed as growth opportunities
- **Position Visualization** - Board state at any move
- **PV Lines** - Shows what could have happened
- **AI Explanations** - Natural language explanations for mistakes

**API Endpoints:**
```
GET  /api/lab/{game_id}           # Get game data for Lab
POST /api/explain-mistake         # Generate AI explanation for a move
GET  /api/game/{game_id}/analysis # Get Stockfish analysis
POST /api/games/{game_id}/reanalyze # Re-run analysis
```

---

### 2. Training System

**Purpose:** Personalized training based on your actual mistakes.

**Components:**
- `TrainingNew.jsx` - Main training interface
- `OpeningTrainer.jsx` - Opening preparation & trick library

#### 2a. Puzzle Training

**Features:**
- **Puzzles from Your Games** - Practice positions where you made mistakes
- **Community Puzzles** - Solve puzzles from other users' games
- **Smart Puzzle Validation** - Stockfish-verified correct/incorrect with explanations
- **Puzzle Difficulty Progression** (Elo-based):
  - Rating starts at 1200
  - Updates based on puzzle performance (K-factor=32)
  - 6 levels: Beginner, Easy, Intermediate, Advanced, Expert, Master
  - Streak tracking and achievements
- **Puzzle Filtering** - "All Puzzles", "My Games", "Community"

**Puzzle Generation Criteria:**
- cp_loss >= 150 OR forced tactic
- NOT just "engine preference" (50-99 cp without tactical content)
- Must have clear teaching point

**API Endpoints:**
```
GET  /api/training/puzzles                    # Get personalized puzzles
POST /api/training/puzzle/validate            # Validate puzzle attempt
GET  /api/training/puzzle-progress            # Get puzzle rating/stats
GET  /api/training/puzzle-difficulty-recommendation
GET  /api/training/puzzle-leaderboard
```

#### 2b. Trick Library (Opening Traps)

**Features:**
- **30+ Common Chess Traps** organized by opening
- **Three Interactive Modes:**
  1. **Execution Mode** - Learn to set up the trap
  2. **Avoidance Mode** - Learn to avoid falling for it
  3. **Recognition Mode** - Identify the trap from the position
- **Trap Statistics** - Track your success rate per trap
- **Personalized Recommendations** - Suggests traps to study based on your weaknesses
- **Difficulty Levels** - Beginner to Master

**Trap Categories:**
- Italian Game Traps (Blackburne Shilling, Fried Liver, etc.)
- Sicilian Traps
- French Defense Traps
- Caro-Kann Traps
- Queen's Gambit Traps
- Scandinavian Traps
- And more...

**API Endpoints:**
```
GET  /api/training/tricks                     # List all traps
GET  /api/training/tricks/{trap_key}          # Get specific trap
GET  /api/training/tricks/{trap_key}/practice # Start practice
POST /api/training/tricks/record-attempt      # Record attempt result
GET  /api/training/tricks/stats               # User's trap statistics
GET  /api/training/tricks/recommendations     # Personalized recommendations
POST /api/training/tricks/validate-avoidance  # Validate avoidance attempt
POST /api/training/tricks/validate-recognition # Validate recognition
```

#### 2c. Opening Preparation

**Features:**
- **Opening Explorer** - Browse openings with Lichess statistics
- **Variation Training** - Practice specific lines
- **Move-by-Move Statistics** - Win rates at each position
- **ECO Classification** - Standard opening nomenclature

**API Endpoints:**
```
GET  /api/training/openings                   # List user's openings
GET  /api/training/openings/stats             # Opening statistics
GET  /api/training/openings/{opening_key}     # Specific opening details
GET  /api/training/lichess/opening            # Lichess Explorer data
GET  /api/training/lichess/variations         # Get variations for position
```

---

### 3. Journey (Progress Tracking)

**Purpose:** Track your chess improvement over time.

**Components:**
- `Journey.jsx` / `JourneyV2.jsx` - Progress dashboard
- `ChessJourney.jsx` - Detailed journey view

**Features:**
- **Game History** - All analyzed games with results
- **Rating Trajectory** - Rating changes over time
- **Weakness Trends** - Track recurring issues
- **Weekly Assessment** - AI-generated weekly review
- **Platform Integration** - Sync from Chess.com & Lichess
- **Background Sync** - Automatic game import (6-hour interval)

**API Endpoints:**
```
GET  /api/journey                   # Basic journey data
GET  /api/journey/comprehensive     # Full journey with stats
GET  /api/journey/weekly-assessment # Weekly AI assessment
GET  /api/journey/weakness-trends   # Weakness patterns over time
POST /api/journey/link-account      # Connect Chess.com/Lichess
GET  /api/journey/linked-accounts   # View connected accounts
POST /api/journey/sync-now          # Manual sync trigger
```

---

### 4. Reflect (Post-Game Reflection)

**Purpose:** Build self-awareness through structured reflection.

**Components:**
- `Reflect.jsx` - Reflection interface

**Features:**
- **Pending Reflections** - Games awaiting your reflection
- **Critical Moments** - AI-identified key positions
- **Contextual Tags** - Categorize your thinking errors
- **Thought Journal** - Record your reasoning at each move
- **Reflection Impact Analysis** - How reflection improves your play

**API Endpoints:**
```
GET  /api/reflect/pending                     # Games needing reflection
GET  /api/reflect/pending/count               # Count of pending
GET  /api/reflect/game/{game_id}/moments      # Key moments in a game
POST /api/reflect/submit                      # Submit reflection
POST /api/reflect/game/{game_id}/complete     # Mark reflection complete
POST /api/reflect/moment/contextual-tags      # Get contextual tags
POST /api/reflect/explain-moment              # AI explanation for moment
```

---

### 5. Dashboard

**Purpose:** Overview of your chess activity and progress.

**Components:**
- `Dashboard.jsx` - Main dashboard

**Features:**
- **Recent Games** - Quick access to latest games
- **Accuracy Trends** - Your accuracy over time
- **Weakness Summary** - Top areas to improve
- **Training Recommendations** - What to focus on
- **Badge Progress** - Gamification achievements

**API Endpoints:**
```
GET  /api/dashboard-stats           # Dashboard statistics
GET  /api/training-recommendations  # What to train
GET  /api/weakness-ranking          # Ranked weaknesses
```

---

### 6. Gamification

**Purpose:** Keep players engaged and motivated.

**Features:**
- **XP System** - Earn XP for activities
- **Levels** - Progress through levels
- **Achievements** - Unlock badges for milestones
- **Daily Rewards** - Streak bonuses
- **Leaderboard** - Compare with others

**Achievement Categories:**
- Puzzle achievements (solve streaks, accuracy)
- Game achievements (wins, accuracy milestones)
- Reflection achievements (consistent reflection)
- Training achievements (trap mastery)

**API Endpoints:**
```
GET  /api/gamification/progress               # XP and level
GET  /api/gamification/achievements           # Unlocked achievements
POST /api/gamification/daily-reward           # Claim daily reward
GET  /api/gamification/leaderboard            # Global leaderboard
GET  /api/gamification/achievement-definitions # All possible achievements
```

---

### 7. Badges System

**Purpose:** Visual recognition of chess competencies.

**Components:**
- `BadgeDetailModal.jsx` - Badge details view

**Features:**
- **Skill Badges** - Based on demonstrated abilities
- **Progress Tracking** - How close to earning each badge
- **Badge Details** - Evidence from your games
- **Badge Tiers** - Bronze, Silver, Gold, Platinum

**API Endpoints:**
```
GET  /api/badges                        # All badges with status
GET  /api/badges/{badge_key}/details    # Specific badge evidence
```

---

### 8. Coaching Loop

**Purpose:** Continuous improvement cycle.

**Features:**
- **Plan Generation** - AI creates improvement plan
- **Mission System** - Specific focus areas per game
- **Habit Tracking** - Build good chess habits
- **Discipline Checks** - Did you follow your plan?
- **Focus Plan** - What to work on this week

**API Endpoints:**
```
GET  /api/focus-plan                    # Current focus plan
POST /api/focus-plan/regenerate         # Create new plan
POST /api/focus-plan/mission/start      # Start a mission
POST /api/focus-plan/mission/complete   # Complete mission
GET  /api/coaching-loop/profile         # Coaching profile
POST /api/coaching-loop/audit-game/{game_id} # Audit game vs plan
```

---

### 9. Notifications

**Purpose:** Keep users engaged and informed.

**Features:**
- **In-App Notifications** - Game analysis complete, achievements, etc.
- **Push Notifications** - Mobile push support
- **Email Summaries** - Weekly digest
- **Notification Center** - View all notifications

**API Endpoints:**
```
GET  /api/notifications                       # Get notifications
POST /api/notifications/{id}/read             # Mark as read
POST /api/notifications/read-all              # Mark all read
POST /api/notifications/register-device       # Register for push
GET  /api/settings/email-notifications        # Email preferences
PUT  /api/settings/email-notifications        # Update preferences
```

---

## Data Models

### User
```javascript
{
  user_id: string,
  email: string,
  name: string,
  picture: string,
  linked_accounts: {
    chess_com: { username: string, linked_at: date },
    lichess: { username: string, linked_at: date }
  },
  preferences: {
    coach_mode: boolean,
    email_notifications: boolean
  },
  created_at: date,
  last_login: date
}
```

### Game
```javascript
{
  game_id: string,
  user_id: string,
  pgn: string,
  source: "chess.com" | "lichess" | "manual",
  user_color: "white" | "black",
  opponent_name: string,
  result: "win" | "loss" | "draw",
  time_control: string,
  played_at: date,
  imported_at: date
}
```

### Game Analysis
```javascript
{
  game_id: string,
  user_id: string,
  stockfish_analysis: {
    move_evaluations: [{
      move_number: number,
      move: string,
      fen_before: string,
      fen_after: string,
      eval_before: number,
      eval_after: number,
      cp_loss: number,
      best_move: string,
      mistake_type: string,
      phase: "opening" | "middlegame" | "endgame"
    }],
    accuracy: number,
    blunders: number,
    mistakes: number,
    inaccuracies: number
  },
  opening: { eco: string, name: string },
  created_at: date
}
```

### Puzzle Rating
```javascript
{
  user_id: string,
  puzzle_rating: number,  // Starts at 1200
  highest_rating: number,
  current_streak: number,
  best_streak: number,
  total_puzzles: number,
  puzzles_solved: number,
  level: "beginner" | "easy" | "intermediate" | "advanced" | "expert" | "master",
  achievements: string[],
  last_puzzle_at: date
}
```

### Trap Statistics
```javascript
{
  user_id: string,
  trap_key: string,
  mode: "execution" | "avoidance" | "recognition",
  attempts: number,
  successes: number,
  failures: number,
  last_attempted: date
}
```

### Reflection
```javascript
{
  user_id: string,
  game_id: string,
  move_number: number,
  fen: string,
  reflection_text: string,
  tags: string[],
  intent: string,  // What user was trying to do
  created_at: date
}
```

### Community Puzzle
```javascript
{
  puzzle_id: string,
  source_game_id: string,
  source_user_id: string,
  fen: string,
  correct_move: string,
  difficulty: number,
  times_solved: number,
  times_attempted: number,
  featured: boolean,
  created_at: date
}
```

---

## Key Services

### 1. Stockfish Service (`stockfish_service.py`)
- Manages Stockfish engine instances
- Position evaluation with depth control
- Best move calculation
- Move validation
- Caching for performance

### 2. Coaching Classifier Service (`coaching_classifier_service.py`)
- Classifies moves into coaching categories
- Prophylactic move detection (h6, a6, etc.)
- Forcing tactic detection
- Determines what shows in Coach Mode vs Engine Mode

### 3. Mistake Explanation Service (`mistake_explanation_service.py`)
- Analyzes why a move was a mistake
- Generates LLM-powered explanations
- Detects tactical patterns (forks, pins, etc.)
- Capture move detection to prevent hallucinations

### 4. Interactive Training Service (`interactive_training_service.py`)
- Generates puzzles from user's games
- Validates puzzle attempts with Stockfish
- Provides detailed feedback on attempts

### 5. Puzzle Progression Service (`puzzle_progression_service.py`)
- Elo-based rating updates
- Level progression
- Achievement tracking
- Streak management

### 6. Trick Library Service (`trick_library_service.py`)
- Database of 30+ chess traps
- Practice position generation
- Move validation for all three modes
- Statistics tracking

### 7. Journey Service (`journey_service.py`)
- Background game sync
- Chess.com & Lichess API integration
- Progress calculation
- Weakness trend analysis

### 8. Blunder Intelligence Service (`blunder_intelligence_service.py`)
- Deep analysis of blunders
- Pattern recognition
- Thinking error categorization
- Evidence gathering for badges

---

## External Integrations

### Chess.com API
- Game history fetching
- Player statistics
- Automatic sync

### Lichess API
- Opening Explorer (position statistics)
- Game imports
- Player data

### OpenAI (via Emergent LLM Key)
- Natural language explanations
- Weekly assessments
- Coaching insights
- Plan generation

---

## Frontend Components

### Pages
| Page | File | Purpose |
|------|------|---------|
| Landing | `Landing.jsx` | Marketing/login page |
| Dashboard | `Dashboard.jsx` | Main overview |
| Lab | `Lab.jsx` | Game analysis |
| Training | `TrainingNew.jsx` | Puzzles & training |
| Journey | `JourneyV2.jsx` | Progress tracking |
| Reflect | `Reflect.jsx` | Post-game reflection |
| Import | `ImportGames.jsx` | Manual game import |
| Settings | `Settings.jsx` | User preferences |

### Key Components
| Component | Purpose |
|-----------|---------|
| `CoachBoard.jsx` | Interactive chessboard |
| `LichessBoard.jsx` | Board using Lichess assets |
| `OpeningTrainer.jsx` | Opening & trap training |
| `BadgeDetailModal.jsx` | Badge evidence display |
| `MistakeMastery.jsx` | Mistake pattern training |
| `Layout.jsx` | App shell with navigation |
| `NotificationBell.jsx` | Notification center |

---

## Authentication Flow

1. **Google OAuth**
   - User clicks "Sign in with Google"
   - Redirects to Google OAuth
   - Callback creates/updates user record
   - Session token stored in cookie

2. **Dev Login** (development only)
   - One-click login for testing
   - Creates test user with ID `test_session_*`

3. **Session Management**
   - Session token in HTTP-only cookie
   - 30-day expiration
   - Auto-refresh on activity

---

## Analysis Pipeline

1. **Game Import**
   - User connects Chess.com/Lichess OR uploads PGN
   - Background sync fetches new games

2. **Stockfish Analysis**
   - Each move evaluated at depth 18
   - Best move calculated
   - CP loss computed
   - Position cached for speed

3. **Move Classification**
   - Coaching Classifier determines category
   - Tactical patterns detected
   - Phase identified (opening/middle/endgame)

4. **Puzzle Generation**
   - Moves with cp_loss >= 150 OR forced tactics
   - Filter out "engine preferences"
   - Store as drillable puzzles

5. **Explanation Generation**
   - On-demand LLM explanation
   - Context includes tactical patterns
   - Coaching principles emphasized

---

## Configuration

### Environment Variables

**Backend (`/app/backend/.env`)**
```
MONGO_URL=mongodb://...
DB_NAME=chess_coach
EMERGENT_LLM_KEY=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
DEV_MODE=true  # Enables dev login
```

**Frontend (`/app/frontend/.env`)**
```
REACT_APP_BACKEND_URL=https://...
```

---

## Key User Flows

### 1. First-Time User
1. Land on homepage → Click "Sign in with Google"
2. Authorize app → Redirect to dashboard
3. Prompt to connect Chess.com/Lichess
4. Background sync imports recent games
5. Navigate to Training for first puzzles

### 2. Post-Game Analysis
1. Game synced automatically (or manual import)
2. Navigate to Lab → Select game
3. View Coach Mode analysis
4. Click mistakes to expand explanations
5. Toggle to Engine Mode for full details
6. Practice critical moments

### 3. Daily Training
1. Navigate to Training tab
2. View puzzle rating and streak
3. Solve puzzles from your games
4. Review mistakes with explanations
5. Check Trick Library for new traps

### 4. Reflection Flow
1. Navigate to Reflect tab
2. See pending games for reflection
3. Click into game → View critical moments
4. Record your thinking at each moment
5. Compare intent vs reality
6. Complete reflection

---

## Recent Changes (Feb 2026)

### Coaching Philosophy Update
- **Coach Mode/Engine Mode toggle** in Lab
- **New move categorization**: Blunder > Tactical > Strategic > Engine Preference
- **Prophylactic move handling**: Good/Phantom/Wrong classification
- **Puzzle threshold raised** from 100cp to 150cp
- **Capture move detection** prevents "undefended" hallucinations

### Puzzle Difficulty Progression
- **Elo-based rating system** (K-factor=32)
- **Level-up celebrations** with modal
- **Achievement system** with toasts
- **Rating change badges** in feedback

### Trick Library Complete
- **30+ traps** with full metadata
- **Three modes**: Execution, Avoidance, Recognition
- **Statistics tracking** per trap
- **Personalized recommendations**

### Community Learning
- **Shared puzzle pool** from all users
- **Integrated into main Puzzles tab**
- **Source attribution** (Your Game vs Community)

---

## Testing

### Test Files
```
/app/tests/
├── test_puzzle_validation.py
├── test_trick_library_modes.py
├── test_community_learning.py
└── ...
```

### Test Reports
```
/app/test_reports/
├── iteration_1.json
├── iteration_2.json
└── ...
```

### Test User
- Dev Login creates: `test_session_{uuid}`
- Use Cookie: `session_token=test_session_...`

---

## Performance Considerations

1. **Stockfish Caching**
   - Position evaluations cached in MongoDB
   - Avoids re-analyzing same positions
   - Cache hit rate typically >60%

2. **Background Processing**
   - Game sync runs in background
   - 6-hour interval for batch sync
   - 5-minute interval for real-time monitoring

3. **Lazy Loading**
   - Explanations generated on-demand
   - PV lines fetched when expanded
   - Images loaded progressively

---

## Known Limitations

1. **Analysis Depth** - Stockfish runs at depth 18 (not tournament depth)
2. **Opening Database** - Limited to common lines from Lichess
3. **Trap Library** - 30+ traps, not exhaustive
4. **Reflection Validation** - Intent validation not yet integrated with coaching

---

## Roadmap (Upcoming)

1. **Reflection Integration** - Validate user intent against position reality
2. **Re-analyze Existing Games** - Apply new coaching classification
3. **Repeated Pattern Detection** - Surface personal "leaks"
4. **Thinking Score** - Separate from engine score
5. **Advanced Trap Recommendations** - Based on opening repertoire

---

## API Quick Reference

### Authentication
```
GET  /api/auth/google/login
GET  /api/auth/dev-login
GET  /api/auth/me
POST /api/auth/logout
```

### Games
```
GET  /api/games
GET  /api/games/{game_id}
POST /api/import-games
POST /api/analyze-game
```

### Training
```
GET  /api/training/puzzles
POST /api/training/puzzle/validate
GET  /api/training/puzzle-progress
GET  /api/training/tricks
POST /api/training/tricks/record-attempt
```

### Analysis
```
GET  /api/lab/{game_id}
POST /api/explain-mistake
GET  /api/eval/position
```

### Progress
```
GET  /api/journey
GET  /api/progress
GET  /api/badges
GET  /api/gamification/progress
```

---

*Last Updated: February 23, 2026*
