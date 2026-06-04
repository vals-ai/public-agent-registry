#!/bin/bash
set -euo pipefail

# This script assumes Debian-based image (i.e. SWE-bench task images)
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y curl

# Install uv
curl -LsSf https://astral.sh/uv/0.7.13/install.sh | sh

# Source uv so it's available in this session
source "$HOME/.local/bin/env" 2>/dev/null || true

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
