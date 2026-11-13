# Opponent mistake cards: name our answer and draw it

Status: built 2026-11-13 under Mohit's standing sign-off for small features.
His answer to "rewrite the caption or always draw the reply?": "best of both".

## 0. Existing surfaces

- `caption_pipeline` draws an opponent card's picture from its own caption
  (`opponent_reply_picture`); since v246 `repick_opponent_arrows` re-picks it
  for the words the card ships with. Both only draw a reply the words name.
- `_reply_attack_arrows` already proves, on the board, what a reply does
  (check, a capture that wins material, an attack on a winnable piece).
- Decision: EXTEND. No new surface; one sentence and its arrows on the existing card.

## 1. What it is

An opponent mistake card whose words name no move of ours, and that draws
nothing, gets one sentence saying our best answer and what it does, with the
answer drawn on the board. Words and arrows come from the same board check.

## 2. What the user sees

    Opponent  43. Ke5   Blunder
    Your opponent played Ke5; Ke7 was the stronger move here.
    Your best answer is Qb8+: it checks the king.
    [board: b4->b8 blue, b8->e5 red]

## 3. In scope

- Opponent cards graded mistake, serious or blunder, with text and no arrows.
- Answer = next position's engine move, else the first move of the line;
  legal on the board shown; must check, capture, or attack a winnable piece.
- Capture said first. Sentence only if the card stays within the word cap.
- Skipped when the words already name a legal move of ours (one recommendation).

## 4. Out of scope

- Quiet answers (no check/capture/target): no sentence, no arrow.
- Silent cards (empty caption under a mistake badge): separate issue.
- Inaccuracy cards; our own cards.

## 5. Success

- Opponent mistake cards with an arrow, on Mohit's 8 newest reviews: 40/52
  before 2026-11-13, 44/52 after (dry run), no caption change elsewhere.
- No card shows an arrow its words do not explain.

## 6. Open questions

- Should silent opponent mistake cards (4 of 52 in that sample) get this
  sentence as their whole text? Mohit's call.

## 7. Pre-code requirements

- Met: sign-off ("best of both"), dry run on real reviews, tests in
  `backend/tests/test_opponent_arrows_follow_the_shipped_words.py`.
