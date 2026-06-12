# Scope — Fact-Templated Captions

*Feature name:* `fact_templated_captions`
*Status:* DRAFT — awaiting Mohit signoff. No code until signed off.
*Created:* 2026-06-10

---

## 0. Existing surfaces audit (EXTEND)

**What already touches this need:**

- **`services/caption_pipeline.py` — the central layer** (`build_move_teaching_decision`). This is THE place caption facts are injected and text is built ([[project_caption_pipeline_central_layer]]). It already has fact-injectors (`inject_user_blunder_detector_facts`, `inject_opp_side_narration_facts`, `inject_good_move_reason_facts`, etc.).
- **The Claude narrator** — production already renders prose via `claude-sonnet-4-6` (`llm_service.py`). We are NOT introducing Claude; it's already here. The confabulations came from bad/missing facts fed to it (and from the deterministic template layer emitting unverified text), not from the model.
- **CAPTION_BACKLOG.md** already has predicate sketches for most of these patterns: **#7** (`opp_abandons_defense`), **#19** (target-verification guard / confabulation), **#20** (delta-grounded reason), plus an existing `missed_fork` detector.
- **PWC (`coach_play/`)** runs its **own** coaching engine and bypasses all of the above (this is the items-1/3 source). [[project_pwc_runs_second_coaching_engine]].

**Overlap vs differentiation:**
- *Overlap:* nearly every pattern below already has a filed sketch. This is not a new idea — it's the consolidation + build of work already scoped.
- *Genuine new piece:* (a) a **fact-verification guard** that blocks any "wins/attacks/then-play X" clause unless it's true on the board; (b) **deterministic template strings** for the clean-fact patterns so they render with **no LLM call**; (c) a **cache layer** so the positional-nuance cases pay Claude once per position-class, not per render.

**Decision: EXTEND `caption_pipeline.py`.** New predicates + a render-mode router live in the central layer. No parallel system. **Scope is the Lab / V5 review surface ONLY.** PWC is in active development (its engine is changing), so it is fully out of this scope — its flagged items (1, 2, 3) stay parked in PROGRESS_BACKLOG #5 for when that work settles.

---

## 1. What it is

A set of generic, engine-grounded detectors that turn a chess position + the move played + Stockfish's verdict into **verified facts** (e.g. "this enemy piece has zero defenders," "that move newly attacks an undefended enemy pawn on b6," "the best move hits two enemy pieces at once"). 

For the patterns where the fact *is* the lesson, we render it as a **plain template sentence with no AI call** — instant, free, and impossible to confabulate because every noun in the sentence was checked against the board. For the handful of patterns that need positional judgement (why one quiet developing move beats another), we ask Claude **once** and **cache** the answer, so we keep the good coaching voice without paying for it on every page load.

Crucially, a hard rule sits in front of every caption: **never state a capture, target, or follow-up move unless it is actually true on the board.** If a *fabricated extra* claim can't be verified, that clause is dropped — silence beats a confident lie.

**The why-rule (non-negotiable):** if a move is a genuine, engine-confirmed mistake/inaccuracy/blunder, the caption **must explain WHY** — what the move allows, abandons, or misses — in coaching tone, simple English. A bare *"X is a mistake, Y was better."* with no why is not acceptable. If the deterministic detectors don't produce a real why, the move is routed to the cached Claude narrator (fed the engine facts) to **write** the why. Silence is allowed **only** for routine/sound moves — never as a substitute for the why of a real mistake. And the why must be **real and position-specific**, never principle-bank filler ([[principle_bank_is_filler]]).

**Narrator delivery (Mohit decision, 2026-06-10):** the live narrator calls the **terminal Claude gateway** (the ngrok-exposed `claude -p` CLI), NOT the in-process Anthropic SDK. Because that gateway is fragile (free ngrok tunnel that rotates/throttles, host must be up, 13–68s latency — all observed during the 2026-06-10 batch), the live integration is **only acceptable with these hard rails:**
- **Async, never blocking** — render the deterministic caption immediately; if it lacks a why, queue the gateway call and serve the upgraded caption on the *next* view. The user never waits on Claude.
- **Cache by position** — one gateway call per position, result stored; never call on a cache hit.
- **Circuit-breaker + graceful degrade** — after N consecutive gateway failures, stop calling and serve the best deterministic caption we have. A user must NEVER see `<client timeout>`, an error, or an empty caption.
- **Config-driven endpoint** — `LLM_API_BASE` + `LLM_API_KEY` from secrets/env; ideally auto-refreshed from the ngrok local API so a URL rotation doesn't break prod.
(The offline batch backfill uses the same gateway; latency/uptime don't matter there.)

The result: the captions that today say "it wins the rook" (when it doesn't) or "attacks their pawn on f6" (when f6 is your own pawn) either become correct, or go quiet.

## 2. What the user sees

No new screen. Same caption slot on the **game-review (Lab)** board. The *content* changes. Before → after, on real flagged Lab positions:

```
POSITION: a4 played, Rd1 was better (review)
  BEFORE: "a4 is an inaccuracy. Rd1 was better. it wins the rook."   <-- false
  AFTER:  "a4 is an inaccuracy. Rd1 was better — it pressures Black's pawn on d6."
          [pattern: move_attacks_target — template, target verified as enemy + attacked]

POSITION: opponent's Qg5 blunder (review)
  BEFORE: "Opponent's Qg5 is a major blunder. Play Rxe2."   <-- no why
  AFTER:  "Opponent's Qg5 left the bishop on e2 unguarded — play Rxe2 to win it."
          [pattern: opp_abandons_defense — template]

POSITION: move 2 e4, routine (review)
  BEFORE: ""   <-- empty/garbled
  AFTER:  (no caption — routine opening move, nothing to teach)
          [pattern: routine_opening — suppressed]

POSITION: Bd2 vs Bd3, positional nuance (review)
  BEFORE: "Bd2 is an inaccuracy. Bd3 was better. 6 of your pieces are still on your side."  <-- filler
  AFTER:  "Bd2 is an inaccuracy. Bd3 was better — it stays active and doesn't block your d-pawn."
          [pattern: positional — fact-fed Claude narrator, CACHED by position-class]
```

**Render decision (the product contract):**
```
move is a genuine mistake/inaccuracy/blunder (engine-confirmed):
    a detector yields the why   -> deterministic template string  (no LLM)
    no detector yields the why  -> cached Claude narrator, fed engine facts, WRITES the why
    HARD RULE: never "X is a mistake, Y was better." with no why;
               never principle-bank filler as the why
move is routine / sound / good:
    -> stay silent (nothing to teach)
any capture / target / follow-up clause (a fabricated EXTRA):
    -> verify on the board; unverifiable -> drop THAT clause
       (the mistake's why still stands via the narrator)
```

## 3. In scope (V1)

Applies to the **Lab / V5 review captions** (game analysis) ONLY. Detectors built in `caption_pipeline.py`.

- **5 clean-fact detectors**, each with (a) a deterministic fire condition, (b) a board-verified template string:
  - `move_attacks_target` — the moved piece **newly** attacks an under-defended **enemy** piece/pawn (ownership + attack both verified — kills the "f6"/"wins the rook" class). *(items 5, 6)*
  - `opp_abandons_defense` — opponent's move vacates the sole defender of a square the user can now win (CAPTION_BACKLOG #7). *(items 5, 9, 10)*
  - `missed_double_attack` — the best move attacks ≥2 enemy pieces (reuse/extend existing fork detector). *(item 8)*
  - `clean_capture` — move captures with an even-or-winning recapture. *(item 9)*
  - `routine_opening` — move 1–6, small cp_loss, severity good → **suppress** (stay silent). *(item 4)*
- **The fact-verification guard** — any clause naming a capture / target / follow-up is checked against the board before render; unverifiable → dropped (CAPTION_BACKLOG #19). *(items 5, 6, 12)*
- **Cached Claude narrator** for the **positional-nuance** path AND as the **guaranteed why-provider** for any engine-confirmed mistake the detectors don't cover (the why-rule above), keyed by a position-class signature so each shape is narrated once and reused. *(items 7, 13, and any uncovered mistake)*
- **The why-rule enforced:** every engine-confirmed mistake/inaccuracy/blunder caption carries a position-specific why in coaching tone, simple English — via template or narrator. No bare "X is a mistake, Y better."; no filler why; silence only for routine/sound moves.
- **"Missing-why" gate** — a check after detector render: move is a flagged mistake AND the caption has no real why (bare/empty/filler) → route to the narrator.
- **Terminal-gateway narrator client** with the 4 hard rails above (async, cache, circuit-breaker, config endpoint). Reuses the validated why-rule prompt from the batch run.
- **Position-keyed cache** for narrator results.
- **Per-detector corpus probe** run BEFORE the gating is locked (fire rate + false-positive sample), per [[feedback_threshold_before_distribution_is_sin]].
- **All flagged Lab caption positions** render correctly (or go silent) on a re-render — this is the acceptance fixture (items 4, 5, 6, 7, 8, 9, 10, 12, 13).
- Passes `backend/scripts/pwc_coaching_lint.py` (no empty / snake_case-leak / jargon / pawn-called-piece).

*(`free_capture_available` is NOT in V1 — its only examples were PWC items 1/3, and there is no Lab example yet. Build it when a Lab instance appears.)*

## 4. Explicitly out of scope (V1)

- **PWC entirely.** PWC is under active development and its engine is expected to change, so this scope does not touch `coach_play/` at all — not the render path, not the detectors, not "build it generically for PWC later." Items 1, 2, 3 stay parked in PROGRESS_BACKLOG #5 and get re-examined once PWC stabilizes.
- **Pure-template rendering of positional patterns.** Items 7/13 go through the cached narrator, NOT hardcoded strings — hardcoding them reproduces the rejected filler ([[principle_bank_is_filler]]).
- **New nuance detectors beyond the cache path** (e.g. a dedicated `queen_harassment_avoided` predicate). The cached narrator covers the long tail in V1; promote a pattern to its own detector only after ≥2 more examples.
- **The clickable-recommended-move UI fix** (PROGRESS_BACKLOG #6) — unrelated frontend work.
- **The "praise + remember good moves" feature** (PROGRESS_BACKLOG #7) — separate product.
- **Drillability / puzzle generation** from these patterns.

## 5. Success criteria

- **Confabulation rate = 0** on a re-render of the flagged corpus: zero captions name a capture/target/follow-up that isn't on the board. (Measured by re-running the verification guard over re-rendered captions + spot engine-check.)
- **Why-coverage = 100%** of engine-confirmed mistake/inaccuracy/blunder captions carry a position-specific why (template or narrator). Zero bare "X is a mistake, Y better." captions; zero principle-bank filler whys. (Measured by scanning re-rendered mistake captions for a why-clause + spot-reading for filler.)
- **All 9 flagged Lab caption positions** from the 2026-06-10 batch (items 4, 5, 6, 7, 8, 9, 10, 12, 13) render either correct or silent — checked against the gateway-Claude gold answers already captured. (Item 11 is a UI bug, out; items 1–3 are PWC, out.)
- **Clean-fact patterns render with no LLM call** (verified: 0 Anthropic calls for those render paths).
- **Per-detector false-positive rate < 10%** on its corpus-probe sample before the detector ships (each gated by `/detector-quality-scan`).
- No regression on `pwc_coaching_lint.py` across the re-rendered corpus.

## 6. Open questions

- **Question:** What is the cache key ("position-class signature") for the narrator cache?
  **Why unresolved:** too tight = no cache hits (pay Claude every time); too loose = wrong prose reused on a different position. Needs design.
  **Unblocking step:** 30-min design + probe how many distinct positional shapes exist in the corpus.

- **Question:** Where does `free_capture_available` sit in detector **precedence** vs existing blunder/opp detectors? (A free capture often co-occurs with other facts.)
  **Why unresolved:** precedence isn't documented; firing two detectors could double-caption.
  **Unblocking step:** read the current dispatch order in `caption_pipeline.py`; define precedence in the scope's architecture doc (separate).

- **Question:** Per-detector gating thresholds (e.g. minimum piece value for `free_capture`, "under-defended" definition for `move_attacks_target`).
  **Why unresolved:** picking before seeing the fire distribution is the threshold-before-distribution sin.
  **Unblocking step:** corpus probe per detector (`/lock-via-data`).

- **Question:** Does V1 include re-rendering existing analyzed games, or only new ones?
  **Why unresolved:** depends on `V5_COACHING_VERSION` bump cost + whether you want the back-catalog fixed now.
  **Unblocking step:** Mohit input + `/refresh-v5-captions` cost check.

- **Question:** How does prod keep `LLM_API_BASE` current when the ngrok URL rotates?
  **Why unresolved:** the gateway is on a free ngrok tunnel that changes URL on restart; a hardcoded value breaks the live narrator.
  **Unblocking step:** decide between (a) manual env update on rotation, (b) a small refresher that reads the host ngrok API, or (c) move the gateway to a stable/paid domain.

- **Question:** Circuit-breaker thresholds (how many failures before tripping, how long before retry) and the first-view behavior (show bare caption vs "coach is thinking" placeholder).
  **Why unresolved:** product + reliability call; depends on observed gateway uptime.
  **Unblocking step:** Mohit input on first-view UX; pick thresholds after watching gateway reliability over the batch run.

## 7. Pre-code requirements

- [ ] Mongo on :27018 reachable from a probe context (the corpus probe must run — note: the backend container could not reach it this session; resolve first).
- [ ] Per-detector corpus probe has returned fire-rate + false-positive distributions (`/lock-via-data`), and each gate is locked against data, not gut.
- [ ] Cache-key (position-class signature) design decided (Open Q1).
- [ ] Detector precedence order documented (Open Q2).
- [ ] The §2 mockup is signed off as the product contract.
- [ ] The chessguru.ai **server** can reach the gateway URL with the key (verify `/health` + `/me` from the prod box, not just locally), and `LLM_API_BASE`/`LLM_API_KEY` are set as prod secrets.
- [ ] First-view UX decided (bare caption vs placeholder) + circuit-breaker thresholds set.
- [ ] `/audit-pre-code` run.
- [ ] **Mohit has explicitly signed off on this scope document.**
