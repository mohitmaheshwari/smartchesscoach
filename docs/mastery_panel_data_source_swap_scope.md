# Mastery Panel Data-Source Swap — Scope Document

**Status:** AWAITING MOHIT SIGNOFF (2026-06-05)
**Skill applied:** `/scope-driven-development` (with Section 0 existing-surfaces audit)
**Next skills:** `/lock-via-data` (if numeric thresholds emerge) → `/audit-pre-code` (before first file)

---

## 0. Existing surfaces audit

This is the audit I should have done BEFORE the conversation reached the "let's just swap the data source" framing. Doing it now changed my recommendation.

### What exists today

| Surface | What it does | Source | File |
|---|---|---|---|
| `MasteryPanel` on `/progress` | Shows 4-state mastery (studied/learning/stale/unseen) per skill, grouped by 6 kinds (concept, endgame, mate_pattern, opening, trap_set, coached_play). Includes evidence modal ("the coach credited you because of THIS move") and a "I don't really get this" demote button. | `GET /api/engine2/mastery-summary` → `coach_memory.learning.skills` (the engine2 SkillProgress table). Populated by **skill drills + lesson completions**. | [`frontend/src/components/coach/MasteryPanel.jsx`](../frontend/src/components/coach/MasteryPanel.jsx) (~520 lines) |
| `MasteryPanel` evidence modal | Per-skill audit trail with rendered chess positions ("we credited you because of this move in this game"). Demote button drops the skill back to learning. | `GET /api/engine2/skill-evidence/{skill_id}` + `POST /api/engine2/skill-demote` | same |
| `/coach/concepts/acknowledged` endpoint | Returns concepts the user has acknowledged from `user_concept_understanding`. Not currently rendered on Progress. | `user_concept_understanding` table. Populated by the central caption pipeline + game-analysis auto-mastery hook. | [`backend/routes/coach.py`](../backend/routes/coach.py) line 1237 |
| `/coach/concepts/mastery-detail` endpoint | (Shipped 2026-06-05) Returns each `user_concept_understanding` row with the PWC Mastery Gate's verdict (mastered/slipping/learning/unseen). Not currently rendered on Progress. | `user_concept_understanding` + `pwc_skill_gate.get_concept_mastery_state()` | [`backend/routes/coach.py`](../backend/routes/coach.py) (newer block) |

### The mismatch (this is the actual product problem)

**Two parallel mastery systems exist and don't acknowledge each other.**

| | engine2 SkillProgress | user_concept_understanding |
|---|---|---|
| **Populated by** | Skill drills, lesson completions | Real-game outcomes (analysis hook) |
| **Signal strength** | Completion = "did the drill right once" | Application = "stopped making this mistake across N games" |
| **Concept namespace** | `endgame_rule_of_square`, `defend_fried_liver`, `mate_kq_vs_k` (~12 skills) | `TAC_HANGING_PIECE`, `END_PASSED_PAWN`, `OP_F2_F7_STRIKE`, `DEF_WALK_KING` (~100+ concepts from the central pipeline) |
| **Has evidence modal** | Yes (per-move audit trail) | No (could be built — `last_evaluated_game_id` is on the row) |
| **Has drill CTA** | Yes (8 skills have detectors) | No |
| **Has demote button** | Yes | No |
| **Read by PWC gate** | No | **Yes — the gate just shipped reads this table** |
| **Read by UI** | **Yes — MasteryPanel** | No (until this scope) |

The gap is real: **the table the gate reads is invisible from the UI; the table the UI shows isn't what the gate reads.**

### Why my earlier "just swap the source" recommendation was wrong

I said yesterday: "EXTEND — swap MasteryPanel's data source." That ignored the namespace mismatch. Swapping MasteryPanel from engine2 to user_concept_understanding would:
- Lose the evidence modal (no per-move audit trail in the new namespace)
- Lose the demote button (no demote endpoint for concept_understanding)
- Lose the drill CTA (8 skills have detectors; concepts don't)
- Surface ~10x more rows (12 skills vs 100+ concepts), drowning the page

Real EXTEND would require rebuilding evidence/demote/drill against the new namespace — that's a multi-week effort, not "~50 lines."

### Decision: PARALLEL (with planned deprecation path)

Add a new section "In-game concept mastery" on `/progress`, BELOW the existing MasteryPanel, reading `/coach/concepts/mastery-detail`. Keep MasteryPanel unchanged.

**Why PARALLEL won the audit:**
- EXTEND (swap source) loses too much — features keyed on engine2 IDs would need redoing
- REPLACE leaves engine2 SkillProgress data orphaned (12 skills with drill detectors)
- MERGE (join-by-concept) is the right end state but the engine2 ↔ concept namespace isn't mapped — that's a separate problem
- PARALLEL is the additive move at small N (memory rule: subtractive wins at scale, additive at ~50 users)

**Long-term path:** when concept_understanding gains evidence + demote + drill, MasteryPanel becomes a strict subset and gets retired. The PARALLEL section IS the future MasteryPanel; we just don't have feature parity yet.

---

## 1. What it is

A new "In-game concept mastery" section on the Progress page that shows what the *PWC Mastery Gate* considers mastered, slipping, or still being learned — based on real-game outcomes, not drill completions.

The existing "Skills · what you've studied" section (drill-based) stays untouched. The new section pairs with it: drills tell you what you've *practiced*, this section tells you what you've *actually stopped getting wrong in your games*.

This is the first surface where the user can see what the coach thinks about their real play. It also makes the gate's decisions inspectable from the UI side — if a coaching message disappears, the user can verify "yes, the coach thinks I've mastered that."

---

## 2. What the user sees

A new section on `/progress`, below the existing MasteryPanel:

```
+---------------------------------------------------------------+
| IN-GAME CONCEPT MASTERY            12 mastered · 4 slipping   |
+---------------------------------------------------------------+
|                                                               |
|   MASTERED — coach stays quiet on these                       |
|   ✓  Walk the king to safety           18 clean games · 1 slip|
|   ✓  Loose piece on the board          14 clean games · 3 slip|
|   ✓  Passed pawns must be pushed       12 clean games · 0 slip|
|   [+ 9 more, collapsed]                                       |
|                                                               |
|   SLIPPING — coach gives a quick reminder                     |
|   !  Trade defenders, keep attackers   was mastered, slipped 8|
|   !  Strike on f7 / f2                 was mastered, slipped 6|
|   [+ 2 more]                                                  |
|                                                               |
|   STILL LEARNING — coach gives full guidance                  |
|   ○  What changed after the move?      29 violations          |
|   ○  Checks, captures, threats first   17 violations          |
|   [+ 14 more, collapsed]                                      |
|                                                               |
+---------------------------------------------------------------+
```

**Hierarchy:**
1. **Section title + summary counts** — at a glance the user sees totals
2. **3 mastery tiers** — mastered (coach silenced) / slipping (downgraded) / learning (full coaching). The relationship to gate behavior is explicit.
3. **Plain-language concept names** — same labels the central pipeline uses (e.g. `TAC_HANGING_PIECE` renders as "Loose piece on the board") via `caption_principles.PRINCIPLES_BY_ID[id].name`. Never the raw `TAC_*` ID.
4. **Meta line** — number of clean games / slip count / violations, depending on state
5. **Per-tier collapse** — only top 5 of each tier shown by default; rest behind "+ N more"

**Not in the mockup (intentional):**
- Per-row evidence modal (would need new endpoint + per-move drill-down on `user_concept_understanding`)
- Per-row demote button (same — needs a `/coach/concepts/demote` endpoint)
- Per-row drill CTA (no concept-keyed puzzle pool exists)

These are V2. V1 is a read-only transparency surface.

---

## 3. In scope (V1)

- New section on `/progress`, rendered BELOW the existing MasteryPanel
- Reads `GET /api/coach/concepts/mastery-detail` (already shipped 2026-06-05)
- Three tier groups: mastered, slipping, learning. Unseen concepts NOT rendered (would be noise)
- Per-row: human-name (from `PRINCIPLES_BY_ID[id].name`), counts, recency text
- Per-tier collapse: top 5 by `clean_games_total` desc, "Show all" expands
- Summary counts in the section header (matches the API's `summary` object)
- Empty state copy when the user has no rows ("As you play, the coach will track what you've mastered.")
- Loading + error states

---

## 4. Explicitly out of scope (V1)

- **Evidence modal for in-game concepts** — needs a new endpoint that joins `user_concept_understanding` ↔ `game_analyses.decryption_v5_data` to surface the specific moves. V2.
- **Demote button for in-game concepts** — `/coach/concepts/demote` doesn't exist. V2.
- **Drill CTA per concept** — no concept-keyed puzzle pool exists; community_puzzles is cognitive_gap-keyed. V2 needs a concept→puzzle mapping.
- **Removing or modifying MasteryPanel** — explicitly preserved. The two sections coexist. Deprecation is a later decision once concept mastery has feature parity.
- **Merging engine2 ↔ concept_understanding** — they have different namespaces (~12 skills vs ~100+ concepts) and no clean mapping. Out of scope; the PARALLEL section sidesteps it.
- **Theme labels per row** (`undefended-piece-capture`-style tags) — 10-12 deterministic rules don't exist yet. Same out-of-scope item as in the UnifiedProgress v2 scope; the rules unblock both.
- **Sort other than `clean_games_total` desc within tier** — no per-row controls.
- **Slipping threshold tuning UI** — `SLIPPING_N_GAMES = 10` is locked in code; not user-tunable in V1.
- **A11y refinements** beyond what the section inherits from Layout.jsx (no new focus traps, no new keyboard shortcuts).

---

## 5. Success criteria

**Primary:** the user can find any concept the PWC Mastery Gate would SUPPRESS for them, **within 30 seconds of landing on `/progress`** (no scroll past one fold; named-tier groups make scanning fast).

This is a UX-discoverability criterion, not a CTR metric, because the section is a transparency surface. The "did this work?" question is "could the user FIND what they wanted?" not "did they click something?"

**Secondary tracked (no targets in V1, just observed):**
- Section visit rate per user per week (does anyone scroll to it?)
- Expand-collapse interactions (does the "+ N more" actually get used?)
- Time between PWC suppression event and user opening Progress page (proxy for "did suppression confuse them into checking?")

**Explicitly NOT a success metric:**
- "Users say it feels useful" (subjective)
- "Reduces support questions" (no support channel; not measurable)

---

## 6. Open questions

### Q1. Where exactly does the section render — above or below MasteryPanel?

- **Why unresolved:** trade-off between freshness (newest signal first — argues for above) and continuity (existing users land on the familiar MasteryPanel — argues for below).
- **Unblocking step:** Mohit's call after seeing a side-by-side preview, or default to BELOW.

### Q2. What's the empty-state policy for a user with zero `user_concept_understanding` rows?

A brand-new user has no rows yet. The section can either hide entirely OR show an empty-state card.

- **Why unresolved:** subtractive-at-small-N argues "show the card so new users see the system exists"; "no clutter" argues "hide until there's something."
- **Unblocking step:** ship with the empty-state card (additive) by default; observe.

### Q3. Should we cap the total rows rendered to prevent runaway lists?

Some users will have 50+ concepts in `learning` state after the backfill. The collapse helps, but a hard cap might be cleaner.

- **Why unresolved:** real distribution unknown — could be 5-150 concepts/user.
- **Unblocking step:** measure `user_concept_understanding` row count per user in production. If p95 > 30, add a cap; if not, defer.

### Q4. Should the section header link to a "/concepts/all" page for the full list?

In case a user with 80 concepts wants to drill into one specific one without scrolling.

- **Why unresolved:** building a /concepts/all page is V2 effort.
- **Unblocking step:** default NO for V1. Collapse handles the long tail.

---

## 7. Pre-code requirements

- [ ] **Mongo on port 27018 reachable** for prod read-back when the section is deployed
- [ ] **`PRINCIPLES_BY_ID` covers all concept IDs the API returns** — if `user_concept_understanding` has IDs not in the principle catalog, the row needs a fallback label. Verify by grepping distinct concept_ids in prod data vs catalog ids.
- [ ] **Q1 decision** — above or below MasteryPanel
- [ ] **Q2 decision** — empty-state card or hide section
- [ ] **Q3 measurement** — distribution of concepts per user; pick cap if p95 > 30
- [ ] **Visual tier styling** — emerald (mastered, matches MasteryPanel's "studied"), amber (slipping, matches "stale"), violet (learning, matches MasteryPanel's "learning"). Match the existing color language so the two sections feel sibling, not duplicate.
- [ ] **Mohit explicit signoff** on this scope doc

After all gates pass: `/audit-pre-code` runs as final check, then implementation begins.

---

## Appendix A — what gets built (descriptive, not part of scope contract)

**Frontend (~150 lines):**
- `frontend/src/components/coach/InGameMasteryPanel.jsx` — new sibling component to MasteryPanel
- Mounted in `frontend/src/pages/UnifiedProgress.jsx` below the existing `<MasteryPanel />` (or above, per Q1)
- Fetches `${API}/coach/concepts/mastery-detail` once on mount
- Uses `PRINCIPLES_BY_ID` for human labels — exposed via a new small endpoint OR by inlining the catalog in the frontend bundle (Q5 below)

**Backend (small):**
- Maybe: `GET /api/coach/principles-catalog` exposing `[{id, name}]` so the frontend doesn't need to ship the catalog. (Decide during build: if catalog < 5KB, inline; else endpoint.)
- The mastery-detail endpoint exists; no other backend work for V1.

**No new collection. No new env flag. No new feature flag.**

This appendix is descriptive. Sections 0–7 are the contract.
