# 期货 demo 因子: 主力合约 N 日动量
#
# 数据要点:
#   - k.close 是逐合约原始价 (di×ii), 槽位复用: 同 ii 不同时段是不同合约
#   - hot.ii[di][ii] == ii 表示该槽当天是所属品种的主力合约 (可交易标志)
#   - uv.all[di][ii] 表示该槽当天有合约挂牌
#   - 动量在真实槽的合约自身价格序列上计算 (同一驻留段内是同一合约, 天然连续)
from xqsim.api import *

SLOTS_SIZE = 50


class Alpha(AlphaBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.n = simcfg.get(self.cfg, "n", 20)
        self.close = self.dr.getdata("k.close")
        self.hot_ii = self.dr.getdata("hot.ii")
        self.uv = self.dr.getdata("uv.all")
        self.ii_range = np.arange(self.meta.ii_size)

    def generate(self, didx):
        did = didx - self.delay
        is_hot = (self.hot_ii[did] == self.ii_range) & self.uv[did]
        mom = self.close[did] / self.close[did - self.n] - 1.0
        self.reset_alpha()
        self.alpha[is_hot] = mom[is_hot]


def create(*args):
    return Alpha(*args)
