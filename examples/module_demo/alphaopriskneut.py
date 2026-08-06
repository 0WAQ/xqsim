from xqsim.api import *
import pandas as pd
import numpy as np

# sys.path.append(".")
from oper_utils import resid

class OperationDemo(OperationBase):
    def __init__(self, *args):
        super(OperationDemo, self).__init__(*args)
        self.risk = self.dr.getdata(simcfg.get(self.cfg, 'risk', 'k.close'))
        self.mode = simcfg.get(self.cfg, 'mode', 0)
        self.delay = simcfg.get(self.cfg, 'delay', 1)

    def apply(self, didx, alpha):
#        log_info("%s apply %s", self.id, didx)
        # print(self.parent_module.cfg)
        vailid = np.isfinite(alpha)
        numInsts = len(univbase.instruments)
        rsk = self.risk[didx-self.delay, 0:numInsts]
        if self.mode == 1:
            rsk = rank(rsk)
        alpha[vailid] = resid(rsk, alpha)[vailid]


def create(*args):
    return OperationDemo(*args)

def rank(x):
    return np.array(pd.Series(x).rank(na_option="keep", pct=True).tolist(), dtype=np.float32)