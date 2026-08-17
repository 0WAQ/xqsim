# xqsim Research Runtime

Run a simulation with the single executable:

```bash
/usr/local/xqsim/xqsim -c /path/to/Config.MyFactor.xml
```

Public research modules live in the adjacent directories:

- `operation/`: export `Operation` or `create`;
- `stats/`: export `Stats` or `create`;
- `provider/`: export `Provider` or `create`;
- `portfolio/`: export `Portfolio` or `create`;
- `config/`: shared XML configuration examples;
- `utils.py`: shared plain Python/NumPy helpers.

Their authoritative repository sources live under `public_modules/`.
`examples/` is optional usage documentation and is never deployed.

Configurations may use the built-in macros `${xqsim_operation}`,
`${xqsim_stats}`, `${xqsim_provider}`, `${xqsim_portfolio}`, `${xqsim_config}`,
`${xqsim_utils}`, and `${xqsim_data}`. Researcher configurations use XML.
Shared futures caches live under `data/futures/cc`; the fixed 2024 snapshot is
`data/futures/cc_2024`. Stock data is not provisioned in this runtime. Factor code and
outputs remain in the researcher's own workspace; factor files export `Alpha`
or `create` and are referenced by their own paths.

Do not edit these shared directories directly. Contribute through the reviewed
public-module repository, then deploy an approved snapshot. Data is managed by
provider and update scripts, not by the release publisher. Provider code must
never contain database credentials. `public-modules.json` records the deployed
source commit and SHA-256 for every managed file.

See `docs/researcher_guide.md` in the source repository for the researcher-facing
XML configuration and module-writing guide.
