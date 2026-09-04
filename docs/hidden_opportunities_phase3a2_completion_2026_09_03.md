# Hidden Opportunities Phase 3A.2 — Completion Record

**Status:** IMPLEMENTATION COMPLETE; ALL FOUR FAMILIES SHADOW  
**Date:** 2026-09-03

The entire 24-position hidden-opportunity architecture lock is now represented
by four separately owned deterministic proof families. This work extends—
and does not replace—the earlier branch evidence, strict caption verifier,
ten-game caption gold, openings/traps/endgames content, and personalized
review architecture.

| Family | Gold ownership | Architecture precision | Independent population fires | Proof version |
| --- | ---: | ---: | ---: | --- |
| Target and line geometry | 8 direct + 2 forcing cases | 10/10 | 34 | v3 |
| Forcing tempo / move order | 6 direct + 2 target-owned | 6/6 | 3 | v2 |
| Endgame / promotion geometry | 4 | 4/4 | 1 | v2 |
| Board transformations | 3 | 3/3 | 0 | v1 |

The target family intentionally abstains on one genuine human-gold idea whose
stored line stops before two legal rook recaptures. Across the composed four
families, all 24 gold opportunities have an owner or an explicit
horizon-limited abstention; none is silently converted into a player claim.

Every family independently records:

- legal replay from the raw FEN and stored SAN;
- persistent physical-piece identity;
- played-versus-better branch difference;
- adversarial branch reversal rejection;
- zero false fires across the 76 locked non-opportunities;
- zero protected player-surface authorizations;
- zero production reads, database writes, fresh engine runs, or LLM calls.

The shared horizon rule now resolves the complete legal capture exchange
instead of treating every nominal recapture as decisive. This semantic change
is versioned in target v3, forcing v2, and endgame v2. All affected blinded
population packets were regenerated after the change.

Final verification: 53/53 focused proof-and-packet tests pass. The broader
deterministic caption/review suite reports 351 passed, 26 skipped, and the same
six pre-existing caption-boundary fixture failures; there are zero new
failures. All four standalone independent validators pass.

## Not a rollout

No family meets the existing Caption promotion evidence bar. There is no
deployment, no feature flag change, and no renderer, planner, mastery, learner
profile, puzzle grader, or public API wiring in this phase. The next product
step is independent blinded adjudication plus additional stored-branch supply,
not relaxing these proofs to manufacture coverage.
