# Own-side alignment — scope

Status: **DRAFT, awaiting Mohit signoff.** No code until he signs off.
Path chosen in Section 0: **EXTEND** (agreed 2026-10-19).
Section 0 and the gate were **re-measured 2026-10-19** after Mohit asked how
this works for positions other than the gold one. The answer changed the
feature — see Section 0b.

Gold case: game `66090078-5673-447e-a9d5-58b3a3005c27`, move 30.
FEN `8/6pp/6k1/3p4/P2Pn1b1/B7/5rPP/3R1BK1 w - - 0 30`.
Played `Rc1` (−0.03). Best `Ra1` (+2.79). `cp_loss` 284.
Today's card: *"You played Rc1; Ra1 was the stronger move here."*

---

## 0. Existing surfaces audit — EXTEND

**What already touches this need.** `caption_facts.py:4779` owns pin/skewer
geometry. Its own opening line is *"Pin/skewer shapes share a common geometry:
a sliding **own** piece lines up two **enemy** pieces."* It already computes
`front_value_vs_rear` with `"higher" → classic skewer shape`.
`_own_passed_pawns()` at line 6947 already finds passed pawns.
`services/line_motif_geometry.py` already provides `walk_line`,
`squares_between`, `blockers_between`, `slider_travels`.

**What it provides on the gold case.** Nothing. The real extractor returned
124 facts, of which `aligned_pieces_evidence = []` and no passed-pawn fact at
all. `pieces_now_undefended` caught only the d4 pawn.

**Three genuine gaps:** polarity (own slider → enemy pieces only, never the
mirror), agency (fires on an alignment the move **creates**, never one it
failed to **prevent**), and no passed-pawn fact reaching the move. A fourth
detail explains why the loose bishop was invisible: `pieces_now_undefended`
is a **delta** fact and the bishop was already undefended before the move.

**Decision: EXTEND.** A parallel detector would duplicate the geometry, the
value table, the taxonomy and the renderer, against
[memory/feedback_single_source_of_truth].

Out of scope but observed: the gold move is stored with
`cognitive_gap: king_safety`, which is wrong — no king is involved.

---

## 0b. Does this generalise? Measured, and it nearly didn't

Mohit: *"how do you make it work for other similar positions?"* The naive
generalisation **fails**, and the control is what proved it. 500 games,
2,285 user mistakes against a control of 9,815 good moves:

| gate | mistakes | good moves | lift |
|---|---|---|---|
| shape present | 52.3% | 40.8% | 1.3x |
| + engine's best move addresses it | 46.5% | 35.8% | **1.3x** |
| + opponent's real reply enters the square | 6.1% | 0.1% | 85x |
| + that entering move **attacks the front unit** | 4.4% | 0.04% | 107x |
| + front and rear are not the king, reply is not mate | **3.2%** | **0.02%** | **155x** |
| *(+ rear unit is a passed pawn)* | *2.4%* | *2.0%* | *1.2x* |

Two things this kills:

1. **Geometry alone is noise.** The shape sits on 41% of *good* moves. Shipping
   on geometry would attach a confident explanation to a third of correct play.
2. **The passed pawn is not the gate.** It is as common under good moves as
   bad (1.2x). Requiring it collapses the family to 5 cases — a position, not
   a pattern, exactly what
   [memory/feedback_design_the_pattern_never_the_position] warns against.

What generalises is **the engine's own punishment line**: the opponent really
does enter that square, and the entering move really does attack the front
unit. Engine gates, board explains
([memory/feedback_engine_gates_board_explains_caption_silent]).

The king exclusion matters and was found by reading cases, not statistics: at
the 107x gate, `Qd2#` and `Re2+` were being caught — those are checks and
mates whose alignment is incidental. They are a different lesson.

**Final measured family: 72 cases across 61 of 500 games — about one every
eight games — against 2 of 9,815 good moves. Precision proxy 97%.**
The gold case passes the gate. Median `cp_loss` 188.

Composition of the 72:

```
rear unit (what gets won) : pawn 54 · rook 9 · knight 6 · bishop 3
front unit (what must move): knight 28 · pawn 20 · bishop 11 · queen 10 · rook 3
rear is a passed pawn      : 5 of 72   (7%)
```

So the common case is **"you lose a pawn"**, not "you lose the game". The
caption must be written for that, with the passer as an optional extra clause.

---

## 1. What it is

When two of your own pieces stand on the same line and the front one is not
safe, your opponent can attack the front one and take whatever is behind it.
Today the coach says nothing about this — it just names a better move. This
change lets the coach see the shape, confirm with the engine that the opponent
really is about to do it, and say it in plain words, including what the better
move does about it.

---

## 2. What the user sees

**Today:**

```
♟ Rc1                                          [ Your move ]

You played Rc1; Ra1 was the stronger move here.
```

**After — the common case (knight in front of a pawn, 1 of the 72):**

```
♟ Ne4                                          [ Your move ]

Your knight and your pawn share a line. Their queen can come to f3 and
skewer them: hit the knight, then win the pawn behind. Nbd7 keeps them
off that line.

When two of your pieces share a line, ask what happens if the front one
must move.
```

**After — the gold case, where the rear unit is the passed pawn (5 of 72).
Same sentence, one extra clause:**

```
♟ Rc1                                          [ Your move ]

Your bishop and your pawn share a line. Their rook can come to a2 and
skewer them: hit the bishop, then win the pawn behind. That pawn is the
only one that can win this. Ra1 takes that square away.

When two of your pieces share a line, ask what happens if the front one
must move.
```

Both inside the 60-word cap in `caption_config.json`. No numbers. The
principle sentence is the universal takeaway, per
[memory/feedback_caption_keep_explicit_principle_ending].

**The word "skewer" is approved** (Mohit, 2026-10-19), overriding the default
in [memory/feedback_caption_voice_avoid_chess_jargon] for this motif. The rule
the mockups follow: **name it and define it in the same breath** — *"skewer
them: hit the knight, then win the pawn behind"*. A 900 learns the word and
the idea together instead of meeting a term they must look up. A named motif
is also what a player can search for and remember later, which an unnamed
description is not.

---

## 3. In scope (V1)

The fact fires only when **all** of these hold. Each was measured in 0b.

- Two own units on one line; the front is undefended **or** worth more than
  the rear; the rear is worth at least a pawn.
- An enemy slider can reach the line in one move, and surviving there.
- **The engine's best move addresses it** — guards the entry square, defends
  the front unit, or moves one of the pair off the line.
- **The opponent's actual best reply lands on that entry square.**
- **That entering move attacks the front unit.**
- Neither front nor rear is the king, and the reply is not mate.
- Stockfish has already called the played move a mistake. This fact never
  decides *that* a move is bad, only *why*.

Plus:

- The existing offensive polarity is untouched; a corpus fingerprint shows
  zero diff on cards that fire today
  ([memory/feedback_snapshot_the_corpus_before_refactoring]).
- One caption variant in `R12_blunder.json`, with the optional passer clause.
- The recommended move is explained, not just named.
- The gold case renders the explanation, not the floor rung.

---

## 4. Explicitly out of scope (V1)

- **Any jargon beyond "skewer".** That one word is approved; this scope does
  not open the door to naming other motifs, and "pin" in particular stays out
  because the sibling shape is not in V1.
- **Checks and mates** where the king is the front or rear unit. Measured as
  a distinct family; different lesson, different caption.
- **Arrows.** The payoff can be several moves out, so a green arrow would
  promise material it cannot deliver in-window
  ([memory/project_a_count_is_not_a_payoff]).
- **Fixing `move_story`.** The `neither / short range 0/0` verdict is the
  proximate reason the card fell to the floor rung, but widening the material
  horizon is a much larger change. This works by adding a static fact.
- **The `cognitive_gap` mislabel.** Belongs to `/classify-moves-from-gold`.
- **Absolute pins against our own king.** Already handled elsewhere.
- **PWC-specific work.** It routes through the same central layer.
- **Backfill of old games.** Version-bump decision, see Pre-code.

---

## 5. Success criteria

Now measured rather than guessed, so `/lock-via-data` has a distribution to
lock against rather than a blank.

- **Gold case.** Move-30 card renders the explanation and survives the claim
  verifier. Binary, must pass.
- **Coverage.** Fires on ~72 user mistakes per 500 games (3.2% of mistakes,
  ~1 in 8 games). A V1 that fires on materially fewer means the port lost
  something.
- **Precision.** Fires on no more than ~0.02% of good moves (2 in 9,815 at
  measurement). Every fire is checked by walking the line.
- **Truth over prose.** Each fired caption passes the per-FEN claim verifier:
  the front unit really is attacked, the rear really is behind it, the
  recommended move really does address it.
- **It reaches a person.** Share of these cards reaching the screen carrying a
  `why`, measured on the rendered card
  ([memory/feedback_verify_to_the_screen_not_the_registry]).
- **No regression.** Zero diff on existing offensive-polarity cards.

---

## 6. Open questions

- **Question:** Does the claim verifier accept this sentence shape?
  **Why unresolved:** this card already reads
  `R12_blunder→FINAL_VERIFY_SOFTENED`, so a `why` was produced and stripped.
  The verifier reads prose literally
  ([memory/project_claim_verifier_reads_prose_literally]).
  **Unblocking step:** run both candidate sentences through the verifier
  before authoring the variant. This is Pre-code item 3.

- **Question:** Is one variant enough, or does `front worth more` (49%) want
  different words from `front undefended` (51%)?
  **Why unresolved:** "it has to move because it is worth more" and "it has to
  move because nothing defends it" are different reasons to a learner.
  **Unblocking step:** draft both sentences and read ten real cases of each.

- **Question:** `V5_COACHING_VERSION` bump, and do old games re-render?
  **Why unresolved:** a bump re-renders the back catalogue — a cost and risk
  decision, not a technical one.
  **Unblocking step:** Mohit's call now that coverage is known.

*Resolved by 0b, previously open:* whether to require a passed pawn — **no**,
it is 1.2x and would shrink the family to 5. Whether the rear unit may be an
ordinary pawn or piece — **yes**, that is 95% of the family.

*Resolved by Mohit 2026-10-19:* the caption may say **"skewer"**, defined
inline. See Section 2.

---

## 7. Pre-code requirements

1. **Mohit has explicitly signed off on this document.**
2. **`/lock-via-data` has run** on the coverage and precision numbers in
   Section 5, against the distribution in 0b.
3. **Both candidate caption sentences have passed the claim verifier**, before
   the variant is authored.
4. **A corpus fingerprint is captured** over existing offensive-polarity cards
   so the no-regression criterion is a per-row diff, not a vibe.
5. **The prototype gate is ported, not rewritten.** The measured gate lives in
   the throwaway probe used for 0b; the port must reproduce **72 / 2** on the
   same 500 games before anything else is believed.
6. **`/audit-pre-code` has run** and passed.

---

*Gold case verified with Stockfish depth 26 on 2026-10-19: Ra1 +2.79, Rb1
+0.05, Re1 +0.01, Rc1 −0.03 — Ra1 is the only move that keeps anything. After
`Rc1 Ra2` every one of White's five best replies moves the bishop; defending
a3 instead loses outright (`Rc3` −6.67, `Rc4` −6.90). The engine's own line
then plays `31.Bc5 Rxa4`, capturing the passer. The stored `pv_after_played`
is only four plies (`Ra2 Bf8 Kf7 Bc5`), which is why a gate requiring the rear
unit to be visibly captured in the stored line rejects the gold case and was
not used.*
