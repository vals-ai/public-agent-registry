#!/bin/bash

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

if ! command -v curl &> /dev/null; then
  apt-get update && apt-get install -y curl || yum install -y curl || apk add --no-cache curl
fi

if ! command -v python3 &> /dev/null; then
  apt-get update && apt-get install -y python3 || yum install -y python3 || apk add --no-cache python3
fi

curl -fsSL https://claude.ai/install.sh | bash

mkdir -p /logs

ln -sf "$HOME/.local/bin/claude" /usr/local/bin/claude

cat <<EOF >/usr/local/bin/claude_code-run
#!/bin/sh
exec python3 "$PWD/collect_outputs.py" "\$@"
EOF
chmod +x /usr/local/bin/claude_code-run
