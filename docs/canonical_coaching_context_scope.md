# Canonical Coaching Context — Scope

**Status:** LOCKED — MOHIT APPROVED 2026-08-28  
**Rollout:** `COACHING_CONTEXT_V1_ENABLED=false` by default

## 0. Existing surfaces audit

### Confirmed current ownership

- Mongo `user_active_focus` owns the current weakness focus and its immutable
  instruction fields.
- `backend/services/focus_bridge.py:get_active_focus_bundle()` is already
  documented as the sole designated reader and applies detector authorization
  plus instruction rollout eligibility.
- PIC extends that bridge with evidence provenance and honest outcomes.
- Coach Play already reads the bridge at session start and snapshots the
  instruction into its mission scoreboard.

### Confirmed parallel readers

- `GET /api/coach/active-focus` directly re-queries `user_active_focus`, owns a
  second label table and calculates legacy trend/day state itself.
- `focus_resolver.get_active_focus()` uses the bridge only when detector
  enforcement is enabled; otherwise it can select `coach_memory.current_focus`
  or aggregate problems.
- routed Game Review (`LabV2 → GameDecryptionV5`) fetches
  `/cognitive/training-priority`, while its move badges independently display
  every detected topic.
- Training paths consume a mix of `focus_resolver`, direct Mongo queries and
  cognitive weaknesses.
- Home and Coach Play already contain partial PIC/instruction integrations but
  do not share one versioned presentation payload with Review and Training.

### Decision

**EXTEND `focus_bridge`; REPLACE the four surfaces' alternate coaching-priority
selection behind one flag.** Do not create a new focus picker, collection,
taxonomy, instruction generator or mastery engine. Legacy endpoints remain as
flag-off compatibility until the migration reaches 100% and stays clean.

## 1. What it is

A versioned coaching-context contract answers one question for every core
surface: “What is this player working on, what exact instruction survives, what
supporting issues may the coach mention, what evidence is honest, and what is
the one next action here?”

It contains one primary focus and a bounded set of supporting focuses. The
primary focus owns the surviving instruction and outcome plan. Supporting
focuses let the coach behave naturally when another important issue appears;
they do not compete for the main CTA or publish independent improvement claims.

## 2. What the user sees

### Home

```text
YOUR MAIN FOCUS
Before every move, ask: can this piece be taken?

Also watching: king safety · using your clock
[ Practise this check ]
```

### Game Review

```text
Your focus showed up twice in this game.
Move 18: the bishop landed where Black could take it safely.

Also worth noticing: your king stayed in the centre.
[ Replay the focus decision ]
```

If the focus did not appear:

```text
This game did not give us a comparable focus decision.
That is not proof that the problem is fixed.
[ Review the most useful moment ]
```

### Training

```text
TODAY'S ASSIGNMENT
3 positions for your current check
Before every move, ask: can this piece be taken?

[ Start assigned practice ]
```

### Coach Play

```text
Same instruction as last time:
Before every move, ask: can this piece be taken?

I may also point out king safety when it matters.
[ Start coached game ]
```

No-focus state is explicit: “I need enough verified games before choosing your
main focus.” User-requested learning such as the Italian Opening appears as an
elective, not as evidence that the coach changed the diagnosed focus.

## 3. In scope (V1)

- One `coaching_context.v1` builder extending `focus_bridge` and reusing PIC,
  detector authorization and concept-mastery projections.
- One authenticated API response used by Home, routed Game Review,
  Prescribed Training and Coach Play setup/session creation.
- Stable core fields: schema version, focus/instruction identity, primary focus,
  supporting focuses, evidence state/provenance, learner projection, typed next
  action and rollout/eligibility state.
- Surface-specific adapters may add game move references or CTA shape, but may
  not choose or rewrite the focus/instruction.
- Primary focus comes only from authorized active `user_active_focus` through
  `focus_bridge`.
- Supporting focuses come only from authorized evidence already attached to
  that focus (`runners_up`) and are visibly secondary.
- Game Review ranks/highlights moves matching the primary instruction first,
  then supporting issues; it may still explain game-deciding issues outside
  both when chess truth requires it.
- Training receives one assigned activity. Optional alternatives remain
  bounded and must be stage-appropriate.
- Coach Play snapshots the same context/instruction IDs for evidence but reads
  the current context fresh at the next session.
- Context IDs are attached to analytics and evidence envelopes; no PGN or
  private coaching text enters PostHog.
- Flag-off behavior is byte-for-byte compatible with current consumers.

## 4. Explicitly out of scope (V1)

- A new focus picker, recommendation model, detector or taxonomy.
- Multiple primary instructions or separate improvement verdicts for supporting
  focuses.
- LLM selection or rewriting of the surviving instruction.
- Opening/endgame curriculum redesign; a player-requested elective is only
  represented, not taught by this contract.
- Replacing PIC evidence rules, concept mastery or detector quality gates.
- Redesigning every legacy page that uses the word “focus.” Only the four core
  surfaces migrate in V1.
- Automatic production rollout or deletion of compatibility paths.

## 5. Success criteria

- One snapshot test proves all four surfaces receive the same primary focus ID,
  instruction ID and literal instruction text for one user state.
- No surface can promote an unauthorized detector output into primary or
  supporting focus.
- Review prioritizes a matching focus move when one exists and explicitly
  reports insufficient focus evidence when none exists.
- Training's assigned activity and Coach Play mission carry the same
  instruction ID as Home.
- Supporting issues never replace the main CTA and never generate “fixed,”
  “improved” or “mastered” language independently.
- No-focus, flag-off, ineligible-role, stale-focus and partial-data states render
  safely without falling back to a rival priority source while flag-on.
- Analytics can join context-view/next-action events by schema and instruction
  ID without private text.
- After two clean weeks at 100%, the four migrated alternate selectors are
  deleted and contract tests prevent their return.

## 6. Open questions

- **How many supporting focuses may be visible at once?** Locked for V1 at one
  contextual supporting focus. See
  `docs/coaching_context_support_cap_data_lock_2026_08_28.md`.
- **Should a requested elective appear in the core response or a separate
  `elective` object?** Recommendation: separate object so it cannot impersonate
  a diagnosed priority.
- **When a game-deciding issue conflicts with the active focus, what leads the
  review narrative?** Recommendation: chess truth leads the story; the active
  focus remains the first explicit practice connection.
- **Which existing Home focus component becomes the only flag-on renderer?**
  `HomePageNew` already has PIC-aware copy, while older `FocusCard` and
  `FocusResolutionBanner` still render legacy trend claims.
- **Does Coach Play fetch the API or call the builder server-side?**
  Recommendation: builder server-side at session creation; the browser must not
  become the authority for session evidence.

## 7. Pre-code requirements

- Mohit signs off this scope and the matching technical spec.
- Data-lock the visible supporting-focus cap with a pre-registered comparison.
- Freeze `coaching_context.v1` JSON examples for primary-only,
  primary-plus-supporting, no-focus, PIC-eligible and insufficient-evidence
  states.
- Inventory every flag-on read in the four surfaces and name the exact legacy
  path it replaces.
- Confirm Review's game-specific move matching uses existing authorized move
  observations; no new classifier is added.
- Enumerate unit, contract, cross-surface snapshot, authorization, flag-off and
  browser E2E tests before implementation.
- Rollout remains subordinate to the one-active-experiment policy.
