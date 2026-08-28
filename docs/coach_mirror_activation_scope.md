# Coach Mirror activation — scope

Status: DRAFT, awaiting Mohit's sign-off. No code changes made under this scope yet.

## 0. Existing surfaces audit

**Finding: what this scope originally set out to build already exists.**

Investigated four places in the codebase that all independently answer "which
weakness matters right now" for a user:

| Mechanism | Selection logic | Rendered anywhere? |
|---|---|---|
| `player_profiles.top_weaknesses` | flat count, never decays | `/profile/weaknesses` exists but has zero frontend callers |
| `user_pattern_decay` / `pattern_decay_service` | exponential decay + recovery credit | **Yes** — Lab's Coach's Pick |
| `coach_memory.recurring_patterns` | count ≥3, no decay | **Yes** — Home coach message, PWC greeting |
| `services/game_mirror.py`'s `_established_patterns()` | recency-window threshold (≥N of last M games) | **Nowhere** |

`game_mirror.py` — "the Mirror" — is the closest thing to the actual ask
("one thing, why it happened, how it's trending, in coach voice"). It:

- Picks the established pattern(s) for a window of games.
- Composes a coach-voice verdict (`_compose_verdict` / `_aggregate_verdict`):
  "Lost, and the same gap turned it: you hung a piece again," "Clean win.
  No fork-miss this time," a "you listened" callback when a flagged pattern
  disappears.
- Is already wired end-to-end on the backend (`routes/home.py:758`,
  `result["last_session"]`) — computed on every Home dashboard load.

**It is rendered nowhere.** Grepped the entire frontend for `last_session`:
zero matches. The exact voice and structure being asked for has been built,
runs on every page load, and no user has ever seen it.

Also found: `_find_concrete_anchor()` (`game_mirror.py:192`) — finds the
single most-decisive move tagged with a given pattern (prefers losses,
highest cp_loss). **Defined, never called.** The actual "why" text today
(`_teaching_prompt()`) is a static, category-keyed generic tip ("practice
spotting forks"), not anything about what happened in the user's own game —
despite the machinery to do exactly that already existing, one function
away.

**Decision: EXTEND, not PARALLEL.** Building a new "coach's note" surface
would be a 5th mechanism doing the same job as the other 4. The real gap is
activation (wire the Mirror to the frontend) and one missing connection
(wire the orphaned anchor function into the sentence builder) — not new
architecture.

Deliberately NOT in this scope (real, related, but separate decisions):
- Retiring `_established_patterns()` in favor of `user_pattern_decay` (the
  decay model is profile-level; the Mirror is per-game-window — the seam
  needs real design, not a drop-in swap). Filed as a named V2 follow-up.
- Routing Mirror sentences through `build_move_teaching_decision` (the
  central caption engine). Different job — the Mirror narrates a pattern
  across a session, the caption engine explains one move. Not pursuing this
  now; the concrete-anchor fix below gets most of the "why" value without
  it.
- The 15-category `move_classification` taxonomy. Not needed for this V1 —
  the Mirror's coarse cognitive_gap categories are enough to name a pattern
  in a sentence; richer labels are a wording upgrade, not a blocker.

## 1. What it is

The Mirror already watches every game you play and knows when an old habit
resurfaces or finally breaks — it just never told you. This ships that: your
Home page gets a short, honest recap after your last session — what
happened, whether an old pattern showed up again (and which real move it
was, not just the category name), and whether you're actually breaking it.

## 2. What the user sees

Real data, Mohit's own account, live window of 2 games (one win, one loss),
established pattern from the last 15 games: `piece_safety`.

**Today (computed, but shown nowhere):**

> Two games — one each way. One came down to hanging pieces. King-safety
> problems also turned up in one of two. Before every move, check both
> sides: is any of MY pieces attacked more times than it's defended? Same
> question for theirs. Second time hanging pieces have shown up — these are
> real now, not noise.

**V1 (rendered on Home, anchor wired in):**

> Two games — one each way. One came down to hanging pieces: **move 27,
> you played Nxf2 when Nc3 kept everything defended.** King-safety problems
> also turned up in one of two. Before every move, check both sides: is any
> of MY pieces attacked more times than it's defended? Same question for
> theirs. Second time hanging pieces have shown up — these are real now,
> not noise.

Bolded sentence is the only new content — everything else is the existing,
already-computed story, just finally visible.

Card also carries (already computed, per `mirror.games_breakdown`): per-game
outcome, opponent, opening, accuracy, and a tap-through to the game. No new
backend fields required for that part.

## 3. In scope (V1)

- `HomePageNew.jsx` renders `result.last_session` (currently silently
  discarded) as a card, in the position appropriate for a "since you last
  played" recap.
- `_find_concrete_anchor()` wired into `_compose_verdict()` /
  `_aggregate_verdict()`: when a repeated pattern has a matching critical
  move in the window, the sentence names the real played/best move and
  move number instead of stopping at the category-level tip.
- Falls back to the current generic-tip sentence when no concrete anchor
  exists for the pattern (matches the function's existing "silent fallback"
  contract — never invent a move that isn't there).
- Card links through to the relevant game (`game_id` already present in
  `games_breakdown`).
- No backend schema changes — `build_game_mirror()`'s return shape already
  carries everything needed; this is wiring, not new computation.

## 4. Explicitly out of scope (V1)

- Swapping `_established_patterns()` for `user_pattern_decay` (named V2
  follow-up above).
- Any use of `build_move_teaching_decision` / the central caption engine
  inside the Mirror's sentences.
- The 15-category `move_classification` taxonomy feeding pattern naming.
- Retiring or changing `player_profiles.top_weaknesses`,
  `coach_memory.recurring_patterns`, or any other existing "which pattern"
  mechanism — they stay as they are.
- Any change to the Mirror's window-opening logic (`mirror_window.opened_at`,
  `WINDOW_MAX_HOURS`) or to `services/mirror_engagement.py`.
- Coach-session (Play with Coach) recap — CLAUDE.md notes imported games
  always win the Evidence slot when present; this scope doesn't touch that
  priority rule.

## 5. Success criteria

Behavior-changing, not vanity:
- Users with an active mirror window (i.e., `result.last_session` is
  non-null on their next Home load) actually see the card — measurable via
  a simple "card rendered" event, since today it's 0% by construction.
- Of sessions where a repeated pattern has a matching critical move in the
  window, the sentence includes the real move (not the generic fallback) —
  target: matches the "1 of 2 games in the Mohit example" rate we'd expect
  from real data, i.e., most repeated-pattern verdicts get a real anchor,
  not most falling back to generic.

## 6. Open questions

- **Question:** Where exactly on Home does this card sit relative to the
  existing "one_thing_to_fix" (motif-based) card and the coach message —
  do they coexist, or does one subsume the other?
  **Why unresolved:** Both are pattern-callout cards from different data
  sources (motif_profile vs. cognitive_gap); haven't audited whether
  showing both reads as repetitive.
  **Unblocking step:** Look at both rendered together on one real account
  before deciding stacking order.

- **Question:** Should the "you listened" callback (pattern disappeared
  from a previously-flagged window) get its own visual treatment, or fold
  into the same card?
  **Why unresolved:** No mockup done yet for the multi-game aggregate case
  with a listening line present.
  **Unblocking step:** Pull a real account with a listening-line case (none
  found in this session's spot checks) before designing that state.

## 7. Pre-code requirements

- Mohit has explicitly signed off on this document.
- Confirm the exact Home card placement (open question above) — at least a
  placeholder decision, even if revisited after seeing it live.
- No numeric threshold locks needed for V1 (this scope doesn't add or
  change any threshold — `/lock-via-data` not required).
