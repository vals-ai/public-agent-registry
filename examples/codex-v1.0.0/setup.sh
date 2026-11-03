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

npm i -g @openai/codex --before="$(node -p 'new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()')"

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

uv_installer=$(mktemp)
trap 'rm -f "$uv_installer"' EXIT
curl -LsSf https://astral.sh/uv/0.13.5/install.sh -o "$uv_installer"
printf '%s  %s\n' '1c6e7f025499664633ac2dce43a210800510e9ef0625c52e034a8afdf8bf177a' "$uv_installer" | sha256sum -c -
UV_UNMANAGED_INSTALL="$HOME/.local/bin" sh "$uv_installer"
export PATH="$HOME/.local/bin:$PATH"
cd /bundle/codex-v1.0.0 && "$HOME/.local/bin/uv" sync --locked

mkdir -p /logs
