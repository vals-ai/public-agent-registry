"""Install pinned native artifacts without relying on a global Node installation."""

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"


def download(url, target, sha256):
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as output:
        shutil.copyfileobj(response, output)
    with target.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != sha256:
        target.unlink()
        raise RuntimeError("Native artifact checksum mismatch")


def main():
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
        raise RuntimeError("This integration currently supports Linux x86_64 with glibc only")
    metadata = json.loads((ROOT / "upstream.json").read_text())
    if metadata["agent"] not in ("pi", "opencode", "omp"):
        raise ValueError("Unknown native agent")
    RUNTIME.mkdir(exist_ok=True)
    if metadata["agent"] == "omp":
        pin = metadata["binary"]
        url = f"https://build.stencil.so/api/products/omp/versions/{metadata['version']}/linux-x86_64"
        with urllib.request.urlopen(url, timeout=60) as response:
            release = json.load(response)
        if release["file"]["sha256"] != pin["sha256"] or release["build"]["commit"] != metadata["commit"]:
            raise RuntimeError("OMP release no longer matches the pinned artifact")
        with tempfile.TemporaryDirectory(dir=RUNTIME) as temporary:
            binary = Path(temporary) / "omp"
            download(release["download"], binary, pin["sha256"])
            binary.chmod(0o755)
            binary.replace(RUNTIME / "omp")
        command = [str(RUNTIME / "omp"), "--version"]
    else:
        version = "22.19.0"
        name = f"node-v{version}-linux-x64"
        with tempfile.TemporaryDirectory(dir=RUNTIME) as temporary:
            archive = Path(temporary) / "node.tar.xz"
            download(
                f"https://nodejs.org/dist/v{version}/{name}.tar.xz",
                archive,
                "c0649af18e6a24f6fe5535a3e86b341dd49a8e71117c8b68bde973ef834f16f2",
            )
            with tarfile.open(archive) as source:
                source.extractall(temporary, filter="data")
            if (RUNTIME / "node").exists():
                shutil.rmtree(RUNTIME / "node")
            (Path(temporary) / name).rename(RUNTIME / "node")
        env = {**os.environ, "PATH": str(RUNTIME / "node/bin") + os.pathsep + os.environ.get("PATH", ""),
               "npm_config_cache": str(RUNTIME / "npm-cache")}
        subprocess.run([str(RUNTIME / "node/bin/npm"), "ci", "--no-audit", "--no-fund", "--ignore-scripts"],
                       cwd=ROOT, env=env, check=True)
        if metadata["agent"] == "opencode":
            subprocess.run([str(RUNTIME / "node/bin/node"), "postinstall.mjs"],
                           cwd=ROOT / "node_modules/opencode-ai", env=env, check=True)
            command = [str(ROOT / "node_modules/opencode-ai/bin/opencode.exe"), "--version"]
        else:
            command = [str(RUNTIME / "node/bin/node"),
                       str(ROOT / "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"), "--version"]
    resolved = subprocess.check_output(command, text=True).strip()
    if not re.search(r"(?<![\d.])" + re.escape(metadata["version"]) + r"(?![\d.])", resolved):
        raise RuntimeError("Installed CLI does not report the pinned version")
    print(f"Installed {metadata['agent']} {resolved}")


if __name__ == "__main__":
    main()
