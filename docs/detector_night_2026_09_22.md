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
| **pin** | 12.5% | **56.2%** | 1.2% / 0.0% |
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

- **pin 56.2%** *(was 32.2% — shipped after you said go; see "The pin branch,
  finished" below)*. The remaining misses are a different shape again and have
  not been clustered yet.
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

## The pin branch, finished

You said go, so it is in and pushed (`ffffa7a9`). **Pin 32.2% -> 56.2%.**

The caption was only the third of three gates, and the smallest. The real
blocker was in the independent verifier: it dropped any alignment that
existed before the move. That is a *novelty* test, not a correctness one --
the ray is still recomputed on the after-board and the stored line still has
to prove the payoff. Novelty is still required of a candidate that claims to
have created something.

Then a subtler one. All 313 newly-admitted fires rendered *"<move> clears a
line for your bishop"* -- the precise falsehood I was trying to avoid --
because every payoff model infers `creation_mode` from where the attacker
stands, and an attacker that never moved reads as "discovered". The flag now
travels with the alignment the payoff actually sees.

**Only payoff C may admit a pre-existing alignment.** C proves the pin was
load-bearing: it finds the recapture the front piece would have to make and
shows it is pseudo-legal but illegal. A and B only observe that a pin exists
somewhere while the move does its work elsewhere. Measured, they supplied
every bad cross-fire -- `Kxf1` and `Kh2` credited to pins they never touched,
and `00hbV` crediting `Nxe6` to a d7 rook that never defended e6. Dropping
them cost 10 fires and bought back all six false ones.

Two captions, not one, because a pin against a **queen** is relative -- the
front piece may legally move, so "cannot move out of the way" was simply
false there. What a player now reads:

> Your queen on g6 is already holding the pawn on g2 in place, because the
> king on g1 is behind it. Nf3+ works because that pawn is not allowed to
> move.
>
> *Before you calculate, look for an enemy piece stuck in front of its own
> king. It is not allowed to move, so it cannot defend and it cannot take
> back.*

Cross-fire rose by 3 fires per 1000 (mateIn2 11->12, backRankMate 0->2). I
replayed each on the board: all three are genuine absolute pins doing the
work, which Lichess simply headlined as mate themes. Nothing else moved --
skewer recall, fork and hangingPiece cross-fire are all unchanged.

Sealed packet: **0 of 50 curated negatives fire**, including all five
labelled `no_created_alignment`, and 50 of 50 recorded fires still fire.

**One thing needs your ruling.** The packet behind this detector's CAPTION
grade has a population of `{direct: 374, discovered: 62}` — **zero**
pre-existing. Its 25/25 pin evidence was drawn entirely from created
alignments, so the grade's evidence does not cover the class I just added.
I bumped the proof to `v5` so the change is attributable and left
`_AUTHORIZATIONS` alone. The negatives holding at 0/50 is real evidence, but
it is not the same as a reviewed positive sample, and I am not allowed to
grade my own work.

---

## A regression I dismissed last night, and should not have

An agent flagged that discovered_attack (priority 435) outranking the aligned
proof (425) was "a shipped change stealing the caption from verified
skewers". I checked that both priorities came from the same original commit,
called it by-design, and moved on. I checked the wrong thing: the question
was never the priority, it was whether **line-walking made discovered_attack
fire where it previously did not.** It did.

`test_caption_fact_drives_feedback_but_not_prompt_or_recovery_identity` fails
on HEAD. With the pre-line-walk proof restored, all 5 tests in that file
pass. Measured overlap on positions the aligned proof verifies:

| | before line-walk | after |
|---|---|---|
| skewer | 0 / 722 | **5 / 722** |
| pin | 9 / 562 | **11 / 562** |

So ~7 positions per 1000 lose a specific pin/skewer caption to a
discovered_attack claim that is not caption-authorized, and fall back to a
generic one. Small, contained, and real. The fix is a priority question --
when a move is both a discovered attack and a skewer, which lesson does a
1200 need? -- so it is yours, not mine. It was already failing before
tonight's pin work; my change adds no new failures.

---

## The branch situation, which you should know about

`origin/working-code` and the **local** `working-code` in
`C:/Users/MIISCO/smartchesscoach` have **diverged** at `c513af68`.

- `origin/working-code` carries every commit from this work — 555 commits
  the local branch does not have, including all 18 `_puzzle_proof.py` files.
- The local `working-code` (`4af8313c`) has 11 commits of its own and
  **zero** detector proof files.

I committed and pushed onto `origin/working-code`, where the work actually
lives. Nothing was merged, rebased or force-pushed. Flagging it because a
force-push of the local branch would destroy the detector work, and because
a checkout there will look like none of this exists.

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
