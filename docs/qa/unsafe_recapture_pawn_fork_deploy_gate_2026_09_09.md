# QA Gate — Verified unsafe-recapture explanation and board replay

**Repo:** smartchesscoach

**Branch:** `codex/unsafe-recapture-pawn-fork-v1`

**Base:** `origin/working-code` at `3f23a213`

**Engineer:** Codex

**Date:** 2026-09-09

**Mode:** Production

## Component(s) touched

| Component | Files / paths touched |
|---|---|
| Deterministic chess proof | `backend/services/caption_facts.py`, `backend/services/pattern_catalog.py` |
| Central coaching decision | `backend/services/caption_pipeline.py`, `backend/data/captions/R12_blunder.json` |
| Stored V5 review projection | `backend/services/game_decryption_v5_service.py` |
| Game Review replay UX | `frontend/src/components/GameDecryptionV5.jsx` |

## Layer 1 — Unit tests

- [x] The Re1 case is locked from legal board state through rendered caption and exact six-move replay payload.
- [x] The alternate real resolution is covered.
- [x] Near misses, malformed stored lines, illegal SAN, wrong recapture, insufficient horizon, and unproved generic opponent lines abstain.
- [x] No gameplay LLM path was introduced.
- [x] The feature and new upstream caption/pattern suites pass after rebase.
- [x] The seven wider-suite failures were reproduced exactly on the clean base.

Evidence:

```text
feature + current upstream suites: 48 passed
feature + newest upstream check:    44 passed
wider selected caption gate:       200 passed, 7 failed
clean origin/working-code base:      82 passed, 7 failed
failure identity:                    exact match; zero new failures
caption JSON parse:                  passed
changed Python compile:              passed
git diff --check:                    passed
```

## Layer 2 — Integration tests

- [x] The central `MoveTeachingDecision` carries the exact SAN line.
- [x] V5 serializes that line only for the fully proved family.
- [x] The existing Game Review component consumes the explicit line and calls board `playVariation` from `fen_before`.
- [x] The rebased frontend production build exits 0.

Build evidence:

```text
Creating an optimized production build...
Compiled with warnings.
exit code: 0
```

Warnings are the repository's existing `chess.ts` source-map and large-bundle warnings.

## Layer 3 — End-to-end production smoke test

Pending deployment. Claude must attach live evidence for all of the following:

- [ ] Backend and frontend images both build with exit code 0.
- [ ] `/api/health` returns 200 from the new release.
- [ ] Opening the affected game regenerates stored V5 data to version 149.
- [ ] Re1 renders the short explanation, not the previous immediate-capture caption.
- [ ] **Show me on the board** replays `Re1 Nxe4 Rxe4 d5 Bxd5 Qxd5` in order.
- [ ] The replay panel says **Why it works** and **Back to game** restores the game position.
- [ ] An unrelated opponent inaccuracy without typed proof receives no new replay payload.

## Engineer's self-declaration

The local and clean-base evidence above reflects commands actually run. The production E2E boxes remain deliberately unchecked until Claude deploys and captures live evidence.

**Signed:** Codex

**Date:** 2026-09-09

## Mohit's gate

**Verdict:** ☐ Approved   ☐ Approved with follow-up   ☐ Rejected — needs rework

**Notes:**
