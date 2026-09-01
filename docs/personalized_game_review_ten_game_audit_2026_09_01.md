# Personalized Game Review — Ten-Game Acceptance Audit

**Date:** 2026-09-01  
**Account:** `bhutramohit@gmail.com`  
**Status:** Baseline audit complete; approved repair implemented and re-audited in an isolated worktree  
**Product code changed:** Yes, behind the existing validation-only flags; not committed or deployed by Codex

## Verdict

The stored Stockfish foundation was useful, but the deployed baseline was not
ready to be treated as a reliable human coach. The baseline result below is
preserved because it explains why the repair was required.

On this acceptance sample, the product is **4/10**. The earlier 6/10 assessment was too generous because it considered engineering structure and isolated successful captions more than whole-game coaching quality.

The main baseline failure was not lack of prose. The system did not maintain
one coherent, verified explanation from chess evidence through moment
selection, caption, lesson, reflection, and board visual.

## Post-repair acceptance result

The final no-write reconstruction over the same ten games produced:

- 58 significant player mistakes/blunders inspected;
- 30 Caption-authorized exact causes and 28 honest abstentions;
- zero V2 chess-claim, teaching, reflection, or visual consistency issues;
- zero pipeline failures;
- zero fresh engine runs;
- zero LLM calls;
- zero database writes.

The expanded promotion packet adds 40 manually reviewed fires and 30 manually
reviewed abstentions from additional games on the same explicitly authorized
account. Combined evidence is 70/70 accepted fires, 30/30 correct abstentions,
and zero critical false claims. See
`docs/verified_single_game_cause_caption_promotion_2026_09_01.md`.

This is a technical truth/consistency acceptance result, not a population UX
score. Blinded coach preference and multi-player ranking validation remain
release gates.

## Method

The sample was fixed before inspection:

- 10 games from `bhutramohit@gmail.com`;
- 4 wins, 4 losses, and 2 draws;
- 5 games with a current-schema `simple_hang` observation and 5 without;
- 2 games already stored at V138;
- 8 older games replayed in memory through the deployed deterministic code;
- stored Stockfish evidence only;
- no Stockfish reruns;
- no LLM calls;
- no Mongo writes.

Every one of the 58 user mistakes/blunders was scanned for teaching completeness. The three planner-selected chapters and the 30 highest-practical-impact captions were then checked manually against the position, legal moves, stored evaluations, and stored principal variations.

This is a single-player acceptance audit, not a population precision estimate. It is sufficient to identify architectural failures, but not to lock corpus-wide percentage targets.

## Sample

| Game | Result | Stored version | Significant moves | Current chapters | Most important move selected? |
|---|---:|---:|---:|---:|---:|
| `100897b9…` | Win | 138 | 8 | 1 | No |
| `3a41fb4c…` | Loss | 138 | 13 | 0 | No |
| `e8d32ff3…` | Win | 135 | 8 | 0 | No |
| `6bb265c0…` | Win | 135 | 5 | 1 | No |
| `344d7079…` | Win | 135 | 4 | 1 | No |
| `2d8b0414…` | Loss | 137 | 4 | 0 | No |
| `cd89653f…` | Loss | 137 | 3 | 0 | No |
| `0aa43a35…` | Loss | 137 | 7 | 0 | No |
| `2127348b…` | Draw | 135 | 3 | 0 | No |
| `4890349f…` | Draw | 135 | 3 | 0 | No |

## Measured Results

### Whole-game coaching

- Only **3 of 10 games** produced a current personalized teaching plan.
- The highest-practical-impact move was selected in **0 of 10 games**.
- The planner produced only **3 chapters from 58 significant moves**.
- All three selected chapters came from `piece_safety.simple_hang`.
- Only **1 of the 3 selected chapters** had its event concept, caption cause, and stored chess line aligned.

### Caption teaching quality

- 57 of 58 captions satisfy the permissive rule “contains at least one WHY signal.”
- Only **22 of 58 (37.9%)** contain all three: a concrete consequence, a causal connector, and a transferable ending.
- **19 of 58 (32.8%)** have no separate transferable instruction.
- **58 of 58** have no board arrow.
- The current narrator verifier reported no violation on the manually reviewed top captions, but missed **8 clearly false claims among the top 30**.

The 57/58 headline therefore overstates quality. A sentence can pass because it contains a generic connector or maxim while its chess cause is false.

### Knowledge integration

- `principle_id_used` was absent on all 58 significant moves.
- Opening teaching signals: **0**.
- Endgame teaching signals: **0**.
- Trap teaching signals: **0**.
- Five sampled games have named openings in stored data.
- One sampled game reaches a clear king-and-pawn endgame where opposition/key-square knowledge is the lesson.

The content exists elsewhere in the repository, but it does not currently become whole-game teaching evidence.

## The Three Chapters the Planner Actually Chose

### 1. `100897b9…`, move 25 `Bh6`

**What happened:** the rook on a1 was attacked by the knight on c2; the stored punishment is `Nxa1`. `Rd1` moves the rook out of danger. The player remained winning.

**What the caption says:** `Rd1` is a forcing move against the exposed king.

**Verdict:** incorrect cause. `Rd1` is neither a check nor a capture. The caption does not name the rook, a1, the knight on c2, or `Nxa1`. The reflection omits the plausible attacking intention behind `Bh6`, and the visual highlights only h6 with no relationship arrow.

### 2. `6bb265c0…`, move 23 `h4`

**What happened:** `h4` permits `Bxe1`, exchanging the bishop for the rook, while `Rg1+` begins a forced mating line. The game remains winning after `h4`; the true practical turning point is later `Rg4`, which gives away the win.

**What the caption says:** this is a missed-mate/checks-first lesson.

**Verdict:** the caption describes the stronger attacking line, but the admitted event is `piece_safety.simple_hang`. Caption, concept, reflection, and selection reason disagree. The planner chooses this secondary moment and misses the later actual turning point.

### 3. `344d7079…`, move 16 `Ba5`

**What happened:** the bishop on f5 is left to `exf5`; `Bc3` attacks the queen and prevents the loss.

**Verdict:** the core cause is correct. The chapter still lacks the e6→f5 attack arrow, the f5 victim marker, and an intention option matching the player's attacking move.

## Clear Chess Failures Found in the Top Captions

| Position | Current teaching | Stored/board truth |
|---|---|---|
| `e8d32ff3…`, 3.Bc4 | Praises “Italian Game direction” and “classic development” | `…dxc4` immediately wins the bishop; a generic opening intro overwrote a blunder explanation. |
| `e8d32ff3…`, 15.f4 | Says `Nxc7+` sacrifices a knight to break the king's pawn shield | The stored line is `Nxc7+ Kf8 Nxa8`; the knight takes the rook. It is a fork/clearance sequence, not that sacrifice story. |
| `0aa43a35…`, 17.Qc2 | Says `Qc2` loses the knight on c3 and `Nd5` saves it by defending c3 | The stored line is `…Nxe4, f3, …Nxc3, bxc3`: the knights are exchanged and White recaptures. `Nd5` moves the c3-knight away; the concrete loss in the played line is not the claimed free knight. |
| `0aa43a35…`, 20.Rcd1 | Says `…Qc6` makes the line cost material | The stored continuation `…Qc6, Rxd8+, Rxd8, f4` shows an equal rook exchange and no demonstrated material loss. The concrete claim outruns the stored proof. |
| `2127348b…`, 8.exd6 | Says the bishop on e3 is lost “for nothing” after `Nxe3` | The stored next move is `fxe3`; White recaptures the knight. The error is not a free-piece loss. |
| `4890349f…`, 6…Nxf2 | Says the knight is lost “for nothing” after `Rxf2` | The stored continuation is `Rxf2 Bxf2+ Kxf2`; the full exchange must be valued. The positional cost cannot be explained as a free knight. |
| `2127348b…`, 30.g3 | Says three enemy pieces are aimed at the king on d3 | The board does not support that attack count in the pawn endgame. |
| `cd89653f…`, 29…Rd1+ | Says three opponent pieces are aimed at Black's king on h5 | The board does not support that claim. |

Other materially weak examples include reducing `Ke3` versus `Kc4` to “attack the pawn” instead of teaching the king-and-pawn endgame mechanism, claiming a problem began “around move 1” without stored causal evidence, and saying a line “costs material” when the stored PV does not demonstrate the claimed exchange.

## Root Causes

### A. Event admission is the coverage bottleneck

`game_review_shadow_runtime.py` adapts only current-schema `simple_hang` into a player-authorized `TeachableEvent`. The planner never receives the missed mates, tactical reversals, opening errors, or endgame moments visible in the same games.

The 0/10 top-moment result is therefore not mainly a ranking-formula failure. The strongest moments are absent from the candidate set.

### B. The verifier is lexical and mostly one-ply

`narrator_claim_verifier.py` checks a small group of phrases: piece-on-square, “free,” no-recapture, mate, outpost, queen chase, allows, and king-center claims.

The important gaps exposed here are structural:

- it does not build a multi-ply material ledger;
- the “free” check looks at the recommended capture, not the opponent response described in a user-move caption;
- the no-recapture check explicitly skips user moves;
- it does not validate purpose labels such as sacrifice, fork, or forcing move;
- it does not validate attack counts, open files, defenders, or move-origin relationships;
- if it cannot construct the board, it returns clean rather than unverified.

That is why `final_verified: true` currently means “none of the few implemented regex checks objected,” not “the explanation is chess-correct.”

### C. Opening promotion can erase mistake truth

The promotion ladder allows `R_PROMOTED_opening_intro` whenever opening-intro data is present. Unlike later shape/basic promotions, it does not require `caption_empty: true` or a sound move. This let a generic opening introduction praise 3.Bc4 while Stockfish and the stored PV show it loses the bishop immediately.

### D. The teaching surfaces have no semantic-consistency gate

The caption, principle, selected concept, reflection options, visual, and plan role can each be individually valid objects while disagreeing about why the move matters.

Examples:

- `Bh6`: piece-safety event, missed-mate caption, rook-safety principle, missed-check reflection;
- `h4`: piece-safety event, missed-mate caption, no hang shown visually;
- a move that stayed winning can be labelled a turning point because every unrecognized `allowed` outcome falls through to that role.

### E. Reflection is routed through the wrong diagnosis family

The simple-hang helper requests quick tags using `missed_forcing_move`. This produces options such as `missed_check` even when the verified best move is the quiet rook-saving move `Rd1`. Options are generated from a broad mistake category instead of the verified event cause plus plausible move intentions.

### F. Visual teaching is effectively absent

Every significant caption in the sample has zero arrows. Highlighting only the played destination does not show attacker→victim, best-move origin→destination, pin line, fork targets, mating route, or passed-pawn race.

### G. Existing chess content is not part of the event graph

Openings, traps, endgames, geometry, and principles may contribute isolated prose elsewhere, but they do not emit compatible review events with shared evidence, quality authorization, and mastery identifiers. Consequently they cannot be selected coherently or connected to the learner model.

## Locked Repair Package

These fixes should be implemented as one coherent release, not as caption-by-caption patches.

### 1. One evidence contract per review moment

Extend the existing `TeachableEvent` path so every candidate moment carries:

- played move and best move;
- pre/post evaluation and practical state change;
- stored played and best PVs;
- exact causal sequence;
- material ledger across that sequence;
- verified motif/concept and phase;
- affected, attacker, defender, and target squares;
- player-history link, when exact and authorized;
- plausible intention/reflection options;
- visual facts derived from the same cause.

No renderer should rediscover chess truth from prose.

### 2. Multi-ply claim verification

Before a caption can be visible, replay the stored line and verify every concrete clause:

- captures and recaptures;
- net material, not first capture only;
- check, mate, and forcing status;
- fork/pin/skewer/discovered-attack geometry;
- attacked and defended pieces;
- open files and attack counts;
- whether a move saves, attacks, trades, or sacrifices the named piece;
- whether the caption's stated purpose matches the line.

Unknown is not clean. An unverifiable concrete claim must be removed or replaced by a narrower verified explanation.

### 3. Correct promotion precedence

Opening, trap, pattern, and principle knowledge may enrich a mistake explanation; they may never overwrite its verified consequence. Generic opening praise is allowed only for a sound move. For a bad opening move, explain the deviation and consequence first, then teach the opening idea.

### 4. Admit the full authorized candidate set

Add adapters for existing authorized signals in this order:

1. allowed mate / missed mate;
2. legal material loss and missed free material;
3. fork, pin, skewer, discovered attack, overload/removal of defender;
4. opening deviation and trap setup/fall;
5. endgame technique and pawn-race/key-square events;
6. positional events only after their detector evidence is strong enough.

Caption-grade evidence may explain one observed game. Recurrence, mastery, and prescription remain gated by their stricter quality surfaces.

### 5. Rank whole-game moments only after coverage exists

The planner must compare all admitted moments using:

- practical state change and win-probability change;
- causal confidence;
- teaching completeness;
- whether the moment introduced, demonstrated, or repeated knowledge;
- personal relevance and recent recurrence;
- novelty versus redundant examples;
- game-arc role: root cause, true turning point, missed conversion, or demonstrated skill.

Do not lock another numeric ranking formula until coach-labelled importance data exists. The current ten-game set becomes the first labelled acceptance set.

### 6. Enforce cross-surface consistency

A chapter ships only if all of these share the same cause ID and position evidence:

- selected concept;
- caption;
- transferable lesson;
- reflection question/options;
- board arrows/highlights;
- plan role;
- next training action.

If they disagree, the chapter is quarantined while the rest of the review remains available.

### 7. Generate reflections from verified cause plus plausible intention

The player should choose among board-supported explanations such as:

- “I was trying to attack the king and stopped checking my rook.”
- “I thought the piece was protected.”
- “I saw the capture but expected to recapture.”
- “I did not notice the attacker.”
- “None of these.”
- “I’m not sure.”

The answer is evidence about the player's thought process, not automatic proof of a weakness. Repeated confirmed answers may update the learner model.

### 8. Make the board teach the same cause

At minimum, show:

- played move arrow;
- attacker→victim or tactical relationship;
- punishment move;
- better-move arrow;
- secondary targets for forks/pins;
- critical squares for endgames.

### 9. Wire canonical chess knowledge into review events

Use the existing canonical sources for opening, trap, endgame, geometry, and principle content. They should attach only when the exact position evidence supports them. Each event must carry a canonical content ID and mastery skill ID so the review can teach, practice, and later verify application in real games.

### 10. Make this audit an acceptance gate

Before rollout:

- zero critical false chess claims in the ten-game gold;
- every selected chapter internally consistent across cause/caption/reflection/visual;
- every selected moment legal and reproducible from stored evidence;
- the human-labelled main lesson is present in each game where evidence supports one;
- no generic opening praise on an engine-confirmed mistake;
- every selected tactical/geometry chapter has relationship arrows;
- the ten games pass unchanged, then a blind coach-labelled expansion set is evaluated.

Population thresholds for precision, moment recall, and teaching preference must be locked from the expanded labelled set, not chosen from intuition.

## What Not to Do

- Do not author eight one-off caption overrides for the examples above.
- Do not rerun Stockfish on already analyzed games.
- Do not use an LLM as deployment-time chess authority.
- Do not add more prose until the evidence contract and verifier can support it.
- Do not add more detectors merely to increase the count; promote and wire the useful existing ones.
- Do not let a content lesson replace the concrete explanation of why this move failed.

## Recommended Implementation Order — After Approval

1. Freeze these ten games as a reviewed gold set with per-move cause and importance labels.
2. Build the multi-ply evidence/claim verifier and fix promotion precedence.
3. Add event adapters for the high-confidence tactical and domain signals.
4. Add the semantic-consistency gate.
5. Rebuild planner ranking against the labelled candidate set.
6. Generate reflection options and visuals from the shared cause contract.
7. Rerun the ten-game gate, then expand blinded coach review before rollout.

The implementation should not begin until this package is accepted as the shared target.
