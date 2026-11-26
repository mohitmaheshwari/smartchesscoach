# The coach: what it must do, and where each piece actually is

The standing record of Mohit's product decisions for the coaching product,
so nothing is lost between sessions. Last updated 2026-11-26.

**Read the status column honestly.** "Built" means the code exists and runs.
It does not mean a user can see it. Today **nothing in this document is
visible to a user.**

---

## 0. The rule that sits above everything

> A mistake is one of two completely different things, and they need
> opposite responses.

**Mohit, 2026-11-26:** *"Even best players like Magnus can sometimes let a
piece undefended. Giving somebody who is good at chess practice for
undefended piece is not going to have him use the site… human coaches don't
give you exercise when you blunder something from eyesight, because they know
you know this."*

| The mistake was | The right response |
|---|---|
| **A knowledge gap** — they did not know it | Teach it. An exercise is correct. |
| **An execution failure** — they knew it and missed it | **No exercise.** Name the real cause: the clock, where their attention was, which part of the board. |

Handing a competent player a drill for something they already know is the
single fastest way to lose them. Every other product treats every mistake as
a training gap; that is the thing we are not doing.

**This is upstream of everything below.** Pillar 1 as built today does not do
it, which means the one piece that is built is built wrong in the way that
matters most.

**Supporting measurement we already had and then ignored** (player-causes
work, 2026-11-10): tactical failures at these ratings are *blindness* —
the patterns are known by everyone — while development correlated at r 0.89
as the genuine knowledge axis.

**Status: understood, not built.** The gate is specified in §6.

---

## 1. Two front doors

| Entry | Who coaches | Who sees the reports |
|---|---|---|
| **Academy signs up** → academy → students | The human coach stays in the loop, and is who the parent trusts | The coach, and through them the parent |
| **Player signs up alone** | The AI is the coach | Nobody. No file is kept for a third party. |

Same engine underneath. The difference is who receives what.

**Status: not built.** Academy collections exist from an older pilot with
1–2 rows.

---

## 2. Content from games where only one move won

**Mohit:** *"Games with only 1 move, else other moves were drawable or
losing, our coach picks up those games and teach those concepts well, Claude
will write down coach script with Maia moves."*

- Find a position in the player's own game where exactly one move wins and
  everything else draws or loses.
- Maia supplies the candidate moves **at that player's rating** — what they
  would actually have reached for, not what Stockfish prefers.
- The script is written from the computed tree, in the shape a coach talks:
  the tempting move dismissed in a sentence, then the win, with the opponent
  fighting back and getting smarter.

**Why it is safe:** in king-and-pawn endgames with few pieces the position is
solved **exhaustively** — the answer is a proof, not an evaluation. Above that
size, one move must clear a winning bar *and* the runner-up must fall well
below it.

**Status: BUILT.** `backend/services/teaching_script_builder.py`,
`backend/scripts/build_teaching_scripts.py`, skill
`.claude/skills/build-teaching-scripts/`. Two scripts produced. **Not loaded
to prod. Not shown to anyone. Missing the §0 triage gate.**

Measured cost: ~20s per game at depth 20 with Maia, ~1 script per 30 games.

---

## 3. Concepts: find out what they already understand

**Mohit:** *"It will try to figure what concepts user already understands, if
it's confused, it will ask user to confirm, asking a puzzle of similar types
and if user answers correctly good, otherwise it teaches those concepts."*

- Work out what the student already has.
- When unsure, **ask** — show a position of the same type.
- Correct → move on. Wrong → *that* is the moment to teach.
- A correct answer earns a **second question on a related position where the
  answer is different.** One right answer is recognition or luck; two with
  opposite outcomes is understanding.

**Asking is not only good teaching — it is the triage mechanism of §0.** It is
the only way to tell a knowledge gap from an execution failure.

**Everything must be sequenced.** Nothing is taught before its prerequisites.
An opening on Monday and an advanced endgame on Tuesday is shuffling, not
teaching. The student should feel **guided**, not handed a buffet.

**Status: scoped, not built.**
See [guided_concept_curriculum_scope.md](guided_concept_curriculum_scope.md).

What exists: 36 named concepts, a mastery machine with 4,224 rows across 76
users, 11,812 question-and-explanation positions, a 388-position diagnostic
pool with frozen grading.

What does not: **any ordering at all** (no prerequisite or difficulty field
exists), and the teaching text is broken — 1,297 concept ids carry more than
one conflicting version of `concept_text`.

**Blocked on Mohit:** the order of the 15 computable concepts (5 endgame, 10
tactical). It is a coaching judgement and should not be invented.

---

## 4. Behaviour detectors

**Mohit:** *"Behavioral detectors are always required, and tracked and these
reports need to be saved for chess academy users, not direct users."*

- Run for **every** player, always.
- **Reports are saved and surfaced for academy users only.**

### What to detect, per §0

The point of these is not a dashboard. It is to answer *"why did I play
that?"* when the student already knew better:

- **Time pressure at the moment of the move** — clock remaining, think time
- **Where on the board** — left, right, centre; and whether the error was far
  from where the action had been
- Unravelling after an error, and thinking collapsing late

### What we measured, and what we killed

Measured on 8 players with 300+ analysed games each, from timestamps,
results, rating gaps and the clock only — nothing that moves when a detector
version changes.

**Real:**

| Reading | Result |
|---|---|
| Lost over the 3 moves after a big error | **85.1 cp** |
| Lost over the 3 moves after a good move | 53.2 cp |
| Ratio | **1.60×** |
| Big errors followed by three rushed moves | 33% |
| Moves 31+: big errors / median think | **8.3% / 2.9s** (vs 10.0% / 5.7s at moves 16–30) |

**Dead — do not sell these:**

- **Tilt is not in our data.** After a loss 62.7 vs 62.4 after a win. After
  *three straight losses* they scored **63.2**, above their own average, and
  73% played on.
- **Endurance barely moves**: game 1 of a sitting 63.3, game 6+ 62.0.
- **`rushed_critical`, which we already ship, does not work** — 59.5 accuracy
  when it fires against 59.3 when it does not. Fix or retire before anything
  quotes it.

**Status: researched, not built.** No detector runs in production. No report
exists. Board-geometry and time-pressure detection **not measured yet.**

---

## 5. Standing rules

- **The chess is computed. The model writes English and chooses nothing.** If
  a sentence cannot be traced to a field of the computed tree, it does not
  ship. This is why this content type is safe where our captions were not —
  87 model-written captions read by hand came out 32 true, 22 weak, 33 wrong.
- **Start where truth is provable.** Endgames and forced tactics. The 20
  positional concepts wait until the format has earned trust.
- **Nothing reaches a student unreviewed.** Generated scripts land as
  `status: "draft"`.
- **Accuracy is the bar, not coverage.** Do not widen a gate to raise yield.
- **Lichess attribution stays where it is a fact about the player's own
  account**: that the game is rated on their real Lichess rating, that they
  need a Lichess account, and that the coach goes quiet because Lichess
  forbids outside help. Elsewhere it can go. Chessiro — the product we are
  benchmarking — names Lichess twice on its own search screen.
- **No "brain development" claim.** The research is mixed; a 2025 Spanish
  study found no gains in working memory or planning. We claim only what we
  measure: how the child decides under time pressure in their own games.

---

## 6. The triage gate — specified, not built

Before any lesson is generated from a mistake, decide which kind it was.

**Evidence that the player already knew it** (we store all four):

1. **Clock** — how much time they had at that move. Almost none is strong
   evidence of execution failure, not ignorance.
2. **Maia band** — does their own rating band find this move easily?
3. **Their own history** — did they get materially similar positions right in
   other games?
4. **Teaching history** — have we taught them this concept before, and did
   they pass the check?

**If the evidence says they knew it:** generate **no lesson**. Produce a
behaviour finding instead.

**If it says they did not:** the §2 lesson is legitimate, and §3's question
confirms it before teaching.

This is a filter on the existing generator, not a rebuild. **It should land
before any script is loaded to prod**, or the first content we ship is
exactly the kind that drives a competent player away.

---

## 7. Open decisions — Mohit's, not mine

1. **The order of the 15 concepts.** Fifteen index cards, one sitting. Blocks
   §3 entirely.
2. **Signoff on [guided_concept_curriculum_scope.md](guided_concept_curriculum_scope.md).**
3. **Does §2 fire only when the player did not know it?** Or are only-move
   positions intrinsically worth teaching regardless? These build differently.
4. **The band-solve cut-off** (currently 90%) is not locked against a measured
   distribution. `/lock-via-data` before anyone reads meaning into it.
5. **The Lichess de-branding pass** — approved in principle, not done.
6. **The player-count line** ("Searching among N users"). Available only by
   presenting as Lichess's own web client; not done, and not recommended.

---

## 8. Honest status of everything above

| Item | Status |
|---|---|
| §0 triage (knowledge vs execution) | Understood 2026-11-26. **Not built.** |
| §1 two doors | Not built |
| §2 only-move content | **Built.** Not loaded, not visible, missing the triage gate |
| §3 concept check and sequencing | Scoped. Blocked on the ordering |
| §4 behaviour detectors | Researched. Not built. Geometry not yet measured |
| §4 academy reports | Not built |
| §5 standing rules | In force |
| §6 triage gate | Specified here. Not built |

**One of seven things built. Nothing visible to a user.**

---

## Related

- [why_chessguru.md](why_chessguru.md) — the case for someone outside.
  **Out of date: it predates §0 and does not carry the triage.**
- [human_coach_gap_map.md](human_coach_gap_map.md) — what a human coach does
  that no AI coach does, measured against competitors' own pages.
- [guided_concept_curriculum_scope.md](guided_concept_curriculum_scope.md) —
  §3's scope and open questions.
