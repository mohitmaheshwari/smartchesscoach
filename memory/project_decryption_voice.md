---
name: ChessGuru Decryption Voice — Canonical Rules
description: The locked voice for the "Show me why" layer that explains what was happening on the board. Sister doc to project_coach_voice.md.
type: project
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
The Decryption Voice is what the player hears when they tap "Show me why" after the Truth line. It is **not feedback** — it is *explanation*.

> **Coach Voice tells you what you did.
> Decryption shows you what was happening.**

Both are required. Both are different. Coach Voice talks *to you* about your play; Decryption tells you what was happening on the board so you understand why a position decided.

These rules apply to V5 plan dicts (`current_problem`, `consequence`, `better_approach`, `transferable_learning`), narrative one-liners, the Decryption layer in the post-game screen, and any LLM-generated position explanation that reaches a player.

**Why:** the existing V5 narratives ("wins two pawns", "Qc2# attacks the king and the knight") are technically correct but emotionally dead. They state engine summaries, not coaching translations. We need a voice that turns "+3.4 after h5" into something a 1100 player remembers next game.

**How to apply:** every decryption string must pass all 6 rules below and the discipline test. Anti-patterns are deleted on sight. **Cleverness is the single biggest failure mode** — quotable poetic lines that don't move the player closer to understanding the position. Cut them.

## The 6 Core Rules

1. **Translate the board, not the engine.**
   Describe what the pieces were doing, not what Stockfish thinks. Never centipawns, never "best move was X," never "+1.4 after this." The player learns position-level cause and effect, not engine output.

2. **Name the exact moment things changed.**
   Decryption pivots around *one* specific move or *one* specific exchange. *"After the queen trade on move 22..."* — not *"in the middlegame..."* The reader needs a hook in the actual game.

3. **Show what the player lost the ability to do.**
   The wow isn't "they did X." It's "X meant you couldn't do Y anymore." *"You weren't simplifying — you were giving up the only piece that could fight in the endgame."* *"After move 18, every one of your pieces had a defensive job. You couldn't create threats."* This is the felt experience of being squeezed.

4. **Explain why the opponent's idea worked.**
   *Not just what it did — why you couldn't stop it.* This is the rule that separates description from understanding. *"Their pawn pushed you back"* describes. *"It worked because you had no piece to challenge it"* explains. Every decryption must answer: **why couldn't the player stop it?**

5. **Use only natural, spoken language.**
   Plain words a 1100-rated player uses naturally. Out: prophylactic, outpost, minority attack, zugzwang, "tactically/positionally/strategically." In: fork, pin, skewer, sacrifice, "pointed at," "tied down," "no piece to challenge it."

   **Easy Indian English specifically.** The audience is players in Bengaluru, Mumbai, Delhi, Hyderabad — English-fluent but not American. Avoid American idioms that don't translate: "dies on the board," "smell a win," "run with it," "off the rails," "got hosed." Use short subject-verb-object sentences (max ~12 words). Plain words: "Their rook stayed on g2 instead of stepping to d2." "Your king reaches e7 next move." Not: "Their rook never quite found its calling on the d-file."

6. **End on the cause, not the verdict.**
   Bad ending: *"...and that's why you lost."* (the player already knows)
   Good ending: *"You had no immediate response because every move you'd made until then was about your queenside plan."*
   Decryption ends with the *reason* — something the player can carry into the next game.

## Style constraints (secondary)

These shape the prose but aren't core thinking rules:

- One idea per sentence. Two ideas per paragraph max.
- Hard cap ~25 words per sentence.
- Narrative prose only — no bullet lists in the decryption body. (Bullets are fine in side panels and Truth lines.)

## Anti-patterns — delete on sight

**Engine leakage:**
- "Stockfish suggests / prefers / sees..."
- "+3.2", "−150 cp", "evaluation drops to..."
- "Best move was X" — instead, *"X would have kept the queens on, which is what your king needed"*
- "Accuracy %", "blunder count", "mistake severity"

**Empty descriptors that explain nothing:**
- *"They created pressure"* — meaningless unless you show *how*
- *"You got into a bad position"* — tells the player nothing
- *"This was strong because it improves their position"* — circular explanation
- *"They had attacking initiative"* — vague jargon for "their pieces were pointed at your king"

**Coaching that breaks immersion:**
- *"You should have..."* — pulls the player out of the position; talk about what *was happening*, not what they should have done
- *"Tactically / positionally / strategically"* — adverbs that hide rather than explain
- *"Material / exchange sacrifice / compensation"* — vague jargon. Replace with what was actually traded and what was gained.
- *"Move 22 was a blunder"* — telling the player what they already know. Skip the verdict; explain the *mechanism*.
- *"Fortunately / unfortunately / sadly"* — stay neutral. The player feels the outcome; the decryption explains it.

**Cleverness:**
- Lines that read like a tweet or a quote.
- Lines that generalize from the position to a principle ("a player who only reacts loses to anyone with a plan").
- Anything you'd want to highlight in a slide deck.
  Decryption explains *this* position, not chess in general.

## Side-by-side calibration

**A back-rank loss after attacking the queen**

- Off-voice: *"Rxa3 was a blunder. The engine evaluation drops by 800 centipawns. Best move was Re8, which would maintain back-rank defense. After Rxa3, Black plays Qxe1 mate."*
- In-voice: *"Your rook went after their queen — good idea, except their bishop on g5 already had your knight pinned, and once your rook left f1, your back rank had no one home. They didn't need to defend the queen. They just played Qxe1 mate. The threat wasn't on the queen — it was on the file you abandoned."*

**A winning position thrown by simplifying**

- Off-voice: *"Trading queens here gives away the win. The endgame is lost because the king activity is unfavorable for White. Better was Qd5, maintaining tension and centralization."*
- In-voice: *"When you traded queens, the position looked simple. But your king was on h1, theirs was already on e6. With queens off, the king that's already centralized starts winning. By move 35, their king was on d4 supporting passed pawns. Yours was still on h1, behind a wall of pawns it didn't need anymore. You didn't simplify the position. You gave up the only piece that could fight in the endgame."*

**A gradual squeeze with no single moment**

- Off-voice: *"By move 20, the position is strategically lost. Black has more space, better piece coordination, and weak squares around White's king. White's pieces are passive."*
- In-voice: *"After move 18: your knight on f6 was defending h7. Your bishop on e7 was defending d6. Your rook was tucked behind a pawn. Every piece had a job — every job was defensive. Meanwhile they had three pieces pointed at your kingside. They were playing both sides of the board. You stayed on one. You couldn't create threats — there was no piece free to do it."*

**A sharp tactical mistake explained**

- Off-voice: *"Bd5 loses material because Nf5 wins the bishop pair and weakens the king's defense. The position evaluation goes from −0.3 to +2.1."*
- In-voice: *"Bd5 stepped right into Nf5. The knight didn't just attack the bishop — it also covered the only square your king had if check came down the e-file. So one move attacked your bishop AND took away your king's escape. You couldn't defend both. That's why it worked."*

## The discipline test

Before any decryption string ships, run it past these six questions:

1. Did I name a specific piece, square, or file? (geometry)
2. Did I describe what was being *done to* the player, not just what the player did wrong? (felt experience)
3. **Did I explain *why* the opponent's idea worked — why the player couldn't stop it?** (understanding)
4. Are all my words ones a 1100-rated player uses naturally? (vocabulary)
5. Did I end on a *reason*, not a *verdict*? (carry-forward)
6. Could I read this 30 seconds after a loss without feeling talked down to or dumped on? (tone)

If any answer is no, rewrite. If the line *also* sounds like a quote — cut the cleverness even if every other test passes.

## Surfaces to align

The Decryption Voice applies to (and currently violates) these surfaces:

- `backend/services/game_decryption_v5_service.py` — `plan` dict generation, narrative templates, PV tactical analyzer prose
- `backend/services/game_decryption_llm_service.py` — LLM system prompt, batch instructions, output schema validation
- `backend/services/postgame_analysis.py` — habit violation explanations, memory insight phrasing
- `backend/services/coach_review_service.py` — narrative arc prose
- `frontend/src/components/GameDecryptionV5.jsx` — section labels, "what happened" copy, explanation accordions
- Any LLM-driven position commentary in `backend/services/coach_narrative_engine.py`
- The Truth line generator (when built) — Truth obeys Coach Voice; the expansion below it obeys Decryption Voice

When in doubt: Truth line uses Coach Voice. Expansion below uses Decryption Voice.
