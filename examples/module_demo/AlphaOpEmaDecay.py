from xqsim.api import *
import numpy as np

class AlphaOpEmaDecay(OperationBase):

    def __init__(self, *args):
        super(AlphaOpEmaDecay, self).__init__(*args)

        self.days: int = simcfg.get(self.cfg, 'days', 8)    # type: ignore
        self.ema = 2. / (self.days + 1.)
        numInsts = len(univbase.instruments)
        self.hist = np.zeros((numInsts,), dtype=np.float32)
        self.hist[:] = np.nan
        self.init = np.ndarray((numInsts,), dtype=np.bool_)
        self.init[:] = False

    def apply(self, didx, alpha):
        numInsts = len(univbase.instruments)

        valid = np.isfinite(alpha)
        # bool mask for stocks with valid alpha
        toapply = np.logical_and(valid, self.init)
        # bool mask for stocks that have valid alpha and have been initialized
        uninit = np.logical_not(self.init)
        # bool mask for stocks that have not been initialized
        toinit = np.logical_and(valid, uninit)
        # bool mask for stocks that have are to be initialized today

        self.hist[toapply] = self.ema * alpha[toapply] \
                             + (1. - self.ema) * self.hist[toapply]
        # apply the ema on the hist of "toapply" ones
        alpha[toapply] = self.hist[toapply]
        # assign alphas to alpha
        self.hist[toinit] = alpha[toinit]
        # initialize history for the "toinit" ones
        self.init[toinit] = True
        # and set init flag for the "toinit" ones

    def archive(self):
        # save hist and init into checkpoint
        # self.ar('hist')
        # self.ar('init')
        ...


def create(*args):
    return AlphaOpEmaDecay(*args)
