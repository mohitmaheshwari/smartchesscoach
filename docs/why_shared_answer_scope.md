# Same reply, different answer, and review cards that ask the engine

Status: SIGNED 2026-11-27. Mohit sent a screenshot of a review card ("this just
tells the line straight up, what the fuck, we have an engine that should be
called and should call LLM for translating to english"). I proposed three steps:
teach the engine this case, make the card ask the engine, and name the better
move when the engine has no reason. He replied "do it".

## 0. What already exists

| Piece | What it does | Gap |
|---|---|---|
| Personalized review card (`game_review_event_adapter._verified_line_teaching`, Sept 1, on in prod) | Exchange, missed-material and missed-mate causes write "After X, the line is a, b, c, d, e. When every recapture is counted, you give up ...". | It reads a stored engine line aloud. On 18.Qd2 the five moves shown contain no capture, yet the card lists six pieces taken further down. No engine reasoning, no words layer. |
| Why engine (`reasoning/differential.py`, behind the why button, on in prod) | Measures both moves and their replies, then explains the difference. | When both moves allow the same reply, it calls that reply "shared" and stops. On 18.Qd2 the prod engine returned `shared_consequence_only`, with no sentence. |
| Words layer (`why_words.py`, gpt-6-luna, on in prod) | Rewrites the engine's facts in plain English, checked against the facts. | Not used by the review card. |
| `/coach/why/{game}/{move}` | The why button's endpoint: engine first, then words, then the why queue. | Only the V5 move card calls it. |

Decision: EXTEND. Add one more engine step, and have the existing card call
the existing endpoint. No new page.

## 1. What it is

**A. Engine.** When both moves allow the same reply, the difference can be
what the mover can do about that reply. Take the mover's answer from the better
move's line, then check whether it still exists after the played move:

- it may be illegal there, for a reason the board shows (the piece moved away,
  the square is taken, the path is blocked);
- or it may still be legal but lose material, by the engine's own line.

**B. Card.** A review card that reads out a line asks the why engine for the
reason when it opens, and shows the engine's finding in the words layer's
English. When the engine has no reason, the card names the better move and
says it cannot put the reason into words yet. It never shows the raw line.

## 2. What the user sees

18.Qd2 (`2r1r1k1/pp2bpp1/1q3n1p/n2P4/7B/2N2B2/PPQ2PPP/1K1R3R w`), production engine:

    Before: After Qd2, the line is Qd2, Nc4, Qc1, Ba3, Rd2. When every
            recapture is counted, you give up a rook, a bishop, and a knight
            but take only two knights and a bishop.
            Keep this with you: Before starting a capture sequence, count
            every recapture to the end.
    After:  d6 was the move. Both moves allow Nc4, but after d6 you answer it
            with Qb3 and trade queens. After Qd2, your queen is no longer on
            c2, so Qb3 is not possible.
            (arrows: d5-d6, a5-c4, c2-b3; the words layer may rephrase)

When the engine has no reason: "d6 was the stronger move here. I can't put the
reason into words yet."

## 3. In scope

- `reasoning/shared_answer.py`. It runs last, only when no other answer was
  found and the move is a mistake or a blunder, so no existing sentence
  changes. Conditions:
  - the same reply on both branches;
  - the branches differ by at least 200 cp and by at least half the gap;
  - the answer differs from the played branch's answer;
  - either the answer is illegal after the played move for a board reason, or
    a search restricted to the answer loses at least 200 cp and its line wins
    the mover's material.
- New mechanism `SHARED_REPLY`: `build_facts` carries the reply, the answer,
  the trade, and why the answer is gone; `why_words` has the relation and its
  check.
- Threat-line fix found on the same position (local engine): "Qd2 stops your
  queen guarding d2" was written about the queen standing on d2. The
  played-move-left guard sentence no longer fires when the played move lands
  on the threatened square.
- `TeachingReference.explain_from_engine`, set for the three line-reading
  kinds. `PersonalizedReviewCoach` fetches `/coach/why` on reveal, shows its
  text and draws its arrows, and on those cards hides the line's principle and
  its "Show the relationship" arrows.
- `V5_COACHING_VERSION` 250, so stored reviews pick up the flag.

## 4. Out of scope

- An answer that is illegal for any other reason (a pin, a check): measured,
  not put into words.
- Saying why the answer matters beyond the trade, or anything about the
  answer's line past the trade.
- The other personalized-review cause kinds (hanging piece walk-through,
  allowed mate, exact endgame); those write sentences rather than lines.
- Working out the reason when the review is built. The card asks when it
  opens; the button already pays that wait.

## 5. Success criteria

- Regression set (42): no sentence changes that is not read true on the board.
- Random real mistakes: every new firing is read true by hand.
- 18.Qd2 on the production engine gets the sentence in section 2.
- No new test failures.

## 5b. Results (2026-11-27, production engine image, button config)

- 18.Qd2: fires, with the sentence in section 2.
- Regression set: 0 of 42 changed. The new step ran on 3 positions (2
  different replies, 1 branches close) and fired on none. The threat-line fix
  changed nothing in the set.
- Random sample: see the commit message (80 real mistakes, cp loss 150+,
  `move_observations`, seed 1127).
- Tests: `tests/test_reasoning_shared_answer.py` 9 passed. Frontend
  `PersonalizedReviewCoach.test.jsx` 13 passed (3 new). Backend selection
  (reasoning, why, review): 945 passed, 9 failed, and the same 9 fail on
  working-code without this change.

## 6. Open questions

- Does the half-the-gap floor suit this case? It is kept from the other
  lines; the measurement is stored on every run (`result["shared_answer"]`).

## 7. Pre-code

- Signed (above). Branch `claude/why-shared-answer` from working-code 9c7b900a.
  No open PR touches these files (PR #1 only).
