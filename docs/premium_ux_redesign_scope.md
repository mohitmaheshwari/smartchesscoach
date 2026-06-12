# Premium UX Redesign — Scope Document (V1)

**Status:** AWAITING SIGNOFF
**Author:** Claude (scope-driven-development)
**Date:** 2026-06-12
**Pages:** Landing.jsx, HomePage.jsx, Dashboard.jsx (Lab), UnifiedProgress.jsx, CoachPlay.jsx

---

## 0. Existing surfaces audit

**Path: EXTEND** — we are enhancing the existing visual system, not replacing it.

What's already there (verified in the codebase, 2026-06-12):

| Surface | Already has | Gap |
|---|---|---|
| Global theme | Dark base `#06060B`, amber/gold accents, glassmorphism (`backdrop-blur` across 39 page files, 403 hits), Fraunces display font in `tailwind.config.js` | Palette is one-note (amber only); no defined semantic colors for success/danger/info moments |
| `src/index.css` | `.animate-stagger` utility (50ms-step nth-child delays), button `transition-all duration-200`, progress-ring transition | No shimmer, no shared timing constants, ad-hoc durations (150/200/500ms mixed) |
| Landing.jsx | Heavily animated already — 38 `motion.*` usages, hero reveal | Polish pass only; entrance choreography is uneven below the fold |
| HomePage.jsx | 4 `motion.*` usages | Mostly static; greeting/prescription/tiles pop in with no choreography |
| Dashboard.jsx (Lab) | 2 `motion.*` usages | Game list renders instantly with no entrance; filter changes are jump-cuts |
| UnifiedProgress.jsx | 2 `motion.*` usages; static SVG `Sparkline` component (line 95) | Sparkline does not draw in; numbers don't count up; pattern cards have no hover depth |
| CoachPlay.jsx | **0** `motion.*` usages | The flagship page has the least motion. Sidebar panels appear/disappear instantly; react-chessboard 4.6.0 default piece animation only |
| Components | shadcn `Skeleton` (pulse, no shimmer), sonner `Toaster` bottom-right, Framer Motion **v12.30.0** | Skeleton lacks shimmer; toasts use sonner defaults |

**Overlap check:** No competing redesign effort exists in `docs/`. `unified_progress_v2_scope.md` covers that page's *content*; this scope covers *motion and visual polish only* and must not change UnifiedProgress's information architecture.

**Decision: EXTEND.** All five pages keep their layout, routes, data flow, and copy. This scope adds motion, refines color, and polishes interaction states on top.

---

## 1. What it is

A premium visual redesign of ChessGuru's five core pages with sophisticated animations, a refined color system, and modern micro-interactions — without adding or removing a single feature. The app should feel fast, responsive, and intentional at every interaction point: pages choreograph in instead of popping in, numbers count up instead of appearing, the board responds to every move with weight, and buttons acknowledge every press. The goal is that a 600-1500 player opens ChessGuru and perceives "professional chess coaching software," not "web app."

---

## 2. What the user sees

### Visual language (applies everywhere)

- **Base:** `#06060B` background unchanged. Amber/gold (`amber-400`/`amber-500`) stays the primary accent.
- **Proposed secondary accents (OPEN QUESTION — see §6):** a cool counterweight for data/progress moments (candidate: teal `#2DD4BF`), and a semantic pair — emerald for wins/clean streaks, rose for blunders/losses. Used sparingly: amber stays >80% of accent usage.
- **Spacing:** unchanged (current Tailwind scale).
- **Timing system (to be locked pre-code, see §7):**
  - Micro (hover, press): 150ms, `ease-out`
  - Standard (cards, panels): 300ms, custom cubic-bezier `(0.22, 1, 0.36, 1)` ("snappy settle")
  - Choreography (page entrance, stagger): 400-600ms total, 60ms stagger step
  - Charts/numbers: 800ms, `ease-in-out`
- All motion respects `prefers-reduced-motion`.

### Landing (`/`) — animated hero + staggered reveal

```
┌──────────────────────────────────────────────────────────┐
│         [logo glows in, 400ms]                            │
│                                                          │
│     A coach that remembers                               │  ← headline words rise
│     every mistake you make.        [♞ board piece        │    in sequence, 60ms
│                                     drifts subtly,        │    stagger, blur→sharp
│     [Start training →]              parallax on scroll]   │
│      ↑ amber gradient sweep on hover,                     │
│        scales 1.02, glow ring                             │
│                                                          │
│   ── scroll ──                                            │
│   ┌────────┐  ┌────────┐  ┌────────┐                     │
│   │ feature│  │ feature│  │ feature│  ← cards rise+fade  │
│   └────────┘  └────────┘  └────────┘    as they enter     │
│                                          viewport          │
└──────────────────────────────────────────────────────────┘
```

### Home (`/home`) — choreographed dashboard entrance

```
┌──────────────────────────────────────────────────────────┐
│  Good evening, Mohit.            (1) fades in first       │
│  Your piece safety is improving. (2) slides up +60ms      │
│                                                          │
│  ┌──────────────────────────────────────┐                │
│  │  TODAY'S FOCUS                        │ (3) hero card  │
│  │  Knights keep landing on squares      │  scales 0.97→1 │
│  │  your pieces can't cover. 12 min.     │  with soft     │
│  │  [Start session →]                    │  amber glow    │
│  └──────────────────────────────────────┘  breathing      │
│                                                          │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  (4) nav tiles      │
│  │ Play │ │ Lab  │ │Train │ │Progr.│   stagger in, 60ms; │
│  └──────┘ └──────┘ └──────┘ └──────┘   hover: lift 2px + │
│                                         shadow deepens    │
└──────────────────────────────────────────────────────────┘
```

### Lab (`/lab`) — animated cards + filtering

```
┌──────────────────────────────────────────────────────────┐
│  COACH'S PICK                                            │
│  ┌──────────────────────────────────────┐                │
│  │ [board preview fades in]  vs Hikaru99 │ ← entrance:    │
│  │ "You hung your queen on move 23 —     │   border glow  │
│  │  same pattern as 3 games this week."  │   pulses once  │
│  │ [Review this game →]                  │                │
│  └──────────────────────────────────────┘                │
│                                                          │
│  [All] [Unreviewed] [Wins] [Losses]  ← active pill slides│
│                                        (layoutId morph)   │
│  ┌────────────────────────┐                              │
│  │ game row               │ ← rows stagger-fade on filter │
│  ├────────────────────────┤   change (exit fade 150ms,    │
│  │ game row               │   enter stagger 40ms/row);    │
│  ├────────────────────────┤   skeleton shimmer while      │
│  │ game row               │   loading                     │
│  └────────────────────────┘                              │
└──────────────────────────────────────────────────────────┘
```

### Progress (`/progress`) — animated charts + pattern cards

```
┌──────────────────────────────────────────────────────────┐
│  Blunders per game                                        │
│   2.4 → 1.6        ← number counts down over 800ms        │
│   ╱╲                                                      │
│  ╱  ╲___╱╲___      ← sparkline path DRAWS left-to-right  │
│              ╲__     (stroke-dashoffset, 800ms), then     │
│                      endpoint dot pops in                  │
│                                                          │
│  CURRENTLY WORKING ON                                     │
│  ┌──────────────────────────────────────┐                │
│  │ Hanging pieces          ● ACTIVE      │ ← card hover:  │
│  │ 4 recent, 2 clean games  [▓▓▓░░]      │   lifts, glow; │
│  │                                       │   progress bar │
│  └──────────────────────────────────────┘   fills on      │
│  (cards below fold reveal on scroll)         viewport     │
└──────────────────────────────────────────────────────────┘
```

### Play with Coach (`/play-with-coach`) — living board + sidebar

```
┌────────────────────────┬─────────────────────────────────┐
│                        │  COACH                          │
│   ♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜    │  ┌───────────────────────────┐  │
│   ♟ ♟ ♟ ♟ ♟ ♟ ♟ ♟    │  │ "Nice — that knight now    │  │
│                        │  │  controls e5. What's your  │  │
│   pieces SLIDE 200ms   │  │  plan for the bishop?"     │  │
│   (cubic-bezier);      │  └───────────────────────────┘  │
│   captured piece       │   ↑ message slides in from      │
│   fades+shrinks 150ms; │     right + typing shimmer      │
│   last-move squares    │                                 │
│   glow amber, fade     │  [Escape squares quiz panel     │
│   over 1s              │   slides in 300ms when          │
│                        │   triggered, slides out on      │
│   ♙ ♙ ♙ ♙ ♙ ♙ ♙ ♙    │   dismiss]                       │
│   ♖ ♘ ♗ ♕ ♔ ♗ ♘ ♖    │                                 │
│                        │  eval-style move-quality chip   │
│                        │  pops in with spring (subtle)   │
└────────────────────────┴─────────────────────────────────┘
```

---

## 3. In scope (V1)

Each bullet is checkable done/not-done.

**Foundation**
- [ ] Motion constants module (`src/lib/motion.js`): exported durations, easings, stagger steps, shared variants — every page imports from here, zero inline magic numbers
- [ ] Refined color palette added to `tailwind.config.js`: amber stays primary; secondary accent + semantic win/loss colors (exact hues pending §6 signoff)
- [ ] `prefers-reduced-motion` respected globally (Framer Motion `useReducedMotion` + CSS media query)

**Buttons & micro-interactions**
- [ ] Primary button: hover scale 1.02 + glow, active scale 0.98, loading spinner state, gradient sweep on hero CTAs
- [ ] Hover states on all cards/tiles: 2px lift + shadow depth increase + border glow (150ms)
- [ ] Ripple-style press feedback on primary action buttons

**Page & list choreography**
- [ ] Page-level entrance choreography on all 5 pages (fade + rise, 60ms stagger between sections)
- [ ] Card entrance stagger on lists (Lab game rows, Progress pattern cards, Home nav tiles)
- [ ] Lab filter transitions: exit fade + enter stagger via `AnimatePresence`; active filter pill morphs via `layoutId`
- [ ] Scroll-triggered reveals (`whileInView`) on Landing below-fold sections, Lab game archive, Progress pattern cards

**Charts & numbers**
- [ ] UnifiedProgress sparkline animates: path draw-in via stroke-dashoffset (800ms), endpoint dot pop
- [ ] Animated number transitions (count up/down) on Progress stats and Home streak counts
- [ ] Pattern-card progress bars fill on viewport entry

**PWC (CoachPlay)**
- [ ] Piece slide animation tuned (react-chessboard `animationDuration`, target ~200ms — exact value pending §6)
- [ ] Capture effect: captured piece fade+shrink
- [ ] Last-move square highlight with amber glow that fades
- [ ] Coach message entrance: slide-in from right + brief shimmer while feedback is being generated
- [ ] Sidebar panels (escape-squares quiz, lesson picker, guardian prompt) slide in/out with `AnimatePresence` (300ms)
- [ ] Move-quality chip pops in with subtle spring

**System polish**
- [ ] Skeleton shimmer effect (upgrade existing shadcn `Skeleton` from pulse to shimmer sweep)
- [ ] Toast animations: sonner configured with slide+fade entrance, amber-bordered styling matching theme
- [ ] `pwc_coaching_lint.py` still passes (no coaching-text regressions); CoachPlay move latency unchanged (animations are presentation-only, never block the move POST)

---

## 4. Explicitly out of scope (V1)

- **3D board effects** — no perspective tilt, no 3D pieces. Flat board stays.
- **Custom fonts** — stays Fraunces + system stack. No font purchases or additions.
- **Sound effects** — no move sounds, no notification sounds.
- **New features** — zero new functionality. No new cards, panels, data, endpoints, or copy changes. Visual/UX polish only.
- **Responsive mobile redesign** — current mobile UX stays as-is. Animations must not *break* mobile, but no mobile-specific motion design in V1.
- **Pages beyond the five named** — GameAnalysis, Reflect, Openings, Settings etc. get the foundation (motion constants, button styles via shared components) for free but no dedicated choreography pass.
- **UnifiedProgress information architecture** — owned by `unified_progress_v2_scope.md`; this scope touches its motion only.
- **Confetti / celebration effects** — deferred; needs its own taste discussion.
- **Dark/light theme rework** — ThemeContext untouched.

---

## 5. Success criteria

- **Smell test passes on five named interactions:** (1) Home loads with visible choreography, not a pop; (2) Lab filter change animates rows instead of jump-cutting; (3) Progress sparkline draws in and the headline number counts; (4) PWC capture has visible weight (fade+shrink) and coach messages slide in; (5) every primary button visibly acknowledges hover and press. Each feels intentional and polished, verified by Mohit clicking through.
- **60fps:** animation frame rate stays at 60fps on a modern browser (Chrome DevTools performance trace on Home entrance, Lab filter, and a 10-move PWC sequence shows no dropped-frame jank; only `transform`/`opacity` animated, no layout-thrashing properties).
- **Nothing feels sluggish or jarring:** no interaction's perceived response exceeds ~100ms to first visual feedback; no entrance choreography delays interactivity (content is clickable while animating in).
- **Perception shift:** Mohit (and 2-3 real users informally) describe the app as feeling like "professional chess coaching software," not "a web app." Subjective, but it's the actual goal — stated honestly.
- **Zero functional regressions:** all existing flows work identically; `test_all_flows.py` (38 tests) still green; PWC move round-trip latency unchanged.

---

## 6. Open questions

1. **Color palette specifics**
   - **Question:** Keep amber as sole accent, or add a secondary? Candidates: teal `#2DD4BF` (cool counterweight for data/progress), purple, rose. And: emerald/rose as semantic win/loss pair? How many shades each (suggest 3: base/hover/muted)?
   - **Why unresolved:** Pure taste call — Mohit's signoff required.
   - **Unblocking step:** Render a one-page palette comparison (amber-only vs amber+teal vs amber+purple) as screenshots; Mohit picks.

2. **Animation timing**
   - **Question:** One consistent 300ms easing everywhere, or the tiered system proposed in §2 (150/300/600/800ms by interaction class)?
   - **Why unresolved:** Recommendation is the tiered system (uniform timing reads as flat), but it's a feel decision.
   - **Unblocking step:** 15-min demo of both on the Home page; lock constants into `motion.js`.

3. **PWC board animations**
   - **Question:** Piece slide duration (150 / 200 / 250ms)? Capture effect: fade-shrink vs bounce-out? Should the coach-feedback shimmer show during the polling window or only past 500ms?
   - **Why unresolved:** Board feel directly affects play rhythm; too slow gets annoying over a 40-move game. Needs hands-on testing, not theory.
   - **Unblocking step:** Build a three-duration toggle on a scratch board; Mohit plays 10 moves with each.

4. **Mobile touch feedback**
   - **Question:** Do touch devices get distinct press feedback (since hover doesn't exist), e.g. `:active` scale only, or tap-highlight glow?
   - **Why unresolved:** Mobile redesign is out of scope, but hover-only feedback would make mobile feel *dead* relative to desktop — minimum-viable touch answer needed.
   - **Unblocking step:** Decide one rule ("all hover effects have an `:active` twin") and test on one real phone.

5. **Landing parallax depth**
   - **Question:** Does the hero get scroll parallax (board piece drift) or is that over the line into gimmick?
   - **Why unresolved:** Taste + performance tradeoff on low-end devices.
   - **Unblocking step:** Prototype behind a quick toggle; Mohit judges on his own machine + phone.

---

## 7. Pre-code requirements

Hard gates — each must be true before the first line of code:

- [x] **Mohit has signed off on this scope document** (2026-06-12, "locked")
- [x] **Color palette choice locked** (§6 Q1 answered; exact hex values below)
- [x] **Animation timing constants locked** (§6 Q2 answered; durations + easing below)
- [x] **Framer Motion version confirmed:** ✅ verified `^12.30.0` in `frontend/package.json`
- [x] **react-chessboard 4.6.0 animation API confirmed** — `animationDuration` prop + custom square styles supported
- [x] **Tailwind config supports new shadow/glow utilities** — Tailwind 3.4.17 confirmed
- [ ] **Performance baseline captured:** DevTools trace before changes
- [ ] **`/audit-pre-code` run** before first file

---

## LOCKED DECISIONS (Mohit + Claude, 2026-06-12)

### Color Palette

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Primary accent | Amber | `#FBBF24` (amber-400) | Existing, keep unchanged; CTAs, hero glows |
| Secondary accent | Teal | `#14B8A6` (teal-500) | Progress bars, data charts, secondary actions |
| Win/progress | Emerald | `#10B981` (emerald-500) | Win streaks, clean game indicators |
| Loss/warning | Rose | `#F43F5E` (rose-500) | Blunders, losses, error states |

**Variants per color:** `-200` (hover/lighter), `-700` (darker), all added to `tailwind.config.js` under `extend.colors`.

### Animation Timing Constants (`src/lib/motion.js`)

```javascript
export const MOTION_TIMING = {
  micro: { duration: 150, easing: "easeOut" },
  standard: { duration: 300, easing: [0.22, 1, 0.36, 1] },
  page: { duration: 600, easing: "easeOut" },
  chart: { duration: 800, easing: "easeInOut" },
};

export const EASING = {
  snappy: [0.22, 1, 0.36, 1], // "snappy settle" cubic-bezier
  bounce: [0.34, 1.56, 0.64, 1], // slight overshoot for piece slides
};

export const STAGGER_STEP = 60; // ms between nth-child entrance
```

### PWC Board Animations

| Action | Duration | Easing | Notes |
|--------|----------|--------|-------|
| Piece slide | 200ms | `bounce` (cubic-bezier) | Smooth, natural chess feel |
| Captured piece fade+shrink | 150ms | `easeOut` | Fade to 0%, scale to 0.7 |
| Last-move glow | 800ms | `easeInOut` | Amber highlight, fades over time |
| Coach message slide-in | 300ms | `standard` | From right, with typing shimmer |

### Mobile Touch Feedback

- **Button `:active` state:** `scale(0.98)` + amber glow ring (4px blur, 2px spread)
- **Applies to:** all `.btn-primary`, `.btn-secondary`, nav tiles, CTAs
- **Media query:** `@media (hover: none)` to detect touch devices

### Landing Parallax

- **Enabled:** Yes
- **Element:** Hero board piece (subtle drift)
- **Amplitude:** 25px vertical offset on scroll
- **Fade zone:** Parallax stops at hero bottom (fade to 0% effect below fold)
- **Implementation:** Framer Motion `useScroll` + `useTransform`

---

*Status: READY FOR CODE. Next: `/audit-pre-code`, then implementation.*
