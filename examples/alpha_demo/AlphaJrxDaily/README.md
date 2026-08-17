# AlphaJrxDaily

`AlphaJrxDaily` 是 `AlphaJrx_MemberSkillSectorPower2InvVol60_v001` 的逐日
xqsim 适配。`AlphaTest` 和 `AlphaNew` 仅作为历史尝试保留，不是本实现的
语义来源。

## 会员持仓转换

`utils.py` 独立承载可复用的单边持仓聚合；因子再由多头、空头矩阵
计算暴露：

```text
单边 rank × ii 榜单 -> member × product 持仓
多头、空头持仓     -> direction、gross share
```

转换保留二维 `rank × ii` 输入，不再由因子构造 `ravel`、广播后的平铺数组。
这里的持仓仅覆盖交易所公布的 Top20 榜单；未上榜不等同于真实持仓为零。

## 横截面 mask

因子和 Operation 使用与数据轴等长的 bool 数组选择研究对象，不持久化
`[48, 98, ...]` 一类业务整数下标：

- `hot_data_mask[ii]`：有效品种的 48 号主力数据拷贝槽。
- `real_contract_mask[ii]`：排除 48/49 槽后的真实合约。
- `active_product_mask[pi]`：会员持仓矩阵中参与计算的品种。
- `sector_masks[product]`：活跃品种向量上的行业分组。
- `hot_contract_mask[ii]`：MapToHot 根据 `hot.ii[di]` 逐日生成的真实主力。

`pi_by_ii` 是合约到品种的标签映射，仅用于会员持仓聚合；它不是品种选择器。
`np.nonzero` 和并列排名的 `inverse` 只是算法内部坐标。

## 日期契约

`generate(di)` 生成目标日 `di` 的原始因子 v1，并且只读取动态数据
`[history_begin, di)`。每次调用只处理信息日 `di-1`；历史状态由 Simulator
根据 `warmup_days` 显式逐日推进，因子内部没有历史回放循环。

核心依赖为：

```text
exposure[di-2] + returns[di-1] -> daily_score[di-1]
last 504 daily_score             -> member_skill[di-1]
member_skill + exposure[di-1]    -> vote[di-1]
vote -> ffill(3) -> 品种48槽      -> v1[di]
```

## v1 与 v2

- v1：`generate(di)` 返回后的 `self.alpha`。
- v2：同日依次执行 sector neutralize、availability mask、Power2 × InvVol60、
  Holding5、ScaleToBooksize(2.0) 后，再映射到 `di` 当天真实主力合约的
  `self.alpha`。

Operation 始终处理 `di` 当天的 alpha；辅助数据窗口由 Operation 自己定义。
例如 InvVol60 使用 `[di-60, di)`，Holding5 使用当日与此前四个目标日子组合。
前五个 op 是权威新版 postprocessor；最后的 MapToHot 只负责 xqsim ii 布局适配。

## 运行

```bash
uv run xqsim -c examples/alpha_demo/AlphaJrxDaily/Config.AlphaJrxDaily.xml
```

本地期货缓存从 2016-01-04 开始；对 2018-01-02 的回测起点，配置使用
`backdays=488`、`warmup_days=487`，恰好从首个可用信息日开始推进。Warmup 只推进 Alpha 的 v1 状态，不执行 Operation、不保存输出、不计算 Stats。
