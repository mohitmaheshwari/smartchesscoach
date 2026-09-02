# Complete Coaching System — Architecture Spec

**Status:** ARCHITECTURE AND PHASE 0 EVIDENCE LOCKED — Mohit approved Phase 1 implementation on 2026-09-02.
**Version:** v1 (2026-09-02).  
**Scope:** largest; multi-phase migration built on `docs/complete_coaching_system_scope.md`.  
**Audited base:** `origin/working-code` at `656e3374`.  
**Final composition flag:** `COMPLETE_COACHING_SYSTEM_V1_ENABLED=false` by default; subsystem truth gates remain independently fail-closed.

---

## 1. The problem

ChessGuru already has most of the required pieces, but not one complete learning machine. On the audited base there are 77 dynamically composed curriculum skills, 41 publishable openings, 36 publishable traps, 19 opening-plan lessons, 20 publishable endgames, three detector execution registries, and 53 explicit detector authorizations. Only one authorization is Plan-grade; three are Caption-grade, 44 are Shadow, and five are Disabled. The content is broader than the proven personalized intelligence.

The product also has competing interpretations of learning: `concept_mastery_service`, the legacy `backend/focus_mastery_service.py` path and `/missions/focus-mastery` projection, `mastery_gate_service`, `pwc_skill_gate`, legacy Engine 2 study state, and domain trackers can disagree. A lesson can resume across an incompatible content or diagnostic version, several verified puzzle claims are collapsed to one hard-coded winner, and current puzzle attempts lack the assistance and attempt-time rating facts required for honest difficulty or mastery analysis.

The target is not another coach page or another detector catalog. It is one governed path from stored chess evidence to a verified chess idea, a personal plan, the right teaching act, an unassisted check, a later real-game opportunity, and an honest progress verdict.

## 2. The shape — one coaching spine, eight contracts

```text
external games / Play with Coach
              │
              ▼
 immutable analysis evidence ── Stockfish / legal board / Fathom-Syzygy
              │                                  ▲
              │                     Otter/Maia rank only safe choices
              ▼
 typed board facts → VerifiedClaimSet (keep every verified explanation)
              │
              ▼
 derived ConceptContractIndex ← skill identity + content refs + authorization
              │
       ┌──────┴──────────┐
       ▼                 ▼
 GameTeachingPlan   canonical focus/curriculum decision
       │                 │
       └──────┬──────────┘
              ▼
 teaching_engine → LessonResult v2 → learning_sessions event ledger
                                          │
                         later comparable opportunity
                                          ▼
                              concept_mastery_service
                                          │
                       Home / Learn / Review / PWC / Progress
```

| Contract | Owner and rule |
|---|---|
| **AnalysisEvidence** | Existing stored move evaluations are immutable truth for analysed games. New live evidence carries provider, version, input fingerprint, legal move, evaluation/PV, and provenance. Existing games are not re-run merely to redesign detectors. |
| **VerifiedClaimSet** | The central caption/proof path preserves every independently verified claim for a position. Claim collection is separate from choosing the one idea to teach. A priority rule may select presentation; it may not erase true evidence. |
| **ConceptContractIndex** | A generated, read-only composition view joins one stable concept identity to detector quality IDs, content references, lesson capabilities, grader, opportunity contract, and transfer rule. It stores no copied opening line, trap, endgame position, detector rule, or caption. |
| **CoachingContext** | `user_active_focus` owns priority and immutable instruction; `focus_bridge` is the only reader. One primary focus owns the CTA, at most one contextual support is visible, and requested material is an elective. |
| **GameTeachingPlan** | Existing review contracts assemble verified claims into the game's human story. Review may teach important off-focus chess, but cannot silently change the active plan. |
| **LessonResult v2** | One versioned event shape records stage, content/grader version, position, answer, assistance, reasoning components, source, and idempotent event identity. Every lesson adapter emits it. |
| **LearnerProjection** | `concept_mastery_service` is the only player-facing reducer. It distinguishes learning, help, independent performance, game application, retention, insufficient evidence, and refresh. |
| **HumanPolicyEvidence** | Fathom/Syzygy may supply exact covered-endgame truth. Otter, with Maia fallback, may estimate human likelihood or rank an already-safe candidate set; neither can decide correctness, intention, weakness, or mastery. |

The student experience becomes: “Here is the chess idea I saw in your games; here is why it matters on this board; try it with the amount of help you need; now do it alone; I will watch for the same decision in later games; here is what the evidence now allows me to say.”

## 3. Schema / files touched — canonical ownership and retirement

### Single-source decisions

| Concern | Canonical owner | Disposition |
|---|---|---|
| Stored engine truth | `game_analyses.stockfish_analysis.move_evaluations` and current analysis envelope | **KEEP.** Adapters may derive typed facts; they do not overwrite engine history. |
| Exact covered endgames | `services/exact_endgame_service.py` with pinned Fathom/Syzygy provenance | **KEEP DEFAULT-OFF**, then authorize per consumer. |
| Human move likelihood | `services/human_policy_runtime.py` | **KEEP SUBORDINATE.** Otter history-first; Maia fallback; no truth authority. |
| Per-move teaching | `services/caption_pipeline.py::build_move_teaching_decision` plus verified proof builders | **EXTEND** to return a claim set and explicit selection reason. No second caption brain. |
| Detector execution | `concept_detectors`, `endgame_detectors`, and Chess Brain registries | **KEEP AS EXECUTION PLUGINS.** Different call contexts are legitimate; every output must declare canonical `concept_id` and `quality_id`. They are not three user taxonomies. |
| Surface authorization | `services/detector_quality.py` | **KEEP/CLARIFY.** Unknown stays Shadow; only evidence-reviewed promotion changes rights. The current `DIAGNOSTIC` surface is internal research evidence, never permission for a player-visible persistent diagnosis. |
| Learner concept identity | `data/coaching/skill_tree.json`, including its current generated content nodes | **EXTEND.** It owns stable learner-facing IDs, labels, domains, aliases, and prerequisites—not chess proof. |
| Openings | `data/opening_curriculum.json` through `opening_unified_source.py` | **KEEP.** Quarantined entries remain unavailable until repaired, never silently deleted. |
| Traps | `data/traps.json` through `trap_library.py` | **KEEP.** |
| Endgames | `data/coaching/endgame_theory_tree.json` through `endgame_theory_service.py` | **KEEP.** `data/endgames.json` remains a compatibility adapter until migrated. |
| Focus and instruction | `user_active_focus` + `focus_bridge.py` | **KEEP/EXTEND.** No direct surface reads after migration. |
| Lesson lifecycle | `services/teaching_engine.py` + `learning_sessions` | **EXTEND.** Session compatibility is keyed by content, grader, diagnostic, and proof-contract versions. |
| Learning event | `personal_curriculum.LessonResult v2` | **KEEP/EXTEND.** It becomes the only adapter output consumed by mastery. |
| Player-facing learning state | `services/concept_mastery_service.py` | **REPLACE INTERNALLY.** Keep the API name; move legacy study summaries behind adapters and retire rival labels. |
| Review story/reflection | `game_review_contracts`, planner, event adapter, reflection service | **KEEP.** Reflection refines diagnosis but cannot alter objective chess truth. |
| Puzzle admission/grading | `verified_puzzle_admission`, `verified_puzzle_builder`, `verified_puzzle_attempt_service` | **EXTEND.** Admission stays fail-closed; attempt evidence becomes versioned and assistance-aware. |
| Rating | `services/rating_resolver.py`; bands from `deterministic_coach_service.RATING_BANDS` | **KEEP.** Every rating carries source, platform, sample, and as-of date. |
| Analytics | Existing coaching analytics/event registry | **KEEP DERIVED.** Analytics never writes mastery or coaching priority. |

`ConceptContractIndex` is code-generated from those owners, not a new JSON catalog. The initial implementation belongs in `backend/services/concept_contract_registry.py` and must fail startup/tests on dangling IDs, duplicate aliases, unauthorized surfaces, missing graders, or copied content. A registered concept can be curriculum-only, Caption-capable, Plan-capable, mastery-capable, or research-only.

### Migration dispositions

- Adapt, compare, then retire player-facing decisions from `backend/focus_mastery_service.py` and the duplicated `/missions/focus-mastery` projection, `services/mastery_gate_service.py`, `services/pwc_skill_gate.py`, legacy `summarize_mastery`, and direct `engine2_skill_builder.pick_next_skill` callers.
- Keep domain trackers only as raw evidence producers. They emit `LessonResult`/opportunity facts and never publish “learned” independently.
- Replace the puzzle builder's single hard-coded winning proof with all verified claims plus a separately selected primary teaching claim.
- Preserve legacy deep links and records. Withdraw only claims that cannot be reproduced; never delete legitimate games, attempts, content, or provenance.
- Do not resume an active lesson when its compatibility fingerprint changes. Finish it on the frozen version when safe; otherwise close it as `superseded` and start a new session with an inspectable reason.

## 4. New facts / data the system needs

- **Concept contract:** `concept_id`, aliases, domain, stage/prerequisites, content references, supported teaching methods, detector `quality_id`s, allowed surfaces, grader version, opportunity-contract version, transfer-contract version, and evidence limitations.
- **Verified claim:** actor, move/ply, claim type, before/after state, involved pieces and squares, legal continuation, objective consequence, verifier/provenance, authorization grade, and whether it is explanation-, plan-, or mastery-eligible.
- **Comparable opportunity:** `occurred / applied / missed / unclear / did_not_occur`, source mode, assisted flag, time control, event time, detector/proof version, focus/instruction IDs, and explicit rejection reason.
- **Learning attempt:** content and grader versions, first/retry attempt, help/reveal/correction, response time, distinct-position identity, accepted alternative reason, source event ID, and cohort.
- **Puzzle attempt v2:** first answer before reveal, all assistance, attempt-time rating plus provenance, model/proof versions, response latency, and admission fingerprint. Old attempts stay `measurement_unknown` rather than being backfilled by guess.
- **Session compatibility fingerprint:** lesson identity + content revision + grader + diagnostic + proof contract + assigned form. Cosmetic text may remain compatible; chess, answer, hint, or measurement changes may not.
- **Forecast:** any “21-day plan” is a forecast based on the player's opportunity rate and scheduled work, with confidence and review point; it is not a guaranteed Elo increase.

## 5. Gating — preventing the “smart coach made it up” trap

1. **Truth:** stored Stockfish or exact tablebase evidence leads; legal replay and independent proof validate every board claim.
2. **Claim-set:** all verified ideas survive extraction; presentation selection cannot change truth.
3. **Authorization:** Shadow/`DIAGNOSTIC` may populate internal research only; Caption explains one event; Plan may publish a persistent diagnosis, prioritize, or prescribe; Mastery additionally requires an explicit opportunity contract. Unknown is Shadow.
4. **Concept identity:** no surface invents or renames a concept locally. Legacy IDs resolve through tested aliases.
5. **Human-model restraint:** Otter/Maia may rank only safe moves or provide shadow findability. They never widen the safe set or diagnose psychology.
6. **Reflection restraint:** one selected option describes one decision. Only repeated independent evidence may affect a durable profile.
7. **Assistance:** hinted, revealed, corrected, Coach Mode, unassisted checkpoint, Play Mode, and external games remain distinct.
8. **Opportunity denominator:** no opportunity means no credit and no failure. Absence of a detector fire is not improvement.
9. **Main-weakness honesty:** until multiple domains have comparable Plan-grade evidence, copy says “one verified focus,” not “your biggest weakness.”
10. **Versioning:** incompatible sessions, stored plans, detectors, or graders fail closed and regenerate/migrate explicitly.
11. **Voice:** the system names the piece, square, threat, plan, or rule before jargon; no centipawn reports or generic knowledge prose reaches the player.
12. **One reader:** Home, Learn, Review, PWC, and Progress may render differently but receive identical focus, instruction, concept, and learner-state IDs.

## 6. Test strategy

1. **Source guards:** every content item and detector output resolves to exactly one concept identity; every concept reference resolves; retired authorities have no migrated callers.
2. **Stateless chess packets:** legal replay, origin/destination safety, forcing replies, exchanges, rays, pins, skewers, forks, discoveries, overloads, trapped pieces, mating patterns, opening purposes, positional relationships, and exact endgames. Include false friends and multiple-good-move positions.
3. **Authorization packets:** precision, true negatives, adversarial failures, distinct source units, opportunity recall, and reproducible fingerprint per detector. Promotion is separate from detector implementation.
4. **Corpus replay:** run the new claim set and concept adapters over all stored analysed games without rerunning Stockfish; compare coverage, conflicts, abstentions, category drift, latency, and old/new visible output.
5. **Predictive validity:** train a player's profile on earlier games and test later games; compare against raw-frequency, recency-only, and rating-only baselines before claiming the learner model predicts future mistakes.
6. **Learning fixtures:** explain → guide → transfer → apply → retain, including help, retry, alternative correct moves, no opportunity, relapse, stale content, duplicate events, and cross-device resume.
7. **Migration rehearsal:** snapshot, restore-test, dry-run, apply to isolated validation data, verify preserved/withdrawn counts, then test one selected account. No broad `--all` before the account gate passes.
8. **API/E2E:** one real account completes Home → Review → reflection → lesson → unassisted check → later-game evidence → Progress; flag-off remains compatible.
9. **Human validation:** Mohit plus two coaches grade blinded complete journeys for chess truth, importance, clarity, personalization, teaching value, and next action. Any critical false claim blocks rollout.
10. **Operational:** prove deterministic replay, idempotency, bounded latency, fallback without model files, no credential/PGN leakage, and explicit backend/frontend build exit codes.

## 7. Risk + rollback

Primary risks are truthful-but-empty coaching, duplicate mastery during migration, a lossy primary-claim selector, stale-session leakage, false personalization, slow analysis, and a human model being treated as truth. Each phase ships additive and default-off, records version/provenance, and retains legacy readers until parity passes.

Rollback sets `COMPLETE_COACHING_SYSTEM_V1_ENABLED=false`; affected surfaces return to the current canonical-context/curriculum/review readers. Lower-level flags can independently disable exact endgames, human policy, personalized review, curriculum, or PIC. Evidence is retained and replayable; rollback never deletes attempts or rewrites mastery. A restore-tested snapshot is mandatory before migrations.

## 8. What this spec does NOT cover

- A promise that every chess idea or every player is understood perfectly.
- A guaranteed Elo gain or fixed 21-day result.
- Free-form LLM chess authority, psychological diagnosis, or LLM-generated detector truth.
- Re-running Stockfish on the existing analysed corpus.
- Promoting all existing detectors by declaration, or hiding valid content because its detector is not Plan-grade.
- A second dashboard, coach, content catalog, focus store, event ledger, caption path, or mastery score.
- Community human explanations; that deserves a later trust, moderation, attribution, reputation, and abuse-prevention scope.

## 9. Implementation order

1. **Phase 0 — evidence and migration lock.** Freeze current code/corpus fingerprints; generate the concept/detector/content crosswalk; inventory every caller of rival focus/mastery/selector paths; run predictive-validity and session/puzzle-attempt coverage audits. Commit docs/data only.
2. **Phase 1 — contract spine, no visible change.** Add the generated `ConceptContractIndex`, `VerifiedClaimSet`, compatibility fingerprint, and source/alias/authorization guards behind default-off flags.
3. **Sign-off gate.** No runtime adapters or data writes start until Mohit approves §10 and Phase 0 measurements.
4. **Phase 2 — one evidence ledger.** Make every migrated lesson, puzzle, review, and game opportunity emit idempotent `LessonResult v2`; extend puzzle attempts to v2; run the canonical mastery reducer in shadow beside legacy outputs.
5. **Phase 3 — chess-intelligence breadth.** Select the next detector families from measured prevalence, distinctiveness, proofability, opportunity coverage, and lesson readiness. Build/polish proof families, independent gold, adversarial packets, Caption promotion, then Plan/Mastery promotion where earned.
6. **Phase 4 — teaching and transfer.** Connect canonical content to concepts; support explain, predict, compare, calculate, recognize, execute, defend, and replay; add unassisted transfer and later-game opportunity measurement.
7. **Phase 5 — complete Review.** Preserve all verified claims, teach the game's opening/intent/tactics/position/endgame story, ask one useful pre-reveal reflection, and prescribe one canonical next action.
8. **Phase 6 — human-chess runtime.** Enable exact endgame truth first after deployment provenance tests. Pilot Otter/Maia only for safe opponent choice, findability, distractors, and shadow audit; promote each use separately.
9. **Phase 7 — one product experience.** Evolve the canonical context across Home, Learn, Review, PWC, and Progress; one primary CTA, one optional support, elective study, and evidence-linked verdicts.
10. **Phase 8 — rollout.** Ship default-off; Mohit + two coaches A/B for one week; then 10% for one week with pre-registered gates; then 100%; delete legacy paths only after two clean weeks at 100%.

Each detector family and destructive migration receives its own data lock, pre-code audit, focused tests, and commit boundary. The architecture spec is not permission to merge every phase in one change.

## 10. Decisions / Open questions for Mohit

### Recommended decisions locked by this draft

1. **Architecture:** extend the approved Complete Coaching System; no parallel product or new data authority.
2. **Truth order:** Stockfish/legal facts and exact tablebases decide chess correctness; Otter/Maia describe human likelihood only.
3. **Identity:** `skill_tree.json` owns learner concept identity; the new index is generated from references and validates, never copies, other authorities.
4. **Focus:** one primary plus at most one contextual support, as locked in `coaching_context_support_cap_data_lock_2026_08_28.md`; requested study is elective.
5. **Evidence:** every verified claim is retained; primary teaching selection is a separate explainable decision.
6. **Mastery:** one `LessonResult v2` ledger and one learner reducer; all rival labels become adapters, then retire.
7. **Personalization:** delivery adapts to the player's games, history, help, rating provenance, and demonstrated knowledge; chess truth never changes to sound personal.

### Open questions that block Phase 2

1. **Which detector families are promoted next?** Shortlist: immediate threat response, fork, pin/skewer, forced mate/back-rank, opening decision/plan, and exact endgame play. **Unblock:** Phase 0 bake-off across the corpus plus independent review; select by evidence, not by this list.
2. **What proves transfer and reliability per family?** Opportunity frequency differs too much for one guessed game count. **Unblock:** opportunity histograms, chronic/learner simulations, and pilot distributions; lock each rule with citations.
3. **Which legacy learning claims survive migration?** Current stores use incompatible meanings. **Unblock:** read-only equivalence report showing preserved, downgraded, unknown, and rejected counts by source.
4. **When can human findability affect visible difficulty or move choice?** Current puzzle attempts cannot calibrate it. **Unblock:** collect prospective v2 attempts and blinded opponent/coach review; until then remain shadow or safe-set-only.
5. **What duration may the personal plan display?** “21 days” is attractive but opportunity cadence varies. **Unblock:** forecast calibration by opportunity rate and completion behavior; show a review date before promising a result date.

**Architecture sign-off:** approved on 2026-09-02. **Phase 0 evidence sign-off:** approved on 2026-09-02. The Phase 1 pre-code audit passes; contract-only implementation is authorized.
