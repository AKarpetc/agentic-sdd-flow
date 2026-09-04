#!/usr/bin/env bash
# Launches cwm-roslyn-navigator pinned to the solution named in ${CLAUDE_PLUGIN_DATA}/roslyn-solution.
set -euo pipefail

BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
TOOL="${ROSLYN_NAVIGATOR_BIN:-$HOME/.dotnet/tools/cwm-roslyn-navigator}"
DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.agentic-sdd-flow}"; mkdir -p "$DATA"
POINTER="$DATA/roslyn-solution"

# shellcheck source=./roslyn-resolve.sh
source "$BIN/roslyn-resolve.sh"

target="${ROSLYN_SOLUTION:-}"
if [[ -z "$target" && -f "$POINTER" ]]; then
    target="$(grep -vE '^\s*(#|$)' "$POINTER" | head -1 | sed 's/[[:space:]]*$//')"
fi

if [[ -z "$target" ]]; then
    echo "roslyn-navigator: no solution pinned — falling back to auto-discovery." >&2
    exec "$TOOL"
fi

if ! sln="$(roslyn_resolve_solution "$ROOT" "$target")"; then
    echo "roslyn-navigator: $sln" >&2
    exec "$TOOL"
fi

echo "roslyn-navigator: binding $sln" >&2
exec "$TOOL" --solution "$sln"
