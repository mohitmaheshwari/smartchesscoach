# ChessGuru Inner Product Experience Redesign — Scope

## 0. Existing surfaces audit

ChessGuru does not need a second interface layered on top of the current one. The working product already has the right customer journey and most of the right capabilities; the problem is that those capabilities are presented through several competing visual and writing systems.

The existing shared application shell is `frontend/src/components/Layout.jsx`. It provides the desktop sidebar, mobile navigation, account controls, dark mode, notifications, and the main customer routes: Home, Learn, Game Review, Progress, and Play with Coach. It is the correct place to establish one coherent inner-product frame.

The existing customer surfaces already provide:

- `HomePageNew.jsx`: a coach greeting, current focus, recommended action, recent-game context, and routes into practice.
- `PersonalCurriculum.jsx` and `Dashboard.jsx`: the current lesson, the next lesson, curriculum exploration, game-review recommendations, and the player’s broader learning library.
- `PrescribedTraining.jsx`, `SkillDrill.jsx`, `MotifDrill.jsx`, opening lessons, and endgame lessons: interactive teaching and practice workspaces.
- `AllGames.jsx`, `ReviewQueue.jsx`, `LabV2.jsx`, and `Reflect.jsx`: game selection, board review, coaching explanations, and reflection.
- `UnifiedProgress.jsx`: active focus, remembered weaknesses, improvement evidence, and next recommendations.
- `CoachPlay.jsx`: the live coached-game experience, including the board, pre-move guidance, opening teaching, feedback, and post-game transition.
- `Onboarding.jsx`, `DiagnosticPuzzles.jsx`, and `ImportGames.jsx`: account setup, initial evaluation, and game connection.
- `Settings.jsx`: personal preferences and account controls.

The overlap is substantial. Home, Learn, Game Review, and Progress all explain what the player should work on, but use different hierarchies and sometimes repeat the same recommendation. Several pages already use the newer `experience-v1` styles, while others retain older violet, gold, plain-white, or report-like layouts. The landing page now introduces a warm emerald, cream, lime, and coral product with restrained motion and conversational coaching, but that promise stops at login.

The genuine redesign opportunity is not new functionality. It is one continuous experience in which every page feels like another part of the same coaching relationship. The player should always understand what the coach noticed, why it matters, what to do now, and what the coach will watch for afterward.

**Decision: REPLACE the customer-facing visual and conversational system while preserving the existing product behavior.** The shared shell and each canonical customer page will be redesigned. Existing APIs, chess logic, stored evidence, working actions, route contracts, and test identifiers will be retained unless a separate approved scope explicitly changes them. Dead pages, route aliases, internal administration, and reviewer tools will not receive parallel redesigns.

## 1. What it is

The ChessGuru inner-product redesign turns the application into one calm, modern coaching room. The visual warmth, color, motion, and polish of the new landing page continue after sign-in, but the experience remains simple enough for a 600–1500 player to use without instruction. Every surface speaks like a coach who knows the player’s games. It avoids dashboards, unexplained measurements, and generic lesson-library language. The product guides the player through one connected loop: understand what matters, learn it, practise it, use it in a game, and return to see what changed.

## 2. What the user sees

### The shared app frame

The sidebar becomes quieter and more deliberate. Home, Learn, Game Review, Progress, and Play with Coach remain the primary destinations. The active destination uses the new emerald treatment; the strongest action uses lime or warm gold only when it genuinely deserves attention. Navigation never competes with the lesson or board.

On smaller screens, the same hierarchy becomes a compact bottom or top navigation with a clear way back. Motion helps the player understand transitions; it never delays a move or lesson.

### Welcome and diagnosis

```text
Let’s build a plan from your chess.

You don’t need to know what is holding you back.
That is my job. Show me where you play, and I’ll start looking.

[ Connect Chess.com ]   [ Connect Lichess ]

No games to connect? We can start with a short game together.
```

The setup feels like meeting a coach, not completing an account form. Questions appear one at a time and explain why the answer matters.

### Home

```text
Good evening, Mohit.

I’ve been looking at your games.
You are finding attacking ideas, but when one of your pieces is attacked,
you often answer before checking what that piece was protecting.

For now, we are working on one habit:
Before moving an attacked piece, look behind it.

[ Practise this with me ]

Afterward, play a game. I’ll watch for the same moment.
```

Home contains one primary coaching message and one primary action. Recent games, other lessons, and utilities remain available below, but they do not compete with today’s direction.

### Learn

```text
Your coaching plan

Here’s where we start
Slow down when a piece is attacked.

I chose this because the same decision has hurt you in different positions.
We’ll keep working on it until you begin catching it during your own games.

[ Continue with your coach ]

Coming naturally after this
The Opposition

Curious about something else?
Explore openings, traps, endgames, tactics, and positional ideas.
Your main lesson will still be here when you return.
```

The learning library remains rich, but it is presented as choices inside a coaching plan rather than a catalogue of unlocked and locked content. Nothing useful is hidden merely to simplify the page.

### Lesson and practice workspace

```text
Your coach

Before you move, tell me what you are checking.

[ The attacked piece ]
[ What it was protecting ]
[ The opponent’s next move ]

                    [ chessboard ]

Take your time. I’m more interested in your thought than your speed.
```

The chessboard is the main object. The coach introduces one idea, asks one understandable question, and responds to the player’s choice. Help appears when requested and is remembered only for the current lesson. Progress through a lesson is described naturally: “One more position like this,” not as a completion percentage.

### Game Review

```text
Let’s look at the moment the game changed.

You saw the attack on your knight.
What you missed was that the knight was also protecting e4.

What were you thinking here?

[ I only looked for a safe square ]
[ I saw e4 but thought it was safe ]
[ I’m not sure ]

                    [ chessboard ]

[ Show me what happens ]
```

Engine truth remains underneath the experience, but the default page does not read like an engine report. The coach uses the board, plain language, and the player’s own thought process. Move quality, alternatives, and consequences are shown only when they help the player understand the position.

### Progress

```text
You’re starting to catch this.

When we began, attacked pieces made you rush.
Now you are stopping to check what changes after they move.

I saw the old habit return in your last game, so we are not leaving it yet.
Play again with the same rule in mind. If it holds, we’ll move on.

[ Play with this focus ]

What you have already changed
- You check loose pieces before attacking.
- You are calmer after a difficult loss.
- You finish simple king-and-pawn endings with a plan.
```

Progress is a remembered coaching conversation, not a ledger. The system may calculate rates, confidence, and recurrence internally, but the customer sees a truthful explanation of what is improving, what is not yet stable, and what comes next.

### Play with Coach

```text
Today I’m watching one thing:
When a piece is attacked, check what it was protecting before you move it.

                    [ chessboard ]

Your coach
Take your time. Tell me when you are ready.
```

The board remains dominant. Coaching appears at the moment it is useful, then gets out of the way. Setup, live play, lesson interruptions, and the post-game handoff all use the same voice and visual system.

### Import and settings

Utility pages become short, friendly, and task-led. Import says what connecting an account lets the coach learn. Settings groups choices by their effect on the coaching relationship. Neither page becomes a marketing surface or a dense control panel.

## 3. In scope (V1)

- Replace the customer-facing application shell with the landing page’s warm, modern visual language.
- Establish shared inner-product tokens for color, typography, spacing, surfaces, shadows, focus states, and restrained motion.
- Redesign the canonical customer journey: welcome, onboarding, diagnosis, Home, Learn, training, openings, traps, endgames, Game Review, game analysis, reflection, Progress, Play with Coach, import, and settings.
- Make every canonical page responsive for desktop, tablet, and mobile.
- Preserve dark mode with an intentionally designed dark palette rather than automatic color inversion.
- Give every page one obvious primary action and a clear route back.
- Rewrite visible headings, labels, empty states, loading states, error states, and coaching transitions in plain conversational language for 600–1500 players.
- Remove default customer-facing decimals, centipawn values, rates, percentages, clinical scores, and report terminology.
- Keep engine evidence and internal measurements available to product logic without making them the customer’s language.
- Keep all valuable curriculum visible and explorable; simplification must not mean deleting or hiding content.
- Preserve existing routes, API calls, chessboard behavior, lesson correctness, authentication, analytics events, security controls, and working test contracts.
- Consolidate repeated visual patterns into shared primitives instead of styling every page independently.
- Add or update focused frontend tests for navigation, primary actions, responsive states, conversational copy rules, and critical lesson/review flows.
- Validate each redesigned page visually on desktop and mobile before the redesign is considered complete.

## 4. Explicitly out of scope (V1)

- New detector logic, Stockfish analysis, puzzle admission rules, curriculum data, or coaching-plan selection logic.
- Changing what the coach recommends; this scope changes how an existing recommendation is explained and used.
- Admin dashboards, caption authoring, reviewer queues, and other internal operating tools.
- Legal pages and the public pricing page, except for shared brand corrections required to prevent a visibly broken transition.
- Redesigning dead components or legacy routes that are not reached by the canonical customer journey.
- Removing route aliases before usage has been checked.
- Adding public social features, leaderboards, achievements, or gamification.
- Turning ChessGuru into a data-heavy performance dashboard.
- Inventing a large permanent coach persona, avatar system, or character story before users validate that it helps.
- Hiding advanced chess knowledge from the curriculum merely to make the interface appear simpler.

## 5. Success criteria

- On every core page, a player can quickly answer: “What does my coach want me to do now, and why is it for me?”
- A player can travel from Home to the assigned lesson, complete the practice, and return to the next recommended action without guessing where to click or using browser backtracking as navigation.
- More players who open an assigned lesson begin it, and more players who begin a lesson reach its natural ending, compared with the current experience baseline.
- More players return from practice to a real game with the prescribed focus still visible.
- In moderated customer testing, players describe the experience as a coach guiding them rather than software reporting on them.
- The redesigned customer surfaces contain no unexplained decimal scores, centipawn values, statistical rates, or report-style language in their default states.
- The design remains usable with reduced motion, keyboard navigation, common mobile widths, and both themes.
- Existing critical customer flows and their security checks remain green after the redesign.

The exact behavioral uplift thresholds will be locked from the existing analytics baseline before release rather than invented in this document.

## 6. Open questions

- **Question:** Should the coach have a visible permanent name, or should the product say “your coach”?
  **Why unresolved:** The current app sometimes uses “Coach Maya,” but the new landing page sells personalization rather than a character.
  **Unblocking step:** Mohit chooses the preferred relationship before shared coach headers are implemented.

- **Question:** Should advanced engine details remain available behind an optional “Show the analysis” control in Game Review?
  **Why unresolved:** The default experience should never feel like a report, but some stronger players may deliberately want the underlying line.
  **Unblocking step:** Review current usage and decide whether the control belongs in V1 or stays internal.

- **Question:** Which lesson and review completion events provide a trustworthy current baseline?
  **Why unresolved:** Success thresholds should come from real behavior, not an arbitrary number.
  **Unblocking step:** Audit the existing analytics events and lock measurable thresholds before release.

- **Question:** Should mobile navigation use a bottom bar or retain the compact top menu?
  **Why unresolved:** Both can support the route set; the decision should be made from the page hierarchy and small-screen prototype.
  **Unblocking step:** Compare the two shells using the Home → Learn → Play flow before implementation spreads across pages.

## 7. Pre-code requirements

- Mohit explicitly signs off on this full scope document.
- The permanent coach-name decision is made, or “your coach” is approved as the V1 default.
- The canonical route inventory is frozen so legacy pages are not accidentally redesigned alongside customer pages.
- Current desktop and mobile screenshots are captured for every canonical surface.
- Every canonical surface is mapped to its shared shell, page header, coach-message, action, card, board-stage, empty-state, and transition primitives.
- Existing analytics are audited and the measurement plan is written before visual changes make the old baseline impossible to reproduce.
- Critical page tests are identified before markup changes, including authentication, game review, lessons, Play with Coach, and mobile navigation.
- Numeric release thresholds are locked through the data-driven decision process.
- The pre-code audit is run and passed before the first inner-page implementation file is changed.
- The working tree’s existing landing-page and Phase 4 changes remain isolated and preserved throughout the redesign.
