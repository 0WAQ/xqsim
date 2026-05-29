from .unitest_base import *


class TestClass(UnittestBase):
    def __init__(self, test_method, dr):
        super().__init__(test_method, dr)

    def __check_price(self, name, max_value, min_value=0.1):
        data = self.dr.get_data(name)
        for di in self.di_list:
            index = np.isnan(data[di]) | (data[di] < min_value) | (data[di] > max_value)
            index &= self.all[di] & ~self.st[di]
            self.check_index(name, di, index)

    def __check_limit_price(self, name, di, ignore_index):
        data = self.dr.get_data(name)
        upper = self.dr.get_data("k.upper")
        lower = self.dr.get_data("k.lower")
        tstatus = self.dr.get_data("k.tstatus")
        # for di in self.di_list:
        index = np.isnan(upper[di]) | np.isnan(lower[di]) | (np.round(data[di], 2) > upper[di]) | (np.round(data[di], 2) < lower[di])
        index &= self.all[di] & ~self.st[di] & (tstatus[di] != 10)
        index &= ~ignore_index
        self.check_index(name, di, index)

    def test_price(self):
        """K线量价数据范围"""
        self.__check_price("k.open", 1e4)
        self.__check_price("k.high", 1e4)
        self.__check_price("k.low", 1e4)
        self.__check_price("k.close", 1e4)
        self.__check_price("k.vwap", 1e4)
        self.__check_price("k.preclose", 1e4)
        self.__check_price("k.volume", 1e10, 0)
        self.__check_price("k.value", 1e15, 0)

    def test_limit(self):
        """K线涨跌停价格"""
        upper = self.dr.get_data("k.upper")
        lower = self.dr.get_data("k.lower")
        tstatus = self.dr.get_data("k.tstatus")
        self.wind_tstatus = self.dr.get_data("k.wind_tstatus")
        for di in self.di_list:
            data = (upper[di] - lower[di]) / (upper[di] + lower[di]) * 2
            data[upper[di] == 99999] = 0.2  # new stock
            data[(data > 0.87) & (data < 0.89)] = 0.2  # new stock
            data[(data > 0.39) & (data < 0.41)] /= 2  # 20%
            data[(data > 0.09) & (data < 0.11)] *= 2  # 5%
            data = np.abs(data - 0.2)
            index = data > (0.01 / upper[di] * 2)
            index &= self.all[di] & ~self.st[di] & (tstatus[di] != 10) & (self.wind_tstatus[di] != 1)

            self.check_index("limit price", di, index)

    def test_limit_null(self):
        """K线涨跌停的nan数量不超过200"""
        upper = self.dr.get_data("k.upper")
        for di in self.di_list:
            count = np.sum(upper[di] == 99999)
            count = int(count / 200)
            self.check_count_is_zero(count, di, "too many null for limit price")

    def test_adj_limit(self):
        """K线adj的正确性；价格处于涨跌停范围内"""
        self.wind_tstatus = self.dr.get_data("k.wind_tstatus")
        adj = self.dr.get_data("k.adj")
        close = self.dr.get_data("k.close")
        preclose = self.dr.get_data("k.preclose")
        for di in self.di_list:
            calc_adj = adj[di - 1] * close[di - 1] / preclose[di]
            index = self.diff_data(calc_adj, adj[di])
            index &= self.all[di] & ~self.st[di]

            ignore_index = index | (self.wind_tstatus[di] == 1) | (self.wind_tstatus[di - 1] == 0)
            self.__check_limit_price("k.open", di, ignore_index)
            self.__check_limit_price("k.high", di, ignore_index)
            self.__check_limit_price("k.low", di, ignore_index)
            self.__check_limit_price("k.close", di, ignore_index)
            self.__check_limit_price("k.vwap", di, ignore_index)
