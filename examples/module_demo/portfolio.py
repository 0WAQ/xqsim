from qsim.api import *


class PortfolioSimple(alphabase.PortfolioBase):

    def __init__(self, *args):
        super(PortfolioSimple, self).__init__(*args)

    def generate_portfolio(self, didx, alpha_list):
        self.alpha = np.mean(np.array(alpha_list), axis=0)
        print(alpha_list)
        print(self.alpha)


def create(*args):
    return PortfolioSimple(*args)
