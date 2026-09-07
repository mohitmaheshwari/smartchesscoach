# Hidden Opportunities Phase 3A.3 - Ranking Evidence Gate

**Status:** DATA GAP PROVED; BOTH-SIDES CENSUS EXPORT READY
**Date:** 2026-09-04
**Runtime exposure:** none
**Production reads/writes:** none during this local measurement
**Fresh engine or model runs:** none

## Outcome

The current deterministic proof substrate is strong enough to generate a
small set of exact Shadow candidates, but the existing grouped evidence is not
large enough to choose which candidate a human coach would feature in a game.
No ranking formula is locked and no player-facing behavior changes.

The implementation now has one canonical composer,
`build_verified_hidden_opportunity`, which applies the locked proof-family
ownership order. Validators, evidence builders, future analysis jobs, and Game
Review no longer need to recreate ownership independently. The composer does
not authorize, rank, or render a claim.

## Locked-gold coverage

| Measurement | Result |
| --- | ---: |
| Coach-labeled Opportunity positions | 24 |
| Exact positions owned by the composer | 22 |
| Exact claims on the 76 non-Opportunity controls | 0 |
| Player-facing proof-family authorizations | 0 |

The two unowned gold rows are defensive resources rather than proved material
wins:

- `00906363fd88603401ce`: the frozen note says `Qf6` forces a queen-winning
  sequence, but the stored line ends at `Qxe7` while the rook on e8 can
  recapture on e7. The whole-branch settlement correctly refuses the claimed
  queen win. A narrower safe-queen explanation may be valid; the current gold
  wording is not.
- `001d12f6e8e923e5d08d`: `Qxc6 bxc6` is an equal queen exchange that prevents
  the played branch's `Qxf3` knight loss. The frozen note says the move takes a
  loose queen, which omits the immediate recapture. A future defensive-resource
  proof may explain the simplification, but it must not call the queen free.

These rows are not converted into successes to improve recall. They require a
separate blinded adjudication and a defensive-resource contract if that
coaching grade is retained.

## Existing 80-game measurement

The versioned 80-game full-game audit was scanned through the canonical
composer:

| Measurement | Result |
| --- | ---: |
| Games | 80 |
| Meaningful player decisions with complete stored branches | 467 |
| Decisions with a positive raw material edge | 184 |
| Exact Shadow opportunity candidates | 14 |
| Games with at least one exact candidate | 13 |
| Games with at least two exact candidates | **1** |
| Candidates inside comparable games | **2** |

The raw positive-edge prefilter is intentionally much wider than the exact
proof: 52 games had two or more positive-edge decisions, but only one had two
complete causal proofs. This confirms that evaluation or raw material change
cannot stand in for chess reasoning.

One comparison game cannot discriminate chronology, largest loss, criticality,
forcingness, payoff, or causal-clarity formulas. Selecting a winner from this
packet would be selection by anecdote. The local review packet remains
versioned as a reproducible limitation and privacy regression, not as a final
ranking gold.

## Both-sides evidence path

The established production exporter now supports the mode
`hidden-opportunity-ranking`. For one player rating band it:

1. reads the stored player and opponent move-evaluation streams;
2. resolves the rating of the actual side to move;
3. keeps the existing rating-aware meaningful-move threshold;
4. legally normalizes both stored four-ply branches;
5. calls the canonical exact composer;
6. deduplicates positions that occur in both stored streams;
7. exports the complete census of games containing at least two exact
   candidates.

The output includes only one-way group keys, rating bands, FENs, stored lines,
engine metadata required for later ranking, and typed proof contracts. It
contains no source game IDs, user IDs, names, usernames, emails, dates, URLs,
PGNs, credentials, captions, or learner profiles. It performs zero writes,
zero Stockfish runs, and zero model calls.

Production command, one band at a time:

```bash
python backend/scripts/export_full_game_chess_fact_audit.py \
  600-899 hidden-opportunity-ranking
```

Repeat for `900-1199`, `1200-1499`, and `1500-1999`. The command prints
base64-encoded JSON using the existing safe transport convention.

## What remains locked off

- Do not select or tune a visible ranking formula from the one comparison.
- Do not show a Shadow proof in Game Review.
- Do not build an answer key before the coach labels are frozen.
- Do not treat a player-only audit as evidence for opponent-side quality.
- Do not add a defensive-resource detector merely to make the gold read 24/24.
- Do not alter the target-line v6 detector before its untouched v4 independent
  review is frozen and scored.

## Next gate

Run and merge the four read-only both-sides census packets. From the resulting
distribution, predeclare only ranking formulas that actually disagree on a
meaningful number of games. Then create a blinded coach packet, freeze the
labels, generate the answer key, and score truth, importance, teaching value,
memorability, and clarity separately. Only a passing proof family plus a
passing selection study can enter the existing Game Review interaction.
