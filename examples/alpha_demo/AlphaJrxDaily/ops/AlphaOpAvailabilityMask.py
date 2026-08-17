# 对目标日 di 的 alpha 应用收益可用性约束。
# 权威新版 ReturnAvailabilityMask(lag=1): 默认检查 di-1 的品种收益。
import numpy as np

from xqsim.api import *
from xqsim.common_module import log_info


class Operation(OperationBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.lag = int(simcfg.get(self.cfg, "lag", 1))  # type: ignore
        if self.lag < 1:
            raise ValueError("availability lag must be at least 1")
        self.ret = self.dr.get_data("k.returns")
        log_info("AlphaJrxDaily AvailabilityMask: lag %d", self.lag)

    def apply(self, di, alpha):
        source_di = di - self.lag
        valid_alpha = np.isfinite(alpha)
        if source_di < self.ret.offset_di:
            alpha[valid_alpha] = np.nan
            return
        available = np.isfinite(self.ret[source_di])
        alpha[valid_alpha & ~available] = np.nan
