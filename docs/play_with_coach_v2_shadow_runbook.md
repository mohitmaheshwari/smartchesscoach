# Play with Coach V2 — Shadow Runbook

**Status:** implemented default-off; not authorized for production enablement or player-facing use
**Schema:** `pwc_v2_shadow.v1`
**Policy bake-off:** `pwc_v2_policy_bakeoff.v1`

## What this release does

- Pins read-only V2 shadow eligibility when an eligible Unified V1 session starts.
- Adapts an already verified Unified V1 coaching decision into the proof-carrying V2 candidate contract.
- Independently adapts exact-position opening, opening-plan, trap, and endgame proofs already owned by the canonical curriculum verifier. The adapter performs no second engine search and owns no curriculum data.
- Runs all three proposed conductor policies on the same admitted candidate list.
- Stores the comparison only inside the existing `coaching_decisions` evidence record.
- Returns exactly the same player response with shadow enabled or disabled.
- Fails open for the game and for live Unified V1 coaching if shadow construction fails.

It does not expose a V2 experience, choose a conductor, alter a move, generate a second player message, or count shadow output as learning.

## Current measurement limit

Packets can now contain both the verified Unified V1 decision and one or more independently verified exact-position curriculum candidates. This makes real multi-candidate policy comparison possible when a mistaken move occurs at a canonical opening, opening-plan, trap, or endgame decision point.

Coverage is deliberately narrow: a merely similar position, an unmatched engine move, invalid engine evidence, an ambiguous curriculum identity, or an unverified canonical line produces no admitted curriculum candidate. Threat, positive-transfer, positional, and time adapters still require their own truth-preserving mappings. `comparison_possible` remains a measured report outcome, never an assumed release claim.

## Exact-curriculum latency lock

**Decision:** the exact-curriculum adapter receives at most 25 ms on a live turn. If it does not finish, Unified V1 continues unchanged and the packet records `canonical_curriculum:timed_out`.

**Evidence (2026-09-16, local Windows host):** three fresh-process calls took 980.05, 1,039.78, and 1,168.34 ms while building immutable indexes. After warm-up, 100 threaded calls measured p50 1.02 ms, p95 1.26 ms, p99 1.58 ms, and max 4.37 ms. The 25 ms cap gives more than 5.7x headroom over the measured threaded maximum while guaranteeing that cold construction cannot add a one-second delay to the player.

**Rejected caps:** 10 ms offered only about 2.3x headroom over the observed threaded maximum; 50 ms doubled worst-case player delay without recovering cold calls. This is an operational shadow budget, not a chess-quality threshold.

## Flags

Both compose files pass these variables to the backend:

```text
PWC_V2_SHADOW_ENABLED=false
PWC_V2_SHADOW_ROLES=admin,super_admin
```

The global flag is a kill switch. A user can be explicitly included or excluded with `feature_flags.pwc_v2_shadow`, but an explicit include cannot override the global kill switch. Shadow also requires the session to resolve to `unified_v1`; it cannot select or expose a V2 runtime.

No flag should be enabled on production until the full backend image passes the repository core flow suite and the deploy owner explicitly authorizes the cohort.

## Read-only report

Run inside the backend environment with the intended read-only Mongo credentials:

```bash
python scripts/report_pwc_v2_shadow.py --examples 25
```

Optional arguments:

- `--limit N` caps the number of sessions read.
- `--examples N` caps disagreement cases containing candidate evidence.
- `--output PATH` writes the JSON report to the named internal artifact.

The report reads only `coach_sessions`. It checks that packets are never player-visible, stored counts match contents, every policy is present, each winner belongs to the admitted candidate set, and the disagreement flag matches the recorded winners. It reports source/category coverage, rejections, adapter completions/timeouts, rating-band coverage, policy winners, and disagreement examples. It always emits `conductor_choice_authorized: false`; human review plus the lock-via-data decision is a separate gate.

## Rollback

Set `PWC_V2_SHADOW_ENABLED=false` and restart the backend. New sessions will not pin shadow. Existing sessions may continue recording read-only packets because rollout state is immutable during a game; this cannot change player output. Do not edit active session versions in place.

## Next gate

Before any player-facing V2 work:

1. Collect exact-curriculum shadow evidence and add the next independently verified adapter only from an existing proof owner.
2. Confirm the report has structurally clean multi-candidate turns across rating bands and game phases.
3. Review disagreements and hard negatives with a strong human player.
4. Lock the conductor policy and numeric guardrails from measured evidence.
5. Record Sign-off Gate A in the V2 spec.
