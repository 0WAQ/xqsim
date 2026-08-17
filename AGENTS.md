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
│   ├── stocks/            # A股 providers (MySQL 数据源)
│   │   ├── DataProvider*.py # Kline / Universe / Industry / Wind* / Barra / Static ...
│   │   ├── *.yml          # config_production / config_debug / config_csv / config_single
│   │   └── mysql.json
│   └── futures/           # 期货 providers (MSSQL 数据源, ldcta 拆分移植)
│       ├── DataProvider*.py # Kline / Universe / Hot / InstrumentInfo / MetaUpdater /
│       │                  # Mssql(基类) / FuturesCommon(代码换算) / HotBuilder(主力判定)
│       │                  # Warehouse / Instock / WindCommodity(pi 维) / PositionsRank(会员持仓 cube)
│       │                  # Industry(品种行业分类 ind.l1/ind.sector, 不连库, 读 industries.csv)
│       ├── industries.csv # 品种 → industry_l1 × CTA 粗行业 静态表 (DataProviderIndustry.py 数据源)
│       ├── config_production.yml
│       └── mssql.json
├── public_modules/        # reviewed researcher-visible modules + deploy allowlist
│   ├── deploy.json        # explicit source -> public runtime target mapping
│   ├── operation/         # canonical public Operation implementations
│   ├── stats/             # canonical public Stats implementations
│   ├── portfolio/         # canonical public Portfolio implementations
│   └── utils.py           # canonical public NumPy helpers
├── data/                  # 仓库内 bootstrap/迁移源，不是生产运行路径
│   ├── stocks/cc/meta/    # Git 跟踪的股票 meta 引导数据
│   └── futures/           # 本地回退副本；生产数据在 /usr/local/xqsim/data
├── examples/              # usage demonstrations only; never canonical/deployed sources
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
│       ├── deploy.py              # unified framework + public-module deployer
│       ├── build_cython.py        # stage + PEP 517 wheel build + artifact manifest
│       ├── build_executable.py    # freeze installed binary wheel into one ELF
│       ├── executable_main.py     # PyInstaller entry point
│       ├── executable_smoke_test.py # external-module + CLI gate
│       ├── release_manifest.py    # explicit source / compiled / excluded modules
│       ├── verify_wheel.py        # static wheel-content gate
│       ├── smoke_test.py          # installed-wheel import gate
│       ├── publish_release.py     # immutable executable releases under install root
│       ├── activate_release.py    # atomic executable switch / rollback
│       ├── PUBLIC_MODULES.md      # deployed researcher-facing module contract
│       ├── README.md
│       └── setup/
│           └── setup.py           # generated-stage PEP 517 build definition
```

`providers/` files are NOT pip-installed — they are referenced as absolute paths from
YAML configs (`provider:.file_path`) and dynamically imported at run time.

## Install / build (uv)

Requires **Python ≥ 3.12**.

```bash
uv sync                 # core runtime dependencies
uv sync --all-extras    # full contributor env: data tools, providers, release, dev
uv run xqsim --version
uv run python tools/ut/ut_run.py
uv add <pkg>            # add a runtime dep (writes to pyproject.toml)
uv add --dev <pkg>      # dev-only dep
```

The researcher-facing release is one Linux ELF at `/usr/local/xqsim/xqsim`.
`release.sh` first builds the Cython platform wheel as an internal artifact,
installs it in a clean venv, then freezes CPython, dependencies, and the compiled
core with PyInstaller. It starts the resulting ELF and loads same-named external
Alpha/Operation/Stats/Provider files before publication. Published versions are
immutable under `/usr/local/xqsim/releases/<version>/`; the root `xqsim` symlink
is the atomic activation and rollback point. `deploy.py` validates every entry in
`public_modules/deploy.json` with the target ELF before atomically copying it;
`release.sh` uses this same entry point when `PUBLISH_ROOT` is set.

`tools/release/release_manifest.py` is the authoritative explicit boundary:
every module under `xqsim/` must be listed as source, compiled, or excluded.
An unclassified module fails the build. Runtime dependencies come from
`pyproject.toml`; `setup/setup.py` consumes generated metadata instead of
maintaining a second dependency list. The same manifest supplies explicit hidden
imports for code executed inside Cython extensions. Builds require CPython 3.12
with `Python.h` and the pinned PyInstaller; `auditwheel` and `patchelf` remain
optional wheel portability checks.
See `docs/deployment.md` for all operational commands and
`tools/release/README.md` for pipeline internals.

Console entry points (declared in `pyproject.toml`):
- `xqsim` → `xqsim.xqsim_run:main`
- `stats_general` → `xqsim.modules.StatsGeneral:main`
- `update_tools` → `xqsim_data_tools.update_tools:cli`

## Running the simulator

The user-facing flow is config-driven, not code-driven. New researcher
configurations use XML only; YAML files are legacy operational inputs and must
not be used in new researcher documentation or examples. Researchers use the
deployed executable; contributors may use the editable environment:

```bash
/usr/local/xqsim/xqsim -c Config.MyFactor.xml
uv run xqsim -c Config.MyFactor.xml
```

`xqsim_run.main` calls `Simulator.init_with_config_path(path)` which:
1. Picks a parser by extension — `.yml` → `common_utils.load_yaml(..., macro=True)`,
   `.xml` → `simulator.load_xml` (the XML parser maps the legacy schema with
   `Universe / Constants / Modules / Portfolio` into the same dict shape as the YAML form).
2. Substitutes `${...}` macros. `${config}` is the config-file directory;
   `${xqsim_modules}` is the bundled built-in module directory. The default
   external root is `/usr/local/xqsim` (override with `XQSIM_HOME` for tests),
  exposed as `${xqsim_home}` plus `${xqsim_operation}`, `${xqsim_stats}`,
  `${xqsim_provider}`, `${xqsim_portfolio}`, `${xqsim_config}`, `${xqsim_utils}`,
  and `${xqsim_data}`. `${xqsim_alpha}` remains a
   compatibility macro but its directory is not created or managed.
3. Walks four config sections in order — `global` → `provider` → `module` → `alpha` —
   wiring providers, alpha modules, ops, and stats into an `AlphaManager`.

The same simulator can also be driven from a Python module by calling
`simulator_run(**kwargs)` (alpha) or `builder_run(**kwargs)` (provider) — the
`__main__` module's file path becomes the alpha/provider source. Demos live in
`examples/module_demo/`.

`build: true` in `global:` short-circuits after providers run — useful for refreshing
the cache without simulating. See `providers/stocks/config_production.yml` for the canonical
"build only" config.

Futures side: generate meta first (`uv run python providers/futures/DataProviderMetaUpdater.py`,
defaults to `/usr/local/xqsim/data/futures/cc` and needs MSSQL access plus
`providers/futures/mssql.json`), then
`uv run xqsim -c providers/futures/config_production.yml` (needs `index_category: FUTURES`
+ `adj_window: -1`, already in that config). Consistency against the legacy ldcta cache
is verified with `tools/futures/compare_ldcta.py`; semantics and validation results are
documented in `docs/futures_adaptation.md` §4.1.
The shared runtime currently provisions futures only: `data/futures/cc` is the live
cache and `data/futures/cc_2024` is the fixed cutoff snapshot. Rebuild that snapshot
with `tools/futures/snapshot_cache.py`; do not copy and rename the live cache.

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
  math; many configs use string offsets like `TODAY-1`. Finite snapshots clamp `TODAY`
  to their final calendar day; exclusive instrument EndDates beyond that calendar keep
  the instrument active through the final day.
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
${provider_dir}/DataProviderKline.py`), and the simulator dynamically imports them — moving or
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
  `meta_dir`. Pass `--index-category FUTURES` with a futures `--meta` path; the default
  category and path are the stock cache.
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

`ut_run.py` instantiates a `dr` against `/usr/local/xqsim/data/stocks/cc` for a small date window
(`TODAY-2` → `TODAY-1`) and registers test classes from `tools/ut/ut_cls/` (`universe`,
`kline`, `nan`, optionally `cw`, `citics_index`, `bar`). To run a single suite, edit
the `html_runner.add_module(...)` calls or use
`HTMLRunner.run_test("ut_cls.kline", dr)`. Output goes to `/tmp/ut/result.html` and a
summary `result.log`. The Prefect flow consumes that `result.log`.
The current shared runtime does not provision this stock cache; create and refresh it
before running the stock HTML suites.

`scripts/smoke_test/` was removed in the 2026-05 cleanup; use `tools/ut/ut_run.py`
or write a one-off `examples/module_demo/`-style script instead.

## Conventions worth knowing

- Runtime data lives under `/usr/local/xqsim/data` (override standalone Python
  tools with `XQSIM_DATA_HOME`). Stocks use `stocks/cc` as production and
  `stocks/cc_update` as provider output, merged by `update_tools`; do not write
  stock providers straight into production. **期货例外**:`futures/cc` 直接作为
  `output_cache_dir`,且
  `data_dir: ""`(扁平布局,数据目录与 `meta/` 同级,无 `Data/` 层);
  扫描与写出路径都按 `meta` 的 `data_dir` para 走,股票侧默认 `Data` 不变。
- Date strings `"TODAY-N"` and `"TODAY+N"` are resolved by the loader; pass them
  through configs rather than computing dates in Python.
- MySQL credentials live in `providers/stocks/mysql.json` (MSSQL for futures:
  `providers/futures/mssql.json`). Providers default to that
  filename next to `DataProviderStatic.py`; override per-provider via `mysql_config`
  in the YAML. The committed file is a placeholder (`127.0.0.1` / `datareader`),
  replace it locally before pointing at a real DB.
- When adding a module under `xqsim/`, classify it explicitly in
  `tools/release/release_manifest.py`. Researcher-facing contracts, base classes,
  entry points, and file-path-loaded built-ins normally remain source; internal
  runtime implementations normally compile to `.so`. Exclusions require a reason.
  Never bypass the manifest coverage check.
- Public research modules live outside the executable under
  `/usr/local/xqsim/{operation,stats,provider,portfolio,config}` plus root-level
  `utils.py`. Operation, Stats, Provider, and Portfolio files export the
  same-named class or `create`; factor files remain in
  researcher workspaces and export `Alpha` or `create`. The loader keys modules
  by absolute path, so equal filenames in different directories are valid.
  Python filenames use a role prefix plus PascalCase: `AlphaOpXxx.py`,
  `StatsXxx.py`, `DataProviderXxx.py`, and `PortfolioXxx.py`. Config `module_id` values are logical
  identifiers and do not need to match filenames. Linux paths are case-sensitive;
  rename the file and all YAML/XML/deployment references in one change.
  Shared reusable functions live in `public_modules/utils.py` and deploy to root
  `utils.py`; helper modules are not registered as plugins.
  `public_modules/` is authoritative for shared researcher modules; `examples/`
  only supplements documentation. Package copies of public Stats must remain
  byte-identical to `public_modules/stats/` and are checked during release.
  Contributions must be reviewed and deployed rather than edited in place;
  credentials never belong in the Provider directory. Add shared files through
  `public_modules/deploy.json`; follow `docs/deployment.md` for validation and
  deployment commands.

## Living documentation

Documentation is part of the implementation and is written for researchers using
the framework, including a future reader with no context from the current task.

- `docs/architecture.md` — verified framework behavior, lifecycle, data layout, and
  interfaces. Update it whenever framework behavior changes.
- `docs/deployment.md` — the single authoritative source for build, deploy,
  verification, rollback, isolated-test, and offline-build commands.
- `docs/factor_research.md` — practical factor research, implementation, timing,
  adaptation, and validation guidance. Record reusable conclusions, not a coding log.
- `docs/researcher_guide.md` — XML-only researcher instructions for running the
  system, writing modules, understanding fields, and configuring experiments.
- `docs/idea_keywords.md` — low-friction inbox for ideas or keywords that are not yet
  mature enough for the other documents. Include enough context to recover the idea.

Before changing framework or factor behavior, read the relevant living document.
Update code and documentation together when an interface, timing contract, data
dependency, workflow, or validated conclusion changes. Put verified facts in the
architecture or factor guide, and label hypotheses and unfinished experiments clearly.
When an inbox idea matures, move its conclusion to the appropriate guide and mark the
inbox entry resolved instead of silently deleting it. If code and docs disagree,
verify runtime behavior and correct the documentation immediately.
