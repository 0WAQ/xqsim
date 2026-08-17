from xqsim.api import *
import pandas as pd
import numpy as np


class OperationDemo(OperationBase):
    def __init__(self, *args):
        super(OperationDemo, self).__init__(*args)
        self.exp: int = simcfg.get(self.cfg, 'exp', 1.) # type: ignore

    def apply(self, didx, alpha):
        print(f"{self.id} apply {didx}")
        # print(self.parent_module.cfg)
        valid = np.isfinite(alpha)
        alpha[valid] = np.power(rank(alpha[valid]) - 0.5, self.exp)


def create(*args):
    return OperationDemo(*args)


def rank(x):
    return np.array(pd.Series(x).rank(na_option="keep", pct=True).tolist(), dtype=np.float32)
