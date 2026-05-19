---
name: multi-move-review-play-the-line
description: For tactical sequences that need 2-3 moves to make sense, the review surface should PLAY THE LINE directly on the board (with intermediate move explanations as needed), not try to explain the whole thing in one caption.
metadata:
  type: project
---

**UX pattern (locked by Mohit 2026-05-19):** when a tactical sequence is 2-3 moves deep, **don't try to explain it in a single caption.** Play the line directly on the board, with intermediate-move explanations where they help.

**Why:** Single captions force the renderer to compress multi-step tactics into one sentence. A Légal-style mate has SETUP → CAPTURE → DISCOVERED-CHECK → MATE — four moves of meaning. Trying to compress it loses the texture, and the user reading it doesn't visualize the moves. Watching it play out on the board, with brief intermediate annotation ("this is the bait", "now the discovery", "and mate"), is how a human coach demos.

**How to apply:** In the Lab review surface (LabV2.jsx already has the `playBestLine` function — it plays the engine's PV on the board after a user picks the correct move). Extend this:

1. **For tactical key-moments where pv_after_best has 3+ plies:** auto-play the line on the board AFTER the user has made their choice (correct OR wrong). Don't just show the "best move" as text.

2. **Intermediate-move annotation:** for each ply in the played line, surface a one-line caption ONLY if the move adds meaning (e.g., the sac, the discovery, the forced reply). Skip captioning trivial moves (forced recaptures, single-legal-moves) per [[no-hollow-coverage]].

3. **Pace:** the line plays out at a watchable pace (~800ms per move) so the user can follow visually. Not instant — that loses the storytelling.

4. **Pause point at critical moves:** if the line has a moment where the user should think ("after Nxe5, what does white have?"), pause and let the user predict the next move. Then continue.

**Existing scaffolding:** `LabV2.jsx:playBestLine` is built and runs on correct answers in the interactive review. It currently plays the line silently. The extension is **intermediate annotations** + **pause-and-predict moments** for deeper sequences.

**Backend data needed:** `pv_after_best` is already populated on game_analyses move records (Stockfish principal variation). Each move in the PV can carry a brief annotation OR get one synthesized at render time. For V1, only annotate the "key" moves (sacs, mates, deflections); skip routine moves.

**Companion:** [[no-hollow-coverage]] (only annotate when the move adds meaning), [[teaching-not-reading]] (voice), [[sub1500-memory-anchors]] (visuals over text for this rating band).
