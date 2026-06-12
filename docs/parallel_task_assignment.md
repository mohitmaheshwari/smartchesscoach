# Parallel task assignment — verified-detector / caption work (2026-06-12)

**How to use this doc:** find your lane below, read the shared rules first, then pick up your section. Each lane is scoped so agents **don't clobber each other**. If your task touches a file another lane owns, STOP and coordinate — don't edit it.

Primary/orchestrator: collects results, lands commits, owns the upfront gate (#1) and the joint finale (#2).

---

## Context (read once)

The system is a **right-or-silent caption loop**: a detector's chess claim is verified against the engine; **verified → ship, unverifiable → abstain → verified narrator → HOLD** if even the narrator can't be verified. Nothing ships a confident lie.

Key files & where things stand (all committed & deployed):
- `backend/services/caption_claim_verifier.py` — detector-side verifier (verify-or-abstain). Has: mate/check/threat/material/tactic checkers + **blunder checker** (`_verify_blunder`, catches "chase the king" confab).
- `backend/services/narrator_claim_verifier.py` — narrator-side verifier (board-checks the LLM's free text: piece-on-square, free-when-defended, no-recapture, mate).
- `backend/services/narrator_fallback.py` — the **single** Claude gateway client (serial, cached per `(fen,move)`, circuit-broken 3-fails→120s, returns None on failure). `narrate_why(...)`, `needs_narrator(...)`.
- `backend/services/game_decryption_v5_service.py` — the **single** caption-narrator wiring point (per-move loop: detector→verify→abstain→narrate→verify→ship/HOLD). **Do not add a second narrator call anywhere.**
- `backend/scripts/build_gold_set.py` → `db.gold_captions` — the **gold standard** (engine-verified Claude captions, stratified by `cognitive_gap`). `--per-gap N`.
- `backend/scripts/narrate_verify_backfill.py` — offline narrate→verify→self-correct→backfill runner.
- `docs/detector_agent_coordination.md` — the category-vs-caption lane split (Agent A = category, Agent B = caption).
- The detector-vs-gold diff finding: detectors are **strong on tactical** patterns (8/10 real-why), **abstain on positional** (piece_safety/king_safety/opening_knowledge ~7-8/10) — and those **don't reduce to predicates → narrator carries them, by design.**

---

## Collision rules — NON-NEGOTIABLE (these are exactly what bit us)

1. **Each agent works in its own `git worktree`.** Land via rebase onto `working-code`. Do **not** all edit one working tree — uncommitted files clobber.
2. **`caption_facts.py` is SHARED → ADD facts only, never edit another agent's.** Each extractor is owned by who wrote it. Only Agent B touches it, add-only.
3. **One gateway client = `narrator_fallback`.** Never open a second Claude client (it kills the cache + circuit-breaker). All Claude calls go through `narrate_why`.
4. **Do NOT `docker cp` shared service files into the one shared container.** Test via `/tmp` copies (`docker cp file chess-coach-backend:/tmp/chk_x.py` then `py_compile`/run there), or use your own container. Overwriting service files corrupted a measurement mid-run.
5. **Do NOT double-write Mongo or the abstention log.** Only Agent D writes `db.gold_captions` / `game_analyses`.
6. **Only commit your own files.** `git add <your files>` explicitly — never `git add -A` (sweeps another agent's WIP into your commit).

## The one bottleneck: the gateway is SERIAL
`narrator_fallback` is one serial client (~13s/call). Lanes **C** and **D** both use it heavily → they **queue, not parallelize.** Give them a **shared budget / time-slice** (C's ~57-move judge first, then D's gold-expansion), or cap both low through the one client. Lanes **A** and **B** don't touch the gateway → fully concurrent with everything.

---

## GATE (do FIRST — primary/orchestrator) — #1 Post-deploy functional verify

**Why first:** the whole loop was committed without a functional run (the Mongo tunnel was down). Everyone else builds on top of a confirmed loop.
- **Steps:** once the tunnel is up, render ~10 real prod games through `generate_game_decryption_v5`; confirm flagged moves ship **verified** captions (no confab), and abstain→narrator→HOLD behaves; spot-check 5 against the engine.
- **Done when:** a short report — % shipped-verified / % abstained / % held, and zero confabulations in the verified set.
- **If broken:** fix before the build lanes proceed.

---

## Lane A — Openings (FULLY independent, no gateway) 🟢

**Goal:** make the Sicilian anti-lines / Caro-Kann Advance sub-variations show as **distinct tracked openings** (they currently *teach* in the lesson tree but aren't *detected* as separate openings).
- **Owns:** `backend/services/opening_lookup.py`, `backend/data/opening_curriculum.json`, the `setup_order` / detection path.
- **Don't touch:** anything in the caption/verifier/narrator/classifier layer.
- **Current state:** the 4 new openings + deepened Sicilian/Caro-Kann trees shipped (`71a7cfd0`). Detection keys off `setup_order` (the main line), so anti-Sicilians (Alapin/Smith-Morra) detect as "Sicilian" not as sub-lines.
- **Steps:** add `setup_order`-based recognition (or a sub-variation tag) so a game that ran through the Alapin/Advance is labelled as that sub-line on the progress page.
- **Done when:** a game in those lines shows the sub-variation; `opening_sync_check` stays green.
- **Gateway:** none.

## Lane B — Detector grow (tactical refinements only) 🟡

**Goal:** close the small **tactical** gaps the gold-diff surfaced — do NOT build positional predicates (those are narrator territory by design).
- **Owns:** `backend/services/caption_claim_verifier.py`, `backend/data/captions/R12_blunder.json`, `caption_rules.py`.
- **Reads (add-only):** `caption_facts.py`.
- **Current state:** blunder checker shipped; 0 filler now leaks (right-or-silent). Tactical patterns cover 8/10 vs gold; positional abstain (correct).
- **Steps:** use the `author-r12-predicate` skill. **Only build a failure mode with ≥2 clean same-mechanism examples** (the skill gates this — piece_safety had none, don't force it). Candidates to validate first: the `hangs_piece`/`exchange_losing` routing pre-empted by check/capture framing (Bxf7+ check-sac, Qxf3 queen-recaptured). File singletons in `CAPTION_BACKLOG.md`, don't build them.
- **Done when:** each new checker verifies against the engine (right-or-silent), probe passes, ≥85% match to the relevant gold slice.
- **Gateway:** none (engine-grounded).

## Lane C — Quality judge (independent code, shares gateway) 🟡

**Goal:** measure the **real quality gap** — the ≥85%-match-to-gold number the diff didn't compute (coverage ≠ quality).
- **Owns:** a **new** script `backend/scripts/judge_vs_gold.py`. Does not edit any service file.
- **Reads:** `db.gold_captions` (the 57 golds), renders current detector output per gold move.
- **Steps:** for each gold move, render the current detector caption (stubbed Stockfish, `game_id=None`), then LLM-judge (via `narrate_why`'s client) MATCH/PARTIAL/MISS on: same why? same alternative? truthful (engine-verified)? easy + has-why? **Validate the judge on ~15 hand-labeled first** (per the skill — don't trust the batch number from an unvalidated judge).
- **Done when:** a per-pattern % match table + the worst-falling-short templates (e.g. the "you were already losing" defeatism) flagged for Lane B.
- **Gateway:** YES — ~57+ calls. **Run before Lane D's expansion** (time-slice).

## Lane D — Gold + narrator scale (independent scripts, gateway-heavy) 🟡

**Goal:** grow the gold standard + wire **demand-driven** narrator backfill (NOT a 7-day eager run).
- **Owns:** `backend/scripts/build_gold_set.py`, `backend/scripts/narrate_verify_backfill.py`; writes `db.gold_captions`, `game_analyses`.
- **Steps:** (1) expand gold — `build_gold_set.py --per-gap 25` across more patterns (king_safety/opening already sampled; add the rest). (2) Wire the **lazy** backfill: process the *real* abstention queue (moves real users view, `game_id` set) — NOT the census log (`game_id=None` = noise). Each move: narrate→verify→self-correct→backfill verified only.
- **Done when:** ≥150-move gold set; the lazy backfill demonstrably fills a held move with a verified caption end-to-end.
- **Gateway:** YES — heavy. **Run after Lane C** (time-slice). Reuse `narrator_fallback`'s client + cache.

---

## FINALE (do LAST — joint, after A/B stable) — #2 Double-Claude-call optimization

**Why last & joint:** it merges the **category** call (Agent A's classifier) + the **caption-why** call into one, so it spans both lanes and touches the shared wiring (`narrator_fallback` + the V5 hook).
- **First pin the question:** *does the category gate caption selection, or is it just metadata written alongside?*
  - **Metadata →** combine into one `narrate() -> {category, why}` call (1 round-trip).
  - **Gates selection →** must sequence (category first), but reuse the **one** client + cache (still 1 client, 2 cached calls).
- **Guarantee:** ≤1 Claude call per move; one client; cached. Wire only in the existing V5 hook.

---

## Sequencing at a glance

```
NOW (parallel):     [#1 verify — primary]  [Lane A]  [Lane B]
                                            (gateway-free, fully concurrent)
GATEWAY (time-slice): [Lane C judge] → [Lane D gold+backfill]
AFTER A+B stable:    [#2 double-call — joint A+B+primary]
```

**Fully concurrent now:** #1, A, B. **Time-sliced on the gateway:** C then D. **Last:** #2.
