#!/bin/bash
set -euo pipefail

# Daytona spawns setup.sh with a minimal PATH that omits /usr/bin and /bin,
# so system tools like ssh-keyscan (from openssh-client in the sandbox image)
# aren't findable. Restore a full default PATH.
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

export DEBIAN_FRONTEND=noninteractive

# git and curl are pre-baked in the sandbox image.
# Lean, elan, lake, Mathlib oleans, and loogle are all pre-baked.

# Install uv
curl -LsSf https://astral.sh/uv/0.7.13/install.sh | sh
source "$HOME/.local/bin/env" 2>/dev/null || true

# Daytona sessions don't share PATH state — each command runs in a fresh
# session with only the default PATH. Symlink everything we install to
# /usr/local/bin/ so it's always findable.
ln -sf "$HOME/.local/bin/uv" /usr/local/bin/uv
ln -sf "$HOME/.local/bin/uvx" /usr/local/bin/uvx

# Configure SSH key for private repo access (model-proxy).
mkdir -p /root/.ssh
printf '%s\n' "$MODEL_PROXY_SSH_KEY" > /root/.ssh/id_ed25519
chmod 600 /root/.ssh/id_ed25519

# GitHub's published SSH host keys (docs.github.com/.../githubs-ssh-key-fingerprints).
# Hardcoded because ssh-keyscan isn't reliably findable in the sandbox image under
# Daytona's minimal spawn env.
cat > /root/.ssh/known_hosts <<'EOF'
github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl
github.com ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBEmKSENjQEezOmxkZMy7opKgwFB9nkt5YRrYMjNuG5N87uRgg6CLrbo5wAdT/y6v0mKV0U2w0WZ2YB/++Tpockg=
github.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCj7ndNxQowgcQnjshcLrqPEiiphnt+VTTvDP6mHBL9j1aNUkY4Ue1gvwnGLVlOhGeYrnZaMgRK6+PKCUXaDbC7qtbW8gIkhL7aGCsOr/C56SJMy/BCZfxd1nWzAOxSDPgVsmerOBYfNqltV9/hWCqBywINIR+5dIg6JTJ72pcEpEjcYgXkE2YEFXV1JHnsKgbLWNlhScqb2UmyRkQyytRLtL+38TGxkxCflmO+5Z8CSSNY7GidjMIZ7Q4zMjA2n1nGrlTDkzwDCsw+wqFPGQA179cnfGWOWRVruj16z6XyvxvjJwbz0wQZ75XK5tKSb7FNyeIEs4TT4jk+S4dhPeAUC5y+bDYirYgM4GC7uEnztnZyaVWQ7B381AK4Qdrwt51ZqExKbQpTUNn+EjqoTwvqNj4kqx5QUCI0ThS/YkOxJCXmPUWZbhjpCg56i+2aB6CmK2JGhn57K5mj0MNdBXA4/WnwH6XoPWJzK5Nyu2zB3nAZp+S5hpQs+p1vN1/wsjk=
EOF
chmod 600 /root/.ssh/known_hosts

# Install lean-lsp-mcp (MCP tool for lean_run_code and submit_proof)
uv tool install lean-lsp-mcp==0.26.1
ln -sf "$HOME/.local/bin/lean-lsp-mcp" /usr/local/bin/lean-lsp-mcp

# Install wrapper project — editable-includes proof_bench/ and applies the
# model-library -> model-proxy override (see pyproject.toml).
# --upgrade-package ensures we always pick up the latest model-proxy@dev
# (new models, config changes, etc.) regardless of the lockfile pin.
uv sync --upgrade-package model-library

mkdir -p /logs

# Resolve loogle index path (glob must match exactly one file)
index_file=$(ls /opt/loogle/index/mathlib-*.idx 2>/dev/null | head -1)
if [[ -z "$index_file" ]]; then
    echo "ERROR: No loogle index found in /opt/loogle/index/" >&2
    exit 1
fi

# Start loogle daemon in background (loads pre-baked index, ~30-60s)
uv run python -m proof_bench.loogle_daemon \
    --port 8765 \
    --binary /usr/local/bin/loogle \
    --index "$index_file" \
    > /logs/loogle_daemon.log 2>&1 &

# Verify daemon process is alive after brief startup
sleep 2
if ! kill -0 $! 2>/dev/null; then
    echo "ERROR: loogle daemon exited early" >&2
    exit 1
fi

echo "Setup complete"
