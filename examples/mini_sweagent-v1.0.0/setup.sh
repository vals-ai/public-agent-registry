#!/bin/bash
set -euo pipefail

# This script assumes Debian-based image (i.e. SWE-bench task images)
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y curl

# Install uv
uv_installer="$(mktemp)"
curl -LsSf https://github.com/astral-sh/uv/releases/download/0.13.5/uv-installer.sh -o "$uv_installer"
printf '%s  %s\n' '1c6e7f025499664633ac2dce43a210800510e9ef0625c52e034a8afdf8bf177a' "$uv_installer" | sha256sum -c -
sh "$uv_installer"
rm "$uv_installer"

# Source uv so it's available in this session
source "$HOME/.local/bin/env" 2>/dev/null || true
export PATH="$HOME/.local/bin:$PATH"

cd mini_sweagent && uv sync

# Wrapper script so `mini` is on PATH
# Pre-create global config to skip interactive first-run wizard
mkdir -p /root/.config/mini-swe-agent
echo 'MSWEA_CONFIGURED=true' > /root/.config/mini-swe-agent/.env

cat > /usr/local/bin/mini << 'WRAPPER'
#!/bin/bash
source /bundle/mini_sweagent-v1.0.0/mini_sweagent/.venv/bin/activate
exec -a mini python -m minisweagent.run.mini "$@"
WRAPPER
chmod +x /usr/local/bin/mini
