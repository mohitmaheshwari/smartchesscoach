# Scope: One Surviving Instruction (Sprint 2)

Status: **IMPLEMENTED, 2026-08-08 — behind `PWC_SURVIVING_INSTRUCTION_
ENABLED` (default OFF), not yet deployed.** v1 rejected (4 inaccuracies).
v2 rated 8.5/10, withheld on 2 amendments (canonical ownership,
orthogonality ruling) — both applied in v3, signed off. During
implementation, subtype-aware matching was further narrowed to
`simple_hang` only after checking the real subtype distribution (see
§3) — a real, data-checked scope reduction, not silently shipped as if
it covered all 5 subtypes. All §7 pre-code requirements are checked
off. 18 dedicated tests + full existing regression suite (33/33)
passing. Not deployed — this flag/gate combination means it cannot
reach any real user even once merged, until an explicit deploy AND a
separate rollout decision after Experiment #1 closes (§4).

---

## 0. Existing surfaces audit

Audit performed by Mohit, re-verified twice against the actual code —
once before v1, once more after v1's review surfaced 4 further
inaccuracies (all 4 independently confirmed true before this revision;
evidence inline below).

**Confirmed exactly as described (unchanged from v1):**

- **`user_active_focus`** — written by `primary_weakness_picker.py:748-784`
  (`assign_focus`). Fields: `user_id, type: "weakness", status, topic_key,
  moments_page_topic, picker_score, coaching_label, coaching_narrative,
  subtype_histogram, runners_up, started_at, locked_until,
  baseline_metric, current_metric, resolution, next_action`.
  **The collection is shared**: `primary_strength_picker.assign_strength()`
  writes `type: "strength"` docs to the same collection with an
  unrelated schema (`baseline_band`, `z_score`, `cohort_mean`, etc.) —
  `focus_bridge` filters to `type: weakness` (or missing `type`)
  explicitly, so this doesn't affect anything below, but don't be
  surprised by a strength doc if you query the raw collection.
  **`assign_focus` runs via an external OS crontab on the production
  server** (`0 3 * * * .../assign_focuses.py --apply`, outside this
  git repo, confirmed live via its log), not from any in-process loop
  in `server.py` — daily, once. Gated on `>=10 analyzed games`
  (`scripts/assign_focuses.py:59`); today 52/114 users (46%) clear
  that bar. `server.py`'s in-process `focus_outcome_loop` only *closes*
  expired locks — it never assigns new ones.
- **`focus_bridge.py:24-78`** (`get_active_focus_bundle`) — sole
  designated reader of `user_active_focus`, replaced four prior rival
  sources per its own docstring.
- **PWC session start** (`coach_game_session.py:294-385`) — builds
  `session_goal`, `session_greeting`, and a local variable named
  `initial_scoreboard = {focus_topic, focus_subtype, focus_label,
  matched_moments, handled_correctly, handled_incorrectly, events}`
  (line 351-361) — **persisted under the key `mission_scoreboard`**,
  not `initial_scoreboard` (that name is a local Python variable only;
  earlier drafts of this scope cited the wrong persisted key — fixed
  throughout this version). `session_focus=focus_bundle` also
  persisted. Only populated when `focus_bundle.get("topic_key")` is
  truthy (line 352) — `None` otherwise, which is the honest, correct
  behavior for a user with no active focus yet, not a bug.
- **Piece-safety subtypes** — real, board-verified:
  `simple_hang, threat_ignored, tactical_seq_loss, quiet_blunder,
  small_slip` (`move_observation_deriver.py:229-287`,
  `_classify_piece_safety_subtype`).
- **`user_teaching_memory`** — confirmed abandoned in Sprint 1. Not to
  be revived.
- **`pwc_insight_shown`** — real, shipped in Sprint 1.

**Correction #1 (from v1) — `pattern_verdict` isn't wired to
`user_active_focus`:**

`pattern_verdict` (`coach_play.py:9874-9928`) is sourced from
`pattern_memory_service.get_top_patterns`, a third, independent
mechanism — not from `user_active_focus`/`focus_bridge`.

**Corrections #2-5 (from v1's review, each independently re-verified):**

1. **`pattern_verdict` does not resolve `user_active_focus` — confirmed.**
   `pattern_verdict` is assembled only into the reflection-UI response
   dict (`coach_play.py:9998`); nothing near that code path writes to
   `db.user_active_focus`. The real resolution mechanism is a **genuine
   14-day cycle**: `assign_focus` sets `locked_until = now + 14 days`
   (`LOCK_DURATION_DAYS = 14`, `primary_weakness_picker.py:442`). A
   daily background loop, `focus_outcome_loop()` (`server.py:95-126`),
   finds `active` focuses past `locked_until`, calls
   `check_focus_outcome` (comparing pre/post mistake rate) then
   `close_focus`, writing `status` (`completed`/`escalated`/`active`)
   and `resolution` (`improved`/`regressed`/`stuck`)
   (`primary_weakness_picker.py:787-830+`). **"Two clean games and the
   instruction is done" is not supported today and is removed from
   this scope** — see the redefinition of "survives" in §3 below.

2. **`update_scoreboard()` only evaluates `focus_topic` — confirmed.**
   `mission_scoreboard.py:263-321` reads `scoreboard["focus_topic"]`
   and dispatches through `is_focus_moment()` (lines 237-260), which
   branches only on topic strings (`piece_safety`, `king_safety`,
   etc.). `focus_subtype` is read elsewhere in the file only for
   message text (e.g. `build_recall_callout`), never for match/handled
   classification. **V1 will add subtype-aware detection** — see §3.

3. **`rebuild_scoreboard_from_history()` drops unlisted fields, and
   this is a real overwrite path — confirmed.**
   `mission_scoreboard.py:324-375` constructs exactly 7 keys
   (`focus_topic, focus_subtype, focus_label, matched_moments,
   handled_correctly, handled_incorrectly, events`); anything else on
   the source scoreboard is silently dropped. Called at
   `coach_play.py:7245` on game completion, where the rebuilt dict
   **replaces** the entire `mission_scoreboard` field via
   `db.coach_sessions.update_one(..., {"$set": update_fields})`
   (line 7253-7256) — confirmed this would erase any field (e.g.
   `instruction_id`) added only at session creation. **§3 makes
   preservation through this path an explicit requirement.**

4. **A real, documented "one experiment at a time" policy exists, and
   Universal Habit Coach is an ACTIVE experiment right now — confirmed,
   and more concrete than the original critique stated.**
   `docs/experiment_01_habit_coach_scaleup_preregistration.md`: status
   "ACTIVE, 2026-08-06," explicit cohorts (A: 8 existing untouched: B:
   next 12-15 new first-assignments, randomized; C: everyone else,
   untouched), explicit exclusion of internal/admin accounts (§5). The
   standing policy — "ChessGuru runs exactly ONE active
   product-learning experiment at a time, unless two experiments are
   proven orthogonal" — is documented there and cross-referenced in
   the Decision Log, Research Ledger, and Launch Readiness Report.
   Existing flags (`PWC_COACH_BLUNDER_GUARD`, `PWC_SKILL_GATE_ENABLED`)
   confirm the real rollout pattern: default-off in code, flipped on
   in `docker-compose.yml` only after validation, each with an inline
   kill-switch comment. One correction to the original critique's
   phrasing: the existing pattern is "exclude internal/admin accounts
   from the cohort," not a separate "validate on internal users first"
   step — those are the same mechanism, not two. §3/§4/§7 below use the
   precise version.

**Corrections #6-7 (from v2's review, each independently re-verified):**

6. **Canonical ownership must be `user_active_focus`, not session-to-
   session chaining — confirmed as a real risk, not just a style
   preference.** v2's §3 was ambiguous about where "the same
   instruction" for session N+1 actually comes from — read literally,
   it could mean "look at what session N said." That's dangerous
   given Sprint 1's own finding: **30% of PWC sessions get stuck
   unresolved** (`docs/product_residency_notes.md`). A chain built on
   session-to-session lookups breaks exactly in that population.
   Checked whether the raw material for a real `instruction_text`
   already exists: **it does.** `_CLOSING_BY_SUBTYPE`
   (`primary_weakness_picker.py:260-307`) is a static, per-subtype
   lookup of literal instruction sentences — e.g.
   `"simple_hang": "Before every move, ask: can this piece be taken?"`
   (line 267) — already used to build the closing line of
   `coaching_narrative` (line 731, via `build_narrative_from_evidence`,
   docstring line 345: "Closing = tier-aware line targeting the
   dominant meaningful subtype"). It's just never materialized as its
   own addressable field — it's baked into the end of the combined
   diagnosis+instruction paragraph. §3 below fixes this: `assign_focus`
   stores `instruction_text` (the `_CLOSING_BY_SUBTYPE` lookup,
   captured once at assignment) and `instruction_id`/`instruction_
   version` directly on `user_active_focus`, and every downstream
   consumer reads through `focus_bridge` fresh, never through a prior
   session document.

7. **Orthogonality ruling — population non-overlap is not sufficient.**
   Explicit product decision, not a code-verifiable claim: Sprint 2
   may only run behind its flag for internal/admin accounts while
   Experiment #1 is active — not any real-user cohort, including
   Cohort C. Reuses Experiment #1's own exclusion definition exactly
   (`docs/experiment_01_habit_coach_scaleup_preregistration.md:103`:
   `role in (admin, super_admin)`) rather than inventing a parallel
   allowlist — confirmed this is the same filter already used
   elsewhere in this codebase (e.g. Sprint 1's own funnel script).

**Decision: EXTEND, scope narrowed to match what's actually true.**
"Survives" is redefined to NOT require inventing new resolution
logic — it rides the existing 14-day `user_active_focus` lifecycle
exactly as built. Sprint 2 adds: a stable instruction identity **owned
by `user_active_focus`, not by session chaining**, subtype-aware
per-game feedback (reusing the existing subtype classifier), and a
rollout gated to internal/admin only until Experiment #1 concludes. It
does not add a new resolution mechanism, and it does not touch the
14-day loop's actual close/resolve logic.

---

## 1. What it is

Today, `user_active_focus` genuinely tracks one weakness for up to 14
days, and PWC genuinely reads it to build a session's goal and
greeting. But nothing keeps *the exact instruction text* stable across
that window, and nothing checks a given game's outcome against the
*specific* thing the player was told to do (only the general topic).
Sprint 2 closes both gaps: the instruction the player sees stays
worded identically for the life of the underlying 14-day focus, and
per-game feedback is honest about whether they did the specific thing
(not just "something piece-safety-related").

## 2. What the user sees

**Session N greeting** (new `user_active_focus` just assigned):
> *"Today I want you to check what changed after every opponent move
> before you decide — that's costing you games right now."*

**Session N postgame — per-game feedback, NOT a focus-resolution
claim:**
> *Followed it: "You checked before moving all game — no simple hangs
> today. Same instruction next time, let's see it hold."*
> *Didn't: "You hung a piece on move 14 without checking first. Same
> instruction again."*

**Session N+1 greeting** (same `user_active_focus`, still `status:
active`, `locked_until` not yet passed):
> *"Last game I asked you to check what changed after every opponent
> move. That's still your instruction today."*

**When the 14-day loop actually resolves the focus** (existing
mechanism, untouched by this scope — `focus_outcome_loop` sets
`status: completed`, `resolution: improved`, or similar):
> Next session's greeting naturally reflects the newly-assigned focus,
> because `focus_bridge` already reads the current `user_active_focus`
> document — no new logic needed here, this already works today.

The instruction's wording survives; the outcome verdict is honest
about "did you do the specific thing" without pretending to close out
the focus itself.

## 3. In scope (V1)

- **Canonical instruction fields live on `user_active_focus`, written
  once by `assign_focus`** (per Correction #6): `instruction_id`
  (simplest option — reuse the `user_active_focus` document's own
  `_id`, already a unique key for exactly one weakness-assignment
  cycle; no new id scheme needed), `instruction_text` (materialized
  from `_CLOSING_BY_SUBTYPE[dominant_subtype]` at assignment time —
  not looked up dynamically on every read, so a future edit to the
  template's wording doesn't retroactively change an already-assigned
  instruction), `instruction_version` (a version stamp on the
  `_CLOSING_BY_SUBTYPE` template content, incremented when that
  content is edited, so a specific instruction's exact historical
  wording is always reconstructable).
- **`focus_bridge.get_active_focus_bundle` exposes these 3 fields** in
  its returned bundle, alongside the existing `topic_key`/
  `dominant_subtype`/`topic_label`.
- **Every PWC session stores an immutable snapshot, not the source of
  truth**: at session creation, the session document records the
  `instruction_id`/`instruction_text`/`instruction_version` it was
  given, for historical evidence ("this session showed this exact
  wording") — but this snapshot is never read back by a later session
  to determine the current instruction.
- **The next session reads the active focus, not the previous
  session**: `session_greeting_service.py` calls `focus_bridge` fresh
  at every session start. If `user_active_focus` hasn't changed, the
  same `instruction_id`/`text` come back naturally — no cross-session
  lookup, no dependency on the previous session document existing,
  being complete, or having resolved cleanly. This is what makes the
  chain immune to the 30%-of-sessions-abandoned problem: an abandoned
  session N doesn't affect session N+1's ability to get its
  instruction, because N+1 never looks at N for that purpose.
- **The previous session is consulted only for outcome-context
  phrasing** ("last game you followed it") — reading the prior
  session's own `mission_scoreboard.handled_correctly`/
  `handled_incorrectly` counts, never its instruction fields. If the
  prior session is missing or malformed, this degrades gracefully:
  the greeting omits the outcome-context line rather than failing.
- **Preserve the canonical fields through every stage explicitly**
  (per Correction #3): `user_active_focus` (source) → `focus_bridge`
  (exposes) → session creation (snapshot) →
  `rebuild_scoreboard_from_history()` (must be extended to carry
  `instruction_id`/`instruction_text`/`instruction_version` through
  its rebuilt dict, not just the existing 7 keys) → the
  `coach_play.py:7245` persistence write → API response serialization
  → frontend rendering (`session_greeting_service.py`,
  `PostGameReflection.jsx`) → `pwc_insight_shown` analytics props. An
  end-to-end test asserting the value survives every stage is a ship
  requirement, not optional.
- **Subtype-aware per-game feedback — narrowed during implementation,
  real data checked first (per Correction #2, refined):**
  `_classify_piece_safety_subtype()` itself cannot run in this call
  path — it needs `opponent_previous`/`opp_next` ("did the opponent's
  prior move create a threat"), which comes from post-game batch
  analysis and doesn't exist in PWC's live `move_history`. Only one of
  the 5 piece_safety subtypes is genuinely board-verifiable from a
  single move in isolation: **`simple_hang`**, via the existing,
  validated `_piece_is_hanging_after_move()` (SEE-based, real reuse,
  no new detection logic). Checked the real distribution before
  deciding whether this is even worth shipping: among the 43
  currently-active piece_safety focuses, `tactical_seq_loss` (needs
  opponent-threat context, NOT verifiable here) dominates 70% (30/43);
  `simple_hang` (verifiable) is dominant only 19% (8/43). **Decision:
  ship simple_hang matching anyway** — zero regression risk (every
  other subtype keeps today's topic-level matching, unchanged), real
  reuse of a validated detector, and the right foundation once
  opponent-threat tracking exists for the dominant subtype. Real
  near-term value is narrow (~19% of piece_safety sessions,
  internal/admin-only besides), consistent with the rest of V1's
  honestly-small rollout. `threat_ignored`/`tactical_seq_loss`/
  `quiet_blunder`/`small_slip` matching is explicitly deferred, not
  silently dropped — a real scoped follow-up, not this scope's problem
  to solve by inventing an unverified opponent-threat proxy (this
  project's own standing lesson: wrong teaching is worse than no
  teaching, the exact reason `ChessBrain` was disabled).
- **"Survives" redefined precisely** (per Correction #1): an
  instruction survives for exactly as long as its underlying
  `user_active_focus` document is `status: active` — i.e., until the
  existing, untouched 14-day `focus_outcome_loop` closes it. Per-game
  success/failure (subtype-aware feedback above) is informational
  feedback to the player and does NOT write to `user_active_focus.
  status`/`resolution`, and does not shorten or extend
  `locked_until`. This scope adds zero new resolution logic.
- **Rollout gating — Correction #7, exact ruling, not a risk to
  manage:**
  - New feature flag, default OFF, naming convention matched to
    existing flags: `PWC_SURVIVING_INSTRUCTION_ENABLED`.
  - While Experiment #1 is active, this feature may run **only** for
    accounts with `role in (admin, super_admin)` — the exact filter
    already defined in `experiment_01_habit_coach_scaleup_
    preregistration.md:103`. Not "excluded from Habit Coach's cohorts"
    (v2's framing) — **blocked for every real user regardless of
    cohort**, including Cohort C ("business as usual, untouched").
  - **Server-side gating before instruction selection, rendering, or
    telemetry** — the eligibility check happens before any Sprint 2
    logic runs at all (not just before its output is shown). A
    non-eligible user's session should not compute
    `instruction_id`/`instruction_text`, not merely hide them.
  - No behavioral conclusions of any kind are drawn from
    internal/admin-only data — that population validates correctness
    (does the mechanism work, does data persist correctly), not
    product impact.
  - A separate rollout/preregistration decision is required after
    Experiment #1 reaches Success, Failure, or Inconclusive — this
    scope does not pre-authorize real-user rollout at any future date.
  - `pwc_insight_shown`'s new props include flag-state and
    eligibility, so who saw what is auditable after the fact.
  - **Test requirement**: with the flag ON, a real (non-admin,
    non-super_admin) user's session must be byte-identical in
    behavior to the flag being OFF — proving the gate actually gates,
    not just that it's documented to.
- V1 covers **piece_safety only** (Mohit-approved boundary, unchanged).

## 4. Explicitly out of scope (V1)

- A new coaching-memory collection.
- A parallel focus selector alongside `user_active_focus`.
- Another mission engine.
- Any change to the 14-day `focus_outcome_loop`/`check_focus_outcome`/
  `close_focus` resolution logic itself.
- Any change to Universal Habit Coach or its active cohorts (A, B) —
  this feature is excluded from those users entirely, not merely
  "not applied to."
- New entries in `pattern_catalog.json`.
- Reviving `user_teaching_memory`.
- Extending the mechanism to cognitive gap types other than
  piece_safety.
- **Any causal claim about carried-forward vs. fresh instructions.**
  Per the review: this comparison is descriptive/correlational only in
  V1 — there is no controlled assignment, so it cannot establish that
  carrying an instruction forward *causes* better resolution. It's
  logged for a future, properly randomized read, not reported as a
  finding from V1 data.
- **Any rollout to real users, including Cohort C, while Experiment #1
  is active** (Correction #7) — a hard gate, not a risk to manage.
  Internal/admin-only (`role in (admin, super_admin)`) until Experiment
  #1 closes with a Success/Failure/Inconclusive verdict.
- **Any behavioral or product conclusion drawn from internal/admin-only
  data.** That data validates mechanism correctness, not user impact.
- **Deciding the post-Experiment-#1 rollout plan now.** That's an
  explicit separate decision point, not something this scope
  pre-authorizes.

## 5. Success criteria

- **Persistence integrity (must be 100%, checkable directly against
  stored data):** for every session with `is_carried_forward=true`,
  the session's snapshotted `instruction_id`/`instruction_text` match
  what `user_active_focus` (via `focus_bridge`) actually held as
  canonical at that session's start — checked against the source of
  truth, not against the prior session's snapshot (Correction #6: the
  prior session is never the thing being verified against). (Also
  corrected per review: not "byte-identical greeting" — the
  surrounding sentence in the greeting can vary naturally; only the
  canonical id/text must match.)
- **Reconciliation correctness:** 100% of subtype-aware per-game
  feedback checks use the session's own `focus_topic`/`focus_subtype`,
  never an independently-derived value.
- **Rebuild-path preservation:** 100% of sessions where
  `rebuild_scoreboard_from_history()` runs post-creation still have
  `instruction_id`/`instruction_text` present afterward — the specific
  regression Correction #3 identified.
- **Rollout gate (hard requirement, per Correction #7):** 0 real
  (non-admin, non-super_admin) users ever execute Sprint 2 logic —
  selection, rendering, or telemetry — while
  `PWC_SURVIVING_INSTRUCTION_ENABLED` is on and Experiment #1 is
  active, verified server-side, not just by hidden UI. This includes
  Cohort C, not only Habit Coach's A/B cohorts.
- **Gate-effectiveness test (must pass before ship):** a real user
  with the flag ON behaves byte-identically to the flag OFF —
  proving the gate blocks execution, not just output.
- **Deferred, explicitly not a V1 deliverable:** carried-forward vs.
  fresh resolution-rate comparison. Cannot be attempted meaningfully
  on internal-only data (too small a population, not representative)
  and is blocked entirely until a separate rollout decision is made
  after Experiment #1 closes.

## 6. Open questions

**Resolved since draft v2 — real query run against `coach_sessions`
(2026-08-07):**

> What % of real PWC sessions currently have no `focus_topic` set on
> `mission_scoreboard`?

**5% of all-time sessions have it (21/460); 95% don't.** Among the 60
real recent signups from Sprint 1's funnel, only 1/28 first sessions
(4%) had it, even though 19/60 of those users actually clear the
`>=10 analyzed games` eligibility bar. This is consistent with, not
contradictory to, everything above: `assign_focus` runs once daily via
cron, gated on analyzed-game count — a user's very *first* PWC session
routinely happens before they've accumulated 10 analyzed games or
before that night's cron run, so `mission_scoreboard` being `None` on
a first session is close to the expected default, not a fallback
failure. **Scope implication, not previously stated:** this feature is
inherently a session-2-or-later phenomenon for most users, and even
then, current real-world reach is ~5% of sessions — not because
anything is broken, but because the eligibility gate + once-daily
assignment cadence are genuinely narrow today. V1's success criteria
(§5) should be read against that real population size, not an assumed
"most sessions" volume. Subtype-aware feedback correctly does nothing
(not fire, not error) when `mission_scoreboard` is `None` — no new
fallback path needs building, the existing `if focus_bundle and
focus_bundle.get("topic_key")` gate (`coach_game_session.py:352`)
already handles this.

**Resolved — explicit ruling, not a code question:** population
non-overlap with Habit Coach's cohorts is **not** sufficient.
Internal QA is not a second product-learning experiment, so no
orthogonality exception is needed or claimed — Sprint 2 simply doesn't
touch real users at all (any cohort) until Experiment #1 concludes.
See Correction #7 and §3/§4/§5 above.

**Resolved since draft v2 — read `scripts/assign_focuses.py:75-80` and
`primary_weakness_picker.py:748-784`:**

> Can an in-flight instruction get silently superseded mid-cycle?

**No — this can't happen today.** The daily cron script explicitly
checks `find_one({"user_id": uid, "status": "active"})` first and
skips any user who already has one (confirmed in its own log: "already
had active focus: 51" of 52 seen). `assign_focus` is only ever called
for a user with zero active focus docs — either brand new, or their
previous one was just closed by the 14-day `focus_outcome_loop`. The
system is naturally serialized (closed → next day's cron → reassigned),
so no "superseded" state needs building in V1 — it's a real scenario
that just doesn't occur given how the picker is actually gated.

## 7. Pre-code requirements

- [x] Real query run against `coach_sessions` for missing-`focus_topic`
      rate — resolved above (5% all-time, 4% of recent first sessions;
      expected given eligibility gate + cron cadence, not a bug).
- [x] Orthogonality question resolved — explicit ruling, not
      confirmation-pending: internal/admin only until Experiment #1
      concludes, no exception claimed.
- [x] `primary_weakness_picker.py` reassignment-cadence read — resolved
      above (cannot happen mid-cycle; picker skips users with an
      already-active focus).
- [x] End-to-end persistence test plan agreed and implemented —
      `backend/tests/test_one_surviving_instruction.py` (18 tests,
      passing): canonical fields survive `rebuild_scoreboard_from_
      history` (the exact Correction #3 regression), the postgame
      endpoint and `session_greeting_service` both read fresh from
      `focus_bridge` per Correction #6. Full `test_all_flows.py`
      (33/33) reconfirmed passing, including live "Start game"/"End
      game" against the project's designated test account.
- [x] Gate-effectiveness test written and passing (flag ON + real user
      = byte-identical to flag OFF) before ship — see §5. 8 dedicated
      tests in `TestGateEffectiveness`, including the literal
      byte-identical-bundle assertion and confirmation the gate isn't
      vacuously always-off (admin+flag-on genuinely gets real fields).
- [x] Mohit has explicitly signed off on this full scope document
      (2026-08-08).
