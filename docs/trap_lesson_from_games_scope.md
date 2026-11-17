# Traps found in your own games: caption, lesson, home

Status: DRAFT for sign-off (2026-11-17). Path EXTEND chosen by Mohit ("go
ahead, do what you recommend"), and the trap rule set from a hand-graded
sample (section 0b). No code until Mohit signs the whole document.

Mohit, 2026-11-17, on 856f6111: "this game can be a good lesson of memory,
understanding and pattern, as the player walked into a mate, somebody tried to
set up a trap and one bad move set up the mate ... see what Maia does at that
level", then "the caption should tell that in the game and it should also be a
lesson so whoever reviews these games and other games can learn the full trap
directly from game review; also a player who falls in a trap should be called
on the home page".

## The example (verified 2026-11-17)

856f6111, lichess rapid, Mohit Black 1448 vs 1625:
1.e4 e5 2.Nf3 Nc6 3.d4 exd4 4.Ng5 h6 5.Nxf7 Kxf7 6.Bc4+ Ke8?? 7.Qh5+ Ke7
8.Qf7+ Kd6 9.Bf4+ Ne5 10.Qd5+ Ke7 11.Qxe5#.

Maia-2 rapid (1448 vs 1625) and Stockfish depth 20:
- 4.Ng5 is a prepared line: Maia-1625 plays 4.Nxd4 92%, Ng5 not in its top six.
- 5.Nxf7 is the bait: 88% at 1625 after 4...h6, Stockfish about -4.5 for White.
- 6...Ke8 is the natural move that loses: 61% at 1448 (76% at 1100, 28% at
  1900), mate in six. 6...d5 keeps the piece (+4.4): 17% at 1448.
- After Ke8, a 1625 player finishes the mate about 89% of the time (Qh5+ 99.8%).
- 4...h6 left g6 with no pawn guarding it; the mate runs through Qxg6+.

## 0. Existing surfaces audit

| Surface | What it already does (render level) | Gap for this request |
|---|---|---|
| Trap library (`data/traps.json` 28, `trap_roles_verified.json` 55, `trap_school.json` 24) + `services/trap_recognition.detect_trap_setup` | Matches the played moves against authored trap lines, move order exact. | Exact lines only. 856f6111 is in none of them. The 2026-11-09 loss study: 0 of 1,000 losses matched ("trap matching must be by pattern"). |
| Game review card (`caption_pipeline` trap state, `game_trap_fires`, V5 `trap_line_full`; `GameDecryptionV5.jsx:2757-2826`) | When a library trap fires, the card can play a "Trap line" with an authored explanation per move, and the caption gets trap-context facts. | Fires only for library traps. 856f6111's cards (v249) explain each move alone: 5.Nxf7 "allows a free piece: play Kxf7", 6...Ke8 "allows a forced mate ... d5 was better". Nothing says it was a trap; `trap_fires` is empty. |
| Trap school `/learn/traps`, `/learn/traps/:slug` (`services/trap_school.py`, `pages/TrapSchool.jsx`) | The lesson format Mohit describes: the line move by move with what each move does, the tempting move, real games replayed. "Traps that caught you / were waiting / could set / sprang" from the player file. How common, in words. | 24 library traps only. A trap found in a player's own game has no page. |
| Player file traps (`player_coach_file.trap_record`, `TrapCard` on CoachLearn and Academy) | A card per trap the player met, "Learn the trap" link to the school. From stored `game_analyses.trap_fires` (36 of 78 players see one). | Same library limit. |
| Home: `LastGameCard` (`/coach/last-game-card`, both themes of Home) | "Who was the better player" in the last game, plus the game's story in up to three lines located by the move. Coach-pages Home behind `user.coach_pages`. | Never says "you fell for a trap". |
| Maia on the card (`human_policy_evidence`, `services/human_policy_runtime.py`) | The plumbing for Maia evidence on each card. | Off: 0 analyses carry it (`human_policy_reason: not_requested`). Maia-2 runs on prod (about 400 ms a move, memory 11-02). |

Overlap: the lesson page, the "trap line" player on the card, the trap card in
the player file and the home story line all exist. What does not exist is
finding a trap that is not in the library.

Genuine new piece: a trap found by pattern in the player's own game, the way
856f6111 shows it: the opponent gives something up (bait), the player's
natural move (Maia, at the player's rating) loses, and the opponent's best
answer wins. That finding then feeds the existing surfaces.

**Recommended path: EXTEND.** One new finder; its result is written where a
library trap's would be, so the card, the trap school page, the player file
card and the home story line show it without new screens. A game-found trap
gets its own trap-school page built from the game (line, the tempting move,
the move that holds, how often players at that level fall for it).

## 0b. How often, and what counts as a trap (measured 2026-11-17)

Mohit's newest 300 analysed games: 167 losses, 505 of his moves losing 200 cp
or more. Maia-2 (blitz or rapid model to match the game, his rating and the
opponent's) on each:
- 123 were natural moves (Maia 30% or more at his rating);
- 77 of those came within two moves of an opponent move that cost the
  opponent 100 cp or more (the "bait"), in 59 of the 167 losses.

That crude rule over-counts. 30 of the 77, drawn at random (seed 1117), graded
by reading the engine lines (not yet each set up on a board):
- 8 clear traps: 856f6111 Ke8 (knight given on f7, then the check);
  c209379f Qxa2 (a2 left loose, Ra1 traps the queen); bb2f61a5 Rxc7 (taking the
  checking knight loses to Qxc7 and Qxd7); 35264481 fxe6 (the natural
  recapture lets the queen in: Qxe6+, Qxc6+, Qxa8+); 701cecc0 fxg4 (taking the
  knight offered on g4 loses to Bxg4, Bxh3); 3bdad5fa dxe5 (taking the
  offered pawn lets in Qh4, Qxh2+); c96adfdb O-O (h3, then g4 traps the
  bishop); 66090078 Nc3 (blocking Qa5+ walks into a pin, Ne4).
- 7 unclear: sacrificial attacks, rows inflated by mate scores.
- 15 not traps: mostly the opponent blundered and the win was missed (a
  different lesson: knowing how to cash in).

What separates the clear traps on the board: the natural move TAKES what the
opponent just offered (a piece or pawn their last move put there, or left
without its guard), or ANSWERS the check that follows their sacrifice, and
the engine line then takes back more than was won, or mates. As a rule on the
same 30: keeps 5 of the 8 clear traps (Ke8, Qxa2, Rxc7, fxe6, fxg4), lets in
0 of the 15. It misses the trapped-bishop, the check-into-a-pin and the
offered-pawn-then-attack shapes (out of scope, section 4).

## 1. What it is

When a player loses to a trap, ChessGuru says so in the game review and
teaches the trap, from the game itself. A trap here means: the opponent
offers something (a piece, a pawn, or a sacrifice that ends in a check), the
move most players at that level would play takes the offer, and that move
loses more than it won. The review card on the losing move says it was a
trap and what the right move was; the card on the opponent's offer says it
was bait; a "trap line" plays the whole trap on the board; a "Learn this
trap" page teaches it move by move, built from the game; and Home tells the
player about it after the game. Anyone who reviews the game (the player, a
coach, an academy) sees the same thing. It uses the screens that already
show library traps; nothing new is added to the navigation.

## 2. What the user sees

Game review, 856f6111, the card on 5.Nxf7 (the opponent's offer):

    Nxf7 is bait. The knight is yours to take, and taking it is right.
    But your king is now out in the open, so the next check is the test.

The card on 6...Ke8 (the move that fell for it):

    Ke8 falls into a trap. Your opponent gave up the knight on f7 to pull
    your king out, betting you would step back to e8. Most players at your
    level do. After Ke8, Qh5+ leads to mate. d5 blocks the check and keeps
    the extra knight.

    [ Play the trap ]   [ Learn this trap ]

"Play the trap" (the existing trap-line player on the card), one line a move:

    5. Nxf7    Gives up the knight to pull your king out.
    5... Kxf7  Takes it. Right so far.
    6. Bc4+    Checks the king.
    6... Ke8   Steps back. This is the mistake.
    7. Qh5+    The queen checks from h5.
    ...        (each move to 11. Qxe5#)
    Instead:   6... d5 blocks the check. You keep the knight.

"Learn this trap" (a trap-school page for this trap, built from the game):

    THE KNIGHT ON F7
    Seen in your game against a stronger player, move 5.
    The offer      5. Nxf7  (what it gives, what it wants)
    The test       6. Bc4+  (most players at your level answer Ke8)
    The punishment 7. Qh5+ ... mate
    What holds     6... d5
    [ the board, move by move, as on any trap-school page ]

Home, the last-game card, one story line and one action:

    You fell into a trap on move 6: your opponent gave up a knight to pull
    your king out.                                      [ Learn the trap ]

The player file and the trap school's "Traps that caught you" list it next to
library traps.

Words follow the caption rules: plain English, no engine numbers. How common
comes as a sentence ("most players at your level", "about half", "some"),
from Maia, never a figure.

## 3. In scope (V1)

- A trap finder over a player's own games, per the rule in 0b: Maia at the
  player's rating 30% or more for the losing move; the move takes what one of
  the opponent's last two moves offered, or answers the check after their
  sacrifice; the engine line after it takes back more than was won (exchange
  ledger) or mates; the better move does not lose it.
- Runs in the analysis worker for new games, and a backfill over stored games
  (after deploy; dry-run count first, see 7).
- The finding is stored with the library trap fires (`trap_fires`, marked as
  found in the game), with the offer ply, the losing ply, the line, the move
  that holds and Maia's share in words.
- Review captions: the losing move's card and the offer's card get the trap
  wording above, through the central caption layer (one source of truth).
- The card's existing trap-line player shows the trap with one plain line per
  move, written from board facts (gives up, takes, checks, steps back, mate,
  wins), and the move that holds.
- A trap-school page per game-found trap at /learn/traps/<id>, the same page
  layout as library traps.
- Home's last-game card: the story line and "Learn the trap" when the last
  game had one.
- The player file and "Traps that caught you" include game-found traps.

## 4. Explicitly out of scope (V1)

- The trap shapes the rule misses: a quiet move that traps a piece (h3, g4
  against a bishop), a check that drives a piece into a pin (Qa5+ Nc3 Ne4),
  an offered pawn followed by an attack rather than material. Each needs its
  own rule and its own graded sample.
- Traps the player SET and the opponent fell for ("sprang"). Same finder,
  opposite side; after V1 is graded.
- Missed wins (the opponent blundered and the player did not cash in): 15 of
  the 30 graded were this. A separate lesson, worth its own scope.
- Names for game-found traps. A library trap keeps its name; a game-found
  one is named by what it does ("the knight on f7"), not a book name.
- Adding game-found traps to the library or to other players' trap school.
- Maia figures on any page.
- The Lichess explorer.

## 5. Success criteria

- Precision: 30 game-found traps from the backfill, across players, graded on
  the board: at least 27 are real traps (offer, natural move that takes it,
  punishment). Below that, it does not ship to Home.
- The trap is learned: of players who see a trap on Home or the review card,
  at least 25% open "Learn this trap" or play the trap line, within two weeks.
- The trap does not repeat: when the same offer pattern comes up again for a
  player who opened the lesson, they take the bait less often than before.
  Measured once enough repeats exist; reported, not a gate.

## 6. Open questions

- Question: is 30% the right Maia bar for "natural"? Why unresolved: set from
  one player's 30 moments. Unblocking step: the dry-run backfill's
  distribution across players, then a second graded sample.
- Question: how far back can the offer be? Why unresolved: two of the
  opponent's moves covers all 8 clear traps in the sample. Unblocking step:
  the same dry run.
- Question: how often will a player see one? Why unresolved: 77 crude
  moments shrink under the rule; the real per-player rate is not measured.
  Unblocking step: dry-run count per player.
- Question: should Home also mention a trap from an older game, not just the
  last one? Why unresolved: product choice. Unblocking step: Mohit.

## 7. Pre-code requirements

- Mohit signs this document.
- The five sample traps the rule keeps are each set up on a board and read
  again (they were graded from engine lines).
- A dry run of the finder over stored games (no writes) gives the per-player
  count and fire distribution, and 30 of its fires are graded before any
  backfill writes.
- The trap-school page route for game-found traps is checked against the
  existing /learn/traps/:slug routing.
