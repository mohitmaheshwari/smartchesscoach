# Hidden Opportunities Phase 3A.2 — Target/Line Proof Result

**Status:** PASS — SHADOW ONLY  
**Date:** 2026-09-03  
**Scope:** first causal proof family only; no player-facing rollout

## What was implemented

Phase 3A.2 extends the Phase 3A.1 branch traces with persistent physical-piece
identity and exact attacked squares. Identity survives ordinary moves,
captures, castling, en passant, and promotion. `caption_facts.py` then composes
five generic, deterministic mechanisms:

- a piece establishes an attack and later captures the same target;
- a target enters a square already controlled by the same piece;
- an exact capture → recapture → recapture exchange sequence;
- the better move removes the exact piece that causes a later loss in the
  played branch.
- an exact immediate loose-target capture backed by the canonical free-piece
  proof.

Every proof carries typed setup, constraint, and payoff steps; both complete
branch traces; the objective material difference; exact target identity and
value; a deterministic fingerprint; and any separately verified supporting
proof IDs. The composer does not author prose or infer a named motif.

## Independent result

The standalone oracle rebuilt all emitted moves, captures, identities, attacked
squares, and material changes directly from each raw FEN and legal move list.
It does not call the stored-line verifier for those checks.

| Gate | Result |
| --- | --- |
| Locked packet | 100 positions |
| Human-gold first family | 9 positions |
| Proved within the stored horizon | 8/9 |
| Total proof fires | 10 |
| Gold true opportunities | 10/10 |
| False fires across 76 non-opportunities | 0 |
| Precision | 100% |
| Wilson lower bound | 72.25% |
| Branch reversals | 10/10 rejected |
| Focused branch/proof tests | 37 passed after V3 exchange tests |
| Stage 1 mate + ten-game gold | 34 passed |
| Broad caption/review contracts | 351 passed, 26 skipped; same 6 baseline failures |
| New broad regressions | 0 |
| Protected surface authorizations | none |
| Fresh engine / production read / database write | 0 / 0 / 0 |

The two additional valid fires are forcing-tempo cases from the next locked
family. `03eccd1bf3d294170e7f` removes an exact future attacker;
`039bd832a639d9c2f8ab` removes the bishop before it takes the queen. The latter
also exposed and fixed a composer bug: a below-floor pawn chain could mask a
later eligible queen-loss chain. The existing mechanism priority is preserved,
but the composer now selects the first chain that actually satisfies the
locked payoff floor.

### V3 legal-exchange correction

The first independent population pass exposed ten fires where an attractive
capture was later recaptured, or where the stored line ended while a legal
recapture could erase the material payoff. V2 treated every available
end-of-horizon capture pessimistically. V3 now resolves the complete legal
capture sequence on that square. Profitable recaptures still erase false
stories, while nominal recaptures that lose the recapturing piece do not hide
a real opportunity.

This correction also removed `00906363fd88603401ce` from the architecture
fires. The human-gold idea is real, but the stored line stops one move before
the queen exchange is resolved. The detector now records the honest result:
true idea, insufficient stored proof.

## False friends now rejected

- both candidate moves recapture the same knight;
- an equal-looking liquidation with no clean branch edge;
- an apparent knight fork whose knight is immediately captured;
- quiet piece pressure whose stored horizon proves only a pawn capture;
- broken or illegal continuations;
- every emitted proof with the branches reversed;
- target payoffs that also occur in the played branch for mechanisms where
  absence is required.

## Compatibility

The stored trace schema is now `stored_line_verifier.v3`. Phase 3A.1 was
recertified after the identity enrichment: 200/200 independently replayed
traces still match, and default `VerifiedLineCause` contracts have zero drift.
The legacy runtime packet and earlier Stage 1 mate-direction work remain
separate regression gates and were not replaced.

That inherited mate gate also exposed three stale strict-verifier fixtures.
They now carry canonical branch-owned mate evidence. The verifier recognizes
“missed the finish” and “allows Qg4#” without confusing a terminal move inside
a demonstrated line with a claim that the played move delivered mate. It also
reports both direction and terminal-move violations when both claims are
wrong. The Stage 1 and ten-game gold suites pass 34/34 after this repair.

## Why this is not deployed

Ten reviewed architecture positives cannot satisfy the existing promotion packet. The
Wilson lower bound is 72.25%, below the locked 85% Caption bar, and the source
packet is an architecture sample rather than a population holdout. The family
is registered as `review:target_line_causal_proof` at Shadow grade. It can be
measured internally, but cannot influence captions, prompts, plans, or mastery.

The V1 machine record preserves the pre-horizon result. The current record is
`backend/data/corpus_snapshots/hidden_opportunities_phase3a2_target_line_validation_v3_2026-09-03.json`.

## Independent pre-promotion population result

The next offline pass used two already-versioned anonymized sources: 467
meaningful decisions from 80 full games and 100 cases from an earlier cause
packet. Three decisions overlapping the architecture gold were excluded. No
production read, engine run, LLM call, identity, or database write was used.

| Measurement | Result |
| --- | ---: |
| Cases scanned | 567 |
| Complete independent branch pairs after overlap removal | 563 |
| V3 candidate fires | 34 |
| Distinct candidate source games | 29 |
| Hard positive-edge no-fire controls available | 209 |
| Blinded controls selected | 30 |
| Blinded review cases | 64 |
| Caption fire minimum | 50 |
| Remaining fire shortfall | 16 |

All 34 fires are retained; none is sampled away. The one added fire is the
independently checked `Nxg5 ...Ne4 ...O-O-O` case: `Nxe4 dxe4` makes the
nominal knight recapture material-neutral, so the earlier bishop capture
remains real. The 30 controls cover every
observed rating-band/phase stratum in the full-game corpus, limit repeated
positions from one game, and add seven distinct source games from the older
packet. Detector status, mechanism, proof object, cp loss, source name, stored
classification, and identity are absent from the reviewer cases.

The deterministic packet is
`backend/data/detector_gold/target_line_causal_pre_promotion_review_v1.json`.
It is a **pre-promotion** artifact: independent adjudication has not happened,
the 50-fire minimum is not met, and no final rendered claim has been audited.

## Next bounded step

Acquire at least 16 additional independent fires with both complete stored
branches, append them through the same deterministic selection contract, and
then send the blinded packet for independent chess adjudication. Only after at
least 50 reviewed fires, 20 reviewed true negatives, ≥95% precision, ≥85%
Wilson lower bound, zero critical adversarial failures, and a final-rendered-
claim audit may this family become visible.
The other three locked proof families are now implemented and independently
validated as separate Shadow owners. Their sparse population supply does not
change this family’s promotion boundary.
