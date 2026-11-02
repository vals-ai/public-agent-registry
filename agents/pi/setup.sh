#!/bin/bash
# Install upstream pi (the pi/ submodule next to this script) from its pinned release and put one
# entry script, pi-run, on PATH. Run from this folder.
#
# pi and the jq that run.sh and finish.sh use go in /opt/pi, which is not on PATH, so the task only
# gains the entry script. Both downloads are checked against checksums.txt before anything is
# installed. pi's release binaries are linked against glibc, so on a musl image (Alpine) this stops
# with a clear message before installing anything. Safe to run again after a failed attempt.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

here="$(pwd)"
install_dir=/opt/pi
release=https://github.com/earendil-works/pi/releases/download

# Release assets are named pi-linux-x64.tar.gz and pi-linux-arm64.tar.gz.
case "$(uname -m)" in
  x86_64) arch=x64 jq_arch=amd64 ;;
  aarch64 | arm64) arch=arm64 jq_arch=arm64 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

# musl is Alpine, or an ldd that says so (musl's ldd --version prints "musl libc" and exits 1, so the
# output is captured first and a pipe never sees that exit code).
musl=""
ldd_output="$(ldd --version 2>&1 || true)"
case "$ldd_output" in
  *[Mm][Uu][Ss][Ll]*) musl=1 ;;
esac
if [ -f /etc/alpine-release ]; then
  musl=1
fi
if [ -n "$musl" ]; then
  echo "pi's release binaries need glibc; this image uses musl" >&2
  exit 1
fi

missing=()
for tool in curl tar; do
  if ! command -v "$tool" &> /dev/null; then
    missing+=("$tool")
  fi
done
if [ "${#missing[@]}" -gt 0 ]; then
  apt-get update && apt-get install -y "${missing[@]}" || yum install -y "${missing[@]}" || apk add --no-cache "${missing[@]}"
fi

asset="pi-linux-${arch}.tar.gz"
jq_asset="jq-linux-${jq_arch}"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# download URL NAME: fetch URL into $work/NAME and check it against NAME's line in checksums.txt.
# The line must exist (an empty check would pass), and nothing is used before this succeeds. curl
# gives up on a connection after 20 seconds and on a transfer after 240, so a hung download cannot
# use up the 10-minute install limit.
download() {
  local url="$1" name="$2" line
  line="$(awk -v name="$name" '$2 == name { print; exit }' "$here/checksums.txt")"
  if [ -z "$line" ]; then
    echo "no sha256 for $name in checksums.txt" >&2
    return 1
  fi
  curl -fsSL --retry 2 --connect-timeout 20 --max-time 240 --retry-max-time 240 "$url" -o "$work/$name"
  (cd "$work" && printf '%s\n' "$line" | sha256sum -c -)
}

mkdir -p "$install_dir"

# jq 1.8.2 static binary: reads upstream.json and package.json here, and the session in finish.sh.
download "https://github.com/jqlang/jq/releases/download/jq-1.8.2/$jq_asset" "$jq_asset"
install -m 0755 "$work/$jq_asset" "$install_dir/jq"
jq="$install_dir/jq"

tag="$("$jq" -r .tag "$here/upstream.json")"
download "$release/$tag/$asset" "$asset"

# The tarball is one pi/ folder: the pi executable and the files it loads from beside itself. It stays
# whole, and it is replaced rather than merged into so an earlier attempt leaves nothing behind.
rm -rf "$install_dir/pi"
tar -xzf "$work/$asset" -C "$install_dir" --no-same-owner
chmod -R a+rX "$install_dir/pi"
if [ ! -x "$install_dir/pi/pi" ]; then
  echo "$asset did not contain pi/pi" >&2
  exit 1
fi

# The binary has to be the release of the code in the submodule, or the pin and the install have
# drifted apart.
package="$here/pi/packages/coding-agent/package.json"
if [ ! -f "$package" ]; then
  echo "missing $package: the pi submodule was not checked out" >&2
  exit 1
fi
expected="$("$jq" -r .version "$package")"
installed="$(PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0 "$install_dir/pi/pi" --version)" || {
  echo "$install_dir/pi/pi --version failed" >&2
  exit 1
}
if [ "$installed" != "$expected" ]; then
  echo "pi version mismatch: installed $installed, submodule $expected" >&2
  exit 1
fi

mkdir -p /logs /usr/local/bin
printf '#!/bin/bash\nexec bash %q "$@"\n' "$here/run.sh" > /usr/local/bin/pi-run
chmod +x /usr/local/bin/pi-run
