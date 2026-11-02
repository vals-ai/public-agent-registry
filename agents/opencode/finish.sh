#!/bin/bash
# Write summary.json for one opencode run and exit with the run's final code.
#
# Usage: finish.sh EVENTS_JSONL AGENT_EXIT_CODE UPSTREAM_JSON OUT_DIR
#
# EVENTS_JSONL is what `opencode run --format json` printed on stdout, one JSON event per line.
# Exit code 0 means opencode stopped on its own and 137 that it was killed. Anything else writes
# one `AgentError: ...` line to $VALKYRIE_ERROR_PATH. The line holds the exit code and the name of
# the last `error` event's error (for example ProviderAuthError), never the event's message, which
# can quote the prompt or model output.
set -euo pipefail

events="$1"
code="$2"
upstream="$3"
out="$4"
jq="${JQ:-jq}"

case "$code" in '' | *[!0-9]*) code=1 ;; esac
[ -r "$events" ] || events=/dev/null

case "$code" in
  0) outcome=completed ;;
  137) outcome=killed ;;
  *) outcome=error ;;
esac

mkdir -p "$out"
"$jq" -n \
  --arg outcome "$outcome" \
  --arg code "$code" \
  --slurpfile upstream "$upstream" \
  '{agent: "opencode", upstream: $upstream[0], outcome: $outcome, stop_reason: $outcome, agent_exit_code: ($code | tonumber)}' \
  > "$out/summary.json"

if [ "$outcome" = error ]; then
  # An error event looks like {"type":"error","sessionID":...,"error":{"name":"ProviderAuthError","data":{...}}}.
  # Lines that are not JSON (a kill can cut the last one short) are skipped, and a name that is not a
  # plain identifier counts as no name.
  name="$("$jq" -R -r '
    fromjson? | select(type == "object" and .type == "error")
    | ((.error | objects | .name | strings | select(test("^[A-Za-z0-9_.-]{1,80}$"))) // "")
  ' "$events" | tail -n 1)" || name=""
  line="AgentError: opencode exited with code $code"
  if [ -n "$name" ]; then
    line="$line ($name)"
  fi
  if [ -n "${VALKYRIE_ERROR_PATH:-}" ]; then
    printf '%s\n' "$line" > "$VALKYRIE_ERROR_PATH"
  fi
fi

exit "$code"
