from bsim.factor_base import *


class Factor(FactorBase):
    def __init__(self, *args):
        super().__init__(*args)
        log_info(id(self.meta))
        log_info(self.meta.begin_trading_day)
        log_info(self.dr.meta.begin_trading_day)
        # log_info(self.meta.date_index)
        self.close_m15 = self.dr.get_data("km15.close")
        self.open_m15 = self.dr.get_data("km15.open")
        self.ret_m15 = self.dr.get_data("km15.ret")
        self.hs300 = self.dr.get_data("uv.hs300")

        tttt = self.cfg.get("tttt", 123456)
        print(tttt)
        print(self.cfg)

    def generate(self, di, ti, mi):
        print(di, ti, self.meta.total_date_index[di], self.meta.interval_time_index[ti], self.close_m15[di][ti][10])
        self.alpha = np.abs(self.close_m15[di][ti])
        self.alpha = np.ma.array(self.alpha, mask=~self.hs300[di]).filled(nan)
        # print(np.sum(np.isfinite(self.alpha)), np.sum(self.hs300[di]))
        # index = ~np.isfinite(self.alpha) & self.hs300[di]
        # print(index, np.where(index))
        return {"zzzz": self.alpha, "yyyy": self.alpha}

    def after_generate(self, di):
        print(self.id, "after: ", di, self.meta.date_index[di])


def main():
    simulator_run(meta_dir="/cc", begin_date=20180101, end_date="20180131", interval="minute15", overwrite="auto", tttt="112")


if __name__ == '__main__':
    main()
