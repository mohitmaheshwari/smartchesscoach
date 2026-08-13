# Pattern Learning System — Evidence

Companion to [pattern_learning_system_scope.md](pattern_learning_system_scope.md). The scope
states the product contract; this file holds the measurements behind it, so the scope can stay
short and every number in it is traceable.

All figures measured against production (`chess_coach` @ 72.60.204.176) on 2026-08-13 unless
stated. Read-only except where a write is explicitly noted.

---

## E0. Corrections to earlier drafts

Recorded so a future reader does not re-inherit a wrong number.

| Claim in an earlier draft | Correction | How it was caught |
|---|---|---|
| "discovered and loose have 0 stored positions for all 58 users" | **Wrong.** I queried `drill_positions`, a read-time verdict field that `_verdict()` only attaches for fork/pin/skewer. The real stored field is `got_positions`, present for all five motifs: fork 558, pin 702, skewer 629, **discovered 669, loose 919**. | The Gate 3 backfill reported rows for all five motifs |
| "`community_puzzles` has zero fork-tagged rows" | **Partly wrong.** True for `issue_type`/`theme`, but there is a separate `motif` field: 2,317 rows tagged, **228 of them `fork`**. | Re-checked while wiring the Gate 3 route |
| "`MistakeMastery.jsx` no longer exists" | **Wrong.** It exists at `frontend/src/components/MistakeMastery.jsx` and is unrouted (0 references in `App.js`, no other importer). I had grepped `pages/` only. | Mohit |
| "A fork only works if the forking square is safe" (draft counterexample copy) | **Chessically wrong.** Winning a rook for a knight is a profitable exchange; a defended forking square does not by itself make a fork unsound. The test is net material after the sequence. | Mohit |
| Gold bar gated on `cp_loss < 1000` | Unexplained numeric proxy. Replaced with explicit `mate_info`; see E4. | Mohit |

---

## E1. Existing surfaces — and the contract bug they shared

### E1.1 The surfaces

| Surface | Behaviour | Verdict |
|---|---|---|
| `PrescribedTraining.jsx:292` | Position → asks for best move → grades. Little instruction before solving. | The host. Extend. |
| `MotifDrill.jsx` | fork/pin/skewer. Header states: *"Shows the position → best move → what happens if user plays wrong. Non-interactive (no move grading)."* | Reviewing, not learning. Replace. |
| `SkillDrill.jsx:45` | Detector-graded via `onPieceDrop`, one static `hint` string per skill. No progression. | Reuse the grading idea. |
| `EndgameLesson.jsx` | `INTRO → TRY → CORRECT/WRONG → COMPLETE`, `circles`/arrows, `interactive`/`viewOnly` gating. | **The spine to generalise.** |
| Opening lessons | Teach lines, validate moves; disjoint from tactics. | Out of scope. |
| Escape-squares / trap lessons | Real geometry, opportunistic only. | Out of scope. |
| `MistakeMastery.jsx` | Exists, unrouted. | See E5. |

### E1.2 The bug (fixed 2026-08-13 — Gate 3 hotfix)

`motif_profile_service.py` stored one record holding two positions:

```
fen               = position AFTER the user's blunder (opponent to move)
solution          = best move in the position BEFORE the blunder
opp_creates_motif = opponent's reply, legal in `fen`
```

Measured across all 558 stored fork positions:

| Check | Result |
|---|---|
| `solution` legal in the stored `fen` | **47 / 558 = 8%** |
| `solution` **illegal** in the stored `fen` | **511 / 558 = 92%** |
| `opp_creates_motif` legal in the stored `fen` | 558 / 558 = 100% |

Both consumers were affected, and a third defect compounded it:

- `PrescribedTraining.jsx:133` mapped `drill.solution → solution_san` and graded the user against
  it **on an interactive board** — asking users to play an illegal move.
- `MotifDrill.jsx:9` documented the contract **backwards** (*"fen: position before the user's
  blunder"*) and printed `solution` beside `fen`. Non-interactive, so it never threw.
- `get_drills()` never returned `opp_creates_motif` or `user_blunder_move` at all, so MotifDrill's
  trap panel was permanently dead code, and the board oriented to the **opponent's** side.

### E1.3 Hotfix outcome (shipped, separate commit)

Storage now carries explicit `fen_before` / `fen_after` / `game_id` / `move_number` /
`contract_version`; legacy `fen` retained unchanged as the alias of `fen_after`. `get_drills()`
emits a normalized `position_fen` + `solution_san` pair for own and community rows alike and drops
rows it cannot resolve. Backfill recovers `fen_before` by joining to
`game_analyses.move_evaluations` on `(fen_after, move)`.

Post-backfill verification, through the real reader, over every stored motif row:

| Criterion | Result |
|---|---|
| Personal solutions legal in the displayed position | **3,395 / 3,395 = 100%** (was 8%) |
| Opponent motif move legal after replaying the blunder | **3,395 / 3,395 = 100%** |
| Unresolved rows remaining in store | **0** |
| Community puzzles legal / affected | 2,317 legal / unaffected |

Backfill counts: 3,477 rows across 45 users on the first pass, then 74 more after a defect was
found and fixed — `player_profiles` is **not unique on `user_id`** (69 docs / 67 users), so
`update_one({"user_id": ...})` silently wrote only the first duplicate. The script now writes by
`_id`. Re-running skipped 144 already-done rows, confirming idempotency.
Rollback collection: `player_profiles_backup_20260813_motifcontract` (58 docs).

Shipped as `25e0114c` (contract fix) and `2b331aa1` (CI wiring) on `origin/working-code`.

### E1.4 Ambiguous provenance (P1, closed)

The reconstruction join keys on `(fen_after, move)`. That pair is **not unique across a player's
games** — the same position and move genuinely recur:

| Games matched by one stored row | Rows |
|---|---|
| exactly 1 | 3,022 |
| **2 or more** | **373 (11%)** |
| worst case | one row matched **32** games |

Taking the first match silently attributed the moment to an arbitrary game, so *"6 days ago, move
23"* could name the wrong game entirely.

**Legality is unaffected**, and this was verified rather than assumed: across every ambiguous key in
production, all candidate games agreed on `fen_before`. The single exception differed only in the
halfmove clock (`- 0 4` vs `- 2 4`) — positionally identical.

Resolution: `build_index` now keeps **all** matches. Legality fields are written regardless;
attribution is written only when the join is unambiguous. Ambiguous rows get
`provenance: "ambiguous"`, `candidate_game_count: N`, and `game_id` / `move_number` set to `None`.
`get_drills()` additionally refuses to emit attribution for any row not stamped `"exact"`, so a
pre-stamp legacy row cannot masquerade as known.

Post-apply verification: 3,395 rows served, **100% legal**, 3,022 `exact` / 373 `ambiguous`,
**0 non-exact rows leaking a game or move number**. Re-run is a no-op (58 users clean).

Any surface printing a game or date must require `provenance == "exact"`.

---

## E2. Semantic audit of `made_sound`

`compute_game_motifs()` counts `made_sound` when the user's move had `cp_loss <= 40` and the
geometry detector fires afterwards. What that *means* differs by motif, because the two detectors
are scoped differently.

| Motif | Detector scope | Measurement | Teaching-grade? |
|---|---|---|---|
| **fork** | `multi_target_attack_evidence`, built from `threats_created` — **move-scoped**, SEE-gated | 57 games sampled: **28 / 28 fork shapes had `via_moving_piece = True`** — the moved piece is the forker. Small n; interval is wide. | **Yes** |
| **pin** | `_aligned_pieces_evidence` — a **board-wide scan of every own slider's ray**, not a move-effect detector | 276 sound user-moves: **29% of pin events were shapes that already existed before the move** | **No — needs a `created_by_move` gate** |
| **skewer** | same | **14% pre-existed** | **No — same gate** |

This does **not** contradict `motif_profile_backlog.md`'s "pin 100% / skewer 87%". That audited
*geometry precision* — is the shape really a pin? It is. What was never audited is *attribution* —
did the user's move cause it? Precision and attribution are separate audits.

Consequences:
1. `motif_profile_service.py:15` (*"Phase 1: FORK only (audited)…"*) is stale relative to the
   backlog. One-line correction required.
2. Before any pin or skewer lesson, `_classify_aligned` must take `board_before` and drop
   pre-existing shapes (~10 lines). Counts drop ~29% / ~14% — corrections, not regressions.
3. V1 is unaffected: fork attribution is clean.

`via_moving_piece` is computed then discarded at `motif_profile_service.py:139`. It is free to
assert, and it is the difference between "you forked them" and "a fork appeared."

---

## E3. Gate 4 (expanded)

Run across all 558 stored fork `got_positions` from 40 users.

**Q2 — which piece creates the fork?** Knight forks are a *minority*; the lesson must filter.

| Piece | Share |
|---|---|
| Queen | 40% (222) |
| **Knight** | **36% (203)** |
| Rook | 11% (59) |
| Pawn | 8% (44) |
| Bishop | 5% (30) |

**Q3 — reconstructability.** Joining to `game_analyses.move_evaluations` on `(fen_after, move)`:
**203 / 203 = 100%**, recovering `fen_before`, `game_id`, `move_number`, `date_played`, played
move, engine best move and `cp_loss`. This is what made the Gate 3 backfill safe.

**Q4 — coverage at the detector bar.** 35 / 40 users with ≥1; 21 with ≥3; 15 with ≥5; median 4.

**Q6 — manual stratified verification, and why Q4 overstates it.** Hand-checking three records
(low / mid / high `cp_loss`) against the board, **2 of 3 were not clean forks**:

- *cp_loss 118* — `Nf5` attacked a bishop on g3 **and two pawns**. SEE-gated, so it fired. A bishop
  plus a pawn is not "one piece attacks two valuable pieces."
- *cp_loss 9217* — `Nf6+` inside a mating attack. The user allowed mate, not a fork.
- *cp_loss 367* — `Nc6` forking a rook and an undefended bishop. **Genuine teaching material.**

**Teaching-grade bar applied to all 203** (≥2 targets worth a minor piece or more; ≥1 genuinely
winnable; knight safe or the trade nets material; not a mate line):

| Class | Count |
|---|---|
| **gold** | **64 (32%)** |
| verified (recognition only) | 1 |
| reject | 138 (68%) |

Reject reasons: only one target worth ≥ a minor piece (79), every valuable target defended (41),
mate line (9), no valuable target (9).

**Stage 8 coverage at the teaching bar: 24 users with ≥1 gold position, 11 with ≥3, median 2,
max 6** — against 58 users with a motif profile, i.e. **~41%**. Gold positions also cluster: two of
the first three came from the same game on consecutive moves with the same fork, so dedupe by
`(game_id, opp_creates_motif)`.

**Q5 — is there one right answer?** For 18 stratified positions we enumerated every legal user move
and asked whether the opponent still had a knight fork afterwards:

> **Median 23.5 of ~34 legal moves prevent the fork.** Range 4–44. Every position had more than
> one. In **2 of 18** the engine's own best move does **not** prevent the fork — it accepts it as
> best overall.

"Play the move that stops the fork" is therefore not an exercise: ~70% of legal moves pass. This is
what forced the Stage 6 and Stage 8 redesigns in the scope. *(Referenced from the scope as E3.2.)*

### E3.1 Is "3 knight forks in your last 20 games" provable?

**No.** Of the 24 users holding any gold knight-fork position, restricted to their 20 most recent
analysed games:

| Gold knight forks in last 20 games | Users |
|---|---|
| 0 | **16** |
| 1 | 5 |
| 2 | 2 |
| 3 | **1** |

Exactly one user in the entire base could truthfully be told "three". Lifetime counts are also
modest — 9 users have 1, 4 have 2, 4 have 3, 4 have 4, 3 have 6. A 20-game query would silence the
personal opener for two-thirds of eligible users and still be wrong for the rest, so the scope
drops the count and moves the specifics to Stage 8, where the position is on screen.

### E3.3 Royal forks: the detector cannot express them

Testing the Stage 8 grading rule against the 63 gold positions — does
`multi_target_attack_evidence` accept the move that historically created the fork?

| Result | Positions |
|---|---|
| Detector accepts the historical fork move | 47 |
| **Detector rejects it** | **16 (25%)** |

Every rejection is the same shape. `Nxc2+` returns targets `['rook', 'pawn']`; `Nd6+` the same.
These are **royal forks** — check plus a piece. `multi_target_attack_evidence` is assembled from
*winnable* targets, and a king is never winnable, so the king never appears in the target list and
the shape reads as a single valuable target.

Two consequences. Detector-only grading on Stage 8 would reject a quarter of the personal positions,
and specifically the most instructive forks. And the Gold bar (which does count the king) and the
detector disagree on exactly these 16 — reconciled per-position during human review.

**Resolution — fixed in the canonical detector, not in the lesson.** `_forced_king_target` folds
the enemy king in as a *forced* target (`value_cp = 0`, `is_forced = true`, so it can never enter
material arithmetic) behind three gates: the other target already passed SEE, the check comes from
the piece that just moved, and the checking piece survives SEE on its own square. After the change
the detector accepts **63/63** of the old gold set, up from 47.

The third gate matters: `pattern_confidence/fork.py:120` sets
`forker_safe = forker_safety_loss <= 0 or gives_check`, which accepts a checking knight the king
simply captures. The canonical implementation deliberately does not copy that leniency.

### E3.3a Why piece-agnostic, measured

Royal forks recovered on a 6,000-move production corpus, by attacking piece:

| Attacker | Royal forks (no floor) | With the ≥300 floor |
|---|---|---|
| **Queen** | 55 | 15 |
| **Knight** | 19 | 13 |
| **Rook** | 12 | 5 |
| **Bishop** | 3 | 2 |

Knights are **21%** of royal forks before the floor and 37% after. A `knight_fork_detector`, or the
lesson-local clause drafted in v4.1, would have fixed 19 cases and missed 70. The canonical
piece-agnostic fix gets all of them, and a future bishop-fork lesson inherits it for free.

Rendered output verified on the newly-firing set — no false claims, no "worth 0", no "win the king".
Real examples: *"Be6+ forks the queen on f5 and the king on c8"* (bishop),
*"Nxf2+ forks the rook on h1 and the king on d1"* (knight),
*"Rh1+ forks the pawn on h3 and the king on f1"* (rook).

### E3.3b The royal-fork value floor

Blast radius matters: this detector powers every caption surface. Without a floor the change raises
total fork detections by **+57%** (121 → 190 on 6,000 moves). Inspecting the rendered output showed
why — 47 of 82 newly-recognised royal forks (**57%**) had a pawn as their only winnable target, e.g.
*"Qa4+ forks the pawn on b4 and the king on d7"* at cp_loss 0. That is tempo, not a teachable fork.

`_ROYAL_FORK_MIN_TARGET_CP = 300` requires the winnable target to be a minor piece or better. The
floor is asymmetric with the normal path on purpose: in an ordinary pawn+pawn fork you still win a
pawn, but in a royal fork the king contributes zero material, so a pawn-only royal fork is just a
check. With the floor, blast radius is **+29%** and 100% of newly-firing royal forks have a
minor-or-better target.

Locked against the distribution, not chosen by feel — but it remains a threshold on a product-wide
surface and is flagged for confirmation (scope §6 Q4).

### E3.4 Gold, redefined as the canonical evidence

The v4 Gold bar was self-contradictory — it required "detector fires" while admitting 16 positions
where the detector did not. Gold is now defined **as** canonical evidence (normal or royal), so the
two cannot diverge. Re-run over the 203 reconstructed knight candidates with the explicit mate gate:

| | v4 hand-rolled bar | v4.2 canonical |
|---|---|---|
| gold | 64 | **97** (27 royal, 70 normal) |
| rejected | 139 | 106 (97 no evidence, 9 mate line) |
| users with ≥1 gold | 24 | **26** |
| users with ≥3 gold | 11 | **16** |
| median per covered user | 2 | **3.5** (max 8) |

The increase is a correction, not inflation: the hand bar rejected 41 positions for "every valuable
target is defended", but SEE correctly treats a defended rook attacked by a knight as winnable
(+500 −300 = +200). The canonical detector was right and my simpler heuristic was wrong.

Separately: **no gold position has more than one fork-creating knight move**, so the grading rule
prevents a regression rather than fixing a live defect.

### E3.5 Regression safety

`tests/test_caption_pipeline_boundary.py` fails 6 of 85 both **before and after** the change —
pre-existing, Stockfish-dependent, unrelated. New suite `tests/test_royal_fork_evidence.py`: 8 tests
on fixtures taken from real analysed games, covering knight *and queen* royal forks, the king's
zero value and forced flag, a real bare check that must stay silent, the floor, the SEE gate, and
the untouched normal path.

---

## E4. Mate gate — explicit state, not a cp proxy

The draft Gold bar rejected `cp_loss >= 1000` as a mate proxy. Replaced with explicit
`mate_info.before` / `mate_info.after`, which is present on 84% of move evaluations (non-null on
5.1% — mate is rare, so absence is informative).

| Gold bar variant | Gold | Users ≥1 | Users ≥3 |
|---|---|---|---|
| `cp_loss < 1000` proxy | 63 | 24 | 11 |
| **explicit `mate_info`** | **64** | 24 | 11 |

The proxy's error, exactly as predicted: one record with `cp_loss = 1012` and `mate_info = None`
was **not** a mate line and was being discarded as one. Every other rejection agreed. Per-user
coverage is unchanged, so no downstream number moves — but the magic number is gone.

No `/lock-via-data` cutoff is needed here because the explicit signal is sufficient. If an
"already lost" *eval* cutoff is wanted later, that is a separate decision and does need one.

---

## E5. Content supply

### E5.1 Lichess corpus — already imported, barely read

`lichess_puzzles`: **4,110,434** rating-calibrated puzzles with theme tags. Already wired into
`coaching_puzzle_service._get_lichess_puzzles()` (which correctly advances past the opponent's setup
move); `WEAKNESS_TO_PUZZLE_THEMES` already maps `"fork": ["fork"]`.

| Slice | Count |
|---|---|
| theme = `fork` | 586,676 |
| rated 0–800 | 28,613 |
| rated 800–1000 | 112,989 |
| rated 1000–1200 | 112,966 |
| **knight** forks at 400–1000 (3,000 sampled, 62% hit rate) | **~87,000** |

Two consequences. Lichess `rating` is a calibrated difficulty scale with hundreds of thousands of
samples per band, so **the scaffolding fade rate can be locked against a real distribution** rather
than guessed. And `/training/prescribed` is reading **one rung** of it: `routes/training.py:211`
computes `max(lichess_rating, chesscom_rating, 1200)` from fields present for 8 and 40 of 69
profiles, so **57 of 69 users get the 1200 default** and are served the 1000–1400 slice — while the
real median user rating is **849**, a quarter below 516. We own 141,602 fork puzzles under 1000 and
serve almost none.

### E5.2 Own-game material (corrected — `got_positions`, not `drill_positions`)

| Motif | Users with ≥1 | Stored positions |
|---|---|---|
| fork | 41 | 558 |
| pin | 42 | 702 |
| skewer | 38 | 629 |
| discovered | 40 | 669 |
| loose | 41 | 919 |

Discovered and loose *do* have material. They remain out of V1 on **detector-audit** grounds
(E2), not content grounds.

### E5.3 Community

`community_puzzles.motif`: 2,317 tagged rows, **228 `fork`**. All 2,317 verified self-consistent
(`best_move_san` legal in `fen`). Usable as Verified-class recognition material; not Gold, because
nothing has been human-reviewed for teaching fit.

### E5.4 Counterexamples

**No source exists.** Every stored position in every pool is a positive instance. Hand-authoring is
the only V1 route; automatic FEN perturbation is out of scope.

### E5.5 Spaced repetition — built, never populated

`mistake_card_service.py` has due-cards, `calculate_next_review`, `is_mastered`, a Socratic "why"
endpoint and habit-progress rollup, routed at `/training/due-cards`, `/training/attempt`,
`/training/card/{id}/why`. But: `extract_mistake_cards_from_analysis` is imported only at
`routes/analysis.py:246` (the on-demand route, **not** the live worker); `is_mastered = consecutive
>= 3`; `MistakeMastery.jsx` is unrouted; and `mistake_cards` holds **0 documents**.

Reuse the scheduling concepts and endpoint shapes. Do not revive the system.

---

## E6. Volume and cohort reality

| Signal | Value |
|---|---|
| Training solve attempts, lifetime | 512 across 17 users |
| Play-with-Coach sessions, August | 10 |
| Users logged in, last 7 days | 4 |
| Users whose games were auto-analysed, last 7 days | 28 |
| Real median user rating | 849 (p25 516, p75 1222) |

Present traffic cannot support a conventional product experiment. V1 requires an explicitly
recruited cohort and stage-level instrumentation from the first commit; with n≈15 the per-stage
failure map is the readable result, not the headline percentages.

---

## E7. Methods

Read-only queries against production, plus direct execution of production service code
(`compute_game_motifs`, `get_drills`, `caption_facts.extract_facts`, `improvement_proof_engine`,
`home_coach_conversation`, `game_mirror`, `focus_bridge`) against live data. Board-level
verification with `python-chess`. Q5 enumerated all legal moves per position and re-ran the fork
detector on every opponent knight reply. Q6 was hand-checked against the board by reading the
position, not by trusting the aggregate — which is how the 68% reject rate was found after the
detector-bar number looked clean.

The only writes performed: the Gate 3 backfill (E1.3) and its backup collection.
