# QSim 架构文档

## 1. 一个因子是怎么跑的

框架按交易日连续调用，`di > 0`。有状态因子可以先请求 warmup，再进入正式
回测区间：

```python
# 可选：只推进原始因子的历史状态，不执行 Operation、保存或 Stats
for di in range(begin_di - warmup_days, begin_di):
    alpha.generate(di)

for di in [begin_di .. end_di]:
    # Step 1: 因子计算，产出 v1
    alpha.generate(di)

    # Step 2: Operator 链式变换，v1 → v2
    for op in operators:
        op.apply(di, alpha)

    # Step 3: v2 → 持仓缩放 → 交易模拟 → 累积 PnL
    stats.calculate_di(di, alpha)

# Step 4: 汇总 PnL 序列，输出 Sharpe/MDD/IC 等绩效指标
stats.save_pnl()
```

---

## 2. Step 1：Alpha 产出 v1

```python
class MyAlpha(AlphaBase):
    def generate(self, di):
        # self.alpha 是长度 6000 的向量，每个位置 = 一只股票的因子值
        # 目标日 di 的仓位只使用 di 之前的数据
        self.alpha[:] = self.close[di - 1] / self.close[di - 21] - 1
```

`generate(di)` 的输出语义是目标日 `di` 的仓位或信号，动态数据一般只能来自
`[history_begin, di)`。函数返回后、Operation 执行前的 `self.alpha` 是
**v1（原始因子值）**。滚动历史由 Simulator 按 `warmup_days` 显式逐日推进，
不应在一次 `generate` 内隐藏回放循环。
AlphaManager 在每次正式调用和 warmup 调用前重置 `self.alpha`，因子只负责写入
当天 v1，不需要在 `generate` 内再次 reset。

---

## 3. Step 2：Operator 链 (v1 → v2)

```
v1 (原始因子值)
 │
 ├── Op1: 去极值 (截断 ±3σ)
 ├── Op2: 行业中性化 (截面回归取残差)
 ├── Op3: 标准化 (z-score)
 ├── Op4: 衰减 (0.5×yesterday + 0.5×today)
 │
 ▼
v2 (处理后的因子值)
```

每个 Operator 接收上一步的 alpha 向量，原地修改，传给下一个：

```python
class DecayOp(OperationBase):
    def apply(self, di, alpha):
        alpha[:] = self.decay * self.last_alpha + (1 - self.decay) * alpha
        self.last_alpha = alpha.copy()
```

Operation 对目标日 `di` 的当前 alpha 原地变换；它使用哪一天或哪段辅助数据由
自身语义决定。整条链执行结束后的 `self.alpha` 是 **v2（处理后因子值）**。
Operation 可以有状态（比如衰减要记住昨天的值），所以必须在逐日循环内执行。

---

## 4. Step 3：v2 → 持仓 → PnL

v2 本身只是一个打分，还不是仓位。Stats 的 `calculate_di` 里做这个转换：

```python
def calculate_di(self, di, alpha):
    # 1. 过滤 + 归一化
    alpha = self.calculate_alpha(di, alpha)
    #    - universe 过滤 (去掉 ST、停牌、不在成分股的)
    #    - benchmark 模式下只保留正值 / top-N 截取
    #    - normalize (可选)

    # 2. 缩放到目标仓位
    value = scale_book_size(alpha, self.book_size)
    #    - 多头总额 = book_size/2, 空头总额 = book_size/2
    #    - 涨跌停限制 (涨停不能买、跌停不能卖)

    # 3. 对比昨日持仓, 模拟交易算 PnL
    self.calculate_general(di, value, self.last_value)
    #    - 拆为 延续持仓 / 新开仓 / 平仓, 用不同价格结算
    #    - trade_price 可配置为 vwap / open / close

    self.last_value = value
```

---

## 5. 分钟频因子

日频时框架只遍历 `di`；分钟频时框架同时遍历 `di` 和 `ti`，因子接口变为 `generate(di, ti)`：

### 主循环对比

```python
# 日频
for di in [begin_di .. end_di]:
    alpha.generate(di)
    for op in operators:
        op.apply(di, alpha)
    stats.calculate_di(di, alpha)

# 分钟频
for di in [begin_di .. end_di]:
    for ti in [begin_ti .. end_ti]:
        alpha.generate(di, ti)
        for op in operators:
            op.apply(di, alpha)
        stats.calculate_di(di, ti, alpha)
```

### 因子写法

因子不需要关心循环，只实现单根 bar 的逻辑：

```python
class MinuteAlpha(AlphaBase):
    def generate(self, di, ti):
        # 框架每根 bar 调一次，因子只管算当前截面
        self.alpha[:] = self.close[di][ti] / self.close[di][ti - 1] - 1
```

### 数据维度

```
日频数据:   shape = (di_size, ii_size)            e.g. (242, 6000)
分钟频数据: shape = (di_size, ti_size, ii_size)   e.g. (242, 48, 6000)  ← minute5 一天48根bar
```

配置里通过 `interval` 控制：
```xml
<Universe startdate="20220101" enddate="20221231" interval="minute5"/>
```

---

## 6. 绩效统计 (Stats)

Stats 是回测框架的最后一环，负责将持仓转化为绩效数字。它的代码结构：

```python
class Stats(StatsBase):
    def __init__(self, dr, cfg):
        # 从 DataRepository 拿行情数据
        self.close = dr.get_data("k.close")
        self.vwap = dr.get_data("k.vwap")
        self.preclose = dr.get_data("k.preclose")
        ...
        # 从配置读参数
        self.book_size = cfg["book_size"]
        self.trade_price = cfg["trade_price"]  # vwap / open / close
        self.benchmark = cfg["benchmark"]      # hs300 / zz500 / None

    def calculate(self, alpha_array):
        """回测结束后调用, 遍历所有 di 累积 PnL 序列"""
        for di in range(begin_di, end_di + 1):
            self.calculate_di(di, alpha_array[di])
        self.save_pnl()  # 输出 CSV + 年度汇总

    def calculate_di(self, di, alpha):
        """单日: v2 → 持仓缩放 → 和昨日对比算 PnL"""
        alpha = self.calculate_alpha(di, alpha)   # universe过滤 + 归一化
        value = scale_book_size(alpha, self.book_size)  # 缩放到目标仓位
        pnl = self.calculate_general(di, value, self.last_value)
        self.last_value = value
```

Stats 最终输出：
- 每日 PnL 序列 → 聚合为 Sharpe / MDD / Calmar / IC / 换手率等指标
- 按年度分组的绩效表
- CSV 文件（raw / daily / year 三个粒度）

---

## 7. 数据层

回测计算需要的行情数据（K线、Universe、行业分类等）由数据层提供。分为两部分：

### 7.1 DataRepository（数据读取）

因子和 Stats 通过 `dr.get_data()` 统一访问数据：

```python
class MyAlpha(AlphaBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.close = self.dr.get_data("k.close")     # 收盘价 (di × ii)
        self.volume = self.dr.get_data("k.volume")    # 成交量
        self.ret = self.dr.get_data("k.ret")          # 日收益率
        self.uv = self.dr.get_data("uv.hs300")        # 沪深300成分 (bool)
```

单个名称返回 `DataViewImpl`（抽象类型为 `DataView`），而不是直接返回
`ndarray`。它包装当前加载的数据块，并把全局 `di` 转换成块内下标：

```python
close = self.dr.get_data("k.close")
row = close[di]                 # ndarray, shape (ii_size,)
window = close[di - 20:di]      # stop 不包含 di
raw = close.data                # 当前内存块的底层 ndarray
first_di = close.offset_di      # raw[0] 对应的全局 di
```

因子应优先通过 `view[di]` 或 `view[begin:di]` 读取；不要把全局 `di` 直接用于
`view.data[di]`，因为 `.data` 使用局部下标。分段加载时，DataView 还能在访问
窗口越界时请求 DataRepository 重载对应数据块。

传入多个名称或通配符匹配到多个名称时，`get_data()` 返回
`dict[str, DataViewImpl]`；最终只解析出一个名称时仍直接返回单个 DataView。

#### 返回形态

| 调用 | 返回值 |
|---|---|
| `get_data("k.close")` | 单个 `DataViewImpl` |
| `get_data("k.close", "k.volume")` | `dict[str, DataViewImpl]` |
| `get_data("k.*")` 匹配多个名称 | `dict[str, DataViewImpl]` |
| 多名称/通配符最终只解析出一个名称 | 单个 `DataViewImpl`，不是字典 |

不存在的明确名称会让框架 abort；通配符一个都未匹配时返回空字典。

#### 索引与 offset

DataView 接收全局 `di`，内部按下面的关系访问当前内存块：

```text
local_di = global_di - view.offset_di
```

例如当前数据块 `offset_di == 6126`：

```python
close = dr.get_data("k.close")
row = close[6613]                 # 实际读取 close.data[487]
value = close[6613, ii]           # tuple 索引继续作用于 ii 轴
rank = dr.get_data("rk.long_pos")
rank_row = rank[6613]             # shape (ri_size, ii_size)
rank_value = rank[6613, ri, ii]
```

切片右端不包含 stop，并且 start、stop 都必须显式提供；`view[:di]` 和
`view[begin:]` 不受支持。分段加载时，请求窗口必须能被当前 segment/back_days
覆盖，因此配置的 `back_days` 至少要达到因子的最大历史窗口。

#### 常用属性

| 属性/方法 | 含义 |
|---|---|
| `.data` | 当前内存块的底层 `ndarray`，使用局部下标 |
| `.offset_di` | `.data[0]` 对应的全局交易日下标 |
| `.offset` | 内部索引 offset；日频通常与 `offset_di` 相同 |
| `.shape` | 当前内存块形状，不是全历史逻辑形状 |
| `.dtype` | 底层数组 dtype |
| `.name` | 数据名称，如 `k.close` |
| `.size` | 当前实现返回底层数组第 0 轴长度 |
| `.enable_write()` | 将底层数组设为可写；普通因子读取不应调用 |

`.shape` 和 `.data.shape` 适合读取维度信息，例如 cube 的 `ri_size`；但
`.data` 绕过了全局日期转换和越界检查。若确实需要局部数组，下标应写成
`di - view.offset_di`，并明确处理后续 reload。

#### 分段重载与对象生命周期

当目标 `di` 不在当前内存块时，DataView 会调用 `DataRepository.reload()`；
DataRepository 在原数组上装入新 segment，并更新共享的 `offset_di`。
底层内存可能因此被覆盖。若要跨多个交易日长期保存 `view[di]` 的结果，应使用
`view[di].copy()`，不要长期持有可能随 reload 改变的底层数组视图。

所有数据统一存储为 `(di × ii)` 或 `(di × ti × ii)` 的 numpy 矩阵，落盘为带 header 的二进制文件。命名约定：

- `k.close` / `k.open` / `k.volume` / `k.vwap` — K线行情
- `k.ret` — 收益率
- `k.upper` / `k.lower` — 涨跌停价
- `uv.hs300` / `uv.zz500` — 成分股 universe（bool 矩阵）
- `idx.k.hs300.ret` — 指数收益率

### 7.2 Provider（数据生产）

Provider 从外部数据源（MySQL / CSV）拉数据，写入磁盘缓存供 DataRepository 读取：

```python
class KLineProvider(ProviderBase):
    def generate(self):
        sql = "SELECT TradingDay, WindCode, ClosePrice, ... FROM ..."
        array = np.full((self.meta.di_size, self.meta.ii_size), nan)

        for row in self.exec_sql_fetchall(sql):
            di = self.meta.offset_di_mapping[int(row["TradingDay"])]
            ii = self.meta.ii_mapping[row["WindCode"]]
            array[di][ii] = row["ClosePrice"]

        self.write_data("k.close", array)
```

Provider 通过配置注册，在回测前的 build 阶段运行：

```xml
<QSim>
    <Constants build="true" niodatapath="/cc"/>
    <Modules>
        <Module id="KLine" path="./kline.py" handler="ProviderHandler"/>
        <Module id="Universe" path="./universe.py" handler="ProviderHandler"/>
    </Modules>
</QSim>
```

数据流向：

```
MySQL / CSV → Provider.generate() → output_cache_dir → merge → 生产缓存 (/cc)
                                                                     ↓
                                                        DataRepository.get_data()
                                                                     ↓
                                                              Alpha / Stats
```

Provider 产出写入临时目录（`output_cache_dir`），通过 `update_tools merge_dir` 合入生产缓存，不直接写生产目录。

---

## 8. 回测框架的边界

```
              ┌────────── 回测框架 ──────────┐
              │                              │
因子代码 ──►  │  Operator链 (v1→v2)          │
  (v1)        │  持仓缩放 (v2→仓位)          │  ──► PnL / Sharpe / MDD
              │  交易模拟 (仓位→收益)         │
              │  绩效统计                     │
              │                              │
              └──────────────────────────────┘
```

- **输入**：每天每个标的一个因子值 (v1 向量)
- **框架做的事**：Operator 变换 → 缩放为仓位 → 模拟交易 → 算绩效
- **输出**：PnL 曲线 + Sharpe / MDD / IC 等

**为什么 Operator 链属于框架内部：**
1. Operator 有状态（衰减需要昨天的值），必须在逐日循环里跑
2. 我们评估因子看的是 v2 之后的绩效，不是 v1 的
3. Operator 的选择和参数是回测配置的一部分，换一套 Op 结果完全不同

---

## 9. 配置示例

```xml
<?xml version="1.0" encoding="ISO-8859-1"?>
<QSim>
    <Constants backdays="20" niodatapath="/cc" adj_window="5"/>
    <Universe startdate="20220101" enddate="20221231"/>

    <!-- 注册模块 -->
    <Modules>
        <Module id="MyAlpha" path="./my_alpha.py" handler="AlphaHandler"/>
        <Module id="OpPower" path="./alphaoppower.py" handler="AlphaOpsHandler"/>
        <Module id="OpDecay" path="./alphaopemadecay.py" handler="AlphaOpsHandler"/>
        <Module id="OpNeut" path="./alphaopriskneut.py" handler="AlphaOpsHandler"/>
        <Module id="Stats" path="${xqsim_modules}/stats_general.py" handler="StatsRegistry"/>
    </Modules>

    <!-- 回测任务: 因子 + Operator链 + Stats -->
    <Portfolio booksize="2e8">
        <Stats moduleId="Stats" book_size="2e8" benchmark="hs300"
               trade_price="vwap" limit="true" expert="true"/>
        <Alpha moduleId="MyAlpha" id="alpha1" universeId="uv.zz1000" n="20">
            <Operations>
                <Operation moduleId="OpPower"/>
                <Operation moduleId="OpDecay"/>
                <Operation moduleId="OpNeut"/>
            </Operations>
        </Alpha>
    </Portfolio>
</QSim>
```

改 XML 就能切换因子、换 Operator 组合、调仓位规模，不需要写脚本。

---

## 10. 单文件发布与外部研究模块

研究员使用 `/usr/local/xqsim/xqsim`，它是面向 Linux x86_64 的单文件 ELF，
内含 CPython 3.12、运行依赖和 Cython 编译后的核心实现。平台 wheel 仍是发布
流水线内部的可验证中间产物，不要求研究员安装 Python、uv 或虚拟环境。
PyInstaller one-file 启动时会把原生库释放到临时目录，因此目标机器的临时
文件系统必须允许加载和执行动态库。

`tools/release/release_manifest.py` 同时控制两个显式边界：每个 `xqsim/`
模块必须归入 source、compiled 或带理由的 excluded 分类；Cython 扩展中静态
分析不可见的运行时 import 必须列入 frozen hidden imports。任何未分类核心模块
或冻结后缺失依赖都会使构建或真实启动 smoke test 失败。

框架版本不可变，根级符号链接负责原子升级和回滚；公共研究代码独立于框架版本：

```text
/usr/local/xqsim/
├── xqsim -> releases/<version>/xqsim
├── releases/<version>/{xqsim,manifest.json,SHA256SUMS}
├── operation/
├── stats/
├── provider/
└── config/
```

配置加载器默认注入 `${xqsim_home}` 以及 `${xqsim_operation}`、
`${xqsim_stats}`、`${xqsim_provider}`、
`${xqsim_config}`；测试环境可用 `XQSIM_HOME` 覆盖根目录。原有
`${xqsim_modules}` 继续指向可执行文件内置模块。`${xqsim_alpha}` 仅作为旧配置
兼容宏保留，发布流程不创建或管理其目标目录；新因子应使用研究员自己的路径。

研究员工作区内的因子文件导出 `Alpha` 或 `create`；公共目录内的外部文件分别
导出 `Operation`、`Stats`、`Provider`，也可以导出统一的 `create` 工厂。动态
加载器根据规范化绝对路径生成内部模块名，而不是使用文件 basename，因此不同
目录下的同名文件可以在同一进程共存；加载异常保留原始 traceback，文件 SHA-256
记录在模块对象和 `--check-module` 输出中。

公共目录由发布流程初始化但不覆盖。研究员通过受审核的模块仓库贡献代码，部署后的
目录对普通用户只读；Provider 凭据、数据缓存、个人因子、输出和 checkpoint 均不
进入 `/usr/local/xqsim` 的框架 release。完整构建、发布和回滚命令见
[`tools/release/README.md`](../tools/release/README.md)。

`public_modules/deploy.json` 是公共文件边界：每项显式声明类型和源码，目标文件名
默认取源码 basename。`tools/release/deploy.py` 在写入前使用目标 `xqsim` ELF 对
所有 Python 模块执行 `--check-module`，随后在同一文件系统暂存并逐文件原子替换；
不在清单中的现有文件不会被删除。脚本既可单独更新公共模块，也可通过 `--artifact`
先发布一个已验证框架制品。每次部署把 Git commit、目标和 SHA-256 写入根目录的
`public-modules.json`。
