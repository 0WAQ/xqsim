from bsim.factor_base import *
import pandas as pd


class Factor(FactorBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.csv = self.cfg["csv"]
        self.data = np.array(pd.read_csv(self.csv))
        self.data_view = DataView(self.data, [self.meta.begin_di], "test")

    def before_generate(self, di):
        print(di, self.meta.date_index[di])

    def generate(self, di, ti, mi):
        self.alpha = self.data_view[di]

    def after_generate(self, di):
        pass
        # print(self.id, "after: ", di, self.meta.date_index[di])


def main():
    simulator_run(meta_dir="/cc", begin_date=20180101, end_date="20180131", interval="minute15", overwrite="auto", tttt="112")


if __name__ == '__main__':
    main()
