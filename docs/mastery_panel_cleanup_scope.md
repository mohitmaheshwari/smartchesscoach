# Mastery Panel Cleanup — Scope Document

**Status:** AWAITING MOHIT SIGNOFF (2026-06-05)
**Skill applied:** `/scope-driven-development` (with Section 0 existing-surfaces audit)
**Predecessor:** [mastery_panel_data_source_swap_scope.md](mastery_panel_data_source_swap_scope.md) — which shipped the PARALLEL `InGameMasteryPanel` alongside MasteryPanel
**Next skills:** `/lock-via-data` if thresholds emerge → `/audit-pre-code`

---

## 0. Existing surfaces audit

### What exists today

| Surface | Behavior | File |
|---|---|---|
| `MasteryPanel` on `/progress` | Renders all 24 skills from `data/coaching/skill_tree.json`, grouped by 6 kinds, including unseen rows with `Not started` + `Tier 1/2/3` badges + `Study` button | [`frontend/src/components/coach/MasteryPanel.jsx`](../frontend/src/components/coach/MasteryPanel.jsx) |
| `InGameMasteryPanel` on `/progress` | Sibling, shipped 2026-06-05. Shows `user_concept_understanding` rows where the gate would SUPPRESS/DOWNGRADE/SHOW. Auto-hides if zero rows. | [`frontend/src/components/coach/InGameMasteryPanel.jsx`](../frontend/src/components/coach/InGameMasteryPanel.jsx) |
| `/engine2/mastery-summary` | Backend endpoint returning skill_id → {state, days_since_studied, ...}. State derived from `coach_memory.learning.skills` SkillProgress records (drill outcomes). | [`backend/routes/training_advanced.py:3623`](../backend/routes/training_advanced.py) |
| `data/coaching/skill_tree.json` | 24-skill tree definition with kind / label / tier / fixes / content_ref. | repo data file |

### The 24 skills, categorized by whether a real-game signal exists

After full inventory:

**Group A — Has clean central-pipeline concept analog (5 skills):**
| skill_id | label | concept_id |
|---|---|---|
| `coached_development` | Develop your pieces | `OP_FINISH_DEVELOPMENT` |
| `defend_fried_liver` | Defend against Fried Liver | `OP_F2_F7_STRIKE` |
| `endgame_opposition` | The Opposition | `END_OPPOSITION` |
| `endgame_rule_of_square` | Rule of the Square | `END_RULE_OF_SQUARE` |
| `defend_scholars_mate` | Defend against Scholar's Mate | (no precise analog; defer) |

These are the skills where a 165-game player who hasn't done the drill HAS demonstrated the skill in real games. "Not started" is misleading for them.

**Group B — Legitimately curriculum-only (19 skills):**
- Specific opening theory: `opening_london_white`, `opening_caro_kann_black`, `opening_scandinavian_black`, `opening_italian_white`, `opening_italian_black`, `opening_queens_gambit`, `opening_french_black`, `opening_ruy_lopez`, `opening_sicilian_black` (9)
- Specific endgame theory: `endgame_lucena`, `endgame_philidor` (2)
- Specific structural concepts: `concept_iqp`, `concept_prophylaxis`, `concept_minority_attack` (3)
- Trap defense: `trap_set_italian`, `trap_set_caro_kann`, `trap_set_london` (3)
- Mating technique: `mate_kq_vs_k`, `mate_kr_vs_k` (2)

For these, "Not started" is honest — the user genuinely hasn't studied the named technique. Rating doesn't override theoretical curriculum knowledge.

### What's wrong (the embarrassment Mohit caught)

For a 165-game player at the existing rating band:
1. "Develop your pieces — Not started · Study" reads as patronizing — the user develops pieces every game
2. The "Tier 1/2/3" badges on every unseen row are coach-curriculum framing, not user-friendly
3. The `InGameMasteryPanel` (shipped earlier today) shows `OP_FINISH_DEVELOPMENT` as **slipping** — meaning the user is past-mastery on it. MasteryPanel right below shows the same skill as "Not started." Two surfaces, opposite verdicts.

### Decision: EXTEND MasteryPanel with cross-system override

Per `/scope-driven-development` Section 0 four paths:
- **EXTEND** — add a cross-system check: when `unseen` skill_id is in Group A and the mapped concept_id has mastery, override display state. Keep MasteryPanel structure intact.
- PARALLEL was already used for `InGameMasteryPanel`. Adding more parallel surfaces would multiply, not consolidate.
- REPLACE (rip out MasteryPanel) is overscoped tonight — engine2 SkillProgress is the source of drill outcomes, evidence modal, drill CTA. Replacing requires building all of that on `user_concept_understanding` first.
- MERGE-and-collapse-both-panels is the right long-term move but is V2 — needs full feature parity (evidence/demote/drill) on the concept_understanding side first.

EXTEND is the smallest move that delivers Mohit's "permanent fix" requirement: never again should MasteryPanel show a misleading "Not started" for a skill the user has demonstrated.

---

## 1. What it is

MasteryPanel learns to read both mastery signals. For the 5 skills where engine2's drill-based signal and the central pipeline's game-based signal both apply, the panel renders the STRONGER signal. A user who develops their pieces in 165 games never again sees "Develop your pieces — Not started."

In plain English: if you've demonstrated a skill in your actual games, MasteryPanel knows. It still shows the curriculum for skills you haven't engaged with at all (specific opening theory, specific endgame techniques, named mating patterns) — those are honest "explore next" suggestions. But it stops calling you a beginner on fundamentals you obviously have.

---

## 2. What the user sees

**Before (today, what Mohit caught):**
```
Coached play  ·  1 to explore
  Develop your pieces                Not started     [Study]    T0
```

**After this scope ships:**
```
Coached play  ·  1 demonstrated in games
  Develop your pieces                Demonstrated in 153 games    [✓]
                                     Last shown: today
```

The "Demonstrated in N games" copy is derived from `user_concept_understanding.clean_games_total` on the mapped concept (`OP_FINISH_DEVELOPMENT.clean_games_total = 153` in Mohit's data). The drill button changes from "Study" to a checkmark icon — the lesson is still reachable via "why?" (existing evidence modal), but it's not the primary action.

**Skills outside Group A are unchanged.** "Isolated Queen's Pawn play — Not started — T2 — Study" still renders as before because there's no real-game signal for IQP play.

The "Tier 1/2/3" badges remain on Group B rows — they're meaningful curriculum guidance for skills the user actually hasn't learned. They're removed from Group A rows because tier is irrelevant once the user has demonstrated the skill.

---

## 3. In scope (V1)

- New mapping file: `backend/data/coaching/engine2_skill_to_concept_map.json` — 4 entries (Group A minus `defend_scholars_mate` which has no clean analog)
- Extend `/engine2/mastery-summary` to enrich response: for each mapped skill_id, look up `user_concept_understanding` for the concept. If `mastered_at` is set AND survives the slipping check (per `pwc_skill_gate.get_concept_mastery_state` returning `mastered`), override the engine2 state to a new `"demonstrated"` value
- Augment the response with `demonstrated_clean_games` (from the concept row's `clean_games_total`) for "Demonstrated in N games" copy
- MasteryPanel renders the new `demonstrated` state with: ✓ icon (emerald, matches `studied`), "Demonstrated in N games" subtitle, no Study button (replaced with a small "View lesson" link in the existing "why?" location)
- Update summary line to reflect demonstrated count: "X studied, Y demonstrated, Z to explore"

---

## 4. Explicitly out of scope (V1)

- **Rating-based override** ("user is 1500, auto-mark these as known") — no. The override requires actual in-game demonstration via the central pipeline. No rating bypass.
- **Removing the "Tier 1/2/3" badges from Group B** — out of scope; tier is meaningful for unseen curriculum-only skills.
- **Softening chess jargon labels** ("Prophylaxis" → "Preventing opponent's plan") — Mohit's caption-voice rule applies to user-facing prose, not to the chess curriculum's named concepts. These ARE the concept names. Defer to its own discussion.
- **Mapping `defend_scholars_mate`** — no clean central-pipeline analog. If a user has demonstrated Scholar's-Mate defense in their games, the system has no signal. Surfacing it as "Not started" stays accurate.
- **Building `mate_kq_vs_k`/`mate_kr_vs_k` real-game detectors** — would require parsing endgame conversions in `decryption_v5_data`. Out of scope; "Not started" remains honest for these.
- **Merging the two panels into one** — V2 cleanup. The PARALLEL decision from the prior scope stands.
- **Auto-deprecating Group B skills the user has rating-evidence for** — same as the rating-based override item. No bypass without in-game evidence.
- **Custom per-skill copy strings beyond "Demonstrated in N games"** — V1 uses one template.

---

## 5. Success criteria

**Primary:** for every Group A skill on Mohit's account (the 4 mapped skills), MasteryPanel now renders the in-game signal rather than "Not started." Verified by visual inspection on prod after deploy.

This is a UX-correctness criterion, not a usage metric. The bug was a misframing; the success is "the misframing no longer renders."

**Secondary tracked:**
- Number of `demonstrated` overrides per user across the cohort (sanity check the mapping is firing)
- Click rate on the "View lesson" link from demonstrated rows (do users still want the lesson even when they've shown mastery? If yes, maybe keep Study button)

**Not a success metric:** "users say it feels less patronizing." Subjective.

---

## 6. Open questions

### Q1. What if the mapped concept is `slipping`, not `mastered`?

`OP_FINISH_DEVELOPMENT` is currently slipping on Mohit's account (recent violation today). Per the gate: slipping = "coach gives a quick reminder." For MasteryPanel, should slipping override show as "Demonstrated · recent slip" or fall back to "Not started"?

- **Why unresolved:** trade-off between "still show user they have the skill" vs "honest signal that they're backsliding."
- **Unblocking step:** default to "Demonstrated · recent slip" (with amber icon, not emerald). Falling back to "Not started" would be worse than today because the user has demonstrated the skill — just imperfectly recently.

### Q2. Should the existing Study button stay accessible on demonstrated rows?

Even after demonstrating a skill, the user might want to read the lesson — confirmation, review, edge cases not in their games.

- **Why unresolved:** UX preference.
- **Unblocking step:** keep the existing "why?" evidence-modal link visible; add a small "View lesson" link inside the modal. Don't render Study as the primary CTA on demonstrated rows.

### Q3. What about skill rows where engine2 says `studied` and concept_understanding says `slipping`?

The user did the drill, but their actual games show backsliding. MasteryPanel currently shows "Studied". Should it amber-flag those?

- **Why unresolved:** doesn't apply to current Mohit data (he hasn't completed Group A drills), but possible.
- **Unblocking step:** out of scope for V1. Add a follow-up note. Engine2 `studied` wins unless we expand the override logic.

### Q4. Should the empty-state copy change when Group A skills get overridden?

Today the section says "Coached play — 1 to explore". If `coached_development` overrides to `demonstrated`, should the count change to "1 demonstrated" or "0 to explore"?

- **Why unresolved:** small copy choice.
- **Unblocking step:** count demonstrated separately from studied. Section title becomes "X demonstrated · Y to explore."

---

## 7. Pre-code requirements

- [ ] **`engine2_skill_to_concept_map.json` reviewed** — confirm the 4 mappings are correct (Mohit eyeball on the table in Section 0)
- [ ] **Q1 decision** — slipping override copy
- [ ] **Q2 decision** — Study button visibility on demonstrated rows
- [ ] **Q4 decision** — section title count breakdown
- [ ] **Mohit explicit signoff** on this scope document

After all gates pass: `/audit-pre-code` runs as final check, then implementation begins.

---

## Appendix A — what gets built (descriptive, not part of scope contract)

**Backend:**
- New: `backend/data/coaching/engine2_skill_to_concept_map.json` (4 entries, ~200 bytes)
- Modified: `backend/routes/training_advanced.py:engine2_mastery_summary` — joins skill records with concept-understanding mastery for mapped skills; emits `demonstrated` state + `demonstrated_clean_games`

**Frontend:**
- Modified: `frontend/src/components/coach/MasteryPanel.jsx` — new `demonstrated` state rendering (✓ icon, "Demonstrated in N games" meta, no Study button), summary count breakdown
- New small util file may be unnecessary — keep changes in MasteryPanel.jsx

**No new endpoints. No new collections. No new env flags.**

This appendix is descriptive. Sections 0–7 are the contract.
