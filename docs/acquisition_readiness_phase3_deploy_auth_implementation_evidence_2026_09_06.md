# Acquisition Readiness Phase 3 — Deployment Authentication Implementation Evidence

**Date:** 2026-09-06

**Branch:** `codex/acquisition-readiness-program-v1`

**Scope:** `docs/acquisition_readiness_phase3_deploy_auth_precode_audit_2026_09_06.md`

**Status:** SOURCE COMPLETE — independent review and live strict-gate proof pending

## Outcome

The Phase 8 deployment verifier now exercises the Phase 1 web authentication
boundary instead of contradicting it:

- authenticated read, canonical Game Review and every Home → lesson → Review
  → Progress journey request send `session_token` as a cookie;
- none of those requests sends an Authorization header;
- `--session-token` and `DEPLOY_VERIFY_SESSION_TOKEN` are the preferred CLI
  and deployment-secret names;
- `--auth-token` and `DEPLOY_VERIFY_AUTH_TOKEN` remain temporary input aliases
  for the same value during server migration, but the value is still sent only
  as a cookie; and
- `scripts/deploy.sh` requires and forwards only the preferred secret into the
  verifier container after performing the bounded legacy-name fallback.

The mobile-only bearer rule is unchanged. No session is minted, rotated,
printed or persisted by this change.

## Verification evidence

### Phase 1 × Phase 8 integration suite

Command:

```powershell
C:\Users\MIISCO\smartchesscoach\backend\.venv\Scripts\python.exe -m pytest `
  tests/test_verify_deployment.py `
  tests/test_complete_coaching_access.py `
  tests/test_phase8_release_prerequisites.py `
  tests/test_phase8_release_evidence.py `
  tests/test_auth_transport_security.py `
  tests/test_auth_analytics_context.py -q
```

Result: **79 passed, 0 failed**, with two existing dependency/deprecation
warnings.

The new tests capture request arguments for authenticated read, canonical
review and the completed complete-journey branch. They require the exact
`session_token` cookie and reject any Authorization header. The deployment
source test requires the preferred secret to be forwarded and the old secret
not to be forwarded into the container.

### Deployment script syntax

Command:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -n scripts/deploy.sh
```

Result: **exit 0**.

The generic `bash` command first resolved to WSL on this workstation and
failed because `/bin/bash` is absent. That environment error is not counted as
a script failure; the installed Git Bash executable performed the syntax
check successfully.

### CLI migration contract

`verify_deployment.py --help` reports the preferred
`--session-token SESSION_TOKEN` option and the deprecated
`--auth-token SESSION_TOKEN` alias. Static inspection finds no request header
that transmits the configured session as bearer authorization.

## Required proof before closure or deployment

This phase must not be marked live or used to raise a score until:

1. an independent reviewer checks the integration diff against both Phase 1
   and Phase 8 contracts;
2. Claude installs/renames the verifier secret without exposing its value;
3. production's strict deploy run reports PASS for auth, contract and journey
   using the dedicated non-admin fixture;
4. a negative live test proves the same ordinary session fails when sent as a
   bearer header and succeeds as a cookie; and
5. the temporary legacy secret alias receives a dated removal decision after
   the server configuration has migrated.

No production write, push, deployment, enrollment or score change was
performed in this phase.
