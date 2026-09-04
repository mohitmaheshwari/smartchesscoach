# Hidden Opportunities Phase 3A.3 - Coverage Diagnosis

**Status:** RANKING CENSUS DEFERRED; BLINDED FALSE-NEGATIVE REVIEW READY
**Date:** 2026-09-04
**Runtime exposure:** none
**Production reads/writes:** none
**Fresh engine or model runs:** none

## Decision

Do not run the four-band production ranking census now. The existing 80-game
packet contains only one game with two exact hidden-opportunity candidates, so
ranking is not the present constraint. When one exact candidate exists, there
is nothing to rank; when two occur, the product can preserve both until a
selection study is justified.

The earlier statement that the hidden-opportunity detector has “nothing to say
in 84% of games” is also not supported. That number is game incidence for one
special Opportunity-grade layer, not recall and not total coaching coverage.
The existing verified mate/exchange/material cause path must be counted before
calling a game silent.

## Measured causal coverage

The canonical composer and the existing `VerifiedLineCause` builder were
replayed over the same 467 meaningful decisions. Both consume only complete,
legal stored continuations.

| Measurement | Result |
| --- | ---: |
| Games scanned | 80 |
| Meaningful decisions | 467 |
| Complete played/better branch pairs | 467 |
| Exact hidden-opportunity candidates | 14 in 13 games |
| Games with an existing verified line cause | 64 |
| Games with either exact cause type | **65 (81.25%)** |
| Games with neither exact cause type | **15 (18.75%)** |
| Meaningful decisions in those 15 games | **38** |

The two paths overlap in 12 games. Adding 13 and 64 without accounting for
that overlap would overstate coverage.

Among the 67 games without a hidden-opportunity candidate, 52 still contain an
existing verified line cause:

| Existing exact cause | Decisions |
| --- | ---: |
| Missed material opportunity | 54 |
| Exchange sequence | 37 |
| Allowed forced mate | 11 |
| Missed forced mate | 3 |
| **Total** | **105** |

This does not prove that every rendered caption is good. It proves that the
current evidence architecture is not silent merely because the cinematic
Opportunity-grade composer abstains.

## What remains unsupported

The 38 meaningful decisions in the 15-game exact-cause remainder have this
stored branch topology:

| Stored branch shape | Decisions | Interpretation boundary |
| --- | ---: | --- |
| No positive material difference | 28 | Usually positional, opening, endgame, horizon-limited, or evidence-insufficient; material logic cannot name the reason. |
| Better move avoids a material loss | 7 | A defensive resource, not a material-winning combination. |
| Better move wins material | 3 | The stored payoff is only +100, +200 and +100 centipawns respectively—pawn-level, not a hidden piece-winning line. |

The seven defensive cases contain three major saves in the stored horizon
(300, 500 and 300 centipawns avoided) and four pawn saves. That makes
**defensive-resource explanation** the strongest measured candidate for a
future proof family. It is not authorized by this audit and must not be
implemented merely to raise coverage.

The 28 non-material cases have a median stored loss of 131.5 centipawns; 12 are
at least 150 and five are at least 300. One is a 9,069-centipawn evaluation
swing whose stored four-ply branches do not reach a checkmate. Large engine
loss therefore does not make the causal explanation available: some cases need
a longer stored horizon, and others need canonical opening, endgame, or
positional authorities rather than a relaxed material detector.

The stored captions attached to the source were deliberately excluded from the
review packet. Most source games carry historical caption versions, so those
strings cannot establish current runtime quality or serve as a false-negative
answer key.

## Blinded review packet

`backend/data/detector_gold/hidden_opportunities_coverage_review_v1.json`
contains every meaningful decision from all 67 games where the canonical
composer abstained. It does not cherry-pick the 15-game remainder or only the
positive-material cases; doing so would bias the reviewer toward finding a
miss.

Packet contract:

- 67 anonymized game groups and 382 decisions;
- complete legal played and better stored branches with typed board events;
- no user IDs, game IDs, names, usernames, emails, dates, URLs or credentials;
- no centipawn loss, critical flag, stored label, existing caption, detector
  family, mechanism name or rejection reason;
- empty reviewer responses and no answer key;
- zero database reads, production writes, Stockfish runs or model calls.

Packet SHA-256:
`02daaf481872541d1d052388f99eb21b811b0e861e1c1d990a60fc536ce05c74`

Source SHA-256:
`63991272bc16330c85989eff35cb47dbd4e7c4eab056737341b0d0808a72c572`

## Review gate

An independent reviewer must freeze one verdict for every decision before an
answer key is created. The allowed surface grades are:

1. `hidden_opportunity` — the stored evidence proves a memorable setup,
   constraint and payoff;
2. `caption_only` — a narrower factual explanation is useful, but the full
   Opportunity-grade chain is not proved;
3. `evidence_insufficient` — the stored horizon cannot support a reliable
   teaching claim.

The review must check legality, actor and direction, recaptures, causal
ownership, horizon survival and teaching value for a 600-1500 player. It may
not infer future moves, a durable weakness, mastery or mental state.

Only after the review is frozen may the answer key reveal canonical composer
membership and calculate:

- game-level opportunity recall;
- decision-level false-negative rate;
- false negatives by evidence topology, phase and rating band;
- whether misses concentrate in defensive resources, stored-horizon limits,
  or canonical knowledge wiring.

## Product and sequencing conclusion

1. Complete Phase 8 deployment verification first; this branch does not block
   that release and contains no player-facing change.
2. Freeze and score this local false-negative review before widening any proof
   family.
3. If reviewed misses concentrate in defensive saves, scope a distinct
   defensive-resource contract. Do not weaken the material-win proof.
4. If misses are opening, endgame or positional, attach their canonical
   authorities by ID after the position fact is independently proved. Do not
   copy their content into the opportunity detector.
5. Keep the production ranking census deferred until multiple exact candidates
   occur often enough that selection changes the user experience.

This preserves the product rule already locked in the approved scope: Game
Review should always try to teach, but Hidden Opportunities must remain a rare,
truthful special layer and must never be padded into every game.

## Verification

The focused coverage, ranking and composer suite passes:

```text
14 passed in 40.21s
```

The first test invocation from the repository root failed during import because
the backend package was not on `sys.path`; no tests ran in that invocation. The
reported passing run was executed from the backend directory.
