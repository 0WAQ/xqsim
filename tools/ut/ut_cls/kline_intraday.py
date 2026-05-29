from .unitest_base import *


class TestClass(UnittestBase):
    def __init__(self, test_method, dr):
        super().__init__(test_method, dr)
        self.interval = "minute1"
        self.abbr = "km1"

    def test_nan(self):
        """日K线close不为nan时，1分钟K线第一根close也不为0"""
        np.set_printoptions(threshold=np.inf)
        close = self.dr.get_data("%s.close" % self.abbr)
        k_close = self.dr.get_data("k.close")
        output_str = ""
        for di in self.meta.di_list:
            index = np.isnan(close[di][0]) & ~np.isnan(k_close[di])
            index &= self.all[di] & (self.wind_tstatus[di] != 0) & self.all[self.meta.end_di]
            if np.sum(index) > 0:
                output_str += ('"%s":["%s"],\n' % (self.meta.date_index[di],
                                                   '","'.join(np.array(self.meta.instrument_index[di])[np.where(index)].tolist())
                                                   ))
                self.check_index("test_nan", di, index)
        output_str = "{\n%s\n}" % output_str[:-2]
        # with open("miss_info.json", "w") as writer:
        #     writer.write(output_str)

    def test_all_zero(self):
        """集合竞价外任一分钟全市场成交额不小于1e8"""
        amount = self.dr.get_data("%s.value" % self.abbr)
        for di in self.meta.di_list:
            if self.meta.date_index[di] == 20160104 or self.meta.date_index[di] == 20160107:
                continue
            sum_amount_all = np.sum(np.nan_to_num(amount[di]), axis=1)
            index = sum_amount_all < 1e8
            index[-3:] = False  # 14:57 -- 15:00
            if np.sum(index) > 0:
                print("date %s, code %s" % (self.meta.date_index[di], np.array(self.meta.time_index_dict[self.interval])[np.where(index)]))
                self.check_index("test_all_zero", di, index)

    def test_volume(self):
        """1分钟线volume求和与日线volume相同"""
        k_volume = self.dr.get_data("k.volume")
        volume = self.dr.get_data("%s.volume" % self.abbr)
        for di in self.meta.di_list:
            sum_volume = np.sum(volume[di], axis=0)
            index = self.diff_data(k_volume[di], sum_volume)
            index &= self.all[di] & (self.wind_tstatus[di] != 0)
            self.check_index("%s.volume" % self.abbr, di, index)

    def test_preclose(self):
        """1分钟线第一根preclose和与日线preclose相同"""
        name = "preclose"
        k_data = self.dr.get_data("k.%s" % name)
        data = self.dr.get_data("%s.%s" % (self.abbr, name))
        for di in self.meta.di_list:
            index = self.diff_data(k_data[di], data[di][0])
            index &= self.all[di] & (self.wind_tstatus[di] != 0)
            self.check_index("%s.%s" % (self.abbr, name), di, index)

    def test_high_low(self):
        """1分钟线任一根的high和low应该在日线的high和low范围内"""
        m_high = self.dr.get_data("%s.high" % self.abbr)
        m_low = self.dr.get_data("%s.low" % self.abbr)
        m_volume = self.dr.get_data("%s.volume" % self.abbr)
        k_high = self.dr.get_data("k.high")
        k_low = self.dr.get_data("k.low")
        for di in self.meta.di_list:
            high = m_high[di].copy()
            high[m_volume[di] == 0] = nan
            high = np.nanmax(high, axis=0)

            low = m_low[di].copy()
            low[m_volume[di] == 0] = nan
            low = np.nanmin(low, axis=0)

            index = self.diff_data(k_high[di], high)
            index |= self.diff_data(k_low[di], low)
            index &= self.all[di] & (self.wind_tstatus[di] != 0)
            self.check_index("%s.high.low" % self.abbr, di, index)

    def __test_price(self, name):
        m_data = self.dr.get_data("%s.%s" % (self.abbr, name))
        m_volume = self.dr.get_data("%s.volume" % self.abbr)
        k_high = self.dr.get_data("k.high")
        k_low = self.dr.get_data("k.low")
        for di in self.meta.di_list:
            data = m_data[di].copy()
            data[m_volume[di] == 0] = nan
            data_high = np.nanmax(data, axis=0)
            data_low = np.nanmin(data, axis=0)

            index = (data_high > k_high[di]) | (data_low < k_low[di])
            index &= self.all[di] & (self.wind_tstatus[di] != 0)
            self.check_index("%s.%s" % (self.abbr, name), di, index)

    def test_price_between_high_low(self):
        """1分钟线任一根的open和close在日线的high和low范围内"""
        self.__test_price("open")
        self.__test_price("close")
