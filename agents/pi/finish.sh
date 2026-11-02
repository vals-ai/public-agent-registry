#!/bin/bash
set -uo pipefail

session_dir="$1"
code="$2"
upstream="$3"
out="$4"
jq="${JQ:-jq}"

case "$code" in '' | *[!0-9]* | ????*) code=1 ;; esac
code=$((10#$code))
[ "$code" -le 255 ] || code=1

session=""
for file in "$session_dir"/*.jsonl; do
  [ -f "$file" ] || continue
  if [ -z "$session" ] || [ "$file" -nt "$session" ]; then
    session="$file"
  fi
done
rm -f "$out/session.jsonl"
if [ -n "$session" ]; then
  cp "$session" "$out/session.jsonl" || echo "finish.sh: could not copy the session" >&2
fi

stop=""
if [ "$code" -ne 137 ] && [ -n "$session" ]; then
  stop="$("$jq" -R -r '
    fromjson? | select(type == "object" and .type == "message")
    | .message | select(type == "object" and .role == "assistant")
    | ((.stopReason | strings | select(test("^[A-Za-z][A-Za-z0-9_-]{0,31}$"))) // "")
  ' "$session" | tail -n 1)" || stop=""
fi

exit_code="$code"
stop_reason="${stop:-unknown}"
case "$code" in
  0) outcome=completed ;;
  137) outcome=killed; stop_reason=killed ;;
  *) outcome=error ;;
esac
if [ "$outcome" = error ] && [ "$stop" = length ]; then
  outcome=completed
  exit_code=0
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
