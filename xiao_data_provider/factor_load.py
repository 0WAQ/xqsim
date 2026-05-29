from bsim.factor_base import *


class Factor(FactorBase):
    def __init__(self, *args):
        super().__init__(*args)
        log_info(id(self.meta))
        log_info(self.meta.begin_trading_day)
        log_info(self.dr.meta.begin_trading_day)
        # log_info(self.meta.date_index)
        data1 = self.dr.get_data("br.exposure")
        data2 = self.dr.get_data("br.dly_factor_return")

    def generate(self, di, ti, mi):
        return {"zzzz": self.alpha, "yyyy": self.alpha}

    def after_generate(self, di):
        print(self.id, "after: ", di, self.meta.date_index[di])


def main():
    simulator_run(meta_dir="/cc", begin_date=20201208, end_date="20201231", interval="minute15", overwrite="auto", tttt="112", cache_list=["./cc_update"])


if __name__ == '__main__':
    main()
