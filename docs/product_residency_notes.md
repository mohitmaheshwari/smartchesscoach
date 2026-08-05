# Product Residency — Session Notes

**Format, agreed 2026-08-05:** one screen per session. Not "what should
we improve" — five fixed questions, every time:

1. What is this screen trying to make the player think?
2. What is it trying to make the player feel?
3. What is it trying to make the player do next?
4. What work is the system doing that never reaches the player?
5. What evidence do we have that it's succeeding?

We redesign nothing until we understand everything. Every session ends
in something concrete — a decision, a document, an experiment, or a
shipped change — never an abstract discussion.

---

## Session 1 — Home (2026-08-05)

**Scores:** Pedagogy 9.5/10, Psychology 9/10, Simplicity 9.5/10,
Engineering efficiency 6/10.

### The four rendered sections

1. **Greeting** — ephemeral, orientation only, zero backend cost.
2. **"Since you last played" (the Mirror)** — `build_game_mirror()`,
   deliberately wins over a coach-session recap whenever any analyzed
   imported game exists ("imported games are where in-the-wild habits
   show up"). Deliberately describes the *shape* of what happened, not
   the SAN — a 2026-06-01 decision, explicit in the code: *"a 1200
   doesn't anchor memory on 'Rf1 on move 16.'"* **Never regress this.**
3. **The Coach Conversation** — gated on `games_analyzed > 0` AND a
   settled focus (`focus_bridge.get_active_focus_bundle`). Stage opener
   → continuity + hedged theory → one action → encouragement, per
   `docs/home_page_coach_conversation_scope.md`. The theory text
   includes a `_get_tilt_overlay()` step — the tilt/post-blunder-
   collapse theory from this session's own research work is **already
   partially wired into what a real user reads**, not just sitting in
   the ledger untested.
4. **Faded nav tiles** — deliberately de-emphasized, a direct 2026-07-31
   quote in the code: *"I'd fade those into the background."*

### The engineering-efficiency finding

`dashboard-v2` computes 11 top-level fields; the frontend reads 3. See
the Evidence Board's new "Home page — orphaned fields" section for the
per-field ownership recommendations. **Decision: do not trim yet** —
ownership-before-deletion, consistent with this session's governance
discipline. Trim only after every field is labeled Owned (real target
surface within 90 days) or Retired.

### Ephemeral vs. cumulative — refined, with one pushback on the draft

| Element | Ephemeral or cumulative | Why |
|---|---|---|
| Greeting | Ephemeral | Pure time-of-day, no memory |
| Mirror | Episodic | Anchored to one specific recent game |
| Coach Conversation — stage opener | Cumulative | Keyed to `games_analyzed`, deepens over months |
| Coach Conversation — continuity + theory-of-why | Cumulative | A persistent belief about a recurring pattern, revised over many games |
| Coach Conversation — **one action** | **Episodic in delivery, cumulative in origin** | Pushback on the draft table: this was marked purely "Cumulative," but the artifact itself is a specific, today-only instruction — the *reasoning behind it* is cumulative, the *instruction* is not. Worth keeping these distinct since they could diverge (a cumulative diagnosis producing a stale-feeling daily instruction is a real failure mode to watch for) |
| Coach Conversation — encouragement/closing | Mixed, leaning cumulative | Relationship-toned, not tied to today's specific event |
| Nav tiles | N/A | Pure utility |

### The open product question: "here's what happened" vs. "here's who you're becoming"

Real answer, not a vague "yes there's a gap": **the Coach Conversation
genuinely does carry identity framing** — the stage opener and the
theory-of-why are claims about who the player is, not what happened
yesterday. The gap isn't in that section's content. It's in **emphasis
order**: the Mirror is unconditional and renders *first*, every single
day, whenever it exists — and the Mirror is 100% episodic by design. So
the very first thing a returning user reads on Home, every day, is
"here's what happened," and only after that "here's who you're
becoming." Not a content problem. An ordering-and-emphasis one, worth
watching rather than acting on yet — noted here so it isn't lost, not
prescribing a fix before more screens are reviewed.

### Concrete outputs, this session

- ✅ Home instrumented with 6 real analytics events (Experiment 0 — pure
  observation, no behavior change). See `frontend/src/lib/analytics.js`
  for the event vocabulary.
- ✅ Ownership table for all 8 unused `dashboard-v2` fields, added to
  the Evidence Board.
- ❌ Did not trim `dashboard-v2` — correctly deferred pending ownership
  decisions above.

---

## Session 2 — Diagnostic (not yet started)
