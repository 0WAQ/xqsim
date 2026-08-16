"""Scale finite positions to a configured gross book size."""

import numpy as np

from xqsim.api import OperationBase, simcfg
from xqsim.common_module import log_info


class Operation(OperationBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.target_booksize = float(
            simcfg.get(self.cfg, "target_booksize", 2.0)
        )
        self.atol = float(simcfg.get(self.cfg, "atol", 1e-12))
        if not np.isfinite(self.target_booksize) or self.target_booksize <= 0.0:
            raise ValueError("target_booksize must be a finite positive number")
        log_info("ScaleToBooksize: target %.3f", self.target_booksize)

    def apply(self, di, alpha):
        values = np.nan_to_num(alpha)
        gross = np.abs(values).sum()
        alpha[:] = np.nan
        if not np.isfinite(gross) or gross <= self.atol:
            return
        result = values * (self.target_booksize / gross)
        nonzero = result != 0.0
        alpha[nonzero] = result[nonzero]
