# Detector Agent Coordination — category vs caption (2026-06-12)

Two parallel agents are building detectors. They are **complementary layers**, not rivals.
This note keeps them in their lanes so we don't clobber each other or double-wire Claude.

## The two layers

| | Layer | Owns | Files |
|---|---|---|---|
| **Agent A** | **CATEGORY / fundamentals** — *"what KIND of mistake?"* (mate, material-loss-by-depth, missed_free_material, endgame_technique, opening_knowledge, bad_trade, missed_tactic, conversion, positional) | the move's gap/fundamental label | fundamentals classifier + facts in `caption_facts.py` |
| **Agent B** | **CAPTION / the why-text** — *"explain WHY this move is bad"* (failure_allows_capture → "lets dxe4 win your pawn on e4") | the rendered coaching caption | `R12_blunder.json` (predicates + templates), `caption_facts.py`, `caption_claim_verifier.py`, `narrator_fallback.py`, the V5 hook |

**Direction:** category is UPSTREAM of caption. The fundamental should eventually route to the right
caption detector (a `missed_free_material` move → the missed-capture caption). Synergistic.

## Hard rules (prevent collisions)

1. **`caption_facts.py` is shared — ADD facts, never EDIT the other agent's.**
   - Each fact extractor is owned by whoever wrote it. Add new keys; don't repurpose existing ones.
   - Agent B (caption) owns: `opp_reply_*` (incl. `opp_reply_captures_piece_type` / `opp_reply_captures_square`), the failure-mode facts, `extract_primary_reason`.
   - Agent A (category) adds NEW fundamentals facts (material-by-depth, etc.) — do not change B's.

2. **ONE shared material/free-capture fact — do NOT fork it.**
   - `missed_free_material` (A's category) and `failure_allows_capture` / `why_user_missed_capture` (B's caption) describe the SAME engine fact from two angles.
   - There must be ONE underlying extractor (material-won / free-capture), read by both layers.
   - If each builds a separate material detector, they WILL disagree on edge cases (pins, recaptures, x-rays). Align on the single fact first.

3. **Reuse `narrator_fallback.py` — do NOT fork the Claude plumbing.**
   - It is single-call (NOT batch — batch-of-10 times out; confirmed by A), cached per `(fen, move)`,
     circuit-broken (3 fails → 120s cooldown), graceful (returns None on failure).
   - Both layers' Claude fallbacks call `narrator_fallback.narrate_why(...)`. Don't rebuild it.
   - Batching guidance (A's finding): single calls, or batches of 3–5 max, reusing the circuit-breaker + cache.

4. **ONE Claude-fallback wiring point — DECIDED (Agent B, 2026-06-12). Do NOT double-wire.**

   **DECISION: the single caption-narrator wiring point is the existing hook in
   `game_decryption_v5_service.py` (the per-move generation loop). Agent A does NOT add a separate
   caption-narrator call in the analysis worker.**

   Rationale: the analysis worker ALREADY calls `generate_game_decryption_v5` (the V5 service) to produce
   captions — so the V5 per-move loop runs *inside* the analysis worker's flow. The abstain→verify→narrate
   hook is already there (built + tested), with a file abstention log + hold-on-fail. Adding a second
   narrator call in the worker would narrate the same move twice = double Claude cost.

   **Integration contract for Agent A (category layer):**
   - A's fundamentals classifier runs UPSTREAM and writes the category onto the move (the cognitive-gap /
     category field) BEFORE caption generation. Do not call `narrate_why` for the caption.
   - To let the caption layer use the category, expose it in the move facts (add a `fundamental_category`
     key in `caption_facts.py`, ADD-only). The V5 hook + caption templates can then read it.
   - The existing V5 hook owns the caption Claude call (verify → ship-or-narrate). A never duplicates it.

   **Cost flag — the real double-Claude risk is two DIFFERENT calls per deferred move:**
   - A's *category-classification* Claude call (when its deterministic classifier defers: bad_trade,
     missed_tactic, conversion, positional) is a SEPARATE prompt from B's *caption-why* narrator call.
   - A deferred move could therefore hit the gateway TWICE (classify category + write why). To avoid:
     - **Sequence:** run A's category first; if A had to use Claude to classify, B's caption layer can often
       reuse that same Claude round-trip — OR
     - **Combine:** one Claude call that returns BOTH `{category, why}` for a deferred move (halves cost).
       (Design item — flag to whoever wires the worker; not blocking, but it's where the cost lives.)
   - Either way: A's category-classifier Claude calls MUST reuse `narrator_fallback`'s gateway client,
     circuit-breaker, and `(fen,move)` cache (different prompt, same plumbing). Do not stand up a second
     gateway client.

## Status snapshot (2026-06-12)

- **Agent A fundamentals:** 6 engine-hard & verified (both mates, both material-loss-by-depth,
  missed_free_material, endgame_technique). 🟡 opening_knowledge partial (early-queen only; same-piece-twice /
  no-castle / off-book need move-history + opening DB). 🔴 bad_trade, missed_tactic, conversion defer to Claude.
  34–45% deferred bucket (positional + the above) needs the hybrid wired (small-batch/single calls).
- **Agent B caption:** verifier loop merged (46% verified-detector free). `failure_allows_capture` root-cause
  fixed (66 captions gold-shaped). Filler-gate fix (55→39). Per-detector quality table exists. Remaining:
  clause-2 concrete better-move reason; m12 order-quirk.

## Shared verifier note
Both layers verify against the engine. A's "engine-hard & verified" categories and B's
`caption_claim_verifier.py` (claim verification) use the same stored engine truth (PV/eval). Worth unifying
the engine-check helpers later, but not blocking now — just don't duplicate the material-win check.
