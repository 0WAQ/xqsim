# Single-File Release Guide

## Final Artifact

Researchers receive one Linux executable:

```text
/usr/local/xqsim/xqsim
```

It embeds CPython 3.12, the Cython-compiled xqsim core, and required runtime
packages. The binary wheel remains an internal, verified intermediate artifact.
Alpha, Operation, Stats, Provider, configuration, credentials, and cache data
remain external. PyInstaller one-file mode extracts native libraries into a
temporary directory at startup; the target host must allow execution there.

## Installed Layout

```text
/usr/local/xqsim/
├── xqsim -> releases/<version>/xqsim
├── releases/
│   └── <version>/
│       ├── xqsim
│       ├── manifest.json
│       └── SHA256SUMS
├── operation/
├── stats/
├── provider/
├── config/
└── README.md
```

`releases/<version>` is immutable. Publishing initializes but never replaces
the four public directories. Framework rollback only repoints the root `xqsim`
symlink.

## External Module Contract

A module is one ordinary Python file and exports its conventional class or a
`create` factory:

- a factor file in the researcher's workspace: `Alpha` or `create`;
- `operation/`: `Operation` or `create`;
- `stats/`: `Stats` or `create`;
- `provider/`: `Provider` or `create`.

The loader derives an internal module name from the absolute path, so equal
filenames in different directories do not collide. Import failures propagate
with their original traceback. The CLI can validate contributions without
starting a simulation:

```bash
/usr/local/xqsim/xqsim \
  --check-module operation /path/to/neutralize.py \
  --check-module stats /path/to/futures_stats.py
```

Configurations always receive these macros:

```text
${xqsim_home}       /usr/local/xqsim
${xqsim_operation}  /usr/local/xqsim/operation
${xqsim_stats}      /usr/local/xqsim/stats
${xqsim_provider}   /usr/local/xqsim/provider
${xqsim_config}     /usr/local/xqsim/config
```

Set `XQSIM_HOME` only for isolated testing or a non-standard installation.
`${xqsim_modules}` remains available for built-in modules bundled with the
runtime. `${xqsim_alpha}` remains a compatibility macro, but the publisher does
not create or manage its target directory; new factor configs use researcher
workspace paths.

## Build

Use CPython 3.12 with `Python.h`. PyInstaller and Cython versions are pinned.
For a local dirty-tree validation:

```bash
PYTHON=/path/to/cpython-3.12/bin/python3.12 \
ALLOW_DIRTY=1 \
OUTPUT=/tmp/xqsim-release-local \
RELEASE_VERSION=1.3.7+glocal \
bash tools/release/release.sh
```

The pipeline:

1. validates the explicit source/compiled/excluded module manifest;
2. builds and statically verifies the Cython wheel;
3. installs the wheel into a clean temporary environment;
4. imports every compiled module;
5. freezes the installed wheel with PyInstaller;
6. starts the ELF and loads four external same-named test modules;
7. optionally publishes the verified executable.

The output keeps `wheels/` for internal diagnosis and places the researcher
artifact at `executable/xqsim`. The manifest records both hashes, ABI, Git SHA,
build tool version, and executable size.

## Publish to /usr/local/xqsim

Build from a clean committed worktree on the oldest supported Linux baseline:

```bash
PYTHON=/path/to/cpython-3.12/bin/python3.12 \
PUBLISH_ROOT=/usr/local/xqsim \
bash tools/release/release.sh
```

`release.sh` refuses a dirty tree by default and never overwrites an existing
version. It routes publication through `deploy.py`, so the allowlisted public
modules are validated against the new ELF and deployed in the same invocation.
Researchers then run:

```bash
/usr/local/xqsim/xqsim -c /path/to/factor.yml
```

If an offline build is required, `DEPENDENCY_WHEELHOUSE` must contain every
locked runtime dependency plus the pinned PyInstaller build dependencies.

## Unified Deployment

`public_modules/deploy.json` is the explicit allowlist for public files. Its
sources are repository-relative; `target` is optional and defaults to the source
basename. The deployer validates all Python modules with the selected runtime,
uses atomic file replacement, records SHA-256 values in
`/usr/local/xqsim/public-modules.json`, and never deletes unlisted files.

Validate the manifest and imports without writing:

```bash
python tools/release/deploy.py --check-only
```

Deploy only the public modules against the active runtime:

```bash
python tools/release/deploy.py
```

Publish an already-built framework artifact and the public modules together:

```bash
python tools/release/deploy.py --artifact /tmp/xqsim-release-version
```

Use `--root`, `--manifest`, `--source-root`, or `--runtime` for an isolated
deployment. Public module files are installed mode `0444`; approved updates are
performed by running the deployer again from a reviewed commit. A write refuses
uncommitted changes to the deployer, manifest, or managed sources; unrelated
worktree changes are ignored. `--allow-dirty` is only for an isolated local test.

## Rollback

Activate any retained release after verifying its manifest hash:

```bash
python tools/release/activate_release.py 1.3.7+gprevious
```

Use `--root` only for a non-default installation. Public modules should be
reviewed in a separate Git repository and deployed read-only. Provider source
must not contain database credentials; keep secrets outside `/usr/local/xqsim`.
