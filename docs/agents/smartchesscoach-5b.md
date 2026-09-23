# smartchesscoach-5b — game-review board arrows

**Status: done, pushed, deployed. Not currently editing anything.**

Last updated 2026-09-23.

## What this was

The arrows on a game-review card were describing a different move from the
caption, drawn on a position the card never displays. Mohit found it: *"Qe7
was black's move, but the arrwo shoed on opoponent queen."*

The card renders `fen_after` — `board_before` plus the move that was
**played** — while the arrow builder computed on `board_before` plus the
**best** move. Those are the same position only when the player found the
best move. On an opponent card it was worse than misaligned: `best_move_uci`
there is the *opponent's* best alternative, a move the caption never names,
while the caption recommends *our* reply. "Qe7" was legal for both sides, so
two different moves wore the same three characters.

Shipped across v172–v175:

- the picture now comes from the move the card actually talks about
- the missed-win picture is **relocated**, not dropped — it ships on
  `best_move_arrows` + `best_move_arrows_fen` and the page draws it under
  "What if I played X?", which already shows that exact board
- the recommended reply leads with the **move itself**, so the picture starts
  on a piece the player can see instead of in mid-air
- a reply no longer has to give **check** to be drawn — a check is what makes
  a threat unanswerable, not what makes it worth showing

Measured over 500 games. User cards: all 514 pictures kept (238 on the card,
276 relocated), 0 anchored to an empty square, down from 276 of 514 false.
Opponent cards: 261 → 2,543 drawing a picture, 77% with two arrows, never
more than four; all 2,543 board-verified, 0 false claims.

## Files

| file | note |
|---|---|
| `backend/services/caption_pipeline.py` | the arrow builders and the choice of which picture a card gets. Heaviest edit. |
| `backend/services/game_decryption_v5_service.py` | two new card fields + `V5_COACHING_VERSION`. See rule 1. |
| `frontend/src/components/GameDecryptionV5.jsx` | draws the relocated picture, and only when the board's FEN matches the one it shipped with. **Missing from the board's shared-file registry — adding it here.** |
| `backend/tests/test_teach_arrow_matches_rendered_board.py` | new, mine alone, 22 tests. |

Branch `fix/opponent-card-arrow`, worktree `_cl_sprint`, merged to
`working-code`. My commits: `fff1802f`, `c4f6d984`, `8ea09678`, `0cda8d16`.
`9a584b69` is the merge, not a change of mine.

## If you touch my files

`caption_pipeline.py` — the invariant that cost the most to find: **an arrow
is only honest on the board the card renders.** The trap cage and the
punishment arrows compute on `board_before + played_move`, which *is*
`fen_after`; that is why they were right all along. Anything computed on a
different position must travel with the FEN it is true of, like
`best_move_arrows` does, or not be drawn.

`GameDecryptionV5.jsx` — the page compares the two FENs before drawing the
relocated picture. Don't remove that check; it is the only thing stopping
the original bug returning.

## Open, with Mohit — not blocking me

The deploy gate's check 8 fails on **every** deploy on its own stale fixture:
it pins UCI `f5e5` against a rotating pool position, and when that move is
rejected the fallback probes legal moves — but the session is `total_items:
1`, so the first probe completes it and nothing later can be accepted. 7 of 8
checks pass and the release genuinely is live while the script prints
"release is not live".

I offered the repair (derive the expected answer from the served FEN; request
a fresh session per candidate) and am waiting on his yes. Three sessions have
now lost time to this — it is rule 3 on the board.

## Not mine

`backend/tests/test_mistake_why_and_coherence.py` has 1 failure. Pre-existing;
confirmed identical on the base commit before any of my changes.
