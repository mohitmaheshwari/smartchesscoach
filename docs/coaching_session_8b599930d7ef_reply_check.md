# Coaching session — player 8b599930d7ef: does he check the reply?

**Purpose.** Two things at once: a personalised session built from his own
games, and a test of whether the first coaching priority in
[the profile](player_profile_8b599930d7ef_canonical.md) §9 actually addresses
his difficulty. If it does not, this session should say so.

**Built with existing instruments only.** No new detector, service, collection
or scoring engine. Everything below is a question, a grading rule or a field
that already exists in the codebase.

**Status:** prepared, not run. Preparing it wrote nothing to any database.

---

## 1. What the session is testing

The profile's first priority is: *teach him to check the opponent's immediate
reply before committing.* The evidence for it is that in **90 of 240**
advantage-losing errors he left material to the opponent's very next move, and
the punishing reply was a capture or a check every time.

But that evidence is consistent with two different difficulties, which need
different teaching:

| | What it means | What to teach |
|---|---|---|
| **He does not look at the reply** | the reply is findable; he commits before checking | a procedural habit — name the reply before moving |
| **He looks and misjudges it** | he sees the capture and plays anyway | evaluation and priority — what the reply is worth |

Nothing in the record distinguishes them. `prediction_correct` is **null on all
232** lesson attempts — he has never once been asked what reply he expects. The
only direct evidence is the nine `reflection_sessions` answers, and they split
**2–2**: twice "I did not notice the piece attacking mine", twice "I was trying
to continue the attack".

**So the session records his expected reply before any help.** That single
field separates the two readings.

---

## 2. Instruments reused

### 2.1 The move question and its grader

`backend/services/lesson_question_spec.py`, category **`calculation_depth`**:

- question: *"One line here runs further than it looks. Find the move that
  still holds up two moves deep."*
- `reason_prompt`: *"How did you pick it?"*
- reason options: **`followed_the_line`** ("I followed the forcing line to the
  end before choosing") — the expected answer — and **`best_right_now`** ("I
  picked the move that looked strongest on this move"), which carries
  misconception `stops_calculating_too_early` and the correction *"Play the
  opponent's best reply in your head before you decide."*

That misconception is precisely the hypothesis under test, already authored.

**The two grading families are the spec's own, not a new one.** The file's
docstring records why: a card that asks "which move keeps every piece safe?"
and then grades the single engine best move cannot be passed by answering the
question it asks. So per position the packet carries the family chosen by the
board, not by preference:

| Moves that hold the position | Family | Printed wording |
|---|---|---|
| 2 or more | `any_safe` | "Play a move that still holds up after their reply. More than one move works here." |
| exactly 1 | `single_best` | "One move holds this position after their reply. Find it." |

A move "holds" if its root evaluation is within 200cp of the engine's best at
depth 14. The packet carries the **full accept list** per position, and a check
that `len(accept_moves) == n_moves_that_hold` passes on all 14.

**Two corrections made during preparation, both worth recording:**

- My first rule sent any position with fewer than three holding moves to
  `single_best`. One position had **two**, so it printed *"One move holds this
  position"* and accepted one of them — exactly the fault
  `lesson_question_spec.py` was written to prevent, reintroduced while citing
  it. The threshold is now `== 1`. Final split: **12 `any_safe`, 2
  `single_best`.**
- **The accept list, not the rule, is the grader.** Re-running the same
  position at the same depth gave a different holding count (2, then 5) —
  multipv with multiple threads is not bit-reproducible. So the facilitator
  grades against the stored `accept_moves`, and must not re-derive it at the
  table. The list belongs to the recorded run (Stockfish 17.1, root depth 14,
  reply depth 16).

### 2.2 The after-the-fact question

`reflection_sessions`, schema `personalized_game_review.v1` — the prompt he has
already answered nine times: *"What were you thinking before this move?"*, five
options plus `none_of_these` and `not_sure`. Existing option ids, used as-is:
`thought_piece_safe`, `thought_protected`, `chose_attack_over_safety`,
`missed_check`, `missed_capture`, `ignored_forcing_sequence`, `played_fast`.

Asked **only after** the three pre-help recordings and after grading.

### 2.3 Fields the attempt record already has

From `learning_sessions.events[].attempt`: `prediction_correct` (exists, has
never been written — this session is its first use), `distinct_position`,
`assistance`, `retry_index`, `reason_choice`, `reasoning_consistent`,
`stopped_early`, `judged_the_end`.

---

## 3. The positions

**14 positions, all his own, all engine-verified before selection** (Stockfish
17.1; root multipv over *every* legal move at depth 14; the reply after his
actual move at depth 16). Full data in
[`session_packet_8b599930d7ef.json`](session_packet_8b599930d7ef.json).

| Group | n | Drawn from | What they are |
|---|---|---|---|
| **`reply_missed`** | 8 | **58 verified** | He was at +300…+1500, played a move costing 400cp+, and the engine's immediate reply captures something his move left undefended |
| **`reply_handled`** | 6 | **40 verified** | Controls: he was at +300…+1500, **a trap was genuinely present** (at least half the legal moves blunder, at most 8 hold), and he played one of the few that hold, losing under 100cp |

**A correction to the profile's figure.** The profile reports **90**
material-to-the-reply cases, classified by rule at depth 14. Re-verified here
with the stricter test actually used for selection — the engine's best reply at
depth 16 must capture a piece worth 3+ that his move left undefended or
underdefended — **58 of the 240 survive**, not 90. The 90 includes shapes the
stricter test rejects (a pawn lost, a defender moved with no immediate capture).
The profile's mechanism split stands as stated for its own rule; the number
usable as *teaching material of this exact shape* is **58**. Both numbers are
now on the record.

The controls are matched on evaluation band and on trap density, so "he does
better here" cannot be explained by the position being safe. They are **not**
matched on his familiarity with the position — see §7.

### The 14 positions

`ANY` = any holding move accepted, `ONE` = one move only. "Cost" is what his
actual move lost. The facilitator never sees this table during the session.

| # | Group | Game | Move | Fam | He played | Cost | Holds | Engine's reply to his move |
|---|---|---|---|---|---|---|---|---|
| 1 | missed | `3a41fb4c` | b28 | **ONE** | `R8e7` | 1338 | 1 (`Qxc7`) | `Qxc4` |
| 2 | missed | `20250391` | w26 | ANY | `f6` | 1311 | 5 | `Rxf7` |
| 3 | missed | `6d16034d` | w14 | ANY | `Bxh6` | 1079 | 9 | `Nxg4` |
| 4 | missed | `2f12436c` | b12 | ANY | `Rg4` | 937 | 11 | `Qxg4` |
| 5 | missed | `c175c090` | w37 | ANY | `Qf5+` | 1252 | 8 | `Bxf5` |
| 6 | missed | `b2e11649` | b29 | ANY | `Qf6` | 1085 | 2 | `Nxf6` |
| 7 | missed | `game_692ab77` | b24 | ANY | `Neg4` | 1137 | 6 | `Qxc5` |
| 8 | missed | `a40f17f5` | w24 | **ONE** | `Ba4` | 963 | 1 (`Qxd8+`) | `Qxg5` |
| 9 | handled | `bcba0a27` | w27 | ANY | `Bxe2` | 32 | 4 | `Nc6` |
| 10 | handled | `19a8e290` | b25 | ANY | `Qc7` | 34 | 3 | `h4` |
| 11 | handled | `088762f5` | w37 | ANY | `Re8` | 28 | 6 | `Ke5` |
| 12 | handled | `8ff0b880` | b15 | ANY | `Ng3` | 0 | 6 | `Qe1` |
| 13 | handled | `0b82f2a2` | w12 | ANY | `Be3+` | 0 | 5 | `c5` |
| 14 | handled | `1435d6fd` | b29 | ANY | `Rf2+` | 0 | 5 | `Kc3` |

Spread: 7 White / 7 Black; moves 12–37; dates 2026-02-24 to 2026-09-25; 12
chess.com, 2 lichess. Positions 1 and 8 are the two where only one move holds —
both are `reply_missed`, so the hardest two are in the treatment group, which
works against the design and is noted in §7.

**Position 1 is the clearest single teaching case in his record**, and I
verified it on the board rather than trusting the script: FEN
`4r3/2Q3kp/5np1/p3rp2/2q5/P1PR4/6PP/3R1K2 b - - 0 28`. **Both queens are
hanging.** White's queen on c7 is defended by nothing, so `Qxc7` simply wins it.
His own queen on c4 is also defended by nothing. He played `R8e7` — moving a
rook, taking neither queen and saving neither — and `Qxc4` took his. +924 to
−414 in one move.

Each item carries: FEN, side to move, the two preceding moves, the grading
family and printed question, the accept set, the count of moves that hold, the
share of legal moves that blunder, the engine's best move, **the accepted
answers for "what reply do you expect"** (any reply within 50cp of the engine's
best reply), what he actually played, its cost, the eval before and after, and
whether he regained the advantage later.

Positions are **interleaved and blinded**: he is not told which group a position
belongs to, that any of them are his own games, or which he got wrong.

---

## 4. Running order, per position

Nothing is revealed until steps 1–5 are recorded.

1. **Show the board and whose move it is.** No evaluation, no clock, no
   commentary, no "there's something here". The position appears on screen; the
   facilitator reads only the printed question from §2.1.
2. **"Do you recognise this position?"** → `distinct_position` (inverted).
   Self-reported; recorded before anything else so the answer is not coloured.
3. **"What move do you intend to play?"** → `intended_move`, in SAN. Recorded
   and locked.
4. **"What do you expect them to reply?"** → `expected_reply`, in SAN.
   Graded against the packet's accept set. `not sure` is a permitted and
   recorded answer.
5. **"How do you rate your position?"** → one of *winning / clearly better /
   slightly better / level / worse / losing*. Compared with the stored eval
   band.
6. **"Having said that reply out loud — do you want to change your move?"**
   → `revised_move`, or none. **This is the most informative single field in the
   session.** If naming the reply changes his move and the new move holds, the
   habit is the gap, not the ability. Both moves are kept.
7. **Then, and only then:** grade, show the refutation, and give the correction
   text already authored on `best_right_now`.
8. **`reason_choice`** from §2.1's two options, then the §2.2 reflection prompt.

**Second pass, with a clock.** The profile found that his winning-position
accuracy degrades from 13% to 28% as his clock drains while his level-position
accuracy does not (13% → 11%). An untimed session cannot see that. So after the
untimed 14, run **6 fresh positions drawn the same way with 60 seconds each**,
recording the same fields. The verified pools are large enough to draw them
without reusing any position; the counts are in the packet's build log.

---

## 5. Pre-registered reading of the result

### Primary: the 2×2 on the 8 `reply_missed` positions

| | He named a refuting reply | He did not |
|---|---|---|
| chose a move that holds | **A** | **B** |
| chose a move that loses | **C** | **D** |

- **D ≥ 5 of 8** — supports the priority. He does not look at the reply, and the
  procedural habit is the right intervention.
- **C ≥ 4 of 8** — **refutes the priority.** He sees the reply and plays the
  move anyway; the difficulty is evaluation or priority, not perception. The
  teaching should become *what the reply is worth*, which matches the two
  `chose_attack_over_safety` reflections. Say so plainly and change the plan.
- **A ≥ 5 of 8** — the positions were easier than his games were, or he
  remembers them. Check §4 step 2 and the dates before concluding anything.
- **No cell ≥ 4** — inconclusive at this size. Rerun at about 30 positions
  before drawing a conclusion either way.

### Secondary, each stated in advance

- **Prediction accuracy, treatment vs control.** If he names the reply as
  accurately on the 8 as on the 6, reply-blindness is not what separates the two
  groups, and the primary reading is weakened whatever the 2×2 shows.
- **Revision rate (step 6).** Revising on ≥3 of 8, with the revision holding, is
  the strongest available evidence that the habit is the gap — and is itself the
  intervention.
- **`reason_choice`.** `best_right_now` concentrated on the 8 and
  `followed_the_line` on the 6 would corroborate. The reverse, or no difference,
  would not.
- **Assessment accuracy (step 5).** Systematic over-rating — calling a +300
  position "winning" — would be a separate, additive finding about how he reads
  an advantage, and is worth recording even though it is not what the session is
  for.
- **Timed pass.** If accuracy on the treatment group falls materially at 60
  seconds while the control group holds, that supports practising conversion
  with a clock (profile §9, second priority).

---

## 6. What a run would let the profile claim

Only this, and only if the numbers come out:

- which of the two difficulties in §1 he actually has — currently **unknown**
  and the reason the profile cannot name a mechanism;
- the first measured value of `prediction_correct` for any user;
- whether the §9 priority survives contact with the player.

It would **not** let the profile claim a rate, a trait, a learning outcome, or
that anything was taught. One session measures one session.

---

## 7. Limits, stated before the session rather than after

1. **Size.** 8 treatment positions can refute a strong pattern and cannot
   estimate a rate. The thresholds in §5 are set accordingly, and "inconclusive"
   is a permitted outcome.
2. **Selection.** The treatment positions are, by construction, ones he got
   wrong, so their difficulty is selected for. The controls hold the evaluation
   band and the trap density constant but **cannot hold constant that he erred
   in one set and not the other.** This is the design's main weakness and no
   result should be reported without it.
   Concretely: the treatment group's holding-move counts are 1, 1, 2, 5, 6, 8,
   9, 11 and the control group's are 3, 4, 5, 5, 6, 6. **Both of the
   one-move-only positions are in the treatment group**, so that group is
   somewhat harder on the one measure available. If he scores worse on the
   treatment positions, compare the two sub-groups with 5 or more holding moves
   (4 treatment against 5 control) before concluding anything.
3. **Recognition.** He has played 694 rated games; most of these positions are
   months old. Recognition is nonetheless self-reported in step 2 and could be
   under-reported. Prefer the older positions if any are recognised.
4. **Cueing.** A facilitator who says "look again" or pauses meaningfully has
   destroyed the measurement. The position goes on screen; only the printed
   question is read aloud.
5. **No retention claim.** One sitting. Any claim about learning needs the
   delayed-transfer shape already visible in his `piece_safety` chain — a fresh,
   unfamiliar position, unassisted, first answer, days later.
6. **Engine settings are fixed and recorded** (depth 14 root, depth 16 reply,
   Stockfish 17.1). A different depth can reorder near-equal moves, so the
   accept sets belong to these settings and the packet records them.
7. **`not sure` is data.** He chose `not_sure` on 2 of 9 reflections and 20 of
   82 reason trials. It must be recordable at every step, and a session that
   pressures him past it measures something else.

---

## 8. Facilitator card

Read only these words.

> *"Here is a position. You are to move. Take as long as you like."*
> 1. *"Do you recognise this position?"*
> 2. *"[printed question from the packet]"* — *"What move do you intend?"*
> 3. *"What do you expect them to reply?"*
> 4. *"How do you rate your position — winning, clearly better, slightly
>    better, level, worse, or losing?"*
> 5. *"Having said that reply out loud, do you want to change your move?"*
> 6. — then grade, show the reply, and read the correction —
> 7. *"How did you pick it?"* (two options)
> 8. *"What were you thinking before this move?"* (the reflection options)

Do not say: "are you sure", "look again", "what about this piece", "there's a
tactic here", or anything about the evaluation. Do not react to the intended
move.
