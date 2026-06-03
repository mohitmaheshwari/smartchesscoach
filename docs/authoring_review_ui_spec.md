# Authoring Review UI — Spec

**Status:** DRAFT v1 — awaiting Mohit sign-off.
**Version:** v1 (2026-06-03).
**Scope:** medium frontend build, ~1 day to ship.

---

## 1. The problem

Parth submits authoring rewrites via the flag-move dialog (`is_authoring_submission=true` on `move_feedback` documents). 158 such submissions sit in the queue today; 73 passed today's strict-gate auto-audit and are being applied via `authoring_apply_safe_subset.py`. The remaining **85** require human judgment because they:

- Have no FEN (7) — can't be verified
- Reference the wrong move (41) — Parth's caption talks about a move that isn't the one being captioned
- Lack material content (41) — same length or shorter than the original
- Are too vague on severe positions (28) — no concrete squares/pieces/move names
- Have junk formatting (6) — dot-separators, underscore runs, ">>>" markers
- Contain jargon (3) — Parth used `outpost` / `fianchetto` / etc.
- Are hollow (1) — "you're on track to checkmate"

Today there's no UI to review these one-by-one. The existing admin queue (`/admin` → Feedback) shows them in a flat list and doesn't surface the comparison Parth's reviewer needs: **original caption | Parth's proposal | engine truth**, side-by-side, with approve/edit/reject buttons.

And: Parth keeps submitting. Without a review UI, every new submission joins the pile. We'd be back here in two weeks.

---

## 2. The shape

A dedicated `/admin/authoring-review` route. Each item shows:

```
┌──────────────────────────────────────────────────────────────────┐
│ fb_f62567c759f9 · game_692ab776c5b1 · m22 Qe7 [blunder, cp=124] │
├──────────────────────────────────────────────────────────────────┤
│ Position  [mini-board rendered from fen]                         │
│ Engine:   best=Be7  cognitive_gap=tactical_oversight             │
│                                                                  │
│ ORIGINAL caption                  │ PARTH's suggestion           │
│ "Qe7 is an inaccuracy. Qe8 was    │ "Qe7 has no good follow-up.  │
│  better. The d-file is open..."   │  c5 pawn is targeted but..." │
│                                                                  │
│ What went wrong (Parth's note): "."                              │
│                                                                  │
│ Auto-gate verdict: REJECT (too-vague-on-severe-position)         │
│                                                                  │
│ [ Approve ]  [ Edit & Approve ]  [ Reject ]  [ Skip → next ]    │
└──────────────────────────────────────────────────────────────────┘
```

Hotkeys: `a` approve, `r` reject, `s` skip, `e` open editor.

Pagination: one item per screen; arrows + auto-advance after action. Bottom bar shows `47 / 158` progress.

---

## 3. Schema / files touched

### Backend (extend [routes/admin.py](backend/routes/admin.py))

- `GET /api/admin/authoring/queue` — paginated list of pending authoring submissions, with each item joined to the latest auto-gate verdict (`authoring_safe_subset.json` snapshot if present)
- `POST /api/admin/authoring/{feedback_id}/approve` — body: `{caption: optional override text}`. Inserts/updates `authored_caption_overrides`, marks the feedback `valid`, records reviewer.
- `POST /api/admin/authoring/{feedback_id}/reject` — body: `{admin_note: str}`. Marks the feedback `dismissed`.
- `POST /api/admin/authoring/{feedback_id}/skip` — marks `status=acknowledged` (no action taken; comes back next pass).

### New frontend page ([frontend/src/pages/AdminAuthoringReview.jsx](frontend/src/pages/AdminAuthoringReview.jsx))

- Loads the queue once on mount
- Renders one card at a time
- Hotkey handlers
- Side-by-side compare with original highlighted-by-removal vs Parth's highlighted-by-addition (diff view, optional)
- Mini-board from FEN (reuses `LichessBoard` component, viewOnly=true)
- Inline editor on "Edit & Approve" — `<textarea>` prefilled with Parth's text, submit triggers approve with the edited text

### Routing ([frontend/src/App.js](frontend/src/App.js))

Add `<Route path="/admin/authoring-review" element={<AdminAuthoringReview />} />`. Gate behind admin auth (existing `ProtectedRoute` + admin role check).

---

## 4. New facts / data the system needs

No new data — the existing `move_feedback` documents already have everything (`fen`, `move_san`, `coaching_text`, `suggested_caption`, `inaccuracy_reason`, `diagnostics`). The queue endpoint just JOINs the auto-gate verdict from the snapshot file if present.

---

## 5. Gating — preventing the "rubber-stamp" trap

The danger with a review UI: Mohit or Parth burns through 158 items in 20 minutes, smashing "approve" without reading. Three gates:

1. **Auto-gate verdict shown prominently** with the reason. Approve while the verdict says REJECT requires a second confirmation click ("you're approving an item the auto-gate flagged — sure?").
2. **Engine-truth panel** always visible — best move, cp_loss, cognitive_gap. If Parth's text contradicts the engine (says "you're winning" on cp_loss=300), the panel turns red as a visual warning.
3. **Item count throttle** — after 30 approvals in a row with no rejections, the UI inserts a "you've approved a lot — take a break?" check. Prevents fatigue-rubber-stamp.

---

## 6. Test strategy

1. **Boundary cases**: feedback with no FEN, with empty suggested_caption, with `inaccuracy_reason="."` only.
2. **Approval flow**: approve → confirm `authored_caption_overrides` upserted + `move_feedback.status=valid` + reviewer/timestamp recorded.
3. **Edit flow**: edit text in textarea → confirm the EDITED text lands in the override, not Parth's original.
4. **Reject flow**: reject → confirm `status=dismissed`, no override row.
5. **Hotkey flow**: rapid `a a a r a` → confirm 4 approves + 1 reject, advance correct.
6. **Two reviewers in parallel** (unlikely but possible): version-check / locking pattern so simultaneous approvals don't dupe-write.

---

## 7. Risk + rollback

**Blast radius**: low — affects only the admin route. No user-facing changes from the UI itself; the override collection IT writes to is the change that affects users (and that already exists with 73 entries from today's strict-gate apply).

**Failure modes:**
- Bad approval → admin override surfaces a broken caption to users on that specific position. Fix: delete the override row.
- Empty queue endpoint → page shows "0 items" with no error.
- Two admins approving same item simultaneously → upsert handles the dedupe at the DB layer.

**Rollback**: feature flag `ADMIN_AUTHORING_REVIEW_UI_ENABLED` on the frontend route gate. If the UI behaves badly, set false → route 404s. The overrides collection stays in place independently.

---

## 8. What this spec does NOT cover

- **Bulk approval** — "approve all REJECTs" type macros. Out of scope; gating that hard would defeat the per-item review purpose.
- **Cross-game pattern detection** — "Parth has 5 submissions on the same fork pattern; promote to R12 predicate." Filed for `/author-r12-predicate` skill follow-up.
- **Authoring submission tooling** — the workflow Parth uses to SUBMIT (the flag-move dialog) is unchanged. If that's where the `move_mismatch` bug originates, it's a separate fix.
- **Mobile responsive** — admin UI is desktop-only; not designing for mobile.

---

## 9. Implementation order

1. **Backend endpoints** in `routes/admin.py` (~half-day):
   - `GET /api/admin/authoring/queue`
   - `POST /api/admin/authoring/{id}/approve|reject|skip`
   - Auth + admin role check on all three
2. **Frontend page** `AdminAuthoringReview.jsx` (~half-day):
   - One-item-at-a-time card layout
   - Mini-board, side-by-side compare, hotkeys
   - Edit modal for "Edit & Approve" flow
3. **Routing + nav link** from existing AdminDashboard (~30 min)
4. **End-to-end test** on a clean checkout — walk 5 items, confirm DB state, confirm overrides land
5. **Ship with the gate disabled by default** (`ADMIN_AUTHORING_REVIEW_UI_ENABLED=false`); flip on for Mohit + Parth first
6. **Drain the 85-item backlog** in one session
7. **Default on** once stable

No "10% rollout" needed — this is an admin tool, not user-facing.

---

## 10. Decisions / Open questions for Mohit

1. **Reviewer role.** Who's clicking through? Mohit alone, Mohit + Parth, or a broader admin group? If broader, do we need a "reviewed by user X" field separate from "submitted by"?
2. **Diff display.** Show Parth's text as raw, OR with a word-level diff highlighting what changed vs original? Diff is more useful but takes UI work. My recommendation: raw for v1, diff for v2.
3. **Mini-board orientation.** Always white-on-bottom, or oriented based on who's moving? Recommendation: oriented based on `user_color` from the feedback's game (matches how the user saw the position).
4. **Hotkey set.** Approve/Reject/Skip/Edit only, or add "open game in Lab" to verify position? Recommendation: add `g` for "open game" — Parth will want to verify on the actual game viewer.
5. **Cap on per-session work.** "After 30 approves in a row without a reject, ask if you're rubber-stamping" — is 30 the right cap? Or 50?
