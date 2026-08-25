# Learning Experience System — Canonical Architecture

**Status:** CANONICAL SHARED AUTHORITIES v1.2 — PIC reuse approved 2026-08-25; knight-fork delivery remains queued  
**Date:** 2026-08-24  
**Scope authorities:** `learning_experience_system_scope.md` v3.2 and `pattern_learning_system_scope.md` v4.4 (fork content only)

This note defines the shared learning authorities without creating another lesson engine,
subject detector, or learner-facing mastery system. PIC inherits the subject-agnostic contracts;
fork-specific content, grading and cohort delivery remain queued. This is an implementation
contract, not permission to start runtime code. All open gates in the active PIC scope still apply.

---

## 1. Decisions

1. `/training` remains the learning host. V1 does not add an Academy, catalog, or new top-level
   product destination.
2. `backend/services/teaching_engine.py` owns the lesson lifecycle vocabulary. It is extended from
   move-only Play With Coach lessons to generic learner interactions; it is not replaced.
3. `backend/services/concept_mastery_service.py` owns every learner-facing state and next-step
   projection for migrated skills.
4. `multi_target_attack_evidence` plus `is_named_fork()` remain the canonical, piece-agnostic fork
   truth and promotion rule. V1 filters that evidence to a knight attacker; it creates no
   `knight_fork_detector`.
5. The runtime records immutable evidence events. Mastery, lesson completion, analytics, and UI
   cards are projections of that evidence, not competing writes to separate progress stores.
6. Raw positions remain in their existing source systems. A reviewed content-manifest entry points to its
   source and freezes the teaching contract for a content version; it does not become another
   puzzle corpus.
7. V1 creates no standalone learning-event collection or analytics service. The lesson's append-only
   event stream lives inside its resumable session, following the existing mission-session pattern;
   selected analytics projections use the existing `CoachAnalyticsService`.

---

## 2. Existing paths and why they are not the new authority

| Existing path | Finding | V1 disposition |
|---|---|---|
| `backend/services/teaching_engine.py` + `coach_sessions` | The dispatcher has the correct `start / process / exit` lifecycle but is coupled to Play With Coach session storage and move interactions. | Extend the lifecycle contract and add a storage boundary. Keep `coach_sessions` for Play With Coach. |
| `backend/coach_engine/teaching_engine.py` | Despite the name, this is a move-coaching rule orchestrator, not a lesson lifecycle dispatcher. It is live in blunder intelligence and Play With Coach integration. | Legitimate separate concern. Do not import, rename, or extend it for the learning runner. Always use the fully qualified `services.teaching_engine` path in lesson code. |
| `PrescribedTraining.jsx` | It is the canonical route host, but its puzzle cursor, reveal, solved count, and completion are local React state. A refresh loses the journey. | Keep the route and page shell. Replace the migrated fork branch with a resumable lesson runner. |
| `EndgameLesson.jsx` | Already has the clearest `INTRO / TRY / CORRECT / WRONG / COMPLETE` interaction shell, arrows, retry, and completion. | Extract or extend its phase-machine and board interaction components; do not rebuild those screens. |
| `diagnostic_sessions` | Already persists assigned items, attempts, the current item, completion, and resume across visits. It is keyed to a diagnostic staircase and diagnosis writes. | Reuse its persistence and resume patterns, not its diagnostic collection or domain fields. Add shared session primitives only where extraction is cheaper than copying. |
| `mission_sessions` | Already embeds ordered interaction events and tracks pause/active time, but two live mission services use incompatible document shapes in the same collection. | Reuse the embedded-event and active-time patterns. Do not add a third polymorphic mission schema or use it for lessons. |
| `deep_sessions` and `opening_practice_sessions` | Already persist a current step, status, move history, hints, completion, and resume-like retrieval for their own flows. | Reuse tested transition and persistence patterns. Their domain collections remain unchanged. |
| `puzzle_attempts`, `training_attempts`, and `training_solve_attempts` | Record variants of puzzle correctness and timing, but not the full ordered chain of stages, help, reveals, form assignment, content version, pause/resume, and delayed recall. | Keep for unmigrated flows. Do not dual-write migrated fork evidence into them. Existing consumers receive derived compatibility views only if required. |
| `learning_checkpoints` | Stores active-recall-specific ranking and concept responses. | Keep as legacy active-recall evidence. Do not repurpose it as the generic lesson ledger. |
| `mistake_cards` and `user_habit_progress` | A separate daily-card mechanism with no live content population demonstrated by the audit. | Do not revive it for V1. |
| `coach_sessions` | A live Play With Coach aggregate with board and move history. | Application evidence may reference it; standalone learning sessions do not write into it. |
| `coach_analytics` + `CoachAnalyticsService` | An existing append-only coaching event logger and collection. It already records lesson assignment and deep-session lifecycle events, but has no idempotent, content-versioned evidence contract. | Extend it only for derived product analytics that reference a canonical session event. Do not build another analytics service or treat analytics rows as mastery truth. |
| `diagnostic_pool` + `build_diagnostic_pool.py` | Already advances the Lichess setup move, filters fork positions, rating-bands them, runs MultiPV/engine gates, and stores source provenance. The builder currently wipes/rebuilds the pool and has too few fork items for matched forms. | Reuse its candidate preparation and engine-gate code for assessment authoring. Seed from existing fork rows; do not create a second Lichess selector. Human review and frozen lesson roles live in a thin manifest so pool rebuilds cannot erase them. |
| Existing caption authoring/reviewer UI | Already provides reviewer authorization, queue navigation, approve/reject/skip states, editing, and keyboard workflow. Its documents are caption-specific. | Reuse reviewer role checks, state-machine conventions, and UI components. Do not force lesson assets into caption collections and do not build a second reviewer identity system. |
| `backend/data/coaching/skill_tree.json` + `concept_mastery_service.py` | The existing curriculum identity and learner-facing mastery surface. | Add the migrated fork skill there so all progress surfaces use the existing identity and projection path. Do not create a parallel lesson catalog for mastery. |
| `lesson_resolver.py` and `lesson_key_mapping.py` | `lesson_resolver.py` is the live canonical game-to-lesson resolver; `lesson_key_mapping.py` repeats its registry and has no live importer in the repository audit. | Never add the fork mapping to both. Use `lesson_resolver.py` if game-to-lesson resolution needs it; separately consolidate the dead duplicate with a guard test. |
| `pattern_decay_service.py` | Describes weakness urgency and recent recovery. | May choose what to teach next. It never publishes knowledge or mastery. |
| Existing mastery trackers | Produce domain evidence or legacy labels from different stores. | May feed adapters. For a migrated skill, their labels are not shown and cannot override the canonical projection. |

The result is two—not three—narrow persistence gaps: a cross-source reviewed content manifest and a
standalone resumable learning session. The session contains its own append-only evidence stream.
Everything else extends or derives from an existing authority.

---

## 3. Canonical ownership map

| Concern | Canonical authority | Must not own |
|---|---|---|
| Lesson lifecycle | `backend/services/teaching_engine.py` | Chess truth, learner-facing mastery, content review |
| Fork geometry and naming | `multi_target_attack_evidence` and `is_named_fork()` in the canonical caption-facts path | Lesson stages, UI state, cohort decisions |
| Curriculum skill identity | Existing `backend/data/coaching/skill_tree.json` | Detector truth or reviewed position data |
| Reviewed lesson contract | Thin `learning_content_manifest` referencing existing source ids | Raw Lichess corpus, player profile, mastery |
| Resumable cursor, assigned forms, and immutable evidence stream | `learning_sessions` with embedded ordered events | Mastery labels, detector output, analytics conclusions |
| Learner-facing projection | `backend/services/concept_mastery_service.py` | Content authoring, detector truth, priority |
| Weakness urgency | `pattern_decay_service.py` | Knowledge or retention state |
| Raw generic and diagnostic candidates | Existing `lichess_puzzles` and `diagnostic_pool` documents | Human Gold status or lesson mastery |
| Raw personal application positions | `player_profiles.motif_profile.<motif>.got_positions`, after the approved recomputation | Lesson completion or user-visible mastery |
| Product analytics | Existing `CoachAnalyticsService`, containing derived references to canonical session events | Writing back mastery or changing content |
| Content review access/workflow | Existing reviewer role and authoring-review interaction patterns | Caption collections as lesson-content storage |

### One-way data flow

```text
existing Lichess / diagnostic / personal source + canonical fork evidence
                     |
                     v
        reviewed learning_content_manifest
                     |
                     v
services.teaching_engine -> learning_sessions
                              |           |
                              |           +--> embedded events (append only)
                              |                         |
                              |        +----------------+----------------+
                              |        v                                 v
                              | concept_mastery_service        experiment analysis
                              |        projection                        |
                              |                 derived references       v
                              +------------------------------> CoachAnalyticsService
                                       |
                          Home / Lab / Training / Play With Coach
```

There is no `learning_mastery` collection. A cached projection may be added only if profiling proves
it necessary, and then it must contain an event-watermark and be safely rebuildable from the ledger.

---

## 4. Persistence contracts

### 4.1 `learning_content_manifest` — reviewed cross-source contracts

This is a thin registry, not a duplicate puzzle database. It follows the existing caption-overlay
pattern: review data and approved role point at canonical content rather than copying the source.
One immutable manifest revision contains:

- `asset_id`, `lesson_id`, `content_version`, `revision`, and `status`;
- `source_type`: `diagnostic_pool`, `lichess`, `personal`, or `authored`;
- a stable source reference when the source exists elsewhere;
- a frozen source hash and the minimal proof needed to detect a changed source;
- allowed lesson roles: teaching example, counterexample, distractor source, assessment, or personal
  application;
- orientation, prompt type, accepted-answer contract, and canonical grader version;
- author, reviewer, review class (`Gold` or `Provisional`), timestamps, and review findings;
- provenance class and source-game reference where personal attribution is allowed.

For referenced content, the source document remains authoritative for the board and moves. Only a
genuinely authored counterexample or distractor with no existing source may store its FEN/moves in
the manifest. Different presentation shapes are derived at read time.

Gold requires a qualified reviewer different from the author. Provisional content is admin-only and
cannot affect mastery, calibration, or confirmatory analysis. An approved asset revision is never
edited in place; a semantic change creates a new revision and content version.

Assessment candidate generation first reuses `diagnostic_pool` fork rows and the candidate
preparation, Lichess setup-move handling, rating tiers, and engine gate in
`scripts/build_diagnostic_pool.py`. That logic is extracted or called; it is not copied. The timed
feasibility batch is a measurement artifact before this manifest exists. It must not be forced into
caption-authoring collections, because those collections review coaching prose, not lesson
positions, distractors, or assessment roles. The future review surface reuses the existing reviewer
role, queue controls, approval states, and UI components.

### 4.2 `learning_sessions` — resumable delivery state

One document per lesson attempt contains:

- `session_id`, `user_id`, `lesson_id`, `content_version`, and server-side rollout eligibility;
- cohort role (`admin`, `calibration`, `confirmatory`, or later `production`) and experiment id;
- assigned baseline/post/delayed form ids and counterbalancing assignment;
- current stage, item cursor, attempt state, pause/exit state, and recall due time;
- created, last-active, completed, and expired timestamps;
- last committed event sequence number for optimistic concurrency and idempotency;
- an embedded, append-only `events` array whose entries follow §4.3.

The session is delivery state only. It may say where the learner resumes; it never says `mastered`,
`remembered`, or `proven`.

The implementation reuses the proven shapes already present in `diagnostic_sessions` (assigned
items, attempts, current cursor, completion, resume), `mission_sessions` (ordered embedded events,
active-time handling), and `deep_sessions` (step transitions). It does not copy those functions
into a new parallel framework: shared primitives are extracted where safe and existing flows remain
regression-tested.

### 4.3 Embedded session events — the evidence ledger

Events are append-only entries inside the owning `learning_sessions` document and have a unique
`(session_id, sequence)` plus an idempotency key. Every event contains:

- `event_id`, `event_type`, `occurred_at`, `received_at`;
- `user_id`, `session_id`, `lesson_id`, `skill_id`, `content_version`;
- cohort and experiment identifiers;
- stage, checkpoint candidate, asset revision, source reference, form id, and form role;
- orientation and prompt type;
- response payload in a typed envelope, grader version, result, and accepted-answer reason;
- hint count, reveal state, attempt number, response time, and interruption/resume context;
- evidence eligibility plus explicit rejection reasons.

Required event types are:

`lesson_started`, `item_presented`, `answer_submitted`, `hint_requested`, `answer_revealed`,
`item_retried`, `stage_completed`, `lesson_paused`, `lesson_resumed`, `lesson_exited`,
`lesson_completed`, `assessment_completed`, `recall_scheduled`, `recall_completed`,
`application_opportunity`, and `application_result`.

Only the backend writes evidence eligibility. The frontend cannot claim completion or mastery.
Selected funnel/experiment summaries may also be logged through the existing
`CoachAnalyticsService`, always with the canonical `session_id` and event sequence. Those analytics
rows are derived observability, never the evidence authority.

---

## 5. Lesson lifecycle extension

`teaching_engine.py` keeps the canonical operations:

- `start_lesson(...)`
- `process_lesson_interaction(...)`
- `exit_lesson(...)`
- `resume_lesson(...)`

`process_lesson_move(...)` remains a compatibility wrapper for existing Play With Coach callers.
The engine receives a lesson definition and a session-store adapter. It does not directly choose a
Mongo collection. Existing Play With Coach lessons continue through a `coach_sessions` adapter;
the standalone runner uses a `learning_sessions` adapter and atomically appends its embedded events.

The engine owns state transitions and rejects illegal transitions. Lesson plugins own content-stage
rules and return typed grader results. Neither layer writes a mastery label.

### Walking-skeleton state path

The first admin-only slice proves this exact chain with stable identifiers:

`start -> present -> answer -> hint -> retry -> reveal -> stage complete -> pause -> resume ->
lesson complete -> schedule recall -> complete recall`

The skeleton may use Provisional reviewed content. Its events are marked ineligible for mastery and
experiments. A broken or discontinuous chain stops the build before a full lesson UI is added.

---

## 6. API and route contract

The existing `/api/training` router owns the standalone lesson API:

- `POST /api/training/lessons/{lesson_id}/start`
- `GET /api/training/lessons/sessions/{session_id}`
- `POST /api/training/lessons/sessions/{session_id}/interactions`
- `POST /api/training/lessons/sessions/{session_id}/exit`
- `GET /api/training/lessons/due-recall`

The interaction endpoint accepts a typed action such as board move, square selection, candidate
choice, hint, reveal, retry, or continue. The server derives the next state and emits events in one
atomic operation. A client retry with the same idempotency key returns the original result.

The frontend extends `PrescribedTraining.jsx` or extracts a shared runner beneath it. The canonical
entry remains `/training/pattern/fork`. Existing `/training/motif/fork` is redirected only after the
new route has parity and carries the same resumable session. Home and game review deep-link to that
same lesson id; they do not start separate journeys.

---

## 7. Content, grading, and evidence adapters

### Generic content

Lichess remains the raw source for rating-tagged generic positions. Existing curated fork rows in
`diagnostic_pool` are the first assessment-candidate source, and its builder's preparation and engine
gates are reused for expansion. A reviewed manifest entry pins a source and revision; the runtime
does not query a random live Lichess row after a session starts.

### Personal application

Personal Stage 8 reads only reviewed positions reconstructed from canonical, recomputed fork
evidence with exact provenance. Ambiguous provenance cannot support a personalized claim. The
lesson stage is optional and never grants internal checkpoint 8; it is guided role reversal, not
verified real-game transfer.

### Grading

All fork grading uses the canonical piece-agnostic evidence and shared promotion rule. Lesson-local
logic may filter attacker type, expected role, orientation, or review class, but may not duplicate
fork geometry. Alternative valid answers are accepted when the grader contract allows them. Exact
engine-move equality is not the default definition of understanding.

`puzzle_attempts`, active recall, gameplay detectors, and legacy mastery trackers may enter through
named evidence adapters. An adapter can emit evidence only when the fork evidence dictionary proves
semantic equivalence; sharing a motif name is insufficient.

---

## 8. Mastery projection

`concept_mastery_service.py` reduces eligible events from `learning_sessions` into:

- `current_demonstrated_checkpoint`;
- `highest_demonstrated_checkpoint`;
- learner state: `Learning`, `Remembered`, or `Proven in games`;
- optional `Refresh needed` modifier;
- concrete capability text and next recommended action;
- evidence timestamp and content version.

Home, Lab, Training, and Play With Coach consume the same projection. They may render it differently
but cannot translate it into a competing label. A failed delayed recall can lower current evidence
without erasing the highest historical checkpoint. Pattern decay can prioritize the lesson but
cannot overwrite this projection.

The exact reducer rules are defined in `fork_learning_evidence_dictionary.md` and must have fixture
tests before any UI publishes the states.

---

## 9. Content versioning and migration

1. A content version freezes asset revisions, stage rules, grader version, assessment forms, and
   analysis eligibility.
2. Cosmetic copy changes do not invalidate evidence when prompts, answers, hints, geometry, or
   difficulty are unchanged.
3. Any semantic change creates a new content version. Pending sessions remain on their frozen
   version or are explicitly invalidated; they never silently switch mid-session.
4. Historical puzzle attempts start as Not measured. They are not bulk-promoted by motif name.
5. A historical adapter may be added only after a documented equivalence audit against the evidence
   dictionary. Otherwise users can test out using unseen, reviewed content.
6. Migrated fork sessions write interaction evidence only to the embedded session ledger. Do not
   dual-write attempts or mastery into legacy trackers. Existing analytics and puzzle-progress
   consumers receive explicit derived views only when a real caller requires them.

---

## 10. Rollout and experiment isolation

Two backend-enforced flags default to false:

- `LEARNING_EXPERIENCE_ENABLED`
- `KNIGHT_FORK_LESSON_ENABLED`

Frontend visibility is never the security or experiment gate. The backend checks role/cohort on
start, resume, and every interaction. Rollout order is:

`off -> admin walking skeleton -> calibration cohort -> separate confirmatory cohort -> measured expansion`

Calibration users cannot appear in confirmatory analysis. Form assignment and cohort role are
persisted before the first item is shown. Assessment pools and analysis rules are frozen before the
confirmatory cohort. Experiment overlap must be explicitly resolved before enrollment.

No numeric threshold, cohort size, delay, tolerance, or stop boundary is selected in this note;
those remain subject to `/lock-via-data`.

---

## 11. Active-recall consolidation

The implementation phase must first make import ownership unambiguous:

1. keep `backend/services/active_recall_service.py`;
2. keep `backend/services/active_recall_integration.py`;
3. replace bare imports with canonical `services.*` imports;
4. verify all references;
5. delete the two root duplicates;
6. add a test that fails if either root duplicate returns or a bare import resolves it.

This is consolidation of identical code, not logic arbitration. It does not authorize changing
active-recall behavior or treating its `learning_checkpoints` rows as fork-lesson mastery.

---

## 12. Required tests before any cohort

- state-transition tests for every allowed and rejected lesson interaction;
- idempotent interaction and duplicate-event tests;
- atomic session-cursor plus embedded-event tests;
- pause/resume tests across process restart;
- content-version pinning and invalidation tests;
- canonical detector boundary tests, including royal forks and non-promoted raw geometry;
- accepted-alternative and reveal/hint evidence tests;
- evidence-reducer fixtures for all checkpoints, demotion, freshness, and test-out;
- role and cohort authorization tests at write time;
- calibration/confirmatory exclusion and counterbalancing tests;
- route-parity and redirect tests for the migrated fork route;
- a browser-level walking skeleton covering answer, help, completion, resume, and recall;
- the active-recall duplicate/import guard;
- a lesson-identity guard proving the migrated skill exists once in the curriculum and is not added
  to both `lesson_resolver.py` and its retired duplicate mapping;
- regression suites for current training and Play With Coach lesson lifecycles.

---

## 13. Blocking gates at the time of this draft

| Gate | State | Required unblock |
|---|---|---|
| Canonical architecture approval | Open | Mohit reviews and approves this note. |
| Fork evidence dictionary | Drafted alongside this note | Approve it and turn each rule into reducer fixtures. |
| Production fork recomputation and threshold refit | Open | Obtain authenticated database access, apply the approved recomputation by `_id`, verify zero illegal or unresolved rows, then `/lock-via-data` the boundaries. |
| Content feasibility | Open | Authoring operator: Codex. Mohit must name an independent qualified human reviewer; then time the complete 5 Gold + 2 counterexample + 15 distractor batch and assessment sample. |
| Numeric calibration | Open | Recruit a named calibration cohort, simulate coverage, collect first-attempt difficulty, form matched triplets, and freeze the rules. |
| Experiment isolation and operating owners | Open | Record overlap decision, rollback owners, and the separate orphan/defect owners required by scope. |

No runtime product code begins now. Items 1–7 in the signed Learning Experience scope must be
discharged before the admin walking skeleton; its items 8–10 must also be discharged before any
non-admin beta. The current audit is additionally blocked by the open fork recomputation and
data-derived boundary refit required before fork drill or personal Stage 8 content is served.
