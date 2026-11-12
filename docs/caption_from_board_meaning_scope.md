# Captions explain what the moves do, never list them

Status: SIGNED 2026-11-12 (Mohit: "yes, go ahead"). Pre-code checks under way. Mohit, same day: "it should not just turn up
the opportunity, understand the moves on the board and then convert ... naming the moves is very
very bad"; "you should know who is winning, losing ... what items are down ... what is relevant and
what piece is not relevant on the caption".

## 0. Existing surfaces audit

| Surface | What it already does | Where |
|---|---|---|
| Card line steps | One short sentence per move of each card line ("Bishop gives itself up on f7. Check.", fork targets, captured square) | `caption_pipeline.describe_line_steps`, `game_decryption_v5_service._v5_line_steps` |
| Card caption | Detectors + templates, verify-then-ship; often "They missed X here" or "Play X - it brings a new piece" | `caption_pipeline.py`, `game_decryption_v5_service.py` |
| Live Why button | Deterministic contrast of the played and better lines: timeline with piece identities, events, relations, chain builder, verify; English by templates, optional `why_words` (gpt-6-luna) phrasing | `services/reasoning/*` (`differential.explain_move`, `timeline`, `chain_builder`, `verify`), `why_differential.py`, `why_words.py` |
| Why queue study | Opus with an engine writes, Fable with an engine checks; since 2026-11-12 the packet carries `situation` (who is winning, what is up or down) and `line_readings` (deciding moment, relevant moves) and the gate refuses any move in notation except the played and better moves | `why_study.read_line`, `why_queue_worker.py` |

Overlap, stated plainly: `why_study.read_line` (deciding moment by quiet-moment material, relevance
by piece participation) repeats part of what `reasoning/timeline` + `chain_builder` already derive
with stronger piece identities. Two readers of one line is the duplication
[[feedback_single_source_of_truth]] forbids for anything that reaches a card.

Measured 2026-11-12 (`project_line_to_english_probe`): gpt-6-luna handed the card's line steps
wrote ~3 of 23 captions better than today and ~10 worse. Every failure was the same: a move list
in, a narrated move list out.

**Decision: EXTEND.** One line reader (the reasoning timeline), used by the card caption, the Why
button and the queue. No new page.

## 1. What it is

Every card caption first understands the position and the two lines: who is winning and what is
up or down, what the better move's line wins or saves and the moves that make that happen, and
what goes wrong after the move played. Only the moves that take part in that are explained, by what
they do, in plain words. The caption names at most the better move. Everything else Stockfish
played stays out.

## 2. What the user sees

```
┌──────────────────────────────────────────────────────────────┐
│  6. e5  ·  Opponent's mistake                                │
│                                                              │
│  Your opponent played e5. That was a mistake. Their e5 lets  │
│  you keep your extra pawn. The better plan was c3, attacking │
│  that pawn. If you take it, their bishop gives itself up on  │
│  f7 to pull your king out. Then their queen checks your king │
│  and hits your bishop at once, and wins it back.             │
└──────────────────────────────────────────────────────────────┘
```

Today the same card says "Play Nge7 - it brings a new piece into the game. They missed c3 here."

## 3. In scope (V1)

- One line reader: extend `reasoning/timeline` with the reading the caption needs (situation in
  words, deciding moment at a quiet moment, relevant moves by piece participation), and point
  `why_study` at it; `why_study.read_line` is removed.
- A caption "meaning" record per faulted card from that reader: situation, what the better line
  achieves, what goes wrong after the played move, the relevant pieces and what each does.
- Caption text from the meaning record (templates first; `why_words`-style phrasing only of a
  finished meaning, behind the existing containment check).
- The no-notation rule as a hard check in verify-then-ship: no move in notation except the played
  and better moves.
- Measured on a fixed set (the 23 probe cards + the why-queue positions), before and after.

## 4. Explicitly out of scope (V1)

- Changing detectors or what counts as a mistake.
- Re-rendering every stored review (only on the normal version bump path, after measurement).
- Positional lessons with no material or mate in either line (they keep today's captions).

## 5. Success criteria

- Zero cards with a move in notation other than the played and better moves.
- On the fixed set, more captions judged "explains why" than today, and none that contradict the
  card's own lines, judged blind per card.
- Behaviour: fewer Why presses on cards whose caption already explains (the press is the player
  saying the caption did not).

## 6. Open questions

- **Template or model wording for the meaning record.** Templates are safe and stiff; the model
  reads better and needs the containment check. *Unblocking:* measure both on the fixed set.
- **Which line wins when the card's line and a deeper search disagree** (6.e5: the card plays
  dxc3, a deeper search prefers d6). Recommendation: the caption explains the card's line and adds
  the main idea, as in the mockup. *Unblocking:* Mohit.

## 7. Pre-code requirements

- Mohit signs this document.
- Check open PRs and branches touching `services/reasoning/*`, `caption_pipeline.py`,
  `game_decryption_v5_service.py`.
- The fixed set and today's captions on it are snapshotted before any change.
