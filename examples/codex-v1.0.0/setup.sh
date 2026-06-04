#!/bin/bash

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

if ! command -v curl &> /dev/null; then
  apt-get update && apt-get install -y curl || yum install -y curl || apk add --no-cache curl
fi

if ! command -v python3 &> /dev/null; then
  apt-get update && apt-get install -y python3 || yum install -y python3 || apk add --no-cache python3
fi

node_major_version() {
  if command -v node &> /dev/null; then
    node --version | sed 's/^v//' | cut -d. -f1
  else
    echo 0
  fi
}

if [ "$(node_major_version)" -lt 20 ] || ! command -v npm &> /dev/null; then
  if command -v apt-get &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
  elif command -v yum &> /dev/null; then
    curl -fsSL https://rpm.nodesource.com/setup_22.x | bash -
    yum install -y nodejs
  else
    apk add --no-cache nodejs npm
  fi
fi

npm i -g @openai/codex

if [ -z "$OPENAI_API_KEY" ]; then
    echo "OPENAI_API_KEY is not set"
    exit 1
fi

mkdir -p "$HOME/.codex"
cat <<EOF >"$HOME/.codex/auth.json"
{
  "OPENAI_API_KEY": "${OPENAI_API_KEY}"
}
EOF

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
cd /bundle/codex-v1.0.0 && uv sync

mkdir -p /logs
