#!/bin/bash
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
problem="$1"
model="$2"
thinking="${3:-}"

pi=/opt/pi/pi/pi
logs=/logs/pi
mkdir -p "$logs"

export PI_SKIP_VERSION_CHECK=1
export PI_TELEMETRY=0

if [[ $model == */* ]]; then
  args=(-p --provider "${model%%/*}" --model "${model#*/}")
else
  args=(-p --model "$model")
fi
if [ -n "$thinking" ]; then
  args+=(--thinking "$thinking")
fi
args+=(--session-dir "$logs/sessions" --no-approve "@$problem")

"$pi" "${args[@]}" > "$logs/final_message.txt" 2> "$logs/stderr.log" < /dev/null
rc=$?

JQ=/opt/pi/jq exec bash "$here/finish.sh" "$logs/sessions" "$rc" "$here/upstream.json" "$logs"
