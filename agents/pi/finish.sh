#!/bin/bash
# Write summary.json for one pi run and exit with the run's final code.
#
# Usage: finish.sh SESSION_DIR AGENT_EXIT_CODE UPSTREAM_JSON OUT_DIR
#
# SESSION_DIR is pi's --session-dir: it holds one <timestamp>_<id>.jsonl session file per run, which
# has an entry per line (packages/coding-agent/docs/session-format.md). The stop reason is the
# `stopReason` of the last assistant message entry in the newest file: stop, length, toolUse, error,
# aborted or deferred.
#
#   exit 0                        -> completed, stop_reason is that stopReason
#   exit 137                      -> killed, passed through with no error line
#   other exit, stopReason length -> completed, exit 0. Print mode exits 1 after a reply that was cut
#                                    off at the output token limit, but the run did finish its work
#   any other exit                -> error, with one `AgentError: ...` line in $VALKYRIE_ERROR_PATH
#
# The error line holds the exit code and the stop reason, never anything the model or the task wrote:
# the stop reason must be a plain word to be printed. Nothing here is allowed to change the exit code,
# so a summary that cannot be written is reported on stderr and the mapped code is still returned.
set -uo pipefail

session_dir="$1"
code="$2"
upstream="$3"
out="$4"
jq="${JQ:-jq}"

# Digits only, at most 255: bash takes exit codes modulo 256, so 256 would turn into success.
case "$code" in '' | *[!0-9]* | ????*) code=1 ;; esac
code=$((10#$code))
[ "$code" -le 255 ] || code=1

# The newest session file; -nt compares modification times and copes with any file name.
session=""
for file in "$session_dir"/*.jsonl; do
  [ -f "$file" ] || continue
  if [ -z "$session" ] || [ "$file" -nt "$session" ]; then
    session="$file"
  fi
done

# The last assistant message entry's stopReason. An assistant message entry looks like
# {"type":"message","id":...,"message":{"role":"assistant","stopReason":"stop",...}}. Lines that are
# not JSON (a kill can cut the last one short) are skipped, and a stopReason that is not a plain word
# counts as none, so an unusable last entry never falls back to an earlier one.
stop=""
if [ "$code" -ne 137 ] && [ -n "$session" ]; then
  stop="$("$jq" -R -r '
    fromjson? | select(type == "object" and .type == "message")
    | .message | select(type == "object" and .role == "assistant")
    | ((.stopReason | strings | select(test("^[A-Za-z][A-Za-z0-9_-]{0,31}$"))) // "")
  ' "$session" | tail -n 1)" || stop=""
fi

exit_code="$code"
case "$code" in
  0) outcome=completed ;;
  137) outcome=killed ;;
  *) outcome=error ;;
esac
if [ "$outcome" = error ] && [ "$stop" = length ]; then
  outcome=completed
  exit_code=0
fi

if [ "$outcome" = killed ]; then
  stop_reason=killed
else
  stop_reason="${stop:-unknown}"
fi

write_summary() {
  mkdir -p "$out" || return 1
  "$jq" -n \
    --arg outcome "$outcome" \
    --arg stop_reason "$stop_reason" \
    --arg code "$code" \
    --slurpfile upstream "$upstream" \
    '{agent: "pi", upstream: $upstream[0], outcome: $outcome, stop_reason: $stop_reason, agent_exit_code: ($code | tonumber)}' \
    > "$out/summary.json.tmp" && mv "$out/summary.json.tmp" "$out/summary.json"
}

# No jq, or an upstream.json it cannot read: still leave a summary, with upstream null. Every other
# value in it is a fixed word or a number, so it is valid JSON as it stands.
write_plain_summary() {
  mkdir -p "$out" &&
    printf '{"agent":"pi","upstream":null,"outcome":"%s","stop_reason":"%s","agent_exit_code":%s}\n' \
      "$outcome" "$stop_reason" "$code" > "$out/summary.json"
}

if ! write_summary; then
  rm -f "$out/summary.json.tmp"
  write_plain_summary || echo "finish.sh: could not write $out/summary.json" >&2
fi

if [ "$outcome" = error ] && [ -n "${VALKYRIE_ERROR_PATH:-}" ]; then
  line="AgentError: pi exited with code $code"
  if [ -n "$stop" ]; then
    line="$line (stop: $stop)"
  elif [ -z "$session" ]; then
    line="$line (no session)"
  fi
  printf '%s\n' "$line" > "$VALKYRIE_ERROR_PATH" || echo "finish.sh: could not write the error line" >&2
fi

exit "$exit_code"
