#!/usr/bin/env bash
# Stops whatever run-all.sh started.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .run/pids ] || exit 0
while read -r pid; do
    kill "$pid" 2> /dev/null || true
done < .run/pids
rm -f .run/pids
