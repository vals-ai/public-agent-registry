#!/bin/bash
# Run upstream pi on one problem statement, then write summary.json.
#
# Usage: run.sh PROBLEM MODEL [THINKING]
#
# PROBLEM is the path of a file holding the task, which pi reads as an @file argument. MODEL is
# provider/id and THINKING one of off, minimal, low, medium, high, xhigh or max (empty keeps pi's
# default, medium). pi runs in print mode in the current directory, which is the benchmark's working
# directory, and writes to /logs/pi/: sessions/<timestamp>_<id>.jsonl (the transcript),
# final_message.txt (what pi printed on stdout), stderr.log and summary.json (from finish.sh, always
# written). The exit code is finish.sh's: 0 when pi stopped on its own, 137 when it was killed, else
# nonzero with an `AgentError: ...` line in $VALKYRIE_ERROR_PATH.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
problem="$1"
model="$2"
thinking="${3:-}"

pi=/opt/pi/pi/pi
logs=/logs/pi
mkdir -p "$logs"

# The only changes to pi's behaviour: no check for a newer version, so the version that runs is the
# pinned one, and no install telemetry. Everything else is as upstream ships it, including its tools
# and the task repo's AGENTS.md/CLAUDE.md.
export PI_SKIP_VERSION_CHECK=1
export PI_TELEMETRY=0

# --no-approve makes explicit what print mode does anyway without a saved decision: the task repo's
# .pi/ settings, extensions and skills are not loaded.
args=(-p --model "$model")
if [ -n "$thinking" ]; then
  args+=(--thinking "$thinking")
fi
args+=(--session-dir "$logs/sessions" --no-approve "@$problem")

# stdin is /dev/null because pi waits for end-of-file on any stdin that is not a terminal and would
# add what it read to the prompt. The task goes in as an @file argument, so it is not limited by argv
# size and does not show up in the process list.
"$pi" "${args[@]}" > "$logs/final_message.txt" 2> "$logs/stderr.log" < /dev/null
rc=$?

JQ=/opt/pi/jq exec bash "$here/finish.sh" "$logs/sessions" "$rc" "$here/upstream.json" "$logs"
