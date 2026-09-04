# Hidden Opportunities Phase 3A.5 — Population Export Data Lock

**Status:** LOCKED BEFORE EXPORT CODE  
**Date:** 2026-09-04

## Decision locked

Export **1,500 anonymized stored-evidence positions from 1,500 distinct
production games**. Selection is detector-label-blind. Run the v4 detector
locally after export and retain every independent fire for the next blinded
packet.

The evidence target is at least **80 total candidate fires**: the existing 33
plus at least 47 new independent fires. Eighty is not a replacement promotion
threshold; it is a stronger evidence target above the existing minimum of 50.

## Evidence

The corrected offline population contains 33 fires among 563 complete branch
pairs:

- measured fire rate: 5.8615%;
- 95% Wilson lower-bound fire rate: 4.2038%;
- additional fires needed for an 80-fire set: 47.

Exact binomial calculations for finding at least 47 new fires:

| Exported positions | At measured rate | At Wilson lower-bound rate |
| ---: | ---: | ---: |
| 800 | 51.47% | 1.49% |
| 1,000 | 95.23% | 23.72% |
| 1,200 | 99.90% | 70.97% |
| 1,400 | approximately 100% | 95.40% |
| **1,500** | **approximately 100%** | **98.65%** |
| 2,000 | approximately 100% | approximately 100% |

An 80-fire review can tolerate four rejected candidates while retaining 95%
precision, and 76/80 has a 95% Wilson lower bound above the locked 85% floor.
The final gate still uses the observed review result, never this forecast.

## Rejected candidates

- **800:** only a coin flip at the measured rate and effectively certain to
  miss the target at the lower-bound rate.
- **1,000:** attractive at the point estimate but only 23.72% at the
  lower-bound rate.
- **1,200:** still leaves nearly a 30% lower-bound failure risk.
- **1,400:** valid, but the additional 100 positions raise lower-bound success
  from 95.40% to 98.65% for little export cost.
- **2,000:** stronger statistically, but adds 500 positions and approximately
  21 lower-bound candidate fires beyond what this gate needs, increasing
  reviewer burden without changing the decision boundary.

## Selection contract

1. Read only already-stored Stockfish evidence. Never run Stockfish, an LLM,
   Maia, or another engine.
2. Use the existing rating-aware meaningful-decision thresholds; no new
   cp-loss threshold is introduced.
3. Require a legal FEN, played move, better move, and two complete legal stored
   continuations of at most four plies each.
4. Select at most one position from any source game.
5. Select 375 positions per rating band: 600–899, 900–1199, 1200–1499, and
   1500–1999.
6. Within every rating band, guarantee at least 50 opening, 50 middlegame, and
   50 endgame positions, then fill the remaining 225 by a deterministic hash
   of chess content.
7. Exclude every position signature already present in the architecture,
   v1/v2 review, or earlier full-game audit packets.
8. Selection may not inspect detector output, current caption, stored cognitive
   label, user identity, game result, or player name.
9. Output only FEN, side to move, played/better SAN, their stored continuation
   SAN, cp loss, rating band, and phase. Source identifiers never leave the
   production process.
10. The exported JSON must fail closed if an email, URL, credential-shaped
    value, forbidden identity key, duplicate position, duplicate source game,
    illegal move, incomplete cell, or unexpected record count is found.

## Privacy and authority

The user's 2026-09-04 authorization is interpreted narrowly as one read-only
export under this contract. It permits no production write, source identifier,
email, username, game ID, user ID, URL, credential, deployment, feature-flag
change, or application-container mutation.

The resulting data can expand a Shadow evidence packet only. It cannot promote
the detector or alter captions until an independent blinded reviewer and the
rendered-claim gate both pass.

## Measurement method

The rate comes from
`target_line_causal_pre_promotion_review_v2.json`: 33 v4 fires among 563
complete independent stored-branch pairs. Binomial tail probabilities use the
observed rate and its two-sided 95% Wilson lower bound.
