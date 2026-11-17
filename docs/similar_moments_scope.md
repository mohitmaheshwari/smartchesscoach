# Similar moments: how a stronger player handled this kind of moment

Status: DRAFT, awaiting Mohit's sign-off. 2026-11-17.

Mohit, 2026-11-17: "pick up player issues, mistakes ... pull up those games
too to show how a better player did here ... how coach expects them to think
here", then: "both [our players' games and Lichess], whichever sounds closer;
we need to keep tagging analysed games as soon as we have them so that each
game knows its similar game".

## 0. Existing surfaces audit

| What exists | Where | What it gives today | Decision |
|---|---|---|---|
| Per-move tags at analysis time | `move_observation_deriver.derive_observations_for_game`, run on completion (`analysis_completion_evidence.py:134`) | For the move PLAYED: landing-square outcome (`destination_safety_exact`: handled / miss, piece, destination, reply), tactic tags, phase, time | **EXTEND**: add the new tag in the same pass |
| "Handled" moments | `move_observations.piece_safety_decision.outcome` (98,568 handled, 11,046 miss, 79 players) | Only that the played move landed safely. It does NOT say a dangerous landing move was available or tempting, so it cannot find "the same kind of moment" | Not enough on its own |
| Landing check and three looks | `services/landing_check.py` (2026-11-17) | Takers of a square, which look finds each, whether a taker wins | **REUSE** for the signature and for the coach's thinking block |
| Lichess puzzles | `lichess_puzzles`, 4,423,645 rows, CC0 | Real game positions where someone erred; the solver punishes | **REUSE** for "from the other side" |
| Lichess opening explorer and masters | token in the server `.env` (LICHESS_API_TOKEN) | What stronger players play in an exact opening position, and how it scores | **REUSE** for opening mistakes |
| Exact-position matching | loss study 2026-11-09 | 71% of losing positions never occur at 1100-1800, so exact matching only works in the opening | Middlegame needs kind-of-moment matching |
| Public Lichess games index | `/root/research/explorer_count.py` streamed the CC0 dump (move sequences only) | No positions, no tags | **BUILD** a tagged pool from the dump |

Decision: EXTEND the analysis-time tagging and the review card; BUILD the
moment index and the Lichess game pool.

## 1. What it is

Every analysed game is tagged, move by move, with the kind of moment each
position was: for now, "a piece could land on a square where it can be won,
found by this kind of look (close by, knight jump, long line)". When a player
makes a mistake, the coach finds a stronger player's real game where the same
kind of moment came up and they played safely, shows it next to the player's
own position, and then shows how the coach wants them to think there. It adds
a Lichess puzzle from the other side: someone made that mistake, and the
player is the one who punishes it.

## 2. What the player sees

On a landing-square mistake in game review, and in the drill:

```
YOU, move 22                        A STRONGER PLAYER, same kind of moment
Be7: the queen on c7 took it.       [board] Their bishop could go to d6,
                                    where the queen on b8 reaches it.
                                    They kept it on c5.

HOW I WANT YOU TO THINK HERE
Before the bishop lands, look from that square:
close by: nothing · knight jumps: nothing · long lines: the queen. Stop.

FROM THE OTHER SIDE
[a Lichess puzzle] Someone left a piece where a queen could take it.
You are the queen. Find it.                     [ Solve ]
```

On an opening mistake: "At your level and a little above, players here
mostly play Nf6, and it scores better than Bg4." (explorer, exact position)

No names, dates or ratings of the other player beyond "a stronger player".
When nothing close enough exists, the block is not shown.

## 3. In scope (V1)

- A moment signature written at analysis time for every move of every newly
  analysed game: for each piece that could land where it can be won, the piece,
  the kind of taker, the phase, and whether the player played such a move.
- Backfill of the signature over already analysed games.
- A matching rule: same signature, a player rated at least 150 above, the
  dangerous move available, the move played safe and not a mistake (cp loss
  below 60). Closest first; both pools searched.
- Pools: (a) our players' public platform games (Lichess, Chess.com), never
  academy children, never games against our own coach; (b) public Lichess
  games (CC0 dump), tagged the same way. Closest example wins, from either pool.
- The card on game review and the drill, with the coach's thinking block
  (three looks, from landing_check.py) and one Lichess puzzle from the other side.
- Openings: the explorer line for exact positions.

## 4. Explicitly out of scope (V1)

- Kinds of moment other than landing squares (forks, king safety, endgames).
  The signature is built to take them later.
- Claims about what the other player thought. The thinking block is the
  coach's method, said as such.
- Showing the other game in full or linking to it.

## 5. Success criteria

- Coverage: share of landing-square mistakes that get a match. Measured
  before building (section 6).
- Behaviour: landing-square slips in the player's real games fall faster for
  players who saw matched examples than for those who did not (the weekly
  plan verdict already measures slips).

## 6. Open questions

- **How often is there a match?** Measured 2026-11-17 (/root/research/
  similar_probe.py, read-only, throwaway container): Mohit's 6 landing misses
  in his newest 30 games against 156,560 positions from players rated 1475+.
  Every one hit the cap of 40 matches, from 7 to 11 different players. BUT
  most matches are not the same kind of moment: "a 1642 player could have
  played Bh6 on move 2" is true and nobody is tempted by it. The good ones
  look like "a 1890 player could have taken on e5 with the knight, like your
  Nxe5, and played Qb7". So matching MUST include temptation (below), whether
  the move was a capture, and whether it gave check. Re-measure coverage after
  the temptation gate; the raw count above is not coverage.
- **How tempting must the dangerous move be?** Maia probability at the
  other player's rating, threshold locked from the distribution, not guessed.

Decided 2026-11-17 (Mohit): no consent rule. The games are public on Lichess
and Chess.com ("these are open games and anybody can see it"). Kept out
regardless: academy children's games (they came in under a parent's consent
for that child's own coaching; using them for others is a different purpose
under DPDP) and games played against our own coach (not public).
- **How big a Lichess pool?** Tagging needs no engine for the landing fact, but
  "played safe and well" needs a cp loss, so pool games need Stockfish.

## 7. Pre-code requirements

- Mohit signs off this document and the consent rule.
- The coverage measurement is in section 6.
- The "recent games by analyzed_at" problem is fixed first if the backfill
  re-analyses anything (it must not), see 2026-11-17 notes.
