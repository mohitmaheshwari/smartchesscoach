# The game story engine: a timeline, an event ledger, then the story

Status: draft v2 for Mohit's sign-off, 2026-10-21. No code yet.
v1 of this file proposed opening / middlegame / finish headings. v2 takes in
the design Mohit pasted the same day (timeline, event ledger, narrative
planner, two reading modes), keeps what fits this product, and changes what
does not. Builds on `docs/game_story_on_screen_scope.md`, which is live.

## What it is

A coach does not hand a player a list of mistakes. They tell the game: how it
started, where it turned, who missed what, and how it ended. Then they give
one lesson that the game actually proves.

The engine does this in four steps. Each step is checked before the next one
uses it.

1. **Timeline.** Who was better at every position, from the stored engine
   evaluations.
2. **Event ledger.** The moments that changed the game, for both players. Each
   moment carries its evidence, and records what happened on the board
   separately from what could have happened.
3. **Story plan.** Which events to tell, in what order, under what kind of
   story, and the one lesson the game supports.
4. **Writing.** Short, plain English from the plan, in two modes from the
   same ledger: a story to read, and coach notes to study.

## What the player sees

Mohit's game 56b6c294, played as Black, won by resignation. Every chess claim
was checked on the board with the engine on 2026-10-21.

### Story mode

```
A WIN WITH TWO NARROW ESCAPES                               You won
Queen's Pawn Opening  ·  They resigned

THE START
The opening was about level.
Then e5 left your d5 pawn weak. They could have won it with Nxd5.
They did not.

THE MIDDLE
Nxg5 let a chance go by. Bxc3 first, and after bxc3 your knight
forks their queen and bishop from c3.
Then they went wrong with e4, and you found the best answer, Nh3+.
Ng5 nearly cost you your queen. After Rh1 she would have had no
safe square. They played f4 instead.

THE FINISH
From there you stayed well ahead, and they resigned.

WHAT TO TAKE FROM THIS GAME
In this game you moved pieces that were guarding something.
Before a piece moves, ask what it was protecting.
```

### Coach mode, the same ledger

```
✗  e5     The e6 pawn guarded d5. After e5, d5 had one defender
          and two attackers. Best for them: Nxd5. Played: Nxe5.
✗  Nxg5   Missed: Bxc3 bxc3 Nxc3, hitting the queen on d1 and the
          bishop on e2.
✓  Nh3+   Their e4 was a big mistake, and this was the best way
          to punish it.
✗  Ng5    The h3 knight was blocking the h-file. After Rh1 every
          queen square is covered. Played: f4.
```

Each coach line opens that move on the review board.

This mockup itself had a false line in its first draft: it said Nh3+ "took"
a loose piece, and Nh3+ is a check, not a capture. The writing step must
check every verb against the move, which is exactly what the quality check
in step 6 is for.

The lesson is earned, not generic. Two of the three mistakes share it: e5
moved the e6 pawn that guarded d5, and Ng5 moved the knight that shielded the
queen.

## What the measurements say

Measured on production, 2026-10-21.

| Measured | Result |
|---|---|
| Positions with a stored evaluation, 2,920 games | 197,000 of 197,000 |
| Opponent moves where their best reply is stored | 31,613 of 95,580 |
| Big chances the player gave that the opponent missed, 3,000 games | in 1,124 games |
| Forced mates the player missed | in 809 games |
| Forced mates allowed that the opponent missed | in 374 games |
| Opening named, chess.com | 939 of 939 |
| Opening named, lichess | 0 of 61, but the stored book record names it from the moves |
| Stored "a pin you could have played" labels resting on a false pin | 388 of 1,457 |

The timeline needs no new engine work. The opponent's best reply is stored
for about a third of their moves, mostly where the player erred, which is
where it matters. The rest is found with a short engine run on only the
positions the ledger selects.

How 2,920 games sort by the shape of the curve, first-cut rules:

| Shape | Games |
|---|---|
| Up and down, lead changed hands twice or more | 527 |
| Clean win, never in trouble | 489 |
| Came back from clearly worse | 461 |
| Was clearly winning and did not win | 378 |
| Outplayed throughout | 265 |
| Level start, then slipped | 263 |
| Decided in the ending | 145 |
| Saved a draw from a bad position | 72 |
| None of these | 320 |

Mohit's game lands in "none of these" on the curve alone, because each danger
lasted one move before the opponent gave it back. Its real story, a win with
two narrow escapes, only appears once the events are added. So the story type
is chosen from the curve and the ledger together.

## What I kept from the pasted design, and what I changed

Kept, because it fits and the data supports it:

- Timeline first, then a ledger of verified events, then the plan, and only
  then the writing.
- Both players' events. What the opponent missed is part of the story.
- "What happened" and "what could have happened" are separate. A missed
  queen trap is never described as a trap that happened.
- One story type per game, chosen only when the game earns it. Most games are
  not dramatic, and the story must not invent drama.
- Three to six moments in a game, not every mistake.
- Two reading modes from one ledger.
- The lesson must be proved by this game, and repeated patterns across games
  become training priorities.

Changed:

- **Plans and intentions are left out of the first version.** Saying what a
  player was trying to do is guessing at a mind. This product has repeatedly
  learned that a board fact is not a cause. A plan appears only where moves
  show it mechanically, such as several pawn moves in a row towards a king.
- **Pressure and initiative are counted, not judged.** "For several moves you
  were the one making threats" is said only from the moves themselves:
  checks, captures, and threats the opponent had to answer.
- **The English is much simpler than the pasted sample.** Words like
  "capitalize", "materially" and "vulnerable", and long sentences, do not
  work for a 600 to 1500 player who may be reading in a second language.
  There are no numbers, as everywhere else.
- **The words are written by rules first, not by a language model.** A model
  may later smooth the English, but only inside a check that rejects any
  sentence claiming something the ledger does not hold. That is how captions
  already work.
- **One story source, not a fifth.** The product already has four services
  that tell a game's story in some form: the coach review story, the coach
  summary, the key-moments service, and the both-sides card on home. They
  disagree with each other today, sometimes about where the game turned. The
  ledger becomes the one source. Each existing surface either reads from it
  or is retired, one at a time, with a check that nothing a player sees gets
  worse.
- **Story types get plain names.** For example: "You came back", "It slipped
  away", "Up and down", "A clean win", "A great escape" and "A win with narrow
  escapes".

## In scope for the first version

1. **Fix first: the pin checker.** It counts a piece as pinned even when that
   piece can take the attacker. Fix the check, relabel the 388 stored labels
   with the idea the board proves or "a chance that went by", and rebuild
   those captions. This is wrong on the live site today, whatever the story
   design.
2. **The timeline,** built at analysis time from stored evaluations, with
   the existing phase measure deciding where the opening and the ending
   begin.
3. **The ledger.** These events, each with evidence and a verification
   status:
   - turning points, from the timeline
   - a player's mistake, and whether the opponent punished it
   - a mistake's real danger when the board proves it: queen lost or
     trapped, or a forced mate allowed
   - missed mates, and allowed mates the opponent missed
   - the opponent's own big mistakes, and whether the player took them
   - good moves from the approved concept checks and executed tactics
   - the opening: its name, how it went, and the costliest opening move
   - the finish: how it ended, and whether a winning position was kept
4. **The story plan:** the story type, three to six events, and one lesson
   that at least two events in the game support, or no lesson.
5. **Writing in both modes,** on the review page. Home keeps a short cut:
   the title, the opening line, and the two most important moments.
6. **Verification before shipping.** Every rule has a test. A run over
   thousands of real games checks the type distribution and that no claim
   lacks evidence. A sample of stories is read by hand against the board.

## Out of scope for the first version

- Plans and intentions, beyond what moves show mechanically.
- A "stopped them castling" check. It is built and proved separately, then
  joins the ledger.
- A language model writing or polishing the story.
- Retiring the four older story services. That comes after, one surface at
  a time.
- Play with Coach games.

## Success criteria

- Every story sentence traces to a ledger event with evidence. A hand-read
  sample finds no claim the board does not support.
- No story calls a game dramatic when its curve and events are quiet.
- The story type distribution over real games matches what the curve and
  ledger show, and is reviewed before any threshold is locked.
- Players open the coach notes from the story, measured by taps.

## Open questions for Mohit

1. **How warm can a line be?** You wrote "a perfect Scandinavian". I suggest
   "You played the Scandinavian well" when no opening move cost anything
   noticeable for the player's rating. "Perfect" would be kept for the rare
   game where every opening move matched the engine. Agree?
2. **The lesson rule.** I propose a lesson only when at least two events in
   the game share it, and otherwise no lesson rather than a generic one.
   Agree?

## Order of work

1. The pin checker fix, relabel, and caption rebuild.
2. The timeline and the ledger, stored at analysis time and measured over
   real games, before any writing.
3. The story plan and story types, with thresholds set from the measured
   distribution.
4. Writing in both modes on the review page, then the home cut.
5. Moving the older story surfaces onto the ledger, one at a time.
