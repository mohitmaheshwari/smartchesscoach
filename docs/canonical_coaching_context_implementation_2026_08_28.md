# Canonical Coaching Context — Implementation Record

**Implemented:** 2026-08-28  
**Runtime status:** default-off  
**Production rollout:** not authorized

## What shipped in code

- `focus_bridge` now builds and validates `coaching_context.v1` from the
  existing `user_active_focus` authority.
- Primary and supporting focuses require strict Plan authorization. Global
  detector-gate permissiveness cannot promote an unknown detector into this
  contract.
- V1 exposes at most one contextual supporting focus, per the production-data
  lock.
- Review attaches only exact, Plan-authorized move observations owned by the
  requested user and game. No matching observation is explicitly not proof of
  improvement.
- Training receives one assignment carrying the same focus ID, instruction ID
  and literal instruction text.
- Coach Play stores an immutable server-side context snapshot. Canonical
  sessions suppress legacy focus fallbacks and derive their mission from the
  canonical primary focus.
- Coach Mode may display the exact canonical instruction. Play Mode hides live
  context, mission, focus, goal and greeting fields from the browser while the
  database retains the snapshot for postgame analysis.
- Home, routed Review, current-focus Training and Coach Play have default-off
  renderers. Explicit pattern training remains a requested elective rather than
  being mislabeled as the diagnosed assignment.
- Flag-off and role-ineligible users retain the legacy paths.

## Verification evidence

- Backend coaching-context and analytics registry: 16 tests passed.
- Isolated-fixture safety and shape: 4 tests passed. The seeder refuses every
  database name except `chessguru_validation`, tags every mutable record, and
  rejects identity, credential and payment fields before I/O.
- Current-worktree contract verification against real Mongo queries in the
  isolated database: 9/9 passed, including stable cross-surface focus identity,
  exact Review matching, no-opportunity restraint, Shadow fail-closed behavior,
  missing-instruction restraint, Training assignment consistency, and Coach vs
  Play visibility isolation.
- Frontend canonical renderers/projection: 9 tests passed.
- Edited backend modules passed `py_compile`.
- Home, Review, Training, Coach Play and shared frontend adapters passed direct
  Babel parsing.
- Scoped `git diff --check` passed; only repository line-ending warnings were
  emitted.

The repository-wide HTTP E2E suite could not run because no backend was running
locally; it failed at its first TCP connection before assertions. The CRA
production build entered optimization but emitted no result for several
minutes and was terminated. These checks are therefore unverified, not passed.
An isolated local browser-backend attempt also stopped before binding a port
because the host Python environment lacks the repository dependency `bcrypt`.
No page assertion ran. The temporary backend and SSH tunnel were terminated and
their generated logs were removed. A second attempt used a disposable temp
package target, but the repository's full pinned dependency installation did
not finish inside the bounded validation window; its exact pip process and
partial temp directory were terminated and removed. Browser validation remains
a staging task.

## Safety state

- `COACHING_CONTEXT_V1_ENABLED` defaults to false.
- `COACHING_CONTEXT_V1_ROLES` defaults to `admin,super_admin`.
- No deployment occurred.
- No production player record was changed.
- The isolated `chessguru_validation` database contains 26 tagged,
  deterministic synthetic fixture records across eight allowlisted
  collections. No player data was copied into it.
- The live backend container was not restarted or modified. Verification ran
  from the current local worktree through a temporary SSH tunnel; the existing
  database credential stayed in memory and was not printed.

## Remaining release work

1. Run the four-surface browser journey against a locally running or staging
   backend with the flag enabled only for Mohit/Parth reviewer accounts.
2. Inspect stored Coach Mode and Play Mode session documents and browser
   payloads to prove snapshot persistence and live-instruction isolation.
3. Run the repository HTTP E2E suite and complete a production frontend build
   in the deployment environment.
4. Record reviewer verdicts before considering any percentage rollout.
