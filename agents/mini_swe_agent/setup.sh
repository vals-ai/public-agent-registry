#!/bin/bash
# Install upstream mini-swe-agent (the mini-swe-agent/ submodule next to this script) into its own
# venv and put one entry script, mini-swe-agent-run, on PATH. Run from this folder.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

here="$(pwd)"
venv=/opt/mini-swe-agent-venv
uv_dir=/opt/mini-swe-agent-uv
python_dir=/opt/mini-swe-agent-python

if ! command -v curl &> /dev/null; then
  apt-get update && apt-get install -y curl || yum install -y curl || apk add --no-cache curl
fi

# uv 0.13.5, checked against a pinned sha256. UV_UNMANAGED_INSTALL puts it in $uv_dir and leaves
# PATH and shell profiles alone, so the task's PATH only gains the entry script below.
uv_installer="$(mktemp)"
curl -LsSf https://github.com/astral-sh/uv/releases/download/0.13.5/uv-installer.sh -o "$uv_installer"
printf '%s  %s\n' '1c6e7f025499664633ac2dce43a210800510e9ef0625c52e034a8afdf8bf177a' "$uv_installer" | sha256sum -c -
UV_UNMANAGED_INSTALL="$uv_dir" sh "$uv_installer"
rm "$uv_installer"
uv="$uv_dir/uv"

# The interpreter lives next to the venv, not under $HOME, so the agent runs under any user.
# --clear rebuilds a venv left by an earlier attempt, so Valkyrie can retry a failed install here.
UV_PYTHON_INSTALL_DIR="$python_dir" "$uv" venv --clear --python 3.12 "$venv"
# The litellm extra "mcp" is requested because litellm 1.106 imports mcp for any request that carries
# tools (mini-swe-agent's always do) but only lists it as an optional extra, so a plain install
# fails with ModuleNotFoundError on the first model call.
"$uv" pip install --python "$venv/bin/python" --exclude-newer "7 days" "$here/mini-swe-agent" "litellm[mcp]"
# certifi is the one package exempt from the age limit, so the CA bundle stays current.
"$uv" pip install --python "$venv/bin/python" "certifi>=2026.10.19"

mkdir -p /logs /usr/local/bin
# The entry script has no stdin, so nothing in the agent can wait for input. -E keeps the task's
# PYTHONPATH, PYTHONHOME and other PYTHON* variables away from the agent's interpreter (they still
# reach the commands the agent runs), so a task setting PYTHONPATH cannot shadow mini-swe-agent's or
# litellm's modules.
printf '#!/bin/bash\nexec %q -E %q "$@" < /dev/null\n' "$venv/bin/python" "$here/run.py" > /usr/local/bin/mini-swe-agent-run
chmod +x /usr/local/bin/mini-swe-agent-run
