#!/bin/bash
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
problem="$1"
model="$2"
variant="${3:-}"

opencode=/opt/opencode/opencode
logs=/logs/opencode
mkdir -p "$logs"

export OPENCODE_DISABLE_AUTOUPDATE=1

args=(run -m "$model" --auto --format json --print-logs --log-level WARN)
if [ -n "$variant" ]; then
  args+=(--variant "$variant")
fi

"$opencode" "${args[@]}" > "$logs/events.jsonl" 2> "$logs/stderr.log" < "$problem"
rc=$?

session_id="$(/opt/opencode/jq -n -R -r 'first(inputs | fromjson? | objects | .sessionID | strings | select(test("^[A-Za-z0-9_][A-Za-z0-9_-]*$")))' "$logs/events.jsonl")" || session_id=""
if [ -n "$session_id" ]; then
  "$opencode" export "$session_id" > "$logs/session.json" 2>> "$logs/stderr.log" < /dev/null || rm -f "$logs/session.json"
fi

JQ=/opt/opencode/jq exec bash "$here/finish.sh" "$logs/events.jsonl" "$rc" "$here/upstream.json" "$logs"
