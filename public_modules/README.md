# Public Research Modules

This directory contains researcher-visible modules maintained with the
framework. `deploy.json` is the authoritative allowlist for files copied into
`/usr/local/xqsim/{operation,stats,provider,config}`.

Researcher-facing Operation, Stats, Portfolio, and utility sources live here.
This directory is the authoritative source for shared researcher modules.
`xqsim/modules/Stats*.py` are packaging mirrors required by the wheel and must
remain byte-identical to `public_modules/stats/Stats*.py`; the release check
rejects drift. Add a module by committing its source and one explicit manifest
entry; never place credentials or personal factor code in this directory.

`examples/` only demonstrates how to use these modules. It is optional
explanatory material, never a deployment source or an implementation authority.

Researcher-facing configuration examples use XML only.

Research modules use role-prefixed PascalCase filenames: `AlphaOpXxx.py`,
`StatsXxx.py`, `DataProviderXxx.py`, and `PortfolioXxx.py`. Linux paths are
case-sensitive; update every config `file_path` and manifest entry together when
renaming a module. Shared reusable functions belong in lowercase root-level
`utils.py`; it is a helper module, not a dynamically configured plugin.

Deployment requires the manifest, deployer, and managed sources to be committed;
unrelated worktree changes do not block it. All operational commands live in
[`docs/deployment.md`](../docs/deployment.md).
