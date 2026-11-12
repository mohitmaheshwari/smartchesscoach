# A published coach study becomes the card's caption, marked as the coach's

Status: DRAFT, awaiting Mohit's sign-off (2026-11-12).

## 0. Existing surfaces audit

| Surface | What it already does | Where |
|---|---|---|
| Why box | Shows a published study after the player presses Why, with a small grey mark "· studied later by the coach" | `GameDecryptionV5.jsx:2289`, `why_queue.known_answer` |
| Card caption | Written when the review is generated, stored in `game_analyses.decryption_v5_data`; never reads `why_reasons` | `game_decryption_v5_service.py` |
| Caption override hook | Replaces a card's caption text from `authored_caption_overrides`, keyed **per game** (game_id, move number, move); engine fields stay | `game_decryption_v5_service.py:4785` |
| Admin "Agree" | Publishes a study (`apply_ruling`); changes nothing on any card | `why_queue.apply_ruling` |

Measured 2026-11-12 on the three published studies: the card shows the old caption first. On Rf7 the
caption and study agree. On Ke7 the caption ("They missed Bd6 — it brings a new piece into the game")
implies Bd6 saves the rook; it does not, the f8 bishop is the difference. On e5 the caption ("Play Nge7
— it brings a new piece into the game") explains nothing; the study says the pawn is not won back.

**Decision: EXTEND.** Same override hook, same card, same Why-box wording. No new page.

## 1. What it is

When the coach has studied a position and a person has agreed with the study, every review card for
that position shows the coach's study as its caption, with a small label saying it came from the coach.
The player no longer reads a weak caption first and finds the real reason only behind a button.

## 2. What the user sees

```
┌──────────────────────────────────────────────────────────────┐
│  6. e5  ·  Opponent's mistake                                │
│                                                              │
│  STUDIED BY THE COACH                                        │
│  Your opponent played e5. That was a mistake. Their e5 does  │
│  not win back the pawn they gave up. So you stay one pawn    │
│  up. c3 was better for them. That pawn attacks your pawn on  │
│  d4. Then cxd4 takes it back, and the pawns are even again.  │
│                                                              │
│  [board: red arrow e4→e5, green arrow c2→c3]                 │
└──────────────────────────────────────────────────────────────┘
```

- The label is small, above the caption, in the card's muted label style (like "Why" in the Why box).
- The grade line ("Your opponent played e5. That was a mistake.") stays from the card; the study
  replaces only the explanation after it.
- Arrows come from the study's replayed claims, the same arrows the Why box draws today.
- The Why button is not shown on that card: its answer would repeat the caption word for word.

## 3. In scope (V1)

- **Prerequisite bug fix: the side guard.** A study is keyed by position, but its "you" and "their"
  are written for one side (`why_reasons.side`). Today `known_answer` returns a published study to
  anyone who presses Why on that position, whichever side they are on, so the pronouns can come out
  backwards. A study is used, in the Why box and on the card, only when the viewer is on the same side
  as the study.
- The V5 generator reads a published study **by position** (fen4 + move) at the override hook, after a
  per-game authored override (a human-authored override still wins), with the side guard.
- A card that uses a study carries `caption_source: "coach_study"`; the frontend shows the label and
  hides the Why button for that card.
- When a study is published (admin Agree, or the worker with auto-publish), the games that asked about
  that position (`why_queue.requests[].game_id`) are re-rendered in the background, so their stored
  caption actually changes. Other games with the same position get it on their next re-render.
- Verified on the three published positions (Rf7 game_48c…, Ke7 5e68fc88, e5 2d86e1f9): the stored
  caption, then the rendered page, shows the study and the label.

## 4. Explicitly out of scope (V1)

- **No-lesson studies on the card.** b3 and e6 keep their card caption. Whether a "no single lesson"
  study should soften the card's "mistake" is a separate question.
- Re-rendering every game that contains a studied position (would need a position index over all
  games; not built).
- A version bump to force re-renders (would re-render every game).
- Notifications that a card changed.
- Play with Coach and other surfaces.
- Rewriting the study text to fit the card; it is used as published.

## 5. Success criteria

- On every card for a published, same-side position, the caption is the study and the label shows:
  3 of 3 on the current set, checked on the rendered page, not only in the database.
- Zero cards where the study appears with the wrong side's pronouns (checked by rendering each of the
  three positions from the other side, where the old caption must stay).
- Behaviour: Why presses on those cards fall to zero (the caption already answers), with no rise in
  the "this doesn't make sense" feedback on them.

## 6. Open questions

- **Label wording.** Recommendation: "Studied by the coach", which matches the Why box's existing
  "studied later by the coach". Alternatives: "Coach's note", "Coach's study".
  *Unblocking:* Mohit picks.
- **Keep or hide the Why button on a studied card.** Recommendation: hide (it would repeat the
  caption). *Unblocking:* Mohit.
- **If a study is later rejected or re-studied,** the card should fall back to the generated caption.
  Recommendation: the same background re-render runs on Disagree and on a re-study write.
  *Unblocking:* Mohit.

## 7. Pre-code requirements

- Mohit signs off this document, including the three open questions.
- Check open PRs and branches touching `game_decryption_v5_service.py`, `why_queue.py`,
  `GameDecryptionV5.jsx` before the first edit.
- The re-render uses the existing single-game regeneration path (no second generator).
- Deploy then re-render (migrate after deploy, never before).
