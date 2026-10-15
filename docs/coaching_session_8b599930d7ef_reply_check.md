# Coaching session — player 8b599930d7ef: the reply check

**Purpose.** A personalised session built from his own games, which produces a
faithful record of his decisions and feedback matched to them. It is **not**
designed to return a verdict about how he thinks, and the readings in §5 are
written so that it cannot.

**Built with existing instruments only.** No new detector, service, collection
or scoring engine. Preparing it wrote nothing to any database.

**Packet:** [`session_packet_8b599930d7ef.json`](session_packet_8b599930d7ef.json)
— schema `coaching_session.reply_check.v3`, 14 positions, **525 prepared
branches**, Stockfish 17.1 at `Threads=1`.

**Revision 2 of this document.** Six repairs, listed in §9, after a review found
that v1 of the packet stored the opponent's reply to his *historical* move and
then offered it as the expected reply to a *different* accepted move — in
position 1 the stored reply is illegal after the accepted move. That, and five
other faults, are fixed below.

---

## 1. What the session is for

The profile's first priority is *check the opponent's immediate reply before
committing*. The evidence is that in a large share of his advantage-losing
errors the punishing reply was the opponent's very next move. That evidence is
consistent with more than one difficulty:

- he did not look at the reply;
- he looked, searched, and did not find it;
- he found it and misjudged what it was worth;
- he found it, judged it correctly, and saw no better option.

Nothing on record separates these. `prediction_correct` is **null on all 232**
lesson attempts — he has never been asked what reply he expects. The nine
`reflection_sessions` answers split **2–2** between "I did not notice the piece
attacking mine" and "I was trying to continue the attack".

**So the session records his intended move, the reply he expects, and his
assessment — before any help.** Those three fields, kept together, let his own
reasoning be read back. They do not by themselves identify a mechanism, and §5
says why.

---

## 2. Instruments reused

### 2.1 Recording is neutral; grading happens afterwards

The recording prompt is **"It is your move. Take as long as you like."**

Nothing printed during recording says a move must "hold up after their reply",
how many moves work, or that there is anything to find. That wording would
*instruct* him to check the reply, which is the behaviour being observed — a
good score under that prompt would show only that he can do it when told to.

Grading uses the packet afterwards and is never shown first.

### 2.2 The move question's grader

A move **holds** if its root evaluation is within 200cp of the engine's best.
Because the hold set moves with search depth, the packet sweeps **depths 14, 16,
18 and 20** at `Threads=1` and stores:

- `accept_moves` — holds at **any** swept depth. **This is the grader.**
- `accept_moves_strict` — holds at **every** depth.
- `hold_count_by_depth` — the counts, so the instability is visible.

A move in `accept_moves` but not `accept_moves_strict` is **accepted** and noted
as depth-sensitive. A plausible move in neither is recorded and marked **pending
verification** — never automatically wrong.

**"One move holds here" may be printed on only 2 of the 14 positions.** The hold
*set* is identical at all four depths on just **3 of 14**, and the count is 1 at
all four depths on only positions 1 and 8. One position read 3/3/2/1 across the
sweep — a single-depth reading would have called it an only-move position. Every
other position uses neutral wording with no count claimed.

### 2.3 The reply question's grader — two levels, reported separately

Reply evidence is prepared **per candidate move**: every legal move in every
position has its own branch, with the engine's top six replies and the
evaluation after each. 525 branches; every stored reply was asserted legal in
its own branch.

Two gradings, because the obvious one is too generous:

| Level | Rule | What it shows |
|---|---|---|
| **wide** | his reply is within 50cp of the best reply in that branch | he knew he was in trouble |
| **narrow** | his reply is in that branch's `punishing_replies` — it actually takes a piece worth 3+ that his move left loose | he saw the specific refutation |

The wide rule accepts **5.8 of 6** stored replies on average, because in an
already-decided position almost everything is winning. On its own it measures
little. The narrow rule discriminates: a material-winning reply exists after
**87%** of losing moves but only **22%** of holding ones — bad moves hand the
opponent something to take, good moves do not. Both are recorded; **neither
alone is "he saw it".**

### 2.4 Correction text is chosen by what he did

`backend/services/lesson_question_spec.py`, category `calculation_depth`, offers
two reason options — `followed_the_line` and `best_right_now` — and the
correction *lives on the option*. So the authored
`stops_calculating_too_early` correction is used **only if he selects
`best_right_now`**. It is not pre-assigned to the position. §4 step 8 has the
full table.

### 2.5 Fields that already exist

From `learning_sessions.events[].attempt`: `prediction_correct` (exists, never
written — this would be its first use), `distinct_position`, `assistance`,
`retry_index`, `reason_choice`, `reasoning_consistent`. The after-the-fact
question is the `personalized_game_review.v1` prompt he has answered nine times.

---

## 3. The positions

| Group | n | Drawn from | What they are |
|---|---|---|---|
| **`reply_missed`** | 8 | 58 verified | He was at +300…+1500, played a move costing 400cp+, and the engine's immediate reply captures something his move left loose |
| **`reply_handled`** | 6 | 40 verified | Controls: he was at +300…+1500, a trap was genuinely present (at least half the legal moves blunder, at most 8 hold), and he played one that holds, losing under 100cp |

**A profile figure corrected.** The profile reports **90** material-to-the-reply
cases from a depth-14 rule. Under the stricter test used for selection here —
the engine's best reply at depth 16 must capture a piece worth 3+ left loose —
**58 of the 240 survive.** Both numbers are on the record.

Spread: 7 White / 7 Black; moves 12–37; 2026-02-24 to 2026-09-25; 12 chess.com,
2 lichess. Positions are interleaved and blinded: he is not told which group a
position is in, that they are his own games, or which he got wrong.

### Position 1, described correctly

Position 1 is `3a41fb4c`, move 28, Black to move:
`4r3/2Q3kp/5np1/p3rp2/2q5/P1PR4/6PP/3R1K2 b - - 0 28`

**He is in check.** The white queen on c7 checks the king on g7 along the
seventh rank. The decision is *how to answer the check*, and there are nine
legal answers — this is what v1 of this document got wrong, describing it as
"both queens hanging and he moved a rook".

| His answer | Root eval | Accepted | Engine's best reply | Replies that win material |
|---|---|---|---|---|
| **`Qxc7`** — takes the checking queen | **+914** | **yes** | `h3` (a quiet pawn move) | none |
| `Qf7` — blocks with the queen | +531 | no | `Qxf7+` (trades queens) | none |
| `Kh6` | −412 | no | `Qxc4` | `Qxc4` |
| `R8e7` — **what he played** | −354 | no | `Qxc4` | `Qxc4` |
| `R5e7`, `Kf8`, `Kh8`, `Kg8`, `Nd7` | −436 … −502 | no | `Qxc4` | `Qxc4` (+`Qxd7+` after `Nd7`) |

So: **the checking queen could be captured, and that is the only answer that
holds.** Blocking or moving the king leaves his own queen on c4 undefended, and
`Qxc4` takes it. Two of the nine answers (`Qxc7`, `Qf7`) keep him much better;
he chose one of the seven that do not.

This position also shows the asymmetry in §2.3 concretely: after the right move
the opponent's best reply is the quiet `h3`, which almost nobody would predict,
while after the wrong moves it is the forced `Qxc4`. **Reply-prediction accuracy
is therefore easier on bad moves than on good ones**, and the two groups must be
compared with that in mind.

---

## 4. Running order, per position

Nothing is revealed until steps 1–6 are recorded.

1. **Show the board and whose move it is.** No evaluation, no clock, no
   commentary. Read only: *"It is your move. Take as long as you like."*
2. **"Do you recognise this position?"** → `distinct_position` (inverted).
3. **"What move do you intend to play?"** → `intended_move`, SAN. Locked.
4. **"What do you expect them to reply?"** → `expected_reply`, SAN. `not sure`
   is permitted and recorded.
5. **"How do you rate your position right now?"** → winning / clearly better /
   slightly better / level / worse / losing.
6. **"And after the reply you just named, how would you rate it then?"** →
   `assessment_after_predicted_reply`. **This step is required**, because §5
   cannot distinguish "he misjudged the reply" from "he saw it correctly"
   without it.
7. **"Having said that out loud, do you want to change your move?"** →
   `revised_move`, or none. Both moves are kept. A revision shows prompting
   helped **on that trial**; it does not show the habit was the only gap.
8. **Then grade, show the branch evidence, and give feedback from this table:**

| What happened | Feedback |
|---|---|
| move holds, reply in narrow set | Confirm both. Show the branch and move on. |
| move holds, reply only in wide set | Confirm the move. Show what they actually have and what it is worth. |
| move holds, reply wrong or `not sure` | Confirm the move. Note the right move was found without the reply — worth recording, not correcting. |
| move loses, reply in narrow set | **Do not assume he misjudged.** Ask what he thought happened after it, and compare with his step-6 answer before saying anything. |
| move loses, reply in wide set only | Show the specific capture from `punishing_replies`. |
| move loses, reply wrong or `not sure` | Show the capture. Do not say "you did not look" — he may have searched and missed it. |
| move not in `accept_moves` but plausible | **Pending verification.** Record it; verify after the session; give no verdict. |

9. **`reason_choice`** — the two options from §2.4. The authored correction is
   read **only** if he picks `best_right_now`.
10. The `personalized_game_review.v1` reflection prompt.

**Exploratory timed pass.** Optionally, 6 fresh positions at 60 seconds each.
This is **exploratory and is not equivalent to real time trouble**: there is no
accumulated fatigue, no clock he has already spent, no game at stake, and he
knows it is a test. It cannot stand in for the profile's observation about
low-clock play in won positions; at most it raises a question.

---

## 5. How to read the result

**No threshold is set in advance, because setting one would not validate it.**
Fourteen selected positions — chosen because of how he played them — cannot
establish a general mechanism, whatever the counts come out at. What the session
produces is a record of fourteen decisions and feedback matched to each.

Report the observed pattern, and for each combination state what it is
consistent with rather than what it proves:

| Observed on a trial | Consistent with |
|---|---|
| chose a losing move, **did not** name a relevant reply | he did not look; **or** he looked and did not find it; **or** he looked and expected a different, plausible reply. These are not separable from this record. |
| chose a losing move, **did** name the punishing reply | an evaluation gap — **but only if** his step-6 assessment of the position after that reply was favourable. If he assessed it as bad for him, something else happened: no better option seen, his own candidates mis-ordered, or a miscount further on. Check step 6 before writing anything. |
| chose a holding move, named the reply | the position was handled. Note whether it was a control or a treatment item. |
| chose a holding move, no reply named | he found a good move without working out the reply. Worth recording; not evidence of a habit either way. |
| revised after step 7 and the revision holds | prompting helped **on that trial**. Not that habit was the sole gap, and not that the prompt would help unprompted. |

Compare the two groups only with §7's caveats attached, and prefer the
sub-comparison there over the headline one.

**What a run would let the profile add:** the first recorded values of
`prediction_correct` for any user, and a documented account of how he described
fourteen of his own decisions. **Not** a rate, a trait, a mechanism, a learning
outcome, or that anything was taught.

---

## 6. The record to keep

Per position: `game_id`, `move_number`, `kind`, recognised, `intended_move`,
`expected_reply`, `assessment_now`, `assessment_after_predicted_reply`,
`revised_move`, then the derived `move_in_accept_moves`,
`move_in_accept_moves_strict`, `reply_wide`, `reply_narrow`, `pending_verification`,
`reason_choice`, the reflection option, and free-text notes verbatim.

Store his words as he said them. `not sure` is data — he chose it on 2 of 9
reflections and 20 of 82 reason trials, and a session that pressures him past it
is measuring something else.

---

## 7. Limits, stated before the session

1. **Size and selection.** 8 treatment positions, chosen because he erred in
   them. Difficulty is selected for. The controls hold the evaluation band and
   trap density constant but **cannot hold constant that he erred in one set and
   not the other.**
2. **The groups are not equally hard.** Treatment hold-counts (at depth 18) are
   1, 1, 2, 6, 9, 9, 9, 4; controls are 1, 3, 5, 5, 5, 6. **Both positions where
   only one move holds at every depth are treatment items.** If he scores worse
   on treatment, compare only the sub-groups with 5 or more holding moves before
   concluding anything.
3. **Reply prediction is confounded with move quality.** A material-winning
   reply exists after 87% of losing moves and 22% of holding ones, so naming a
   punishing reply is intrinsically easier after a bad move. Position 1 is the
   clear case: `h3` after the right move, `Qxc4` after the wrong ones.
4. **Engine answers move with depth.** The hold set is identical at all four
   swept depths on only 3 of 14 positions. The packet is frozen for
   reproducibility and grades on the union; a plausible unlisted move is pending,
   not wrong.
5. **Recognition is self-reported** and may be under-reported across 694 games.
6. **Cueing.** A facilitator who says "look again", or pauses meaningfully,
   has ended the measurement. Read only the words in §8.
7. **No retention claim.** One sitting. Retention needs the delayed-transfer
   shape already visible in his `piece_safety` chain — a fresh, unfamiliar
   position, unassisted, first answer, days later.
8. **The timed pass is exploratory**, for the reasons in §4.

---

## 8. Facilitator card

Read only these words.

> *"It is your move. Take as long as you like."*
> 1. *"Do you recognise this position?"*
> 2. *"What move do you intend to play?"*
> 3. *"What do you expect them to reply?"*
> 4. *"How do you rate your position right now?"*
> 5. *"And after the reply you just named, how would you rate it then?"*
> 6. *"Having said that out loud, do you want to change your move?"*
> 7. — then grade, show the branch, and give the §4 step 8 feedback —
> 8. *"How did you pick it?"*
> 9. *"What were you thinking before this move?"*

Never say: "are you sure", "look again", "what about this piece", "there's
something here", or anything about the evaluation. Do not react to his move.

---

## 9. The six repairs made in this revision

1. **Replies are now prepared per candidate move.** v1 stored the reply to his
   historical move and offered it as the expected reply for any accepted move.
   In position 1 it accepted `Qxc7` and expected `Qxc4` — **illegal after
   `Qxc7`, because that move captures the queen that would play it.** Every
   legal move in every position now has its own branch (525 total), and every
   stored reply was asserted legal in its own branch.
2. **Position 1 is described correctly:** he is in check, there are nine legal
   answers, and the decision is how to answer it — including the available
   capture of the checking queen.
3. **The diagnostic overclaims are gone.** No cell means "he doesn't look". §5
   lists the alternatives for each combination, requires his
   after-the-reply assessment before any misjudgement reading, and treats a
   successful revision as help on that trial only.
4. **The pass/refute thresholds are gone.** Nothing is pre-registered as
   validating or refuting; §5 reports patterns and says plainly that these
   positions cannot establish a general mechanism.
5. **Unstable engine answers are handled.** Depths 14/16/18/20 at `Threads=1`;
   grading on the union; "one move holds" permitted on only the 2 positions
   where that is true at every depth; plausible unlisted moves pending rather
   than wrong.
6. **Assessment is separated from teaching.** The recording prompt is neutral
   and claims nothing; the correction is selected by his own reason choice
   rather than pre-assigned to `stops_calculating_too_early`; the timed pass is
   labelled exploratory and explicitly not equivalent to real time trouble.

---

## 10. Running it

The session cannot be run from here: it needs the player's own answers, and
inventing them would make the record worthless. Everything else is ready — the
positions, the per-branch evidence, the neutral prompts, the grading and the
feedback text.

A single-page instrument for conducting it, which shows one position at a time,
captures the six answers in order, and only then reveals the branch evidence and
the matched feedback, accompanies this document.
