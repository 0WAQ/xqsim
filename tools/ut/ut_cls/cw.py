from .unitest_base import *


class TestClass(UnittestBase):
    def __init__(self, test_method, dr):
        super().__init__(test_method, dr)

    def test_cw(self):
        """指数的权重求和与1.0的误差范围不超过1e-2"""
        data_dict = self.dr.get_data("cw.*")
        for name, data in data_dict.items():
            # log_info("test_cw: %s", name)
            for di in self.meta.di_list:
                total_weight = np.sum(data[di])
                if abs(total_weight - 1.0) > 1e-2:
                    self.check_count_is_zero(1, di, msg="%s total weight error: %s" % (name, total_weight))
