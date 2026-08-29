# ChessGuru Full Frontend Experience — Scope Document

**Status:** SIGNED OFF by Mohit on 2026-08-27 — “go, do it”
**Date:** 2026-08-27
**Product promise:** ChessGuru should look premium, feel easy, guide the player without making them plan their own training, and create personal moments worth sharing.

## 0. Existing surfaces audit

### The user need

The redesign is not a coat of paint on six screens. A player should experience one recognizable ChessGuru from the first landing page through activation, review, lessons, training, coached play, progress, payment and settings. The chessboard should be the visual hero wherever it appears. The coach should feel warm and personal. Every important screen should make the next action obvious, and the strongest personal insights should be beautiful enough to share.

### Verified frontend shape

- `frontend/src/App.js` declares 57 routes. Some are canonical product pages, some are aliases, some are specialist flows, and some are internal or legacy surfaces.
- The player journey is already implemented across Landing, Activation, Home, Lab, Game Review, multiple Training routes, Openings, Endgames, Missions, Play with Coach, Reflect, Recovery, Progress, Pricing and Settings.
- Three aliases already redirect to canonical destinations: `/dashboard → /home`, `/today → /home`, and `/journey → /progress`.
- Several route families still overlap: `/coach` and `/focus`; `/games`, `/lab` and several review routes; multiple Training URLs; `/openings` and `/openings-overview`; specialist Plateau Breaker and Recovery journeys.
- The frontend contains very large orchestrators—CoachPlay, Lab/Game Review, Reflect, Training and Admin—so a visual rewrite that also rewrites their business logic would be high risk.
- Boards are rendered through both `react-chessboard` and Chessground-based components. Board colors, framing, highlights, arrows, controls and responsive sizing are not governed by one visual contract.
- The shared theme defines wine/gold in light mode and amber/gold in dark mode. A prior premium pass added teal, emerald and rose. Newer core pages hardcode violet and several page-local slate, gray and purple treatments. The result is visible brand drift.
- Typography primitives already include Outfit for headings, Manrope for interface text, Fraunces for the coach's voice and JetBrains Mono for notation. Pages do not use those roles consistently.
- Framer Motion, reduced-motion support, shared motion constants, shimmer utilities and touch feedback already exist. They are unevenly applied.
- No real player-facing share/export journey exists. Current download/copy actions are mainly admin or debugging tools; “share my thinking” is reflective input, not social sharing.
- The current live browser audit cannot start because Codex's Windows sandbox helper fails with OS error 206. Static code evidence is valid; visual and interaction evidence remains pending.

### Existing route families and decisions

| Route family | What exists now | Decision |
|---|---|---|
| Public acquisition: `/`, `/login`, `/pricing` | A strongly animated dark Landing page, authentication, and amber-led pricing. They already communicate a premium direction but are not visually continuous with newer violet authenticated pages. | **EXTEND:** give Landing, Login and Pricing a dedicated acquisition pass using the same brand, board and type system as the product. |
| Public teaching and trust: `/learn/openings/*`, Terms, Privacy, Refund, Contact | SEO opening guides and required trust/legal pages. | **EXTEND LIGHTLY:** preserve content and SEO structure; apply the global shell, typography, spacing, forms and responsive quality. They do not receive coaching-product complexity. |
| Activation: `/welcome`, `/onboarding`, `/diagnostic`, `/import` | Several ways to connect games, prove value and gather initial evidence. The current routing can make the new player choose the activation method. | **CONSOLIDATE:** one guided activation sequence with contextual fallbacks. Existing capabilities and routes remain available, but only one action is dominant at a time. |
| Application shell: `Layout.jsx` | Desktop sidebar with Home, Learn, Progress and a gold Play CTA. Mobile hides the same destinations inside a menu. | **EXTEND:** one premium shell; persistent mobile destinations; plan continuity; utilities visually subordinate. |
| Direction: `/home`, with `/dashboard` and `/today` aliases | Home already behaves like a coach conversation with one next action. It also contains page-local violet and older card treatments. | **EXTEND:** preserve the signed coach-conversation mission; redesign the composition, states and Start/Resume handoff. Keep aliases redirected. |
| Evidence and history: `/lab`, `/games`, `/game/:id`, `/lab/game/:id`, `/replay/:id`, `/game-old/:id`, `/weaknesses` | Coach's Pick, game archives, multiple review presentations, behavioral replay, an old game page and a separate weakness tracker. | **CONSOLIDATE:** Lab owns game selection; canonical Game Review owns board-led explanation; specialist replay remains a mode or deep link; old and duplicate destinations are redirected or retired after reference checks. |
| Reviewer/admin review: `/review`, `/review/authoring` | Internal review queues, not the player's game-review journey. | **SEPARATE:** inherit tokens and accessibility, remain internal, and never determine player navigation vocabulary. |
| Training: `/training`, `/training/prescribed`, `/training/pattern/:pattern`, `/training/skill/:id`, `/training/motif/:motif`, `/daily-fix/drill`, `/training/quiz/:openingKey` | Prescribed puzzles, skill and motif drills, timed fixes and opening quizzes. Core training is already consolidated partly, but activity screens use separate board and feedback treatments. | **CONSOLIDATE AND EXTEND:** one Training home and one shared Activity Stage. Preserve deep links and specialist grading, while making every session finite and visually consistent. |
| Opening/endgame learning: `/openings`, `/openings/:key`, `/opening-walkthrough`, `/openings-overview`, `/endgames/:category/:lesson` | Repertoire, guided lessons, practice, traps, walkthroughs, quizzes and endgame lessons. Two overview concepts compete. | **CONSOLIDATE AND EXTEND:** one Learn catalog, exact lesson routes and direct prescribed entry. No second choice when ChessGuru already selected the lesson. |
| Transfer: `/play-with-coach`, `/mission/:id`, `/challenge` | The full coached-game system, behavioral missions and challenge play. PWC already contains the richest teaching loop but also the densest UI and multiple competing panels. | **EXTEND:** board-first layout, one active coaching panel, shared activity state and responsive bottom sheet; preserve teaching logic. |
| Reflection and recovery: `/reflect`, `/recover/:id`, `/plateau-breaker/*` | Reflection, post-loss recovery and an enforced-learning sequence overlap with review, training and Focus Games. | **CONSOLIDATE:** retain distinct emotional jobs, but express them as modes of the same improvement cycle rather than separate products. Route retirement requires an incoming-reference audit. |
| Proof: `/progress`, with `/journey` alias | Unified Progress already combines progress and journey. It contains several competing proof systems. | **CONSOLIDATE:** one canonical focus verdict leads; trends, mastery and history support it. Keep `/journey` redirected. |
| Personal email landings: `/coach/moments/:topic` | Topic-specific pages satisfy the email-to-page contract and can render a board. | **EXTEND:** preserve exact promise delivery and bring the layout, board and CTA into the shared system. |
| Account: `/settings` | Account, integrations, preferences and subscription controls. | **EXTEND:** calm, task-based sections; clear save feedback; premium upgrade treatment consistent with Pricing. |
| Admin: `/admin/*` | Large operational surfaces for openings, captions, drafts and authoring. | **INHERIT:** receive shared typography, tokens, controls, tables, loading and accessibility. No product-journey rewrite in V1. |
| Prototype and legacy: `/prototype/interactive-moment` plus old/duplicate routes | Design review and compatibility paths. | **DO NOT REDESIGN AS PRODUCTS:** keep prototypes explicitly marked; redirect or retire legacy paths only after reference and analytics checks. |
| Board implementations | `react-chessboard` and Chessground serve different working flows. | **UNIFY THE VISUAL CONTRACT, NOT THE ENGINE:** shared Board Stage roles and tokens with adapters for both renderers. |
| Existing design documents | Premium motion/palette, PWC responsive layout, Home coach conversation, Lovable brief and the Personal Improvement Cycle all contain valuable decisions, but some conflict. | **INHERIT DELIBERATELY:** PIC owns the journey; Home scope owns Home's emotional mission; prior amber/teal motion system supplies the foundation; this document supersedes conflicting dashboard-heavy, five-page-only and PWC-only limitations. |

### Overlap

Nearly every requested capability already exists somewhere: responsive primitives, themes, motion, boards, lessons, drills, missions, coach memory, analysis, progress and payment. Building a parallel “new frontend” or replacing working orchestrators would duplicate behavior and risk regressions. The problem is fragmentation—routes, visual styles, board treatments, hierarchy and action continuity disagree.

### Genuine differentiation still missing

- One art-directed ChessGuru identity across public, activation and authenticated pages.
- One Board Stage contract for every full board and board thumbnail.
- One guided Start/Resume action that selects the correct activity for every trustworthy surfaced focus.
- One activity language across puzzles, lessons, missions, quizzes and Focus Games.
- One responsive shell with persistent mobile navigation and board-first layouts.
- One family of complete loading, empty, partial, error, offline and success states.
- Real shareable personal moments with privacy-safe preview and export.
- A route plan that consolidates aliases and duplicate experiences instead of polishing all 57 declarations independently.
- Visual validation on real rendered pages, not code inspection alone.

### Section 0 decision

**Path: EXTEND existing + CONSOLIDATE overlaps.** All player-facing route families receive a deliberate design treatment. Legal, SEO and admin pages inherit the system at an appropriate depth. Prototypes and legacy aliases are not promoted into independent products. Existing data, coaching logic and board engines are reused.

## 1. What it is

The Full Frontend Experience redesign turns the existing ChessGuru product into one premium, guided and recognizable coaching environment. It keeps the working chess intelligence and routes, but gives them one art direction, one board language, one responsive shell and one improvement journey. The player sees what ChessGuru noticed, why it matters and one clear Start or Resume action. Lessons, drills, missions and coached games feel like parts of the same plan. Public pages communicate that experience honestly, and personal insights become tasteful, privacy-safe moments the player may choose to share.

## 2. What the user sees

### A. Visual direction — Warm Intelligence

ChessGuru feels like a modern coach's study: deep ink backgrounds, warm light surfaces, restrained amber highlights, calm teal progress, emerald success and soft rose mistakes. Amber is the recognizable brand accent; semantic colors explain meaning and never become decoration. Violet no longer acts as a competing primary brand color.

Outfit gives interface headings clarity. Manrope handles controls and supporting text. Fraunces is reserved for the coach's voice and important reflective lines. JetBrains Mono is limited to notation, clocks and compact chess data. Pages use breathing room and editorial hierarchy instead of stacking bordered cards.

Motion is purposeful: the board responds to play, the coach arrives when there is something to say, progress changes are legible, and controls acknowledge touch. The existing reduced-motion contract remains mandatory.

### B. Shared desktop shell

```text
┌───────────────┬────────────────────────────────────────────────────────────┐
│  ChessGuru    │  Current plan: Keep your pieces safe      [ Resume plan ] │
│               ├────────────────────────────────────────────────────────────┤
│  Home         │                                                            │
│  Learn        │  Page title                                                 │
│  Play         │  One sentence explaining this page's job                   │
│  Progress     │                                                            │
│               │  [one dominant content area]                               │
│  ───────────  │                                                            │
│  Import       │  [supporting details, visually quieter]                    │
│  Settings     │                                                            │
│               │                                                            │
│  Mohit        │                                                            │
└───────────────┴────────────────────────────────────────────────────────────┘
```

The plan strip appears only when it helps continuity and never competes with an in-progress board. The shell has one visual weight, one selected-state treatment and one utility area.

### C. Shared mobile shell

```text
┌───────────────────────────────┐
│ ChessGuru          Plan · 2/4 │
│                               │
│ Current page                  │
│ Board/content uses full width │
│                               │
├───────────────────────────────┤
│ Home    Learn    Play  Progress│
└───────────────────────────────┘
```

Primary destinations remain visible. Settings, account and notifications live in a compact utility menu. Board pages may replace the bottom navigation temporarily with move or activity controls, but provide an obvious exit.

### D. Landing, Login and Pricing

```text
Your games already know
what you should work on next.

ChessGuru studies your games, finds the habit costing you points,
and guides you through a plan built from your own positions.

[ Connect my games ]       See how it works

┌────────────────────┐  ┌─────────────────────────────────────┐
│ personal board     │  │ “This appeared in four recent games.│
│ moment             │  │  Here is the one habit to practise.”│
└────────────────────┘  └─────────────────────────────────────┘
```

Landing demonstrates the closed loop visually instead of listing many features. Login feels like the same product. Pricing sells continuous problem ownership and measured progress; checkout remains unchanged.

### E. Activation and importing

```text
Let your coach study how you play

Connect the account where your games already live.
We will use those games to find your first focus.

[ Connect Chess.com ]     [ Connect Lichess ]

No account to connect?
Play one coached game or try a short provisional diagnostic.
```

One recommended path dominates. Progress, analysis and failure states explain what is happening and what the player can do next. The player is not presented with a feature menu before receiving value.

### F. Home

```text
Good evening, Mohit.

I watched your recent games again.
When you find an attacking idea, you stop checking whether
your pieces are still safe.

This week, we are changing that habit.

Before you move, ask:
“What changed after their move?”

[ Start my plan ]

Last time
You understood the example from your game. Next is guided practice.
```

Home remains one coach conversation. Navigation tiles, metrics and secondary suggestions are quiet. After starting, the action becomes **Resume my plan** and continues at the correct unfinished activity.

### G. Lab and game history

```text
Learn from your games

COACH'S PICK
┌──────────────┐  vs KnightRider · Loss
│ mini board   │  The same piece-safety habit appeared again.
│              │  Move 24 is the clearest example.
└──────────────┘
                  [ Review this game ]

Your games
[ All ] [ Unreviewed ] [ Wins ] [ Losses ]        Search
──────────────────────────────────────────────────────────
vs Arjun       Loss       Piece safety              Review ›
vs Mia         Win        Clean game                Review ›
```

Lab owns game discovery and selection. Secondary intelligence is disclosed after Coach's Pick and the archive, not presented as competing hero cards.

### H. Canonical Game Review

```text
vs KnightRider · Move 24

┌─────────────────────────────┬──────────────────────────────────┐
│                             │  THIS IS THE MOMENT              │
│                             │                                  │
│         BOARD STAGE         │  Your bishop moved to g5, but    │
│                             │  the knight on e4 could take it. │
│                             │                                  │
│                             │  Better: e3 keeps it safe.       │
├─────────────────────────────┤                                  │
│  ‹ Previous    ▶    Next ›  │  REMEMBER                        │
└─────────────────────────────┤  “What changed after their move?”│
                              │                                  │
                              │  [ Start this plan ]             │
                              └──────────────────────────────────┘
```

The board and one teaching explanation dominate. Move list, engine detail, alternate review modes and feedback remain available but subordinate. On mobile: board, sticky move controls, explanation, action; details open in sheets.

### I. Universal guided activity

```text
Keeping your pieces safe
Guided practice · Position 2 of 5

“What changed after their move?”

┌──────────────────────────────┐
│         BOARD STAGE          │
└──────────────────────────────┘

This came from your game against Arjun.
Choose the safest continuation.

[ Show one hint ]
```

The Activity Stage adapts to the assigned work:

- board pattern → finite prescribed training;
- exact opening, trap or endgame → exact lesson;
- time-management issue → timed drill;
- thinking habit or concept → mission or focused coached game;
- insufficient evidence → review, import or coached play to gather evidence.

The player never chooses the content type after ChessGuru has already prescribed it. Every session has a beginning, visible progress, readable feedback and one completion/transfer action.

### J. Play with Coach

```text
Focus Game
Your job: “What changed after their move?”

┌─────────────────────────────┬───────────────────────────────┐
│                             │  COACH                        │
│         BOARD STAGE         │                               │
│                             │  I will stay quiet while the  │
│                             │  position is calm. I will     │
│                             │  step in when your focus      │
│                             │  matters.                     │
└─────────────────────────────┴───────────────────────────────┘
```

The board is the hero. Setup clearly distinguishes a normal game, Focus Game and lesson. Only one coaching module occupies the active panel. Mobile uses a board-first sheet. Silence is an intentional coach state, not an empty panel.

### K. Progress

```text
Your progress

CURRENT FOCUS
Keeping your pieces safe

We checked comparable decisions from your games.
The habit is improving, but it is not reliable yet.

[ Continue my plan ]

Also tracking                         You have made reliable
• Calculation depth                  • Back-rank awareness
• Time discipline                    • Basic development
```

One canonical verdict leads. Trends, mastery, history and calibration support the verdict without producing rival conclusions.

### L. Shareable personal moments

```text
┌────────────────────────────────────┐
│ ChessGuru                          │
│                                    │
│ I fixed a habit that appeared      │
│ across 7 of my games.              │
│                                    │
│ KEEPING MY PIECES SAFE             │
│ Working on it  →  Reliable         │
│                                    │
│ [small privacy-safe board moment]  │
│                         chessguru.ai│
└────────────────────────────────────┘

[ Share ]   [ Save image ]   Preview privacy details
```

Share cards are generated only from genuine personal milestones or insights. The player previews exactly what will be shared. Email, opponent identity, exact rating and private notes are excluded by default. Sharing is optional and never blocks progress.

Initial share-worthy moments are: first Chess DNA reveal, a concrete recurring-pattern insight, focus graduation, and a weekly improvement recap. Their rollout order remains an open question.

### M. Settings, legal, SEO and admin

Settings uses clear task groups, visible save confirmation and consistent subscription presentation. Legal and SEO pages use readable editorial layouts and the public header/footer. Admin and reviewer surfaces inherit tokens, controls, tables, forms, loading states and accessibility, but keep their operational information density.

### N. Required states

Every changed surface has designed loading, empty, partial-data, recoverable error, offline/retry, permission, locked/premium and success states. No blank card, unexplained spinner, broken board, raw detector key or disabled action may appear without an explanation and next step.

## 3. In scope (V1)

### Foundation and brand

- Replace the competing page-local visual directions with one approved source of truth for color roles, typography, spacing, page width, radius, borders, elevation, iconography, motion, focus states and responsive behavior.
- Inherit the prior amber/teal/emerald/rose semantic foundation and the existing motion/reduced-motion utilities. Render representative variants before locking exact light/dark surfaces and deciding how existing violet treatments migrate.
- Use Outfit for headings, Manrope for interface text, Fraunces for coach voice and JetBrains Mono for notation/clock data, with documented exceptions.
- Create shared page, section, card, control, feedback, skeleton, empty-state, error-state and completion primitives using the existing Tailwind, shadcn and Framer Motion stack.
- Keep both light and dark themes first-class and verify every component in both.
- Place the redesign behind one default-off frontend experience flag with a documented flag-off path and cohort boundary.

### Navigation and routes

- Redesign the desktop sidebar, tablet shell and persistent mobile navigation as one system.
- Carry the canonical current plan and Start/Resume state through the shell only where it helps the current task.
- Produce a route disposition table for every one of the 57 declarations: canonical, deep link, alias/redirect, internal, prototype, or retire-candidate.
- Preserve working deep links while consolidating duplicate page identities. A route may redirect to a canonical screen without losing its intended context.
- Give Landing, Login, Pricing, activation, Home, Lab, Game Review, all player-facing training/lesson routes, Play with Coach, Reflect/Recovery, Progress, Personal Moments and Settings a dedicated layout and state pass.
- Apply the shared visual system and responsive/accessibility baseline to SEO, legal, reviewer and admin routes without changing their core operational purpose.

### Board Stage

- Define one Board Stage visual contract used by both `react-chessboard` and Chessground adapters.
- Standardize square palette roles, piece presentation, board framing, coordinates, orientation, last move, selected square, legal move, check, played mistake, suggested move, arrows, disabled/locked state and board loading.
- Define three board modes: interactive full board, review/teaching board and non-interactive thumbnail.
- Keep move legality, engine integration and board-provider-specific behavior unchanged.
- Protect board size and touch usability at phone, tablet, laptop and wide desktop layouts.
- Ensure board meaning is never communicated by color or arrows alone.

### Guided improvement experience

- Reuse the Personal Improvement Cycle and canonical active focus as the journey; add no rival plan owner.
- Build one shared diagnosis-to-action presentation contract that maps every trustworthy surfaced focus to its best supported existing activity and next unfinished step.
- Make Start/Resume consistent across Home, Review, Training, exact lessons, Missions, Play with Coach and Progress.
- Prevent an exact recommendation from landing on a generic dashboard, catalog, setup screen or content picker.
- Make every assigned activity finite, with progress, feedback, completion and one transfer action.
- Preserve an honest insufficient-evidence path instead of inventing precision from a broad or low-confidence label.

### Page-family redesign

- Landing: demonstrate the personalized closed loop and route the main action into activation.
- Login: visually continuous, clear authentication states and post-login destination.
- Pricing: sell continuous coaching ownership, preserve Razorpay behavior and show entitlements clearly.
- Activation/import: one recommended evidence path, understandable analysis progress, graceful fallbacks and an immediate payoff.
- Home: preserve one coach conversation, one instruction and one dominant Start/Resume action.
- Lab: Coach's Pick first, scannable archive second, secondary intelligence disclosed or relocated.
- Game Review: board + current moment + concrete why + remembered instruction + exact action as one synchronized unit.
- Training, quizzes and lessons: one Activity Stage language with mode-specific grading and content preserved.
- Play with Coach: responsive board-first layout, one active coaching panel, clear game mode and complete postgame handoff.
- Reflect, Recovery and Plateau Breaker: retain their emotional intent while visually and navigationally reconnecting them to the canonical cycle.
- Progress: one focus verdict first; supporting evidence, mastery and history second.
- Personal Moments: exact email promise, board evidence and one matching action.
- Settings: task-based sections, integrations, notification controls, theme and subscription.

### Viral pull and sharing

- Design reusable privacy-safe share cards for Chess DNA, recurring-pattern insight, focus graduation and weekly recap.
- Add explicit preview, Share and Save Image actions using supported browser capabilities with a copy-link fallback.
- Exclude private identity and coaching data by default; let the player cancel before any external share action.
- Keep share prompts contextual and secondary. No modal interrupts a lesson or coached game to demand sharing.
- Add impression, preview, share-attempt, share-success/cancel and inbound-link attribution events using existing analytics infrastructure.

### Quality, rollout and evidence

- Design loading, empty, partial, offline/retry, error, locked/premium and success states for every changed page family.
- Meet WCAG AA contrast, logical keyboard order, accessible names, visible focus, reduced motion and touch-target requirements.
- Verify representative long copy, long names, dense move lists and maximum notification states.
- Capture a dark/light screenshot matrix at the locked phone, tablet, laptop and wide-desktop viewports.
- Add visual regression coverage for shared primitives and critical page states.
- Add interaction coverage for route continuity, Start/Resume, board states, activity completion, mobile sheets, sharing preview and flag-off behavior.
- Implement in reversible slices: foundation → shell → public/activation → Home/Lab/Review → Activity Stage → Play with Coach → Progress/Settings → sharing → secondary/internal inheritance.
- Roll out default-off, then internal A/B, limited cohort, full rollout and legacy cleanup only after the signed technical spec defines the gates.

## 4. Explicitly out of scope (V1)

- New chess detectors, caption predicates, Stockfish behavior, move classification, rating bands, mastery formulas or progress claims.
- A second active-focus collection, plan engine, learner model, instruction bank, training service or analytics store.
- Replacing `react-chessboard` or Chessground merely to obtain a new visual style.
- Rewriting large page orchestrators and their business logic as part of the styling pass unless the technical spec proves an isolated extraction is required.
- New opening, endgame, puzzle or lesson content.
- A social feed, follower system, public player profiles, comments, leaderboards or a contribution economy.
- Automatic sharing, preselected public visibility or exposing private opponent/player data without explicit preview.
- Casino-style gamification, excessive confetti, intrusive streak pressure, decorative 3D boards, cinematic delays or sound as a required interaction.
- A native mobile application.
- Rewriting legal policy content, SEO teaching content or admin workflows. Those surfaces receive the shared presentation baseline only.
- Promoting prototypes or legacy pages into the main journey.
- Deleting or redirecting a route before its incoming references, analytics and external deep links are checked.
- A broad logo or product-name rebrand.
- Introducing another component framework, icon library or page-specific design-token file.
- Shipping the full redesign as one unflagged release.
- Calling the redesign successful solely because it looks modern or receives stakeholder approval. It must also make the product easier to understand and use.

## 5. Success criteria

V1 succeeds only if ChessGuru becomes more coherent, easier to act on and more desirable to return to—not merely more decorated.

1. **Complete route accountability:** all 57 route declarations are classified. Every player-facing canonical route has an approved treatment; every alias, internal, prototype and retire-candidate route behaves according to the signed disposition table.
2. **One recognizable product:** a blind screenshot review can identify Landing, Home, Game Review, Training, Play with Coach and Progress as the same product in both themes without relying on the logo.
3. **Board consistency:** the same semantic board states look and mean the same thing across both board renderers. Provider differences are not visible as brand or interaction drift.
4. **Guided action:** when a trustworthy focus and matching activity exist, one activation starts or resumes the correct next step. Generic catalog landings or an extra content-type decision are release-blocking.
5. **Instruction continuity:** Review, Home, the assigned activity, Play with Coach and Progress display the same available instruction and focus identity. Any contradiction is release-blocking.
6. **Task comprehension:** representative 600–1500 players can state what the current screen wants them to do, why it matters and what happens next. The pass bar and sample are locked before implementation.
7. **Core journey completion:** an eligible player can activate, review evidence, begin the prescribed activity, finish it, transfer it into play and understand the outcome without a dead end.
8. **Mobile viability:** activation, board review, training, lessons, coached play, progress, checkout and settings work at the locked phone viewport with no horizontal page scrolling, clipped controls, hover dependency or unusably small board.
9. **Accessibility:** changed player-facing surfaces meet WCAG AA contrast, expose accessible names and non-color board meaning, preserve logical keyboard order, show visible focus and respect reduced motion.
10. **Performance:** the redesign stays inside pre-registered load, interaction and animation tolerances. Motion never blocks input or a network action.
11. **Share usefulness:** eligible personal moments reach preview and successful share/save at the pre-registered rate without increasing abandonment of the learning task. “No eligible moment” is valid and never padded.
12. **Functional compatibility:** the default-off experience remains unchanged; authentication, import, review, training, lessons, Play with Coach, progress, payment, email deep links and settings retain their existing data meaning.
13. **Honest fallback:** missing, partial or low-confidence data never creates invented coaching copy, fake progress, a broken share card, a blank panel or an unexplained disabled action.
14. **Perception shift:** in the final qualitative review, target players describe the experience as premium, calm, personal and easy to follow. This complements behavioral evidence; it does not replace it.

## 6. Open questions

1. **Question:** When can the live browser audit and screenshot capture run?
   **Why unresolved:** Codex's Windows sandbox helper exits with OS error 206 before the browser-control runtime starts.
   **Unblocking step:** repair/restart the Codex sandbox setup path, then capture every canonical page family in dark/light and representative data states.

2. **Question:** Which rendered surface treatment becomes final within the inherited amber/teal identity, and how is violet retired or reassigned?
   **Why unresolved:** existing documents lock amber/teal while current Home, Lab and Training use violet prominently. Code inspection cannot decide depth, warmth and contrast.
   **Unblocking step:** render the same Home, Game Review and Activity Stage in two coherent variants using the inherited semantic roles; select one after visual and accessibility comparison.

3. **Question:** Which duplicate and specialist routes redirect, become modes, or remain independent deep links?
   **Why unresolved:** route declarations prove overlap but not current incoming-link and production usage.
   **Unblocking step:** build the full route/reference table, query route analytics where available and exercise each deep link before signing retirements.

4. **Question:** Which shareable moment launches first?
   **Why unresolved:** Chess DNA, recurring-pattern insight, focus graduation and weekly recap have different frequency, emotional value and privacy risk.
   **Unblocking step:** measure eligible-event counts, prototype each card with real-shaped data and choose the first surface through the data-lock process.

5. **Question:** What exact privacy defaults and attribution appear on share cards?
   **Why unresolved:** opponent name, rating, game date and board position can make a story credible but may expose more than the player expects.
   **Unblocking step:** author a field-by-field privacy table and approve the preview/cancel flow before implementing export.

6. **Question:** Do the inherited motion timings and board effects still feel premium across long games and low-end phones?
   **Why unresolved:** prior values are implemented foundations, but the full all-page rollout has not been performance-tested.
   **Unblocking step:** capture baselines and run representative repeated interactions with reduced motion on/off before retaining or adjusting any timing.

7. **Question:** Does the redesign share the Personal Improvement Cycle cohort flag or use its own frontend flag?
   **Why unresolved:** coupling affects attribution, rollback and combinations of old/new UI with old/new focus behavior.
   **Unblocking step:** audit the live PIC flags and analytics cohorts, then name one experiment boundary in the technical spec.

8. **Question:** Which current analytics events and denominators can support rollout and viral-pull decisions?
   **Why unresolved:** events exist across pages, but production coverage and database access were not available during this scope pass.
   **Unblocking step:** create an event/denominator table and query the configured analytics/Mongo environment before setting any pass bar.

9. **Question:** Which exact phone, tablet, laptop and wide-desktop viewports form the release matrix?
   **Why unresolved:** arbitrary widths can miss the real audience.
   **Unblocking step:** use production viewport distribution if trustworthy; otherwise lock a conservative standards-based matrix through the data-lock process.

10. **Question:** Where should the canonical Learn catalog end and prescribed activity routes begin?
    **Why unresolved:** Openings, endgames, training, skills, motifs and quizzes currently have separate entry concepts.
    **Unblocking step:** test the proposed Learn information architecture against voluntary exploration and exact prescribed-entry tasks before consolidating navigation.

## 7. Pre-code requirements

- [x] Static Section 0 audit completed across all route families, visual foundations, board renderers and existing design scopes.
- [x] EXTEND + CONSOLIDATE direction approved by Mohit in principle.
- [x] Literal mockups exist for the shell, public promise, activation, Home, Lab, Game Review, guided activity, Play with Coach, Progress and sharing.
- [x] Mohit explicitly signed off on this complete full-frontend scope document on 2026-08-27.
- [ ] The live browser audit succeeds and captures the current rendered baseline, or Mohit explicitly signs off on a static-only limitation after seeing its impact.
- [ ] Every canonical player-facing page family is captured in dark/light at the locked screenshot viewports and relevant loading/empty/error/success states.
- [ ] A complete 57-route disposition and incoming-reference table is approved before redirects or retirements.
- [ ] The Home, Game Review and Activity Stage visual variants are rendered; one canonical direction is selected and its exact tokens supersede conflicting guidance.
- [ ] The Board Stage state matrix is rendered through both `react-chessboard` and Chessground and approved for interaction, accessibility and mobile sizing.
- [ ] Start/Resume continuity is specified against the canonical active focus plus existing lesson, training, mission, Daily Fix, Play with Coach and progress state.
- [ ] Every surfaced focus type is mapped to a destination with verified content supply and completion state; a route existing by itself does not count.
- [ ] Share-card eligibility, field privacy, preview/cancel behavior and first launch moment are approved.
- [ ] Current route, funnel, task-completion, performance and share-eligibility baselines are queried; missing instrumentation is named.
- [ ] Numeric usability, performance, animation, viewport and rollout choices are locked through `/lock-via-data`; unavailable data reports “unknown.”
- [ ] The frontend/PIC flag boundary, default-off behavior, cohort plan and rollback path are named.
- [ ] `docs/frontend_experience_ui_ux_spec.md` is written from this signed scope with exact files, components, flags, tests and rollout phases, then signed off.
- [ ] Existing user changes in the dirty worktree are mapped before implementation; overlapping files are preserved or explicitly coordinated.
- [ ] The relevant frontend build, unit, integration, E2E, visual regression, accessibility and backend compatibility test commands are named.
- [ ] `/audit-pre-code` passes immediately before the first application file is edited.
