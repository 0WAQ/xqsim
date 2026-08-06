import pandas as pd
import click
from xqsim.alpha_base import *
from xqsim.base.stats_base import StatsBase
import xqsim.utils as utils
from xqsim.base.utils import empty_alpha
from xqsim.data.data_repository import DataRepository as dr


class StatsPnl(object):
    def __init__(self):
        self.pnl = 0.0
        self.long_value = 0.0
        self.long_num = 0
        self.short_value = 0.0
        self.short_num = 0
        self.trade_value = 0.0
        self.hold_value = 0
        self.ret = 0.0

    def reset(self):
        self.pnl = 0.0
        self.long_value = 0.0
        self.long_num = 0
        self.short_value = 0.0
        self.short_num = 0
        self.trade_value = 0.0
        self.hold_value = 0
        self.ret = 0.0


class Stats(StatsBase):
    def __init__(self, *args):
        super().__init__(*args)

        suffix = "k"

        self.vwap = self.dr.get_data("%s.vwap" % suffix)
        self.close = self.dr.get_data("%s.close" % suffix)
        self.preclose = self.dr.get_data("%s.preclose" % suffix)
        self.value = self.dr.get_data("%s.value" % suffix)
        self.open = self.dr.get_data("%s.open" % suffix)
        self.high = self.dr.get_data("%s.high" % suffix)
        self.low = self.dr.get_data("%s.low" % suffix)
        self.ret = self.dr.get_data("%s.ret" % suffix)

        self.all = self.dr.get_data("uv.all")
        self.upper = self.dr.get_data("k.upper")
        self.lower = self.dr.get_data("k.lower")

        self.last_value = empty_alpha(self.meta.ii_size, 0)

        self.limit_flag = simcfg.get(self.cfg, "limit", False)
        if self.limit_flag:
            log_info("Stats limit is True")
        self.value_pct = simcfg.get(self.cfg, "value_pct", None)
        if self.value_pct is not None:
            self.value_pct = float(self.value_pct)
            log_info("Stats value pct is %s", self.value_pct)

        self.norm_mode: int = simcfg.get(self.cfg, "norm", -1)  # type: ignore
        if self.norm_mode != -1:
            log_info("Stats norm mode is %s", self.norm_mode)

        self.benchmark = simcfg.get(self.cfg, "benchmark", None)
        self.benchmark_ret = None
        if self.benchmark is not None:
            log_info("Stats benchmark is %s", self.benchmark)
            if self.benchmark != "all":
                self.benchmark_ret = self.dr.get_matrix_data("idx.k.%s.ret" % self.benchmark).data.flatten()
            else:
                self.benchmark_ret = self.dr.get_matrix_data("k.ret")
                self.benchmark_ret = np.nanmean(self.benchmark_ret.data, axis=1)

            self.top_n: int = simcfg.get(self.cfg, "top", -1)   # type: ignore
            if self.top_n >= 0:
                self.norm_mode = -1
                log_info("Stats top n is %s, and norm mode change to %s", self.top_n, self.norm_mode)

        self.long_only = False
        if "long_only" in self.cfg:
            log_info("Stats long only is %s", self.cfg["long_only"])
            self.long_only = self.cfg["long_only"]

        self.universe = None
        if "universe" in self.cfg:
            log_info("Stats universe is %s", self.cfg["universe"])
            self.universe = self.dr.get_data("uv.%s" % self.cfg["universe"])

        self.scale = 1
        if "scale" in self.cfg:
            log_info("Stats scale is %s", self.cfg["scale"])
            self.scale = self.cfg["scale"]

        self.stats_list = []
        self.stats = StatsPnl()

        self.trade_price: str = simcfg.get(self.cfg, "trade_price", "vwap")   # type: ignore
        log_info("Stats trade price is %s", self.trade_price)
        self.trade_price = self.__dict__[self.trade_price]

        self.print = simcfg.get(self.cfg, "print", False)

        self.expert = simcfg.get(self.cfg, "expert", False)

    def calculate(self, alpha_array: np.ndarray):
        log_info("Stats calculate start, id %s", self.id)
        alpha_array = alpha_array.view()
        self.last_value = empty_alpha(self.meta.ii_size, 0)
        self.stats_list = []
        for di in range(self.meta.begin_di, self.meta.end_di + 1):
            self.calculate_di(di, alpha_array[di - self.meta.begin_di])

        year_result, daily_df = self.save_pnl()
        log_info("Stats calculate finish, pnl path %s", self.pnl_file)
        return year_result, daily_df

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

        if self.benchmark is not None:
            daily_df["Pnl"] = daily_df["RawPnl"] - pd.DataFrame(self.benchmark_ret, index=daily_df.index, columns=["ret"])["ret"] * daily_df["LongValue"]
            daily_df["Return"] = daily_df["Pnl"] * 2.0 / daily_df["BookSize"]
        else:
            if self.long_only is False:
                daily_df["Pnl"] = daily_df["RawPnl"]
                daily_df["Return"] = daily_df["RawReturn"]
            else:
                daily_df["Pnl"] = daily_df["RawPnl"]
                daily_df["Return"] = daily_df["Pnl"] * 2.0 / daily_df["BookSize"]

        result1, result2, result3 = utils.pnl_scale(daily_df.copy(), "Y", 2)

        if self.pnl_file:
            raw_df.round(round_dic).to_csv(self.pnl_file + "_raw.csv", index=False, header=True)
            daily_df.round(round_dic).to_csv(self.pnl_file + "_daily.csv", index=False, header=True)
            result1.to_csv(self.pnl_file + "_year.csv", index=False, header=True)
        return result1, daily_df  # year, daily

    def calculate_di(self, di, alpha):
        corr = utils.calc_cor(alpha, self.ret[di])
        # print(corr)
        alpha = self.calculate_alpha(di, alpha)
        value = utils.scale_book_size(alpha, self.book_size, self.scale)
        if self.limit_flag:
            value = self.calculate_trade_limit(di, value, self.last_value, self.value_pct)
        self.calculate_general(self.stats, di, value, self.last_value, self.book_size)
        result = [self.meta.total_date_index[di],
                  self.meta.interval_time_index[0],
                  self.stats.pnl,
                  self.stats.long_value,
                  self.stats.short_value,
                  self.stats.ret,
                  self.book_size,
                  self.stats.trade_value,
                  self.stats.hold_value,
                  self.stats.long_num,
                  self.stats.short_num,
                  corr]
        self.stats_list.append(result)

        self.last_value = value.copy()
        if self.print:
            print("%d %20s %11.2f %10d  x %10d %10f %10d %10d %6d  x %5d" %
                  (univbase.dates[di], self.parent_module.id, self.stats.ret, int(self.stats.long_value), int(self.stats.short_value), self.stats.ret,
                   int(self.stats.hold_value), int(self.stats.trade_value), int(self.stats.long_num), int(self.stats.short_num)))
        return value

    def calculate_alpha(self, di, alpha):
        if self.norm_mode >= 0:
            alpha = utils.normalize(alpha, mode=self.norm_mode)
        new_alpha = np.nan_to_num(alpha)
        if self.universe is not None:
            new_alpha = np.ma.array(new_alpha, mask=~self.universe[di]).filled(0)
        if self.benchmark is not None:
            new_alpha[new_alpha < 0] = 0
            if self.top_n >= 0:
                n = np.sum(new_alpha > 0)
                if n > self.top_n:
                    n = self.top_n
                index = new_alpha.argsort()[::-1][0:n]
                new_alpha[:] = 0
                new_alpha[index] = 1
        return new_alpha

    def calculate_trade_limit(self, di, cur_value, last_value, value_pct=None):
        value_data = np.nan_to_num(self.value[di])
        change_value = cur_value - last_value
        index = np.where(value_data <= 0.0)
        cur_value[index] = last_value[index]

        if value_pct is not None:
            index = np.where(abs(change_value) > np.nan_to_num(self.value[di]) * value_pct)
            change_value[index] = np.nan_to_num(self.value[di][index]) * value_pct * np.sign(change_value[index])
            cur_value[index] = last_value[index] + change_value[index]

        index = np.where((np.nan_to_num(np.abs(self.low[di] - self.upper[di])) < 1e-5) & (change_value > 0))
        cur_value[index] = last_value[index]

        index = np.where((np.nan_to_num(np.abs(self.high[di] - self.lower[di])) < 1e-5) & (change_value < 0))
        cur_value[index] = last_value[index]

        cur_value = np.ma.array(cur_value, mask=~self.all[di]).filled(0)
        return cur_value

    def calculate_general(self, stats, di, cur_value, last_value, book_size):
        stats.reset()
        hold_value = np.minimum(np.abs(cur_value), np.abs(last_value)) * np.sign(cur_value)
        hold_value[cur_value * last_value < 0] = 0

        open_value = np.full(cur_value.shape, 0.0)
        index = np.where((cur_value * last_value > 0) & (np.abs(cur_value) >= np.abs(last_value)))
        open_value[index] = cur_value[index] - last_value[index]
        index = np.where(cur_value * last_value <= 0)
        open_value[index] = cur_value[index]

        close_value = np.full(cur_value.shape, 0.0)
        index = np.where((cur_value * last_value > 0) & (np.abs(cur_value) < np.abs(last_value)))
        close_value[index] = last_value[index] - cur_value[index]
        index = np.where(cur_value * last_value <= 0)
        close_value[index] = last_value[index]

        preclose_price = np.copy(self.preclose[di])
        preclose_price[preclose_price == 0] = NAN
        trade_price = np.copy(self.trade_price[di])
        trade_price[trade_price == 0] = NAN

        hold_rtn = np.nan_to_num(self.close[di] / preclose_price - 1.0, posinf=0.0, neginf=0.0)
        open_rtn = np.nan_to_num(self.close[di] / trade_price - 1.0, posinf=0.0, neginf=0.0)
        close_rtn = np.nan_to_num(trade_price / preclose_price - 1.0, posinf=0.0, neginf=0.0)

        stats.long_value = np.sum(cur_value[cur_value > 0])
        stats.long_num = cur_value[cur_value > 0].size
        stats.short_value = np.sum(cur_value[cur_value < 0])
        stats.short_num = cur_value[cur_value < 0].size
        stats.trade_value = np.sum(np.abs(cur_value - last_value))
        stats.hold_value = np.sum(np.abs(hold_value))

        if self.expert:
            stats.pnl = np.sum(hold_value * hold_rtn + open_value * open_rtn + close_value * close_rtn)
        else:
            stats.pnl = np.sum(last_value * hold_rtn)
        # if self.benchmark is not None:
        #     if self.benchmark != "all":
        #         stats.pnl -= self.benchmark_ret[di][ti][0] * stats.long_value
        #     else:
        #         mean_ret = self.benchmark_ret[di][ti][np.isfinite(self.benchmark_ret[di][ti])].mean()
        #         stats.pnl -= mean_ret * stats.long_value
        stats.ret = stats.pnl * 2.0 / book_size


@click.command()
@click.option('--meta_dir', required=True)
@click.option('--alpha_path', required=True)
@click.option('--pnl_dir', help="Pnl output directory", default="./pnl")
@click.option('--book_size', help="Total book size, default is 2e8", default="2e8", type=float)
@click.option('--limit', help="Use limit, default is false", default=False, type=bool)
@click.option('--value_pct', help="Value limit, valid when limit is true", default=None, type=float)
@click.option('--norm', help="example: -1, 0, 1", default=-1, type=int)
@click.option('--benchmark', help="example: sz50, hs300, zz500", default=None)
@click.option('--universe', help="example: sz50, hs300, zz500", default=None)
@click.option('--top', help="if top > 0, norm set to -1", default=-1, type=int)
def main(**kwargs):
    kwargs.update(dict(arg.split('=') for arg in sys.argv[1:] if "=" in arg))
    kwargs["id"] = "stats"
    kwargs["module_name"] = "stats_general"
    alpha_path = kwargs["alpha_path"]
    data_header = DataRepository.load_header_from_file(alpha_path)
    kwargs["begin_date"] = int(data_header.begin_trading_day)
    kwargs["end_date"] = int(data_header.end_trading_day)

    file_name = os.path.basename(alpha_path)
    elements = file_name.split(".")
    alpha_id = ".".join(elements[0:-3])
    kwargs["alpha_id"] = alpha_id

    ti_size = int(data_header.ti_size)

    dr = init_dr(**kwargs)

    if ti_size == len(dr.meta.time_index_dict["minute15"]):
        interval = "minute15"
    elif ti_size == len(dr.meta.time_index_dict["minute5"]):
        interval = "minute5"
    elif ti_size == len(dr.meta.time_index_dict["minute1"]):
        interval = "minute1"
    elif ti_size == 1:
        interval = "day"
    else:
        raise Exception()
    kwargs["interval"] = interval

    dr = init_dr(**kwargs)

    alpha_array = dr.load_data_from_file(alpha_path, dr.meta.begin_trading_day, dr.meta.end_trading_day)
    stats = Stats(dr, kwargs)
    print(stats.calculate(alpha_array))


if __name__ == '__main__':
    main()
