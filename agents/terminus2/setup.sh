#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

here="$(pwd)"
venv=/opt/terminus2-venv
uv_dir=/opt/terminus2-uv
python_dir=/opt/terminus2-python

musl=""
ldd_output="$(ldd --version 2>&1 || true)"
case "$ldd_output" in
  *[Mm][Uu][Ss][Ll]*) musl=1 ;;
esac
if [ -f /etc/alpine-release ]; then
  musl=1
fi
if [ -n "$musl" ]; then
  echo "Terminus 2's dependencies (litellm) need glibc; this image uses musl" >&2
  exit 1
fi

missing=()
for tool in curl tmux; do
  if ! command -v "$tool" &> /dev/null; then
    missing+=("$tool")
  fi
done
if [ "${#missing[@]}" -gt 0 ]; then
  if command -v apt-get &> /dev/null; then
    apt-get update && apt-get install -y "${missing[@]}"
  elif command -v dnf &> /dev/null; then
    dnf install -y "${missing[@]}"
  elif command -v yum &> /dev/null; then
    yum install -y "${missing[@]}"
  elif command -v apk &> /dev/null; then
    apk add --no-cache "${missing[@]}"
  else
    echo "cannot install ${missing[*]}: no apt-get, dnf, yum or apk" >&2
    exit 1
  fi
fi

uv_installer="$(mktemp)"
trap 'rm -f "$uv_installer"' EXIT
curl -fsSL --retry 2 --connect-timeout 20 --speed-limit 1024 --speed-time 60 \
  https://github.com/astral-sh/uv/releases/download/0.13.5/uv-installer.sh -o "$uv_installer"
printf '%s  %s\n' '1c6e7f025499664633ac2dce43a210800510e9ef0625c52e034a8afdf8bf177a' "$uv_installer" | sha256sum -c -
UV_UNMANAGED_INSTALL="$uv_dir" sh "$uv_installer"
uv="$uv_dir/uv"

rm -rf "$venv"
UV_PROJECT_ENVIRONMENT="$venv" UV_PYTHON_INSTALL_DIR="$python_dir" \
  "$uv" sync --frozen --no-dev --managed-python --project "$here/harbor"
"$uv" pip install --python "$venv/bin/python" "certifi>=2026.10.19"

mkdir -p /usr/local/bin
printf '#!/bin/bash\nexec %q -E %q "$@" < /dev/null\n' "$venv/bin/python" "$here/run_terminus2.py" > /usr/local/bin/terminus2-run
chmod +x /usr/local/bin/terminus2-run
