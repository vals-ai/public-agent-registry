#!/bin/bash
# Install upstream Harbor (the harbor/ submodule next to this script), which contains Terminus 2,
# into its own venv, install tmux, and put one entry script, terminus2-run, on PATH. Run from this
# folder. Safe to run again in the same sandbox after a failed attempt.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

here="$(pwd)"
venv=/opt/terminus2-venv
uv_dir=/opt/terminus2-uv
python_dir=/opt/terminus2-python

# Harbor's lock pins a litellm whose only Linux wheels need glibc (manylinux_2_28), so on a musl
# image (Alpine) the install would fail building it. Stop with a clear message before installing
# anything. musl is Alpine, or an ldd that says so (musl's ldd --version exits 1, so the output is
# captured first).
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

# curl fetches the uv installer. tmux is Terminus 2's terminal; without it, Terminus 2 would try to
# install it (or build it from source) at the start of every run.
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

# uv 0.13.5, checked against a pinned sha256 before it runs. UV_UNMANAGED_INSTALL puts it in
# $uv_dir and leaves PATH and shell profiles alone, so the task's PATH only gains the entry script
# below. curl gives up on a connection after 20 seconds and on a transfer that stays under 1 KB/s
# for 60 seconds, so a stalled download cannot use up the 10-minute install limit.
uv_installer="$(mktemp)"
trap 'rm -f "$uv_installer"' EXIT
curl -fsSL --retry 2 --connect-timeout 20 --speed-limit 1024 --speed-time 60 \
  https://github.com/astral-sh/uv/releases/download/0.13.5/uv-installer.sh -o "$uv_installer"
printf '%s  %s\n' '1c6e7f025499664633ac2dce43a210800510e9ef0625c52e034a8afdf8bf177a' "$uv_installer" | sha256sum -c -
UV_UNMANAGED_INSTALL="$uv_dir" sh "$uv_installer"
uv="$uv_dir/uv"

# Harbor's own lock, without its dev group (which pulls in harbor[cloud]). The interpreter is a
# uv-managed Python (the version in harbor/.python-version) kept next to the venv, not under $HOME
# and not the task's own Python, so the agent runs under any user and survives changes the task
# makes to the system Python. The venv is rebuilt from scratch so an earlier attempt leaves nothing.
rm -rf "$venv"
UV_PROJECT_ENVIRONMENT="$venv" UV_PYTHON_INSTALL_DIR="$python_dir" \
  "$uv" sync --frozen --no-dev --managed-python --project "$here/harbor"
# certifi is exempt from any age limit, so the CA bundle stays current.
"$uv" pip install --python "$venv/bin/python" "certifi>=2026.10.19"

mkdir -p /usr/local/bin
# The entry script has no stdin, so nothing in the agent can wait for input. -E keeps the task's
# PYTHONPATH, PYTHONHOME and other PYTHON* variables away from the agent's interpreter (they still
# reach the shell the agent works in), so a task setting PYTHONPATH cannot shadow Harbor's modules.
printf '#!/bin/bash\nexec %q -E %q "$@" < /dev/null\n' "$venv/bin/python" "$here/run_terminus2.py" > /usr/local/bin/terminus2-run
chmod +x /usr/local/bin/terminus2-run
