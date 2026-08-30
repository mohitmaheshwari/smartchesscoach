# Personalized Curriculum Teaching — Pre-Code Audit

Date: 2026-08-30
Result: PASS

## Feature

Personalized Curriculum Teaching: one canonical chess lesson taught through a
student-specific evidence path, with honest independent, application, and
retention states.

## Gate evidence

### 1. Literal UI mockup — PASS

complete_chess_curriculum_scope.md contains the literal Coaching Plan and
lesson-stage mockups, including player-facing narrative, evidence, actions,
waiting states, and the Why explanation.

### 2. Pattern/geometry headline — PASS

The literal headline is “Make every defender count.” The player's move and
game are evidence beneath the concept, not the headline. The delivery contract
requires named squares, pieces, lines, defenders, and pawn shapes before
jargon.

### 3. Data-derived thresholds — PASS

complete_curriculum_learning_evidence_lock_2026_08_30.md cites the versioned
production snapshot and inherits the measured five-game eligibility floor,
three-occurrence repair rule, one-to-two occurrence expansion rule,
three-measured-game review cadence, and 21-day evidence-free check-in.

The feature adds no guessed graduation threshold. One distinct,
answer-hidden, unassisted, board-verified checkpoint may earn Can do alone
because that is an existing semantic state contract, not a new accuracy bar.
Reliable remains unavailable until clean delayed evidence supports a separate
data lock.

### 4. Behavior-changing success metric — PASS

The primary learning outcomes are:

- independent success on an unseen, answer-hidden position;
- successful transfer to a different-looking position;
- opportunity-normalized application in coached or organic games with the
  source preserved;
- later independent retention after intervening games;
- reduced assistance and misconception-specific correction.

Lesson views, card exposure, aggregate clicks, and pre-launch PostHog behavior
are not treated as learning success.

### 5. Deferred items remain deferred — PASS

V1 does not implement:

- a public Reliable state before the clean bake-off;
- an unlimited chat coach;
- deep theory primarily above 2000;
- a second Academy, profile, or mastery ledger;
- fixed learner types;
- LLM-authored chess truth;
- social rewards, certificates, or leaderboards;
- public rollout before final coach validation.

### 6. Explicit sign-off — PASS

Mohit approved all three recommendations in
personalized_curriculum_teaching_spec.md on 2026-08-30 and instructed the
implementation to proceed.

## Source-of-truth check

complete_curriculum_source_map_2026_08_30.md names the canonical curriculum
state, progression index, subject content, player evidence, and every known
compatibility migration. The implementation will:

- extend personal_curriculum.py rather than add a mastery engine;
- build a read-only teaching-profile projection rather than persist another
  profile;
- extend existing canonical subject sources rather than create a new concept
  catalog;
- use phase_principles.json as the promoted owner for cross-phase routines;
- migrate duplicate positional and endgame readers through parity-tested
  adapters.

## Verdict

PRE-CODE AUDIT: PASS

Proceeding to implementation behind PERSONALIZED_TEACHING_ENABLED=false.
