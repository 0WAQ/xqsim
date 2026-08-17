# XQSim 研究员使用手册

本文面向编写、运行和评估因子的研究员，只说明系统怎样使用、模块怎样编写以及
XML 配置怎样填写。研究员不需要了解框架内部实现。

研究配置统一使用 XML。

## 1. 共享环境与个人目录

研究员使用以下共享内容：

```text
/usr/local/xqsim/
├── xqsim                  # 运行命令
├── utils.py               # 公共 NumPy 工具函数
├── operation/             # 公共 AlphaOpXxx.py
├── stats/                 # 公共 StatsXxx.py
├── provider/              # 公共 DataProviderXxx.py
├── portfolio/             # 公共 PortfolioXxx.py
├── config/                # 公共 XML 配置
└── data/futures/
    ├── cc/                # 持续更新的数据
    └── cc_2024/           # 固定截止 2024-12-31 的历史快照
```

因子、私人配置和结果放在自己的工作目录，不要修改 `/usr/local/xqsim`：

```text
my_research/
├── AlphaMySignal.py
├── Config.MySignal.xml
└── output/
    ├── cache/
    ├── csv/
    └── pnl/
```

固定研究结论优先使用 `cc_2024`，保证以后复现时数据不变；需要最新日期时使用
`cc`。

## 2. 一份完整的 XML 配置

在个人目录创建 `Config.MySignal.xml`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<QSim>
    <Macros RESEARCH="${config}"/>

    <Constants niodatapath="${xqsim_data}/futures/cc_2024"
               output_cache_dir="${RESEARCH}/output/cache"
               interval="day" backdays="60"
               index_category="FUTURES" adj_window="-1"
               overwrite="force"/>

    <Universe startdate="20230103" enddate="20241231"/>

    <Modules>
        <Module id="MySignal" path="${RESEARCH}/AlphaMySignal.py"
                handler="AlphaHandler"/>
        <Module id="Availability"
                path="${xqsim_operation}/AlphaOpAvailabilityMask.py"
                handler="AlphaOpsHandler"/>
        <Module id="Holding"
                path="${xqsim_operation}/AlphaOpHoldingAverage.py"
                handler="AlphaOpsHandler"/>
        <Module id="Scale"
                path="${xqsim_operation}/AlphaOpScaleBooksize.py"
                handler="AlphaOpsHandler"/>
        <Module id="FuturesStats" path="${xqsim_stats}/StatsFutures.py"
                handler="StatsRegistry"/>
        <Module id="EqualWeight"
                path="${xqsim_portfolio}/PortfolioSimple.py"
                handler="PortfolioHandler"/>
    </Modules>

    <Portfolio id="MyPortfolio" moduleId="EqualWeight"
               booksize="20000000" save="false">
        <Alpha id="MySignalRun" moduleId="MySignal"
               universeId="uv.all" delay="0" warmup_days="60"
               save="true" overwrite="force">
            <Operations>
                <Operation moduleId="Availability" lag="1"/>
                <Operation moduleId="Holding" holding_days="5"/>
                <Operation moduleId="Scale" target_booksize="2.0"/>
            </Operations>
            <Stats moduleId="FuturesStats" booksize="20000000"
                   dumpPnl="true" pnlDir="${RESEARCH}/output/pnl"
                   print="false"/>
        </Alpha>
    </Portfolio>
</QSim>
```

运行：

```bash
/usr/local/xqsim/xqsim -c Config.MySignal.xml
```

先用较短日期区间检查字段、shape、缺失值和输出，再扩大到完整样本。

## 3. XML 配置结构

### `QSim`

根节点。一个配置只能有一个 `QSim`。

### `Macros`

定义可复用路径。属性名和大小写由使用者决定：

```xml
<Macros RESEARCH="${config}" MODEL="${config}/models"/>
```

`${config}` 表示当前 XML 所在目录。系统还提供：

- `${xqsim_home}`：共享根目录；
- `${xqsim_data}`：共享数据；
- `${xqsim_operation}`、`${xqsim_stats}`、`${xqsim_provider}`；
- `${xqsim_portfolio}`、`${xqsim_config}`；
- `${xqsim_utils}`：公共 `utils.py` 文件路径；
- `${xqsim_modules}`：随程序提供的内置模块目录。

路径一律优先使用宏，不要写个人用户名、仓库 checkout 或版本号。

### `Constants`

全局运行参数：

| 属性 | 作用 |
|---|---|
| `niodatapath` | 数据缓存目录，必填 |
| `output_cache_dir` | 因子输出目录，应为个人可写路径 |
| `backdays` | 正式区间前额外准备的历史交易日数 |
| `interval` | 日频写 `day` |
| `index_category` | 期货写 `FUTURES` |
| `adj_window` | 真实期货合约写 `-1` |
| `overwrite` | 默认输出策略，如 `force` 或 `append` |
| `save` | Alpha 未单独设置时的默认保存开关 |
| `save_csv` | Alpha 未单独设置时的默认 CSV 目录 |

`backdays` 必须不小于最大的 `warmup_days`，并覆盖 Operation 所需的历史窗口。

### `Caches`

可选的额外只读缓存目录：

```xml
<Caches>
    <Cache path="/path/to/extra_cache"/>
    <Cache path="/path/to/another_cache"/>
</Caches>
```

### `Universe`

正式研究区间：

```xml
<Universe startdate="20230103" enddate="20241231"/>
```

日期使用 `YYYYMMDD`，也可以使用 `TODAY-1` 等相对日期。固定历史研究建议写明确
日期，避免样本随运行日变化。

### `Modules`

给文件登记逻辑 ID。后续 Alpha、Operation、Stats 和 Portfolio 只引用 ID：

| `handler` | 文件 | 导出内容 |
|---|---|---|
| `AlphaHandler` | `AlphaXxx.py` | `Alpha` 或 `create` |
| `AlphaOpsHandler` | `AlphaOpXxx.py` | `Operation` 或 `create` |
| `StatsRegistry` | `StatsXxx.py` | `Stats` 或 `create` |
| `PortfolioHandler` | `PortfolioXxx.py` | `Portfolio` 或 `create` |

`id` 只需在当前配置中唯一，不要求与文件名相同。Linux 路径区分大小写。

### `Portfolio`

Portfolio 是运行任务的外层容器。主要属性：

| 属性 | 作用 |
|---|---|
| `id` | 组合任务名 |
| `moduleId` | `Modules` 中的 Portfolio ID |
| `booksize` | 组合名义规模 |
| `save` | 是否保存组合结果 |
| `overwrite` | 组合输出覆盖策略 |

一个 Portfolio 可以包含一个或多个 `Alpha`。公共
`${xqsim_portfolio}/PortfolioSimple.py` 对子 Alpha 等权平均。

### `Alpha`

每个 `Alpha` 节点代表一次独立因子实验：

| 属性 | 作用 |
|---|---|
| `id` | 实验名及默认输出名 |
| `moduleId` | `Modules` 中的 Alpha ID |
| `universeId` | 可选 universe，如 `uv.all` |
| `delay` | 输出日期标记；目标日持仓语义的新因子通常用 `0` |
| `warmup_days` | 正式区间前逐日推进状态的天数 |
| `save` | 是否保存因子缓存 |
| `save_csv` | 可选的逐日 v1/v2/持仓输出目录 |
| `save_csv_total` | 是否连同扩展日期一起输出 |
| `overwrite` | `force`、`append`、`auto` 或 `no` |
| `dir_name` | 保存因子时使用的目录名 |

因子自定义参数也写成 Alpha 属性，例如 `window="20"`。代码中从 `self.cfg` 读取。

### `Operations` 与 `Operation`

`Operations` 内部顺序就是实际执行顺序：

```xml
<Operations>
    <Operation moduleId="Availability" lag="1"/>
    <Operation moduleId="Holding" holding_days="5"/>
</Operations>
```

`moduleId` 引用已登记的 Operation；其余属性全部作为该 Operation 的参数。

### `Stats`

Stats 可以放在单个 Alpha 内，也可以放在 Portfolio 内。常用期货配置：

```xml
<Stats moduleId="FuturesStats" booksize="20000000"
       dumpPnl="true" pnlDir="./output/pnl" print="false"/>
```

属性区分大小写，应写 `booksize`、`dumpPnl`、`pnlDir`，不要写成
`book_size`、`dump_pnl`、`pnl_dir`。

## 4. 编写 Alpha

文件名使用 `AlphaXxx.py`。最小日频因子：

```python
import numpy as np

from xqsim.api import AlphaBase


class Alpha(AlphaBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.ret = self.dr.get_data("k.returns")

    def generate(self, di):
        previous_ret = np.asarray(self.ret[di - 1])
        valid = np.isfinite(previous_ret)
        self.alpha[valid] = previous_ret[valid]
```

必须遵守：

- `generate(di)` 产出目标日 `di` 的原始因子值 v1，每次只计算一天；
- 一般只能使用 `[begin, di)` 的动态数据，最常见的信息日是 `di-1`；
- 最终给 `self.alpha` 的 ii 轴赋值，未赋值位置保持 `NaN`；
- 合约、品种和主力的选择使用与数据轴同长的布尔 mask；
- 先按日期取得数组，再使用 NumPy，例如 `np.asarray(self.close[di - 1])`；
- 滚动状态保存在实例属性中，并通过 `warmup_days` 逐日预热；
- 不要在 `generate` 内重新循环整段历史。

公共函数可以直接导入：

```python
from utils import aggregate_member_product_position
```

个人因子目录中的同名 `utils.py` 优先，适合保存只属于该研究的辅助函数。

## 5. 数据字段与 NumPy

常用期货字段：

| 字段 | 含义 | 常见 shape |
|---|---|---|
| `k.open/high/low/close` | OHLC | `di × ii` |
| `k.returns` | 合约日收益 | `di × ii` |
| `k.volume/amount/position` | 成交量、成交额、持仓量 | `di × ii` |
| `uv.all` | 当日活跃真实合约 | `di × ii` bool |
| `hot.ii` | 当日主力合约标签 | `di × ii` |
| `static.pi` | ii 对应品种标签 | `di × ii` |
| `ind.l1/ind.sector` | 品种行业标签 | `di × ii` |
| `rk.long_pos/short_pos` | 会员持仓排名 | `di × rank × ii` |
| `rk.*_member` | 对应排名的会员编号 | `di × rank × ii` |

所有合约数据最后一维都是 ii。三维会员数据先选日期得到 `rank × ii`，再做聚合。
缺失值使用 `np.isfinite` 构造 mask；除非零有明确业务含义，不要先把 `NaN` 全部
替换为零。

## 6. Operation：从 v1 到 v2

Operation 处理目标日 `di` 的当前 alpha，并原地修改数组：

```python
import numpy as np

from xqsim.api import OperationBase


class Operation(OperationBase):
    def apply(self, di, alpha):
        valid = np.isfinite(alpha)
        alpha[valid] = np.sign(alpha[valid]) * np.sqrt(np.abs(alpha[valid]))
```

前一个 Operation 的输出是后一个的输入。Operation 可以使用自己的历史窗口，但要
明确是否包含 `di`，并避免使用目标日尚不可获得的数据。

公共 Operation：

| 文件 | 用途 | 主要参数 |
|---|---|---|
| `AlphaOpSectorNeutralize.py` | 排名标准化、行业中性 | `min_cs`, `min_unique` |
| `AlphaOpAvailabilityMask.py` | 按历史收益可用性过滤 | `lag` |
| `AlphaOpPowerInvvol.py` | signed power、逆波动加权 | `power`, `inverse_vol_window`, `inverse_vol_floor_quantile`, `min_names` |
| `AlphaOpHoldingAverage.py` | 多日目标持仓平均 | `holding_days` |
| `AlphaOpScaleBooksize.py` | 缩放 gross exposure | `target_booksize`, `atol` |
| `AlphaOpMapToHot.py` | 品种槽映射到目标日真实主力 | 无 |

主力槽因子应把 `AlphaOpMapToHot.py` 放在链尾。

## 7. Stats：评估结果

Stats 接收 Operation 链后的 v2：

- `StatsGeneral.py` 使用股票字段和股票口径；
- `StatsFutures.py` 使用期货 `k.returns` 名义本金口径。

期货研究不要使用 `StatsGeneral.py`。期货 Stats 可输出 raw、daily 和 year CSV。
自定义 Stats 使用 `StatsXxx.py`，导出 `Stats` 或 `create`，并明确收益、换手、费用、
保证金和缺失值口径。

## 8. Portfolio：组合多个 Alpha

公共 `PortfolioSimple.py` 对所有子 Alpha 做等权平均。自定义 Portfolio：

```python
import numpy as np

from xqsim.api import PortfolioBase


class Portfolio(PortfolioBase):
    def generate_portfolio(self, di, alpha_list):
        self.alpha = np.mean(np.asarray(alpha_list), axis=0)
```

组合前应确认子因子的量纲、方向、缺失值、Operation 链和 universe 可比。

## 9. Provider：公共数据贡献

普通因子研究直接读取共享缓存，不需要在研究 XML 中注册 Provider。只有新增公共字段
或维护数据时才编写 `DataProviderXxx.py`。贡献说明必须包含：

- 数据源和可用时点；
- 输出字段名、dtype、shape 和缺失值；
- 全量、增量或静态写入范围；
- 覆盖行为和验证方法；
- 凭据文件位置，源码中不得出现密码。

共享数据构建由维护者使用审核过的 XML 和部署流程执行；个人研究不得直接覆盖共享
缓存。

## 10. 复现与提交清单

一次可复现研究至少保存：

1. 因子假设、公式和目标持仓语义；
2. 完整 XML 配置；
3. 数据目录、截止日期和样本区间；
4. Alpha、Operation、Stats、Portfolio 的版本和参数；
5. v1/v2 覆盖率、分布和异常值检查；
6. PnL、换手、容量假设和样本内外结果；
7. `/usr/local/xqsim/xqsim --version` 输出。

先验证数据和时序，再解释收益。使用目标日之后数据的结果不能作为有效回测。
