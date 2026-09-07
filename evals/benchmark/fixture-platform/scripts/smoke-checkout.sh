#!/usr/bin/env bash
# CI smoke: one checkout of two SKU-1 must cost 18.00 after the 10 % promotion.
set -euo pipefail
BASE=${1:-http://127.0.0.1:5081}
body=$(curl -sf -X POST "$BASE/api/checkout" -H 'Content-Type: application/json' \
    -d '{"customerId":1,"requestId":"smoke-1","lines":[{"sku":"SKU-1","quantity":2}]}')
echo "$body"
echo "$body" | grep -q '"total":18.00' || { echo "checkout total is not 18.00" >&2; exit 1; }
