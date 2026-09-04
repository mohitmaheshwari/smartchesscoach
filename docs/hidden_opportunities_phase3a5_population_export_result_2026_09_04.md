# Hidden Opportunities Phase 3A.5 — Population Export Result

Date: 2026-09-04

## Outcome

The explicitly authorized production read completed without production writes,
engine runs, model calls, or identity export.

- 1,500 anonymized positions
- 1,500 distinct source game records by construction
- 1,500 unique chess-position signatures after sequential cross-band exclusion
- 375 positions in each rating band
- 445 opening, 830 middlegame, and 225 endgame positions
- 664 prior-evidence position signatures excluded
- zero overlap with the prior-evidence signature set
- every played and better branch replayed legally from its FEN
- four stored continuation plies retained for every non-terminal branch

The first local assembly attempt correctly failed closed after detecting six
cross-band duplicate chess positions. The exporter was not weakened. Instead,
each later rating band was made to exclude all positions already selected in
earlier bands, and the same authorized read was rerun. The accepted packet has
zero cross-band duplicates.

## Versioned evidence

Combined population packet:

`backend/data/corpus_snapshots/target_line_population_export_v1_2026-09-04.json`

SHA-256:

`44e535f0866ddee08d4aeeb43adccedb45a4d6eae6f774fdaa1040174f6a4989`

The four band packets are stored beside it with rating-band suffixes.

The output contains only rating band, phase, FEN, side to move, played and
better SAN, the two stored SAN continuations, and cp_loss. It contains no user
or game IDs, names, usernames, emails, dates, URLs, PGN headers, credentials,
captions, cognitive labels, or detector outputs.

## Deterministic v4 measurement

The existing v4 target/line proof was run locally over the 1,500 exported
positions using only the frozen stored continuations.

- complete two-branch evidence: 1,500
- new detector fires: 64
- positive-edge no-fire control population: 652
- non-positive-edge no-fires: 784

New fire mechanisms:

- persistent piece attack: 28
- immediate free capture: 19
- remove future attacker: 7
- target enters controlled square: 6
- exchange sequence: 4

## Expanded blinded review packet

Packet:

`backend/data/detector_gold/target_line_causal_pre_promotion_review_v3.json`

SHA-256:

`cc6b129d75fdbe4590c4f5829be57dd2818a45e11a9980ec826a99378fe21699`

The v3 packet preserves all 33 prior v4 candidates and adds the 64 population
candidates. It contains:

- 97 hidden detector candidates
- 30 hidden controls drawn from the new population
- 127 total blinded cases
- 92 distinct candidate source units
- all 12 rating-band/phase cells represented among controls
- exactly one control per source unit
- detector labels and candidate/control membership absent from every case
- cp_loss absent from every public case
- zero fire shortfall against the locked minimum of 50

No v3 answer key has been generated yet. That is deliberate: membership stays
unavailable until the independent reviewer freezes a complete response file.

## Independent reviewer protocol

Give Claude only the v3 review packet above and this instruction:

> Review every one of the 127 blinded chess cases independently. Do not inspect
> the packet builder, detector implementation, prior answer keys, validation
> snapshots, or any file that could reveal candidate/control membership. For
> each `case_id`, replay both supplied branches from the FEN and return exactly
> one verdict: `proved_target_line_payoff`, `not_proved`, or
> `insufficient_stored_horizon`. Also return `critical_false_claim` as a boolean
> and a short chess-specific `review_note`. A positive verdict requires the same
> physical setup piece and target to be followed, a target/line relation that
> distinguishes the branches, a positive causal material payoff, and no
> recapture or terminal-horizon leak that erases it. Return one response for
> every case, with no duplicates or omissions. Do not modify code.

After the complete review is frozen, Codex will generate the v3 answer key,
bind it to the packet hash, score the blinded confusion matrix, inspect every
disagreement, and run the final rendered-claim audit. Promotion remains blocked
until those steps pass.

## Verification

- exporter and replay contracts: 6 tests passed
- exact branch-evidence, packet, and historical-score contracts: 56 tests passed
- sibling proof-family packet regression contracts: 12 tests passed
- total executed in this phase: 74 tests passed

No commit, push, deployment, feature-flag change, or production write occurred.
