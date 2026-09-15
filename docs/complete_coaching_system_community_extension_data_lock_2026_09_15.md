# Complete Coaching System — Community Extension Data Lock

**Status:** LOCKED FOR THE SHADOW FOUNDATION
**Date:** 2026-09-15
**Parent scope:** docs/complete_coaching_system_scope.md
**Evidence packet:** backend/data/corpus_snapshots/full_game_chess_fact_audit_v1_2026-09-03.json
**Evidence packet SHA-256:** 69ed59d5f5448da4651cefec2109c10aee0563aaba118ac3dc9c14b908984ca6

## Decision locked

The first community-game selector must apply these decisions in order:

1. admit only a legally replayable game with approved source provenance and a current safe GameTeachingPlan projection;
2. require at least two independently authorized, presentation-safe teaching chapters;
3. require the learner's existing canonical rating band for the first pool;
4. prefer a game containing at least one chapter for the learner's canonical active focus;
5. among those games, prefer broader game-phase coverage;
6. then prefer more focus-matching chapters and more authorized chapters;
7. exclude studies the learner already completed or explicitly left for later;
8. use a stable opaque identity only as the final deterministic tie-breaker.

No popularity, player fame, raw centipawn loss, largest blunder or spectacularity score enters the formula. No cross-source recency weight is introduced until source-mix evidence exists.

## Evidence

The existing anonymized packet contains 80 legally replayed complete games: 20 in each of four research rating strata and five from each opening, tactical, endgame and general stratum. It contains no source IDs, user IDs, names, usernames, emails, dates, URLs, PGN headers or credentials.

The packet's 600–899 / 900–1199 / 1200–1499 / 1500–1999 strata are sampling proxies, not a new product taxonomy; two of their boundaries cross ChessGuru's live bands. Runtime admission and learner matching must import the canonical keys and boundaries from deterministic_coach_service.RATING_BANDS. The research table below supports the value of rating fit, but must never be copied into runtime code as band authority.

Chapter supply from the stored teaching projection was:

| Minimum teaching chapters | Eligible games | 600–899 | 900–1199 | 1200–1499 | 1500–1999 |
|---|---:|---:|---:|---:|---:|
| 1 | 66 | 15 | 17 | 16 | 18 |
| 2 | 54 | 12 | 12 | 13 | 17 |
| 3 | 36 | 6 | 8 | 7 | 15 |
| 4 | 27 | 2 | 6 | 6 | 13 |
| 5 | 24 | 2 | 6 | 5 | 11 |

Two chapters is the last floor before the largest supply cliff: moving from two to three removes 18 of 54 otherwise useful games and halves beginner supply from 12 to 6. A one-chapter item remains useful as a position lesson, but does not earn the whole-game-study promise.

Fifty-eight packet games supplied a deterministic pseudo-learner profile with a dominant stored gap. Each formula selected from the other games:

| Formula | Focus match | Same rating band | Mean matching chapters | Mean total chapters | Mean phase breadth | Unique games selected |
|---|---:|---:|---:|---:|---:|---:|
| Rating first | 33/58 | 58/58 | 1.40 | 8.81 | 1.97 | 8 |
| Focus first | 58/58 | 15/58 | 3.53 | 8.79 | 2.19 | 9 |
| Balanced | 58/58 | 58/58 | 2.40 | 6.90 | 2.03 | 19 |
| Spectacle first | 41/58 | 14/58 | 0.91 | 6.00 | 1.02 | 2 |

The balanced formula is locked. It preserved both focus relevance and rating fit in every measured pseudo-profile and selected more than twice as many distinct games as either single-axis formula. Spectacle-first selection collapsed to two repeated games and produced the weakest teaching fit.

## Source policy locked

- External V1 source: only the official Lichess open database released under CC0. Store provider, release identifier, source checksum and license with every admitted game.
- Chess.com cross-user imports: excluded. Chess.com's current agreement restricts commercial, derivative, automated and competing educational uses without written authorization. A public game record is not treated as a commercial reuse license.
- ChessGuru games: private by default. A game may enter community teaching only after a versioned explicit opt-in, identity removal, withdrawal/deletion behavior and retention rule exist.
- Future ChessGuru human matches: both players must separately consent before the game can enter the reusable study pool. Match participation alone is not publication consent.

Official sources reviewed on 2026-09-15:

- https://database.lichess.org/
- https://www.chess.com/legal/user-agreement
- https://www.chess.com/legal/updates

This is a product source policy, not legal advice. Any change to provider terms reopens admission for that provider without invalidating already stored analysis evidence.

## Human-match mode locked

The first human-opponent mode is invite/scheduled, not instant anonymous matchmaking. The versioned acquisition baseline measured only 31 non-admin users across any direct action in the preceding 30 days, with inconsistent activity authorities. That is enough to reject a reliable instant-queue promise, but not enough to invent a wait-time target.

Competitive games are unassisted by default. Any coached variant must be explicitly named, accepted by both players and mechanically symmetric.

## Limits

The 80-game packet uses stored teaching-content presence as the offline proxy. Runtime eligibility must be stricter: every displayed chapter must resolve through the current player-facing fact and caption authorization path. The locked formula does not promote a detector, authorize a caption or admit a game by itself.

No player-visible rollout is authorized by this lock. The first implementation runs in Shadow until Mohit and the coach reviewers judge a blinded packet of the actual neutral community projections.
