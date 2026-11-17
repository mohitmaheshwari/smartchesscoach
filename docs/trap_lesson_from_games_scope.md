# Traps found in your own games: caption, lesson, home

Status: DRAFT for sign-off (2026-11-17). Path EXTEND chosen by Mohit ("go
ahead, do what you recommend"); the trap rule set from a hand-graded sample
(section 0b); everything first marked out of scope moved in (Mohit: "nothing
should be left out"), built in stages A-E. No code until Mohit signs.

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
offered-pawn-then-attack shapes; those get their own rules (Stage B).

## 1. What it is

ChessGuru finds the traps in a player's games, says so in the game review,
and teaches them from the game itself. Four kinds of moment, all shown the
same way:

1. **You fell into a trap.** The opponent offers something, risking it on
   purpose, and the move most players at your level would play loses to it.
   Four shapes: you take what they offered and lose more; you answer the
   check after their sacrifice and walk into mate or loss; a quiet move of
   theirs threatens to shut in one of your pieces and the natural move lets
   it happen; their check makes the natural block a pinned piece that falls.
   Plus the slower one: you take an offered pawn and their attack follows.
2. **Your trap worked, or almost did.** The same, with the sides swapped: you
   offered, they took it and lost. Or they did not take it, and the lesson is
   why the trap was a risk.
3. **They slipped and you did not cash in.** The opponent gave something away
   by mistake, not as a trap, and the natural reply missed it. The lesson is
   how to take it.
4. **Traps that happen to players like you.** Game-found traps, from games
   whose players allow it, go into the trap school for everyone at that
   level, each named by what it does, or by its book name when it matches one.

The review card on the move says what kind of moment it was and what the
right move was; the card on the opponent's offer says it was bait; "Play the
trap" plays the whole thing on the board; "Learn this trap" opens a lesson
page built from the game; Home tells the player after the game, and keeps
reminding them of a trap they have not opened yet. Anyone who reviews the
game sees the same thing. It uses the screens that already show library
traps; nothing new is added to the navigation.

## 2. What the user sees

All words follow the caption rules: plain English, no engine numbers, "your"
and "their" by whose move it is. How common comes as a sentence ("most
players at your level", "about half", "some"), from Maia.

**Fell for it, took the offer** (856f6111). Card on 5.Nxf7:

    Nxf7 is bait. The knight is yours to take, and taking it is right.
    But your king is now out in the open, so the next check is the test.

Card on 6...Ke8:

    Ke8 falls into a trap. Your opponent gave up the knight on f7 to pull
    your king out, betting you would step back to e8. Most players at your
    level do. After Ke8, Qh5+ leads to mate. d5 blocks the check and keeps
    the extra knight.

    [ Play the trap ]   [ Learn this trap ]

"Play the trap", one line a move:

    5. Nxf7    Gives up the knight to pull your king out.
    5... Kxf7  Takes it. Right so far.
    6. Bc4+    Checks the king.
    6... Ke8   Steps back. This is the mistake.
    7. Qh5+    The queen checks from h5.
    ...        (each move to 11. Qxe5#)
    Instead:   6... d5 blocks the check. You keep the knight.

**A piece shut in** (c96adfdb, 10...O-O after h3):

    O-O falls into a trap. h3 looked slow, but it gets g4 ready to shut in
    your bishop on f5. Most players at your level castle here. After O-O,
    g4 leaves the bishop no square. e5 makes room first.

**A check into a pin** (66090078, 7.Nc3 after Qa5+):

    Nc3 falls into a trap. Qa5+ is a check that wants you to block with the
    knight. Many players at your level do. Then Ne4 hits the knight, and it
    cannot move because it shields your king. c3 blocks with a pawn.

**An offered pawn, then an attack** (3bdad5fa, dxe5):

    dxe5 takes the pawn they offered. Taking it opens the way for their queen:
    Qh4 comes in and h2 falls with check. h3 keeps the queen out first.

**Your trap worked** (any game where the opponent took your offer):

    Your trap worked. You gave up the knight on f7, and they stepped back to
    e8, as most players at their level do. Qh5+ then mates.

**They did not fall for it**:

    They did not take the bait. Nxf7 was a risk: after Kxf7 and d5 they keep
    the extra knight. Next time, play Nxd4 here.

**They slipped, you did not cash in** (a4615ca4, 27.exd6 after Qa3):

    Qa3 was a slip by your opponent: it leaves their bishop on c7 with no
    guard. exd6 misses it. Qxc7 takes the bishop.

**Learn this trap** (a trap-school page built from the game, same layout as a
library trap):

    THE KNIGHT ON F7
    Seen in your game, move 5.
    The offer      5. Nxf7  (what it gives, what it wants)
    The test       6. Bc4+  (most players at your level answer Ke8)
    The punishment 7. Qh5+ ... mate
    What holds     6... d5
    [ the board, move by move ]

**Home**, the last-game card, one line and one action:

    You fell into a trap on move 6: your opponent gave up a knight to pull
    your king out.                                      [ Learn the trap ]

or "Your trap worked on move 9", or "Your opponent slipped on move 27".
When the last game had none, Home shows the newest trap from a recent game
that the player has not opened yet:

    Still to learn: the trap from Tuesday's game, a knight given on f7.
                                                        [ Learn the trap ]

**Trap school**: "Traps that caught you" and "Traps you set" list game-found
traps next to library traps; "Traps that happen at your level" adds
game-found traps from other players' games that allow it, named by what
they do ("the knight on f7") or by the book name when the line matches one.

## 3. In scope (V1, built in stages; each stage ships to Home only after its gate in 5)

Stage A. Took the offer (the 0b rule):
- Finder: Maia at the player's rating 30% or more for the losing move; the
  move takes what one of the opponent's last two moves offered, or answers
  the check after their sacrifice; the engine line after it takes back more
  than was won (exchange ledger) or mates; the better move does not lose it.
- Captions on the losing move and the offer; "Play the trap" with one line a
  move from board facts; the "Learn this trap" page; Home; player file and
  "Traps that caught you".

Stage B. The three shapes the A rule misses, each with its own rule:
- A piece shut in: the opponent's quiet move costs them (bait), and after the
  natural move the engine line traps one of the player's pieces (no safe
  square; the existing TRAPPED reading).
- A check into a pin: the opponent's check costs them, the natural reply
  blocks with a piece, and the engine line wins that piece through the pin.
- An offered pawn, then an attack: the natural move takes an offered pawn,
  and the engine line answers with checks or threats on the king within four
  moves and the position is lost by more than the pawn.

Stage C. Traps the player set:
- The same finders with the sides swapped (Maia at the opponent's rating for
  their move): "Your trap worked". When the opponent found the move that
  holds: "They did not take the bait", with why the trap was a risk.

Stage D. Missed wins:
- The opponent's move costs them a clear amount without being bait (no trap
  shape: nothing offered on purpose), and the player's natural reply misses
  it: "They slipped, you did not cash in", explained by the why button's
  existing missed-side reasoning (opportunity line, ledger gain, mate).

Stage E. Sharing and names:
- Game-found traps from games whose players allow it go into "Traps that
  happen at your level" in the trap school. Consent follows the similar-
  moments rule (0e452784): public games only, no academy children, no coach
  games. No player names.
- Matching to the library by pattern, not move order: the same offer, the same
  natural reply and the same punishment, in any move order. A match takes the
  library trap's name and page; otherwise the trap is named by what it does.
- The same trap seen in several games is one trap with several games, as
  library traps have.

For every stage:
- Runs in the analysis worker for new games, and a backfill over stored games
  (after deploy; a dry run first, see 7).
- Stored with the library trap fires (`trap_fires`, marked as found in the
  game, with its kind and stage).
- Words through the central caption layer (one source of truth).
- Home: the last game's moment first; if it had none, the newest unopened
  trap from a recent game.

## 4. Explicitly out of scope (V1)

- Maia figures on a page ("61%"). Kept as words because of the standing rule
  that published text carries no numbers (Mohit, feedback "Published text:
  simple English, no numbers"). Mohit can lift it; then the card can say "6
  of 10 players at your level play Ke8 here".
- Showing another player's game without the consent rule in Stage E.

## 5. Success criteria

- Precision gate, per stage: 30 of its finds from the dry run, across
  players, graded on a board: at least 27 real. Below that, the stage does
  not ship to Home (review cards only, until fixed).
- Learned: of players who see a trap on Home or a review card, at least 25%
  open "Learn this trap" or play the trap line within two weeks.
- Not repeated: when the same pattern comes up again for a player who opened
  the lesson, they take the bait less often than before. Reported once enough
  repeats exist.
- Stage C and D: of players shown "your trap worked" / "they slipped", the
  share who open the lesson, compared with Stage A.

## 6. Open questions

- Question: is 30% the right Maia bar for "natural"? Why unresolved: set from
  one player's 30 moments. Unblocking step: the dry run's distribution across
  players, then a graded sample.
- Question: how far back can the offer be? Why unresolved: two of the
  opponent's moves covered all 8 clear traps. Unblocking step: the dry run.
- Question: how much must a bait cost the setter, and where does a slip end
  and a trap begin (Stage D against A)? Why unresolved: the crude 100 cp bar
  let in 15 slips in 30. Unblocking step: grade the dry run's split.
- Question: how often will a player see each kind? Why unresolved: not
  measured per player. Unblocking step: dry-run counts per player and stage.
- Question: how recent is "a recent game" for Home's unopened trap? Why
  unresolved: product choice plus play frequency. Unblocking step: the
  start-to-start gap per band (memory 11-12) and Mohit.
- Question: Maia figures on the card? Why unresolved: standing rule. Unblocking
  step: Mohit.

## 7. Pre-code requirements

- Mohit signs this document.
- The five sample traps the A rule keeps, and the three B examples, are each
  set up on a board and read again (they were graded from engine lines).
- A dry run of each stage's finder over stored games (no writes) gives the
  per-player count and distribution, and 30 of its finds are graded, before
  any backfill writes for that stage.
- The trap-school route for game-found traps is checked against
  /learn/traps/:slug, and the consent filter is checked against the
  similar-moments implementation before Stage E writes anything.
