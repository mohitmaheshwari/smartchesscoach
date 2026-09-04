# Full-game chess-fact audit — 2026-09-03

## Decision

ChessGuru's stored Stockfish evidence is strong enough to support a much better
deterministic coach, but the current interpretation layer is not yet safe enough
to be treated as a universal chess-understanding authority.

The current V5 caption renderer is materially better than the stale captions
stored in most sampled reviews. It removes every mechanically proven
equal-trade-as-a-hang error and the unsound rook-praise error in this sample.
It still emits two wrong-direction mate captions and marks both as finally
verified. That is a release-blocking truth-gate defect for any rollout claiming
that every visible chess fact is verified.

The broader limitation is coverage and taxonomy, not Stockfish quality:

- the current cognitive-gap classifier agrees with calibrated conservative gold
  on only 124 of 272 hard-classifiable decisions (45.59%);
- 187 of 467 meaningful decisions (40.04%) receive no category;
- the full-corpus detector replay is stable but not yet authorized: 69,913
  candidate events across 446,422 user moves, zero exceptions, and zero of 48
  detector families allowed to write Mastery or Prompt evidence;
- the separate Game Review concept dispatcher recognizes something on 168 of
  467 decisions (35.97%) and emits only seven broad pattern types.

No product code was changed during this audit.

## Scope

The first exploration contained 100 isolated positions. This audit expands the
evidence to 80 complete games:

| Dimension | Coverage |
| --- | ---: |
| Rating bands | 600–899, 900–1199, 1200–1499, 1500–1999 |
| Games per band | 20 |
| Label-blind strata per band | 5 opening, 5 endgame, 5 tactical/geometric, 5 general |
| Complete legal plies | 5,931 |
| User moves | 2,966 |
| Rating-aware meaningful decisions | 467 |
| Fresh Stockfish calls | 0 |
| LLM calls | 0 |
| Production writes | 0 |

The sample was selected by a stable content hash. Exact public game traces were
deduplicated so the same game could not enter twice through two player accounts.
Seven candidate games were rejected because their stored evaluation record could
not be aligned back to the legal PGN. The exporter reconstructs the full game
from PGN because some historical analyses contain only the evaluated player's
moves rather than every ply.

The versioned packet contains no source IDs, user IDs, names, usernames, emails,
dates, URLs, PGN headers, or credentials. All 5,931 plies and all stored
four-ply continuations were replayed for legality before acceptance.

## Evaluation method

Four separate systems were measured. They should not be confused:

1. `AnalysisInterpreter` assigns one persistent cognitive-gap category.
2. The 48-entry concept-detector registry grades curriculum/mastery events.
3. The Game Review concept dispatcher recognizes review motifs.
4. The central caption pipeline converts position and stored-line facts into
   player-facing language.

A conservative hard-gold builder independently replays both the played and best
stored branches. It labels only facts that can be proved without guessing:

- a missed mating continuation;
- a newly allowed mate;
- a real material loss rather than an equal capture/recapture;
- a materially better forcing continuation;
- an exact opening or endgame phase fallback.

It abstains on positional residue. Sixteen positions, one from every
rating-band/stratum cell, were manually walked before using the builder on the
batch. It matched 15 of 16 (93.75%), above the precommitted 85% trust bar. Its
one miss is retained in the evidence packet rather than hidden.

This makes the 272-position hard-gold comparison defensible, but it is not a
claim that the remaining 195 positional decisions have been solved.

## Finding 1 — the current category is often not the chess cause

The fresh current classifier produced:

| Category | Decisions |
| --- | ---: |
| No category | 187 |
| Piece safety | 73 |
| King safety | 65 |
| Missed tactic | 53 |
| Endgame technique | 49 |
| Tactical oversight | 29 |
| Opening knowledge | 11 |

Stored and freshly rerun labels differ on only three decisions. The problem is
therefore not stale classifier data; it is the current classifier.

On 272 decisions where conservative gold can prove a primary category:

| Gold category | Decisions | Current exact | Current silent |
| --- | ---: | ---: | ---: |
| Missed tactic | 113 | 45 | 17 |
| Endgame technique | 67 | 36 | 20 |
| Piece safety | 36 | 18 | 10 |
| Opening knowledge | 30 | 10 | 14 |
| King safety | 26 | 15 | 0 |
| **Total** | **272** | **124** | **61** |

The main confusion is structural. A single legacy rule cascade asks shallow
questions in sequence. Immediate PV material loss can swallow a missed tactic;
any king move can become king safety; low-confidence calculation, pawn, and
piece-activity results are later erased to silence; phase categories arrive only
after these decisions. That is not a causal comparison between “what your move
caused” and “what the missed move would have achieved.”

## Finding 2 — the detector systems are fragmented and narrow

The 80-game anonymized packet retains stored best-move evidence for its 467
meaningful decisions, not for every quiet move. Because many positive-only
application detectors require proof that the played move matched the stored
best move, its 16 fires cannot be used as an overall reach estimate. They remain
a useful no-exception smoke test across all 48 families, but the full-corpus
replay is the correct reach measurement.

The read-only full-corpus replay covered 14,007 analyzed games and 446,422 user
moves:

| Detector census | Result |
| --- | ---: |
| Registered families | 48 |
| Generalized detectors | 28 |
| Generalized detectors with at least one fire | 27 |
| Exact canonical-position transfer checks | 20 |
| Exact transfer checks with at least one fire | 0 |
| Applied candidate events | 68,646 |
| Missed candidate events | 1,267 |
| Total candidate events | 69,913 |
| Detector exceptions | 0 |

The 20 silent curriculum entries are exact-position transfer checks. Their
silence is expected because they require a real game to reproduce a canonical
lesson position exactly; they are not generalized endgame-understanding
detectors. Of the 28 generalized families, only Lucena was silent across the
entire corpus. Opening recognition succeeded in 10,395 of 14,007 games
(74.21%).

This is broad *candidate reach*, not validated correctness. Events overlap, and
the corpus replay has no independent human/Codex label per fire. Several
`missed` predicates also have very low median stored centipawn loss: rule of the
square 0, queen mate 10, rook mate 10, opening play 14, trap detection 21, and
opposition 44. A missed concept can coexist with an equally sound move, so the
numbers do not prove those predicates wrong. They do prove that a detector's
`missed` result alone is insufficient evidence for “this hurt your game” or
“this is your weakness.” Promotion must combine concept recognition with a
separately verified consequence or opportunity.

Across the unbiased 80-game sample, the packet-supported subset produced 16
fires on 15 positions:

| Detector | Fires |
| --- | ---: |
| Rule of the square | 8 |
| Queen-and-king mate | 5 |
| Defend Scholar's Mate | 2 |
| Rook-and-king mate | 1 |

The authorization result is stricter still: 47 of the 48 are Shadow, one is
Disabled, and zero are authorized to write Mastery or Prompt evidence. The
runtime runner correctly filters those fires before persistence. Consequently,
all 69,913 corpus events describe latent candidate reach, not claims that
currently change a player's mastery state.

The separate Game Review dispatcher detected a concept on 168 of 467 meaningful
decisions (35.97%). Its full vocabulary in this sample was:

- walked into capture;
- walked into mate;
- missed check;
- missed capture;
- missed attack on a high-value piece;
- pawn race;
- missed castling.

This is useful tactical scaffolding, but it is far below the product promise of
explaining forks, pins, skewers, removal of defenders, overloads, trapped
pieces, opening ideas, positional imbalances, endgame technique, and memorable
alternative lines from one coherent source.

## Finding 3 — stale captions exaggerate the current defect

The sampled stored caption versions are:

| V5 version | Games |
| --- | ---: |
| 135 | 72 |
| 136 | 6 |
| 137 | 1 |
| 140 | 1 |

Production code is v140 and the review endpoint regenerates older reviews on
read. Therefore the stored-caption audit measures historical/cached product
output, not the complete current read path.

In the stored captions:

- 467 of 467 decisions had text;
- 38 of 364 captions requiring a reason failed the deterministic WHY check
  (10.44%);
- 13 distinct captions were mechanically proved false (2.78% lower bound);
- ten called an equal-or-better capture/recapture a hanging piece;
- two reversed a missed winning mate into “you allowed mate”;
- one praised a 780cp rook error as sound open-file play.

“Lower bound” matters: only claim families with independent machine
falsifiers were counted. This is not a 97.22% accuracy claim.

## Finding 4 — current v140 fixes most exact stored failures, not all

The current central v140 pipeline was replayed offline over every complete game
using only the stored engine evidence. Fresh engine verification was explicitly
disabled. Account memory, authored overrides, opponent-only engine rows, exact
per-account current rating, and optional personalized rendering were excluded;
the result is a pure current-renderer truth audit, not a byte-identical API
response.

Results:

- 463 of 467 decisions produced a caption;
- 20 of 364 captions requiring a reason failed the WHY check (5.49%);
- caption text changed on 231 of 467 decisions versus stored output;
- all ten equal-trade “hang” errors disappeared;
- the unsound rook-open-file praise disappeared;
- two wrong-direction mate captions remained (0.43% proven lower bound);
- both surviving false captions reported `final_verified: true`.

The two exact survivors are:

1. The player had `f5+ Kh5 Rxh7#`, played `Kg2`, and received
   “Kg2 allows mate in 2.”
2. The player had `Qxf6+ Qf7 Rxd8#`, played `fxg3`, and received
   “fxg3 allows mate in 2.”

In both positions the mating line belongs to the missed best branch, not the
played branch.

## Proven root cause of the mate leak

`caption_facts._mate_threat_evidence` merges mate evidence from
`pv_after_played` and `pv_after_best` into one record. It retains booleans
for where the mate was found, but the R01 renderer does not use those booleans
to distinguish:

- the player delivered mate;
- the player has a forced mate after the played move;
- the player missed a forced mate available only in the best branch;
- the player allowed the opponent to force mate.

When the played-position evaluation is not itself a mate sentinel, the
delivering side can remain unknown even though the best line ends in mate.
R01 then falls through to the “user allows mate” variant.

Both truth gates miss it:

- the structured caption verifier treats the mere existence of
  `mate_threat_evidence` as sufficient;
- the text verifier's mate pattern does not match “allows mate” or “misses
  mate,” and it does not compare branch ownership/direction.

The final verifier therefore certifies a false statement.

## Required repair architecture

### P0 — one branch-owned causal fact

Replace the merged mate record with explicit, independently replayed facts:

- `played_branch_result`: who mates whom, terminal ply, completeness;
- `best_branch_result`: who mates whom, terminal ply, completeness;
- `transition`: delivered, preserved, missed, allowed, already_lost, or
  unproven.

Caption templates must consume the transition enum, never infer direction from
an evaluation sign plus a mate found in either branch.

### P0 — one final claim gate for every user-facing surface

The final gate must validate both:

- structured cause against the exact played/best branch evidence; and
- rendered language against actor, direction, square, material accounting,
  and line completeness.

An exception or incomplete evidence is “not verified,” never a clean pass.
The stricter checks currently hidden behind `strict_v2` should be folded into
the one canonical gate after their own adversarial regression packet is green.
Review, Home, Play with Coach, puzzles, and future community explanations must
all call the same gate.

### P0 — causal classifier, not a label cascade

For each meaningful decision, compute two separate typed objects:

1. `played_consequence`: what the player's move actually allowed or lost.
2. `missed_opportunity`: what the verified alternative would have achieved.

Then choose the primary teaching cause through an explicit, gold-tested
precedence:

1. real moved-piece or exchange loss;
2. missed/allowed forced mate;
3. verified tactic with stored payoff;
4. exact king-safety consequence;
5. exact endgame result/technique;
6. exact opening decision/plan;
7. positional cause only when its own proof family is authorized;
8. otherwise abstain from the label while still showing the verified line.

Do not treat `cp_loss`, “best move is a capture/check,” or game phase alone as
proof of the cause.

### P1 — consolidate the detector topology

The classifier, curriculum detector registry, Game Review dispatcher, caption
facts, and puzzle proof families should publish the same typed
`ChessEvidenceEvent` contract:

- position identity;
- actor and user colour;
- played move and best move;
- played-branch evidence;
- best-branch evidence;
- exact mechanism;
- payoff/result;
- confidence and abstention reason;
- detector version;
- authorization grade and allowed surfaces.

Different surfaces may select different events, but no surface may independently
re-detect or rename the chess fact.

### P1 — promotion gates measure precision and opportunity recall

For each detector family:

- review at least 50 distinct-source fires;
- review at least 20–30 near-negative opportunities;
- require at least 95% precision with a Wilson lower-bound gate;
- require zero critical actor/direction/material/mate failures;
- measure opportunity recall, not just fire precision;
- keep caption, prompt, mastery, and plan authority separate.

The current 80-game sample is a reach audit, not enough evidence to promote
rare detectors.

### P1 — regenerate only after current-code proof

After P0 is fixed:

1. rerun the 16-position calibration and the 80-game offline audit;
2. require zero proven actor/direction/material/mate failures;
3. expand the manual gold for every promoted category;
4. bump `V5_COACHING_VERSION`;
5. dry-run caption regeneration;
6. inspect exact changed-claim counts;
7. regenerate stored reviews;
8. run authenticated API E2E before wider rollout.

## Verification notes

The two audit scripts compile, all five full-game JSON artifacts parse, the
public packet hash remains stable, and `git diff --check` is clean.

A focused clean-base regression run covering the caption boundary, missed-mate
handling, detector authorization, concept wiring, endgames, opening principles,
and positional detectors produced 118 passes and 6 failures. The failures are
current-contract disagreements rather than changes introduced by this audit:

- one test expects a forced-recapture blunder to be downgraded, while current
  code deliberately refuses to downgrade a canonical serious mistake;
- one test fixture calls a pawn undefended although the position shows it
  defended by the queen;
- four tests require Socratic question/hint text that the current R18 content
  contract intentionally leaves empty.

Those disagreements should be resolved before treating that suite as a release
gate. They do not explain or invalidate the two independently replayed mate
direction failures above.

The repository-required `tests/test_all_flows.py` was also invoked. It stopped
at its first live HTTP request because no backend server was running in the
isolated worktree, so that run is inconclusive rather than green or regressed.

## Acceptance gates

The deterministic chess-fact layer is not “excellent, no leaks” until:

- 0 actor/direction reversals across the complete adversarial packet;
- 0 equal trades described as hangs or free wins;
- 0 praise attached to a materially losing move;
- 0 illegal or incomplete line presented as proof;
- 0 verifier exceptions treated as verified;
- at least 95% precision with Wilson lower bound per player-facing detector;
- opportunity recall is measured and reported per category;
- every visible claim carries one replayable evidence identity;
- stale caption versions are distinguishable and regenerated deliberately;
- one user-facing surface cannot bypass the canonical gate.

The evidence supports building toward those gates. It does not support claiming
that they are already met.

## Versioned evidence

- `backend/data/corpus_snapshots/full_game_chess_fact_audit_v1_2026-09-03.json`
- `backend/data/corpus_snapshots/full_game_chess_fact_classifier_inputs_v1_2026-09-03.json`
- `backend/data/corpus_snapshots/full_game_chess_fact_calibration_gold_v1_2026-09-03.json`
- `backend/data/corpus_snapshots/full_game_chess_fact_audit_report_v1_2026-09-03.json`
- `backend/data/corpus_snapshots/full_game_chess_fact_caption_versions_v1_2026-09-03.json`
- `backend/data/corpus_snapshots/current_detector_fires_2026-09-03.json`
- `backend/scripts/export_full_game_chess_fact_audit.py`
- `backend/scripts/audit_full_game_chess_facts.py`
- `docs/full_game_chess_fact_audit_sample_lock_2026_09_03.md`

The full-corpus detector snapshot contains aggregate counts only: no users,
games, moves, FENs, PGNs, or identifiers.
