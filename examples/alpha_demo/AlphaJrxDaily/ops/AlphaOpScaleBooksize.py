# 权威新版 ScaleToBooksize(2.0): 将 Holding5 后的 v2 gross 恢复到目标值。
import numpy as np

from xqsim.api import *
from xqsim.common_module import log_info


class Operation(OperationBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.target_booksize = float(
            simcfg.get(self.cfg, "target_booksize", 2.0)
        )  # type: ignore
        self.atol = float(simcfg.get(self.cfg, "atol", 1e-12))  # type: ignore
        if not np.isfinite(self.target_booksize) or self.target_booksize <= 0.0:
            raise ValueError("target_booksize must be a finite positive number")
        log_info(
            "AlphaJrxDaily ScaleToBooksize: target %.3f",
            self.target_booksize,
        )

    def apply(self, di, alpha):
        values = np.nan_to_num(alpha)
        gross = np.abs(values).sum()
        alpha[:] = np.nan
        if not np.isfinite(gross) or gross <= self.atol:
            return
        result = values * (self.target_booksize / gross)
        nonzero = result != 0.0
        alpha[nonzero] = result[nonzero]
