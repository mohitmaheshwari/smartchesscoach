# Community Game Study — Offline Packet Amendment

**Status:** APPROVED BY MOHIT'S “GO AHEAD” FOR THE NEXT EVIDENCE GATE
**Date:** 2026-09-15
**Parent:** `docs/complete_coaching_system_community_extension_spec.md`

## Clarification

Delivery step 3 requires an actual neutral community-game packet, while the
first implementation slice correctly prohibited provider ingestion. This
amendment authorizes one bounded research acquisition only:

- read a size-capped prefix of the official Lichess rated-standard CC0 archive;
- request the same public games' already-stored Lichess analysis variations;
- retain only anonymous replay, canonical rating band and current verified
  neutral Review projections in a versioned reviewer packet;
- discard raw identity-bearing PGN rather than writing it to the repository.

This is not product ingestion. It creates no database record, route, rollout
flag, production write or player-visible community study. It runs no Stockfish,
LLM, Maia or other model. It cannot authorize the visible feature by itself.

The source is the official Lichess open database:

- archive terms and CC0 statement: `https://database.lichess.org/`;
- rated-standard monthly releases and checksums:
  `https://database.lichess.org/standard/`.

The reproducible reader version for this evidence run is
`zstandard==0.23.0`, installed in a temporary research environment rather than
added to ChessGuru's production dependency set.

## Newly measured prerequisite

The Shadow foundation originally accepted only already-neutral source events.
The live Review adapter emits learner-facing `you/your` copy, so that contract
could validate a hypothetical event but could not project a real one. Neutral
projection may now render a bounded template from an intact, fingerprint-bound
typed cause. Untyped personalized prose, stale cause fingerprints and unknown
cause kinds still fail closed.

## Exit condition

Freeze an identity-free packet of actual projections for independent coach
review. Only after that review is scored may the personal-versus-community
source mix be locked or player-visible integration begin.

## Frozen measurement

The bounded run requested 60 public analyzed-game exports after scanning 2,119
games from an 8 MiB prefix of the August 2026 archive. Forty-one games passed
the full current gate and produced 110 neutral chapters:

- 13 games have two chapters and 28 have three;
- 12 are beginner-low, 22 beginner-high and 7 intermediate;
- 49 chapters occur in the opening, 54 in the middlegame and 7 in the endgame;
- every replay and displayed chapter move is legal;
- no identity/private key, URL, email or second-person source diagnosis appears
  in the reviewer cases.

Phase location is not teaching breadth. All 110 admitted chapters come from
only two current verified cause families: 58 legal material losses and 52
missed material opportunities. No opening-knowledge, positional-plan,
endgame-principle or forced-mate chapter survived this sample. Independent
review must therefore grade both factual quality and whether these narrow
chapters form a worthwhile whole-game lesson; phase counts alone cannot be used
as evidence that the broader community-study promise is ready.

Nineteen exports abstained: eight had zero current Caption-authorized chapters
and eleven had one. The minimum remains two; the run did not weaken admission
to improve yield.

The frozen reviewer packet is
`backend/data/detector_gold/community_game_study_neutral_review_v1.json`, with
SHA-256
`08fa4dca2d127f6dda7663d883658527a28305932c635c2f598e43a342e1f6da`.
The bounded identity-bearing archive prefix and temporary decompression
environment were deleted after this packet passed the structural audit.

## Independent v1 verdict

The independent review is preserved beside the source packet as
`community_game_study_neutral_review_v1.reviewed.json` and is bound to the v1
SHA above. It changed only reviewer-response fields and review metadata; all 41
games and 110 source chapters remain byte-equivalent to v1.

- `correct_and_teachable`: 0;
- `correct_but_not_teachable`: 72;
- `unclear_or_too_generic`: 31;
- `incorrect_or_overclaimed`: 7;
- assignment-worthy: 0 of 110 chapters and 0 of 41 games.

The measured causes were shared implementation defects: the neutral renderer
discarded the verified line and move purpose, the canonical first-capture
helper could select an opponent capture as the learner's payoff, and 31
capture-on-arrival cases repeated the destination without explaining the
attacker.

## v2 repair and re-review boundary

V2 uses the identical 41-case selection fingerprint. The repair is upstream of
the packet:

- canonical best-line target selection now chooses the first initiator capture;
- legal material loss names the exact attacker and its square;
- the safer move states its verified purpose when available;
- material opportunities explain the legal sequence through the payoff;
- every chapter carries a legal SAN demonstration for the existing future
  replay interaction;
- candidate-comparison and neutral-projection versions were advanced rather
  than treating changed semantics as v1.

All 110 v2 demonstrations replay legally and all 110 explanations now contain
a board-bound cause or sequence. This is implementation evidence, not a quality
verdict. Player visibility and source-mix locking remain prohibited until an
independent reviewer scores v2.

The v2 packet is
`backend/data/detector_gold/community_game_study_neutral_review_v2.json`, with
SHA-256
`1d92050c950d3cfa2a17eae7b07208f2156096596b582f00254bef7b68def974`.
