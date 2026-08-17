# 对目标日 di 的子组合与此前 holding_days-1 个目标日子组合做固定分母平均。
from collections import deque

import numpy as np

from xqsim.api import *
from xqsim.common_module import log_info


class Operation(OperationBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.holding_days = int(simcfg.get(self.cfg, "holding_days", 5))  # type: ignore
        if self.holding_days <= 0:
            raise ValueError("holding_days must be positive")
        self._buffer = deque(maxlen=self.holding_days)
        log_info("AlphaJrxDaily HoldingAverage: days %d", self.holding_days)

    def apply(self, di, alpha):
        self._buffer.append(np.nan_to_num(alpha))
        result = np.sum(self._buffer, axis=0) / self.holding_days
        alpha[:] = np.nan
        nonzero = result != 0.0
        alpha[nonzero] = result[nonzero]
