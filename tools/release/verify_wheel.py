#!/usr/bin/env python3
"""Statically verify the source/binary boundary of an xqsim wheel."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from release_manifest import (
    COMPILED_MODULES,
    EXCLUDED_MODULES,
    SOURCE_MODULES,
)


BINARY_SUFFIXES = (".so", ".pyd")
PACKAGE_MODULES = {
    "xqsim",
    "xqsim.base",
    "xqsim.data",
    "xqsim.manager",
    "xqsim.modules",
}


def source_member(module_name: str) -> str:
    path = module_name.replace(".", "/")
    if module_name in PACKAGE_MODULES:
        return f"{path}/__init__.py"
    return f"{path}.py"


def verify_wheel(wheel: Path) -> None:
    errors: list[str] = []
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())

        for module_name in SOURCE_MODULES:
            expected = source_member(module_name)
            if expected not in names:
                errors.append(f"missing source module: {expected}")

        for module_name in COMPILED_MODULES:
            prefix = module_name.replace(".", "/") + "."
            binaries = [
                name
                for name in names
                if name.startswith(prefix) and name.endswith(BINARY_SUFFIXES)
            ]
            if len(binaries) != 1:
                errors.append(
                    f"expected one binary for {module_name}, found {sorted(binaries)}"
                )
            leaked_source = module_name.replace(".", "/") + ".py"
            if leaked_source in names:
                errors.append(f"compiled source leaked into wheel: {leaked_source}")

        for module_name in EXCLUDED_MODULES:
            source = source_member(module_name)
            binary_prefix = module_name.replace(".", "/") + "."
            leaked = source in names or any(
                name.startswith(binary_prefix) for name in names
            )
            if leaked:
                errors.append(f"excluded module leaked into wheel: {module_name}")

        metadata_files = [
            name for name in names if name.endswith(".dist-info/METADATA")
        ]
        entry_files = [
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        ]
        if len(metadata_files) != 1:
            errors.append(f"expected one METADATA file, found {metadata_files}")
        if len(entry_files) != 1:
            errors.append(f"expected one entry_points.txt, found {entry_files}")
        elif "xqsim = xqsim.xqsim_run:main" not in archive.read(
            entry_files[0]
        ).decode():
            errors.append("xqsim console entry point is missing")

    if errors:
        raise RuntimeError("wheel verification failed:\n- " + "\n- ".join(errors))
    print(
        f"verified {wheel.name}: {len(COMPILED_MODULES)} binary modules, "
        f"{len(SOURCE_MODULES)} source modules"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    verify_wheel(args.wheel.resolve())


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        raise
