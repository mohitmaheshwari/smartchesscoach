# Community Game Coherent Walkthrough

**Status:** APPROVED BY MOHIT — EXTEND EXISTING
**Date:** 2026-09-15
**Parent:** `docs/complete_coaching_system_community_extension_spec.md`

## 0. Existing surfaces audit

ChessGuru already owns every surface this experience needs:

- **Game Review library:** `AllGames.jsx` already presents one coach-selected game before the full archive. It gives the user a reason to review and opens the existing review experience.
- **Guided board review:** `GameDecryptionV5.jsx` already owns the board, move navigation and move-coaching cards. Its current Socratic block can render a question and click-to-reveal hint for the existing authored move-caption variants. It does not provide a community-chapter prediction flow, line-watching controller or learner replay. It remains the only page where the new walkthrough is shown, but the five-step interaction is new work inside it.
- **Personal review selection:** the current review planner and coach-selected review service already choose, resume, dismiss and complete personal reviews.
- **Community-game safety:** `community_game_study_service.py` already owns licensed-source admission, anonymity, legal replay, neutral chapter projection and Shadow ranking. It does not yet serve a player-visible study.
- **Chess facts and language:** `caption_facts.py` and `caption_pipeline.py` already own board-grounded causes. `caption_principles.py` owns the named principle catalog. The opening theory tree and exact curriculum proof own opening knowledge. The endgame theory tree, exact curriculum proof and tablebase evidence own endgame knowledge. `detector_quality.py` alone decides which of those facts may speak to a player.
- **Learning evidence:** the existing lesson-result, learning-ledger and Progress paths already distinguish assisted study from later-game transfer.

There is substantial overlap with the proposed experience. A new page, caption engine, principle table, opening recognizer, endgame library or progress tracker would duplicate existing authorities and create conflicting coaching.

The genuine missing value is **coherence**: arranging several independently verified moments from one game into a memorable beginning, turning point and finish, while explaining why this particular game belongs in this learner's plan. The v2 independent review proved the factual foundation but measured only 4 of 41 coherent stories, only 10 studies reaching the finish, 12 uncovered checkmates and only two repeated principles.

**Decision: EXTEND EXISTING.** The existing Game Review library, `GameDecryptionV5` renderer, review lifecycle, community admission service and canonical chess-fact sources are extended. No parallel product surface or knowledge source is created.

## 1. What it is

The coach chooses a complete, anonymous game from players near the learner's level because the game contains a lesson that fits the learner's current plan. Instead of listing two or three unrelated mistakes, the coach tells the story of the game: what the position was asking for, where the important idea appeared, what could have happened, and how the game actually ended. The learner predicts, receives a bounded hint, watches the verified line on the existing board and replays the idea. Every sentence comes from legal board facts and authorized chess knowledge; when ChessGuru cannot prove an explanation, the chapter is omitted.

## 2. What the user sees

Game Review continues to lead with one coach decision:

```text
MY PICK FOR YOU

The queen left before her pieces were ready

This game was played by someone near your level. The opening looked safe,
but one unsupported queen move shaped everything that followed. The finish
shows why your current piece-safety lesson matters.

[ Study this game with me ]      [ Choose another day ]
```

The existing review board opens a guided story, not a report:

```text
THE STORY OF THIS GAME                         Chapter 1 of 3

The queen moved before her support was ready

White's queen is safe for the moment, but the knight on f6 can attack it
while developing. The queen must move again while Black improves a piece.

What would you expect Black to do?
[ Attack the queen and develop ]
[ Trade queens immediately ]
[ I am not sure yet ]

[ Give me one hint ]   [ Show the idea ]
```

After the learner answers, the same board demonstrates the verified sequence:

```text
YES — THIS IS THE IDEA

...Nxd5 attacks the queen while bringing a piece into the game.
Develop with a threat when you can: you improve a piece and make them respond.
Watch the two-move sequence, then replay it yourself.

[ Watch the line ]   [ Let me replay it ]   [ Continue ]
```

The final chapter explains the ending when a verified finish exists:

```text
HOW THE GAME ENDED

The king ran out of safe squares

The rook controls the back rank and the pawns block the king's escape.
Qf1 is checkmate because the king has no legal square and no piece can block.
When the king has no escape square, a rook or queen can finish the game there.

[ Watch the finish ]   [ Replay from the turning point ]
```

The chapter headline always leads with the pattern, geometry or chess idea. SAN appears only in the explanation, board controls or replay evidence. If an exact opening or named endgame technique is not currently authorized, the coach uses a narrower board fact or stays silent; it never substitutes generic theory.

## 3. In scope

- Extend the current community-game neutral projection and existing Game Review renderer; create no new destination page.
- Build one deterministic story from authorized chapters in the same game, with explicit narrative roles such as setup, turning point, missed possibility and finish.
- Use variable chapter counts based on evidence. Never add a filler chapter to satisfy a visual layout.
- Generate pattern-led headlines from the verified cause, geometry or canonical concept—not from the SAN move.
- Prevent one study from repeating the same transferable principle as separate teaching three times. Later occurrences may be concise reinforcement only when they advance the story.
- Include an exact checkmate or terminal-result chapter when the stored game and current authorized fact prove it.
- Add already Caption-authorized tactical families to the candidate measurement: forced mate, fork, pin/skewer, free piece, verified material sequence and exact endgame result change.
- Measure existing exact opening and named endgame families in Shadow and create separate blinded promotion evidence before any of their names or teaching claims can appear.
- Reuse the opening theory tree, endgame theory tree, canonical proof services, caption principle catalog and detector-quality registry. Adding a family must not create a copied content table.
- Keep source-player identity and private diagnosis absent. Personalization explains why the selected lesson fits the current learner; it never rewrites the neutral chess fact.
- Add the predict, hint, reveal, watch and learner-replay states inside the existing review path. These interactions are not treated as pre-existing or free. A demonstration must legally prove the visible explanation, and an interactive chapter must carry the authored content needed by every state.
- Record completion as assisted learning through the existing learning ledger. Only a later unassisted game may affect transfer or improvement claims.
- Produce a new frozen, anonymized packet and require independent factual, teaching and whole-game review before visibility.
- Keep the feature default-off. The first visible cohort is exactly the three existing admin accounts through the canonical complete-coaching access decision; no separate allowlist is created.

## 4. Explicitly out of scope

- A second Game Review page, separate community feed or public game browser.
- Popularity, famous-player, spectacle or largest-engine-swing ranking.
- New opening, endgame, tactical or positional facts invented inside the community-study service.
- Promoting a Shadow or Disabled family because the walkthrough needs more variety.
- Generic opening labels that are not tied to the exact position and decision.
- Naming an endgame technique from material count alone.
- LLM-written chess claims, Stockfish reruns, Maia inference or model calls at runtime.
- Guaranteeing that every study covers opening, middlegame and endgame. Many real games do not contain all three; the coach promises a coherent story, not three padded labels.
- Claiming mastery, rating improvement or transfer from finishing the walkthrough.
- Human-opponent matchmaking, shared review, community reputation or user-authored explanations. Those remain separate workstreams in the parent program.
- Ordinary-user rollout before the new independent packet and account-isolated E2E pass.

## 5. Success criteria

- **Truth:** independent review finds zero incorrect or overclaimed chapters and zero critical false claims. Every demonstration legally replays and proves the visible explanation.
- **Teaching:** the new packet exceeds v2's `correct_and_teachable` rate of 71.8% (79 of 110), rather than merely exceeding its raw count, without reducing factual precision. Pattern-led headlines, principle diversity and finish coverage are graded separately so one strong total cannot hide a weak dimension.
- **Whole-game value:** the independent reviewer would assign more games than the v2 baseline of 20 of 41 and judges the selected chapters to form a coherent story more often than the v2 baseline of 4 of 41. The exact rollout floor is locked from the measured v3 distribution before visibility, not chosen in advance.
- **Behavior:** after visibility is approved, the primary product measure is whether a learner who starts the assigned study completes its predict → watch → replay path and continues to the coach's linked personal next action. The acceptance threshold is locked from the existing personal-review baseline before rollout.
- **Honesty:** study completion records assisted learning only. No completion event changes a later-game transfer verdict.
- **Continuity:** when the community-study flags are off, the current personal recommendation and Game Review behavior remain byte-equivalent.
- **Reach:** a user who has no qualifying community game receives the existing personal review or an honest no-assignment state, never a generic or repeated filler study.
- **Rollback:** immediately disable community-study visibility if any player receives an incorrect or unauthorized chess claim, an illegal or mismatched demonstration, source identity, an interaction that cannot be completed or escaped, or a changed personal-review result while the feature is off. Preserve study and attempt evidence, return the user to the personal review path and require a new independent packet before re-enabling. If the measured completion-to-next-action rate misses the separately locked cohort floor, stop cohort expansion and return to Shadow without claiming the product worked.

## 6. Questions resolved by the data lock

- **Chapter budget:** variable two-to-three chapters. Game length does not set the count. A fourth chapter added no coverage and nearly doubled repetition in the frozen comparison.
- **Authorized family mix:** verified single-game causes remain primary. Fork, alignment and free-piece proofs enrich the same moment instead of creating duplicate chapters. Forced mate and exact endgame result remain available only when their exact proof fires.
- **Opening and named endgame knowledge:** remain Shadow. The measured population did not support a promotion and the walkthrough does not infer them.
- **Quality thresholds:** locked in `docs/community_game_coherent_walkthrough_data_lock_2026_09_15.md` as rates, with denominators always reported.
- **Behavior threshold:** current production history is insufficient. The first three admins are an operability cohort only; ordinary-user expansion is blocked until server-side journey events create an honest baseline.

## 7. Pre-code requirements

- Mohit explicitly signs off on this complete scope document after the `EXTEND EXISTING` decision.
- The v2 independent review remains versioned and bound to packet SHA `1d92050c950d3cfa2a17eae7b07208f2156096596b582f00254bef7b68def974`.
- A read-only family-incidence measurement identifies what each existing Caption-authorized family would add to the frozen population.
- The candidate chapter-budget and story-order formulas are compared with data; no new count, weight or cutoff is selected from intuition.
- The exact authorization grade and limitation of every candidate family are recorded before it can enter the neutral projection.
- The independent v3 review rubric is frozen before generating the packet and separately grades truth, teachability, pattern-led headline, principle diversity, finish coverage and whole-game coherence.
- Tests prove that Shadow and Disabled knowledge cannot cross the player-facing boundary, even when it would improve apparent coverage.
- The implementation plan names the existing files being extended and demonstrates that no new content registry, caption engine, review lifecycle or learning authority is being created.
- Interaction ownership is locked before implementation:
  - `GuidedReviewMoment.jsx`, a new child mounted by `GameDecryptionV5.jsx`, owns the predict choices, hint request and reveal state. It does not create another page or another board.
  - `GameDecryptionV5.jsx` owns watch-line playback on its existing board and learner replay from the chapter's starting FEN; `GuidedReviewMoment.jsx` only sends the requested action and displays its state.
  - `InteractiveMoment.jsx` remains the prototype/GameMoments interaction and is not silently mounted into the canonical review path.
  - A community hint is un-gated only when the admitted neutral chapter contains a non-empty validated question, prediction options and hint authored through the existing central fact-to-teaching source for that authorized family. JSX cannot invent or fall back to generic hint text. Empty authored content makes that chapter non-interactive and therefore ineligible for the visible walkthrough.
- The pre-code audit passes after the data lock and before the first implementation edit.
