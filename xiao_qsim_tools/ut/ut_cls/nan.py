from .unitest_base import *


class TestClass(UnittestBase):
    def __init__(self, test_method, dr):
        super().__init__(test_method, dr)

    def test_industry(self):
        # self.ignore_ii = [171]
        # self.check_nan("ind.", 50)
        pass

    def test_mf(self):
        """mf.buy_value_exlarge_order的nan数量不超过50"""
        self.check_nan("mf.buy_value_exlarge_order", 50)

    def test_dv(self):
        """dv.s_dq_mv的nan数量不超过50"""
        self.check_nan("dv.s_dq_mv", 50)

    def test_barra(self):
        """barra.price的nan数量不超过10"""
        self.check_nan("barra.price", 10)

    def test_shsc(self):
        """shsc.S_QUANTITY的nan数量不超过1"""
        self.check_nan("shsc.S_QUANTITY", 1)
