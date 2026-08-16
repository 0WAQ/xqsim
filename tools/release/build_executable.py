#!/usr/bin/env python3
"""Freeze an installed binary xqsim wheel into one Linux executable."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path

from release_manifest import (
    COMPILED_MODULES,
    FROZEN_HIDDEN_IMPORTS,
    PYINSTALLER_REQUIREMENT,
)


RELEASE_DIR = Path(__file__).resolve().parent
ENTRY_POINT = RELEASE_DIR / "executable_main.py"


def run(command: list[str], *, cwd: Path) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_environment() -> str:
    expected_version = PYINSTALLER_REQUIREMENT.split("==", 1)[1]
    actual_version = importlib.metadata.version("pyinstaller")
    if actual_version != expected_version:
        raise RuntimeError(
            f"PyInstaller {expected_version} is required, got {actual_version}"
        )

    for module_name in COMPILED_MODULES:
        module = importlib.import_module(module_name)
        if Path(module.__file__).suffix not in {".so", ".pyd"}:
            raise RuntimeError(
                f"{module_name} is not from the binary wheel: {module.__file__}"
            )
    return actual_version


def rewrite_checksums(output: Path, manifest: dict[str, object]) -> None:
    paths = [
        output / "constraints.txt",
        output / "manifest.json",
        output / str(manifest["executable"]),
        output / "wheels" / str(manifest["wheel"]),
    ]
    audit_report = output / "auditwheel.txt"
    if audit_report.is_file():
        paths.append(audit_report)
    warning_report = output / "pyinstaller-warnings.txt"
    if warning_report.is_file():
        paths.append(warning_report)
    lines = [
        f"{sha256(path)}  {path.relative_to(output)}"
        for path in sorted(paths)
    ]
    (output / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def build(output: Path, keep_work: bool = False) -> Path:
    pyinstaller_version = validate_environment()
    output = output.resolve()
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    executable_dir = output / "executable"
    if executable_dir.exists() and any(executable_dir.iterdir()):
        raise FileExistsError(
            f"executable output must be new or empty: {executable_dir}"
        )
    executable_dir.mkdir(exist_ok=True)

    work_root = output / ".pyinstaller"
    if work_root.exists():
        raise FileExistsError(f"PyInstaller work path already exists: {work_root}")
    work_root.mkdir()

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "xqsim",
        "--distpath",
        str(executable_dir),
        "--workpath",
        str(work_root / "build"),
        "--specpath",
        str(work_root / "spec"),
        "--copy-metadata",
        "xqsim",
    ]
    for module_name in FROZEN_HIDDEN_IMPORTS:
        command.extend(["--hidden-import", module_name])
    command.append(str(ENTRY_POINT))
    run(command, cwd=work_root)

    warning_source = work_root / "build" / "xqsim" / "warn-xqsim.txt"
    warning_output = output / "pyinstaller-warnings.txt"
    if warning_source.is_file():
        shutil.copy2(warning_source, warning_output)

    executable = executable_dir / "xqsim"
    if not executable.is_file():
        raise FileNotFoundError(executable)
    with executable.open("rb") as reader:
        executable_magic = reader.read(4)
    if executable_magic != b"\x7fELF":
        raise RuntimeError(f"not a Linux ELF executable: {executable}")
    executable.chmod(0o755)

    executable_metadata = {
        "artifact_type": "onefile-executable",
        "executable": str(executable.relative_to(output)),
        "executable_sha256": sha256(executable),
        "executable_size": executable.stat().st_size,
        "pyinstaller": pyinstaller_version,
        "runtime_home_default": "/usr/local/xqsim",
    }
    if warning_output.is_file():
        executable_metadata["pyinstaller_warnings"] = warning_output.name
    manifest.update(executable_metadata)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rewrite_checksums(output, manifest)

    if not keep_work:
        shutil.rmtree(work_root)
    print(f"one-file executable: {executable}")
    return executable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()
    build(args.output, args.keep_work)


if __name__ == "__main__":
    main()
