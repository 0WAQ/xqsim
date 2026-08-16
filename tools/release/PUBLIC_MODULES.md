# xqsim Research Runtime

Run a simulation with the single executable:

```bash
/usr/local/xqsim/xqsim -c /path/to/config.yml
```

Public research modules live in the adjacent directories:

- `alpha/`: export `Alpha` or `create`;
- `operation/`: export `Operation` or `create`;
- `stats/`: export `Stats` or `create`;
- `provider/`: export `Provider` or `create`;
- `config/`: shared configuration examples.

Configurations may use the built-in macros `${xqsim_alpha}`,
`${xqsim_operation}`, `${xqsim_stats}`, `${xqsim_provider}`, and
`${xqsim_config}`. Personal factor code and outputs should remain in the
researcher's own workspace.

Do not edit these shared directories directly. Contribute through the reviewed
public-module repository, then deploy an approved snapshot. Provider code must
never contain database credentials.
