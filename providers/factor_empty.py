from bsim.factor_base import *


class Factor(FactorBase):
    def __init__(self, *args):
        super().__init__(*args)
        log_info(id(self.meta))
        log_info(self.meta.begin_trading_day)
        log_info(self.dr.meta.begin_trading_day)

        tttt = self.cfg.get("tttt", 123456)
        print(tttt)
        print(self.cfg)

    def generate(self, di, ti, mi):
        # if not self.meta.get_para("real_time.start"):
        #     return
        print(di, ti, self.meta.total_date_index[di], self.meta.interval_time_index[ti])
        self.alpha.fill(1.0)

    def after_generate(self, di):
        print(self.id, "after: ", di, self.meta.date_index[di])


def main():
    simulator_run(meta_dir="/cc", begin_date=20180101, end_date="20180131", interval="minute15", overwrite="auto", tttt="112")


if __name__ == '__main__':
    main()
