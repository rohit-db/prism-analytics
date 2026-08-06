#!/usr/bin/env bash
# Launch the three-vertical Prism demo: ONE build, three branded instances.
#
#   :8000  Prism · Travel Intelligence      (BCD anchor; Lakebase + tenant isolation ON)
#   :8001  Meridian Retail · Vendor Portal
#   :8002  Cascade Hotels · Owner Portal
#
# The point of the demo: all three run the SAME frontend/dist and the SAME server code.
# Only config differs (brand.config.json, content.config.json, KPI measures, assets),
# read at RUNTIME — so re-skinning needs no rebuild and no redeploy.
#
# Env vars are EXPORTED here rather than left to .env because server/auth/sessions.py
# reads os.environ at import time and never loads .env (it is stdlib-only by design), so
# a .env-only AUTH_SESSION_COOKIE is silently ignored. Distinct cookie names matter:
# browsers scope cookies by host and IGNORE port, so a shared name makes the instances
# evict each other's sessions mid-demo.
#
# Usage:
#   ./demo/run-all.sh          # start all three
#   ./demo/run-all.sh stop     # stop all three
#   tail -f /tmp/prism-travel.log
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
REPO="$PWD"
PORTS=(8000 8001 8002)

stop_all() {
  for port in "${PORTS[@]}"; do
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "  stopping :$port ($pids)"
      # shellcheck disable=SC2086
      kill $pids 2>/dev/null || true
    fi
  done
}

if [ "${1:-}" = "stop" ]; then
  echo "Stopping Prism demo instances…"
  stop_all
  echo "Done."
  exit 0
fi

# Refuse to start if a port is busy — silently attaching to someone else's process (or
# double-starting) is exactly the kind of surprise you don't want minutes before a demo.
busy=""
for port in "${PORTS[@]}"; do
  if lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    busy="$busy $port"
  fi
done
if [ -n "$busy" ]; then
  echo "ERROR: port(s) already in use:$busy"
  echo "Run './demo/run-all.sh stop' first (it only kills listeners on 8000-8002)."
  exit 1
fi

start_instance() {
  local name="$1" port="$2" env_file="$3" log="/tmp/prism-${1}.log"
  echo "  :$port  $name"
  (
    # Subshell so each instance's exported env stays isolated from the others.
    if [ -n "$env_file" ]; then
      set -a
      # shellcheck disable=SC1090
      . "$REPO/$env_file"
      set +a
    fi
    exec python -m uvicorn app:app --host 127.0.0.1 --port "$port"
  ) > "$log" 2>&1 &
}

echo "Starting Prism demo (one build, three branded instances)…"
# Travel uses the repo defaults (.env + brand.config.json) — no env file, and it keeps
# Lakebase ON so conversation history and the tenant-isolation demo work.
start_instance travel 8000 ""
start_instance retail 8001 "demo/envs/retail.env"
start_instance hotel  8002 "demo/envs/hotel.env"

echo "Waiting for startup…"
for i in $(seq 1 30); do
  ready=0
  for port in "${PORTS[@]}"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$port/api/config" 2>/dev/null || echo 000)
    [ "$code" = "200" ] && ready=$((ready + 1))
  done
  [ "$ready" -eq 3 ] && break
  sleep 1
done

echo
for port in "${PORTS[@]}"; do
  name=$(curl -s "http://127.0.0.1:$port/api/config" 2>/dev/null \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); i=d["brand"]["identity"]; print(i["appName"], "·", i["tagline"])' 2>/dev/null \
    || echo "NOT READY")
  printf "  http://localhost:%s  %s\n" "$port" "$name"
done
echo
echo "Logs: /tmp/prism-{travel,retail,hotel}.log     Stop: ./demo/run-all.sh stop"
