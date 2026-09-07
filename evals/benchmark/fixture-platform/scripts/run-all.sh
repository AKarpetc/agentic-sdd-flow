#!/usr/bin/env bash
# Starts the five services on the ports in their appsettings.json and waits for each to answer "/".
# Peer URLs come from configuration (Services:<Name>:BaseUrl) — override them with
# Services__<Name>__BaseUrl in the environment, never by editing a port into the code.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .run
: > .run/pids

start() {
    local project=$1 port=$2
    dotnet run --project "src/$project" --urls "http://127.0.0.1:$port" > ".run/$project.log" 2>&1 &
    echo $! >> .run/pids
    for _ in $(seq 1 60); do
        if curl -sf "http://127.0.0.1:$port/" > /dev/null; then
            echo "$project up on $port"
            return 0
        fi
        sleep 1
    done
    echo "$project did not start on $port — see .run/$project.log" >&2
    return 1
}

start Orders.Api 5082
start Inventory.Api 5083
start Pricing.Api 5084
start Ledger.Api 5085
start Checkout.Api 5081
