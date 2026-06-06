#!/usr/bin/env bash
# worker_capacity_probe.sh — how many analysis-workers can srv1050112
# run without starving the OTHER apps on this shared host?
#
# Built 2026-06-06. The server co-hosts chessguru + matrimonial +
# satsang-seva + traefik + postgres. Analysis workers (Stockfish depth 18,
# ~1 core + ~350MB RAM each when active) compete with those live apps.
# This probe reads host CPU/RAM + current container usage and recommends
# a SAFE worker count, leaving headroom so nothing crashes or thrashes.
#
# Run ON THE SERVER:  bash scripts/worker_capacity_probe.sh
# Read-only. Changes nothing.

set -euo pipefail

# ── Tunables (conservative) ──────────────────────────────────────────
CPU_HEADROOM_CORES=2          # keep this many cores free for OS/traefik/API spikes
CPU_TARGET_UTIL=0.80          # don't plan past 80% of cores
PER_WORKER_CORES=1            # Stockfish = 1 thread/engine; ~1 core when active
PER_WORKER_RAM_MB=400         # Stockfish hash(128M) + python(~250M) when active
RAM_HEADROOM_MB=2048          # keep this much RAM free as a buffer

echo "================ WORKER CAPACITY PROBE — $(hostname) ================"
echo

# ── CPU ──────────────────────────────────────────────────────────────
CORES=$(nproc)
read -r L1 L5 L15 _ < /proc/loadavg
echo "CPU"
echo "  cores:            $CORES"
echo "  load avg (1/5/15): $L1 / $L5 / $L15   (load = avg runnable procs)"
# load already includes the running chess workers. Spare capacity:
SPARE_CORES=$(awk -v c="$CORES" -v l="$L1" -v t="$CPU_TARGET_UTIL" -v h="$CPU_HEADROOM_CORES" \
  'BEGIN{printf "%.1f", (c*t) - l - h}')
echo "  usable spare (target ${CPU_TARGET_UTIL}× cores − load − ${CPU_HEADROOM_CORES} headroom): ${SPARE_CORES} cores"
echo

# ── RAM ──────────────────────────────────────────────────────────────
echo "MEMORY (MB)"
TOTAL_MB=$(free -m | awk '/^Mem:/{print $2}')
AVAIL_MB=$(free -m | awk '/^Mem:/{print $7}')   # "available" = reclaimable + free
echo "  total:     $TOTAL_MB"
echo "  available: $AVAIL_MB"
USABLE_RAM_MB=$(( AVAIL_MB - RAM_HEADROOM_MB ))
echo "  usable for workers (available − ${RAM_HEADROOM_MB} headroom): ${USABLE_RAM_MB}"
echo

# ── Current container footprint (what the OTHER apps + workers use) ──
echo "TOP CONTAINERS BY CPU/MEM (live snapshot):"
docker stats --no-stream --format '  {{.Name}}\t{{.CPUPerc}}\tMEM {{.MemUsage}}' \
  | sort -t$'\t' -k2 -hr | head -12 || echo "  (docker stats unavailable)"
echo
RUNNING_WORKERS=$(docker ps --filter name=analysis-worker --format '{{.Names}}' | wc -l)
echo "  analysis-workers currently running: $RUNNING_WORKERS"
echo

# ── Recommendation ───────────────────────────────────────────────────
# Max ADDITIONAL workers the spare CPU + RAM can take, then total safe.
CPU_MORE=$(awk -v s="$SPARE_CORES" -v p="$PER_WORKER_CORES" 'BEGIN{v=s/p; if(v<0)v=0; printf "%d", v}')
RAM_MORE=$(awk -v u="$USABLE_RAM_MB" -v p="$PER_WORKER_RAM_MB" 'BEGIN{v=u/p; if(v<0)v=0; printf "%d", v}')
ADD=$(( CPU_MORE < RAM_MORE ? CPU_MORE : RAM_MORE ))
TOTAL_SAFE=$(( RUNNING_WORKERS + ADD ))
BIND=$([ "$CPU_MORE" -lt "$RAM_MORE" ] && echo "CPU" || echo "RAM")

echo "================ RECOMMENDATION ================"
echo "  Headroom allows ~$ADD MORE worker(s)  (bound by: $BIND)"
echo "    CPU permits +$CPU_MORE   |   RAM permits +$RAM_MORE"
echo "  => SAFE TOTAL workers: ~$TOTAL_SAFE  (currently $RUNNING_WORKERS)"
echo
echo "  Apply (temporary, for the backlog drain):"
echo "    docker compose up -d --scale analysis-worker=$TOTAL_SAFE --no-recreate analysis-worker"
echo
echo "  NOTE: this is a SHARED host (matrimonial + satsang-seva are live)."
echo "  Workers only peg a core WHILE analyzing (~84s/game), idle between."
echo "  After the backlog drains, scale BACK to 1-2 (steady state is ~1-2"
echo "  new games/day): docker compose up -d --scale analysis-worker=1 analysis-worker"
echo "==============================================="
