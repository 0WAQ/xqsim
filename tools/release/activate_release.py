#!/usr/bin/env python3
"""Atomically activate an existing /usr/local/xqsim executable release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def activate(publish_root: Path, version: str) -> Path:
    publish_root = publish_root.resolve()
    if publish_root in {Path("/"), Path.home().resolve()}:
        raise ValueError(f"unsafe publish root: {publish_root}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", version):
        raise ValueError(f"unsafe release version: {version!r}")

    release = publish_root / "releases" / version
    executable = release / "xqsim"
    manifest_path = release / "manifest.json"
    if not executable.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(f"verified release does not exist: {release}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("artifact_type") != "onefile-executable":
        raise RuntimeError(f"release is not a one-file executable: {release}")
    if str(manifest.get("version")) != version:
        raise RuntimeError(
            f"release manifest version does not match directory: {release}"
        )
    if sha256(executable) != manifest.get("executable_sha256"):
        raise RuntimeError(f"release executable hash mismatch: {release}")

    link = publish_root / "xqsim"
    if link.exists() and not link.is_symlink():
        raise RuntimeError(f"runtime entry is not a symlink: {link}")
    temporary_link = publish_root / f".xqsim.{os.getpid()}"
    try:
        temporary_link.symlink_to(Path("releases", version, "xqsim"))
        os.replace(temporary_link, link)
    finally:
        if temporary_link.is_symlink():
            temporary_link.unlink()
    print(f"{link} -> releases/{version}/xqsim")
    return link


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument(
        "--root", type=Path, default=Path("/usr/local/xqsim")
    )
    args = parser.parse_args()
    activate(args.root, args.version)


if __name__ == "__main__":
    main()
