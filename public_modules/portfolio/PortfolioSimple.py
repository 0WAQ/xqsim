"""Combine multiple alpha vectors with an equal-weight average."""

import numpy as np

from xqsim.api import PortfolioBase


class PortfolioSimple(PortfolioBase):
    def generate_portfolio(self, di, alpha_list):
        self.alpha = np.mean(np.asarray(alpha_list), axis=0)


def create(*args):
    return PortfolioSimple(*args)
