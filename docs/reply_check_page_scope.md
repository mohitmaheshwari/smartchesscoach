# Scope: the reply-check page in ChessGuru

**Why.** The session needs the player's intended move, the reply he expects and
his assessment, recorded before any help. Typing moves in chess notation is the
wrong interface — the facilitator has to read SAN out loud and transcribe it,
which is slow and error-prone. The player should play the move on a real board
and the page should work out the notation.

**One sentence.** A page where he plays each move on a board, the page records
what he chose before showing him anything, and the whole sitting is saved.

## What it does

Fourteen positions, one at a time. For each:

1. "Do you recognise this position?" — two buttons.
2. **He plays his intended move on the board.** Only legal moves land; he can
   take it back until he locks it. The page converts it to notation.
3. **He plays the reply he expects, on the same board**, from the position his
   own move produced. Or says "not sure".
4. "How do you rate your position right now?" — six buttons.
5. "And after the reply you just named?" — the same six.
6. "Do you want to change your move?" — plays a new move, or keeps.

Only then does the page show whether the move holds, what the opponent actually
has, and the feedback matched to what he did. Then two existing questions: the
`calculation_depth` reason options, and the `personalized_game_review.v1`
reflection prompt.

## What it is not

- Not a trainer: no score, no streak, no "correct!", nothing that ranks him.
- No hint, no engine line, no evaluation shown before step 6 is recorded.
- No new detector, scoring engine or coaching logic. The page reads a frozen
  packet and writes down answers.

## Data

**Reads** a frozen packet at `backend/data/reply_check/<user>.json` — the one
already prepared and verified, with every legal move's branch. Nothing is
computed at request time.

**Writes** one document per position to a new collection `reply_check_responses`:
the identifiers, his six answers, the derived flags, and his reason and
reflection choices. Append-only. It stores answers, not judgements about him.

## Endpoints

```
GET  /api/coach/reply-check/packet     the positions, without the answer keys
GET  /api/coach/reply-check/evidence/{position_id}   the branch data, after recording
POST /api/coach/reply-check/response   record one position
GET  /api/coach/reply-check/responses  what has been recorded so far
```

The evidence is a separate call on purpose: the answer key does not reach the
browser until his answers are recorded, so it cannot be read ahead by accident.

## Route

`/reply-check` — authenticated, not linked from any nav. It is an instrument for
one sitting, not a product surface.

## Done when

- He can play a move with the mouse and never type notation.
- The page refuses to show evidence until all six answers exist for that position.
- A reload mid-session resumes where he left off.
- The recorded sitting can be read back from the database.

## Deliberately out

Timed pass, multi-user support, an admin view of results, and any aggregate
read of the responses. One player, one sitting, recorded faithfully.
