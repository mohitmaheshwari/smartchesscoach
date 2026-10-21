# How Claude finds out why a move was a mistake

Written for whoever designs or extends the reasoning engine.

Two parts, because Mohit asked for two things. Part 1 is the procedure used on
a single position: given a move the engine faulted, how do you work out why it
was worse than the alternative. Part 2 is how that procedure was arrived at —
the loop that turned a hand-reasoned position into a rule the engine runs
176,000 times.

Part 1 is now code (`services/move_reasoning.py`). Part 2 is not code and
probably never will be, which is why it needs writing down.

---

# Part 1 — The procedure, on one position

## Step 0. The engine tells you THAT, never WHY

Stockfish says `Rae1` cost 188 centipawns. That is the entire content of its
opinion. It does not say what the 188 is made of, and the number is not a
reason — it is the receipt for a reason you still have to find.

This matters because the fastest wrong move available is to read the engine's
principal variation and paraphrase it. The PV is what happens *next*; the
mistake is what made it possible. Those are different moves, often several
plies apart. Paraphrasing the PV produces captions that describe the
punishment and never name the error.

So the first discipline: the engine gates, the board explains.

## Step 1. Expect a size

Before looking at anything, decide what kind of answer could possibly be
right.

- 188cp is a positional or small-material lesson.
- 8,600cp is not. Nothing positional explains 8,600cp; somebody is being
  mated, and a sentence about pawn structure on that card is an insult.

Checking this first stops a whole class of confident nonsense. In this engine
it is `_size_is_consistent`, and it cut 51 findings in 500 games — every one
of which was a positional lesson offered to a player in a lost position.

## Step 2. Two futures, and the reason lives in the difference

This is the step that makes everything else work, and it is the one every
other explanation surface in the repo was missing.

Set up two boards: the position after the move that was played, and the
position after the move the engine wanted. Then look for something true of the
first and false of the second.

A fact that is true in *both* futures is a fact about the position. The player
would have faced it either way, so it cannot be why their move was worse —
however true it is, and however well it reads.

```
"Your opponent has not castled"        true after both   → not a reason
"Nc3 blocks your own c-pawn"           false after O-O   → a reason
```

Most true sentences about a chess position fail this test. That is the point.

## Step 3. What do *we* get to do in the better line?

Push the engine's preferred move and look at what becomes available to us that
is not available after the move we played. A square, a capture, a check, a
piece that gets somewhere.

Stated as "the better move was legal before and your move made it illegal",
this is mechanical and cheap, and it catches the large family where the player
stepped on their own plan.

## Step 4. Is my own move physically in the way?

A narrower version of step 3 and worth keeping separate, because it is the
most common shape at 600–1500: the piece you just moved is standing on the
square your own plan needed. It is also the easiest to verify and the easiest
to say in one sentence.

## Step 5. Who is doing what to whom — on the board, not in the line

Walk the board, not the notation. Which of my men are attacked, which are
defended, which stopped being defended when I moved, what can still get to
them. The answers that survive to step 8 nearly all come from here.

The failure this step exists to prevent is reading structure as its effect. A
bishop with no squares is a structural fact; "you are losing" is an
evaluation. Verify the structure, and never let the evaluation stand in for it.

## Step 6. Attack the story before you ship it

Take the explanation you have just built and try to break it.

This step came directly from Mohit reading a card that said his knight came
back to b1 and losing patience with it:

> "why would nC3 comes back to b1, there is no attack on nc3 in coming
> future, it's safe there"

He was right, and the board agreed: nothing ever attacked c3, so the knight
was regrouping, not retreating. "The move loses time" was reading a deliberate
manoeuvre backwards. Measured afterwards: **102 of 264 retreat findings, 39%,
failed their own premise.** Four cards in ten.

So for every claim, ask what the claim assumes, and check that the board
agrees. A claim whose premise is unverified is not a weaker claim, it is a
different claim.

## Step 7. Does the answer match the engine's number?

Now go back to step 1 with an actual answer in hand. If the claim names
material, the material has to account for the loss — not approximately, and in
the right direction.

Two ways this fails, and they want different fixes:

- **The claim is too big.** "dxe5 wins your knight" on a move the engine
  priced at one pawn. The claim is describing a different event.
- **The claim is too small.** Naming a pawn on a card where a pawn *and a
  knight* fall. True, and it tells a player who lost four pawns that they lost
  one.

The second one is subtler and took a full-corpus scan to find. It is also the
one where the obvious fix is wrong — see Part 2.

## Step 8. One sentence a 1200 would use

Deliberately not the engine's job. The engine emits structured evidence; the
caption layer turns it into English, because that layer is voice-tested and
verified and there is a CI guard against teaching prose appearing anywhere
else.

The sentence has to name the concept, not the coordinates. "Users remember
patterns, not moves."

---

# Part 2 — How the procedure was arrived at

Part 1 reads like it was designed. It was not. Every step in it exists because
a specific card was wrong, and the loop below is what converted each wrong
card into a rule. The loop matters more than the steps, because the steps will
keep changing and the loop is how they change.

## 1. Start from a card that is wrong, never from a theory

Every question in the engine traces to a position someone looked at and said
"that is not why". Not one came from a taxonomy of chess concepts.

The failures are better raw material than the successes. A card that is silent
tells you a mechanism is missing; a card that is confidently wrong tells you
which mechanism is wrong, and roughly where.

## 2. Reason it out by hand, in words, before touching code

Sit with the board and say in plain language why the move was worse than the
alternative. No code, no probe, no engine line.

This is slow and it is the only step that cannot be skipped. Every shortcut
around it — classify the position by its material signature, cluster by
keyword, ask a model — has produced a wrong answer in this repo, and the
record is in the memory files.

## 3. Ask whether it is one position or a family

A hand-reasoned explanation is an anecdote. Before it earns any code, ask how
many cards in the corpus have the same shape, and specifically how many of
those currently say *nothing*.

For the loose-man mechanism:

```
1,874 cards carry a man of ours that is attacked and undefended
  520 of those, the better move holds him and the played move does not
  493 of those were silent
```

493 silent cards was more than the entire framework explained at the time.
That is what justified building it. Had the number been 11, the honest
conclusion would have been "interesting, not a feature".

## 4. Design the pattern, never the position

The flagged position is one sample of a family. A clause set that fires on it
and nothing else is a hardcoded answer with extra steps.

## 5. Pay for honesty in reach, deliberately and with the number

The loose-man question has a clause that costs most of its coverage: **they
must actually take the man.** Loose and never taken is a risk, not a cost, and
it cost 267 of the 493 cards to insist on the difference.

That trade should always be explicit. Write down what the clause costs, so the
next person can argue with the price instead of guessing it.

## 6. Pick thresholds from the distribution, never from judgement

Look at the histogram first. Then say which you found:

- **A real break.** Material falling beyond the man named: 63.3% at exactly
  zero, 7.4% at one pawn more. An 8.5× cliff. The threshold is the cliff.
- **A judgement at a percentile.** How far a claim may sit above the engine's
  number: p95 is +202 and the tail is smooth. 200 keeps 95%, and the comment
  in the code says it is a judgement rather than pretending otherwise.

Both are legitimate. Confusing one for the other is not.

## 7. Write the control test, and give the probe a positive control

Two different things, both required.

The **control test** asserts the board facts independently of the code under
test — attackers computed by hand, legality checked, not "the function said
so".

The **positive control** asserts the measuring harness can detect the thing it
is looking for, *before* its report of absence is believed. A probe that
cannot see a finding will report that there are none, in a confident voice.

## 8. Run at full scale, and hunt the defect rather than the headline

500 games said the loose-man question was the cleanest in the engine. True,
and incomplete. 18,920 games found 962 of its claims naming a man worth less
than a third of the loss — the only question in the engine doing that.

A small sample can nail the total volume and still miss the shape. Scale is
not for a tighter percentage; it is for the failure mode that is too rare to
appear in a slice and common enough to matter in production.

## 9. When you find a defect, measure before you fix it

The obvious fix for "the claim is too small for the loss" is a ratio: refuse
claims under some fraction of the loss. Measuring killed it.

Of 515 such claims, **301 (58.4%) were sound** — the large number was the
*consequence* of losing the man, not evidence that more material went. A ratio
would have deleted about 560 good cards to repair about 400 bad ones.

The real discriminator was not the size of the loss at all. It was what the
line does: walk it, and count whether more falls than the man being named.

## 10. Ask whether the fix belongs to the question or to the framework

It belonged to the framework, and getting this wrong is apparently easy,
because the file had already learned it once. `_size_is_consistent` carries
the note that it was promoted to a framework rule because it "lived inside a
single question, so it protected one concept and nothing else" — and the swing
check shipped as one question's clause anyway, an hour later.

The tell was the clearance. The ratio metric scored every *other* question at
0%, so they looked clean. But that metric had just been shown to catch only
385 of 1,550 real defects. Re-measured properly, a second question had 275 of
the same defect, including one on a 133cp card naming a 330cp bishop — ratio
0.4×, invisible to any ratio bar that could ever be set.

**A zero from an instrument you have just proven blind is not evidence of
absence.**

---

# The part worth repeating

Across the session that produced this engine, the engine's chess data was
correct every single time. Nearly every wrong answer came from the layer that
measured it:

- a counter that merged three unrelated rejection reasons under one label, so
  a flat 8 looked like a jump to 175;
- a probe that passed four arguments to a two-argument helper, swallowed the
  `TypeError`, and reported a clean **100.0%**;
- a control whose own line recaptured the piece it claimed was lost;
- a classifier run twice on caption text that scored two perfectly good
  explanations as explaining nothing;
- a harness with the player's colour hardcoded, which rejected every claim in
  every game played from the other side.

Not one was a chess bug. All five would have shipped a confident, specific,
wrong number, and the only reason none did is that each produced a figure too
tidy to believe — 100.0%, or an unchanged 8, or a zero.

So the last rule, which is really the first: **when a measurement comes back
clean, suspect the measurement.** The board is almost never the thing that is
broken.
