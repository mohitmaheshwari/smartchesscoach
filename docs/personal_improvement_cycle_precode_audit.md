# Personal Improvement Cycle — Pre-code Audit

**Result:** PASS — signed by Codex (implementation owner), 2026-08-25.  
**Scope:** `personal_improvement_cycle_scope.md` and spec v1.3.  
**Authorization:** the task instruction authorizes implementation after the
validation relabel. The independent reviewer is recorded as review evidence,
not as the product approver.

## Gate 1 — Schema before mockup: PASS

The existing `move_observations` emitter remains canonical. The additive
runtime contract is a versioned `piece_safety_decision` fact on each current
SEE-backed observation; no evidence collection is added. `user_active_focus`
remains the focus/instruction authority and receives only bounded projection
fields. Raw evidence remains on its game observation.

The observation schema advances from v16 to v17 for the additive D_live fact.
PIC diagnosis may read SEE-backed schemas `>=16`; D_live may read only records
whose nested fact version is exactly `piece_safety.d_live.v1`. Stored schemas
`<16` are hard-excluded. Re-derivation may replace an old record with a current
record, but an old event is never copied forward as evidence.

## Gate 2 — Pattern before notation: PASS

The user-facing focus is “Keeping your pieces safe,” supported by concrete
positions. SAN/coordinates remain evidence details, never the headline or
learner-state identity. The immutable instruction is read from the existing
focus record.

## Gate 3 — Instrument before outcome: PASS

`piece_safety.d_live.v1` is locked as:

- eligible: a knight, bishop, rook or queen is legally capturable on its
  destination after the user's move;
- miss: canonical destination SEE is at least 150 and stored Stockfish
  `cp_loss` is at least 150;
- handled: eligible and not a miss.

The corpus supplies 22,583 decisions across 149,886 v16 moves (15.07%). Two
independent SEE implementations agreed on 399/400 stratified positions. This
is implementation agreement only; the shared Stockfish gate is not presented
as independently verified. Resolution sample sizes and improvement bars remain
unset until the declared post-launch procedure runs.

## Gate 4 — Forecasted bottleneck: PASS

The pre-launch bottleneck is semantic coach meaning, not event supply. A
stratified human/engine read of approximately 50 D_live misses is required
before confirmatory rollout. Rating coverage is separately measured; unknown
ratings never receive a guessed band.

## Gate 5 — Deferred work remains deferred: PASS

Knight-fork LES content, generic community/social features, non-piece-safety
resolution, annual billing, new gamification and product-response thresholds
remain out of V1. PIC reuses LES lesson/mastery/tier/cohort authorities without
copying their rules.

## Gate 6 — Explicit implementation authorization: PASS

The current task explicitly says to start implementation after correcting the
validation label. That condition is incorporated in v1.3 and the corpus
evidence. Codex signs this implementation audit; the independent reviewer's
recommendation is not substituted for product authorization.

## First runtime slice

1. Emit `piece_safety.d_live.v1` at `move_observation_deriver.py` and bump the
   additive observation schema to v17.
2. Extend canonical `rating_resolver.py`; persist authoritative per-game rating
   at import/analysis and provide a dry-run-by-default idempotent backfill.
3. Add a default-off PIC projection through the existing
   `/api/coach/active-focus` endpoint. It reads only schema `>=16` diagnoses and
   exact-version D_live facts.
4. Suppress legacy focus-trend improvement claims while PIC is enabled; no
   resolution language appears until the post-launch evidence rule is locked.
5. Add focused unit/integration tests before expanding to teaching, mastery,
   Focus Game and frontend handoffs.

No new active-focus collection, detector service, lesson dispatcher, mastery
service, rating table or progress engine is authorized.
