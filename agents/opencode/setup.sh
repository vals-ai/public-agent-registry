#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

here="$(pwd)"
install_dir=/opt/opencode
release=https://github.com/anomalyco/opencode/releases/download

missing=()
for tool in curl tar; do
  if ! command -v "$tool" &> /dev/null; then
    missing+=("$tool")
  fi
done
if [ "${#missing[@]}" -gt 0 ]; then
  apt-get update && apt-get install -y "${missing[@]}" || yum install -y "${missing[@]}" || apk add --no-cache "${missing[@]}"
fi

case "$(uname -m)" in
  x86_64) arch=x64 jq_arch=amd64 ;;
  aarch64 | arm64) arch=arm64 jq_arch=arm64 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

musl=""
ldd_output="$(ldd --version 2>&1 || true)"
case "$ldd_output" in
  *[Mm][Uu][Ss][Ll]*) musl="-musl" ;;
esac
if [ -f /etc/alpine-release ]; then
  musl="-musl"
fi
if [ -n "$musl" ] && command -v apk &> /dev/null; then
  apk add --no-cache libstdc++ libgcc
fi

baseline=""
if [ "$arch" = x64 ] && ! grep -qwi avx2 /proc/cpuinfo 2> /dev/null; then
  baseline="-baseline"
fi

asset="opencode-linux-${arch}${baseline}${musl}.tar.gz"
jq_asset="jq-linux-${jq_arch}"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

download() {
  local url="$1" name="$2" line
  line="$(awk -v name="$name" '$2 == name { print; exit }' "$here/checksums.txt")"
  if [ -z "$line" ]; then
    echo "no sha256 for $name in checksums.txt" >&2
    return 1
  fi
  curl -fsSL --retry 3 "$url" -o "$work/$name"
  (cd "$work" && printf '%s\n' "$line" | sha256sum -c -)
}

mkdir -p "$install_dir"

download "https://github.com/jqlang/jq/releases/download/jq-1.8.2/$jq_asset" "$jq_asset"
install -m 0755 "$work/$jq_asset" "$install_dir/jq"
jq="$install_dir/jq"

tag="$("$jq" -r .tag "$here/upstream.json")"
download "$release/$tag/$asset" "$asset"
tar -xzf "$work/$asset" -C "$install_dir"
chmod a+rx "$install_dir/opencode"

package="$here/opencode/packages/opencode/package.json"
if [ ! -f "$package" ]; then
  echo "missing $package: the opencode submodule was not checked out" >&2
  exit 1
fi
expected="$("$jq" -r .version "$package")"
installed="$(OPENCODE_DISABLE_AUTOUPDATE=1 "$install_dir/opencode" --version)"
if [ "$installed" != "$expected" ]; then
  echo "opencode version mismatch: installed $installed, submodule $expected" >&2
  exit 1
fi

mkdir -p /logs /usr/local/bin
printf '#!/bin/bash\nexec bash %q "$@"\n' "$here/run.sh" > /usr/local/bin/opencode-run
chmod +x /usr/local/bin/opencode-run
