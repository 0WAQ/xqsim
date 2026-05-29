from .unitest_base import *


class TestClass(UnittestBase):
    def __init__(self, test_method, dr):
        super().__init__(test_method, dr)

    def __check_price(self, name, max_value, min_value=0.1):
        data = self.dr.get_data(name)
        for di in self.di_list:
            index = np.isnan(data[di]) | (data[di] < min_value) | (data[di] > max_value)
            self.check_index(name, di, index)

    def test_price(self):
        """citis K线量价数据范围"""
        self.__check_price("ciidx.level1.open", 1e6)
        self.__check_price("ciidx.level1.high", 1e6)
        self.__check_price("ciidx.level1.low", 1e6)
        self.__check_price("ciidx.level1.close", 1e6)
        self.__check_price("ciidx.level1.vwap", 1e6)
        self.__check_price("ciidx.level1.preclose", 1e6)
        self.__check_price("ciidx.level1.volume", 1e15, 0)
        self.__check_price("ciidx.level1.value", 1e20, 0)
