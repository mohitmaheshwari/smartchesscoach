# Hidden Opportunities Phase 3A.7 — Quiet-Check Settlement Data Lock

Date: 2026-09-04

## Correction that triggered this lock

The Phase 3A.6 settlement was structurally blind to a quiet checking move.
Review case `c1d5d2537da9d8784fd8` ends its stored better branch with White to
move. `Qd7+` is neither a capture nor a promotion, so the capture-only search
never considered it. Every legal Black reply then permits `Qxe6`, and the
claimed material payoff does not survive.

The independent reviewer also disclosed a bug in its first horizon-search
implementation: it returned alpha/beta window bounds instead of the best
fail-soft score. The corrected search changed ten settled values but changed
no verdicts. For this lock, the frozen reviewer verdicts—not either searcher''s
numeric score—are the semantic reference.

## Evidence and candidates

The bake-off used the 97 detector candidates already adjudicated in the
frozen v3 packet. It performed no database read, production write, engine run,
Maia run, LLM call, or network call.

Evidence:

- `backend/data/corpus_snapshots/target_line_causal_quiet_check_bakeoff_v1_2026-09-04.json`
- SHA-256: `76e9489b8a75d44843ffb04341d6ecbde1e7860b81fa1872088d33330ccab179`

| Candidate | Retained | Reviewer-positive | False positive | Critical | Precision | Wilson lower | `c1d5…` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Capture/promotion only, depth 2 | 65 | 64 | 1 | 1 | 98.46% | 91.79% | retained |
| Checks only on first settlement ply, depth 3 | 49 | 49 | 0 | 0 | 100% | 92.73% | rejected |
| Quiet checks at every node, depth 3 | 49 | 49 | 0 | 0 | 100% | 92.73% | rejected |
| Quiet checks at every node, depth 4 | 59 | 59 | 0 | 0 | 100% | 93.89% | rejected |

The promotion evidence floor is at least 50 retained reviewed fires, at least
95% semantic precision, at least 85% Wilson lower bound, and zero critical
false claims.

## Locked decision

Use four settlement plies. At a quiet node, generate legal captures,
promotions, and checks. At a node already in check, generate every legal
evasion. Either side may stand pat only when it is not in check. Score exact
signed capture and promotion material from the stored-line initiator''s
perspective. Use exact minimax; do not use alpha/beta window bounds as scores.

This is the narrowest measured policy that:

- rejects `c1d5d2537da9d8784fd8`;
- retains at least 50 previously reviewed true cases;
- has zero reviewer-negative survivors and zero critical false claims; and
- clears both the point-precision and Wilson thresholds.

The first-ply-only and three-ply variants are rejected because each retains
only 49 reviewed cases. The capture-only policy is rejected because it leaks a
known critical claim. No threshold or formula was selected from intuition.

## Boundaries

This remains a bounded material verifier, not a chess engine. It can establish
that a stored material payoff survives the measured forcing-check horizon. It
does not claim to see every non-checking quiet tactic, positional resource, or
forced line beyond four settlement plies. The detector remains Shadow until a
fresh blinded holdout clears promotion independently.

The next 1,500-position production export must not run until the runtime and
independent oracle both implement this lock and a replay of the frozen v3
evidence rejects `c1d5…` with zero reviewer-negative survivors.

## Implementation verification

The gate above is now satisfied.

- Production proof version: `target_line_causal_proof.v6`
- Canonical verifier: `stored_line_verifier.v4`
- Architecture validation:
  `backend/data/corpus_snapshots/hidden_opportunities_phase3a7_target_line_validation_v6_2026-09-04.json`
  (SHA-256
  `7cd87a2ff14d7a779f1a4e1ccde3227ebfa2a1e32b9f8458f290e9bb379ea664`)
- Production-shaped frozen replay:
  `backend/data/corpus_snapshots/target_line_causal_frozen_runtime_replay_v6_2026-09-04.json`
  (SHA-256
  `f0dd528ff1ce6575eed663caa9c850704d7a577c4bcccd89b13223b20ad5d093`)
- Frozen replay result: 59 retained, 59 reviewer-positive, zero
  reviewer-negative survivors, zero critical false claims, `c1d5…` rejected,
  100% point precision, 93.89% Wilson lower bound.
- Focused verifier/proof-family tests: 54 passed.

The broader caption-fact consumer run produced 317 passes and six failures in
pre-existing caption-pipeline behaviors (forced-recapture fixture, coach-extra
copy, and empty Socratic question/hint fields). None touches the target-line
verifier, proof version, or evidence gate; they remain visible rather than
being folded into this detector change.

## Fresh holdout after the gate

Only after the frozen replay passed, the authorized read-only export ran:

- 1,500 positions from 1,500 distinct source games;
- exactly 375 positions in each of the four rating bands;
- 420 opening, 874 middlegame, and 206 endgame positions;
- 2,164 previously consumed content signatures excluded;
- zero production writes, engine runs, Maia runs, LLM calls, identities, game
  IDs, user IDs, emails, credentials, URLs, dates, or PGNs;
- combined export:
  `backend/data/corpus_snapshots/target_line_population_export_v2_2026-09-04.json`;
- export SHA-256:
  `b1ce69027e402a56768c947dd86e80aa1c7a31afd5137ec7b1c23fe7fc2d44c5`.

The canonical v6 detector found 53 fires: 17 immediate free captures, 20
persistent piece attacks, nine removed future attackers, and seven targets
entering controlled squares. All 53 are included without subsampling in the
new blind packet, alongside 30 positive-edge no-fire controls covering every
rating-band/phase cell:

- `backend/data/detector_gold/target_line_causal_pre_promotion_review_v4.json`
- SHA-256:
  `2689486856bb0c026f188f1d7a649d150cd15bc458359b1479c2a28acc6efa4f`
- 83 total blinded cases;
- detector membership, proof objects, cp loss, source identity, and labels are
  absent;
- no answer key has been created.

The packet's canonical regeneration, privacy, blinding, disjointness, verifier,
and proof-family suite passes: 62 tests.
