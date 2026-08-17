#!/usr/bin/env python3
"""Build a versioned binary wheel from an explicit xqsim module manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tomllib
from pathlib import Path

from release_manifest import (
    BUILD_REQUIRES,
    COMPILED_MODULES,
    EXCLUDED_MODULES,
    PUBLIC_SOURCE_MIRRORS,
    SOURCE_MODULES,
    SUPPORTED_PLATFORMS,
    SUPPORTED_PYTHON,
)
from verify_wheel import verify_wheel


RELEASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = RELEASE_DIR.parent.parent
PACKAGE_ROOT = REPO_ROOT / "xqsim"


def run(command: list[str], *, cwd: Path | None = None) -> str:
    print("+", " ".join(command), flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.returncode:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
        )
    return completed.stdout


def module_path(module_name: str) -> Path:
    relative = Path(*module_name.split("."))
    package_init = REPO_ROOT / relative / "__init__.py"
    if package_init.is_file():
        return package_init
    return (REPO_ROOT / relative).with_suffix(".py")


def discovered_modules() -> set[str]:
    modules: set[str] = set()
    for path in PACKAGE_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(REPO_ROOT)
        if path.name == "__init__.py":
            modules.add(".".join(relative.parent.parts))
        else:
            modules.add(".".join(relative.with_suffix("").parts))
    return modules


def validate_manifest() -> None:
    source = set(SOURCE_MODULES)
    compiled = set(COMPILED_MODULES)
    excluded = set(EXCLUDED_MODULES)
    overlap = (source & compiled) | (source & excluded) | (compiled & excluded)
    if overlap:
        raise RuntimeError(f"modules classified twice: {sorted(overlap)}")

    actual = discovered_modules()
    classified = source | compiled | excluded
    missing = actual - classified
    stale = classified - actual
    if missing or stale:
        details = []
        if missing:
            details.append(f"unclassified modules: {sorted(missing)}")
        if stale:
            details.append(f"manifest entries without source: {sorted(stale)}")
        raise RuntimeError("; ".join(details))

    for module_name, public_relative in PUBLIC_SOURCE_MIRRORS.items():
        package_source = module_path(module_name)
        public_source = REPO_ROOT / public_relative
        if not public_source.is_file():
            raise RuntimeError(f"public source mirror is missing: {public_source}")
        if package_source.read_bytes() != public_source.read_bytes():
            raise RuntimeError(
                "packaging mirror differs from authoritative public source: "
                f"{package_source} != {public_source}"
            )


def validate_platform() -> None:
    python_version = sys.version_info[:2]
    target = (platform.system(), platform.machine().lower())
    if python_version != SUPPORTED_PYTHON:
        raise RuntimeError(
            f"binary release requires CPython {SUPPORTED_PYTHON[0]}."
            f"{SUPPORTED_PYTHON[1]}, got {python_version[0]}.{python_version[1]}"
        )
    if platform.python_implementation() != "CPython":
        raise RuntimeError("binary release currently supports CPython only")
    if target not in SUPPORTED_PLATFORMS:
        raise RuntimeError(f"unsupported release platform: {target}")

    python_header = Path(sysconfig.get_path("include")) / "Python.h"
    if not python_header.is_file():
        raise RuntimeError(
            f"Python development header not found: {python_header}; "
            "use a CPython build with development headers"
        )


def load_project_metadata(version: str) -> dict[str, object]:
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    project = pyproject["project"]
    return {
        "version": version,
        "description": project["description"],
        "requires_python": project["requires-python"],
        "dependencies": project["dependencies"],
        "compiled_modules": list(COMPILED_MODULES),
    }


def source_version() -> str:
    namespace: dict[str, str] = {}
    exec((PACKAGE_ROOT / "version.py").read_text(encoding="utf-8"), namespace)
    return namespace["VERSION"]


def validate_version(version: str) -> None:
    # Sufficient PEP 440 subset for normal and internal local versions.
    pattern = r"[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc|\.dev)[0-9]+)?"
    pattern += r"(?:\+[a-zA-Z0-9.]+)?"
    if not re.fullmatch(pattern, version):
        raise ValueError(f"unsupported release version: {version!r}")


def prepare_stage(stage: Path, metadata: dict[str, object]) -> None:
    source_root = stage / "src"
    cython_root = stage / "cython_src"

    for module_name in SOURCE_MODULES:
        source = module_path(module_name)
        destination = source_root / source.relative_to(REPO_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if module_name == "xqsim.version":
            destination.write_text(
                f'VERSION = "{metadata["version"]}"\n__version__ = VERSION\n',
                encoding="utf-8",
            )
        else:
            shutil.copy2(source, destination)

    for module_name in COMPILED_MODULES:
        source = module_path(module_name)
        destination = cython_root / source.relative_to(REPO_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    shutil.copy2(RELEASE_DIR / "setup" / "setup.py", stage / "setup.py")
    (stage / "release_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    build_requires = ",\n    ".join(json.dumps(item) for item in BUILD_REQUIRES)
    (stage / "pyproject.toml").write_text(
        "[build-system]\n"
        f"requires = [\n    {build_requires},\n]\n"
        'build-backend = "setuptools.build_meta"\n',
        encoding="utf-8",
    )


def export_constraints(destination: Path) -> None:
    command = [
        shutil.which("uv") or "uv",
        "export",
        "--frozen",
        "--no-dev",
        "--no-emit-project",
        "--no-hashes",
        "--output-file",
        str(destination),
    ]
    run(command, cwd=REPO_ROOT)


def git_value(*args: str) -> str | None:
    try:
        return run(["git", *args], cwd=REPO_ROOT).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finalize_artifacts(
    output: Path,
    wheel: Path,
    version: str,
    auditwheel_platform: str | None,
) -> None:
    verify_wheel(wheel)
    commit = git_value("rev-parse", "HEAD")
    status = git_value("status", "--porcelain")
    libc_name, libc_version = platform.libc_ver()
    manifest = {
        "distribution": "xqsim",
        "version": version,
        "source_version": source_version(),
        "git_commit": commit,
        "git_dirty": bool(status),
        "built_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "soabi": sysconfig.get_config_var("SOABI"),
        "system": platform.system(),
        "machine": platform.machine(),
        "libc": {"name": libc_name, "version": libc_version},
        "auditwheel_platform": auditwheel_platform,
        "wheel": wheel.name,
        "wheel_sha256": sha256(wheel),
        "source_modules": list(SOURCE_MODULES),
        "compiled_modules": list(COMPILED_MODULES),
        "excluded_modules": EXCLUDED_MODULES,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    checksummed = [wheel, output / "constraints.txt", output / "manifest.json"]
    lines = [
        f"{sha256(path)}  {path.relative_to(output)}" for path in checksummed
    ]
    (output / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def build(args: argparse.Namespace) -> Path:
    validate_manifest()
    validate_platform()
    version = args.version or source_version()
    validate_version(version)

    output = args.output.resolve()
    if output in {Path("/"), Path.home().resolve(), REPO_ROOT.resolve()}:
        raise ValueError(f"unsafe output directory: {output}")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"release output must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    stage = output / ".stage"
    raw_wheels = output / "raw-wheels"
    wheels = output / "wheels"
    stage.mkdir()
    raw_wheels.mkdir()
    wheels.mkdir()

    metadata = load_project_metadata(version)
    prepare_stage(stage, metadata)
    export_constraints(output / "constraints.txt")

    command = [
        shutil.which("uv") or "uv",
        "build",
        "--wheel",
        # raw_wheels is freshly created above, so version-specific cleanup
        # and gitignore flags are unnecessary.
        "--python",
        sys.executable,
        "--out-dir",
        str(raw_wheels),
    ]
    if args.no_build_isolation:
        command.append("--no-build-isolation")
    command.append(str(stage))
    run(command, cwd=REPO_ROOT)

    built = sorted(raw_wheels.glob("xqsim-*.whl"))
    if len(built) != 1:
        raise RuntimeError(f"expected exactly one wheel, found: {built}")

    auditwheel_platform = None
    if args.manylinux_platform:
        auditwheel = shutil.which("auditwheel")
        if auditwheel is None:
            raise RuntimeError(
                "auditwheel is required when --manylinux-platform is set"
            )
        if shutil.which("patchelf") is None:
            raise RuntimeError("patchelf is required for auditwheel repair")
        audit_report = run([auditwheel, "show", str(built[0])])
        (output / "auditwheel.txt").write_text(
            audit_report, encoding="utf-8"
        )
        run(
            [
                auditwheel,
                "repair",
                "--plat",
                args.manylinux_platform,
                "--wheel-dir",
                str(wheels),
                str(built[0]),
            ]
        )
        auditwheel_platform = args.manylinux_platform
    else:
        shutil.copy2(built[0], wheels / built[0].name)

    final_wheels = sorted(wheels.glob("xqsim-*.whl"))
    if len(final_wheels) != 1:
        raise RuntimeError(
            f"expected exactly one final wheel, found: {final_wheels}"
        )
    final_wheel = final_wheels[0]
    finalize_artifacts(output, final_wheel, version, auditwheel_platform)

    if not args.keep_stage:
        shutil.rmtree(stage)
        shutil.rmtree(raw_wheels)
    print(f"binary wheel: {final_wheel}")
    print(f"release manifest: {output / 'manifest.json'}")
    return final_wheel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="new or empty release output directory"
    )
    parser.add_argument(
        "--version",
        help="PEP 440 release version; defaults to xqsim.version",
    )
    parser.add_argument(
        "--manylinux-platform",
        help="run auditwheel repair, e.g. manylinux_2_28_x86_64",
    )
    parser.add_argument(
        "--no-build-isolation",
        action="store_true",
        help="use active pinned Cython/setuptools (development only)",
    )
    parser.add_argument(
        "--keep-stage", action="store_true", help="retain generated sources"
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        build(parse_args())
    except Exception as error:
        print(f"release build failed: {error}", file=sys.stderr)
        raise
