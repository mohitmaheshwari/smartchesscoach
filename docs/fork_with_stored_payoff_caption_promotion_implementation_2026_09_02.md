# Fork With Stored Payoff Caption Promotion — Implementation Record

**Date:** 2026-09-02
**Status:** IMPLEMENTED LOCALLY; not backfilled, pushed or deployed
**Scope:** `docs/fork_with_stored_payoff_caption_promotion_scope.md`
**Data lock:** `docs/fork_with_stored_payoff_caption_promotion_data_lock_2026_09_02.md`

## Delivered

1. `build_fork_payoff_caption_promotion_packet.py` independently reconstructs legal moves, post-move attack geometry, original-target survival, target capture and net material payoff from stored evidence. Its gold path does not import the production fork detector or proof builder.
2. `fork_payoff_caption_promotion_v1.json` freezes 50 distinct-source positive fires and 25 stratified near-negative controls. It contains board/proof facts and one-way source keys, but no user, account or game identity.
3. `tactic:fork_with_stored_payoff` is promoted from Shadow to Caption. Prompt, Plan and Mastery remain false under the central authorization contract.
4. Fresh Caption-grade fork verdicts remain `AdmissionStatus.BROAD`: `caption_concept_id` may explain a completed attempt while `concept_id` stays absent and the recovery identity remains `missed_tactic`.
5. The existing centralized verified-puzzle feedback renderer now describes the exact moved piece, destination square and every attacked target square. It no longer says “two targets” when the proof contains three.

## Evidence result

The reproducible production-container audit read stored evidence only:

| Gate | Result |
|---|---:|
| Documents scanned | 52,060 |
| Existing exact candidates | 709 |
| Distinct candidate sources | 589 |
| Full-population independent exact passes | 709 / 709 |
| Stored fact mismatches | 0 |
| Candidate replay failures | 0 |
| Promotion fires | 50 / 50 true |
| Near-negative controls | 25 / 25 abstained |
| Raw semantic precision | 100% |
| 95% Wilson lower bound | 92.87% |
| Critical adversarial errors | 0 |

The 50 positives span both stored pools, knight/bishop/rook/pawn forks, and both two-target and three-target cases. The negative packet contains five distinct-source cases each for fewer than two qualifying targets, incomplete stored lines, insufficient net gain, no original target captured, and insufficient stored consequence.

Full stored-candidate distribution:

| Dimension | Count |
|---|---:|
| Community puzzles | 155 |
| Community training positions | 554 |
| Knight | 451 |
| Bishop | 118 |
| Rook | 80 |
| Pawn | 60 |
| Two targets | 651 |
| Three targets | 58 |

Packet selection fingerprint:

    d5917f80f7ed646d3672c8ed205c6e7209ad54c1361f4f42240bb3296b53dff0

Canonical packet SHA-256:

    43bb871f6167984d577799effb645eccfef3b2870606065d0164d46ebd47436f

Stockfish runs, LLM calls and database writes were all zero.

## Player-facing boundary

After a solved or missed admitted position, the coach may now say, for example:

> e5 puts your pawn on e5, attacking the pieces on d6 and f6 at the same time.

The reusable reminder is:

> Before choosing a move, scan every legal check and capture for one move that attacks more than one piece.

The move and square tokens come only from verified proof facts. The renderer does not claim that every defence loses, does not infer why the player missed the move, and does not turn one fork into a persistent weakness or mastered skill.

## Verification

- Focused fork/evidence/admission/feedback/runtime suite: **63 passed**.
- Every direct test dependent on detector authorization, verified admission, verified feedback, runtime or fork proof: **337 passed**.
- Wider puzzle, curriculum and training suite: **254 passed, 59 skipped** after excluding the known live-HTTP `test_puzzle_progression.py` module.
- The excluded module produced 13 setup errors because its external base URL returned 404 for dev-login; no test in that module reached the changed code.
- The repository-mandated `test_all_flows.py` live-server script was invoked, but no local backend was running; it stopped on its first connection attempt. It was not pointed at production because later flow steps can mutate data.
- All 50 frozen positive cases rebuilt fresh verdicts and rendered the exact piece, fork square and all target squares.
- Voice audit: plain-language explanation for the 600–1500 audience, exact squares named, reusable principle retained, and no parallel coaching renderer added.
- Changed-file Python compilation passed.

## Explicitly unchanged

- no frontend component, route, visual design or API response shape;
- no accepted answer, Stockfish result, detector geometry, payoff threshold or target-value threshold;
- no persistent prompt, learner focus, plan, recurrence, mastery, skill tree or improvement claim;
- no production record, backfill, migration, feature flag, push or deployment;
- no Maia, Otter, Fathom, runtime LLM or fresh Stockfish work.

Existing stored rows will show this exact feedback only after a separately approved admission reconciliation/backfill. That write operation is outside this phase.
