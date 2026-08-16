# 因子研究与适配指南

本文面向使用 xqsim 研究、实现和验证因子的研究员。记录可复用的结论；单次
调试过程和未验证猜测不写成既定事实。

## 时间与输出契约

- `generate(di)` 计算目标日 `di` 的原始信号或目标持仓，一般只能使用
  `[history_begin, di)` 的动态数据。
- Simulator 保证 `di > 0` 且逐日连续调用。一次 `generate` 只推进一天，不能
  在函数内部回放历史。
- AlphaManager 在每次正式调用和 warmup 调用前重置 `self.alpha`；因子不需要
  在 `generate` 内重复调用 `reset_alpha()`。
- `generate` 返回后的 `self.alpha` 是 v1。Operation 按配置顺序对同一目标日
  的 alpha 原地执行；整条链结束后的值是 v2。
- 有状态因子通过 `warmup_days` 请求正式区间之前的逐日预热。warmup 只推进
  v1 状态，不执行 Operation、不保存输出、不计算 Stats。

研究时必须先写清楚：目标日、每项输入的可用时间、滚动窗口是否包含当日、
缺失值规则，以及输出究竟是评分还是目标持仓。

## 因子挖掘工作流

1. 从可证伪的经济或行为假设出发，先定义方向、持有期和预期失效条件；不要从
   回测曲线反推故事。
2. 审计每个字段的发布时间与可交易时点，先消除未来数据和幸存者偏差。
3. 先保存并检查 v1 的覆盖率、截面分布、IC、分组收益和换手，再引入
   Operation；原始信号与组合构造要分开评价。
4. 比较候选因子时固定 universe、Operation 链、成本和样本区间；一次只改变
   一个假设或参数。
5. 至少保留时间外样本，并检查不同年份、品种或行业、参数邻域和缺失值规则下
   的稳定性。报告负结果，避免只保留最佳试验。
6. 最终评估 v2 的换手、容量、交易成本和极端行情表现。保留配置、数据版本、
   运行命令和关键指标，使研究可复现。

## AlphaJrxDaily 当前结论

权威语义来自
`examples/alpha_demo/AlphaJrx_MemberSkillSectorPower2InvVol60_v001/`；
`AlphaTest` 和 `AlphaNew` 仅是历史适配尝试，不作为依据。逐日实现位于
`examples/alpha_demo/AlphaJrxDaily/`。

```text
rk.*[di-1]                         -> exposure[di-1]
exposure[di-2] + returns[di-1]    -> daily_score[di-1]
最近 504 个 daily_score           -> member_skill[di-1]
member_skill + exposure[di-1]     -> vote -> ffill(3) -> v1[di]
v1[di] + 当日 Operation 链        -> v2[di]
```

会员榜单转换已从因子公式中拆出到 `AlphaJrxDaily/utils.py`：通用函数把
单边 `rank × ii` 榜单按会员和品种聚合为 `member × product` 持仓；
因子的 `_aggregate_exposure` 再由多头、空头矩阵计算 `direction` 和
`gross_share`。数据只覆盖公开 Top20，未上榜记录在当前口径下按零处理，
但不能解释为会员真实持仓为零。

适配以数学语义为单位，不照搬 pandas 的 DataFrame、pivot 或 groupby 过程；逐日
热路径优先使用清晰的 NumPy 数组和必要的滚动状态。当前实现把每日能力样本统一为
`daily_score[sector, member]`，用一个 504 日滚动缓冲计算
`skill[sector, member]`，不再为每个行业维护字典状态。

横截面业务集合统一表示为与所属轴等长的 bool mask：
`hot_data_mask[ii]` 选择 48 号主力数据拷贝槽，`real_contract_mask[ii]` 选择
真实合约，`active_product_mask[pi]` 选择会员矩阵中的有效品种，
`sector_masks[product]` 表示行业分组；MapToHot 再由 `hot.ii[di]` 逐日生成
`hot_contract_mask[ii]`。因子与 Operation 不保存 `product_ii`、
`product_slots` 或 `target_ii` 等业务整数索引。类别标签与算法内部坐标不属于
该限制：`pi_by_ii` 仍负责合约到品种的聚合映射，`np.nonzero` 和并列排名
`inverse` 仅服务于 `bincount` 与排名计算。

2018 年权威金标验证中，
v1、v2 的有限值位置完全一致，相关系数均为 1.0，最大绝对误差分别为
`7.22e-16` 和 `6.94e-16`。

## 公共研究模块

研究员个人因子和配置保留在自己的工作目录；可复用实现经过审核后发布到
`/usr/local/xqsim/alpha`、`operation`、`stats`、`provider` 或 `config`。
四类 Python 模块分别导出 `Alpha`、`Operation`、`Stats`、`Provider`，也可以
导出 `create` 工厂。公共基类统一从 `xqsim.api` 导入。

配置优先使用 `${xqsim_alpha}`、`${xqsim_operation}`、`${xqsim_stats}`、
`${xqsim_provider}` 和 `${xqsim_config}`，不要硬编码具体框架版本目录。提交公共
模块时必须附最小配置、输入数据契约和验证结果；Provider 还要说明写入范围，且不得
包含凭据。共享目录不是协作工作区：贡献应经过 Git 审核后部署，不能直接在线修改。

每次研究记录应保存框架版本、配置、公共模块仓库 commit，以及运行时输出的模块
SHA-256。同名文件可以存在于不同分类目录，加载器会按绝对路径隔离模块身份。

## 研究记录要求

新增或修改因子时，至少记录：假设及经济含义、公式、数据字段与可用时点、
universe、缺失值和异常值处理、v1 与 Operation 链、参数、样本区间、对照基准，
以及可复现的验证命令和结果。假设、实验结果和已上线结论必须明确区分。
