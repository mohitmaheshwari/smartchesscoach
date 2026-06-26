# PWC Coach Conductor — Architecture & Build Plan

_Status: BUILD IN PROGRESS. Mohit, 2026-06-26: "build this all together, with proper
testing, 100 user scenarios, until 100% confident on the output for my vision."_
_Parent: [coaching_presence_scope.md](coaching_presence_scope.md). This is the engine that delivers it._

---

## The vision (Mohit's words, assembled across the design conversation)

**One coach. One model of you. Live at the board.** The same intelligence behind Progress /
Lab / Review, but speaking while you play. It knows you cold (motif profile, identity,
patterns, history) and at each moment says the **single** thing that serves your learning —
naming your real patterns when they recur, fluent across tactics / endgames / openings /
traps / move-quality — and it does it as a **relationship**, not a feature menu.

## The laws (non-negotiable; every component obeys these)

1. **STATE, never ASK.** No quizzes. "Can you see it?" / "What's threatened?" / "Guess my
   move" are banned. If the player sees it, their move proves it → the coach says "you saw
   it." If not, the coach tells them *after* the move. Your move already answers the question.
2. **Memory is a THREAD, not a ledger.** Never "you blundered 28 times." The model of you is
   an invisible *lens* (what the coach watches for) and a *thread* (what it says, when). It
   surfaces at the live, engine-confirmed moment the pattern recurs.
3. **Engine-true or silent.** Every claim — including the pattern callback — is verified on
   the board / by the engine. A coach confidently wrong about your weakness is worse than
   silent. (Reuses the per-FEN verifier already inside the caption door.)
4. **Restraint.** Pull a thread once, with weight — not on every instance. Nagging is just a
   ledger with a voice.
5. **Catch the wins too.** The day you spot the skewer, the coach notices: "that — you saw
   it." Progress and warmth live here, not in stickers.
6. **One voice chooses.** Not N independent reflexes firing on triggers. A single per-move
   decision picks the one most-useful thing, driven by the model of you.

## Acceptance — what "100% confident" means (measured by the harness)

- **0 quizzes** rendered anywhere in a live game (no "?", no "can you see", no predict panel).
- **0 false claims** across the scenario set (per-FEN verifier — same bar as today).
- **Personalized threads fire correctly**: on an engine-confirmed instance of a motif/pattern
  that is in *this player's* weak profile, the coach names the thread as a STATEMENT; on a
  motif the player is strong at, it does not nag.
- **Restraint holds**: a given thread fires at most once per game.
- **Wins are caught**: a sound instance of the player's weak motif is acknowledged.
- **Coherence**: where the player-model has something to say, it wins over the generic caption.
- **Honest rates**: when a rate is spoken it's the REAL rate ("about 1 in 3 skewers"), never
  the gamified ladder-fill (the "82%").

---

## Architecture — the seams (from the 2026-06-26 research)

The caption door `build_move_teaching_decision(inputs, state)` is the one chokepoint; both
PWC and review route through it. The conductor plugs in WITHOUT rewriting the R-rules:

```
MoveInputs  (+ player_model: motif_profile, identity, weak_patterns)
CrossMoveState (+ threads_pulled_this_game)         <- restraint memory
        │
        ▼
build_move_teaching_decision
        │  extract_facts()  -> caption_facts            (fork/pin/skewer already detected live)
        │  inject_player_model_facts()  [NEW]           -> stamps conductor_thread when:
        │      this move is an engine-confirmed instance of motif M
        │      AND M is in player's weak profile  AND  M not in threads_pulled
        │  extract_primary_reason()  [+Priority 0]       -> conductor_thread wins selection
        │  render -> R_CONDUCTOR rule (statement, no question)  [NEW caption file]
        │  verify (existing per-FEN verifier)            -> engine-true or abstain
        ▼
decision.text.caption   +   state.threads_pulled += M
```

Key facts from research:
- `extract_primary_reason` (caption_facts.py ~1384) is a clean priority ladder → add Priority 0.
- `MoveInputs` / `CrossMoveState` (caption_pipeline.py ~140 / ~230) accept new fields cleanly.
- Motif detection (`multi_target_attack_evidence`, `aligned_pieces_evidence`) **already fires
  live** — the conductor only has to cross-reference it with the player's profile.
- Brain data: `player_profiles.motif_profile` + `.motif_recognition`, `player_identities`,
  `coach_memory` — load at session start onto the session, thread per move.
- Endgame detectors (`concept_detectors/endgame_{lucena,philidor,opposition}.py`) exist and
  are pure `(fen)->Optional[dict]`; just call them in the live path.
- Defensive-anticipation metric is computable from stored `opponent_move_evaluations`
  (best_move + pv_after_best per opponent move).

---

## Build order (each step has a harness check before moving on)

0. **Harness** — scenario evaluator (real games + constructed scenarios). Scores every law.
   Baseline the CURRENT behavior (expect: many quizzes, 0 personalized threads).
1. **Brain load** — load motif_profile + recognition + identity + memory onto the session at
   start; thread `player_model` through MoveInputs to the door.
2. **Motif thread** — `inject_player_model_facts` + `R_CONDUCTOR` statement rule + Priority 0
   + `threads_pulled` restraint + the win-callback. The heart.
3. **No-quiz purge** — delete hint_for_user questions, opponent_opportunity, escape-squares,
   predict-move, rate-move, habit-prompts; turn today's-goal into a one-line statement (or cut).
4. **Conductor selector** — generalize Priority 0 beyond motifs to known-weakness recurrence
   (e.g. overconfidence-when-winning from coach_memory) so one voice picks the player-relevant thing.
5. **Endgame live recognition** — call concept_detectors in the live path; statement: "this is
   a Lucena — the winning idea is the bridge." (engine/技术-verified).
6. **Defensive-anticipation metric** — build the mirror of `compute_game_recognition`; make the
   motif profile two-sided (offense / defense-caused / defense-anticipation) and speak honest rates.
7. **Iterate** — run the 100-scenario harness; fix until all acceptance bars are green.

## Testing — the scenario set (≥100)

- **Replay**: ~60 real analyzed games (prod data) rendered move-by-move through the live path.
- **Constructed**: targeted scenarios — walk-into-fork, miss-a-skewer (player weak), make-a-sound-
  skewer (win-callback), strong-motif-no-nag, repeat-motif-same-game (restraint), Lucena/Philidor
  endgame, opening line, an all-good game (does it over-talk?), a losing game (lost-position floor).
- **Per scenario, assert the laws**: no "?"/quiz tokens; 0 false claims (verifier); thread fires
  iff player-weak + engine-confirmed; ≤1 per motif/game; win acknowledged; rate spoken is real.
- The harness prints a transcript (the felt experience) + a scorecard. "100% confident" = scorecard
  all-green across the set AND the transcripts read like a coach.
