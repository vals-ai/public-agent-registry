#!/bin/bash
set -euo pipefail

# The fabv2 runner image ships a uv-managed venv but not the latest model-proxy;
# install SSH tooling, then refresh model-library from vals-ai/model-proxy into
# that existing interpreter before fabv2 runs.

if [[ -z "${MODEL_PROXY_SSH_KEY:-}" ]]; then
  echo "MODEL_PROXY_SSH_KEY not set; using bundled public model-library"
  exit 0
fi

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
apt-get update && apt-get install -y --no-install-recommends openssh-client
mkdir -p "$HOME/.ssh" && printf '%s\n' "$MODEL_PROXY_SSH_KEY" > "$HOME/.ssh/model_proxy_ssh" && chmod 600 "$HOME/.ssh/model_proxy_ssh"
ssh-keyscan github.com > "$HOME/.ssh/known_hosts"
GIT_SSH_COMMAND="ssh -i $HOME/.ssh/model_proxy_ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOME/.ssh/known_hosts" uv pip install --python /app/.venv/bin/python --upgrade "model-library @ git+ssh://git@github.com/vals-ai/model-proxy.git@dev"
