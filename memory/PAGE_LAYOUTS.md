# ChessGuru — Page Layouts & Design Specification

## Design System
- **Background**: Warm off-white `#F5F3F0` (CSS var `--background: 37 16% 96%`)
- **Cards**: White `#FFFFFF` with 1px border `hsl(35 10% 87%)`, rounded-sm
- **Primary accent**: Wine Red `#722F37` — used for CTAs, loss indicators, critical badges, danger states
- **Gold accent**: `#CBA135` for section labels, active states, win indicators. Text gold: `#8B6F1F`
- **Win color**: `#16a34a` (emerald-600)
- **Fonts**: 
  - Headings: `Playfair Display` serif — tracking-tight, font-normal weight
  - Body: `DM Sans` — light weight (300-400)
  - Labels/mono: `JetBrains Mono` — used for section labels, stats, badges
- **Section labels**: ALL CAPS, 10px, letter-spacing 0.2em, JetBrains Mono, gold color `#8B6F1F`
- **No emojis, no icons in labels** — icons only as functional elements
- **Logo**: Gold chess knight SVG + "ChessGuru" in Playfair Display

---

## Sidebar Layout (All Pages)
```
┌─────────────────┐
│ 🏇 ChessGuru  < │  ← Logo + name, collapse button
│                 │
│ ○ Home          │  ← Thin icons (strokeWidth 1.5)
│ ○ Lab           │  ← Active: gold left border (2px #CBA135)
│ ○ Openings      │     + subtle bg-white/3%
│ ○ Progress      │
│                 │
│ ██ Play w Coach │  ← Gold bg button (#CBA135), dark text
│                 │
│ ○ Admin         │  ← Only for admin users
│                 │
│─────────────────│
│ ○ Light/Dark    │
│ ○ Settings      │
│ 👤 User Name    │
└─────────────────┘
```
- Width: 224px expanded, 64px collapsed
- Background: `#F0EDE8` (slightly darker than page bg)
- Border-right: 1px solid rgba(0,0,0,0.05)
- Nav items: text-sm, font-light, text-gray-500 default, text-gray-900 active
- Hover: bg-black/3%

---

## 1. Landing Page

```
┌──────────────────────────────────────────────────┐
│ NAVBAR (fixed, blur backdrop)                     │
│ [Logo+Name]              [Theme] [Get Started]    │
├──────────────────────────────────────────────────┤
│                                                   │
│ HERO (full viewport height)                       │
│ ┌─────────────────┬─────────────────────┐        │
│ │ AI CHESS COACHING│                     │        │
│ │ (gold mono label)│   Chess king        │        │
│ │                  │   photograph        │        │
│ │ Your coach       │   (faded with       │        │
│ │ remembers        │    white gradient   │        │
│ │ everything.      │    overlay from     │        │
│ │                  │    left to right)   │        │
│ │ "remembers" in   │                     │        │
│ │ Wine Red         │                     │        │
│ │                  │                     │        │
│ │ [Start Free]     │                     │        │
│ │ [See how it works]│                    │        │
│ └─────────────────┴─────────────────────┘        │
│                                                   │
├──────────────────────────────────────────────────┤
│ COACH PERSONA (dark section — bg-gray-950)        │
│ Dramatic contrast against the light page          │
│                                                   │
│    MEET YOUR COACH (gold label)                   │
│                                                   │
│    "You didn't lose over many mistakes.           │
│     You lost in one moment                        │
│     of inattention."                              │
│    (italic Playfair, "one moment" in Wine Red)    │
│                                                   │
│    Subtext in gray-500                            │
│                                                   │
├──────────────────────────────────────────────────┤
│ FEATURES (bento grid on light bg)                 │
│                                                   │
│ WHAT MAKES THIS DIFFERENT (gold label)            │
│ Built around you, not the engine.                 │
│ ("you" in Wine Red)                               │
│                                                   │
│ ┌─────────────────────────┬────────────┐         │
│ │ Chess DNA (large, 8col) │ Adaptive   │         │
│ │ "Know who you are       │ Decryption │         │
│ │  as a player"           │ (4col)     │         │
│ │                         ├────────────┤         │
│ │ Archetype tags:         │ Pattern    │         │
│ │ [The Thrower]           │ Memory     │         │
│ │ [The Blind Spot]        │ (4col)     │         │
│ │ [The Strategist]        │            │         │
│ ├────────────┬────────────┴────────────┤         │
│ │ Community  │ Play With Coach         │         │
│ │ Training   │ (6col)                  │         │
│ │ (6col)     │                         │         │
│ └────────────┴─────────────────────────┘         │
│                                                   │
│ Feature cards: bg-card, border-border, gold       │
│ labels, Playfair titles, muted-foreground body    │
│                                                   │
├──────────────────────────────────────────────────┤
│ STATS (4 columns, border-t/b)                     │
│  24/7    │   100%    │   <2s    │   Free          │
│ Available│Personalized│Analysis │ To start         │
│ (Playfair numbers, JetBrains Mono labels)         │
│                                                   │
├──────────────────────────────────────────────────┤
│ CTA                                               │
│ "Stop guessing. Start knowing."                   │
│ ("Start knowing." in Wine Red)                    │
│ [Start Free with Google] (Wine Red button)        │
│                                                   │
├──────────────────────────────────────────────────┤
│ FOOTER                                            │
│ [Logo] ChessGuru    Built with AI. For chess.     │
└──────────────────────────────────────────────────┘
```

---

## 2. Home Page (Coach-First Dashboard)

```
┌─ SIDEBAR ─┬──────────────────────────────────────┐
│           │                                       │
│           │  COACH MESSAGE (Playfair, text-2xl)   │
│           │  "Calculation Depth is showing up     │
│           │   in almost every game."              │
│           │  subtext: "19 times recently. This    │
│           │  is your biggest leak right now."     │
│           │                                       │
│           │  ┌──────────────────┬────────────┐   │
│           │  │ LAST GAME        │ ACTIONS    │   │
│           │  │ (3/5 width)      │ (2/5 width)│   │
│           │  │                  │            │   │
│           │  │ ┌──────┬───────┐│ ██████████ │   │
│           │  │ │Chess │vs Name││ Train Calc │   │
│           │  │ │Board │WON/LOST│ Depth      │   │
│           │  │ │(half)│       ││ (Wine Red) │   │
│           │  │ │      │Diag-  ││            │   │
│           │  │ │      │nosis  ││ ────────── │   │
│           │  │ │      │       ││ Play with  │   │
│           │  │ │      │Move 28││ Coach      │   │
│           │  │ │      │Kh8→Rf7││            │   │
│           │  │ │      │Review>││ ────────── │   │
│           │  │ └──────┴───────┘│ Study      │   │
│           │  │                  │ Openings   │   │
│           │  └──────────────────┴────────────┘   │
│           │                                       │
│           │  ┌──────────────────┬────────────┐   │
│           │  │PATTERNS ACROSS   │YOUR CHESS  │   │
│           │  │GAMES (1/2)       │DNA (1/2)   │   │
│           │  │                  │            │   │
│           │  │• Calc Depth  19x │ Developing │   │
│           │  │• Missing Tac 14x │            │   │
│           │  │• Short Calc   8x │ Before:... │   │
│           │  │(each clickable→  │ After:...  │   │
│           │  │ training)        │            │   │
│           │  │                  │ ─────────  │   │
│           │  │                  │ Rating     │   │
│           │  │                  │ projection │   │
│           │  └──────────────────┴────────────┘   │
│           │                                       │
│           │  38 games          58% accuracy       │
│           │  (footer, mono, muted)                │
└───────────┴───────────────────────────────────────┘
```

**Coach Message Logic**:
- 3+ losses streak → "Stop playing. Start reviewing." (action: Review Losses)
- 3+ wins streak + sloppy → "Momentum is real. But those wins had blunders."
- Critical pattern dominant → "[Pattern] is showing up in almost every game."
- Lost last game → "Last game didn't go well. Let's see why."
- Default → "Let's get better today."

**Primary Action Card**: Wine Red bg, white text. Changes based on context:
- "Train Calculation Depth" / "Review This Loss" / "Review Your Losses"

---

## 3. Lab Page (Coach's Review Queue)

```
┌─ SIDEBAR ─┬──────────────────────────────────────┐
│           │                                       │
│           │  Lab                    [Import]      │
│           │  1/38 reviewed (mono)                 │
│           │                                       │
│           │  ┌──────────────────────────────┐    │
│           │  │ 6W 9L last 15 games          │    │
│           │  │ 5 games thrown from winning   │    │
│           │  │ positions. That's where your  │    │
│           │  │ rating is leaking.            │    │
│           │  └──────────────────────────────┘    │
│           │                                       │
│           │  COACH'S PICK (gold label)            │
│           │  ┌──────────────────────────────┐    │
│           │  │▎vs BigDthree  WON  62.3%     │ >  │
│           │  │▎                              │    │
│           │  │▎You've made this mistake      │    │
│           │  │▎(calculation depth) 136 times.│    │
│           │  │▎Let's fix it here.            │    │
│           │  └──────────────────────────────┘    │
│           │  (gold left border 3px)               │
│           │                                       │
│           │  TO REVIEW (36 MORE) (gold label)     │
│           │  ┌──────────────────────────────┐    │
│           │  │▌vs agmadbilal                │ ✓  │
│           │  │ LOST · Giuoco Piano 4.O O    │    │
│           │  │──────────────────────────────│    │
│           │  │▌vs Aboamr57                  │ ✓  │
│           │  │ LOST · Scandinavian · 4B     │    │
│           │  │──────────────────────────────│    │
│           │  │▌vs abdullah7OO4  In Progress │ ✓  │
│           │  │ WON · Nimzowitsch Larsen     │    │
│           │  └──────────────────────────────┘    │
│           │                                       │
│           │  ▌= color bar (green=win, red=loss)   │
│           │  ✓ = mark as reviewed button          │
│           │  "In Progress" = amber badge          │
│           │                                       │
│           │  REVIEWED (1) (muted label)           │
│           │  ✓ vs MrTyulu  WON  (50% opacity)    │
└───────────┴───────────────────────────────────────┘
```

**Smart Game Picker Priority**:
1. Recurring pattern (same mistake 3+ times across games)
2. Thrown game (was winning, lost)
3. Single decisive blunder
4. Skip: clean wins, already reviewed

**Review States**: not_started → in_progress (opened game) → reviewed (reached last move)

---

## 4. Game Review Page

```
┌─ SIDEBAR ─┬──────────────────────────────────────┐
│           │ ← Back  Game Review  vs Name  Lost 51%│
│           │                      [Coach] [Decrypt]│
│           ├──────────────────────┬────────────────┤
│           │                      │                │
│           │                      │ COACH MODE:    │
│           │    CHESS BOARD       │ ┌────────────┐ │
│           │    (55% width)       │ │Summary│Hab│Mem│
│           │                      │ │            │ │
│           │    Interactive       │ │ Diagnosis: │ │
│           │    with arrows       │ │ MATE_BLIND │ │
│           │                      │ │            │ │
│           │                      │ │ Root cause │ │
│           │                      │ │ text...    │ │
│           │                      │ │            │ │
│           │                      │ │ Context    │ │
│           │                      │ │ bullets... │ │
│           │                      │ │            │ │
│           │                      │ │ Coach note │ │
│           │                      │ └────────────┘ │
│           │                      │                │
│           │  ┌──────────────────┐│ DECRYPT MODE: │
│           │  │ Move navigation  ││ Coaching card │
│           │  │ |< < ▶ > >|     ││ for current   │
│           │  │ Move 15 / 34    ││ move with     │
│           │  └──────────────────┘│ narrative,    │
│           │                      │ plan, better  │
│           │  1.e4 e5 2.Nf3 Nc6  │ approach      │
│           │  (move list)         │               │
│           ├──────────────────────┴────────────────┤
│           │ [Sticky bar after reaching last move] │
│           │ "You've reviewed every move. See the  │
│           │  full picture."  [Open Coach View]    │
└───────────┴───────────────────────────────────────┘
```

**Coach/Decrypt Toggle**: Wine red underline for Coach, Gold underline for Decrypt
**Coach 3 Tabs**: Summary (one brutal truth), Habits (pass/fail checklist), Memory (Chess DNA + rating projection)

---

## 5. Progress Page

```
┌─ SIDEBAR ─┬──────────────────────────────────────┐
│           │                                       │
│           │  Progress                             │
│           │  38 games analyzed (mono)             │
│           │                                       │
│           │  YOUR ACCURACY JOURNEY (gold)    55%↘ │
│           │  ┌──────────────────────────────┐    │
│           │  │  ·  ·      ·                 │    │
│           │  │ ·  ·  · ·   · · ·   · · ·  ·│    │
│           │  │      ·    ·       · ·     ·   │    │
│           │  │ (gold line, green/red dots,   │    │
│           │  │  gold gradient fill under)    │    │
│           │  └──────────────────────────────┘    │
│           │  Slipping: 60% → 55% — slow down     │
│           │                                       │
│           │  ┌─────────────┬─────────────────┐   │
│           │  │ WIN RATE    │ BLUNDERS RISING  │   │
│           │  │             │ (RED label if ↑) │   │
│           │  │ 5W 5L → 5W │ 1.6/g → 2.8/g   │   │
│           │  │     5L      │ (2.8 in RED)     │   │
│           │  │             │                  │   │
│           │  │ Holding     │ Slow down. Check │   │
│           │  │ steady.     │ threats before   │   │
│           │  │             │ every move.      │   │
│           │  └─────────────┴─────────────────┘   │
│           │                                       │
│           │  DANGER ZONES (gold label)            │
│           │  ┌──────────────────────────────┐    │
│           │  │ ⚠ Calculation Depth  19x CRIT│ >  │
│           │  │ ⚠ Missing Tactics    14x CRIT│ >  │
│           │  │ ⚠ Short Calculation   8x MED │ >  │
│           │  └──────────────────────────────┘    │
│           │  Click a pattern to train it.         │
│           │                                       │
│           │  YOUR CHESS IDENTITY (gold label)     │
│           │  ┌──────────────────────────────┐    │
│           │  │ Developing    BIGGEST LEAK:   │    │
│           │  │               TACTICAL ERROR  │    │
│           │  │ Appeared 210 times.           │    │
│           │  └──────────────────────────────┘    │
│           │                                       │
│           │  LAST 10 GAMES (gold label)           │
│           │  ┌──────────────────────────────┐    │
│           │  │ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██│    │
│           │  │ 54 42 54 63 68 49 41 54 42 57│    │
│           │  │ older →                recent │    │
│           │  └──────────────────────────────┘    │
│           │  (bars: green=win, wine=loss,         │
│           │   opacity = accuracy/100)             │
└───────────┴───────────────────────────────────────┘
```

---

## 6. Training Page

```
┌─ SIDEBAR ─┬──────────────────────────────────────┐
│           │                                       │
│           │  Train                          1/18  │
│           │  8 from your games · 10 community     │
│           │  ═══════════════════════ (progress)   │
│           │                                       │
│           │  [All] [Tactical Miss] [Calc Depth]   │
│           │  (filter tabs, active=amber bg)        │
│           │                                       │
│           │  ┌──────────────────┬────────────┐   │
│           │  │                  │             │   │
│           │  │  CHESS BOARD     │ Find the    │   │
│           │  │  (interactive)   │ Best Move   │   │
│           │  │                  │             │   │
│           │  │  User plays the  │ "You made a │   │
│           │  │  move they think │ mistake     │   │
│           │  │  is best         │ here."      │   │
│           │  │                  │             │   │
│           │  │                  │ [Calc Depth]│   │
│           │  │                  │ [medium]    │   │
│           │  │                  │             │   │
│           │  │                  ├────────────┤   │
│           │  │                  │ Your        │   │
│           │  │                  │ Patterns    │   │
│           │  │                  │             │   │
│           │  │                  │ Calc  4/5━━ │   │
│           │  │                  │ Pos   2/3━━ │   │
│           │  │                  │ Pin   1/2━━ │   │
│           │  └──────────────────┴────────────┘   │
│           │  From your game · Move 12             │
│           │                                       │
│           │  AFTER SOLVING (replaces prompt):      │
│           │  ┌────────────────────────────┐       │
│           │  │ ✓ You Found It (green)     │       │
│           │  │ or                         │       │
│           │  │ ✗ Not Quite (red)          │       │
│           │  │                            │       │
│           │  │ Best move was: Qh4+        │       │
│           │  │ Original player: gxh6      │       │
│           │  │                            │       │
│           │  │ IDEAS IN THIS POSITION:    │       │
│           │  │ [Qh4+] gives check [BEST] │       │
│           │  │ [e4] central control       │       │
│           │  │ [Qf6+] gives check         │       │
│           │  │                            │       │
│           │  │ 65% of players missed this │       │
│           │  │                            │       │
│           │  │ [Next] or [Retry]          │       │
│           │  └────────────────────────────┘       │
└───────────┴───────────────────────────────────────┘
```

---

## 7. Admin Dashboard

```
┌─ SIDEBAR ─┬──────────────────────────────────────┐
│           │                                       │
│           │  Admin Dashboard                      │
│           │  [Overview] [Users] [Feedback]         │
│           │                                       │
│           │  ┌────┬────┬────┬────┐               │
│           │  │Tot │Act │Act │Tot │               │
│           │  │Usr │ 7d │30d │Gam │               │
│           │  │ 20 │  1 │  2 │ 89 │               │
│           │  ├────┼────┼────┼────┤               │
│           │  │Ana │Com │Fdbk│Fdbk│               │
│           │  │lyse│Pool│Pend│Tot │               │
│           │  │ 86 │136 │ 15 │ 21 │               │
│           │  └────┴────┴────┴────┘               │
│           │                                       │
│           │  Recent Signups                       │
│           │  ┌──────────────────────────────┐    │
│           │  │ Role Test User    Admin Mar26│    │
│           │  │ First User        User  Mar26│    │
│           │  │ Test Admin User   User  Mar26│    │
│           │  └──────────────────────────────┘    │
│           │                                       │
│           │  Feedback tab: Full diagnostics       │
│           │  per flag (FEN, move, best_move,      │
│           │  cp_loss, PV, candidates, user note)  │
└───────────┴───────────────────────────────────────┘
```

---

## Component Patterns

### Section Label
```
text-[10px] tracking-[0.2em] uppercase font-mono color: #8B6F1F
Example: "YOUR ACCURACY JOURNEY", "COACH'S PICK", "DANGER ZONES"
```

### Result Badge
```
Won:  bg: rgba(22,163,74,0.1)  text: #16a34a  "WON"
Lost: bg: rgba(114,47,55,0.08) text: #722F37  "LOST"
Draw: bg: rgba(0,0,0,0.05)     text: #888     "DRAW"
font: JetBrains Mono, 10px
```

### Action Card
```
Primary:   bg: #722F37, text: white, icon left, chevron right
Secondary: bg-card, border-border, text-foreground
Both: p-4, rounded-sm, hover:shadow-sm, cursor-pointer
```

### Severity Badge
```
Critical: bg: rgba(114,47,55,0.06) text: #722F37 "CRITICAL"
Medium:   bg: rgba(203,161,53,0.1) text: #8B6F1F "MEDIUM"
font: JetBrains Mono, 9px, uppercase
```

### Game Row (in Lab)
```
┌─▌───────────────────────────────────┬───┐
│ ▌ vs OpponentName    [In Progress]  │ ✓ │
│ ▌ LOST · Opening Name · 4B         │   │
└─▌───────────────────────────────────┴───┘
▌ = 1px color bar (green/red), ✓ = mark reviewed
```
