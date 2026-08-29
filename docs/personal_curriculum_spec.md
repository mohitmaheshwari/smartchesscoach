# Personal Curriculum — Spec

**Status:** PHASE 4 IMPLEMENTATION AUTHORIZED behind the default-off role gate;
representative-player and coach sessions remain final acceptance evidence.
**Version:** v1 (2026-08-28).
**Scope:** largest of the current learning rewrites; multi-day, phased migration.

---

## 1. The problem

ChessGuru already teaches openings, traps, endgames, tactical skills, principles, and recurring mistakes, but the player experiences separate products rather than one coach. Home recommends an action, Learn/Lab presents a skill tree plus game review, Study presents openings and endgames, Training presents several drill systems, and Play with Coach contains additional teaching modes. Mastery is described by several stores and vocabularies.

The signed-off product scope is `docs/personal_curriculum_scope.md`. Its audit found duplicated destinations, poorly exposed lessons, player-facing locks, questionable universal prerequisites, disconnected lesson completion, and a personal story dominated by repair rather than new knowledge.

The replacement must make a 600–1500 player able to answer: “What am I learning?”, “Why did my coach choose it?”, and “What do I do next?” without understanding ChessGuru’s internal taxonomy.

## 2. The shape — 6 curriculum outcomes

The Personal Curriculum is a composition layer over existing content and evidence. On each read it resolves the student into one primary outcome and, when justified, one short review.

| Outcome | When it applies | What the student sees | Next action |
|---|---|---|---|
| **OBSERVE** | Too little trustworthy evidence | “Let’s see how you naturally play.” | Diagnostic, import, or coached game |
| **REPAIR** | A demonstrated recurring problem deserves priority | “This keeps costing you. We’ll fix one part today.” | Existing personal lesson/drill |
| **EXPAND** | Student is ready for one new useful idea | “You’re ready to add this because…” | Teach → guided try → independent try |
| **CONTINUE** | An active lesson has not reached an independent attempt | “Last time you needed help. Let’s continue.” | Resume at the correct support level |
| **REVIEW** | Previously learned knowledge needs retrieval | “You learned this earlier. One position will keep it fresh.” | Short no-teaching-first recall |
| **APPLY** | Student can solve independently but lacks game evidence | “Now let’s use it in a game.” | Focused coached game or future-game watch |

The selector never emits a wall of equal recommendations. Candidate generation may consider many items; the player receives one primary item with a plain-language reason.

```text
Existing evidence owners
  recurring-focus evidence ─┐
  concept evidence ─────────┤
  opening evidence ─────────┤
  trap/endgame evidence ────┼─> curriculum composer
  lesson attempts ──────────┤       │
  diagnostic + rating ──────┘       ├─ primary outcome
                                     ├─ optional review
Canonical content registries ────────└─ route + lesson contract

Home / Learn / lesson / PWC / Progress all read the same composed decision.
```

Student-facing states are a translation, not a new score:

| Student state | Required evidence shape |
|---|---|
| **New** | No trustworthy attempt or application evidence |
| **Learning** | Explanation started or lesson seen |
| **Can do with help** | Correct only after a hint, correction, or guided line |
| **Can do alone** | Independent success on a distinct valid position |
| **Used in games** | Verified relevant opportunity with correct application |
| **Reliable** | Delayed independent recall plus repeated verified application; exact gates remain data-locked |

“Opportunity did not occur” and “evidence unclear” never advance the state.

Route ownership after migration:

| Route/surface | V1 ownership |
|---|---|
| **Home** | Coach conversation plus the single primary curriculum action |
| **Learn** | Canonical plan: learning now, review, naturally next, Explore |
| **Lesson route** | Shared lesson shell and resume behavior around existing interactive components |
| **Play with Coach** | Application environment for the active lesson |
| **Progress** | Evidence ledger; no competing next-lesson selector |
| **Game review** | Explains games and may nominate evidence/candidates; does not own curriculum |
| **Legacy Study/Training routes** | Detail destinations during migration, then redirected or nested under Learn |

## 3. Schema / files touched

No new chess-content database or independent mastery collection is permitted in V1.

### Canonical content ownership

- Openings: `backend/data/opening_curriculum.json`, read through `services/opening_unified_source.py`.
- Traps: `backend/data/traps.json`, read through `services/trap_library.py`.
- Endgames: `backend/data/coaching/endgame_theory_tree.json`, read through `services/endgame_theory_service.py`. `backend/data/endgames.json` remains a legacy adapter source only.
- Curriculum identity/prerequisites: `backend/data/coaching/skill_tree.json`, after invalid dependencies and content references are audited.
- Recurring repair identity: existing focus/concept sources remain authoritative; curriculum references their IDs.

### Existing evidence ownership

- `coach_memory.learning.skills`: Engine 2 skill attempts and learned lists.
- `user_concept_understanding`: concept opportunities, violations, clean evidence, and mastery history.
- `user_opening_progress` owns opening study participation; `user_opening_mastery` owns analyzed-game application. Curriculum composes them without merging their meanings.
- trap mastery/evidence: existing trap scanner and trap mastery tracker.
- `learning_sessions`: lesson-session completion evidence used by concept mastery.
- active focus/PIC records: recurring-repair selection and lifecycle.
- `user_learning_progress`: older aggregate learning summary; read-only legacy unless the ownership audit proves a required role.

### Planned backend changes
- Extend `services/today_composer.py` or extract its selection responsibility into one canonical curriculum composer; there must not be two selectors.
- Replace direct `engine2_skill_builder.pick_next_skill` use on player-facing paths with the canonical composed decision.
- Add one API response shared by Home and Learn containing primary outcome, optional review, reason, resume state, destination, and evidence summary.
- Add a lesson-result contract shared by opening, trap, endgame, concept, drill, and coached-play adapters.
- Extend existing memory only for active-plan continuity if measurement proves a derived plan cannot remain stable. It may store references and timestamps, never copied content or a second mastery verdict.

### Planned frontend changes
- `frontend/src/pages/HomePageNew.jsx`: consume the canonical curriculum decision.
- `frontend/src/pages/Dashboard.jsx`: replace the skill-tree-first Learn experience with the signed-off coaching-plan hierarchy.
- `frontend/src/components/Layout.jsx`: make navigation labels and active-route ownership consistent.
- Existing opening, endgame, skill-drill, and PWC pages/components: adopt the shared lesson entry/result/resume contract.
- `frontend/src/pages/UnifiedProgress.jsx`: render translated evidence states without selecting the next lesson.
- Legacy routes in `frontend/src/App.js`: remain reachable during A/B, then redirect according to the signed-off route map.

## 4. New facts / data the system needs

The composer needs normalized facts, derived from existing owners:

- evidence source and source record ID;
- skill/content ID and canonical content source;
- last explanation, guided attempt, independent attempt, and review timestamps;
- whether help was used and what kind;
- independent result on a distinct valid position;
- verified real-game opportunity outcome: applied, missed, did not occur, or unclear;
- active repair priority and its reason;
- lesson availability and board-verification status;
- destination capability: teach, guided practice, independent practice, review, or coached application;
- student rating band and confidence in that rating;
- stale/conflicting evidence flags.

The system also needs a reviewed V1 lesson manifest. This is an index of canonical IDs and capabilities, not copied lesson content. It may be generated from canonical registries; if persisted, a guard test must prove it is regenerable and complete.

Selection data is versioned in `backend/data/corpus_snapshots/personal_curriculum_selection_2026-08-28.json` and `backend/data/corpus_snapshots/personal_curriculum_review_opportunities_2026-08-28.json`, then locked in `docs/personal_curriculum_selection_data_lock_2026_08_28.md`. Evidence-personalized selection starts at 5 analysed games; repair starts at 3 occurrences of a named topic; evidence-led V1 topics require population support plus a lesson destination; evidence review follows 3 fully D_live-instrumented games; the 21-day backstop is a check-in, not a verdict; generic unnamed detections cannot name a lesson.

## 5. Gating — preventing the “new dashboard over fragmented truth” trap

1. **One-selector gate:** Home, Learn, and Today cannot call different next-skill functions.
2. **Evidence-owner gate:** the composer reads verdicts from evidence owners; it cannot infer mastery from labels, CTA completion, or missing opportunities.
3. **Content-owner gate:** lesson adapters reference canonical IDs; they do not copy names, moves, explanations, or prerequisites.
4. **Independent-attempt gate:** viewing an explanation or following a forced line cannot become “Can do alone.”
5. **Opportunity gate:** no real-game opportunity means no application credit and no failure.
6. **Detector-verification gate:** “Used in games” appears only for lesson types with audited opportunity detectors.
7. **Cold-start honesty gate:** sparse data produces OBSERVE or universal fundamentals, never fake personalization.
8. **Lock-UX gate:** rating/prerequisite guidance may affect recommendation order but cannot make educational content undiscoverable.
9. **One-voice gate:** internal labels such as Engine 2, skill ID, tier, gate, and mastery formula never reach student copy.
10. **Migration gate:** a legacy capability cannot be removed until its canonical Learn destination passes parity checks.

## 6. Test strategy

### Phase 1: stateless probes
- Feed synthetic student evidence into each outcome and snapshot the composed decision.
- Cover no data, conflicting evidence, stale evidence, urgent repair, active lesson, due review, and application-ready cases.
- Prove deterministic output for the same evidence and clock.
- Prove missing opportunity never advances state.

### Phase 2: boundary and ownership suite
- Guard that all player-facing selectors route through the canonical composer.
- Guard that every V1 content ID resolves through exactly one canonical source.
- Guard that every lesson adapter emits the shared result contract.
- Test rating boundaries without hiding Explore content.
- Test hint-assisted versus independent success.
- Test legacy deep links and redirect destinations.

### Phase 3: corpus and snapshot checks
- Run selector candidates on stratified 600–900, 1000–1200, and 1300–1500 users.
- Compare 2–4 repair/expand/review policies side by side before choosing one.
- Measure activation volume and empty-plan rate.
- Review the top decision and reason for real users; reject output that does not feel personally true.
- Snapshot Home, Learn, lesson, PWC handoff, and Progress states on desktop and mobile.

### Phase 4: human teaching review
- Mohit and Parth inspect complete sessions, not isolated cards.
- Moderated players answer: what, why, next.
- A chess reviewer validates every V1 lesson and application detector.
- Voice review covers 600, 900, 1200, and 1500 variants.

Required existing backend and frontend suites continue to run after every affected phase.

## 7. Risk + rollback

Primary risks:

- choosing the wrong lesson and weakening trust;
- merging incompatible mastery meanings into a false universal score;
- losing existing features during route consolidation;
- calling assisted success independent learning;
- false real-game application claims;
- a composer that is deterministic but monotonous;
- Explore becoming difficult to browse;
- Home and Learn drifting back into separate recommendations.

Rollout flag: `PERSONAL_CURRICULUM_ENABLED=false` by default. Frontend and backend must both treat missing/false as legacy behavior.

Rollback:

1. Set `PERSONAL_CURRICULUM_ENABLED=false`.
2. Existing Home, Lab/Learn, Study, Training, lesson, and Progress routes resume their legacy reads.
3. New writes, if any are approved, must be additive and safely ignored by legacy readers.
4. Revert the isolated implementation commit only if disabling the flag is insufficient.

No destructive migration or legacy-field deletion occurs before two clean weeks at 100%.

## 8. What this spec does NOT cover

- Authoring the complete 600–1500 curriculum.
- Premium entitlement and pricing.
- New chess detectors solely to make the first release look comprehensive.
- Replacing the recurring-mistake Personal Improvement Cycle.
- Social, classroom, leaderboard, or human-coach features.
- LLM-generated chess truth.
- Mastery thresholds, ranking weights, or rollout success thresholds beyond the locked three-game review and 21-day check-in cadence.
- Final visual design; this spec defines hierarchy, state, and ownership.
- Consolidating every historical opening/endgame service unrelated to V1 paths.

## 9. Implementation order

1. **Evidence audit only**
   - Finish collection and field ownership matrix.
   - Resolve opening-progress and endgame-content duplication.
   - Proposed commit: `docs: lock Personal Curriculum evidence ownership`.

2. **Data locks — complete**
   - Use the versioned offline snapshot and measured lock document.
   - Review after three fully D_live-instrumented games; use 21 days only as a check-in backstop.
   - Proposed commit: `docs: lock Personal Curriculum selection data`.

3. **Contract and probes**
   - Define the composed-decision and lesson-result contracts.
   - Build stateless probes and ownership guards.
   - Ship default-off.
   - Proposed commit: `feat(curriculum): add default-off composition contracts`.

4. **Read-only A/B surface**
   - Render the same canonical decision on Home and the replacement Learn surface.
   - Existing lesson destinations remain unchanged.
   - Mohit + Parth A/B for one week with the flag on.
   - Proposed commit: `feat(curriculum): add coach-led Learn experience behind flag`.

5. **Lesson continuity**
   - Adapt the audited V1 lesson set to the shared entry/result/resume contract.
   - Connect focused Play with Coach application.
   - Proposed commit: `feat(curriculum): connect V1 lesson continuity`.

6. **10% rollout**
   - Run for one week; monitor selection validity, empty plans, lesson continuation, errors, and legacy parity.

7. **100% rollout**
   - Promote only after quantitative gates and moderated-player checks pass.

8. **Delete legacy after two clean weeks**
   - Redirect superseded routes.
   - Remove parallel selectors and retired UI.
   - Preserve canonical detail pages and deep links.

No implementation phase begins until its blocking decisions in section 10 are signed off.

## 10. Locked decisions / Open questions

1. **Canonical route — corrected by live validation:** `/learn` is canonical;
   `/games` is the player-facing Game Review index. `/lab` remains the
   preserved legacy learning-path route until redirect evidence exists.
2. **Plan persistence — locked:** Store only a compact active-plan reference in `coach_memory.learning`; do not copy lesson, detector, or progress truth into it.
3. **Explore autonomy — locked:** Explore runs alongside the coach plan and does not replace the recommendation automatically.
4. **First lesson slice — locked:** Rule of the Square is first, through “Can do alone”; suppress real-game application and mastery claims until its detector is Plan-grade.
5. **Opening state — locked:** `user_opening_progress` owns lesson progression; `user_opening_mastery` remains detector-derived evidence. They are composed, not merged.
6. **Endgame content — locked:** `backend/data/coaching/endgame_theory_tree.json` owns routed V1 lesson truth; `backend/data/endgames.json` remains a legacy adapter only.
7. **Review game-count — locked:** Review after three fully D_live-instrumented games. The 21-day backstop prompts re-engagement but never manufactures an evidence verdict.
8. **Product-owner visual approval — locked:** Mohit approved the interactive
   desktop/mobile Home, Learn, Explore, and lesson-return prototype on
   2026-08-28.
9. **Representative-player validation — final acceptance:** Observe the signed tasks with
   600–900, 1000–1200, 1300–1500, and a browse-oriented participant. The
   server-side recruitment snapshot confirms structural reach; sessions must
   still be real. On 2026-08-29 Mohit explicitly moved these sessions after
   implementation so the completed product can be audited with other coaches.

**Sign-off gate:** Mohit approved the Phase 4 visual contract and instructed
the work to move forward. Pre-launch PostHog behavior remains excluded as an
engagement baseline. Structural recruitment reach is cited from
`backend/data/corpus_snapshots/funnel_and_recruitment_2026-08-28.json`.
Representative-player and coach sessions are the final acceptance gate before
cohort expansion; they are no longer a pre-code gate.
