#!/bin/bash
set -uo pipefail

events="$1"
code="$2"
upstream="$3"
out="$4"
jq="${JQ:-jq}"

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
