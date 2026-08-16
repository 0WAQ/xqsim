import pandas as pd

from xqsim.alpha_base import *
from xqsim.base.stats_base import StatsBase
import xqsim.utils as utils
from xqsim.base.utils import empty_alpha


class StatsPnl(object):
    def __init__(self):
        self.pnl = 0.0
        self.long_value = 0.0
        self.short_value = 0.0
        self.ret = 0.0
        self.trade_value = 0.0
        self.hold_value = 0.0
        self.long_num = 0
        self.short_num = 0

    def reset(self):
        self.pnl = 0.0
        self.long_value = 0.0
        self.short_value = 0.0
        self.ret = 0.0
        self.trade_value = 0.0
        self.hold_value = 0.0
        self.long_num = 0
        self.short_num = 0


class Stats(StatsBase):

    def __init__(self, *args):
        super().__init__(*args)

        self.ret = self.dr.get_data("k.returns")
        self.universe = self.dr.get_data("uv.all")

        self.last_value = empty_alpha(self.meta.ii_size, 0)

        self.stats_list = []
        self.stats = StatsPnl()

    def save_pnl(self):
        columns = ["Date", "Time", "RawPnl", "LongValue", "ShortValue", "RawReturn", "BookSize", "TradeValue", "HoldValue", "LongNum", "ShortNum", "IC"]
        round_dic = {column: 0 for column in columns}
        round_dic["Return"] = 6
        round_dic["IC"] = 6
        round_dic["Pnl"] = 0
        round_dic["RawReturn"] = 6

        raw_df = pd.DataFrame(self.stats_list, columns=columns)

        daily_df = utils.get_daily_df(raw_df)
        columns = daily_df.columns.tolist()
        columns.insert(5, "Return")
        columns.insert(2, "Pnl")

        daily_df = daily_df.reindex(columns=columns)
        daily_df["Pnl"] = daily_df["RawPnl"]
        daily_df["Return"] = daily_df["RawReturn"]

        # pnl_scale 里 df.loc[:, 'Date'] = [Timestamp...] 要求 Date 列是 datetime,
        # int64 列在新版 pandas 会 LossySetitemError, 这里先转换 (stats_general 有同样的问题)
        df_for_scale = daily_df.copy()
        df_for_scale["Date"] = pd.to_datetime(df_for_scale["Date"], format="%Y%m%d")
        result1, result2, result3 = utils.pnl_scale(df_for_scale, "Y", 2)

        if self.dump_pnl:
            raw_df.round(round_dic).to_csv(self.pnl_file + "_raw.csv", index=False, header=True)
            daily_df.round(round_dic).to_csv(self.pnl_file + "_daily.csv", index=False, header=True)
            result1.to_csv(self.pnl_file + "_year.csv", index=False, header=True)

        # print(result1)
        # print(result2)
        # print(result3)

    def calculate_di(self, di: int, alpha: np.ndarray):
        corr = utils.calc_cor(alpha, self.ret[di])
        value = utils.scale_to_booksize(alpha, self.booksize, 0)
        value = np.ma.array(value, mask=~self.universe[di]).filled(0)

        stats = self.stats
        stats.reset()
        hold_mask = (value * self.last_value > 0)

        stats.pnl = np.sum(self.last_value * np.nan_to_num(self.ret[di]))
        stats.long_value = np.sum(value[value > 0])
        stats.short_value = np.sum(value[value < 0])
        stats.ret = stats.pnl * 2.0 / self.booksize
        stats.hold_value = np.sum(np.minimum(np.abs(value), np.abs(self.last_value))[hold_mask])
        stats.trade_value = np.sum(np.abs(value - self.last_value))
        stats.short_num = value[value < 0].size
        stats.long_num = value[value > 0].size

        result = [self.meta.total_date_index[di],
                  self.meta.interval_time_index[0],
                  stats.pnl,
                  stats.long_value,
                  stats.short_value,
                  stats.ret,
                  self.booksize,
                  stats.trade_value,
                  stats.hold_value,
                  stats.long_num,
                  stats.short_num,
                  corr]
        self.stats_list.append(result)

        self.last_value = value.copy()
        if self.print_pnl:
            print("%d %20s %11.2f %10d  x %10d %10f %10d %10d %6d  x %5d" %
                  (self.meta.total_date_index[di], self.parent_module.id, stats.ret,
                   int(stats.long_value), int(stats.short_value), stats.ret,
                   int(stats.hold_value), int(stats.trade_value), int(stats.long_num), int(stats.short_num)))
        return value
