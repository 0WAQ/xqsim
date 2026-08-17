#!/usr/bin/env python3
"""Publish one verified executable and initialize public module directories."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path


PUBLIC_DIRS = ("operation", "stats", "provider", "portfolio", "config")
DATA_DIRS = (
    Path("data", "futures", "cc"),
    Path("data", "futures", "cc_2024"),
)
PUBLIC_README = Path(__file__).with_name("PUBLIC_MODULES.md")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_version(version: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", version):
        raise ValueError(f"unsafe release version: {version!r}")


def resolve_executable(
    artifact_dir: Path, manifest: dict[str, object]
) -> Path:
    if manifest.get("artifact_type") != "onefile-executable":
        raise RuntimeError("artifact is not a verified one-file executable")
    relative = Path(str(manifest["executable"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe executable path in manifest: {relative}")
    executable = artifact_dir / relative
    if not executable.is_file():
        raise FileNotFoundError(executable)
    actual_hash = sha256(executable)
    if actual_hash != manifest.get("executable_sha256"):
        raise RuntimeError(
            f"executable hash mismatch: {actual_hash} != "
            f"{manifest.get('executable_sha256')}"
        )
    with executable.open("rb") as reader:
        executable_magic = reader.read(4)
    if executable_magic != b"\x7fELF":
        raise RuntimeError(f"not a Linux ELF executable: {executable}")
    return executable


def initialize_public_dirs(publish_root: Path) -> None:
    for name in PUBLIC_DIRS:
        path = publish_root / name
        if path.exists() and not path.is_dir():
            raise RuntimeError(f"public module path is not a directory: {path}")
        path.mkdir(exist_ok=True)
        path.chmod(0o755)
    for relative in DATA_DIRS:
        path = publish_root / relative
        if path.exists() and not path.is_dir():
            raise RuntimeError(f"runtime data path is not a directory: {path}")
        path.mkdir(parents=True, exist_ok=True)
    readme = publish_root / "README.md"
    if readme.exists() and not readme.is_file():
        raise RuntimeError(f"runtime README path is not a file: {readme}")
    temporary_readme = publish_root / f".README.md.{os.getpid()}"
    try:
        shutil.copy2(PUBLIC_README, temporary_readme)
        temporary_readme.chmod(0o444)
        os.replace(temporary_readme, readme)
    finally:
        if temporary_readme.is_file():
            temporary_readme.unlink()


def activate(publish_root: Path, version: str) -> Path:
    executable = publish_root / "releases" / version / "xqsim"
    if not executable.is_file():
        raise FileNotFoundError(executable)
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
    return link


def publish(artifact_dir: Path, publish_root: Path) -> Path:
    artifact_dir = artifact_dir.resolve()
    publish_root = publish_root.resolve()
    if publish_root in {Path("/"), Path.home().resolve()}:
        raise ValueError(f"unsafe publish root: {publish_root}")
    if not publish_root.is_dir():
        raise FileNotFoundError(publish_root)

    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest["version"])
    validate_version(version)
    executable = resolve_executable(artifact_dir, manifest)

    releases = publish_root / "releases"
    releases.mkdir(exist_ok=True)
    initialize_public_dirs(publish_root)
    runtime_entry = publish_root / "xqsim"
    if runtime_entry.exists() and not runtime_entry.is_symlink():
        raise RuntimeError(
            f"runtime entry is not a symlink: {runtime_entry}"
        )
    destination = releases / version
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(
            f"release already exists and is immutable: {destination}"
        )

    temporary = Path(tempfile.mkdtemp(prefix=f".{version}.", dir=releases))
    try:
        published_executable = temporary / "xqsim"
        shutil.copy2(executable, published_executable)
        shutil.copy2(manifest_path, temporary / "manifest.json")
        checksums = (
            f"{sha256(published_executable)}  xqsim\n"
            f"{sha256(temporary / 'manifest.json')}  manifest.json\n"
        )
        (temporary / "SHA256SUMS").write_text(
            checksums, encoding="utf-8"
        )
        published_executable.chmod(0o555)
        (temporary / "manifest.json").chmod(0o444)
        (temporary / "SHA256SUMS").chmod(0o444)
        temporary.chmod(0o555)
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    link = activate(publish_root, version)
    print(f"published {version} to {destination}")
    print(f"{link} -> releases/{version}/xqsim")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("publish_root", type=Path)
    args = parser.parse_args()
    publish(args.artifact_dir, args.publish_root)


if __name__ == "__main__":
    main()
