from .unitest_base import *


class TestClass(UnittestBase):

    def test_all_zero(self):
        amount = self.dr.get_data("b1.amount")
        for di in self.meta.di_list:
            sum_amount_all = np.sum(np.nan_to_num(amount[di]), axis=1)
            index = sum_amount_all < 1e8
            index[-3:] = False  # 14:57 -- 15:00
            self.check_index("b1.amount", di, index, self.meta.time_index_dict["minute1_239"])
            # if np.sum(index) > 0:
            #     print("date %s, code %s" % (self.meta.date_index[di], np.array(self.meta.time_index_dict["minute1_239"])[np.where(index)]))

    def test_volume(self):
        k_volume = self.dr.get_data("k.volume")
        volume = self.dr.get_data("b1.volume")
        for di in self.meta.di_list:
            sum_volume = np.sum(np.nan_to_num(volume[di]), axis=0)
            k_volume_di = k_volume[di]
            index = self.diff_data(k_volume_di, sum_volume, 0.2)
            index |= k_volume_di > sum_volume
            index &= (self.all[di] & (self.wind_tstatus[di] != 0) & (self.wind_tstatus[di] != 1) & ~self.st[di])
            # print(sum_volume[4408])
            # print(k_volume_di[4408])
            if np.sum(index) > 0:
                print(k_volume_di[index])
                print(sum_volume[index])
            self.check_index("b1.volume", di, index)

    def test_preclose(self):
        name = "preclose"
        k_data = self.dr.get_data("k.%s" % name)
        data = self.dr.get_data("b1.%s" % name)
        for di in self.meta.di_list:
            index = self.diff_data(k_data[di], data[di][0])
            index &= self.all[di] & (self.wind_tstatus[di] != 0)
            self.check_index("b1.%s" % name, di, index)

    def __test_price(self, name, start=0):
        m_data = self.dr.get_data("b1.%s" % name)
        m_volume = self.dr.get_data("b1.volume")
        k_high = self.dr.get_data("k.high")
        k_low = self.dr.get_data("k.low")
        for di in self.meta.di_list:
            data = m_data[di].copy()
            data[m_volume[di] == 0] = nan
            data[m_volume[di] == nan] = nan
            index = np.nanmax(data[start:], axis=0) > k_high[di]
            index |= np.nanmin(data[start:], axis=0) < k_low[di]

            index &= self.all[di] & (self.wind_tstatus[di] != 0)
            self.check_index("b1.%s" % name, di, index)

    def test_close(self):
        self.__test_price("close")

    def test_open(self):
        self.__test_price("open", 1)

    def __test_all_nan(self, name1, name2):
        m_data1 = self.dr.get_data("b1.%s" % name1)
        m_data2 = self.dr.get_data("b1.%s" % name2)
        for di in self.meta.di_list:
            sum_data = np.sum(np.nan_to_num(m_data1[di]), axis=0) + np.sum(np.nan_to_num(m_data2[di]), axis=0)
            index = sum_data == 0.0
            index &= self.all[di] & (self.wind_tstatus[di] != 0) & (self.wind_tstatus[di] != 1) & ~self.st[di]
            self.check_index("b1.%s.nan" % name1 + name2, di, index)

    def test_valid(self):
        self.__test_all_nan("tot_ask_close", "tot_bid_close")
        self.__test_all_nan("avg_ask_close", "avg_bid_close")
