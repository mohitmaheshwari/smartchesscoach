# First steps — scope

**Status:** DRAFT — awaiting Mohit's sign-off. No code until signed.
**Author:** Claude, 2026-11-06, against `origin/working-code` at 290803eb.
**Mockup:** the first class (the rook, with "collect the stars"), playable —
linked in the sign-off record at the end.
**Sibling:** `docs/ai_personal_class_scope.md` — the same class shape for a
child who already has games. This document is for the child who has none.

Mohit, 2026-11-06: *"a parent comes to us, says my child wants to learn chess,
we don't have anything there."*

---

## 0. Existing surfaces audit

| Existing | What it does today | Use here |
|---|---|---|
| `backend/data/board_geometry_lessons.json` (4 modules, `review_status: engine_verified_internal`) | Short visual lessons on the straight line, diagonal, knight L and pawn V. Activity kinds already built: `select_piece`, `select_targets` ("tap every empty square the rook on d4 can see"), `choose`, `move`. Stages run baseline → practice → post-test → delayed recall | **The activity format for every rules class.** The four shapes become the rook, bishop, knight and pawn classes |
| `/training/geometry` page and its player | Plays those activities with hints | The base of the class player |
| AI personal class (draft, 290803eb) | Warm-up → idea → practice → play it → wrap-up, adapting to answers | **The same sequencer.** First steps adds content, not a second engine |
| Academy and family accounts | A child can be added with **no** chess account (`routes/academy.py` takes the usernames as optional; the test child shows "No online account added") | Where a first-steps child is created |
| Class games (`/play/:token`, built 2026-11-05) | Two children of a batch play on our site; the game is stored in `games` and queued for analysis | The bridge from rules to real games for academy children |
| Play with Coach opponent | Never plays below 1500 (`coach_play/coach_opponent.py` line 104) | **Not usable** for a beginner |
| Win it back opponent (`routes/academy.py` `homework_opponent`) | Plays at a given rating; measured 2026-11-05 at skill 3 for rating 900 | Still far too strong for a child who just learnt the moves |
| `docs/teaching_opponent_scope.md` (status: SCOPE, unsigned) | An opponent that teaches | Read before designing the first opponent; not reused blindly |
| Diagnostic v2 | Puzzle placement for players who already play | Not for a child who does not know the moves |
| Rules of chess content | **None found.** No lesson on how the pieces move in the lesson data or the curriculum documents | New content — the main work of this scope |

Outside us: Lichess has a free "Learn" section for the rules (not checked
today). The difference we offer is the coach, the personal next class, and the
parent report — not the rules themselves.

**Decision: EXTEND.** New content (rules classes and mini-games) played by the
existing geometry activity format inside the class sequencer. One genuinely new
piece: a first opponent weak enough for a beginner.

---

## 1. What it is

A path for a child who has never played. A two-minute placement finds where
they are. Then short classes teach one piece at a time, each ending with a
little game — collect the stars with the rook, a pawn race, a capture race.
Every tap tells the coach something, so the next class repeats what the child
found hard. After the last rules class the child plays real games on
ChessGuru against an opponent at their level, and from then on the personal
class built from their own games takes over. The parent gets one line after
every class, and the weekly report once there are games.

## 2. What the user sees

```
PARENT                    CHILD
Sign up "I am a parent"   ┌───────────────────────────────┐
Add child (no account)    │ Hi Aarav! Let's find out what │
        │                 │ you know.                     │
        ▼                 │ Tap the rook.        [board]  │
  Placement (2 min) ────► │ Where can the knight go?      │
  three tap tasks         │ Which move is check?          │
        │                 └───────────────────────────────┘
        ▼
  Level 0 "never played"  → class 1 the rook ... class 8 checkmate
  Level 1 "knows moves"   → check, checkmate, first games
  Level 2 "plays games"   → first games, then the personal class
        │
        ▼
┌─────────────────────────────────────────┐
│ CLASS 1 · THE ROOK              ★ ☆ ☆ ☆ │
│ Warm-up   Tap the rook.                 │
│ Idea      The rook goes in straight     │
│           lines. Tap every square it    │
│           can reach.                    │
│ Practice  A pawn is in the way. Where   │
│           can it go now? / Which piece  │
│           can the rook take?            │
│ Play it   ★ Collect the stars ★         │
│           in as few moves as you can.   │
│ Wrap-up   Next class: the bishop.       │
│ Parent:   "Today Aarav learnt how the   │
│           rook moves."                  │
└─────────────────────────────────────────┘
```

What the coach notices from taps, without any games:

```
Tapped a diagonal square       → "That's how the bishop moves" ;
                                 bishop class compares the two
Tapped a square behind a piece → "It can't jump" ; next warm-up
                                 starts with a blocked rook
Took more moves than needed    → the stars game repeats at the
                                 same level before the next one
```

## 3. In scope (V1)

- **Placement:** three tap tasks, scored by fixed rules, putting the child at
  level 0, 1 or 2. The parent can override.
- **Eight rules classes**, each in the class shape (warm-up, idea, practice,
  play it, wrap-up): rook, bishop, queen, knight, pawn (with promotion), king,
  check, checkmate (king and queen against king, in one move).
- **Three mini-games**, each with a level that gets harder:
  - *Collect the stars* — one piece, stars on squares, fewest moves (the
    least possible number worked out by the computer, not authored);
  - *Pawn race* — pawns only, first to the far side wins;
  - *Capture race* — one piece against a few pawns that move.
- **Every answer is exact.** Rules tasks are checked by legal-move logic, not
  an engine opinion, so every reply can be proved.
- **Mistake kinds recorded per answer** (wrong direction, jumped a piece,
  missed a capture, moved into check). The next class's warm-up uses the
  child's most frequent kind.
- **A first opponent** for the first real games: plays like a beginner, leaves
  pieces to be taken at a rate set by data (section 6), never plays a long
  forced win against a beginner.
- **Graduation:** after the checkmate class and the first three real games,
  the child moves to the personal class from their own games.
- **Read-aloud** with the browser's own speech for every coach line, so a
  child who reads slowly can follow. Output only — no microphone.
- **One parent line after each class**, in plain words with no numbers.

## 4. Explicitly out of scope (V1)

- **Listening to the child** (microphone). Read-aloud only.
- **Castling, en passant and draws** as their own classes. They come up in
  the first games and are explained there.
- **A coach character, sounds and animations** beyond stars.
- **Hindi and other languages.**
- **Openings.** A beginner learns the pieces and checkmate first.
- **Children under about five**, who cannot follow a tap-and-read class even
  with read-aloud. Parents of younger children are told so.

## 5. Success criteria

1. **Children finish without a human.** Of the level-0 test children, the
   share who complete all eight classes and play a first full game within
   three weeks, with no reminder from a person.
2. **They really learnt the moves.** Every class ends with a no-hint check
   (the geometry lessons already have this stage). A class counts as learnt
   only when that check is passed, and again when the delayed recall a few
   days later is passed.
3. **They come back.** Day-2 and day-7 return without a reminder — the same
   kill test as the personal class. Mohit sets the bar before the test.

Not success: classes opened, stars given, minutes spent.

## 6. Open questions

| Question | Why unresolved | Unblocking step |
|---|---|---|
| Youngest age we accept | Depends on reading; read-aloud helps but is untested with children | Try with two or three children aged 5–6 in the test group |
| How weak is the first opponent? How often does it leave a piece? | Not measured | Measure on the first test children's games; lock with data |
| Which opponent engine? A very weak engine setting, Maia's lowest model, or our own rule-based "beginner" | Maia's lowest model is far above a child who just learnt the moves (not measured here) | Compare the three on a few games, then choose |
| Coach name and look | Product taste | Mohit, after the mockup |
| Placement tasks — are three enough? | Not tested | Try on the test children; add a fourth only if levels come out wrong |
| Does recording mistake kinds count as behavioural monitoring under DPDP section 9(3)? | Same question as the personal class | The lawyer |

## 7. Pre-code requirements

- Mohit signs off this document.
- The eight classes are written out as content (prompts, positions, answers,
  hints, the no-hint check, the delayed recall) and every answer is checked by
  legal-move logic before code.
- The test children are named, including at least two who have never played.
- The first-opponent question has a measured answer before that piece is built
  (the rules classes can ship first without it).

---

## Sign-off record

- 2026-11-06 — drafted. Awaiting Mohit.
- Mockup (playable first class, the rook): https://claude.ai/artifact/7A1SVPguLVSmcaU5iRPvzV
