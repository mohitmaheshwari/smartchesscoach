# PWC evaluation reliability repair -- independent review handoff

Date: 2026-09-15. Branch: codex/pwc-evaluation-reliability-v1.
Base: origin/working-code a979a691. Isolated worktree: _pwc_evaluation_repair.
Status: implemented and locally tested; NOT pushed, deployed or enabled.
Keep PWC_UNIFIED_EXPERIENCE_V1_ENABLED OFF.

## Incident and verified limits

Claude reports an almost-silent unified session and unreliable stored losses.
This repair does NOT certify those stored figures or claim nine real blunders.
The private session, exact positions and production credentials were not available.
No production records were read, written, exported or reanalysed in this work.
No caption rule/template, detector grade, rollout flag or learning baseline changed.
No model calls. Local Stockfish ran only against fixed test positions.

The two peer session names in the report were not available in the Codex task
listing. This isolated branch avoids editing another builder's worktree; coordinate
with Claude before integrating, especially if another repair has started.

## Confirmed code defects

1. Search errors in _quick_eval returned 0.0 and the parent still reported depth 10.
2. Depth 8/10 and node counts were fabricated constants, not completed search data.
3. Shared UCI engine creation was locked, but its multi-search requests were not.
4. A scalar last-session score was reused without matching FEN, POV or units.
5. Unified suppressed verified MID captions: TeachingMeta.has_teaching_content
   meant HIGH only, while the existing classifier defines MID as concrete chess
   content. The real queen-loss canary reproduced this exactly.
6. Already-searched continuations were not passed to canonical caption inputs.

## Repair

- Serialize each evaluation transaction on the shared engine.
- Compare unrestricted and forced proposed-move searches on the same root.
- Retain the scalar-cache argument for call compatibility but ignore it as evidence.
- If the proposed move IS the unrestricted best move, reuse that exact result:
  a second search cannot manufacture a loss against the same recommendation.
- Consume individual UCI info updates, retaining completed exact iterations.
  SimpleEngine.analyse merges dictionaries and can retain old bound markers.
  Last exact depth/PV/score stay together; no completed exact iteration -> unknown.
- Preserve White-view score convention and the existing caller's player conversion.
- Store exact root, move, POV, score units, actual depths and UCI lines alongside
  unified decisions. Failure reasons are persisted too.
- Validate and convert those lines into existing pv_after_played/pv_after_best
  inputs; no alternative caption generator or fresh verification search added.
- Allow final-verified HIGH/MID teaching through the unified adapter. LOW/NONE,
  empty and unverified content remains rejected. This is not detector promotion.
- Invalid evaluation produces a nonblocking operational notice, not a chess
  verdict. Such notices do not consume the teaching cadence allowance.
- Unknown stays unknown in public move quality; invalid scores remain null in
  private persisted evidence. Ordinary genuinely good moves still take the quiet
  path. This repair does not implement a broader positive-coaching curriculum.

## Actual tests

Before repair: existing focused suite 24 passed.
Seven newly written defect tests: 7 FAILED against original code, then passed.
Broader existing PWC/deployment suite on unchanged backend: 61 passed, exit 0.
Final candidate suite: 80 passed, exit 0, including 4 real-engine canaries.

From backend, with PYTHONPATH=.:

    RUN_PWC_ENGINE_CANARY=1 STOCKFISH_PATH=<local engine> python -m pytest +      tests/test_fast_eval_reliability.py +      tests/test_unified_pwc_coaching.py +      tests/test_a_failed_eval_never_says_good.py +      tests/test_unified_pwc_real_engine_canary.py +      tests/test_pwc_unified_experience_contract.py +      tests/test_pwc_unified_background_contract.py +      tests/test_pwc_unified_observability.py +      tests/test_verify_deployment.py -q

Local engine: Stockfish 18 Windows AVX2.
Real pipeline canaries:

- f3 e5 g4 Qh4#: verified intervention at g4, game legally reaches mate.
- e4 e5 Bc4 Nc6 Qh5 Nf6 Qxf7#: verified intervention at Black's Nf6.
- e4 e5 Qh5 Nc6 Qxe5+ Nxe5: verified intervention at the queen loss.
- Four concurrent real searches: completed results identify the blunder;
  requests without completed evidence explicitly return unknown.

The queen-loss canary initially FAILED after the evaluator fix and caught the
separate HIGH-only adapter suppression. It was not removed or weakened.
The first real-engine run also caught the merged-bound issue missed by mocks.

Additional regressions: both POVs, corrupt scalar cache, missing score, zero
depth, search exceptions, bound-only output, wrong forced move, engine overlap,
queue timeout, exact iteration followed by a bound, best=played, visible failure,
teaching allowance preservation, and deploy gate ordering.

scripts/deploy.sh passes bash -n. git diff --check passes.
No full repository pytest pass claimed.

## Deploy guard

The deploy script runs the real-engine canary in the built candidate image using
docker compose run --rm --no-deps, BEFORE docker compose up replaces production.
It is mandatory for backend/all deployments even when unified is disabled,
because fast_eval is shared with legacy. Failed canary aborts the deployment.
Requirements include pytest; Dockerfile copies tests and installs Stockfish.
This Docker execution was NOT run locally; Claude must validate it in the image.
The canary itself is service integration, NOT browser/HTTP/session-persistence E2E.

## Open acceptance gates -- do not confuse local pass with release approval

1. Independent code review, particularly shared fast_eval effects on legacy,
   root-score comparison, streaming info validity, and MID-caption admission.
2. Candidate Linux image canary and repeated-run/concurrency timing. The inherited
   800ms budget is not a measured P95 guarantee. Engine startup and UCI stopping
   can exceed it; a cold request may be unavailable rather than falsely good.
3. tests/test_all_flows.py was attempted against localhost:8001 and failed at its
   first request with httpx.ConnectError. No local backend was listening.
   Run with authorized staging services; this gate is OPEN, not skipped-as-pass.
4. Authorized HTTP/browser losing-game walkthrough: verified text actually
   rendered, holds/revise/continue correct, failure notice visible, persistence
   matches scores/POV, Play mode stays quiet, postgame still works.
5. Replay the incident's exact authorized FENs with the correct pending-move
   context and compare new evidence. Old cp_loss values are not ground truth.
6. Only then consider a controlled pilot. Do not enable globally or silently
   switch an existing unified session to legacy mid-game.

The short deterministic games catch the previous trivial-opening canary gap,
but they are not a long deteriorating middlegame, retention evidence or a full
personalized-coach quality score.

One additional product observation, not repaired here: a mate example's canonical
transferable_instruction discussed a strong knight square rather than king safety,
although its displayed mate caption was relevant. Review instruction/caption
alignment separately; do not treat this repair as certification of all prose.

## Claude's integration checklist

- Inspect branch diff from a979a691; do not take the unrelated frontend branch.
- Compare against current working-code and preserve newer fixes.
- Keep unified OFF through review and candidate-image testing.
- No backfill/migration necessary. Search evidence is additive for future moves.
- Shared evaluator changes affect legacy even with unified OFF: test both paths.
- Backup/normal deployment responsibilities remain with Claude.
- Do not declare live on a build result: require the authorized user walkthrough.
- Code rollback restores the previous image; it cannot undo coaching a user saw.
  No existing data is rewritten by this patch.
