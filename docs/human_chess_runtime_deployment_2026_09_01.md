# Human Chess Runtime — Deployment Handoff

This release is default-off. Deploying the image changes no user behavior until the flags are enabled.

## Artifact layout on the host

Set `HUMAN_CHESS_RUNTIME_DIR` to a directory with this read-only layout:

```text
bin/fathom
models/rapid_model.pt
models/otter-0.2.0-eb8dc98b.safetensors
syzygy/*.rtbw
syzygy/*.rtbz
```

The container mounts it at `/opt/chessguru/human_chess`. No request downloads models or tablebases.

## Required provenance values

Set the actual Fathom binary SHA-256 as `FATHOM_BINARY_SHA256`. Set a stable bundle label as `SYZYGY_TABLEBASE_BUNDLE_ID`, the configured maximum as `SYZYGY_MAX_MEN`, and the canonical filename-to-file-hash digest as `SYZYGY_TABLEBASE_MANIFEST_SHA256`. Generate the last value inside the built container with `python scripts/verify_human_chess_runtime.py --compute-syzygy-manifest /opt/chessguru/human_chess/syzygy`.

The runtime requires Maia-2 `0.11.0` Rapid weights (`65aae8465eed5e65df66a24ea7370715579f9e5435098d06fe18bdb1e267e997`) and Otter `0.2.0` weights (`53dc65068c88e298de5abe3dfd93141ea1e3bf795961a686f239b5574804757d`). It hashes the mounted files itself and rejects package/model drift.

## Developer verification already completed

On 2026-09-01 the production adapter was executed against those two audited local weight files, not mocks. Maia-2 returned 20 legal moves through the no-history fallback; Otter returned 20 legal moves with `history_mode=verified`. Both provider identities, package families, artifact hashes, probability contracts, and legal moves passed. The consolidated deterministic gate is 210 passing tests.

The Linux Fathom binary and Syzygy bundle are deliberately not committed, so exact-engine execution must still pass inside the built production container. The local model check does not replace that deployment gate or the combined-image memory/latency observation.

## Safe sequence

1. Build and deploy with all six new flags false.
2. Set the provenance values and enable `EXACT_ENDGAME_ENGINE_ENABLED=true` plus `HUMAN_POLICY_EVIDENCE_ENABLED=true` in the container used for verification.
3. Inside that exact backend image, run `python scripts/verify_human_chess_runtime.py --require-exact --require-human`.
4. Require JSON `ok: true`, `exact.complete_legal_partition: true`, Maia provider `maia2`, Otter provider `otter`, and Otter history mode `verified`.
5. Enable `PUZZLE_HUMAN_DIFFICULTY_SHADOW_ENABLED=true`; it remains metadata-only. Keep `HUMAN_CHESS_ANALYSIS_ENRICHMENT_ENABLED=false` during the one-account validation so scaled analysis workers do not each load both models. The code path is complete, but broad background enrichment needs an observed memory/latency envelope first.
6. For Mohit's enrolled validation account only, enable `EXACT_ENDGAME_REVIEW_ENABLED=true` and `PWC_HUMAN_POLICY_OPPONENT_ENABLED=true`.
7. Reopen selected reviews and run manual Play-with-Coach validation. Do not enable a broad rollout from this commit.

Rollback is the six flags to false plus a backend restart. Stored evidence is additive and cannot alter mastery, admission, answers, or historical Stockfish truth.
