# xqsim 部署手册

本文是部署命令的唯一权威入口。所有命令均从仓库根目录执行；默认安装根目录为
`/usr/local/xqsim`。目标机需为 Linux x86_64，完整构建需 CPython 3.12、
`Python.h` 和可执行的临时文件系统。

## 部署公共模块

先用当前正式 ELF 校验 `public_modules/deploy.json` 中的全部模块，不写文件：

```bash
python tools/release/deploy.py --check-only
```

校验通过后，原子部署 Operation、Stats、Provider、Portfolio、根级 utility 和
Config：

```bash
python tools/release/deploy.py
```

部署器不删除清单外文件，Python 模块写为 `0444`，并将 Git commit、目标路径和
SHA-256 写入 `/usr/local/xqsim/public-modules.json`。写入时，部署器、清单和受管
源码必须已提交；无关的 `examples/` 改动不会阻塞部署。

新增公共模块时，提交源码并在 `public_modules/deploy.json` 增加显式映射，然后依次
执行上述校验和部署命令。因子文件仍放在研究员自己的工作区。

## 构建并发布完整版本

完整发布要求整个 Git worktree 干净。指定带开发头文件的 CPython 3.12：

```bash
PYTHON=/path/to/cpython-3.12/bin/python3.12 \
PUBLISH_ROOT=/usr/local/xqsim \
bash tools/release/release.sh
```

该命令依次构建 Cython wheel、在干净虚拟环境中导入验证、生成 PyInstaller
单文件 ELF、运行真实启动测试、发布不可变 release，并部署公共模块。

如需先构建、审核制品，再单独发布：

```bash
PYTHON=/path/to/cpython-3.12/bin/python3.12 \
OUTPUT=/tmp/xqsim-release-version \
bash tools/release/release.sh

python tools/release/deploy.py \
  --artifact /tmp/xqsim-release-version
```

## 发布后验证

```bash
/usr/local/xqsim/xqsim --version
readlink /usr/local/xqsim/xqsim
file /usr/local/xqsim/xqsim
python -m json.tool /usr/local/xqsim/public-modules.json
```

校验某个外部模块：

```bash
/usr/local/xqsim/xqsim \
  --check-module operation /usr/local/xqsim/operation/AlphaOpSectorNeutralize.py \
  --check-module stats /usr/local/xqsim/stats/StatsFutures.py \
  --check-module portfolio /usr/local/xqsim/portfolio/PortfolioSimple.py
```

校验某个不可变 release 的哈希：

```bash
cd /usr/local/xqsim/releases/<version>
sha256sum -c SHA256SUMS
```

## 回滚框架

先列出保留版本，再切换根符号链接：

```bash
find /usr/local/xqsim/releases -mindepth 1 -maxdepth 1 -type d -printf '%f\n'
python tools/release/activate_release.py <version>
/usr/local/xqsim/xqsim --version
```

回滚仅切换框架 ELF，不会改动公共模块。公共模块需要从目标 Git commit 重新运行
部署器。release 目录不可覆盖；不要直接修改 `/usr/local/xqsim` 中的共享文件。

## 隔离测试与离线构建

在临时根目录测试公共模块部署：

```bash
mkdir -p /tmp/xqsim-deploy-test
python tools/release/deploy.py \
  --root /tmp/xqsim-deploy-test \
  --runtime /usr/local/xqsim/xqsim \
  --allow-dirty
```

`--allow-dirty` 只用于隔离测试。离线完整构建时，将包含全部锁定依赖、PyInstaller
及构建依赖的 wheel 目录传给发布脚本：

```bash
PYTHON=/path/to/cpython-3.12/bin/python3.12 \
DEPENDENCY_WHEELHOUSE=/path/to/wheelhouse \
UV_FIND_LINKS=/path/to/wheelhouse \
UV_NO_INDEX=1 \
OUTPUT=/tmp/xqsim-release-offline \
bash tools/release/release.sh
```

## 数据目录与生成

共享运行数据与 ELF 使用同一根目录，但不进入不可变 release：

```text
/usr/local/xqsim/data/
└── futures/
    ├── cc/             # 持续更新的完整期货缓存
    └── cc_2024/        # 固定截止 2024-12-31 的研究快照
```

首次迁移保留源数据，并用全量 checksum 验证：

```bash
mkdir -p /usr/local/xqsim/data/futures/cc
rsync -a data/futures/cc/ /usr/local/xqsim/data/futures/cc/
rsync -a --checksum --dry-run --itemize-changes \
  data/futures/cc/ /usr/local/xqsim/data/futures/cc/
```

第二条命令无输出即内容一致。生成期货数据时先更新 meta，再运行 build 配置：

```bash
uv run python providers/futures/DataProviderMetaUpdater.py
uv run xqsim -c providers/futures/config_production.yml
```

从完整缓存生成固定历史快照：

```bash
uv run python tools/futures/snapshot_cache.py \
  /usr/local/xqsim/data/futures/cc \
  /usr/local/xqsim/data/futures/cc_2024 \
  --cutoff 20241231
```

脚本按 `DateIndex.csv` 将截止日收敛到最近交易日；连续矩阵会截断 payload 并重写
header，逐日压缩文件只复制截止日以内的数据，`DateIndex.csv` 同步裁剪，且移除
截止日后才上市的 InstrumentIndex 行。目标目录必须不存在，脚本通过临时目录完整
校验后才原子改名。

配置统一使用 `${xqsim_data}`；独立 Python 工具默认读取 `/usr/local/xqsim/data`，
测试其他根目录时设置 `XQSIM_DATA_HOME`。
期货缓存使用 `update_tools` 时同时传
`--meta /usr/local/xqsim/data/futures/cc --index-category FUTURES`。

当前共享目录不部署股票数据。框架仍保留股票支持；未来需要时应另行创建
`/usr/local/xqsim/data/stocks/cc`，并先用
`providers/stocks/DataProviderMetaUpdater.py` 刷新生产 meta。

发布框架只创建并保留数据目录，不复制、删除或回滚数据。Provider 源码不得包含
数据库凭据；checkpoint、个人因子和运行输出仍不属于共享安装目录。
