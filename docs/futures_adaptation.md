# XQSim 期货适配方案

本文档记录将 xqsim 从股票截面回测适配到期货的评估结论与改动方案。
配套阅读：`docs/architecture.md`（引擎机制）。

> 2026-08-08 修订：引入 ldcta（common_cache_mssql_cron_ldcta）后，
> 推荐路线由「主力连续合约」修正为「真实合约 ii + hot 映射」，见第 2、5 节。

## 0. 核心结论

引擎是「每个 ii 一个数」的截面模型（di × ii × ti），品种无关。**推荐路线下引擎本体零改动**，
所有改动落在数据生产与可插拔模块层（provider / op / stats 本来就是配置按 file_path
动态加载的，新增模块不算改引擎）。

推荐路线（2026-08-08 修订）：**真实合约 + 槽位复用 ii + 主力（hot）映射筛可交易合约
+ day 级先行**。槽位复用沿用 ldcta 思想，xqsim meta_loader 天然兼容（见 2.1 节）。

双资产定位：同一套引擎分市场跑（股票一个 `meta_dir`、期货一个 `meta_dir`），
不做股期混合截面（见第 6 节）。

## 1. 运行前置条件（现状）

引擎入口已通（`uv sync` + `uv run xqsim --version`），跑起来还需：

1. **meta 索引**：`meta_dir` 下要有 `meta/index/{DateIndex,InstrumentIndex,StaticIndexSize}.csv`。
   仓库现成一份股票全市场的在 `data/stocks/cc/meta/`，放/软链到 `meta_dir` 指向处；
   期货侧由 `providers/futures/meta_updater.py` 生成到 `data/futures/cc/meta/`。
2. **sample 配置路径**：`examples/sample_config.yml` 假设工作目录有 `./module` 和 `./cc`，
   是旧布局遗留；要么搭 staging 目录做软链，要么改配置里的 `provider_dir` 宏。
3. **数据源凭证**：kline/universe provider 从 MySQL 抽数，`providers/mysql.json` 是占位符；
   无 MySQL 可走 CSV 流程（`providers/config_csv.yml` + `tools/prefect/csv_flow.py`）。
   期货侧数据源为 MSSQL（见第 5 节），需要 `pymssql` 依赖和可达的网络。
4. **运行顺序**：先 `build: true` 刷缓存 → `update_tools check <cache_dir>` 校验 →
   再跑完整回测配置。

## 2. 股票特异性分布与期货改动点

### 2.1 Universe / instrument 语义（最大改动）

- 股票：instrument 持久（上市→退市），`InstrumentIndex.csv` = WindCode + StartDate/EndDate。
- 期货：合约有到期日，且品种（product，永续）与合约（contract，寿命约一年）是两层概念。
  候选建法：
  - **真实合约 + 槽位复用 ii（推荐，2026-08-08 定）**：沿用 ldcta 的槽位制思想——
    ii 空间有界（如 80 品种 × 50 槽 = 4000），同一槽位在不同时段承载不同合约。
    xqsim 的 meta_loader 按天按槽填充 `instrument_index[di][ii]`，同一 ii 在
    InstrumentIndex.csv 里写多行（不同合约、日期段不重叠）即可实现槽位复用，
    **loader 零改动**。已知次要影响：`all_instrument_index[ii]` 后写覆盖只留最后
    一段的合约码（仅影响展示）；`ii_mapping[合约码] = ii` 因合约码唯一而无冲突。
  - 真实合约 + 终身 ii（否决）：槽位无限膨胀、僵尸列、合约语义稀释。
  - 主力连续合约当持久 ii（降级为备选）：需要换月映射 + 连续价格复权，
    不如真实合约干净。
- **EndDate 排他语义（重要）**：加载器对每行按 `[StartDate, EndDate)` 左闭右开填充
  （EndDate 当天无效）。股票行 EndDate=20751231 所以历史无感。期货约定：
  **EndDate 写合约最后交易日**（当天即被排除，符合"末日不交易"惯例）；
  StartDate/EndDate 必须是日历中存在的交易日（加载时直接查 di 映射，
  落在周末/假日会 KeyError）。同一槽位的多段**只需不重叠**，段间空窗是正常状态
  （空 = 该槽当天无合约），无需任何衔接约定；若两段重叠，重叠期的值会被
  CSV 后一行覆盖（顺序依赖，要避免）。
- **策略侧认知**：一列 = 同一月份合约的跨年接力（如 rb 某槽 = 历届 10 月合约），
  列内不做跨换月连续假设；跨换月的仓位连续性由主力（hot）标记 + op 层负责。

改动物：futures universe provider（由 MSSQL 合约表生成 InstrumentIndex，
含 8888 主力/0000 指数虚拟槽行）、hot 主力映射 provider（移植 ldcta
`builder/futures_hot.py` 的持仓量排序 + 防回跳平滑逻辑）。

### 2.2 复权通道（真实合约路线下基本闲置）

- 股票：`k.adj` 复权因子（分红拆股），`adj_window` 控制窗口，
  实现在 `xqsim/data/data_repository_impl.py` 的 `__prepare_adj`，
  格式层是 `DataHeader.adj_mode`（ADJ_NONE/ADJ_PRICE/ADJ_VOLUME）。
- 期货真实合约路线：价格即真实成交价，**不需要复权**，配置 `adj_window: -1` 关闭
  （注意 `adj_window > 0` 时 `__prepare_adj` 强制要求 `k.adj` 存在）。
- 备选连续合约路线才需要把换月调整因子灌进 `k.adj` 复用该通道。

改动物：无（真实合约路线）。

### 2.3 仓位与盈亏口径（ops + stats 模块）

- 股票口径：仓位 = 金额/股数；ret = pnl / book_size；turnover 按成交额
  （见 `xqsim/utils.py` 的 stats 公式：sharpe / bpmargin / tvr / mdd 等）。
- 期货口径：**PnL = Δ价 × 合约乘数 × 手数**。

改动物（全部是插拔模块，不动引擎）：

- `multiplier`（合约乘数，每品种固定）：新静态票维数据 provider，
  数据可取自 ldcta 的合约信息表（`provider/futures_instrument_info.py` 对应来源）。
- 期货版 stats 模块：先定收益口径（按保证金 or 名义本金），再逐个核对
  sharpe / bpmargin / tvr 等公式。
- 期货版 op：仓位 sizing 按手数；按 hot 映射筛主力/移仓；分组中性化用品种
  （pi）分组而非股票行业。

### 2.4 品种（pi）维度

期货特有的第二维：品种（约 80 个）⊃ 合约（数千）。引擎只有 ii 一维，pi 不进引擎，
作为**静态票维数据**由 provider 产出（每个 ii 一个 product_id），分组类 op
（中性化、分组排序）从 dr 读它即可。ldcta 的 pi/pi_mapping 概念照此落地。

### 2.5 日历与交易时段

- day 级：DateIndex 换期货交易日；注意**夜盘归属**（国内惯例夜盘算下一交易日）。
  股票/期货交易日历在 day 粒度基本一致，可复用同一套日历机制。
- 分钟/tick 级：`meta/time_index/` 的 `minute1_239.csv` 等是股票 240 分钟交易日的
  产物，需按期货时段（含夜盘）重新生成。

#### 夜盘适配方案（二期预留）

现状障碍：`MetaLoader.__check_time` 用 date × time 笛卡尔积构建 `interval_date_time_index`，
隐含两个假设：一个交易日内时间单调递增、时间都属于当天自然日。夜盘
（21:00-23:00 + 次日 00:00-02:30，归属下一交易日）两个假设都打破，
`Meta.get_ti` 的二分和 strptime 的 `%H < 24` 限制都会失效。

推荐方案——**虚拟时钟**（业界标准做法）：跨零点的时间 +24 小时，
使一个交易日内时间轴严格单调：

```
一个期货交易日的时间轴: 09:30 ... 15:00, 21:00 ... 23:59, 24:00 ... 26:30
                                                       ↑ 次日00:00  ↑ 次日02:30
```

需要改动（均在 meta 时间处理层，引擎主循环/DataView/缓存格式不动）：

1. time_index CSV 按虚拟时钟生成：夜盘时段写为 21:00-26:30，ti 连续编号，
   文件格式不变；
2. `__check_time` 的时间解析：strptime 改为「日期 + 当日秒数偏移」的手工构造
   （timedelta），绕开 `%H < 24` 限制；
3. provider 时间戳映射：原始行情的自然日时间戳映射为「归属交易日 + 虚拟时间」
   （如周五 21:30 → 下周一交易日 21:30；周六 01:00 → 下周一 25:00），
   属数据侧规则，引擎无感。

展示层如需打印真实时间，最外层加一个 `25:30 → 01:30(+1)` 的转换函数即可。

改动物：meta CSV 数据本身；引擎零改动。

## 3. 改动清单汇总

| 层 | 内容 | 是否动引擎 |
|---|---|---|
| meta 数据 | DateIndex / InstrumentIndex（合约 listed/expired）/ time_index 换期货 | 否 |
| provider | 期货 universe、kline、hot 映射、multiplier、pi 静态数据 | 否（新模块） |
| op | 品种分组中性化、hot 筛主力/移仓、按手数 sizing | 否（新模块） |
| stats | 期货盈亏口径（乘数、保证金/名义本金） | 否（新模块） |
| 引擎 | Simulator / AlphaTask / DataView / DataManager / checkpoint | **零改动** |

引擎内仅有的两个股票假设，均可用配置绕开：

1. `adj_window > 0` 时 `__prepare_adj` 强制要求 `k.adj` —— 真实合约路线
   `adj_window: -1` 关闭即可。
2. `k.` 前缀与 `adj_mode` 是格式约定，沿用即可。

## 4. 与 ldcta（common_cache_mssql_cron_ldcta）的关系

2026-08 引入的参考项目：ywang 的期货 common cache 系统（MSSQL 数据源、cron 日更、
裸二进制缓存格式）。与 xqsim 的关系定位：**同一个思想（meta 索引 + 按 di 排行的
二进制截面缓存）的两次实现**，不长期维护两套，避免 meta 双真相源漂移。
ldcta 无活跃下游需要照顾（2026-08-08 确认）。

处置方式：

| ldcta 组成 | 处置 |
|---|---|
| 缓存文件格式 / manager.py 读写层 / viewers | **弃用**。xqsim 的 DataManager/DataView 更成熟（header、压缩、append、内存管理） |
| MSSQL 数据库（FuturesData.dbo.\*、Meta.dbo.\*） | **作为数据源**。xqsim futures provider 直读，与股票 provider 读 MySQL 同一位置 |
| `base.py` 代码换算（CZC 年份位、RO→OI 等品种码） | **移植**进 xqsim futures provider / 工具函数 |
| `builder/futures_hot.py` 主力构建（持仓量排序 + 防回跳） | **移植**为 hot 映射 provider |
| 合约 ii 模型（listed/expired、IIModel） | **借鉴**为 InstrumentIndex 生成逻辑 |
| meta.py 模块级连库 / 明文凭证 / exit(-1) | **不移植**，这些是要避开的设计 |

注意：ldcta 的 MSSQL 连接串含明文凭证，移植时用 xqsim 的 `mysql_config`
同款外置配置文件机制，不入库。

## 4.1 一期实施结果（2026-08-09，已落地并通过比对）

ldcta 已拆分为 `providers/futures/`（对齐 stocks 布局）：

| 文件 | 来源 | 产出 |
|---|---|---|
| `futures_common.py` | ldcta `base.py` 纯函数 | wind码→标准码换算、槽位常量 |
| `mssql_provider.py` | 新建基类（仿 stocks `static_provider.py`） | `exec_sql_fetchall` / `get_ii` / `listed_code` / `fetch_oi_rows` |
| `meta_updater.py` | `builder/futures_ii.py` | 直接落 meta CSV，砍掉 MSSQL 中间表；**EndDate = 摘牌日下一交易日**；StartDate 吸附到首个 ≥ 上市日的交易日（wind 上市日不一定是交易日） |
| `hot_builder.py` | `builder/futures_hot.py` | 主力判定内存计算：持仓排序 + 不回退 + 1.1x 滞回；砍掉 hot 表往返 |
| `kline.py` | `provider/futures_kdata.py` | `k.open/high/low/close/volume/amount/settle/position/preclose/returns` + 48 号主力槽拷贝 |
| `universe.py` | `provider/futures_universe.py` | `uv.all`（活跃合约）+ `static.pi`；不连库 |
| `hot.py` | `provider/futures_hot.py` | `hot.ii` / `hot.ii_next`（修掉 ldcta 顺序 bug） |
| `instrument_info.py` | `provider/futures_instrument_info.py` | `static.multiply` / `static.ticksize` |
| `config_production.yml` | 新建 | `index_category: FUTURES`、`adj_window: -1` |

运行（需 MSSQL 网络，`mssql.json` 已配）：`meta_updater.py` →
`uv run xqsim -c providers/futures/config_production.yml` →
`tools/futures/compare_ldcta.py` 比对。

### kline 语义（实证自 ldcta 生产缓存，与 ldcta 当前代码已漂移）

**ldcta 生产缓存 ≠ ldcta 仓库代码**（生产是「直通+整行前填」，代码是
「is_valid 闸门+OHLC=昨收前填」——代码漂移，语义以生产数据为准）：

- 直通：wind 有行写原值；OHLC null → NaN（无成交日 wind 仍发布 close/settle）
- volume/amount/position null → 0.0；amount ÷ 100
- 前填：段内 wind 完全无行的日子**整行复制上一日**（含 OHLC，上日 NaN 则填 NaN），
  preclose=上一日 close，returns=0；段首从未有行的日子保持 NaN
- preclose = 前一日 close（段首 NaN）；returns = close/preclose-1，
  段首 close/open-1，open 也缺则 NaN

### 全量比对结果（20160104~20260807，2574 天 × 4000 槽）

- `uv.all`、`k.close/settle/volume/amount/position`、`static.multiply/ticksize`
  真实槽：**零失配**
- `k.preclose`/`k.returns`：真实槽各 5 格边角
- `k.open/high/low`：真实槽 500 格，全部是强麦（wr）2018-09~2019-01 段——
  wind 对死品种历史行做过回溯清理，生产缓存是当年快照，**不可复现，以新数据为准**
- hot 槽 ~6000 格 + `hot.ii` 1839（0.13%）：生产 hot 表对停牌/退市品种
  （bb/JR/PM/RI/ZC 等）保留陈旧主力并每天拷贝旧值；本实现重算主力、
  无交易品种给 NaN。**以本实现为准**
- `hot.ii_next` 64814（4.6%）：次主力依赖 ldcta 历史表播种，口径模糊，一期挂起

### pi 维基本面（warehouse / instock / wind_commodity，2026-08-09 补齐）

- 存储约定：pi 维数据**原生 di×80 存储**（缓存格式在 `shape[1] != meta.ii_size`
  时文件名记为 `M80`，读写/DataView 全链路已验证），消费方 `view.data[:, pi]`
  直接读取；由 `MssqlProvider.write_pi_data` 落地
- `wh.*`（仓单 7 字段）/ `istk.*`（交割库存 2 字段，CTAMap join）/
  `wc.*`（库存 3 字段，CONTPRO join）；`futures_apispot` 废弃（与 warehouse 重复）
- **ldcta `wind_commodity` 三 buffer 同写 bug 已修**（生产三文件内容相同，实锤；
  其 `in_stock_total`/`available_in_stock` 无比对价值）
- ldcta 的硬编码品种剔除名单（LR、SC、NR、LU、BC、PTA）不沿袭：meta 里有的
  品种统一收录。因此比对时 LR（wh.*）和 PTA（istk.*）列"失配"为预期差异——
  我方有 wind 真实值（0.0），ldcta 为 NaN，**以本实现为准**
- 其余字段（wh.on_warrant/available_warehouse/cancelled_warrants、wc.in_stock）
  零失配

### 遗留问题

- **数据权威链**：wind（会回溯改历史，wr OHLC 实证）→ 本仓库 provider 代码 →
  xqsim 缓存，每环可全量重放。ldcta 生产缓存是十年增量构建的化石
  （当时 wind 快照 × 当时代码版本 × 当时 hot 表状态），不再作为语义依据
- **增量路径未验证**：目前只跑过全量重建；`TODAY-10` 小窗口日更有两个已知
  薄弱点——hot 窗口首日播种差异、`do_generate` 目录存在即静默跳过。
  首次日更后应对当天数据跑一次 compare_ldcta 确认与全量一致
- `hot_builder` 窗口首日播种与 ldcta 历史表不同（日更小窗口首日主力可能差一天，
  日更建议带几天回看窗口）
- 死品种 hot 槽语义差异（上表），若下游策略依赖陈旧主力需知悉
- pi 维基本面（库存/仓单/现货）已落地（见上节）；若以后扩充到 GFEX/INE/CFFEX
  品种，注意 ldcta 的剔除名单已废弃，新品种自动收录
- 夜盘/分钟级、期货版 op/stats：见第 6 节分期

## 5. 股票 + 期货双资产适配评估

「一套引擎同时适配股票和期货」的需求**合理**，但按以下边界理解：

- **同一引擎、分市场跑（采纳）**：股票一个 `meta_dir`、期货一个 `meta_dir`，
  各自配置各自回测。引擎的 di×ii×ti 模型品种无关，资产差异全部压到
  meta 数据 + provider + 可插拔 stats/op 层。引擎零改动。
- **股期混合截面（不采纳，至少现在不做）**：需合并 ii 空间、处理期货夜盘时段、
  仓位口径混算（股数 vs 手数×乘数）、跨资产分组中性化，引擎和 stats 都要实质改动。
  做期货截面策略不需要它；如未来做股期混合配置再单独立项。

## 6. 分期建议

- **一期**：day 级 + 真实合约 ii + hot 映射筛主力 + 名义本金口径 stats。
  工作量集中在 provider 移植（MSSQL 读取、换月规则、multiplier、pi）和
  期货版 stats/op 模块。
- **二期**：分钟/tick 级（夜盘时段与归属）、保证金口径收益。
- **三期（可选）**：股期混合截面，视策略需要再评估。
