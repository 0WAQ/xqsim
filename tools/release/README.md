# Release Pipeline Internals

The researcher artifact is a Linux x86_64 one-file ELF containing CPython 3.12,
the Cython-compiled core, and runtime dependencies. The platform wheel remains
an internal verification artifact. PyInstaller extracts native libraries into a
temporary directory at startup, so the target host must allow execution there.

`release_manifest.py` is the explicit source/compiled/excluded boundary for all
modules under `xqsim/` and also supplies frozen hidden imports. `build_cython.py`
stages and verifies the binary wheel. `build_executable.py` freezes the installed
wheel. The two smoke tests verify compiled imports and real ELF loading of
external Alpha, Operation, Stats, and Provider modules.

`publish_release.py` creates immutable `releases/<version>/` directories and
atomically activates the root `xqsim` symlink. It initializes, but never deletes
or replaces, `data/stocks/cc` and `data/futures/cc`. `deploy.py` is the unified entry
point: it can publish a verified framework artifact and deploy the explicit
`public_modules/deploy.json` allowlist. Public files are validated with the target
ELF, atomically replaced, installed read-only, and recorded with SHA-256 values.

Operational commands, validation, rollback, isolated testing, and offline build
instructions are maintained only in
[`docs/deployment.md`](../../docs/deployment.md).
