# ChessGuru — Product Requirements Document

## Vision
A hyper-personalized chess coaching platform that tracks who you are as a player across every game. Not another analysis tool — a coach that remembers your patterns, knows your weaknesses by name, and tells you exactly what to fix.

## Core Principles
1. **One screen = one job** — each page has a single clear purpose
2. **Teaching, not commenting** — every coaching text includes WHY and WHAT TO DO NEXT TIME
3. **Adaptive difficulty** — 1100 players see blunders, 1600 players see inaccuracies
4. **Identity over statistics** — "The Blind Spot" means more than "57% accuracy"
5. **Coach-first UX** — the coach talks TO you, doesn't wait for you to ask

## User Personas
- **Primary**: 800-1500 rated chess.com/lichess players who want to improve but don't know HOW
- **Language**: Many are non-native English speakers — simple, clear language
- **Behavior**: They play games, lose, feel frustrated, want answers

## Features (Implemented)

### Home Page — Coach Dashboard
- Dynamic coach greeting based on streak/patterns/last game
- Last game board with critical position
- Contextual primary action (train/review/play based on state)
- Patterns across games + Chess DNA

### Lab — Coach's Review Queue  
- Smart game picker (recurring pattern > thrown > decisive blunder)
- 3-state review tracking (not started → in progress → reviewed)
- Auto-review when reaching last move
- Coach prompt to switch to Coach view after decrypt

### Game Review (Lab V2)
- **Decrypt Mode**: Move-by-move coaching with adaptive filtering
- **Coach Mode**: 3-tab panel (Summary / Habits / Memory)
- Rich inline flagging for developer debugging

### Play with Coach
- Live game against AI with real-time coaching
- Opponent plan reading from Stockfish PV
- Pre-move checklist

### Training
- Positions extracted from real games (community pool)
- Pattern-filtered: calculation_depth, tactical_miss, etc.
- Solve feedback with candidate moves + ideas

### Progress
- Accuracy journey chart
- Win rate + blunder rate trends  
- Danger zones (critical patterns)
- Chess Identity (archetype + biggest leak)

## Design System
- **Background**: Warm off-white `#F5F3F0`
- **Cards**: White `#FFFFFF` with subtle border
- **Primary**: Wine Red `#722F37`
- **Accent**: Gold `#CBA135` (text: `#8B6F1F`)
- **Fonts**: Playfair Display (serif headings), DM Sans (body), JetBrains Mono (mono)
- **Logo**: Gold chess knight SVG (`/chessguru-logo.svg`)

## Changelog

### March 28, 2026
- Home Page V4: coach-first design with dynamic messaging
- Progress Page V2: trajectory + danger zones + chess identity
- Lab rebuilt as coach's review queue with smart picker
- Auto-mark reviewed when reaching last move + coach prompt
- Training: solve feedback with candidate moves (board fix in progress)
- Auto-extract training positions in analysis_worker
- Opponent plan reading from PV (kingside attacks, pawn storms, exchanges)

### March 27, 2026
- Coach Insight Panel: 3-tab system (Summary/Habits/Memory)
- Adaptive game decryption V5: rating-based filtering
- Habits fix: mate blunders excluded from hanging pieces check
- V5 PV consequence analysis: walks PV for captures/checks
- Teaching-focused coaching language (replaced cute nicknames)
- Minor inaccuracy softening (cp_loss < 50)
- Full light theme applied across all pages
- ChessGuru branding (logo, name, favicon)
- Premium landing page with coach persona section
- Rich feedback diagnostics for debugging

### Earlier (Feb-March 2026)
- Core V5 coaching engine
- Book move false positives fixed
- Checkmate blunder hallucination fixed
- Inline flagging system
- Community Intelligence Training
- Opening World + Endgame Lessons
- Play with Coach mode
- SVG logo generation
