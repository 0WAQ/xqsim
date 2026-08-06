# QSim 架构文档

## 1. 一个因子是怎么跑的

回测区间 242 个交易日，标的池 6000 只股票。框架逐日循环：

```python
for di in [begin_di .. end_di]:
    # Step 1: 因子计算，产出 v1
    alpha.generate(di)

    # Step 2: Operator 链式变换，v1 → v2
    for op in operators:
        op.generate(di, alpha)

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
        self.alpha[:] = self.close[di] / self.close[di - 20] - 1  # 20日动量
```

每天调一次，输出一个截面向量——这就是 **v1**。

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
    def generate(self, di, alpha):
        alpha[:] = self.decay * self.last_alpha + (1 - self.decay) * alpha
        self.last_alpha = alpha.copy()
```

Operator 有状态（比如衰减要记住昨天的值），所以必须在逐日循环内执行——这就是为什么 **v1→v2 属于回测框架的一部分**。

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
        op.generate(di, alpha)
    stats.calculate_di(di, alpha)

# 分钟频
for di in [begin_di .. end_di]:
    for ti in [begin_ti .. end_ti]:
        alpha.generate(di, ti)
        for op in operators:
            op.generate(di, ti, alpha)
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
        <Module id="Stats" path="${qsim_modules}/stats_general.py" handler="StatsRegistry"/>
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
