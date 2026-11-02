#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

here="$(pwd)"
venv=/opt/mini-swe-agent-venv
uv_dir=/opt/mini-swe-agent-uv
python_dir=/opt/mini-swe-agent-python

if ! command -v curl &> /dev/null; then
  apt-get update && apt-get install -y curl || yum install -y curl || apk add --no-cache curl
fi

uv_installer="$(mktemp)"
curl -LsSf https://github.com/astral-sh/uv/releases/download/0.13.5/uv-installer.sh -o "$uv_installer"
printf '%s  %s\n' '1c6e7f025499664633ac2dce43a210800510e9ef0625c52e034a8afdf8bf177a' "$uv_installer" | sha256sum -c -
UV_UNMANAGED_INSTALL="$uv_dir" sh "$uv_installer"
rm "$uv_installer"
uv="$uv_dir/uv"

UV_PYTHON_INSTALL_DIR="$python_dir" "$uv" venv --clear --python 3.12 "$venv"
"$uv" pip install --python "$venv/bin/python" --exclude-newer "7 days" "$here/mini-swe-agent" "litellm[mcp]"
"$uv" pip install --python "$venv/bin/python" "certifi>=2026.10.19"

mkdir -p /logs /usr/local/bin
printf '#!/bin/bash\nexec %q -E %q "$@" < /dev/null\n' "$venv/bin/python" "$here/run.py" > /usr/local/bin/mini-swe-agent-run
chmod +x /usr/local/bin/mini-swe-agent-run
