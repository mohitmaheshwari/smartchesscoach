# Home Replay Diagnostic — Spec

**Status:** APPROVED v1 — Mohit signed off on 2026-09-02 (“go ahead”).
**Version:** v1 (2026-09-02).
**Scope:** largest Home slice; multi-day to implement and verify.

---

## 1. The problem

The enabled Home experience currently names an active topic and says that the coach found it in the player's games, but its evidence disclosure can reduce to “This is the one idea in your current coaching plan.” A developing player may not remember the game, and a reference to an opponent, move number or lost rook does not prove that the coach understands what the player knows now.

The system also currently accepts one stored best move as the answer to an exact destination-safety puzzle. That is valid for a best-move puzzle but invalid for a concept diagnostic: a player may avoid the exact safety error with another legal move. Conversely, a random move may avoid that error while failing for a different chess reason. The diagnostic must judge the target idea separately from overall move soundness.

Production evidence supports a Mohit-only V1. His exact focus has 193 verified fires across 160 games and 189 distinct positions, leaving 13,556 strict cross-game/cross-piece pairs. Position supply is abundant. The missing product is an answer-hidden test, an honest result, and continuity into later coaching.

## 2. The shape — six outcomes

Architecture:

```text
active exact focus + Plan authorization
                |
                v
strict pair selector -----> no valid pair: preserve current Home action
                |
                v
answer-hidden position 1 -> move first -> optional reason after move
                |
                v
answer-hidden position 2 -> different game/FEN/piece -> reason if needed
                |
                v
target-concept grader + independent move-soundness guard
                |
                v
diagnostic result -> existing curriculum action -> later evidence
```

| Observable result | Home conclusion | Next action |
|---|---|---|
| Both target checks pass independently and the final reason agrees | Demonstrated transfer in these two positions | Quiet coached application |
| First passes; different position fails or reasoning conflicts | Familiar-position recognition only | Teach the reusable board signal |
| Target check passes after substantive help | Prompted recognition | Build a pre-move trigger |
| Both target checks fail independently | Current learning need | Teach the board relationship directly |
| Target check passes but soundness guard finds a separate serious problem | The tested idea was handled; the move has another issue | Preserve the target result and explain/retry the separate issue |
| Any proof, grading, identity or redaction contract fails | No conclusion | Fail closed to the existing Home action |

The target-concept result and overall move quality are never collapsed into one “correct” boolean.

## 3. Schema / files touched

### Backend

- Extend `services/personal_curriculum.py` with the versioned diagnostic result contract and projection into existing curriculum states. Do not add another mastery enum or store.
- Extend `services/teaching_engine.py` with `delivery_mode=blind_diagnostic`, two-position progression, idempotent responses and a public projection that withholds lesson identity, answer material and private proof facts until the correct reveal stage.
- Extend `services/personalized_lesson_adapter.py` to resolve a strict diagnostic pair from verified own-game material. It references existing detector and admission identities rather than copying chess rules.
- Extend `services/destination_safety_detector.py` with a counterfactual entry point that evaluates the player's newly submitted legal move using the existing exact exchange calculation.
- Reuse `services/legal_exchange_verifier.py` for independent destination-loss proof and the existing coach move-soundness guard for non-target tactical safety. No second exchange evaluator is introduced.
- Extend `routes/training.py` with owned diagnostic start/respond/help/pause endpoints or thin adapters over the existing personalized-session functions.
- Extend `routes/coach.py` personal-curriculum response with a derived `home_diagnostic` projection and current lifecycle state.
- Extend `analysis_worker.py` only for shadow creation of authorized organic application/miss evidence. A clean game without a positive opportunity remains `not_measured`.
- Reuse `review_reflection_service.py`/the canonical quick-tag registry to author options, but store diagnostic answers in the existing learning-session event. Do not add a reflection collection.

### Frontend

- Extend `components/curriculum/CurriculumPrimary.jsx` to render the diagnostic state in place of the generic primary card.
- Add `components/curriculum/HomeReplayDiagnostic.jsx` as a renderer/orchestrator only. It owns no chess rules, answers or result classification.
- Reuse `components/LichessBoard.jsx`, existing help controls and current Home visual language.
- Extend `lib/analytics.js` with the predeclared diagnostic lifecycle events.

### Existing storage only

- `learning_sessions`: add versioned `delivery_mode`, pair identity, stage and events inside the existing document.
- `user_active_focus`: remains the owner of the active focus; no duplicate diagnostic focus is stored.
- `move_observations` and verified puzzle evidence remain chess-evidence owners.
- No new collection is created.

## 4. New facts / data the system needs

- `diagnostic_version` and stable pair fingerprint.
- Exact quality id, detector version and normalized position fingerprints for both positions.
- Honest source kind for each position: own game or verified external-to-player position.
- Target-concept result for the submitted move: pass, fail or unmeasured.
- Independent exchange proof for the submitted move.
- Separate overall soundness result from the existing guard; it cannot rewrite the target result.
- Help requested before submission and whether the answer or decisive square was revealed.
- Stable reason option ids, shown ids and selected id when reflection is required.
- Bounded diagnostic result and the existing curriculum action it selected.
- Later evidence source: controlled lesson, coached application or organic game.
- Explicit `not_measured` when no authorized positive or negative opportunity exists.

The first public payload contains no lesson title, rule, detector name, original move, best move, accepted moves, opponent, game id, explanation, highlighted answer square or result label.

## 5. Gating — preventing the “engine move equals understanding” trap

1. **Authorization gate:** only an exact Plan-authorized quality id can create the player-facing hypothesis.
2. **Pair gate:** same quality id/version; different game, normalized FEN and moved-piece type; both positions independently admitted.
3. **Answer-hidden gate:** tests assert forbidden fields are absent recursively, not merely unused by the component.
4. **Target-versus-soundness gate:** exact concept understanding and overall move quality are separate contracts and separate copy.
5. **Independent-proof gate:** the target result must agree with the canonical detector and independent exchange verifier.
6. **Reasoning gate:** a lucky safe move with an inconsistent explanation cannot earn demonstrated transfer.
7. **Assistance gate:** substantive help caps the result at prompted recognition.
8. **No-primary-weakness gate:** Home says “a decision I want to test,” never “your main weakness,” unless a later comparative system proves that claim.
9. **No-absence-as-success gate:** zero misses is not organic application. Positive application needs an authorized positive opportunity; otherwise the state remains not measured.
10. **Single-source gate:** the Home component, pair selector and session engine reference canonical detector, admission, reflection and curriculum contracts; none restates their chess rules.
11. **Idempotency gate:** refresh, duplicate clicks and repeated submissions cannot add evidence or change pair assignment.
12. **Scope gate:** automatic detector discovery, community explanations and reputation remain outside this feature.

## 6. Test strategy

### Phase 1 — stateless chess and contract tests

- Every legal move in sealed sample positions is classified by target concept and soundness independently.
- Safe non-best moves pass the target concept without being called the engine's best move.
- Random safe but tactically losing moves preserve the target pass and fail the soundness guard.
- Illegal moves, promotion edges outside the detector packet and unsupported proof families fail closed.
- Strict pair matching rejects same-game, transposed, same-piece and mixed-detector pairs.
- Result mapping covers every combination of move outcome, help and reason consistency.

### Phase 2 — backend boundaries

- Start returns a stable owned session and byte-identical pair on retry.
- Recursive leak tests prove no private answer or lesson fields leave before reveal.
- Respond/help are idempotent and reject cross-user sessions.
- Only existing evidence collections are written.
- Home projection advances theory → test → result → action without contradictory states.

### Phase 3 — frontend

- Home shows one action and the approved literal copy.
- Board orientation, legal move submission, help, loading, retry, pause and mobile layout work.
- Refresh resumes the exact stage without showing the answer.
- The generic disclosure does not remain beside the diagnostic.

### Phase 4 — corpus and independent chess review

- Run a sealed Mohit pair packet across openings, middlegames, endgames and all four moved-piece types.
- Independently verify each board, target result, safe alternative and separate soundness conclusion.
- Review every user-facing sentence against its exact proof.

### Phase 5 — production validation

- Deploy default-off; enroll only Mohit's account.
- Run API E2E, payload leak inspection and browser verification.
- Compare the conclusion with independent Codex chess reasoning and human coaches.
- Keep later organic evidence shadow-only until positive-opportunity authorization exists.

## 7. Risk + rollback

**Flag:** `HOME_REPLAY_DIAGNOSTIC_ENABLED=false` by default. Enrollment is additionally required on the user record; the flag alone exposes nobody.

Main risks are answer leakage, a false same-skill pair, rejecting a valid safe alternative, accepting a move that passes the narrow idea but fails tactically elsewhere, duplicate evidence, and interpreting no future miss as improvement.

Rollback is runtime-only: disable the flag and restart the backend/frontend as required. Home immediately returns to the existing curriculum card. Diagnostic sessions remain inert evidence and do not alter the active focus or existing lesson state.

## 8. What this spec does NOT cover

- Automatic discovery or promotion of new chess detectors.
- Community explanation, reputation or community-coach marketplace features.
- More than the Plan-authorized exact destination-safety family in visible V1.
- A claim that the tested idea is the player's largest weakness.
- Broad positional-understanding inference from two positions.
- Positive organic application inferred from silence.
- Automatic graduation before an opportunity-aware rule is separately measured and locked.
- Replacing Game Review, Training, Progress or Play with Coach.
- Maia/Otter/Fathom in the correctness path.
- Wider rollout thresholds before real validation sessions exist.

## 9. Implementation order

1. **Docs and locks:** land scope, production snapshot, data lock and this spec separately from implementation.
2. **Contracts and chess grader:** pair contract, blind projection, counterfactual exact grading and separate soundness result; tests first.
3. **Session integration:** extend the existing personalized session and Home curriculum projection; no new collection.
4. **Home experience:** replace the generic primary body with the approved board flow and analytics.
5. **Shadow continuity:** record later authorized misses and keep unsupported positive application as not measured.
6. **Ship default-off:** flag false, no enrolled users.
7. **Mohit A/B validation:** enroll only Mohit; compare existing Home with the diagnostic experience and audit each result.
8. **10% rollout:** only after §10 decisions and validation thresholds are locked from new evidence; monitor for one week.
9. **100% rollout:** only after the 10% gate passes; monitor for two weeks.
10. **Delete legacy generic diagnostic disclosure:** only after two clean weeks at 100%; retain ordinary curriculum fallback for users without a valid pair.

## 10. Decisions / Open questions for Mohit

- **Target versus soundness:** Approved. A move may pass the tested idea while receiving a separate warning about another chess problem.
- **Organic application:** Approved honesty boundary. V1 detects authorized later misses but never calls a clean game “applied.” A positive-opportunity detector remains a separately scoped follow-up.
- **Graduation:** Approved honesty boundary. V1 stops at controlled transfer / watching / measured miss until opportunity-aware graduation is data-locked.
- **Broader knowledge:** Approved. The architecture is generic; visible V1 starts with exact destination safety. Each later family needs an exact pair predicate and answer grader.
- **Rollout:** Approved. Mohit-only production validation precedes any 10% cohort.
