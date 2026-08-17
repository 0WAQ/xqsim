# Public Research Modules

This directory contains researcher-visible modules maintained with the
framework. `deploy.json` is the authoritative allowlist for files copied into
`/usr/local/xqsim/{operation,stats,provider,config}`.

Operation sources live here. Existing framework Stats modules remain canonical
under `xqsim/modules/` and are referenced by the manifest instead of duplicated.
Add a module by committing its source and one explicit manifest entry; never
place credentials or personal factor code in this directory.

Research modules use role-prefixed PascalCase filenames: `AlphaOpXxx.py`,
`StatsXxx.py`, and `DataProviderXxx.py`. Linux paths are case-sensitive; update
every config `file_path` and manifest entry together when renaming a module.
Directory-local reusable functions belong in lowercase `utils.py`; it is a
helper module, not a dynamically configured Operation, Stats, or Provider.

Deployment requires the manifest, deployer, and managed sources to be committed;
unrelated worktree changes do not block it. All operational commands live in
[`docs/deployment.md`](../docs/deployment.md).
