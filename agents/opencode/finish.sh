#!/bin/bash
# Write summary.json for one opencode run and exit with the run's final code.
#
# Usage: finish.sh EVENTS_JSONL AGENT_EXIT_CODE UPSTREAM_JSON OUT_DIR
#
# EVENTS_JSONL is what `opencode run --format json` printed on stdout, one JSON event per line.
# Exit code 0 means opencode stopped on its own and 137 that it was killed. Anything else writes
# one `AgentError: ...` line to $VALKYRIE_ERROR_PATH. The line holds the exit code and the name of
# the last `error` event's error (for example ProviderAuthError), never the event's message, which
# can quote the prompt or model output. Nothing here is allowed to change the exit code, so a summary
# or error line that cannot be written is reported on stderr and the mapped code is still returned.
set -uo pipefail

events="$1"
code="$2"
upstream="$3"
out="$4"
jq="${JQ:-jq}"

# Digits only, at most 255: bash takes exit codes modulo 256, so 256 would turn into success.
case "$code" in '' | *[!0-9]* | ????*) code=1 ;; esac
code=$((10#$code))
[ "$code" -le 255 ] || code=1
[ -r "$events" ] || events=/dev/null

case "$code" in
  0) outcome=completed ;;
  137) outcome=killed ;;
  *) outcome=error ;;
esac

write_summary() {
  mkdir -p "$out" || return 1
  "$jq" -n \
    --arg outcome "$outcome" \
    --arg code "$code" \
    --slurpfile upstream "$upstream" \
    '{agent: "opencode", upstream: $upstream[0], outcome: $outcome, stop_reason: $outcome, agent_exit_code: ($code | tonumber)}' \
    > "$out/summary.json.tmp" && mv "$out/summary.json.tmp" "$out/summary.json"
}

# No jq, or an upstream.json it cannot read: still leave a summary, with upstream null. Every other
# value in it is a fixed word or a number, so it is valid JSON as it stands.
write_plain_summary() {
  mkdir -p "$out" &&
    printf '{"agent":"opencode","upstream":null,"outcome":"%s","stop_reason":"%s","agent_exit_code":%s}\n' \
      "$outcome" "$outcome" "$code" > "$out/summary.json"
}

if ! write_summary; then
  rm -f "$out/summary.json.tmp"
  write_plain_summary || echo "finish.sh: could not write $out/summary.json" >&2
fi

if [ "$outcome" = error ] && [ -n "${VALKYRIE_ERROR_PATH:-}" ]; then
  # An error event looks like {"type":"error","sessionID":...,"error":{"name":"ProviderAuthError","data":{...}}}.
  # Lines that are not JSON (a kill can cut the last one short) are skipped, and a name that is not a
  # plain identifier counts as no name. Without a working jq there is no name.
  name="$("$jq" -R -r '
    fromjson? | select(type == "object" and .type == "error")
    | ((.error | objects | .name | strings | select(test("^[A-Za-z0-9_.-]{1,80}$"))) // "")
  ' "$events" | tail -n 1)" || name=""
  line="AgentError: opencode exited with code $code"
  if [ -n "$name" ]; then
    line="$line ($name)"
  fi
  printf '%s\n' "$line" > "$VALKYRIE_ERROR_PATH" || echo "finish.sh: could not write the error line" >&2
fi

exit "$code"
