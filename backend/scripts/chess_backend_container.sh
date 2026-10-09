#!/usr/bin/env bash
# Resolve the smartchesscoach backend container id. Source this; it sets
# CHESS_BACKEND.
#
# WHY THIS EXISTS. Every cron on this box said `docker exec
# chess-coach-backend`. On 2026-10-10 a `docker compose up -d` left the
# container renamed `b6d877cac808_chess-coach-backend` -- Docker's
# mid-recreate name -- and `docker exec chess-coach-backend` began failing
# with "No such container". The site was fine, so nothing surfaced; both
# nightly jobs would simply have failed at 03:00 and said nothing.
#
# The filter is scoped to the PROJECT as well as the service on purpose. The
# service label alone matches `mail_sender-backend-1` too, so a naive
# label filter would have exec'd into an unrelated application.
CHESS_BACKEND=$(docker ps \
  --filter "label=com.docker.compose.project=smartchesscoach" \
  --filter "label=com.docker.compose.service=backend" \
  --format "{{.ID}}" | head -1)

if [ -z "${CHESS_BACKEND}" ]; then
  echo "cannot find the smartchesscoach backend container; refusing to run" >&2
  exit 1
fi
export CHESS_BACKEND
