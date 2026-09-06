#!/usr/bin/env bash
# Status line command: prints what the session's subagents are doing right now.
# Wire it in ~/.claude/settings.json:
#   "statusLine": { "type": "command", "command": "<plugin root>/bin/agent-pulse.sh", "refreshInterval": 5 }
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/agent-pulse.py" render
