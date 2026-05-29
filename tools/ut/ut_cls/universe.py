from .unitest_base import *


class TestClass(UnittestBase):
    def test_all(self):
        """uv.all和instrument index一致"""
        for di in self.di_list:
            array = np.array(self.meta.instrument_index[di])
            count = np.sum(array[self.all[di]] == "")
            self.check_count_is_zero(count, di, "%s" % (array[self.all[di]] == ""))
