# AGENTS.md

This file provides guidance to AI Coding Agent when working with code in this repository.

## Repository layout

This workspace is a quantitative-simulation stack. The top-level layout is flat:
the two installable packages live at the repo root, next to a few support directories:

```
xqsim-py/
├── pyproject.toml         # uv-managed project metadata, hatchling build backend
├── uv.lock
├── xqsim/                  # core simulator engine (installable package)
├── xqsim_data_tools/       # Prefect flows + update_tools CLI (installable package)
├── providers/             # ProviderBase scripts referenced by absolute path from YAML
│   ├── *.py               # kline / universe / industry / wind_* / barra / static_provider ...
│   ├── *.yml              # config_production / config_debug / config_csv / config_single
│   ├── cc/meta/           # cache index CSVs (DateIndex / InstrumentIndex / Calendar ...)
│   └── mysql.json
├── examples/              # sample configs and demo modules referenced by configs
│   ├── sample_config.yml
│   ├── sample_config.xml
│   └── module_demo/       # alpha_demo / op_demo / portfolio_simple ...
├── tools/                 # operational scripts not part of the installable packages
│   ├── ut/                # HTML-report unit tests over a built data cache
│   ├── config/            # update_production / update_debug / update_csv* yaml
│   ├── prefect/           # Prefect server + agent + helpers (all in one place)
│   │   ├── backend.toml
│   │   ├── supervisord.conf
│   │   ├── init_server.sh # bring up local Prefect server
│   │   ├── run_agent.sh   # launch supervised prefect agent
│   │   ├── common.py      # legacy stand-alone Prefect flow helpers
│   │   └── csv_flow.py
│   └── release/           # Cython release pipeline (kept separate from the packages)
│       ├── release.sh
│       ├── build_cython.py
│       └── setup/
│           └── setup.py   # wheel-only setup; runtime deps live in pyproject.toml
```

`providers/` files are NOT pip-installed — they are referenced as absolute paths from
YAML configs (`provider:.file_path`) and dynamically imported at run time.

## Install / build (uv)

Requires **Python ≥ 3.12**.

```bash
uv sync                 # create .venv, install xqsim + xqsim_data_tools editable
uv run xqsim --version
uv run python tools/ut/ut_run.py
uv add <pkg>            # add a runtime dep (writes to pyproject.toml)
uv add --dev <pkg>      # dev-only dep
```

The Cython release pipeline (Cython-compile most of `xqsim/` to `.so`) lives in
`tools/release/`. `release.sh` calls `build_cython.py`, which uses
`tools/release/setup/setup.py` to build a wheel of the compiled `.so` files.
Runtime dependencies are managed by `pyproject.toml`, NOT by this setup.py.
The `copy_only_list` in `build_cython.py` controls which files stay as plain
Python (public API, base classes, entry points). Edit it when adding files
that must remain importable as source.

Console entry points (declared in `pyproject.toml`):
- `xqsim` → `xqsim.xqsim_run:main`
- `stats_general` → `xqsim.modules.stats_general:main`
- `update_tools` → `xqsim_data_tools.update_tools:cli`

## Running the simulator

The user-facing flow is config-driven, not code-driven:

```bash
uv run xqsim -c <config.yml | config.xml>
```

`xqsim_run.main` calls `Simulator.init_with_config(path)` which:
1. Picks a parser by extension — `.yml` → `common_utils.load_yaml(..., macro=True)`,
   `.xml` → `simulator.load_xml` (the XML parser maps the legacy schema with
   `Universe / Constants / Modules / Portfolio` into the same dict shape as the YAML form).
2. Substitutes `${...}` macros (the runtime always injects `${xqsim_modules}` pointing
   at the installed `xqsim/modules/` dir, plus `${config}` = config-file dir).
3. Walks four config sections in order — `global` → `provider` → `module` → `alpha` —
   wiring providers, alpha modules, ops, and stats into an `AlphaManager`.

The same simulator can also be driven from a Python module by calling
`simulator_run(**kwargs)` (alpha) or `builder_run(**kwargs)` (provider) — the
`__main__` module's file path becomes the alpha/provider source. Demos live in
`examples/module_demo/`.

`build: true` in `global:` short-circuits after providers run — useful for refreshing
the cache without simulating. See `providers/config_production.yml` for the canonical
"build only" config.

## Architectural anchors

When tracing a run, these are the key seams:

- **`Simulator` (`simulator.py`)** — owns `Meta`, `DataRepositoryImpl`, `ProviderManager`,
  `AlphaManager`. `run()` calls `__build()` (providers fill the cache), then loops
  `for di in [begin_di, end_di]` calling `alpha_manager.run_before_di / run /
  run_after_di / save`. Checkpointing serializes the `AlphaManager` via `lz4.frame` +
  `cPickle` to `meta.checkpoint_dir/save.bin` plus a `.list` of source paths so a
  resumed run can re-import the alpha modules.
- **`Meta` (`meta.py`)** — calendar, date index, instrument index, `di`/`ii` mappings,
  run-time params (`set_para` / `get_para`). `Calendar` does bisect-based trade-day
  math; many configs use string offsets like `TODAY-1`.
- **`DataRepository` (`data_repository.py` / `_impl.py`)** — `DataView` is the abstract
  array-with-offset accessor; alphas/providers consume `dr.get_data("k.close")` and the
  `DataView` resolves into a numpy array shaped `(di_size, ii_size)` (or with a
  `ti_size` axis when `interval != "day"`).
- **`ProviderBase` (`provider_base.py`)** — `generate()` writes named arrays to the
  on-disk cache via `write_data` / `append_data` / `*_compress_data`. `enable_modify()`
  and `enable_part_overwrite()` toggle whether an existing cache directory is rewritten
  or appended.
- **`AlphaBase` / `AlphaOperationBase` (`module_base.py`, `alphabase.py`)** —
  `generate(di, ...)` produces a per-instrument vector into `self.alpha`; ops run as
  a chain after the alpha; stats run via `AlphaManager.save_stats` at the end.
  `simcfg.get` is the canonical way to coerce config values (it special-cases `bool`
  to handle `"true"`/`"false"` strings).
- **`AlphaManager` / `AlphaTask` (`alpha_manager.py`)** — one `AlphaTask` per `alpha:`
  entry in the config, holding the alpha + its op list + its stats list. Portfolio
  entries (any alpha config containing a nested `Alpha:` key) become a `portfolio_task`
  instead.

Provider configs reference Python files by absolute path (`file_path:
${provider_dir}/kline.py`), and the simulator dynamically imports them — moving or
renaming a provider file means updating every YAML/XML that references it.

**Import shims for external code** — `api.py` re-exports everything from
`alpha_base` plus `alphabase`; `alphabase.py` re-exports `AlphaBase`,
`OperationBase` (as `AlphaOperationBase`), and `PortfolioBase`. External
alphas/modules should import from `xqsim.alpha_base` (for `simulator_run` /
`builder_run`) or `xqsim.alphabase` (for the base classes).

**Binary cache format** — each cache file starts with a 1024-byte C struct
header (`DataHeader` in `data_manager.py`) encoding `begin_trading_day`,
`end_trading_day`, `di_size`, `ii_size`, `ti_size`, type info, and `adj_mode`,
followed by the raw numpy data. Providers write via `ProviderBase.write_data` /
`append_data`; consumers read via `DataRepository.get_data` which returns a
`DataView` over the mmap'd array.

## Data tools (`xqsim_data_tools` + `tools/`)

- `update_tools` CLI exposes `show / check / merge / merge_dir` for inspecting and
  combining cache directories produced by providers. Use it after a `build: true` run
  to validate header consistency and merge an `output_cache_dir` into the production
  `meta_dir`.
- `prefect_task.py` defines the Prefect tasks that orchestrate daily updates.
  Uses Prefect 3.x (`@flow` / `@task` decorators, `get_run_logger()`,
  `flow.serve(cron=...)` for scheduling, `run_deployment()` for sub-flows).
- Bring up a local Prefect server with `bash tools/prefect/init_server.sh`
  (runs `prefect server start` on port 4200), then run a worker under
  supervisord with `bash tools/prefect/run_agent.sh` (listens on port 9001).
  Stand-alone flows live next to it as `tools/prefect/common.py` (main
  production flow) and `tools/prefect/csv_flow.py` (CSV build flow).

## Tests

There is no `pytest` suite. Tests are HTML-report unit tests over a built data cache:

```bash
uv run python tools/ut/ut_run.py
```

`ut_run.py` instantiates a `dr` against `meta_dir=/cc` for a small date window
(`TODAY-2` → `TODAY-1`) and registers test classes from `tools/ut/ut_cls/` (`universe`,
`kline`, `nan`, optionally `cw`, `citics_index`, `bar`). To run a single suite, edit
the `html_runner.add_module(...)` calls or use
`HTMLRunner.run_test("ut_cls.kline", dr)`. Output goes to `/tmp/ut/result.html` and a
summary `result.log`. The Prefect flow consumes that `result.log`.

`scripts/smoke_test/` was removed in the 2026-05 cleanup; use `tools/ut/ut_run.py`
or write a one-off `examples/module_demo/`-style script instead.

## Conventions worth knowing

- `meta_dir` is conventionally `/cc`; provider output goes to `output_cache_dir`
  (often `./cc_update` or `/cc_update`) and is merged into `/cc` by
  `update_tools merge_dir`. Don't write straight into `/cc` from a provider.
- Date strings `"TODAY-N"` and `"TODAY+N"` are resolved by the loader; pass them
  through configs rather than computing dates in Python.
- MySQL credentials live in `providers/mysql.json`. Providers default to that
  filename next to `static_provider.py`; override per-provider via `mysql_config`
  in the YAML. The committed file is a placeholder (`127.0.0.1` / `datareader`),
  replace it locally before pointing at a real DB.
- The Cython release pipeline means: if you add a new module under `xqsim/` that
  needs to be importable as source (base class, public API, entry point), add it to
  `copy_only_list` in `tools/release/build_cython.py`. Otherwise it will be shipped
  as a compiled `.so`/`.pyd` only.
