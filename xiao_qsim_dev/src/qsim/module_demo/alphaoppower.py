from qsim.api import *
import pandas as pd
import numpy as np


class OperationDemo(alphabase.AlphaOperationBase):
    def __init__(self, *args):
        super(OperationDemo, self).__init__(*args)
        self.exp = simcfg.get(self.cfg, 'exp', 1.)

    def apply(self, didx, alpha):
        log_info("%s apply %s", self.id, didx)
        # print(self.parent_module.cfg)
        valid = np.isfinite(alpha)
        alpha[valid] = np.power(rank(alpha[valid]) - 0.5, self.exp)


def create(*args):
    return OperationDemo(*args)


def rank(x):
    return np.array(pd.Series(x).rank(na_option="keep", pct="true").tolist(), dtype=np.float32)
