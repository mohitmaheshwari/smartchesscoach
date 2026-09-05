#!/usr/bin/env bash
#
# The one deploy path for chessguru.ai. Run ON THE SERVER from the repo root.
#
#   ./scripts/deploy.sh              # backend + frontend
#   ./scripts/deploy.sh backend      # backend only
#   ./scripts/deploy.sh frontend     # frontend only
#
# WHY THIS EXISTS
#
# Three separate deploys in one day reported success while shipping the wrong
# thing, each in a different way:
#
#   1. the backend image build failed on a missing gcc; the script carried on,
#      published the frontend, and left the backend running the OLD image while
#      every log line said the deploy had worked
#   2. `docker compose run frontend-builder` was called without `--build`, so a
#      stale builder image re-emitted a byte-identical bundle and the new code
#      never reached users
#   3. `git pull` failed on a GitHub connection timeout; the rebuild ran on
#      stale code and still exited 0
#
# All three were caught by hand afterwards. None would have been caught by the
# script. So this script asserts, at every stage, that the thing it intended to
# happen actually happened -- and stops on the first failure.
set -euo pipefail

TARGET="${1:-all}"
BRANCH="${DEPLOY_BRANCH:-working-code}"
DOCROOT="${DEPLOY_DOCROOT:-/var/www/chessguru.ai}"
HEALTH_URL="${DEPLOY_HEALTH_URL:-https://chessguru.ai/api/health}"
VERIFY_BASE_URL="${DEPLOY_VERIFY_BASE_URL:-https://chessguru.ai}"

step()  { printf '\n=== %s\n' "$1"; }
ok()    { printf '    OK   %s\n' "$1"; }
die()   { printf '    FAIL %s\n' "$1" >&2; exit 1; }

# --- 1. working tree must be clean, or a pull will silently not apply -------
step "pre-flight"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  git status --short | head -10
  die "uncommitted tracked changes on the server; refusing to deploy over them"
fi
ok "worktree clean"

BEFORE_HEAD="$(git rev-parse HEAD)"

# --- 2. pull, and PROVE it moved -------------------------------------------
step "pull $BRANCH"
git fetch origin --quiet || die "git fetch failed (network?); nothing was deployed"
REMOTE_HEAD="$(git rev-parse "origin/$BRANCH")"
git merge --ff-only "origin/$BRANCH" >/dev/null || die "fast-forward failed; server has diverged from $BRANCH"

HEAD_SHA="$(git rev-parse HEAD)"
[ "$HEAD_SHA" = "$REMOTE_HEAD" ] || die "HEAD ($HEAD_SHA) != origin/$BRANCH ($REMOTE_HEAD) after pull"
ok "at $(git log -1 --format='%h %s' | cut -c1-64)"
[ "$HEAD_SHA" = "$BEFORE_HEAD" ] && printf '    note  already at this commit; rebuilding anyway\n'

export GIT_COMMIT="$HEAD_SHA"

# --- 3. backend: build and run must BOTH succeed ---------------------------
if [ "$TARGET" = "all" ] || [ "$TARGET" = "backend" ]; then
  step "backend image"
  docker compose build backend analysis-worker \
    || die "backend image build failed; backend still on the previous image"
  ok "image built"

  docker compose up -d backend analysis-worker \
    || die "backend containers failed to start"

  step "backend running the intended commit"
  for _ in $(seq 1 30); do
    RUNNING="$(docker exec chess-coach-backend printenv GIT_COMMIT 2>/dev/null || true)"
    [ -n "$RUNNING" ] && break
    sleep 2
  done
  [ "$RUNNING" = "$HEAD_SHA" ] \
    || die "container GIT_COMMIT=${RUNNING:-unset} but repo HEAD=$HEAD_SHA -- a stale image is running"
  ok "container GIT_COMMIT matches HEAD"
fi

# --- 4. frontend: --build is mandatory, and the bundle must actually change -
if [ "$TARGET" = "all" ] || [ "$TARGET" = "frontend" ]; then
  step "frontend bundle"
  BUNDLE_BEFORE="$(grep -oE 'main\.[a-f0-9]+\.js' "$DOCROOT/index.html" 2>/dev/null | head -1 || true)"

  # `build` is NOT optional: without it a stale builder image re-emits the old
  # bundle and the deploy looks clean while shipping nothing.
  docker compose build frontend-builder || die "frontend builder image failed to build"
  docker compose run --rm frontend-builder || die "frontend build failed; docroot untouched"

  BUNDLE_AFTER="$(grep -oE 'main\.[a-f0-9]+\.js' "$DOCROOT/index.html" 2>/dev/null | head -1 || true)"
  [ -n "$BUNDLE_AFTER" ] || die "no bundle in $DOCROOT/index.html after build"
  if [ "$BUNDLE_BEFORE" = "$BUNDLE_AFTER" ]; then
    # Legitimate when a commit changes no frontend code -- but it is also
    # exactly what a stale builder looks like, so say so out loud.
    printf '    note  bundle unchanged (%s). Expected only if this commit\n' "$BUNDLE_AFTER"
    printf '          touched no frontend source.\n'
  else
    ok "bundle $BUNDLE_BEFORE -> $BUNDLE_AFTER"
  fi
fi

# --- 5. the site must actually answer --------------------------------------
step "health"
for _ in $(seq 1 30); do
  CODE="$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" || true)"
  [ "$CODE" = "200" ] && break
  sleep 5
done
[ "$CODE" = "200" ] || die "$HEALTH_URL returned $CODE"
ok "$HEALTH_URL 200"

# --- 6. prove a non-admin can reach the complete coaching journey ----------
step "strict deployment and non-admin journey verification"

# The gate's secrets live in .env, which is gitignored and never committed.
# Read them literally instead of sourcing the file: the fixture value is
# JSON containing braces and quotes, and `. ./.env` would let the shell
# brace-expand it and hand the verifier a mangled fixture.
if [ -f .env ]; then
  for SECRET_KEY in \
    DEPLOY_VERIFY_AUTH_TOKEN \
    DEPLOY_VERIFY_GAME_ID \
    PHASE8_VERIFICATION_FIXTURE_JSON \
    DEPLOY_VERIFY_BASE_URL
  do
    if [ -z "${!SECRET_KEY:-}" ]; then
      SECRET_VAL="$(sed -n "s/^${SECRET_KEY}=//p" .env | head -1)"
      [ -n "$SECRET_VAL" ] && export "$SECRET_KEY=$SECRET_VAL"
    fi
  done
fi
for REQUIRED_SECRET in \
  DEPLOY_VERIFY_AUTH_TOKEN \
  DEPLOY_VERIFY_GAME_ID \
  PHASE8_VERIFICATION_FIXTURE_JSON
do
  [ -n "${!REQUIRED_SECRET:-}" ] \
    || die "$REQUIRED_SECRET is required for the deployment reach gate"
done

case "$TARGET" in
  all)
    REQUIRED_CHECKS="commit,bundle,health,auth,contract,queue,failures,journey"
    ;;
  backend)
    REQUIRED_CHECKS="commit,health,auth,contract,queue,failures,journey"
    ;;
  frontend)
    REQUIRED_CHECKS="bundle,health,auth,contract,queue,failures,journey"
    ;;
  *)
    die "unknown deploy target: $TARGET"
    ;;
esac

docker exec \
  -e DEPLOY_EXPECT_COMMIT="$HEAD_SHA" \
  -e DEPLOY_VERIFY_AUTH_TOKEN \
  -e DEPLOY_VERIFY_GAME_ID \
  -e PHASE8_VERIFICATION_FIXTURE_JSON \
  chess-coach-backend \
  python3 scripts/verify_deployment.py \
    --base-url "$VERIFY_BASE_URL" \
    --frontend-marker "phase8-transfer-verdict" \
    --require-checks "$REQUIRED_CHECKS" \
  || die "strict deployment verification failed; release is not live"
ok "strict checks passed, including the non-admin coaching journey"

printf '\nDeployed %s at %s\n' "$TARGET" "$(git log -1 --format='%h %s' | cut -c1-64)"
