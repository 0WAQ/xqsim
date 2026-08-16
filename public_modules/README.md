# Public Research Modules

This directory contains researcher-visible modules maintained with the
framework. `deploy.json` is the authoritative allowlist for files copied into
`/usr/local/xqsim/{operation,stats,provider,config}`.

Operation sources live here. Existing framework Stats modules remain canonical
under `xqsim/modules/` and are referenced by the manifest instead of duplicated.
Add a module by committing its source and one explicit manifest entry; never
place credentials or personal factor code in this directory.

Validate without writing:

```bash
python tools/release/deploy.py --check-only
```

Deploy the listed public modules:

```bash
python tools/release/deploy.py
```

Deployment requires the manifest, deployer, and managed sources to be committed;
unrelated worktree changes do not block it.
