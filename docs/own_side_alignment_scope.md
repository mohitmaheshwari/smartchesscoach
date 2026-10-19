# Own-side alignment — scope

Status: **DRAFT, awaiting Mohit signoff.** No code until he signs off.
Path chosen in Section 0: **EXTEND** (agreed 2026-10-19).

Gold case: game `66090078-5673-447e-a9d5-58b3a3005c27`, move 30.
FEN `8/6pp/6k1/3p4/P2Pn1b1/B7/5rPP/3R1BK1 w - - 0 30`.
Played `Rc1` (−0.03). Best `Ra1` (+2.79). `cp_loss` 284.
Today's card: *"You played Rc1; Ra1 was the stronger move here."*

---

## 0. Existing surfaces audit — EXTEND

**What already touches this need.** `caption_facts.py:4779` owns pin/skewer
geometry. Its own opening line is *"Pin/skewer shapes share a common geometry:
a sliding **own** piece lines up two **enemy** pieces."* It already computes
`front_value_vs_rear` with `"higher" → classic skewer shape` — the exact
taxonomy this feature needs. `_own_passed_pawns()` at line 6947 already finds
passed pawns. `services/line_motif_geometry.py` already provides `walk_line`,
`squares_between`, `blockers_between` and `slider_travels`, used today by the
clearance / interference / xray puzzle-proof services.

**What it provides on the gold case.** Nothing. The real extractor was run on
the real move and returned 124 facts, of which:

```
aligned_pieces_evidence = []          <- fired nothing
(no passed-pawn fact present at all)
pieces_now_undefended   = [ d4 pawn, lost_defender d1 ]
```

**Overlap vs genuine differentiation.** The geometry, the value table, the
`front_value_vs_rear` taxonomy and the renderer are all shared — that is pure
overlap and must not be rebuilt. Three things genuinely differ:

1. **Polarity.** The walker looks for *our slider → two enemy pieces*. It
   cannot see *enemy slider → two of our own units*.
2. **Agency.** It fires on an alignment the played move **creates**. Here the
   alignment already exists; the mistake is failing to **guard the entry
   square**. A "what did this move create" detector structurally cannot see
   "what did this move fail to prevent".
3. **The rear unit's meaning.** A passed pawn behind the loose piece is not
   just material — it is the only winning asset in the position. Nothing
   currently tells a caption that.

Supporting detail for why the loose bishop was invisible:
`pieces_now_undefended` is a **delta** fact. It caught d4 losing its defender
because the rook left d1. The a3 bishop was *already* undefended before the
move, so a change-based fact can never see it.

**Decision: EXTEND** `caption_facts.py`. A parallel detector would duplicate
four things that already exist, against
[memory/feedback_single_source_of_truth]. Where the two readings need to
*speak* differently, that is handled at the caption-variant level, not with a
second detector.

Also observed and NOT part of this scope: the gold move is stored with
`cognitive_gap: king_safety`, which is wrong — no king is involved.

---

## 1. What it is

When two of your own pieces stand on the same line and the front one is not
defended, your opponent can attack the front one and take whatever is sitting
behind it. Today the coach says nothing about this — it just names a better
move. This change lets the coach see that shape **before** anything is lost,
say it in plain words, and say why the better move fixes it. It matters most
when the thing behind is a passed pawn, because then the player is not losing
a pawn, they are losing the whole game plan.

---

## 2. What the user sees

The same card that exists today, with a real explanation in place of the
one-line shrug.

**Today:**

```
♟ Rc1                                          [ Your move ]

You played Rc1; Ra1 was the stronger move here.

  ▸ Why? Play it out
```

**After:**

```
♟ Rc1                                          [ Your move ]

Your bishop and your pawn are on the same line. Their rook can land
under the bishop. The bishop has to move, and your pawn goes with it.
That pawn is the only thing that can win this game for you. Ra1 takes
that square away and sits behind the pawn.

Keep your rook behind a passed pawn.

  ▸ Why? Play it out
```

59 words including the principle line, inside the 60-word cap.
No jargon word for the motif itself — the shape is described, not named.
No numbers. The principle sentence is the universal takeaway, per
[memory/feedback_caption_keep_explicit_principle_ending].

---

## 3. In scope (V1)

- The alignment walker runs in **both polarities**: own slider → two enemy
  units (today's behaviour, unchanged) and enemy slider → two own units (new).
- The new polarity fires on an alignment that **already exists** on the board
  before the played move, not only one the move creates.
- Evidence emitted uses the existing `front_value_vs_rear` vocabulary; no new
  taxonomy.
- The front unit must be **undefended** for the new polarity to fire.
- The enemy slider must be able to **reach the line in one move**, and that
  entry square is emitted as a fact.
- A passed-pawn fact is surfaced on every move from the existing
  `_own_passed_pawns()`, so a caption can name the rear unit as the passer.
- One new caption variant in `R12_blunder.json` for the case, with a `why`
  and a principle ending.
- The recommended move is explained, not just named — it must say what `Ra1`
  does ([memory/feedback_explain_why_recommended_move_good]).
- Today's offensive behaviour is unchanged: a before/after corpus fingerprint
  shows zero diff on cards that fire today
  ([memory/feedback_snapshot_the_corpus_before_refactoring]).
- The gold case above renders the explanation, not the floor rung.

---

## 4. Explicitly out of scope (V1)

- **Naming the motif.** The caption describes the shape; it does not say
  "skewer" or "pin". Jargon decision deferred — see Open Questions.
- **Arrows for this case.** The payoff is several moves away, so a green
  arrow would promise material it cannot deliver inside the window
  ([memory/project_a_count_is_not_a_payoff]). Arrows stay as they are.
- **Fixing `move_story`.** The `neither / short range 0/0` verdict is the
  reason the card fell to the floor rung, but widening the material horizon
  is a separate and much larger change. This feature works by adding a static
  fact, not by changing the verdict.
- **The `cognitive_gap` mislabel** on this move (`king_safety`). Category
  correctness belongs to `/classify-moves-from-gold`.
- **Pins against our own king** (absolute pins). The rear-unit-is-king case
  already has handling and is not touched.
- **PWC live play.** It routes through the same central layer and will pick
  this up automatically; no PWC-specific work and no PWC-specific claim.
- **Backfill of old games.** Re-rendering history is a version-bump decision,
  listed in Pre-code.

---

## 5. Success criteria

Numbers deliberately left unlocked — picking a threshold before seeing the
distribution is the sin in
[memory/feedback_threshold_before_distribution_is_sin]. `/lock-via-data`
fills these in after Section 7's distribution run.

- **Gold case.** The move-30 card renders the explanation and survives the
  claim verifier. Binary, must pass.
- **Coverage.** The new polarity fires on at least _N_ user mistakes across
  the measured corpus, where _N_ comes from the distribution run. A detector
  that fires on one position is a hard-code, not a family
  ([memory/feedback_design_the_pattern_never_the_position]).
- **Truth.** Every fired case is checked by walking the line: the front unit
  really is attackable, really is undefended, and the rear unit really is
  lost after the front one moves. Target false-positive rate locked by data.
- **It reaches a person.** The share of these cards reaching the screen with
  a `why` — measured on the rendered card, not the registry
  ([memory/feedback_verify_to_the_screen_not_the_registry]).
- **No regression.** Zero diff on the existing offensive-polarity cards.

---

## 6. Open questions

- **Question:** Does the caption get to say the word "skewer"?
  **Why unresolved:** the audience is 600–1500 and
  [memory/feedback_caption_voice_avoid_chess_jargon] says avoid jargon, but a
  named motif is also how a player searches for and remembers a pattern.
  **Unblocking step:** Mohit's call on the mockup in Section 2.

- **Question:** Is "passed pawn" itself too much jargon for the principle
  line, versus something like "free pawn"?
  **Why unresolved:** same tension; "passed pawn" is standard and taught
  early, but it is still a term.
  **Unblocking step:** Mohit's call on the mockup.

- **Question:** Should the fact fire when the rear unit is an ordinary pawn
  or piece rather than a passed pawn?
  **Why unresolved:** the shape is the same but the urgency is not. Firing
  everywhere risks noise; firing only on passers may be too narrow to be a
  family.
  **Unblocking step:** the distribution run — count positions by rear-unit
  type before deciding.

- **Question:** Does the claim verifier accept this sentence shape?
  **Why unresolved:** this card already shows `R12_blunder→FINAL_VERIFY_SOFTENED`,
  so a `why` was produced and then stripped. The verifier reads prose
  literally ([memory/project_claim_verifier_reads_prose_literally]).
  **Unblocking step:** run the candidate sentence through the verifier before
  writing the variant.

- **Question:** Does this need a `V5_COACHING_VERSION` bump, and do old games
  get re-rendered?
  **Why unresolved:** a bump re-renders the back catalogue, which is a cost
  and a risk decision, not a technical one.
  **Unblocking step:** Mohit's call once coverage is known.

---

## 7. Pre-code requirements

Each one is a hard gate. No first line of code until all are true.

1. **Mohit has explicitly signed off on this document.** Not "sounds good".
2. **Distribution run completed** over a real corpus: how many user mistakes
   carry this shape, split by rear-unit type (passed pawn / other pawn /
   piece) and by whether the front unit is undefended. Feeds Section 5 and
   the third open question. Run on the server, per
   [memory/project_local_container_not_prod].
3. **`/lock-via-data` has run** on every number Section 5 leaves blank.
4. **The candidate caption sentence has been through the claim verifier**
   and passes, before the variant is authored. This card is already being
   softened by `FINAL_VERIFY`; authoring a sentence the verifier will strip
   wastes the whole build.
5. **A corpus fingerprint is captured** over the existing offensive-polarity
   cards, so the no-regression criterion in Section 5 can be checked as a
   per-row diff rather than a vibe.
6. **The engine gate is confirmed**: this fact only ever explains a move
   Stockfish already called a mistake. It never decides *that* a move is bad
   ([memory/feedback_engine_gates_board_explains_caption_silent]).
7. **`/audit-pre-code` has run** and passed.

---

*Gold case verified with Stockfish depth 26 on 2026-10-19: Ra1 +2.79, Rb1
+0.05, Re1 +0.01, Rc1 −0.03 — Ra1 is the only move that keeps anything. After
`Rc1 Ra2` every one of White's five best replies moves the bishop; defending
a3 instead loses outright (`Rc3` −6.67, `Rc4` −6.90). The engine's own line
then plays `31.Bc5 Rxa4`, capturing the passer.*
