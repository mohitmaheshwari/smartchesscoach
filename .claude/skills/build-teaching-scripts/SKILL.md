# Build teaching scripts from played games

Turn games we have already analysed into coach-style teaching scripts: a
position where exactly one move wins, what players at that rating actually
play instead, and the defender fighting back with an answer to each try.

Built 2026-11-26 after Mohit showed a YouTube short teaching two endgame
ideas and said: *"pick up content and actually teach user in his own style…
user should feel like guided, not like Aimchess and Chessiro where you can do
whatever you want."* Then: *"build a skill so me as a human coach can just use
your skill and we can keep pushing more games in this as soon as we have
new."*

**The rule this skill exists to enforce: the chess is computed, the words are
written from what was computed.** Nothing in a script may be a model's opinion
about a chess position. That is what makes this content type safe when our
caption text was not.

## When to invoke

- New games have landed and should be converted ("push more games in")
- Mohit types `/build-teaching-scripts`
- After the builder improves and old scripts should be redone (`--rebuild`)
- Before a review session, to refill the draft queue

Do NOT invoke for:
- Writing or editing a single script by hand — edit the row
- Caption work on the game-review page — that is a different pipeline
- Anything positional. This skill only produces scripts whose answer is
  provable (see Limits)

## What it produces

One row per converted game in the `teaching_scripts` collection:

| field | meaning |
|---|---|
| `game_id`, `user_id`, `ply` | where the position came from |
| `player_missed_it` | true if the player themselves got it wrong — the best lessons |
| `played_instead` | what they actually played |
| `user_rating_at_time` | the rating the human column was computed for |
| `tree` | the whole lesson: only move, alternatives, defender tries, main line, the bare race |
| `tree.proof` | `exhaustive` (solved to the end, no engine) or `search` |
| `status` | `draft` — **nothing is shown to a user until a coach promotes it** |
| `builder_version` | so a better builder can re-do old rows |

Inside `tree`:
- `only_move` — the unique winning move, with its verdict
- `alternatives` — ordered by *how likely this rating is to play them*, not by
  engine rank, so the script answers the likely mistake first
- `defender_tries` — their replies worst-for-us first, each with our answer,
  and `forced: true` when only one of our replies still wins
- `bare_race` — the position stripped to kings and the passed pawn, so the
  script can *prove* "count first, their king is in time" instead of saying it
- `main_line` — the win played out

## Steps to run this skill

1. **Check nothing else is converting.** Two runs at once will duplicate work
   and fight over the engine.

2. **Dry run first, always.**
   ```bash
   python3 backend/scripts/build_teaching_scripts.py --limit 5 --dry-run --scan 150
   ```
   Read the lines it prints. Each one names the game, the piece count, whether
   the proof was exhaustive, the only move, and whether the player missed it.
   If the only moves look wrong or everything is being skipped, stop and find
   out why before writing anything.

3. **Run for real.**
   ```bash
   python3 backend/scripts/build_teaching_scripts.py --limit 25 --scan 800
   ```
   Add `--maia` to include what each rating actually plays. It is slower and
   needs `maia2_models/rapid_model.pt`, and it only produces a human column
   for ratings inside the band `human_policy_runtime.py` allows (600-1500 by
   default). Without it, scripts still build — they just cannot open on
   "nearly one in five players your rating plays this".

4. **Report the yield**, honestly: how many games were looked at, how many
   produced a script, how many had no teachable position. A low yield is
   information, not a failure — most games do not contain an only-move
   position inside the piece limit.

5. **Hand the drafts to the coach.** Every row lands as `status: "draft"`.
   This skill never promotes anything. A human reads the script and decides.

6. **Never claim a script is live because the script ran.** Check the
   collection count before and after, and read one row end to end.

## Flags

| flag | what it does |
|---|---|
| `--limit N` | how many scripts to build this run (default 20) |
| `--scan N` | how many analysed games to look through (default 600) |
| `--user ID` | restrict to one player |
| `--max-men N` | only positions with at most N pieces (default 7) |
| `--depth N` | search depth (default 24) |
| `--threads N` | engine threads (default 4) |
| `--maia` | add the human move distribution for the player's rating |
| `--rebuild` | redo games converted by an older builder version |
| `--dry-run` | write nothing |

## Where to run it, and how the writing works

**Build here, load there.** This workstation has the cores (12, native
Stockfish at `C:\Users\MIISCO\chess-tools\engine\stockfish\`) but its
database login is **read-only** — `chessguru_local_ro` cannot write to
`chess_coach`, by design. The production box can write but must not run an
engine; it serves the site.

So a real run is two steps:

```bash
# 1. build on the workstation, into a file
MONGO_URL=<the local RO url, host.docker.internal -> localhost> \
  python backend/scripts/build_teaching_scripts.py \
    --limit 25 --scan 900 --maia --out /tmp/scripts.jsonl

# 2. copy it over and load it where the login can write
scp /tmp/scripts.jsonl root@72.60.204.176:/root/
ssh root@72.60.204.176 'cd /root/repos/smartchesscoach && \
  python3 backend/scripts/build_teaching_scripts.py --load /root/scripts.jsonl'
```

`--dry-run` needs neither; use it for every first look.

**There is a ready-made overnight runner** at
`C:\Users\MIISCO\teaching_out\run_overnight.sh`. It sets `MONGO_URL` from the
container, appends to `batch.jsonl` and `batch.log`, and prints the two load
commands when it finishes. Interrupting it costs nothing: the builder skips
games that already have a script, so starting it again carries on.

Budget roughly **20 seconds per game** at `--depth 20` with `--maia`, and
expect about **one script per 30 games** — measured 2026-11-26. An overnight
run of eight hours covers roughly 1,400 games and yields around 45 scripts.

If you forget `--out` and the login cannot write, the run now says
`WRITE REFUSED` once and **keeps going** rather than dying — but it stores
nothing, so you have burned the engine time. Before the fix, one refused
write killed the whole run with a traceback and lost everything built so
far. Use `--out` for any run you care about.

The `chess-coach-backend` container also works and has `MONGO_URL` already,
but it has no source mount: `docker cp` both files in first or they will not
be there. It is slower than the host.

Never run the build on the production server. It is a research job.

**Redirect output to a file and poll the file.** Piping this to `head` or
`tail` buffers everything until it finishes, which looks exactly like a hang.
This cost three wasted runs on the day the skill was written.

## Limits — read before widening the scope

The skill only converts positions whose answer can be **proved**:

- **at most 5 men, kings and pawns only** → solved exhaustively. No engine
  opinion is involved at all. `tree.proof == "exhaustive"`.
- **up to `--max-men` pieces** → the engine must put exactly one move above
  +500cp *and* the second best below +250cp. The gap matters: a position where
  the choice is between +600 and +580 is not an only-move lesson and is
  rejected.

It does **not** handle positional ideas — bad bishop, pawn breaks, piece
activity. Those have no provable answer, and they are precisely where our
coaching text has been unreliable. Do not extend this skill to cover them
without a separate decision.

## What NOT to do

- **Do not let a model choose a move, a branch or a verdict.** It renders the
  tree into English and nothing else. If a sentence in a script cannot be
  traced to a field in `tree`, it does not ship.
- **Do not promote drafts automatically.** A coach reads them first.
- **Do not lower `WIN_CP` / raise `NOT_WIN_CP`** to increase yield. A wider
  gate buys volume by letting in positions where "the only move" is not
  actually the only move.
- **Do not quote Maia percentages to a student.** Use them to order the
  script and to judge whether a position is worth teaching. Our own notes
  record Maia being unreliable at fine ordering.
- **Do not switch it back to reading `game_analyses`.** It reads `games.pgn`
  and replays locally, on purpose. Measured 2026-11-26: pulling the analysis
  documents cost **2.9 seconds per game** over the tunnel (~300 KB of move
  evaluations each), and only **3 games in 40** contained any position small
  enough to be worth looking at — so ~97% of the run was spent dragging move
  arrays across the wire to throw them away. A PGN is about 2 KB, replays
  locally, and already says what the player played. The analysis document is
  not needed: the tree is built from the position by the engine.

## Related

- `backend/services/teaching_script_builder.py` — the tree builder and the
  exhaustive solver
- `backend/scripts/build_teaching_scripts.py` — the runner this skill drives
- `docs/guided_concept_curriculum_scope.md` — the curriculum these scripts
  feed, and its open questions
- `docs/human_coach_gap_map.md` — why this content type is the differentiator
