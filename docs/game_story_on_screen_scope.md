# The game story on screen: the review page and the home page

Status: draft for Mohit's sign-off, 2026-10-21. No code yet.
Builds on `docs/game_story_at_analysis_time_scope.md`, which made the story.
This document is about where a player sees it.

## What it is

Every analysed game already has a short story: the few moves that mattered,
good and bad, and one or two things that were true for a long stretch, such
as a rook that never got out. Nobody can see it yet.

This puts it in two places:

1. **The game review page.** It opens the review, above the walkthrough. Each
   line is a move you can tap to jump straight to it.
2. **The home page.** The card that already shows your last game gains the
   same story, cut down to its top lines. When the coach has picked a game
   for you to review, the card shows that game instead of the last one.

## What the player sees

All text below is real output from real games in the database, except lines
marked *(new)*. Those are what the rules in the next section would produce.

### Home page: a lost game (game 20619e20, white, lost by resignation)

```
┌───────────────────────────────────────────────────────────────────┐
│  ┌─────────────┐   YOUR LAST GAME                                  │
│  │             │                                                   │
│  │   board,    │   They held together better than you did.         │
│  │ position    │   They gave you less to work with than you        │
│  │ before Kg3, │   gave them.                                      │
│  │ arrow on    │                                                   │
│  │ the move    │   WHAT THIS GAME LEFT YOU                         │
│  │             │   ●  You played Kg3. This is where the game       │
│  └─────────────┘      got away.                          (new)     │
│                    ●  You played b4. You found the best move       │
│  You played Kg3        when it mattered.                           │
│  here. It is where ●  Their rooks worked together and yours        │
│  the game turned.     did not.                                     │
│                                                                    │
│                    [ See the moment  › ]                           │
└───────────────────────────────────────────────────────────────────┘
```

Today the story's own headline for this game is "Found the best move when it
mattered", on a game the player lost. The deciding move, Kg3, is hidden
because the detector that would name it is not yet approved.

### Home page: a won game (game 77594c18, black, won on time)

```
   YOUR LAST GAME

   You were the steadier player in that one.
   They went wrong and you went straight at it.

   WHAT THIS GAME LEFT YOU
   ●  You played Bxa6. You took what was offered.
   ●  You played Bd6. There was a pin you could have played.
   ●  Your bishop on g7 had almost nowhere to go.

   [ See the moment  › ]
```

### Review page: the top of the start card (same lost game)

```
┌───────────────────────────────────────────────────────────────────┐
│  WHAT THIS GAME LEFT YOU                                           │
│                                                                    │
│  ✗  Kg3       This is where the game got away.          (new)  ›   │
│  ✓  b4        You found the best move when it mattered.        ›   │
│  ✓  Rxg7+     You answered a threat.                            ›   │
│                                                                    │
│  ALL GAME LONG                                                     │
│  ·  Your opponent held the middle of the board.                    │
│  ·  Their rooks worked together and yours did not.                 │
└───────────────────────────────────────────────────────────────────┘
   (then the cards already there: "What I've noticed",
    "Where the game turned", and Begin walkthrough)
```

Tapping a row opens the walkthrough at that move. The card there already
explains it with the pieces and squares, and that explanation is checked
against the board. The story says where to look. The move card says why.

## The rules that make it safe to show

These come from measuring the story on the last three games of the 60 most
active players, 168 games in all.

| What was measured | Games |
|---|---|
| Lost games | 79 |
| Lost games where the move that decided it is hidden | 41 |
| Lost games whose headline is a compliment | 15 |
| Lost games with nothing to show at all | 3 |
| Games with at least one long-stretch line | 161 |

1. **A lost game never leads with a compliment.** When the deciding mistake
   has an approved name, that name leads. When it does not, the line says
   only where it happened: "You played Kg3. This is where the game got away."
   That claim needs the engine alone, which already decides a move is bad.
   It makes no claim about why. This one rule repairs about half the lost
   games.
2. **Every line names the move.** A line like "Took what was offered" alone
   says nothing. Each moment line starts with the move that was played.
3. **One move per card for "where the game turned."** The board and the
   first story line must point at the same move. Today they are built by two
   different services. On the six games where both exist locally, they named
   the same move zero times. See open question 1.
4. **No numbers.** No move numbers, no counts. The move itself, such as Kg3,
   is how a line is located. The current card already does this.
5. **"Answered a threat" never leads.** It was the headline of 12 of the 168
   games, once on the second move of the game. It can appear lower down on
   the review page and not on home.

## In scope

- The story section at the top of the review page's start card, with rows
  that jump to the move.
- Up to three story lines inside the existing home card for the last game.
- Picking the coach's chosen review game for the home card when the player
  has one, and the last game otherwise.
- The five rules above, each locked by a test, including a test that no
  digit reaches the player except inside a move such as Kg3.
- Recomputing old stored stories on read. This already works.

## Out of scope

- A new home card. The existing one is extended.
- New detectors, or approving shadow detectors so more mistakes get a name.
  That is the real fix for the hidden lines and it is separate work.
- Replacing the older review summary tab, which runs on its own story
  service. See open question 3.
- Play with Coach games on home. The home card skips them today, and so
  will this.

## Success criteria

- On the same 168 games, no lost game leads with a compliment, and no game
  with a deciding move has an empty story.
- The board and the first line agree on every home card.
- Players tap a story row on the review page. A tap is recorded so this can
  be counted. If almost nobody taps, the rows are not earning their space.
- Three visits to home after three new games show three different cards.

## Open questions

1. **Which service owns "where the game turned"?** The home card uses the
   both-sides review, which can pick the opponent's move. The story uses only
   the player's own moves. My recommendation is that the story owns it on the
   board, because a player can train their own move and cannot train the
   opponent's. The both-sides headline stays as the title. The cost is that
   the line about the opponent's mistake moves into the story as its own
   "they went wrong here" line.
2. **The steadier-player contradiction.** On game 8f40005b the home card says
   "You were the steadier player. The game was still yours when your flag
   fell." The story's top line for the same game is a rook given away on
   Rxf3+. Both may be true if the opponent gave it back. I will check that
   game by hand before building, and the card must not say both without
   joining them.
3. **The review page now has two story sources.** The summary tab runs on the
   older coach review service. Do you want the new story to replace that tab's
   opening paragraph, or to sit only in the start card for now? I recommend
   the start card only for now, and replacing the tab later once the new one
   has proved itself.

## Before code starts

- Mohit signs off on the mockups and answers open question 3.
- The naming fix from earlier today is committed and deployed, since every
  line here depends on it.
- Game 8f40005b is checked by hand.
