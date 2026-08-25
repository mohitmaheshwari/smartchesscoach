# `simple_hang` Corpus Evidence — 2026-08-25

Pulled from production (`72.60.204.176`, `chess_coach`) via SSH on 2026-08-25.
Corpus facts only. **No behavioural or conversion metric appears here** — those
were discarded as baselines per the 2026-08-25 decision that pre-release
engagement data is not representative.

Canonical detector: `move_observation_deriver.py` `SCHEMA_VERSION = 16`
(v16, 2026-07-05 — `simple_hang` upgraded from attacker>defender COUNT to SEE).

---

## 1 · `piece_safety` observations by schema version and subtype

`move_observations` total: **421,464**

| schema_version | observations | share |
|---|---|---|
| 16 (current, SEE) | 149,886 | 35.6% |
| 15 (pre-SEE) | 268,968 | **63.8%** |
| 9 | 2,555 | 0.6% |
| 12 | 43 | — |
| 11 | 12 | — |

Top subtypes overall: `None` 380,719 · `small_slip` 7,939 ·
`tactical_seq_loss` 5,413 · `unverified_hint` 5,084 · `generic_oversight` 3,410 ·
`missed_generic_tactic` 3,103 · `ignored_king_attack` 3,008 ·
**`simple_hang` 2,003** · `generic_structure_slip` 1,791.

## 2 · Current-schema (v16) `simple_hang`

| metric | value |
|---|---|
| events | **858** |
| distinct games | **732** |
| distinct users | **40** |
| share of all v16 observations | **0.57%** |
| v16 coverage | 4,585 games, 46 users |

## 3 · Recurrence per user (v16)

| threshold | users |
|---|---|
| ≥1 | 40 |
| ≥2 | 37 |
| ≥3 | 35 |
| ≥5 | 31 |
| ≥8 | 25 |
| ≥10 | 21 |
| ≥15 | 17 |
| ≥20 | 13 |
| ≥30 | 10 |

Median per user: **10**. Top counts: 158, 90, 61, 53, 45, 44, 39, 31, 31, 30.
Per-game rate ranges **0.11 – 0.68** hangs per analysed game.

**Users with ≥10 analysed v16 games and zero `simple_hang`: 0.**
The behaviour is universal among active users — which also means there is no
natural "already clean" control group inside the corpus.

## 4 · Rating band

| band | hangs | v16 moves | rate | users |
|---|---|---|---|---|
| <1000 | 81 | 3,798 | **2.13%** | 11 |
| 1000–1399 | 76 | 27,843 | 0.27% | 6 |
| 1400–1799 | 27 | 11,860 | 0.23% | 5 |
| 1800+ | 11 | 3,143 | 0.35% | 3 |
| **unknown** | **663** | 103,242 | 0.64% | **38** |

**77% of hangs (663/858) fall in `unknown`** because `games.user_rating` is
absent for those `game_id`s. Rating-band targeting cannot be relied on for this
cohort until that field is backfilled.

## 5 · Candidate comparable-decision denominators

Random v16 moves, independent SEE (≥150cp), n = 500–600 per run.

| denominator | size | usable? |
|---|---|---|
| **D1** every v16 user move | 149,886 | Too broad — avoiding a hang is the default. |
| **D3** "a hang was available in this position" | **86.8%** of moves | **Unusable.** Nearly always true; carries no information. |
| **D_live** moved a piece ≥knight onto an opponent-attacked square | **16.3%** of moves | **Usable.** ≈6–7 live decisions per 40-move game. |

Within **D_live**: **handled 71.4%**, **missed (lost ≥150) 28.6%**.

Causation split (did the *move* create the hang, vs already loose):

| | share of moves |
|---|---|
| move created a new hang | 3.5% – 5.0% (sampling range) |
| already hanging before the move | ~9% |
| clean | ~86% |

## 6 · Board-correctness sample (independent re-verification)

260 v16 `simple_hang` events re-checked with an independently implemented SEE
(not the product's own function):

| result | n |
|---|---|
| confirmed real hang | **252** |
| not a hang | 8 |
| undecidable | 0 |
| **precision** | **96.9%** |

## 7 · Old-schema residue (reported separately)

| schema | events | games | users |
|---|---|---|---|
| 15 | 1,124 | 1,000 | 41 |
| 9 | 19 | 16 | 7 |
| 12 | 2 | 1 | 1 |

**1,145 of 2,003 `simple_hang` events (57%) sit on pre-SEE schemas.** The v16
code comment records that the COUNT-based predecessor over-fired ~⅓ of the time.
This residue must not be mixed into any baseline or verdict.

---

## 8 · The recall problem (the blocking finding)

Precision is measured and strong. **Recall is not measured, and the two
available estimates disagree:**

- Corroborated real-hang rate (SEE-created **and** `cp_loss ≥ 150`): **~1.00%**
  of moves, versus a detector flag rate of **0.57%** → implied recall ≈ 57%.
- A separate random 600-move sample found **0 of 21** SEE-created hangs carried
  the `simple_hang` flag → implied recall ≈ 0%.

Both samples are small and drawn independently (`$sample` is not seeded), so the
spread is sampling noise plus genuine disagreement about *which* moves qualify.
48% of SEE-created hangs carry `cp_loss < 50`, i.e. static SEE over-fires on
compensated tactics — which is why the raw SEE rate cannot stand alone.

**Consequence.** A detector with proven precision and unmeasured recall can
support *diagnosis* ("here is a hang you played — verified") but cannot support
*resolution* ("you have stopped hanging pieces"). Zero flagged hangs is not
evidence of improvement if the detector may only see a fraction of them. This is
the same limitation already written into
[mission_scoreboard.py:422](../backend/services/mission_scoreboard.py#L422).

**Unblocking step.** Measure recall directly: take a stratified sample of moves
where SEE and `cp_loss ≥ 150` agree a hang occurred, and count how many the
detector flags. That single number decides whether the resolution loop is
buildable. It is a corpus measurement and needs no live users.

---

## 9 · Full-v16 recall audit (2026-08-25)

The unblocking measurement was run read-only across the complete v16-covered
corpus using `backend/scripts/audit_simple_hang_recall.py`:

- **4,585** analyses;
- **150,937** user moves;
- **149,886** stored v16 observations;
- canonical SEE from `coach_blunder_guard.material_hung_after`;
- Stockfish corroboration at the already-existing `cp_loss ≥ 150` boundary;
- stored `move_observations.subtype == "simple_hang"` as the flag under test.

### Recall results

| target | corroborated hangs | flagged `simple_hang` | recall |
|---|---:|---:|---:|
| Broad: SEE ≥150 and cp_loss ≥150 | 3,798 | 827 | **21.77%** |
| Current simple-hang taxonomy: broad target plus quiet/non-capture, non-king, cp_loss ≥200, no prior created threat | 1,339 | 825 | **61.61%** |
| D_live misses: moved ≥knight piece is legally capturable on destination, destination SEE ≥150 and cp_loss ≥150 | 2,138 | 344 | **16.09%** |

The broad miss reasons are intentionally non-exclusive: 1,974 forcing/capture
moves, 693 moves in the 150–199 cp_loss band, 270 king moves, 42 prior-threat
cases, 1,354 moves not tagged `piece_safety`, and 7 missing v16 observations.
This is why broad recall and taxonomy recall must not be conflated.

### D_live full-corpus result

Restricting both numerator and denominator to stored v16 observations found
**22,583 D_live decisions across 149,886 moves (15.07%)**. The preliminary
22,758 count included 1,051 analyzed moves from v16-covered games that did not
themselves have a v16 observation; it is superseded. The strict result still
confirms the earlier 16.3% exposure estimate: the event supply is roughly six
decisions in a 40-move game.

The formula bake-off produced:

| formula | exposure | miss rate |
|---|---:|---:|
| Raw attacked destination; `cp_loss ≥150` only | 25,013 / 149,886 (16.69%) | 17.39% |
| Raw attacked destination; SEE ≥150 only | 25,013 / 149,886 (16.69%) | 43.83% |
| Raw attacked destination; SEE ≥150 and `cp_loss ≥150` | 25,013 / 149,886 (16.69%) | 8.55% |
| **Legal destination capture; SEE ≥150 and `cp_loss ≥150`** | **22,583 / 149,886 (15.07%)** | **2,138 / 22,583 (9.47%)** |

The 28.6% sampled miss rate was not reproduced by any declared formula. Static
SEE alone over-counts compensated tactics; `cp_loss` alone does not establish
that the moved piece caused the loss; raw attack maps include attackers that
cannot legally capture. Those alternatives are rejected rather than averaged.

### Independent D_live SEE implementation check

`backend/scripts/audit_d_live_outcome_validation.py` checked the production SEE
result against a separately implemented exhaustive legal capture tree. The
sample was fixed before the query: seed `20260825`, 100 positions in each of
four strata (candidate miss, compensated sacrifice, other cp-loss and clean
exchange).

| result | value |
|---|---:|
| Overall SEE-outcome agreement | **399/400 (99.75%)** |
| Candidate-miss stratum agreement | **99/100 (99.0%)** |
| Each other stratum agreement | **100/100 (100.0%)** |

The pre-registered implementation gate was ≥98% candidate-miss-stratum
agreement and ≥95% agreement in every stratum. It passed. The sole disagreement
was a threshold-edge exchange: canonical SEE 150 versus exhaustive SEE 100.

This is **not an external precision/recall measurement**. Candidate and checker
reuse the same stored `cp_loss ≥150` value, so positions below that gate agree
structurally. The check establishes deterministic agreement between two SEE
implementations; the Stockfish gate and the coaching meaning of the combined
rule were not independently verified here.

### Data lock

**DECISION LOCKED:** existing stored `simple_hang` flags may support positive
diagnosis but may not support absence-based improvement or resolution.

**DECISION LOCKED:** `piece_safety.d_live.v1` is approved as the comparable
decision/outcome fact:

- decision: a knight, bishop, rook or queen moved to a destination where the
  opponent has a legal capture of that moved piece;
- miss: canonical destination SEE is ≥150 and Stockfish `cp_loss` is ≥150;
- handled: an eligible decision that does not meet both miss gates.

`cp_loss` is corroboration of a harmful move, not a literal material-loss
quantity. A D_live fact is evidence input; focus resolution still requires the
separately data-locked evidence minimum and comparison rule.

**EVIDENCE:**

- positive precision is 96.9%;
- taxonomy-eligible recall is only 61.61%;
- D_live miss recall through the stored subtype is only 16.09%;
- zero stored flags therefore cannot mean zero hangs.

**REJECTED:**

- broad stored-flag absence: loses nearly four out of five corroborated hangs;
- taxonomy-only stored-flag absence: still loses more than one out of three;
- sampled 28.6% D_live miss rate: no declared full-corpus formula reproduced it;
- static SEE alone, `cp_loss` alone and raw attacked-square outcomes: each fails
  at least one causal or legal-move requirement.

**IMPLEMENTATION CONTRACT:** emit D_live through the existing analyzed-move
observation path and existing canonical SEE. The independent exhaustive checker
remains a read-only audit utility, not a second runtime authority. D_live must
not be inferred from the incomplete stored `simple_hang` subtype.

**PRE-LAUNCH SEMANTIC CHECK:** a human/engine reviewer must read a stratified
sample of approximately 50 D_live misses and judge whether each is genuinely a
piece-safety error a coach would teach. Record false positives and failure
patterns before confirmatory rollout. This is not a pre-code blocker.
