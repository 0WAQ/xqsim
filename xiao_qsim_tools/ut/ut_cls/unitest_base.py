import unittest
from qsim.alpha_base import *


class UnittestBase(unittest.TestCase):
    def __init__(self, test_method, dr):
        super().__init__(test_method)
        self.dr: DataRepository = dr
        self.meta: Meta = self.dr.meta
        self.di_list = self.meta.di_list
        self.all = self.dr.get_data("uv.all")
        self.st = self.dr.get_data("uv.st")
        self.wind_tstatus = self.dr.get_data("k.wind_tstatus")
        self.tstatus = self.dr.get_data("k.tstatus")
        self.ignore_di_ii = {}
        self.ignore_ii = []

    def check_ignore(self, di, index):
        index[self.ignore_ii] = False

    def check_count_is_zero(self, count, di, msg):
        content = "Invalid count %s > 0, date %s(%s)" % (count, self.meta.date_index[di], di)
        content += ", " + msg
        self.assertTrue(count == 0, msg=content)

    def check_index(self, name, di, index, mapping_index=None):
        if mapping_index is None:
            mapping_index = self.meta.instrument_index[di]
        self.check_ignore(di, index)
        self.check_count_is_zero(np.sum(index), di, "name %s, index %s, code %s" % (name, np.where(index), np.array(mapping_index)[np.where(index)]))

    def check_nan(self, abbr, limit, ignore_list=None):
        if ignore_list is None:
            ignore_list = list()
        name_list = self.dr.get_name_list()
        for name in name_list:
            if name == abbr and name not in ignore_list:
                data = self.dr.get_data(name)
                log_info("check nan %s", name)
                for di in self.meta.di_list:
                    index = np.isnan(data[di])
                    index &= self.all[di] & ((self.wind_tstatus[di] != 0) | np.isnan(self.wind_tstatus[di]))
                    count = np.sum(index)
                    if limit > 1:
                        self.check_count_is_zero(int(count / limit), di, "%s nan count is %s" % (name, count))
                    else:
                        self.check_index(name, di, index)

    def diff_data(self, data1, data2, delta=1e-6):
        index1 = (np.isfinite(data1)) & (~np.isfinite(data2))
        index2 = (np.isfinite(data2)) & (~np.isfinite(data1))
        index3 = (np.isfinite(data2)) & (np.isfinite(data1)) & (np.abs((data1 - data2) / (data1 + data2)) > delta)
        return index1 | index2 | index3
