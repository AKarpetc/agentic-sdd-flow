#!/usr/bin/env bash
# Usage: smoke-report.sh <customerId> "<expected substring>" — asserts the customer report line against a running API.
set -euo pipefail
body=$(curl -fsS "${ORDERS_API_URL:-http://127.0.0.1:5000}/api/customers/$1/report")
grep -q -- "$2" <<<"$body" || { echo "report for customer $1 was: $body"; exit 1; }
