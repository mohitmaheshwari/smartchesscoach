---
name: feasibility-verdict
description: Use BEFORE answering any "can we build/implement X?", "is X possible?", "does Y already exist?", "do we have Z?", or "can our detectors/captions/classifier already do W?" question about this codebase. Forces codebase research FIRST, then a single binary evidence-backed verdict (YES with the exact how, or NO with why) — never speculation, never a hedge, never an answer that changes next turn. If the user's exact idea can't be used as-is, return 2-3 grounded alternatives. Trigger on any feasibility/existence/"can we"/"does it already"/"do we have"/"can X already do Y" intent.
---

# Research → one 100%-confident verdict. Never flip-flop.

**Why this exists (real, 2026-06-12):** Mohit asked about a reflection-coaching idea; I "suggested" ~8 features as if novel — *they were already built* (intent + confidence capture in `reflect.py`, the intent taxonomy in `coaching_classifier`, the intent-vs-reality "awareness_gap"). Then across turns I hedged ("probably", "~80%") and changed the answer. That erodes trust and wastes his time. The fix: **verify in the code FIRST, then state one verdict with confidence earned by evidence — and hold it.**

## When to invoke
- "can we build / implement / do X?", "is X possible / feasible?"
- "does Y already exist?", "do we have Z?", "can our detectors / captions / classifier / memory already do W so we don't write a new thing?"
- ANY existence or feasibility question, BEFORE committing to build or declaring something missing.

Do NOT invoke for a pure design/opinion question with no factual claim to verify (e.g. "which of these two UIs do you prefer").

## The hard rule
**Never answer a feasibility/existence question from memory or speculation.** Research first; then deliver ONE verdict. Confidence is *earned by verification*, never asserted.

## The ordered process — do NOT answer before Step 3
1. **Research the actual code.** `grep`/read the real files; run it if the env allows. Find what EXISTS (with `file:line`) and what's MISSING. "I think we have that" is not allowed — go look.
2. **Verify the claim end-to-end, including the DATA.** A function that exists but reads an empty/missing collection is **not working** (the recurring "capture-rich, siloed, underused" trap here — `habits_report` 1%, `cognitive_gap_history` missing, reflections never reaching `coach_memory`). Existence of code ≠ a working capability. Check the wiring and the data, not just the symbol.
3. **Deliver ONE binary verdict with evidence:**
   - **YES — exists / implementable:** state it plainly, cite `file:line`, give the exact how — *what you reuse, and the only genuinely-new piece*. No "probably."
   - **NO — not as asked:** state it plainly, cite why with evidence. No "maybe."
4. **If NO (or "exists but not the way asked"): give 2-3 TOP alternatives, ranked** — the closest grounded approaches, each with what it reuses + rough effort (S/M/L). Not a brainstorm dump; the best 2-3.

## What counts as 100% confidence (and the honest boundary)
- ✅ From **verification**: "I grepped/read/ran it — here's the evidence."
- ❌ NOT from assertion or memory.
- **If you genuinely can't fully verify** (env down, can't execute): split it explicitly —
  - *Verified:* what you proved by reading code (symbols/wiring exist or don't) — state with full confidence.
  - *Pending:* what needs a live run to confirm (does it produce a sane result) — name the exact check.
  - You are still 100% confident **about the part you checked**. Be honest about the boundary, but **do not let the unverified part make you flip-flop on the verified part** next turn.

## Anti-patterns this kills (all happened this session)
- **Suggesting features without checking they exist** → grep before you ideate.
- **Flip-flopping** → verify once, answer once, hold the verdict; only change it if NEW evidence appears (and say what evidence).
- **Hedging when a grep would settle it** ("probably", "~80%", "I think") → if you *can* check, check.
- **"It's in the code" → "it works"** → verify data + wiring; cite the collection counts / the missing write.

## Output shape
```
VERDICT: YES / NO  (re: exactly what was asked)
EVIDENCE: <file:line facts — what exists, what's missing, data/wiring checked>
IF YES → HOW: reuse <X, Y>; only new piece = <Z>; effort = S/M/L
IF NO  → WHY: <evidence>  +  TOP ALTERNATIVES (2-3, ranked, each: reuse + effort)
VERIFIED vs PENDING: <what I proved> | <what still needs a live run, and the exact check>
```

## Notes
- Sibling of the existing disciplines: [[feedback_check_for_existing_ui_before_building_offline]], [[feedback_query_engine_before_authoring]], [[feedback_three_detection_principles]] (prove detection before building). This one generalizes them to *every* feasibility/existence answer.
- Pairs with `end-to-end-trace` (use it as the Step-1 research method when the question is "is this flow wired").
