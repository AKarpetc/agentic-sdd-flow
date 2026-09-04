#!/usr/bin/env bash
# Resolves a project short name (or a path) to one absolute .slnx/.sln path.
# Prints the path on success; prints the reason and returns 1 on failure.
roslyn_resolve_solution() {
    local root="$1" target="$2" dir candidates=() matches=()

    # An explicit solution file, absolute or root-relative.
    if [[ "$target" == *.sln || "$target" == *.slnx ]]; then
        [[ "$target" != /* ]] && target="$root/$target"
        if [[ -f "$target" ]]; then
            printf '%s\n' "$target"
            return 0
        fi
        printf 'no solution file at %s\n' "$target"
        return 1
    fi

    # A project directory, given as a path.
    if [[ -d "$target" || -d "$root/$target" ]]; then
        [[ -d "$root/$target" ]] && target="$root/$target"
        candidates=("$target")
    else
        # A project short name
        # 1. Explicit index in .claude/agentic-sdd-flow.json → "projects": { "<name>": "<sln path>" }.
        local indexed
        indexed="$(python3 - "$root" "$target" <<'PY'
import json, os, sys
root, name = sys.argv[1], sys.argv[2]
path = os.path.join(root, ".claude", "agentic-sdd-flow.json")
try:
    print((json.load(open(path)).get("projects") or {}).get(name, ""))
except Exception:
    print("")
PY
)"
        if [[ -n "$indexed" ]]; then
            [[ "$indexed" != /* ]] && indexed="$root/$indexed"
            if [[ -f "$indexed" ]]; then printf '%s\n' "$indexed"; return 0; fi
            if [[ -d "$indexed" ]]; then candidates=("$indexed"); fi
        fi

        # 2. Directory named exactly like the target anywhere under the root (depth ≤ 4), then substring.
        if [[ ${#candidates[@]} -eq 0 ]]; then
            while IFS= read -r dir; do candidates+=("$dir"); done < <(find "$root" -maxdepth 4 -type d \( -name .git -o -name bin -o -name obj -o -name node_modules \) -prune -o -type d -name "$target" -print 2>/dev/null)
        fi
        if [[ ${#candidates[@]} -eq 0 ]]; then
            while IFS= read -r dir; do candidates+=("$dir"); done < <(find "$root" -maxdepth 4 -type d \( -name .git -o -name bin -o -name obj -o -name node_modules \) -prune -o -type d -name "*$target*" -print 2>/dev/null)
        fi
    fi

    # bash 3.2 errors on empty-array expansion under `set -u`.
    for dir in ${candidates[@]+"${candidates[@]}"}; do
        while IFS= read -r sln; do
            matches+=("$sln")
        done < <(find "$dir" -maxdepth 1 \( -name '*.slnx' -o -name '*.sln' \) 2>/dev/null | sort)
    done

    if [[ ${#matches[@]} -eq 0 ]]; then
        printf 'no .sln/.slnx found for "%s"\n' "$target"
        return 1
    fi
    if [[ ${#matches[@]} -gt 1 ]]; then
        printf 'ambiguous "%s" — matches: %s. Pin the full solution path instead.\n' \
            "$target" "$(printf '%s ' "${matches[@]}")"
        return 1
    fi

    printf '%s\n' "${matches[0]}"
}
