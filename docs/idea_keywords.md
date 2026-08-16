# 脑海中突然浮现的关键词

这里是研究灵感的低成本入口。关键词不必完整，但要写明日期、上下文和下一步
问题，确保未来的自己或其他研究员能恢复当时的想法。未经验证的内容不能当作
框架事实或研究结论。

想法成熟后，将可复用结论整理到 `architecture.md` 或 `factor_research.md`，
并把原条目标记为“已整理”；不要直接删除历史线索。

## Inbox

### 2026-08-15 · 逐日因子语义

- 目标日持仓：`generate(di)` 最终得到 `di` 日的 `self.alpha`。
- 信息边界：动态输入通常只能来自 `[history_begin, di)`。
- 两层因子值：generate 后是 v1，Operation 链后是 v2。
- Operation 是对目标日 alpha 的变换，辅助数据时点由具体 Operation 定义。
- 语义改写：移植数学关系和状态转移，不照搬 pandas 中间表。
- 显式 warmup：历史状态由 Simulator 逐日推进，因子内部不隐藏回放。

下一步：把这些约束抽象成通用因子模板和可自动检查的无未来数据测试。

### 2026-08-15 · 研究员友好的数据访问层

状态：已记录，当前暂停；先完成 `AlphaJrxDaily` 的简化适配。

- 现状：`DataView` 很适合引擎处理 offset、back_days 和 segment reload。
- 痛点：研究员仍需理解全局 `di`、局部 `.data`、二维/三维 shape、字符串字段名
  和动态返回类型，探索代码与生产因子之间迁移成本较高。
- 设计修正：问题核心不是缺少研究抽象，而是 DataView 没有适配 NumPy 协议。
- 已否定：FactorContext、field/many 包装层和额外研究术语；它们增加研究员不需要
  的编程概念，偏离数学研究习惯。
- 当前方向：保留全局 `di` 和 segment 能力，让 DataView 实现 NumPy array/ufunc
  协议，支持 `np.nanmean(view)`、`np.isfinite(view)`、`view * 2` 等直接运算。
- 目标：NumPy 运算结果返回普通 ndarray，不让派生结果继续携带 offset 语义。

下一步：用现有 DataView 复现研究员常用 NumPy 操作的失败案例，只补最小协议和
兼容性测试；暂不增加新的研究 API。
