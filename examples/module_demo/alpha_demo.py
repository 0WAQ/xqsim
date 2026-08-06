from xqsim.api import *


class AlphaDemo(AlphaBase):

    def __init__(self, *args):
        super(AlphaDemo, self).__init__(*args)

        self.n = simcfg.get(self.cfg, 'n', 218)
        self.cps = self.dr.getdata('k.close')
        self.volume = self.dr.getdata("k.volume")
        self.adj_close = self.dr.getdata("k.adj_close")
        self.data = self.dr.getdata("ret_20_1")
        self.num = 1
        self.f = "func1"

    def generate(self, didx):
        print("generate %s %s %s %s" % (didx, univbase.dates[didx], self.cps[didx - 1][218],
                                        self.volume[didx - 1][218]))
        f = eval(self.f)
        f(self.volume)

        self.num += 1
        print("num, price", self.num, self.adj_close[didx - 1][10])
        # did = didx - self.delay
        # numInsts = len(univbase.instruments)
        #
        # v = self.valid[didx, 0:numInsts]
        self.alpha[:] = self.adj_close[didx - 1]
        # self.alpha[v] = - (self.cps[did, v] / self.cps[did - self.n, v] - 1.)


def create(*args):
    return AlphaDemo(*args)
