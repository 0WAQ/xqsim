#!/usr/bin/env python3
"""Deploy a framework artifact and/or allowlisted public research modules."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from publish_release import (
    initialize_public_dirs,
    publish,
    resolve_executable,
)


RELEASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = RELEASE_DIR.parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "public_modules" / "deploy.json"
PUBLIC_TYPES = {"operation", "stats", "provider", "config"}
MODULE_TYPES = PUBLIC_TYPES - {"config"}
DEPLOYMENT_RECORD = "public-modules.json"
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


@dataclass(frozen=True)
class ModuleEntry:
    module_type: str
    source: Path
    source_label: str
    target_name: str

    @property
    def relative_target(self) -> Path:
        return Path(self.module_type, self.target_name)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_root(path: Path) -> Path:
    root = path.resolve()
    if root in {Path("/"), Path.home().resolve(), REPO_ROOT.resolve()}:
        raise ValueError(f"unsafe deployment root: {root}")
    if not root.is_dir():
        raise FileNotFoundError(root)
    return root


def load_manifest(manifest_path: Path, source_root: Path) -> list[ModuleEntry]:
    manifest_path = manifest_path.resolve()
    source_root = source_root.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("public-module manifest schema_version must be 1")
    raw_modules = payload.get("modules")
    if not isinstance(raw_modules, list):
        raise TypeError("public-module manifest modules must be a list")

    entries: list[ModuleEntry] = []
    targets: set[Path] = set()
    for index, raw in enumerate(raw_modules):
        if not isinstance(raw, dict):
            raise TypeError(f"module entry {index} must be an object")
        module_type = str(raw.get("type", "")).lower()
        if module_type not in PUBLIC_TYPES:
            raise ValueError(
                f"module entry {index} has unsupported type {module_type!r}"
            )

        source_label = str(raw.get("source", ""))
        source_relative = Path(source_label)
        if (
            not source_label
            or source_relative.is_absolute()
            or ".." in source_relative.parts
        ):
            raise ValueError(
                f"module entry {index} has unsafe source {source_label!r}"
            )
        source = (source_root / source_relative).resolve()
        if not source.is_relative_to(source_root) or not source.is_file():
            raise FileNotFoundError(source)
        if module_type in MODULE_TYPES and source.suffix != ".py":
            raise ValueError(f"{module_type} source must be a .py file: {source}")

        target_name = str(raw.get("target", source.name))
        if (
            Path(target_name).name != target_name
            or not SAFE_NAME.fullmatch(target_name)
        ):
            raise ValueError(
                f"module entry {index} has unsafe target {target_name!r}"
            )
        relative_target = Path(module_type, target_name)
        if relative_target in targets:
            raise ValueError(f"duplicate deployment target: {relative_target}")
        targets.add(relative_target)
        entries.append(
            ModuleEntry(module_type, source, source_label, target_name)
        )
    return entries


def artifact_executable(artifact_dir: Path) -> Path:
    artifact_dir = artifact_dir.resolve()
    manifest = json.loads(
        (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    )
    return resolve_executable(artifact_dir, manifest)


def validate_modules(runtime: Path, entries: list[ModuleEntry]) -> None:
    runtime = runtime.resolve()
    if not runtime.is_file() or not os.access(runtime, os.X_OK):
        raise FileNotFoundError(f"xqsim runtime is not executable: {runtime}")
    command = [str(runtime)]
    for entry in entries:
        if entry.module_type not in MODULE_TYPES:
            continue
        command.extend(
            ["--check-module", entry.module_type, str(entry.source)]
        )
    if len(command) == 1:
        return
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(completed.stdout, end="")
    if completed.returncode:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
        )


def git_commit() -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def managed_git_changes(
    manifest_path: Path,
    entries: list[ModuleEntry],
) -> list[str]:
    candidates = [
        manifest_path.resolve(),
        Path(__file__).resolve(),
        RELEASE_DIR / "publish_release.py",
        RELEASE_DIR / "PUBLIC_MODULES.md",
        *(entry.source for entry in entries),
    ]
    relative_paths = sorted(
        {
            str(path.relative_to(REPO_ROOT))
            for path in candidates
            if path.is_relative_to(REPO_ROOT)
        }
    )
    if not relative_paths:
        return []
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            *relative_paths,
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return completed.stdout.splitlines()


def deploy_modules(
    root: Path,
    manifest_path: Path,
    entries: list[ModuleEntry],
) -> Path:
    initialize_public_dirs(root)
    staging = Path(tempfile.mkdtemp(prefix=".public-modules.", dir=root))
    deployed: list[dict[str, object]] = []
    try:
        for entry in entries:
            staged = staging / entry.relative_target
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry.source, staged)
            staged.chmod(0o444)

        for entry in entries:
            destination = root / entry.relative_target
            if destination.is_symlink() or (
                destination.exists() and not destination.is_file()
            ):
                raise RuntimeError(
                    f"deployment target is not a regular file: {destination}"
                )

        for entry in entries:
            destination = root / entry.relative_target
            source_hash = sha256(entry.source)
            changed = (
                not destination.is_file()
                or sha256(destination) != source_hash
            )
            if changed:
                os.replace(staging / entry.relative_target, destination)
                action = "deployed"
            elif destination.stat().st_mode & 0o777 != 0o444:
                destination.chmod(0o444)
                action = "permissions-updated"
            else:
                action = "unchanged"
            print(f"{action}: {destination} sha256={source_hash}")
            deployed.append(
                {
                    "type": entry.module_type,
                    "source": entry.source_label,
                    "target": str(entry.relative_target),
                    "sha256": source_hash,
                }
            )

        try:
            manifest_label = str(manifest_path.resolve().relative_to(REPO_ROOT))
        except ValueError:
            manifest_label = str(manifest_path.resolve())
        record = {
            "schema_version": 1,
            "deployed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_git_commit": git_commit(),
            "source_manifest": manifest_label,
            "modules": deployed,
        }
        record_path = root / DEPLOYMENT_RECORD
        temporary_record = root / f".{DEPLOYMENT_RECORD}.{os.getpid()}"
        try:
            temporary_record.write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary_record.chmod(0o444)
            os.replace(temporary_record, record_path)
        finally:
            if temporary_record.is_file():
                temporary_record.unlink()
        return record_path
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path("/usr/local/xqsim")
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--artifact",
        type=Path,
        help="optional verified release artifact directory to publish first",
    )
    parser.add_argument(
        "--runtime",
        type=Path,
        help="runtime used to validate modules; defaults to artifact or ROOT/xqsim",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="validate the manifest and imports without writing",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow deployment from uncommitted managed sources",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = safe_root(args.root)
    entries = load_manifest(args.manifest, args.source_root)
    if args.runtime is not None:
        runtime = args.runtime
    elif args.artifact is not None:
        runtime = artifact_executable(args.artifact)
    else:
        runtime = root / "xqsim"

    validate_modules(runtime, entries)
    print(f"validated {len(entries)} public module entries")
    if args.check_only:
        return

    changes = managed_git_changes(args.manifest, entries)
    if changes and not args.allow_dirty:
        details = "\n".join(changes)
        raise RuntimeError(
            "refusing to deploy uncommitted managed sources; "
            "commit them or pass --allow-dirty for a local test:\n"
            + details
        )

    if args.artifact is not None:
        publish(args.artifact, root)
    record_path = deploy_modules(root, args.manifest, entries)
    print(f"public module deployment record: {record_path}")


if __name__ == "__main__":
    main()
