from qsim.api import *

class AlphaDemo(alphabase.AlphaBase):

    def __init__(self, *args):
        super(AlphaDemo, self).__init__(*args)

        self.n = simcfg.get(self.cfg, 'n', 5)
        self.cps = self.dr.getdata(simcfg.get(self.cfg, 'data', "k.close"))
        self.data = self.dr.getdata("alpha5dr_1")
#        self.cps = self.dr.getdata('k.adj_close')

    def generate(self, didx):
        did = didx - self.delay
        numInsts = len(univbase.instruments)

        v = self.valid[didx, 0:numInsts]
        self.alpha[v] = self.cps[did, v] / self.cps[did - self.n, v] - 1.

def create(*args):
    return AlphaDemo(*args)
