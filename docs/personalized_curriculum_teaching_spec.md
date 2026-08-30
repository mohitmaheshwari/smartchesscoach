# Personalized Curriculum Teaching — Spec

**Status:** APPROVED v1 — Mohit signed off on 2026-08-30.
**Version:** v1 (2026-08-30).
**Scope:** largest of the curriculum slices; multi-day to ship and verify.

---

## 1. The problem

ChessGuru can already choose a personal focus, remember recurring mistakes,
track skill progress, and serve verified opening, trap, endgame, and puzzle
content. The user correctly identified the remaining product failure: selecting
the right topic is not enough if the lesson itself reads like generic chess
knowledge.

The 2026-08-30 production audit found useful evidence but fragmented delivery:
59 profiles contain analyzed-game evidence, 58 contain ranked weaknesses, 65
coach memories contain skill progress, and 3,723 concept-understanding rows
exist. Yet only three of 69 profiles store a learning preference, and the live
teaching engine mostly varies generic questions by rating band.

The desired experience is one coach teaching one student. Chess truth remains
fixed; the example, vocabulary, question, help, correction, pace, and connection
to prior play change according to verified evidence about that student.

## 2. The shape — six outcomes

Architecture:

    canonical lesson + current position
                    |
                    v
      read-only teaching-profile view
                    |
                    v
       evidence-gated delivery decision
                    |
                    v
        existing generic teaching engine
                    |
                    v
       versioned learning-session events
                    |
                    v
       existing Personal Curriculum states

| Outcome | Player experience | Evidence result |
| --- | --- | --- |
| DIAGNOSE | “I do not know whether you missed the line or the defender. Show me what the knight protects.” | Records answer and supported misconception; makes no prior-history claim |
| PERSONAL_EXPLAIN | Starts from the player's own move, known prerequisite, repertoire, or prior confusion | Learning |
| TARGETED_CORRECT | Explains the exact missed defender, reply, geometry, or rule boundary, then gives a different retry | Learning or Can do with help |
| INDEPENDENT_PROOF | New answer-hidden position with no theme label or assistance | Can do alone only when board-verified and reasoning is consistent when requested |
| COACHED_OR_ORGANIC_APPLY | Creates or observes a real opportunity and labels the source | Coached application remains distinct; authorized organic evidence can earn Used in games |
| RETAIN_OR_REFRESH | Re-tests after measured games and returns a lapsed skill to the plan | Reliable remains unavailable until delayed evidence thresholds are data-locked |

The delivery contract always answers:

- Why this lesson for me?
- Why this explanation now?
- What did I prove?
- What remains unmeasured?

## 3. Schema / files touched

### Backend

- Add services/personal_teaching_profile.py as a read-only derived view. It
  joins current interaction, coach memory, concept evidence, active focus,
  repertoire, high-confidence identity, and broad understanding. It performs
  no writes.
- Extend services/personal_curriculum.py rather than creating another mastery
  service. LessonResult gains content version, evidence source, optional
  prediction/reason result, misconception, help action, and provenance.
- Generalize services/teaching_engine.py and the existing PIC learning-session
  path from piece safety to any verified canonical lesson.
- Extend services/curriculum_content_validator.py with counterexample,
  misconception-correction, independent checkpoint, primary-skill, and
  personalization-anchor validation.
- Extend routes/training.py with generic start, respond, help, pause, resume,
  and evidence endpoints while keeping the PIC endpoints as compatibility
  adapters during rollout.
- Extend routes/coach.py personal-curriculum response with the current teaching
  projection and evidence explanation.
- Extend data/coaching/skill_tree.json as an index only.
- Extend canonical subject records in data/theory/tactical_patterns.json,
  data/coaching/phase_principles.json,
  knowledge_base/strategic_imbalances.py,
  knowledge_base/pawn_structures.py, data/theory/opening_mistakes.json,
  data/opening_curriculum.json, data/traps.json, and
  data/coaching/endgame_theory_tree.json. Keep
  data/theory/positional_rules.json scoped to consequence wording. Do not copy
  lesson prose into the skill tree.

### Frontend

- Generalize components/training/PICPieceSafetyLesson.jsx into a reusable
  personalized lesson workspace; preserve the old component as a thin adapter
  until rollout is complete.
- Extend pages/PrescribedTraining.jsx to render Diagnose, Notice, Explain,
  Contrast, Guide, Recall, Mix, Transfer, Apply, and Retain stages.
- Extend pages/PersonalCurriculum.jsx and curriculum components with “Why?”,
  evidence source, honest Not measured, and resume state.
- Connect Play with Coach to the same delivery and evidence contract; it must
  not generate a parallel generic lesson.

### Stored event additions

Learning-session events add:

- schema_version and content_version;
- skill_id and primary_skill_id;
- stage and attempt_kind;
- assistance and requested_help;
- position_id, board_verified, and distinct_position;
- prediction or reason result when requested;
- supported misconception and corrective action;
- source_type: lesson, mixed_drill, coached_application, or organic_game;
- application opportunity and outcome;
- detector identity, version, and quality;
- evidence owner and reference.

No new player-profile or mastery collection is created.

## 4. New facts / data the system needs

Each exposed concept lesson needs:

- a concrete geometry-first explanation;
- prerequisites and known vocabulary;
- one guided example;
- one distinct independent checkpoint;
- one near-neighbor counterexample where the rule changes;
- supported misconception choices;
- a targeted correction and different reassessment position;
- one primary tested skill;
- use-it and defend-against-it treatment where applicable;
- legality plus engine, tablebase, or coach-verification evidence;
- content version and deprecation status.

The teaching-profile view needs no new inferred personality. It needs direct,
versioned evidence of what the player answered, which help was used, and what
worked on later transfer.

## 5. Gating — preventing fake personalization

1. **Evidence-anchor gate:** every personal claim resolves to owner and record
   reference. No reference means Diagnose or general truth, not invented history.
2. **Chess-truth gate:** adaptation cannot change legal moves, geometry,
   principle, counterexample, or grader.
3. **Current-answer precedence:** a player's present explanation outranks a
   stale global profile label.
4. **No learner-type gate:** visual/verbal/practice labels cannot permanently
   route teaching.
5. **Lucky-answer gate:** contradictory move and reasoning cannot earn
   independent proof.
6. **Attribution gate:** one position has one primary tested skill.
7. **Source gate:** coached application cannot become organic application.
8. **Reliable gate:** public Reliable promotion stays closed until the clean
   delayed-evidence bake-off.
9. **Generic-copy gate:** a lesson fails if the personalized introduction can
   be moved unchanged to an unrelated player.
10. **Jargon gate:** name squares, pieces, lines, defenders, and pawn shapes
    before specialist terms.

## 6. Test strategy

Phase 1 — stateless contracts:

- paired player histories produce different delivery but identical chess truth;
- missing evidence produces Diagnose;
- unsupported personal claims are rejected;
- hint/reveal never earns Can do alone;
- wrong reasoning blocks lucky-answer proof;
- Reliable cannot be constructed.

Phase 2 — backend boundaries:

- source resolution for every skill-tree record;
- no-write teaching-profile tests;
- owner/ref provenance;
- learning-session idempotency, ownership, pause/resume, and version migration;
- detector-quality and application-source boundaries.

Phase 3 — content and frontend:

- all player-visible records pass the extended offline content gate;
- component tests cover every teaching stage and help choice;
- Home, Learn, Training, Review, Progress, and Play with Coach show one state;
- production frontend build and focused backend suites pass.

Phase 4 — final human validation:

- Mohit and invited coaches test 600–900, 1000–1200, 1300–1500, and
  browse-first experiences;
- compare two evidence histories on the same lesson;
- flag generic wording, false personal claims, wrong chess, over-helping, and
  mastery overstatement.

## 7. Risk + rollback

Primary risks:

- fragmented profile evidence produces contradictory claims;
- personalized prose changes chess truth;
- the new workspace bypasses old lesson completion;
- legacy and new mastery labels diverge;
- a content expansion exposes incomplete lessons;
- too much questioning makes coaching annoying.

Rollout flag: PERSONALIZED_TEACHING_ENABLED=false by default. Eligibility also
requires PERSONAL_CURRICULUM_ENABLED and its role allowlist.

Rollback:

- set PERSONALIZED_TEACHING_ENABLED=false to return to the current verified
  lesson delivery while preserving append-only evidence;
- keep compatibility PIC endpoints and component during rollout;
- never delete or rewrite historical evidence during rollback;
- retire compatibility code only after the clean 100% period.

## 8. What this spec does NOT cover

- Public Reliable thresholds before clean delayed evidence exists.
- A general unlimited chat coach.
- LLM-authored chess truth or automatically published lessons.
- A second Academy, Learn page, player profile, or mastery ledger.
- Deep specialist content primarily above 2000.
- Paid packaging, certificates, leaderboards, or streak pressure.
- Using contaminated pre-launch behavior as an engagement baseline.

## 9. Implementation order

1. Land this spec, source map, evidence lock, and coverage matrix separately.
2. Add stateless teaching-profile and delivery contracts behind the default-off
   flag; no UI replacement.
3. Extend LessonResult and learning-session events with provenance and
   misconception evidence.
4. Generalize the existing PIC workspace and endpoints; keep compatibility
   adapters.
5. Extend and validate canonical concept content family by family. Migrate
   structure_plan_database.py through a parity-tested adapter instead of
   authoring another positional copy.
6. Wire Learn, Home, Review, Progress, and Play with Coach to the same state and
   delivery projection.
7. Ship default-off for Mohit and invited-coach A/B validation.
8. After a clean treatment window, lock rollout and rollback thresholds; do
   not use historical PostHog behavior.
9. Roll to 10%, monitor for one week, then 100% if the registered gates pass.
10. After two clean weeks at 100%, remove compatibility endpoints/components
    and any retired legacy delivery readers.

## 10. Approved decisions

1. **Player control over teaching form.** Recommended: show three lightweight
   choices when help is requested — “Show it on the board,” “Ask me one
   question,” and “Let me try.” Remember success per concept, not as a permanent
   global learner type.
2. **Initial content breadth.** Recommended: expose the adaptive workspace for
   all currently verified openings, traps, and endgames plus the first
   geometry/tactics/positional concept families that pass the extended gate.
   Do not wait for every recognition alias to become a separate lesson.
3. **Reliable visibility.** Recommended: do not render a locked Reliable badge.
   Show the highest proven state and “Real-game/retention evidence: not measured”
   inside Why. Add Reliable only after the clean bake-off.

Mohit approved all three recommendations on 2026-08-30. Phase 2 implementation
may proceed behind the default-off rollout flag.
