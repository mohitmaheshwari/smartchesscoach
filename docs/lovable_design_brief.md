# ChessGuru — Design Brief for Lovable

> Paste this whole document into Lovable. It describes an existing, working product
> (ChessGuru / chessguru.ai) and asks for a **fresh, modern, fully responsive UI redesign**.
> The backend, data, and logic already exist — we want **new front-end designs only**.
> Build in **React + Tailwind CSS** with **shadcn/ui** components. Support **light and dark mode**.
> Every screen must be **fully responsive: mobile (≥360px), tablet (≥768px), and desktop (≥1024px)**.

---

## 1. What the product is

ChessGuru is a **personalized chess coaching app**, not a puzzle app. It watches how a player
actually plays, remembers their specific mistake patterns across games, and builds training
around *their* weaknesses. The core promise to the user is:

> "A coach who knows *you*, remembers what you've worked on, shows you you're improving, and turns
> your own mistakes into your training."

**Target users:** 600–1500 rated club players stuck on a plateau. They are NOT chess experts.
- Use plain, warm, encouraging language. **No chess jargon** ("fianchetto", "zwischenzug",
  "prophylaxis", "tempo"). Name the square, name the idea.
- They remember *patterns* ("I got forked", "my queen came out too early"), not move notation.
- Lead with the idea/feeling, not the algebraic move.

**Tone of the UI:** calm, premium, confidence-building. Feels like a great human coach in your
pocket — never a cold engine readout, never a noisy gamified casino.

---

## 2. Brand & visual direction

- **Mood:** warm, focused, premium, modern. Think "Headspace meets a chess coach." Clean, lots of
  breathing room, soft shadows, rounded corners (xl–2xl radii). Confident but gentle.
- **Color (current app uses an amber-primary system — evolve it, don't fight it):** The existing
  product's locked palette is: **amber/gold as the primary brand color**, **teal for data/progress**,
  **emerald for wins/mastered**, **rose (soft) for blunders/mistakes**. You may modernize and refine
  this, but keep the warm amber identity. Use red/rose sparingly and softly — mistakes must feel
  coachable, not punishing. Severity scale: good = emerald, inaccuracy = amber, mistake = orange,
  blunder = soft rose.
- **Typography:** a clean modern sans for UI (Inter or similar). For the **coach's voice / teaching
  text**, use a friendly serif (e.g. Fraunces) to make coaching feel human and distinct from data.
- **Motion (timing system to standardize on):** subtle, purposeful (Framer Motion).
  - Micro-interactions **150ms**, standard transitions **300ms** (snappy settle), page transitions
    **600ms**, chart/number animations **800ms**. Stagger grouped items at **~60ms** steps.
  - Buttons: scale **1.02** + soft glow on hover, **0.98** on active. Cards: lift **2px** + deepen
    shadow on hover.
  - Board: pieces slide ~200ms; captured piece fades + shrinks; coach messages slide in from the
    side with a typing-shimmer. Numbers/stats count up; sparklines draw left-to-right.
  - **Everything respects `prefers-reduced-motion`.** No gratuitous animation; motion is meaning.
- **Theme:** full **light and dark mode**, toggle in settings. Dark mode is the default many chess
  players prefer — make it first-class, not an afterthought.
- **Imagery:** chessboards rendered with react-chessboard. Boards must look crisp on every screen
  size and be the visual hero where present.

---

## 3. Global layout & responsive navigation

**Desktop (≥1024px):** persistent left sidebar nav (logo + nav items + user avatar at bottom).
Main content area centered, max-width ~1200px. Where a screen has a board + coaching, use a
**two-column layout**: board left, coaching panel right.

**Tablet (768–1023px):** collapsible sidebar OR top bar. Board + coaching can stay two-column if it
fits, otherwise stack with the board on top and coaching below.

**Mobile (≤767px):** **bottom tab bar** with 4–5 primary destinations (Home, Play, Train, Lab,
Profile). Everything is single-column and vertically scrollable. On the Play and Game-Review
screens, the **board sits on top** and the **coaching panel becomes a bottom sheet / stacked card**
below it (or a swipe-up drawer). The board must never be smaller than usable — prioritize it.

**Primary nav destinations:**
1. **Home** (the dashboard / coach's daily view)
2. **Play** (Play with Coach)
3. **Train** (drills, daily mission, pattern training)
4. **Lab** (game review & history)
5. **Profile / Progress** (improvement, settings)

---

## 4. Screens (with the real content each must show)

### 4.1 Onboarding (first run)
A short, warm 2–3 step flow.
- **Step 1 — Welcome + value:** one sentence on what ChessGuru does. A "Try it now" path that lets a
  brand-new user **play one quick game with the coach or solve 3 sample drills immediately** — show
  the coaching magic *before* asking for anything. (This "instant value" empty-state is important.)
- **Step 2 — Link account:** connect a Chess.com or Lichess username to import real games. Show
  clearly why ("so your coach can study how *you* play"). Validate username, show success state.
- **Step 3 — Instant Chess DNA:** after import, a delightful reveal of the player's profile/style
  (strengths, top weakness, rating band) as a payoff.
- Design empty-states for "no games yet" gracefully — never a dead end.

### 4.2 Home / Coach's Dashboard (the emotional hook)
This is the most important screen. When the user opens the app it must feel like **"my coach
remembers me and sees my progress,"** not a stats dashboard. Sections:

- **Time-of-day greeting** with the player's name.
- **Today's Mission (hero card):** the daily personalized task, e.g. *"Today's mission: solve 5 fork
  drills (10 min)."* with a big start button and a progress ring (e.g. 2/5 done).
- **Training streak:** a 🔥 streak counter ("7-day streak — keep it alive"), with subtle stakes.
- **"Your coach remembers" card:** continuity from coach memory, e.g. *"You've mastered the Fried
  Liver. We've been working on hanging pieces — down from 5 to 2 last week. Next up: endgames."*
- **Coach's prescription / Pattern of the Day:** the #1 thing to fix right now, specific and
  evidence-backed, e.g. *"You keep leaving pieces undefended to forks — 3 games this week. Before
  each move, ask: can they fork me?"* with a "Fix this" button → drills.
- **Improvement trend:** concrete proof of progress, e.g. *"23% fewer blunders than your last 10
  games."* Small chart or trend chip. Hide gracefully if not enough data.
- **Fundamentals snapshot:** a small radar/bar set — Opening / Tactics / Endgame / King Safety
  scored 0–100 with a "you vs. typical 1200 player" benchmark, highlighting the weakest domain.
- **Last game card:** small board thumbnail of the last game, opening name, result, one-line recap,
  "Review →" button.
- **Win-streak banner:** if the player is on 3+ wins, a celebratory positive-momentum banner.
- Quiet nav tiles to Play / Lab / Train / Openings.

### 4.3 Play with Coach (live coaching board)
The interactive game screen. **Two-column on desktop (board left, coach panel right); stacked with
board-on-top + coach bottom-sheet on mobile.**

- **Board** (hero), with move highlights, and **coach arrows** drawn on the board (green arrow to a
  better move when relevant). Coordinate labels, last-move highlight, check highlight.
- **Coach panel** — the live, two-part coaching flow that is the product's signature:
  1. After the **user's move**: a coaching card showing the move, a severity badge (good / inaccuracy
     / mistake / blunder), and a 1–2 sentence **serif coach explanation** of what happened (lead with
     the idea, e.g. "Your queen walked into a fork"), optional better-move and consequence text. On a
     mistake/blunder the board **locks** until the user acknowledges ("I see it — let me play").
  2. After the **coach's move**: a distinct card ("Coach played Nf3") in the serif coach voice
     explaining *why*, with an optional Socratic hint ("Can you see the threat?") and optional trap
     alert.
  - **Important new behavior:** also show a short, warm reinforcement on **good moves** ("Nice — that
    keeps your king safe"), so the coach feels present, not only when scolding.
- **Pre-move guardian:** an optional "Are you sure?" prompt before a clearly risky move, with the
  safer alternatives.
- **Session goal card:** "Today's focus: keep your pieces safe." Shown at session start and in the
  panel. **Warmth gradient:** for a brand-new player it's band-generic; after ~5 games it becomes
  genuinely personal ("you tend to drop pieces in the middlegame"). Don't promise "personal" on game 1.
- **Early Profile card (panel):** a short "your coach sees you" snapshot — playing identity/style,
  your main leak, your weakest phase, and a confidence label that grows as more games are analyzed.
  Confidence-scaled (don't over-claim early).
- **★ Rate Your Move (engagement mechanic):** on instructive moves, *before* the coach's verdict,
  the panel asks the user to self-grade their move with **3 tap buttons (Good / Inaccuracy /
  Mistake)**. Then a **reveal** shows the real answer + why, with a "Got it →" button. Guess-then-
  reveal flow in the same coaching slot. Always skippable.
- **★ Predict Coach's Move (engagement mechanic):** on the coach's turn, *before* the move plays,
  show **2–3 candidate moves as tappable buttons (also as board arrows)**. The user taps a guess →
  reveal: "I played Nc6 — ✓ nice, you saw it" / "✗ you guessed Bc5, I went Nc6 because…". Non-
  blocking, skippable, frequency scales with rating.
- **Real-time opening guidance (opening phase, moves ~1–12):** per-move nudge of one of three types
  — **on book** ("Nf3 — prepares castling; in the Italian, develop the kingside first"), **fine
  alternative** ("Nf6 is also okay; the main line is Nf3"), or **deviation** ("that steps outside the
  Italian — the book move is Nf3; fine if you have a reason"). Capped per game; silences once out of
  book.
- **Habit reminder (optional, low-friction):** at decision moments a gentle pre-move prompt — "Before
  you move: is anything hanging? what is your opponent threatening?" — reinforcing a universal good
  habit. Skippable, not a modal.
- **Game setup sub-screen:** choose color, difficulty/time, and (optional) a focus/opening.
- **Coach chat:** a small "Ask the coach" input to ask about the position.
- **Post-game Story (not a report):** at game end, a focused recap card — accuracy, top 2–3 habits
  this game vs recent games, and **one lesson tied to today's goal** in the coach's voice ("that one
  move is the whole lesson — tomorrow, same rule, one more game"), with CTAs ("Drill your hanging-
  piece mistakes", "Review this game").
- Lesson modes (traps & endgames) launchable from a "Learn" picker in the panel.
- **Note on coaching cadence (drives how busy the panel feels):** the coach is **quiet by default**
  and speaks more for lower-rated players, less for higher. For concepts the player has **mastered**,
  the coach stays silent; for ones they're **slipping** on, it gives a brief reminder; for ones
  they're **still learning**, it gives full guidance. Design the panel so silence feels intentional
  and calm, not empty.

### 4.4 Game Review / Lab (the closed loop made visible)
Open an imported or played game and walk through it move-by-move. **Board + move list + coaching
card.** This is where "your mistakes become your training" must be *visible*.

- **Board** with eval graph and a scrollable **move list** (mistakes/blunders flagged with severity
  colors).
- **Per-move coaching card:** for taught moves, the move, severity, a concrete plain-English **"why"**
  (what went wrong + what the idea was), and the better move when relevant. Routine moves can be
  quiet — don't fabricate. Lead with the pattern, not the notation.
- **★ "Drill this" bridge (key):** on every flagged blunder, a prominent button: *"You missed this
  fork — drill it now →"* that launches the exact position as a personalized puzzle. This makes the
  closed loop tangible.
- **Lab home / game history list:** a "Coach's Pick" highlighted card (the best unreviewed game to
  study right now), then the full game list with opening, result, date, review status, and the
  detected weakness tags per game. Filters: reviewed/unreviewed, result, pattern.

### 4.5 Train (drills, daily mission, pattern training)
The daily-habit home for practice.

- **Daily Mission** front and center (mirrors the Home hero): a timed, personalized set of drills,
  with a completion/streak reward.
- **Pattern training:** pick a weakness (e.g. piece safety, missed tactics, king safety) and drill
  puzzles drawn **from the user's own mistakes first**, then community/curated. Each puzzle shows a
  board, prompts the user for the move, then gives plain-English coaching feedback (what your move
  let happen, the better idea, the takeaway).
- **Spaced repetition:** missed puzzles resurface a few days later ("You missed this 3 days ago —
  try again").
- **Progress per pattern:** a small mastery indicator per weakness ("fork recognition: getting
  there").
- Handle the **thin-pool empty state** gracefully ("Play or import a few more games to unlock drills
  tailored to you").

### 4.6 Progress / Profile
Make the player *feel* themselves improving — the #1 reason people pay for coaching. This screen
holds several stacked sections (no separate routes):

- **Improvement over time:** charts of accuracy, blunders/game, rating trend (numbers count up,
  sparklines draw in).
- **Fundamentals scores** (Opening / Tactics / Endgame / King Safety / Piece Safety) with benchmarks.
- **"Currently working on" card (UnifiedProgress v2):** the top weakness bucket with a trend
  ("Tactical patterns — down 14% over 90 days"), a **plain-language concept line** ("you get forked
  when your knight jumps to the rim" — NOT move notation), a **most-recent example** (opponent name +
  date + outcome, not SAN), a collapsible "earlier examples (N)" list, and two buttons: **"Review the
  game"** and **"Drill this pattern."**
- **"Also tracking" section:** secondary weaknesses, each with a one-line concept summary, a recent
  count, and a Drill button.
- **★ Concept Mastery Panel (key — a 4-state progression):** shows the concepts the coach tracks,
  grouped by mastery state, each row a human-readable name (never raw IDs) with an icon + color:
  - **Mastered** (emerald ✓): "Demonstrated in N games · last shown [date]". The coach goes quiet on
    these in live play.
  - **Slipping** (amber !): "was mastered, slipped N games ago". The coach gives a quick reminder.
  - **Still learning** (violet ○): "N times · still building the streak". The coach gives full
    guidance.
  - **Unseen:** not shown.
  - Show top ~5 per tier with a "+ N more" expander. Section summary line: "X studied · Y
    demonstrated · Z to explore." Hide the whole panel gracefully if there's no data yet.
- **"Archived · you've been consistent at":** patterns that *were* a problem but are now clean for N
  games — visibly "faded/resolved." Celebrate these; it's proof of improvement.
- **"You've learned" timeline:** openings/traps/endgames/concepts the coach has graduated the player
  on ("Mastered: Italian Game, Fried Liver. Working on: endgames").
- **Streaks & stats**, account/links, theme toggle, settings.

### 4.7 Openings
- Opening repertoire overview, individual opening lessons with a board walkthrough, and short
  quizzes. Plain-language explanations of *ideas*, not theory dumps.

### 4.8 Settings
- Account, linked Chess.com/Lichess, theme (light/dark), notifications, **subscription/plan**
  (Free vs. Pro upgrade — design a clean upgrade screen and a "you're on Free, here's what Pro
  unlocks" comparison).

---

## 5. Reusable components to design

- **CoachCard** — the serif-voiced coaching message card (variants: user-move, coach-move,
  reinforcement, trap alert). Used in Play and Review.
- **SeverityBadge** — good / inaccuracy / mistake / blunder, with consistent soft colors.
- **BoardPanel** — responsive chessboard wrapper with arrows, highlights, coordinates.
- **MoveList** — scrollable, severity-colored, current-move highlight.
- **MissionCard** — daily mission with progress ring + start CTA.
- **StreakChip** — 🔥 streak counter.
- **FundamentalsChart** — radar or bars with benchmark line.
- **TrendChip / TrendChart** — improvement proof.
- **GamePreviewCard** — board thumbnail + opening + result + recap + CTA.
- **DrillCard** — puzzle prompt + feedback states.
- **RateMoveControl** — 3-button self-grade (Good/Inaccuracy/Mistake) + reveal state.
- **PredictMoveControl** — 2–3 candidate-move buttons (synced with board arrows) + reveal state.
- **MasteryRow / MasteryPanel** — concept name + state icon (mastered/slipping/learning) + count,
  grouped tiers with "+ N more" expander.
- **EarlyProfileCard** — playing identity / main leak / weak phase / confidence label.
- **WeaknessCard** — "currently working on" with concept line, recent example, Review + Drill buttons.
- **EmptyState** — friendly, encouraging, with a clear next action (used everywhere data is thin).
- **UpgradeCard** — Free vs Pro comparison + checkout CTA.

---

## 6. Responsiveness requirements (must-have)

Design and deliver **all three breakpoints** for every screen:

- **Mobile (≤767px):** single column, bottom tab bar, board-on-top + coaching as a stacked
  card/bottom sheet, large tap targets (≥44px), no horizontal scroll, sticky primary CTA where it
  helps. The chessboard scales to viewport width with sensible min size.
- **Tablet (768–1023px):** comfortable two-column where it fits, otherwise graceful stacking;
  collapsible nav.
- **Desktop (≥1024px):** persistent sidebar, two-column board+coaching layouts, max content width
  ~1200px, generous whitespace.

Test that long coach text, long opening names, and small-screen boards all behave. Cards should
reflow, never clip.

---

## 7. States & accessibility (don't skip these)

- Every data-driven section needs **loading**, **empty**, and **error** states. Empty states must be
  encouraging and point to a next action — never a dead end.
- The coach "thinking" state (between a move and feedback) needs a tasteful shimmer/typing
  indicator.
- Accessibility: sufficient color contrast in both themes, text alternatives for board states and
  arrow-only hints (don't rely on color/arrows alone), keyboard navigability, reduced-motion
  support.

---

## 8. What NOT to do

- Don't make it look like a cold engine analysis tool (no big numeric eval bars as the hero).
- Don't gamify it into a noisy casino — streaks and wins should feel earned and calm.
- Don't use chess jargon in UI copy; write for a 600–1500 player.
- Don't lead coaching text with move notation; lead with the idea/pattern.
- Don't let the board get tiny on mobile.
- Don't punish mistakes harshly — they're coachable moments.

---

## 9. Deliverable

A fresh, cohesive, responsive UI design system + all screens above, in React + Tailwind + shadcn/ui,
light & dark mode, mobile/tablet/desktop. Prioritize the **Home dashboard**, **Play with Coach**, and
**Game Review** screens — those carry the product.
