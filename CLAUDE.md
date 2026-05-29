# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

This workspace is a quantitative-simulation stack split into three sibling Python packages. They are not independent: `xiao_data_provider` and `xiao_qsim_tools` both `import qsim`, so `qsim` (from `xiao_qsim_dev`) must be installed first.

- `xiao_qsim_dev/` — the `qsim` core library and simulator runtime (the engine).
- `xiao_data_provider/` — concrete `ProviderBase` subclasses that pull market/fundamental data (Wind, MySQL, CSV, etc.) into the qsim cache. Not pip-installable; files are referenced by path from YAML configs.
- `xiao_qsim_tools/` — the `qsim_data_tools` package: Prefect flows, ssh/agent orchestration, cache merge/check CLI (`update_tools`), and the unit-test harness used to validate the data cache.

The core directory (`xiao_qsim_dev/src/qsim`) is treated as the development tree; release builds Cython-compile most of it (see "Build & release" below).

## Install / build

The intended Python is 3.6+ inside a conda env. There is no top-level installer; install each subpackage as needed.

```bash
# 1. core engine (dev install)
pip install -r xiao_qsim_dev/src/qsim/setup/requirements.txt
cd xiao_qsim_dev/src/qsim/setup && pip install -e ../..   # uses src/ layout

# 2. data tools (Prefect flows + CLI)
cd xiao_qsim_tools && pip install .

# 3. data provider files have no setup.py — they are referenced by absolute
#    path from YAML configs (see provider:.file_path entries).
```

`xiao_qsim_dev/src/qsim/release/release.sh` produces a Cython-compiled distribution at `$OUTPUT` (hard-coded to `/home/michael/qsim`) by running `build_cython.py`. `build_cython.py` cythonizes every `.py` under `src/qsim/` **except** the files in its `copy_only_list` (public API / base classes / entry points stay as plain Python). The `extra_dir_list = ["modules"]` is copied verbatim. Edit those two lists when adding files that must remain importable as source.

Console entry points installed by `qsim` setup:
- `qsim` → `qsim.qsim_run:main` (config-file simulator)
- `stats_general` → `qsim.modules.stats_general:main`

`qsim_data_tools` setup installs:
- `update_tools` → `qsim_data_tools.update_tools:cli`

## Running the simulator

The user-facing flow is config-driven, not code-driven:

```bash
qsim -c <config.yml | config.xml>
```

`qsim_run.main` calls `Simulator.init_with_config(path)` which:
1. Picks a parser by extension — `.yml` → `common_utils.load_yaml(..., macro=True)`, `.xml` → `simulator.load_xml` (the XML parser maps the legacy schema with `Universe / Constants / Modules / Portfolio` into the same dict shape as the YAML form).
2. Substitutes `${...}` macros (the runtime always injects `${qsim_modules}` pointing at the installed `qsim/modules/` dir, plus `${config}` = config-file dir).
3. Walks four config sections in order — `global` → `provider` → `module` → `alpha` — wiring providers, alpha modules, ops, and stats into an `AlphaManager`.

The same simulator can also be driven from a Python module by calling `simulator_run(**kwargs)` (alpha) or `builder_run(**kwargs)` (provider) — the `__main__` module's file path becomes the alpha/provider source. Demos live in `xiao_qsim_dev/src/qsim/module_demo/`. `xiao_data_provider/dmgr_demo.py` and `factor_load.py` are similar single-file launchers.

`build: true` in `global:` short-circuits after providers run — useful for refreshing the cache without simulating. See `xiao_data_provider/config_production.yml` for the canonical "build only" config.

## Architectural anchors

When tracing a run, these are the key seams:

- **`Simulator` (`simulator.py`)** — owns `Meta`, `DataRepositoryImpl`, `ProviderManager`, `AlphaManager`. `run()` calls `__build()` (providers fill the cache), then loops `for di in [begin_di, end_di]` calling `alpha_manager.run_before_di / run / run_after_di / save`. Checkpointing serializes the `AlphaManager` via `lz4.frame` + `cPickle` to `meta.checkpoint_dir/save.bin` plus a `.list` of source paths so a resumed run can re-import the alpha modules.
- **`Meta` (`meta.py`)** — calendar, date index, instrument index, `di`/`ii` mappings, run-time params (`set_para` / `get_para`). `Calendar` does bisect-based trade-day math; many configs use string offsets like `TODAY-1`.
- **`DataRepository` (`data_repository.py` / `_impl.py`)** — `DataView` is the abstract array-with-offset accessor; alphas/providers consume `dr.get_data("k.close")` and the `DataView` resolves into a numpy array shaped `(di_size, ii_size)` (or with a `ti_size` axis when `interval != "day"`).
- **`ProviderBase` (`provider_base.py`)** — `generate()` writes named arrays to the on-disk cache via `write_data` / `append_data` / `*_compress_data`. `enable_modify()` and `enable_part_overwrite()` toggle whether an existing cache directory is rewritten or appended.
- **`AlphaBase` / `AlphaOperationBase` (`module_base.py`, `alphabase.py`)** — `generate(di, ...)` produces a per-instrument vector into `self.alpha`; ops run as a chain after the alpha; stats run via `AlphaManager.save_stats` at the end. `simcfg.get` is the canonical way to coerce config values (it special-cases `bool` to handle `"true"`/`"false"` strings).
- **`AlphaManager` / `AlphaTask` (`alpha_manager.py`)** — one `AlphaTask` per `alpha:` entry in the config, holding the alpha + its op list + its stats list. Portfolio entries (any alpha config containing a nested `Alpha:` key) become a `portfolio_task` instead.

Provider configs reference Python files by absolute path (`file_path: ${provider_dir}/kline.py`), and the simulator dynamically imports them — moving or renaming a provider file means updating every YAML/XML that references it.

## Data tools (`xiao_qsim_tools`)

- `update_tools` CLI exposes `show / check / merge / merge_dir` for inspecting and combining cache directories produced by providers. Use it after a `build: true` run to validate header consistency and merge an `output_cache_dir` into the production `meta_dir`.
- `prefect_task.py` defines the Prefect flow that orchestrates daily updates: it loads the YAML config, runs `meta_updater`, dispatches build/check tasks across hosts via `qsim_data_tools/ssh.py`, and triggers UTs.
- Bring up a local Prefect server with `bash xiao_qsim_tools/init.sh`, then run an agent under supervisord with `bash xiao_qsim_tools/run_agent.sh` (writes `~/supervisor/supervisord.conf`, listens on port 9001).

## Tests

There is no `pytest` suite. Tests are HTML-report unit tests over a built data cache:

```bash
# from xiao_qsim_tools/
python ut/ut_run.py
```

`ut_run.py` instantiates a `dr` against `meta_dir=/cc` for a small date window (`TODAY-2` → `TODAY-1`) and registers test classes from `ut/ut_cls/` (`universe`, `kline`, `nan`, optionally `cw`, `citics_index`, `bar`). To run a single suite, edit the `html_runner.add_module(...)` calls or use `HTMLRunner.run_test("ut_cls.kline", dr)`. Output goes to `/tmp/ut/result.html` and a summary `result.log`. The Prefect flow consumes that `result.log`.

`xiao_qsim_dev/src/qsim/test/main*.py` are ad-hoc smoke scripts (load adj data, summarize, etc.) — run them directly with `python`.

## Conventions worth knowing

- `meta_dir` is conventionally `/cc`; provider output goes to `output_cache_dir` (often `./cc_update` or `/cc_update`) and is merged into `/cc` by `update_tools merge_dir`. Don't write straight into `/cc` from a provider.
- Date strings `"TODAY-N"` and `"TODAY+N"` are resolved by the loader; pass them through configs rather than computing dates in Python.
- MySQL credentials live in `xiao_data_provider/mysql.json` (and `mysql_235.json`). Providers default to `mysql.json` next to `static_provider.py`; override per-provider via `mysql_config` in the YAML.
- The Cython release pipeline means: if you add a new module under `qsim/` that needs to be importable as source (base class, public API, entry point), add it to `copy_only_list` in `build_cython.py`. Otherwise it will be shipped as a compiled `.so`/`.pyd` only.
