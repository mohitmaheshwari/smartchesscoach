# PWC Responsive Redesign — Scope

Status: AWAITING SIGNOFF
Owner: Mohit · Date: 2026-06-22
Design source: `C:\Users\MIISCO\Downloads\ChessGuru` (`Play.jsx` desktop, `MobilePlay.jsx` mobile, `styles.css` tokens)

---

## 0. Existing surfaces audit (EXTEND)

**Surfaces touching this need:**
- [frontend/src/pages/CoachPlay.jsx](../frontend/src/pages/CoachPlay.jsx) — 3173-line orchestrator. Holds ALL state + teaching logic. Renders a thin top strip + a `flex` shell (`h-[calc(100vh-80px-44px)]`) containing board + sidebar side-by-side.
- [frontend/src/components/coach/CoachPlayBoard.jsx](../frontend/src/components/coach/CoachPlayBoard.jsx) — `flex-1`, board capped `max-w-[min(550px, calc(100vh-180px), calc(100vw-450px))]`, eval bar, controls.
- [frontend/src/components/coach/CoachPlaySidebar.jsx](../frontend/src/components/coach/CoachPlaySidebar.jsx) — fixed `w-[380px] border-l`, ~1160 lines, ALL live coach panels.
- [frontend/src/components/coach/CoachPlaySetup.jsx](../frontend/src/components/coach/CoachPlaySetup.jsx) — pre-game screen.

**What they already provide:** the complete working teaching loop — SSE push, chess.js, escape-squares quiz, traps, opening guidance, predict-move, rate-move, behavioral coaching, chat, postgame summary, eval bar, move history/browse. None of this is in the design mock.

**Overlap vs differentiation:** the design = a clean *visual + layout* language (warm off-black, amber accent, bottom-sheet on mobile, two-column on desktop) for the SAME loop. It does NOT redefine the coaching content — it restyles and re-lays-out it. Genuine new value = responsiveness + the design aesthetic. Overlap = the teaching content itself (keep as-is).

**Decision: EXTEND.** Re-skin + responsive shell over the existing components. No teaching logic rewritten. (Code comment at CoachPlay.jsx:2960 already warns against rebuilding it — confirmed.)

---

## 1. What it is

Play with Coach gets the new ChessGuru design language and becomes fully responsive. On a phone the board sits on top and the coach lives in a draggable bottom sheet you pull up to read and act; on a tablet/desktop the board and a coach side-panel sit two-up. The coaching content, moves, and every existing panel are unchanged — only the skin and the layout adapt to the screen.

## 2. What the user sees

**Mobile (`< 1024px`)** — board on top, coach in a bottom sheet:
```
┌─────────────────────────┐
│ ‹  Play with Coach   ↻   │  header (thin, sticky)
│      SPANISH · GUIDED    │
│ ┌─ Coach · teaching ───┐ │  opponent strip (+ eval read inline)
│ └──────────────────────┘ │
│      [  CHESS BOARD  ]    │  full-width, square, centered
│ ┌─ You · 1247 ─── e4 e5┐ │  you strip (+ last moves)
│ └──────────────────────┘ │
│ ╭──────⎯⎯──────────────╮ │  ← bottom sheet (drag handle)
│ │ G  Coach · your move │ │
│ │ "Develop AND hit e5" │ │  coach thought
│ │ ▸ Nf3   develop+atk  │ │  candidate cards (tap → preview
│ │ ▸ Bc4   italian      │ │     on board, expand for verdict,
│ │ ▸ Nc3   quiet        │ │     Play button commits)
│ ╰──────────────────────╯ │
└─────────────────────────┘
```

**Desktop / tablet-landscape (`≥ 1024px`)** — two columns:
```
┌──────────────────────────────────────────────┐
│  Play with Coach    SPANISH·GUIDED   Restart  │
├───────────────────────────┬──────────────────┤
│  ┌ Coach · teaching ────┐ │  Even ▏━━━━●━━━   │ position read
│  │                      │ │  G Coach·your move│
│  │     CHESS BOARD      │ │  "Develop and hit │ coach thought
│  │     (fluid square)   │ │   e5 at once."    │
│  │                      │ │  ▸ Nf3  explore   │ candidate rows
│  └ You · 1247 ──────────┘ │  ▸ Bc4  explore   │
│   1.e4 e5  2.Nf3 …        │  ▸ Nc3  explore   │
│                           │  ─ practiced today│ keepsake
└───────────────────────────┴──────────────────┘
```

Look: deep-amber accent `#d97706`, warm off-black surfaces, Inter + JetBrains Mono, hairline borders; dark + light. Existing panels (quiz/trap/predict/etc.) render inside the same sheet/column, restyled to the tokens.

## 3. In scope (V1)

- Responsive shell in CoachPlay.jsx: stacked + bottom-sheet `< 1024px`; two-column board + side panel `≥ 1024px`. Replaces the fixed `flex` + `w-[380px]`.
- Board sizes fluidly to its container (no `100vw-450px` collapse); square preserved.
- Mobile bottom sheet for the coach panel: drag handle, collapsed (peek) ↔ expanded states; scrollable body.
- PWC-scoped design tokens (amber/warm palette, fonts, hairlines) applied to board + sidebar, honoring the app's existing dark/light ThemeContext.
- All existing CoachPlaySidebar panel states keep working, restyled to tokens.
- Player strips (Coach / You) above & below the board, with the inline eval "read".
- Touch targets ≥ 44px on mobile; candidate/Play actions thumb-reachable.

## 4. Explicitly out of scope (V1)

- Rolling the design language to the rest of the app (Home/Lab/Analysis) — PWC only for now.
- Changing any coaching *content*, copy, detector, or backend behavior.
- The scripted demo loop from the mock (we keep the real engine).
- Replacing react-chessboard or the eval-bar component.
- New features not already present (skill pills, nav rail redesign, etc.).
- CoachPlaySetup full redesign — V1 gives it the tokens only, not a re-layout (fast-follow).

## 5. Success criteria

- No horizontal scroll / board never collapses at 360px, 768px, 1024px, 1440px widths.
- Every existing panel + control reachable and usable at 360px wide.
- Zero regressions in the teaching flow (move → coach reply → feedback → panels) — manual pass on desktop + a mobile viewport.
- Lighthouse/manual: tap targets ≥ 44px on mobile; board interaction works by touch.

## 6. Open questions

- **Q:** Bottom-sheet behavior — peek height + does it auto-expand when the coach has a new prompt? **Unresolved:** UX preference. **Unblock:** follow the mock (`370px` peek, expands to `78%` on candidate tap); confirm with Mohit on first build.
- **Q:** PWC-scoped palette vs retheming globally. **Unresolved:** Mohit's rollout intent. **Unblock:** V1 scopes tokens to PWC; revisit for global rollout.
- **Q:** Tablet portrait (768–1023) — sheet or side-panel? **Unresolved.** **Unblock:** treat as "mobile" (stacked + sheet) in V1; it reads cleaner than a cramped side column.

## 7. Pre-code requirements

- [x] Design source reviewed (Play.jsx, MobilePlay.jsx, styles.css).
- [x] Existing PWC components mapped.
- [ ] Mohit signs off on this scope.
- [ ] Feature branch created (don't build on the shared `working-code` lane branch).
- After signoff: build shell → tokens → sheet → panel restyle, verifying at each breakpoint.
