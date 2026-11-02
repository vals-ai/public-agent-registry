#!/bin/bash
# Run upstream opencode on one problem statement, then write summary.json.
#
# Usage: run.sh PROBLEM MODEL [VARIANT]
#
# PROBLEM is the path of a file holding the task; opencode reads it from stdin. MODEL is
# provider/model and VARIANT the provider's reasoning effort (empty keeps its default). opencode
# runs in the current directory, which is the benchmark's working directory, and writes to
# /logs/opencode/: events.jsonl and stderr.log (what opencode printed), session.json (the
# transcript, from `opencode export`) and summary.json (from finish.sh, always written).
# The exit code is finish.sh's: 0 when opencode stopped on its own, 137 when it was killed, else
# nonzero with an `AgentError: ...` line in $VALKYRIE_ERROR_PATH.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
problem="$1"
model="$2"
variant="${3:-}"

opencode=/opt/opencode/opencode
logs=/logs/opencode
mkdir -p "$logs"

# No self-update, no opencode.json (or .opencode/) from the task's repo, no bundled plugins:
# the agent runs as pinned and configured by the model arguments alone.
export OPENCODE_DISABLE_AUTOUPDATE=1
export OPENCODE_DISABLE_PROJECT_CONFIG=1
export OPENCODE_DISABLE_DEFAULT_PLUGINS=1

args=(run -m "$model" --auto --format json)
if [ -n "$variant" ]; then
  args+=(--variant "$variant")
fi

# The task goes in on stdin, never on the command line, so it is not limited by argv size and
# does not show up in the process list.
"$opencode" "${args[@]}" > "$logs/events.jsonl" 2> "$logs/stderr.log" < "$problem"
rc=$?

# Every event carries the session id. Export the transcript when there is one; a failed export
# only costs session.json, so it never changes the exit code.
session_id="$(/opt/opencode/jq -n -R -r 'first(inputs | fromjson? | objects | .sessionID | strings | select(test("^[A-Za-z0-9_][A-Za-z0-9_-]*$")))' "$logs/events.jsonl")" || session_id=""
if [ -n "$session_id" ]; then
  "$opencode" export "$session_id" > "$logs/session.json" 2>> "$logs/stderr.log" < /dev/null || rm -f "$logs/session.json"
fi

JQ=/opt/opencode/jq exec bash "$here/finish.sh" "$logs/events.jsonl" "$rc" "$here/upstream.json" "$logs"
