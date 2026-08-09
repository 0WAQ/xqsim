# 期货 demo 因子: 仓单库存变化 (pi 维数据用法示例)
#
# 数据要点:
#   - wh.deliverable 是 pi 维数据, 原生 di×80 布局 (不是 di×ii!),
#     view.data[:, pi] 即该品种的可交割库存
#   - 因子值在品种维计算, 再映射回该品种的主力合约槽 (alpha 必须是 di×ii)
#   - 仓单上升 -> 供给压力 -> 做空主力, 故取负号
from xqsim.api import *

SLOTS_SIZE = 50


class Alpha(AlphaBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.n = simcfg.get(self.cfg, "n", 20)
        self.deliverable = self.dr.getdata("wh.deliverable")   # di×80
        self.hot_ii = self.dr.getdata("hot.ii")                # di×ii
        self.uv = self.dr.getdata("uv.all")
        self.ii_range = np.arange(self.meta.ii_size)
        self.pi_of_ii = self.ii_range // SLOTS_SIZE

    def generate(self, didx):
        did = didx - self.delay
        # 品种维: N 日仓单变化率 (di×80 上直接算)
        inv_chg = self.deliverable[did] / self.deliverable[did - self.n] - 1.0
        # 映射回主力合约槽
        is_hot = (self.hot_ii[did] == self.ii_range) & self.uv[did]
        self.reset_alpha()
        self.alpha[is_hot] = -inv_chg[self.pi_of_ii[is_hot]]


def create(*args):
    return Alpha(*args)
