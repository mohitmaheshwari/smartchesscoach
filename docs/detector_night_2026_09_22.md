# Detector night — 2026-09-22

**Nothing deployed. Everything on `working-code`. `_AUTHORIZATIONS` untouched,
so none of this reaches a player until you grade it.**

Seven agents in parallel, four repairing existing detectors and three building
new ones. Every number below I re-measured myself against the **committed**
code, not the agents' reports — two of them turned out to need that.

---

## The scoreboard

| detector | before | after | cross-fire (mateIn2 / fork) |
|---|---|---|---|
| **trappedPiece** | 0.4% | **96.6%** | 0.0% / 0.3% |
| **capturingDefender** | 34.9% | **72.8%** | 0.3% / 0.3% |
| **discoveredCheck** | 0.6% | **92.8%** | 0.0% / 0.3% |
| **discoveredAttack** | 54.0% | **82.9%** | 0.0% / 0.3% |
| **pin** | 12.5% | **32.2%** | 2.0% / 0.0% |
| backRankMate | 91.0% | **100.0%** | 0.0% / 0.0% |
| fork | 66.8% | **79.8%** | 1.7% / — |
| skewer | 72.2% | 72.2% | unchanged |
| mateIn1 | 100.0% | 100.0% | 0.0% / 0.0% |

### New detectors — seven motifs we could not name at all

| detector | recall | cross-fire (mateIn2 / fork) |
|---|---|---|
| interference | **99.5%** | 3.0% / 1.0% |
| xRayAttack | **99.0%** | 2.3% / 0.3% |
| deflection | **91.5%** | 1.3% / 0.7% |
| attraction | **89.6%** | 0.0% / 0.0% |
| advancedPawn | **83.6%** | 0.0% / 0.0% |
| clearance | **83.0%** | 6.3% / 1.3% |
| defensiveMove | **61.9%** | 0.0% / 2.7% |

Coverage went from **4 measurable detectors to 16**.

`discoveredCheck` was effectively a new capability: 0.6% before, because the
proof only ever looked at the best move and only ever priced material, and a
king is worth 0 cp to every winnable-target gate.

---

## Your 100% bar: hit twice, and I will not pretend about the rest

`mateIn1` and `backRankMate` are at 100%. Nothing else is, and you chose
precision when they conflict, so here is where each one stops and why.

- **pin 32.2%.** The remaining mass is real and reachable — 344 of 1000 pin
  puzzles exploit a pin that was *already on the board*, which measures 55.5%
  if admitted. It was not shipped because the existing caption would then read
  *"<move> lines your bishop up with…"* when nothing was lined up. **That is a
  caption-policy call, not a detector one, and it is roughly +20 points waiting
  on your word.**
- **defensiveMove 61.9%.** 38% of the theme is king-and-pawn endgames decided
  by opposition or zugzwang. The board cannot license "this was the only move
  that held" there; it needs an engine, which is a different kind of proof.
- **capturingDefender 72.8%.** +15 points are available by accepting pawn and
  empty-square targets — declined because it raised cross-fire on *both*
  controls, and one of the new fires would teach "remove the guard" where the
  lesson is a knight fork.
- **discoveredAttack 82.9%.** A third of the residue is explicit rulings of
  yours from 2026-09-19 (target not winnable, target fled, gain below a pawn);
  another third needs `DISCOVERY_WINNABLE_CP` below 200, which would undo the
  Nxh7 threshold you read off the distribution. A further ~2.8 points sits in
  `caption_facts._discovered_attack_evidence`, whose mutual-line SEE gate
  discards a real discovery — outside the file that agent was scoped to, and
  duplicating the ray scan would give the detector two disagreeing shape
  sources.
- **advancedPawn** fires on 100% and *proves a payoff* on 83.6%. The gap is
  positions where the pawn never queens and the advance wins material instead.
  That claim belongs to the fork and free-piece proofs; admitting it here would
  mean telling a player "this pawn queens" when it does not.

Five relaxations were built, measured and reverted across the agents. The
clearest: one gained 0.8 points of pin recall for a **9× cross-fire increase**.

---

## The two best findings of the night were causes, not numbers

**trappedPiece was a vacuous quantifier, not a threshold.** The escape
enumeration ran while the victim's side was *in check* — where the victim has
no legal moves at all, so "every escape loses material" is trivially true of
every piece its owner has. 89% of `fork` puzzles and 100% of `mateIn2` open
with check, which is exactly why my own attempt yesterday measured 83.6% recall
at 73.3% cross-fire. Gating on "the owner is not in check" takes both controls
to 0.0%. The same vacuity covered pinned victims: 0 of 290 trapped fires had a
pinned victim, 116 of 116 pin fires did — a perfect separator at zero recall
cost.

**Walking the line was the single biggest lever, three times over.** Fork
66.8% -> 79.8%, discoveredAttack 54.0% -> 82.9%, discoveredCheck 0.6% ->
92.8% — all by running the same unchanged shape scan at every initiator ply
of the stored line instead of only at `best_move`. The ply histogram makes
it plain: of discoveredCheck's 928 fires, **268 land at ply 2 or later** and
were simply invisible before. No gate was loosened for any of it, which is
why cross-fire did not move.

**capturingDefender was reading two conditions on the wrong board.** The
target's second defender is routinely the piece that *recaptures the guard*,
and the attack on the target is often opened *by* that recapture. Both now
settle at the ply the line actually captures the target. Worth +22 points
between them; the SEE gate I predicted was only +5.5.

---

## What is wired, and what is not

**Wired to coaching (the last-wire gap):** missed forks of every piece now
reach `user_pattern_events`. `build_fork_proof` has covered all five piece
types since it was written and fed only the admin review page. Over 400
analysed games that is **72 new events — knight 27, bishop 13, queen 12,
rook 10, pawn 9** — where coaching previously held *zero* non-queen forks, and
knight forks are 42% of all forks at 600-1500.

**Reviewable:** all seven new detectors are on `/admin/detector-review`, plus
the pin and trapped-piece queues from yesterday. That is how the evidence for
grading them gets made.

**Not wired:** nothing else. No `_AUTHORIZATIONS` entry was added or changed,
so none of the new work can drive a plan or a caption.

---

## Three things I want you to look at

1. **`_AUTHORIZATIONS["tactic:remove_defender_with_stored_payoff"]` prose is now
   stale.** It describes "literal sole-defender removal" and the proof no longer
   works that way. The grade is SHADOW so nothing is renamed for a player, but
   the practical effect is roughly twice as many positions admitted as broad
   missed-tactic puzzles. Untouched by rule; yours to correct.

2. **The pin caption branch** — +20 points of pin recall behind one honest
   sentence for pre-existing pins. Something like: *"Qxh3+ works because your
   bishop on d5 already holds the pawn on g2 in front of the king on h1. The
   pawn cannot take back."*

3. **Parallel agents on one worktree and one container is not safe.** Three
   agents reported another's git operation wiping their uncommitted work, and a
   shared scratch file being overwritten mid-measurement. The container also
   ended the night in a restart loop from mismatched file copies (repaired). It
   worked, but by luck in places. If we do this again, each agent needs its own
   worktree.

---

## Corrections to my own work tonight

- I claimed the seven new proofs "drop straight into the existing
  `_missed_motif` producer" because the signatures match. They do not — that
  wrapper reads `target_square`/`targets`, which only fork and discovered_attack
  carry, so it raised `UnboundLocalError` **455 times** on attraction and the
  queue returned nothing. Caught by running it. A dedicated producer now serves
  them.
- I corrupted `pattern_catalog.json` by reading it as cp1252 and writing UTF-8,
  turning every em-dash and "Légal's family" into mojibake. Reverted and redone;
  the shipped diff is +7 lines, additive only.
- I measured `capturingDefender` at 0.0% and nearly reported the agent's 71.5%
  as unreproducible. The relaxations live behind kwargs in `shape_detectors.py`,
  which I had not refreshed in the container. My error, not its.
- An agent flagged that discovered_attack (priority 435) outranks the aligned
  proof (425) and called it "a shipped change stealing the caption from verified
  skewers". I checked: both values came from the same original commit. It is
  by design, not a regression — though whether the ordering is *right* is a fair
  product question.
