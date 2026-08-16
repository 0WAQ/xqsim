#!/usr/bin/env python3
"""Smoke-test the frozen executable and external module loading."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path


MODULES = (
    ("alpha", "Alpha", "AlphaBase", False),
    ("operation", "Operation", "OperationBase", False),
    ("stats", "Stats", "StatsBase", False),
    ("provider", "Provider", "ProviderBase", True),
)


def run(command: list[str]) -> str:
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
            completed.returncode, command, output=completed.stdout
        )
    return completed.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    executable = args.executable.resolve()

    version_output = run([str(executable), "--version"])
    if args.expected_version not in version_output:
        raise RuntimeError(
            f"expected version {args.expected_version!r}, got {version_output!r}"
        )

    with tempfile.TemporaryDirectory(prefix="xqsim-external-modules.") as temp:
        root = Path(temp)
        command = [str(executable)]
        for module_type, export_name, base_name, use_factory in MODULES:
            module_dir = root / module_type
            module_dir.mkdir()
            module_path = module_dir / "shared.py"
            source = (
                "import numpy as np\n"
                f"from xqsim.api import {base_name}\n\n"
                f"class {export_name}({base_name}):\n"
                "    smoke_value = int(np.arange(4).sum())\n"
            )
            if use_factory:
                source = (
                    "import numpy as np\n"
                    f"from xqsim.api import {base_name}\n\n"
                    f"class FactoryObject({base_name}):\n"
                    "    smoke_value = int(np.arange(4).sum())\n\n"
                    "def create(*args, **kwargs):\n"
                    "    return FactoryObject(*args, **kwargs)\n"
                )
            module_path.write_text(source, encoding="utf-8")
            command.extend(
                ["--check-module", module_type, str(module_path)]
            )

        module_output = run(command)
        for module_type, _, _, _ in MODULES:
            marker = f"checked {module_type} module"
            if marker not in module_output:
                raise RuntimeError(f"missing smoke output: {marker}")

    print("frozen executable smoke test passed")


if __name__ == "__main__":
    main()
