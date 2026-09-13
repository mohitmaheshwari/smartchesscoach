# Deterministic Teaching Intelligence — Data Lock

**Date:** 2026-09-13  
**Status:** LOCKED FOR EVIDENCE PREPARATION; PRODUCT PROOF-FAMILY IMPLEMENTATION REQUIRES THE SECOND LOCK DESCRIBED BELOW  
**Scope:** `docs/deterministic_teaching_intelligence_scope.md`

## Decision 1 — fresh development and holdout design

### Value

- Fresh development corpus: **100 complete games**.
- Fresh untouched holdout: **34 complete games**, exactly one per eligible player.
- Eligible player for this cycle: at least **eight** complete eligible games at the capture cutoff.
- Development contribution cap: **three games per player**.
- Exclude every source game in the earlier 100-game development set and earlier 42-game holdout before either new set is selected.
- Select the new holdout first by stable SHA-256 order under a new versioned tag, then select development with an exact capacity-constrained allocation under a separate new tag.
- Development rating quotas remain population-proportional at **19 / 11 / 30 / 31 / 9** games for 600–799 / 800–999 / 1000–1199 / 1200–1399 / 1400–1500. The exporter must fail rather than relax the quotas silently.
- The new development and holdout packets expose only opaque signatures. They contain no internal game identity, user identity, account name, email, URL or credential.

### Evidence

A read-only production aggregate on 2026-09-13 found:

| Measure | Result |
|---|---:|
| Complete eligible games | 6,942 |
| Eligible players | 42 |
| Games per player — minimum | 1 |
| Games per player — p25 | 31 |
| Games per player — median | 67 |
| Games per player — p75 | 185 |
| Games per player — maximum | 1,124 |
| Players with at least 5 games | 35 |
| Players with at least 8 games | **34** |
| Players with at least 10 games | 32 |

The earlier evidence design consumed at most four games from one player: one holdout game plus at most three development games. For every player starting with at least eight eligible games, excluding those four and reserving one new holdout game leaves at least three fresh games. Thirty-four players therefore provide a guaranteed development capacity of 102 games under the three-game cap, enough for the locked 100 without allowing a prolific account to dominate.

The population rating counts were 1,356 / 761 / 2,103 / 2,124 / 598. Largest-remainder allocation to 100 games produces 19 / 11 / 30 / 31 / 9. The phase population contains 959 opening-only games, 1,639 opening-and-middlegame games, 779 opening-and-endgame games and 3,565 three-phase games.

The query returned aggregates only and performed zero production writes, engine runs and model calls. It printed no identity, position or credential.

### Rejected candidates

- **A new 42-player holdout:** rejected because seven eligible players have fewer than five games. Their earlier evidence may already have consumed every available fresh game.
- **A 35-player holdout using the five-game floor:** rejected because a player with exactly five games can have four earlier games excluded and one new holdout reserved, leaving no development capacity.
- **A 32-player holdout using a ten-game floor:** feasible but rejects two independently useful player clusters without buying a needed safety property; the eight-game floor already guarantees the development cap.
- **A 150- or 200-game development corpus:** rejected for this cycle. A three-game player cap provides at most 102 guaranteed fresh games across the 34 safe players, and relaxing the cap would reintroduce prolific-player dominance.
- **A smaller 60-game development corpus:** rejected because the earlier 100-game audit produced 219 independently proposed teaching moments and exposed the coverage failure. Reducing the game count would lower phase and proof-family diversity precisely when discovery breadth is the goal.
- **Random game splitting:** rejected because it can place the same prolific player and repeated personal pattern on both sides and cannot be reproduced exactly.

### Measurement method

Read-only Python/PyMongo census executed inside the production backend container using its existing environment. Eligibility matched the existing whole-game exporter: rating 600–1500, joined non-empty game, at least eight stored V5 move rows, and a SAN, pre-move FEN and recognized phase for every row.

## Decision 2 — inherited player-experience locks

The following values remain locked from existing measured evidence. This phase does not reopen them:

- Maximum **three featured moments per game**. The candidate census found that 3,981 of 4,141 candidate-bearing games, or 96.14%, contained at most three complete candidates.
- Collapsed moment explanation: at most **two prose sentences and 32 prose words**, followed by a separate memory cue of at most **18 words**. The board replay carries additional detail; truth-changing conditions are never truncated.
- A replay continues until the claimed payoff, defence or recapture is settled. It is not cut mechanically at four plies.
- The current review selector remains **resume → active-focus match → authorized chapter richness → recency**. In the measured bake-off, this selected the active-focus game for 3/3 eligible users; newest-first selected it for 0/3.
- Candidate generation, when already available, remains **played move → stored best move → exact authoritative candidates → human-policy candidates to 80% cumulative mass, floor three, cap eight, total cap ten**.
- The Maia candidate-budget bake-off covered the observed played move 86.33% of the time with 4.33 candidates on average. Fixed five covered 86.17% with five candidates. Fixed eight added 84.8% more candidates than the selected policy for 7.17 percentage points of observed-move coverage without evidence of more unique teaching value.
- Maia/Otter may order plausible candidates only. They never determine chess truth, caption correctness, weakness, mastery or transfer.

## Decision 3 — actual product comparison

### Value

The release comparison is the **authorized rendered player experience**, not internal fact availability.

- Current and candidate reviews are projected under their real detector authorization.
- The independent chess inventory is frozen before either product version is revealed.
- A lesson counts as covered only when the visible text and replay teach the same causal fact or an independently adjudicated causal equivalent.
- Same move with a different reason does not count.
- Shadow facts are reported as research headroom and excluded from candidate product coverage.
- Primary paired unit: game, clustered by player.
- Release gate: the lower bound of a player-clustered 95% bootstrap interval for candidate-minus-current useful-lesson coverage must be above zero.
- Critical false chess claims: zero.

### Evidence

The first whole-game cycle failed because the current visible review covered 70/90 proved moments while the shared deterministic fact layer reached only a 72/90 upper bound. Game-level macro improvement was +3.947 percentage points, but its 95% player-clustered interval was −6.140 to +14.474. That result proves why internal fact counts cannot serve as the release metric.

### Rejected candidates

- **Fact-layer exact-match percentage:** rejected because it can include Shadow evidence that no player receives.
- **Best-move agreement:** rejected because two systems may recommend the same move for different reasons; the reason is the teaching product.
- **Aggregate per-position comparison:** rejected because prolific games and players would dominate confidence estimates.
- **A positive point estimate without a confidence requirement:** rejected because the previous +3.947-point estimate still included no-improvement and regression.

## Decision 4 — proof-family priority is a second data lock

No new positional, tactical, opening or endgame proof family is selected from intuition in this document.

The evidence-preparation stage must first:

1. export the fresh 100-game development packet with the current player-visible baseline withheld;
2. have Codex review each complete game before seeing ChessGuru’s captions, detector labels, selected moments or answers;
3. freeze every proposed lesson and its evidence verdict;
4. join the frozen inventory to current authorized output;
5. group uncovered proved lessons by reusable causal shape, phase and required evidence;
6. measure opportunity count, player count, current coverage, criticality and deterministic proof feasibility for every group.

Only then may a second lock select which shared proof families enter product implementation. The comparison must include at least:

- **frequency-first:** highest number of uncovered proved lessons;
- **player-reach-first:** highest number of distinct players affected;
- **safety-and-feasibility-first:** strongest independently verifiable consequence with hard negatives available;
- **balanced:** player reach, useful opportunity count, consequence importance and proof feasibility reported separately rather than hidden in one unexplained score.

The winning policy and every numeric floor must cite the fresh development distribution. Critical false-claim classes are mandatory regressions regardless of frequency. A family may not be chosen merely because it is easy to implement or resembles an opened holdout failure.

Until that second lock exists, product implementation may not add a new proof family, recognition rule, template, ranker or authorization.

## Decision 5 — validation thresholds inherited without reinterpretation

- At least 60 blinded coach comparisons and at least 39 strict preferences for the candidate version, excluding ties; Wilson 95% lower bound above 50%.
- No admitted cause family with a majority preferring the baseline when at least ten examples exist.
- At least 30 paired first-attempt player-recognition records, exact paired test at `p < 0.05`, post-review correct-rate Wilson 95% lower bound above 50%, and no answer leakage.
- At least 50 independently reviewed visible claims and at least 95% semantic precision with Wilson 95% lower bound at least 85% for a player-facing proof family.
- Zero critical false claims overrides every average score.
- Practice, hints, reveal and replay remain separate from independent recognition and later unassisted-game transfer.

## Authorization boundary

This lock authorizes only the evidence-preparation slice:

- extend the existing whole-game exporter to generate the fresh, disjoint development packet and sealed holdout membership;
- add overlap, privacy, determinism and answer-hiding tests;
- freeze the current authorized player-visible baseline separately from the blind Codex packet;
- conduct and freeze the independent Codex complete-game review;
- produce the proof-family opportunity report and second data-lock candidates.

It does **not** yet authorize new product proof families, detector logic, chess-content tables, templates, rankers, UI behavior, historical regeneration, rollout or deployment.

