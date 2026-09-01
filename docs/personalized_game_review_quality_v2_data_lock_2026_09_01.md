# Personalized Game Review Quality V2 — Data Lock

**Status:** LOCKED for technical design  
**Date:** 2026-09-01  
**Source:** read-only production MongoDB measurement on deployed commit `7bc99da4ee61542ca9050dc7b698368045d07835`  
**Reproducibility:** `backend/scripts/measure_personalized_game_review_quality_v2.py`  
**Raw aggregate:** `backend/data/corpus_snapshots/personalized_game_review_quality_v2_2026-09-01.json`

No Stockfish run, LLM call or database write was performed. Credentials remained inside the production backend container. The snapshot contains no user IDs and includes only one product-owner-approved regression position.

## 1. Population

The measurement found 947 current-schema (`schema_version >= 16`) `simple_hang` observations across 813 games. Stored V5 data joined to 943 events; four games had no V5 payload. Of those 943 events, 106 games contained at least two competing `simple_hang` chapters.

This is large enough to lock deterministic proof requirements and to compare ranking candidates. It is not sufficient to declare a ranking winner without independent importance labels.

## 2. Cause proof lock

The deployed observation proves that some material can be lost by legal exchange, but it does not store the affected piece, square, attacker or winning capture. Quality V2 must rebuild those facts from the post-move board using the existing canonical `legally_hanging_pieces` legal-exchange authority.

That independent verifier proved an exact cause for 913 of 943 joined events (96.82%). It found:

- 204 events where the best move verifiably moves the affected piece out of danger;
- 193 where it verifiably adds a defender;
- 68 where it verifiably removes the exact attacker;
- 448 where the hang is proven but that narrow best-move purpose is not proven.

Twenty-eight stored `simple_hang` events no longer pass the canonical legal-exchange proof, and two contain a move that cannot be replayed in the joined V5 position. They are evidence of semantic drift, not permission to weaken the verifier.

**Lock:** a V2 `simple_hang` cause may name a piece, square, attacker and punishment only when legal-exchange truth rebuilds them. A best-move purpose may be named only when the move saves the affected piece, removes the exact attacker or adds a defender and the piece is safe afterward. If the cause fails, V2 stays off and the unchanged legacy chapter remains available. If only the purpose fails, the chapter keeps the verified cause and omits the purpose clause.

This preserves 96.82% of joined content rather than requiring the stored first PV move to perform the capture, which covered only 57.79% and would have hidden too much valid teaching.

## 3. Reflection-purpose lock

The played move had a board-possible attacking purpose in 734 of 943 events (77.84%). The current quick-tag output included either existing attack-intention option in only 339 events (35.95%). There were 464 events (49.20%) where an attacking purpose was board-possible but the current reflection omitted it.

The audited `Bh6` move is one of them: the bishop pressures the king ring by attacking `g7`, but category routing produces no attacking-intention option.

**Lock:** do not add another reflection vocabulary. Reuse the existing stable option IDs, but select options from verified move purposes in the cause package rather than the broad mistake category. “Not sure” and “None of these” remain mandatory. A purpose option means “this was possible in the position,” never “the system knows this was your intention.”

The first supported purpose facts are check, capture, development, pressure on the opponent king ring and a direct attack on an opponent piece. Only legal-board facts can activate them. The player’s answer is stored separately and cannot alter objective chess truth.

## 4. Practical-framing and ranking lock

Raw `cp_loss` is not a practical turning-point measure. Across the joined events its median was 453cp, while median stored win-probability loss was 0.244. The audited `Bh6` event lost 8,701cp on mate-score scale but changed win probability by only 0.046, kept the player in a winning state and did not change decisiveness.

On the 106 multi-event games:

| Candidate | Selected a true decisiveness change | Selected a stayed-winning event | Mean selected win-probability loss |
|---|---:|---:|---:|
| Deployed teaching-first formula | 83.02% | 1.89% | 0.3372 |
| State-transition-first | 91.51% | 0.00% | 0.3419 |
| Teaching-then-state | 91.51% | 0.00% | 0.3419 |

The practical candidates chose a different top event from the deployed formula in 12.26% of games. The two practical formulas agreed on this corpus because teaching completeness did not discriminate their top events.

**Lock:** practical wording must use `mover_state_before`, `mover_state_after`, `decisiveness_changed`, `stayed_winning` and `mover_winprob_delta`. Raw `cp_loss` cannot independently trigger “turning point,” “threw the game” or equivalent language.

**Ranking decision:** do not change visible ranking in V1 from proxy metrics alone. Carry the state-transition-first candidate into the blinded validation packet and ask coaches to judge the better moment on the 13-game disagreement set implied by this population. A final formula is locked only from those labels. This is an explicit no-change decision, not an unresolved numeric guess.

## 5. Caption conflict lock

Six of 943 authorized `simple_hang` captions (0.64%) used forcing/check language even though the stored best move was neither a check nor a capture. One was routed through `distilled:missed_mate`; it is the approved `Bh6` regression.

**Lock:** once an authorized `simple_hang` cause package is present, generic mate-score or forcing-language templates cannot replace its cause. Caption, visual, reflection and takeaway must be projected from that package or the V2 projection abstains.

## 6. Deriver identity lock

Zero of 166,417 current-schema observations carries `deriver_identity`, `deriver_version` or `deriver_hash`. A schema number therefore cannot distinguish two implementations with different semantics.

**Lock:** every new or regenerated observation stores both:

- a human-readable semantic version; and
- a deterministic manifest SHA-256 over the observation deriver plus its semantic dependencies and locked constants.

The manifest, not the schema number alone, is the cache identity. Existing observations without that identity may remain historical inputs, but V2 verifies their board cause at read time and may not present them as reproducible V2 evidence.

## 7. Detector-promotion packet order

Coverage does not authorize a detector, but it tells us which evidence packet has the largest potential return. The highest-reach Shadow families are:

| Quality ID | Games | Users | Decision |
|---|---:|---:|---|
| `gap:piece_safety:small_slip` | 1,717 | 38 | Do not prioritize: the label is intentionally nonspecific and has no stable lesson cause. |
| `gap:piece_safety:tactical_seq_loss` | 1,533 | 43 | Promotion packet priority 1: high reach and a concrete forcing-sequence hypothesis. |
| `gap:king_safety:*` | 1,498 | 39 | Do not promote wildcard; split into exact causal families first. |
| `gap:missed_tactic:missed_generic_tactic` | 992 | 40 | Do not prioritize generic label; prefer named tactical proof families. |
| `gap:king_safety:ignored_king_attack` | 915 | 42 | Promotion packet priority 2 after exact threat/counterfactual proof is defined. |
| `gap:opening_knowledge:*` | 913 | 43 | Do not promote wildcard; exact curriculum detectors remain the authority. |
| `gap:missed_tactic:missed_pin` | 309 | 31 | Promotion packet priority 3 because it is named, teachable and already has geometric infrastructure. |
| `gap:missed_tactic:missed_fork` | 197 | 30 | Promotion packet priority 4 after the pin packet, using existing fork proof. |

All remain Shadow until their existing precision, recall, true-negative and adversarial gates pass. Feature code cannot change these grades.

## 8. Approved regression truth

For game `100897b9-0989-47db-b114-fe7064cecd4d`, move 25:

- played move: `Bh6`;
- best move: `Rd1`;
- affected piece: white rook on `a1`;
- attacker: black knight on `c2`;
- legal winning capture: `Nxa1`;
- material available by legal exchange: 500cp;
- verified best-move purpose: move the affected rook out of danger;
- played-move purpose option: pressure the king ring;
- practical state: winning before, winning after, stayed winning, no decisiveness change;
- forbidden V2 claim: `Rd1` checks, captures, or is a forcing move against the king.

This exact packet is mandatory in unit, contract and frontend projection tests.
