from xqsim.dbg import *
from sortedcollections import SortedDict, SortedList
import bisect


class Meta(object):
    def __init__(self):
        # 全局日历
        self.meta_dir = ""
        self.total_date_index: list[int] = []
        self.total_di_mapping = SortedDict()
        self.total_di_size = 0

        self.date_index: list[int] = []
        self.di_mapping = SortedDict()

        # 相对窗口
        self.offset_date_index = []
        self.offset_di_mapping = SortedDict()

        # 本次运行窗口
        self.begin_trading_day: int = 0
        self.end_trading_day: int = 0
        self.begin_di: int = 0
        self.end_di: int = 0
        self.di_size: int = 0
        self.di_list: list[int] = []

        self.today_date: int = 0
        self.today_di: int = 0

        # 回看天数
        self.back_days: int = 0
        # self.valid_begin_trading_day: int = 0
        # self.valid_begin_di: int = 0
        # self.valid_di_size: int = 0
        self.matrix_back_days: int = 0
        self.max_back_days: int = 0

        # 股票/合约
        self.instrument_index: dict[int, list] = {} # n_dates * n_instruments
        self.ii_mapping: dict[str, int] = {}    # code => di
        self.ii_size: int = 0
        self.last_instrument_index: list[str] = []
        self.all_instrument_index: list[str] = []   # ii => code
        self.ii_list = []

        # 分钟/tick 的时间轴
        self.time_index_dict = {}
        self.time_int_index_dict = {}
        self.time_mapping_dict = {}
        self.begin_ti = 0
        self.end_ti = 0

        self.interval = "day"
        self.interval_time_index = []
        self.interval_time_mapping = SortedDict()
        self.interval_ti_size = 1

        self.interval_date_time_index = []
        self.interval_date_time_int_index = []

        self.enum_index_dict = {}
        self.enum_mapping_dict = {}

        # 不同市场的日历
        self.calendar_dict: dict[str, SortedList] = {}  # market ==> trading_day

        # 断点日期
        self.checkpoint = False
        self.check_save_di: int | None = None
        self.check_load_di: int|None = None
        self.checkpoint_dir: str | None = None
        self.check_file_list = set()

        self.current_di: int | None = None

        # 全局参数
        self._global_cfg = {}

    def set_para(self, k, v):
        self._global_cfg[k] = v

    def get_para(self, k):
        return self._global_cfg[k]

    def get_para_default(self, k, d):
        return self._global_cfg.get(k, d)

    def get_ti(self, current_time, interval=None):
        if interval is not None:
            time_index = self.time_index_dict[interval]
        else:
            time_index = self.interval_time_index
        ti = bisect.bisect_right(time_index, current_time)
        if ti >= len(time_index):
            return -1
        return ti

    @property
    def global_cfg(self):
        return self._global_cfg


class Calendar(object):
    def __init__(self, meta: Meta):
        self.__calendar_dict = meta.calendar_dict

    def valid_date(self, date, exchange_market='SSE') -> int:
        date = int(date)
        trade_days = self.__calendar_dict[exchange_market]
        if not trade_days[0] <= date <= trade_days[-1]:     # type: ignore
            abort("Invalid date is provided as %s" % date)
        return date

    def get_next_trade_date(self, date, exchange_market='SSE'):
        # next(x for x in trade_days if x > date)
        trade_days = self.__calendar_dict[exchange_market]
        date = self.valid_date(date, exchange_market)
        i = bisect.bisect_right(trade_days, date)
        # i = np.searchsorted(trade_days, date, side="right")
        return trade_days[i]

    def get_previous_trade_date(self, date, exchange_market='SSE'):
        # next(x for x in trade_days[::-1] if x < date)
        trade_days = self.__calendar_dict[exchange_market]
        date = self.valid_date(date, exchange_market)
        i = bisect.bisect_left(trade_days, date) - 1
        # i = np.searchsorted(trade_days, date, side="left") - 1
        return trade_days[i]

    def get_trade_dates(self, start_date, end_date, exchange_market='SSE'):
        # [x for x in trade_days if start <= x <= end]
        start_date, end_date = self.valid_date(start_date, exchange_market), self.valid_date(end_date, exchange_market)
        trade_days = self.__calendar_dict[exchange_market]
        i_s = bisect.bisect_left(trade_days, start_date)
        i_e = bisect.bisect_right(trade_days, end_date)
        # i_s = np.searchsorted(trade_days, start_date, side="left")
        # i_e = np.searchsorted(trade_days, end_date, side="right")
        return trade_days[i_s:i_e]

    def is_trade_day(self, date, exchange_market='SSE'):
        trade_days = self.__calendar_dict[exchange_market]
        date = self.valid_date(date, exchange_market)
        return date in trade_days

    def get_n_previous_trade_dates(self, date, n, exchange_market='SSE'):
        # [x for x in trade_days if x < date][-n:]
        trade_days = self.__calendar_dict[exchange_market]
        date = self.valid_date(date, exchange_market)
        i = bisect.bisect_right(trade_days, date)
        # i = np.searchsorted(trade_days, date, side="right")
        return trade_days[i - n: i]

    def get_n_next_trade_dates(self, date, n, exchange_market='SSE'):
        # [x for x in trade_days if x > date][:n]
        trade_days = self.__calendar_dict[exchange_market]
        date = self.valid_date(date, exchange_market)
        i = bisect.bisect_right(trade_days, date)
        # i = np.searchsorted(trade_days, date, side="right")
        return trade_days[i: i + n]

    def get_latest_trade_date(self, date, exchange_market='SSE'):
        # next(x for x in trade_days[::-1] if x <= date)
        trade_days = self.__calendar_dict[exchange_market]
        date = self.valid_date(date, exchange_market)
        # import numpy as np
        # i = np.searchsorted(trade_days, date, side="left")
        # if trade_days[i] == date:
        #     return date
        # else:
        #     return trade_days[i - 1]

        i = bisect.bisect_right(trade_days, date) - 1
        return trade_days[i]

    def get_latest_trade_date_next(self, date, exchange_market='SSE'):
        # next(x for x in trade_days[::-1] if x <= date)
        trade_days = self.__calendar_dict[exchange_market]
        date = self.valid_date(date, exchange_market)
        i = bisect.bisect_left(trade_days, date)
        return trade_days[i]