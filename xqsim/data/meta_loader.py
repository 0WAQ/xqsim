import os
import datetime
import itertools
from sortedcollections import SortedDict, SortedList
from xqsim import common_utils
from xqsim.dbg import *
from xqsim.data.meta import Meta

DAY_TIME = "15:00:00"
DAY_TIME_INT = 150000


class MetaLoader(object):
    def __init__(self, config_dict: dict):
        self.__config_dict: dict = config_dict
        self.__meta = Meta()

    def run(self):

        self.__meta.meta_dir = common_utils.realpath(self.__config_dict["meta_dir"])
        log_info("Load index from path %s", self.__meta.meta_dir)

        self.__load_static_size(self.__meta.meta_dir)
        self.__load_date_index(self.__meta.meta_dir)
        self.__check_date(self.__config_dict)
        self.__load_time_index(self.__meta.meta_dir)
        self.__check_time(self.__config_dict)
        self.__load_enum(self.__meta.meta_dir)
        self.__load_calendar(self.__meta.meta_dir)
        log_info("Load meta finish")
        return self.__meta

    def __load_static_size(self, meta_dir: str):
        """获取标的数量 (ii size)"""
        file_path = os.path.join(meta_dir, "meta", "index", "StaticIndexSize.csv")
        index_category = self.__config_dict.get("index_category", "ASHARE")
        lines = common_utils.load_csv_file(file_path)
        for line in lines:
            if line[2] == index_category:
                self.__meta.ii_size = int(line[1])
        if self.__meta.ii_size == 0:
            abort("Load ii size failed, category %s", index_category)
        log_info("Load ii size %s, category %s", self.__meta.ii_size, index_category)

    def __load_date_index(self, meta_dir: str):
        file_path = os.path.join(meta_dir, "meta", "index", "DateIndex.csv")
        lines = common_utils.load_csv_file(file_path)
        for i in range(len(lines)):
            line = lines[i]
            di = int(line[0])   # 行号就是 di
            if di != i:
                abort("Date index file error, di(%s) != i(%s)", di, i)
            trading_day = int(line[1])
            self.__meta.total_date_index.append(trading_day)
            self.__meta.total_di_mapping[trading_day] = di  # yyyymmdd to di
        self.__meta.total_di_size = len(self.__meta.total_date_index)
        self.__meta.date_index = self.__meta.total_date_index
        self.__meta.di_mapping = self.__meta.total_di_mapping
        log_info("Load di size %s", self.__meta.total_di_size)

    def __get_di(self, date: str, cmp_func) -> int:
        date_str = str(date)
        if date_str.startswith("TODAY"):
            diff_day = 0
            now = datetime.datetime.now()
            today_date = int(now.strftime("%Y%m%d"))

            # 下午 4 点后算第二天
            if today_date in self.__meta.total_date_index and now.hour >= 16:
                diff_day += 1

            if date_str.startswith("TODAY-"):
                diff_day -= int(date_str[len("TODAY-"):])

            di = cmp_func(self.__meta.total_date_index, today_date)
            if today_date > self.__meta.total_date_index[di] and cmp_func == common_utils.equal_or_first_less:
                # weekend for end date
                di += 1
            di = di + diff_day
            if di > self.__meta.total_di_size:
                abort("Date invalid, date %s, di(%s) > meta.total_di_size(%s)", date_str, di, self.__meta.total_di_size)
            return di
        else:
            abort_if(len(date_str) != 8, "date error: %s", date_str)
            return cmp_func(self.__meta.total_date_index, int(date_str))

    def __check_date(self, config_dict: dict):
        if config_dict.get("total", False):
            begin_date = config_dict.get("begin_date", None)
            end_date = config_dict.get("end_date", None)
        else:
            begin_date = config_dict["begin_date"]
            end_date = config_dict["end_date"]
        back_days = config_dict.get("back_days", 0)

        if config_dict.get("build", False):
            if begin_date is None or end_date is None:
                log_warn("No begin data or end date")
                begin_date = self.__meta.total_date_index[0]
                end_date = self.__meta.total_date_index[-1]
        log_info("User config begin date %s, end date %s, back days %s", begin_date, end_date, back_days)

        # begin date 及其之后的第一个交易日
        begin_di = self.__get_di(str(begin_date), common_utils.equal_or_first_greater)
        # end date 及其之前的最后一个交易日
        end_di = self.__get_di(str(end_date), common_utils.equal_or_first_less)

        # 加载标的, 范围是 [begin_di - back_days, end_di]
        self.__load_instrument_index(self.__meta.meta_dir, begin_di - back_days, 
                                     end_di, self.__config_dict.get("simple_index", False))

        # checkpoint
        if config_dict.get("checkpoint") == "true":
            self.__meta.checkpoint = True
            self.__meta.checkpoint_dir = config_dict["checkpointDir"]
            checkpoint_days = int(config_dict["checkpointDays"])
            self.__meta.check_save_di = end_di - checkpoint_days
            check_date_path = os.path.join(self.__meta.checkpoint_dir, ".date") # type: ignore
            if os.path.exists(check_date_path):
                with open(check_date_path, "r") as reader:
                    date = int(reader.read())
                    check_load_di = self.__meta.di_mapping[date] + 1
                    if check_load_di > end_di:
                        abort("check load di %s > end di %s, need delete checkpoint", check_load_di, end_di)
                    elif check_load_di < begin_di:
                        abort("check load di %s < begin di %s, need delete checkpoint", check_load_di, begin_di)
                    else:
                        begin_di = check_load_di
                        self.__meta.check_load_di = check_load_di
                        for file_name in os.listdir(self.__meta.checkpoint_dir):
                            if file_name == ".date":
                                continue
                            self.__meta.check_file_list.add(file_name)

            log_info("check point enable, dir %s, days %s, load di %s, save di %s", self.__meta.checkpoint_dir, checkpoint_days,
                     self.__meta.check_load_di, self.__meta.check_save_di)

        # get yyyymmdd
        self.__meta.begin_trading_day = self.__meta.total_date_index[begin_di]
        self.__meta.end_trading_day = self.__meta.total_date_index[end_di]

        log_info("User set begin trading day %s(%s), end trading day %s(%s)", self.__meta.begin_trading_day, begin_di, self.__meta.end_trading_day, end_di)
        abort_if(begin_di != self.__meta.total_di_mapping[self.__meta.begin_trading_day] or end_di != self.__meta.total_di_mapping[self.__meta.end_trading_day],
                 "Meta di mapping error")
        abort_if(begin_di > end_di, "Begin di(%s) should <= end di(%s)", begin_di, end_di)

        valid_begin_di = begin_di - back_days
        # TODO: comment in meta.py?
        # self.__meta.valid_begin_trading_day = self.__meta.total_date_index[valid_begin_di]
        self.__meta.back_days = back_days
        self.__meta.matrix_back_days = config_dict.get("matrix_back_days", back_days)
        self.__meta.max_back_days = max(self.__meta.back_days, self.__meta.matrix_back_days)
        # log_info("User set back days %s, valid begin trading day %s", self.__meta.back_days, self.__meta.valid_begin_trading_day)
        log_info("User set matrix back days %s", self.__meta.matrix_back_days)

        # NOTE: how offeset_* ?
        for di in range(begin_di, end_di + 1):
            new_di = di - begin_di
            trading_day = self.__meta.total_date_index[di]
            self.__meta.offset_date_index.append(trading_day)
            self.__meta.offset_di_mapping[trading_day] = new_di

        # self.__meta.valid_begin_di = begin_di - back_days
        self.__meta.begin_di = begin_di
        self.__meta.end_di = end_di
        # self.__meta.valid_di_size = self.__meta.end_di - self.__meta.valid_begin_di + 1
        self.__meta.di_size = self.__meta.end_di - self.__meta.begin_di + 1
        self.__meta.di_list = list(range(self.__meta.begin_di, self.__meta.end_di + 1))
        log_info("User set user begin di %s, user end di %s, user di size %s",
                 self.__meta.begin_di, self.__meta.end_di, self.__meta.di_size)
        if "today_date" in config_dict:
            self.__meta.today_di = self.__get_di(config_dict["today_date"], common_utils.equal_or_first_less)
            self.__meta.today_date = self.__meta.date_index[self.__meta.today_di]
            log_warn("User set today date %s, today di %s", self.__meta.today_date, self.__meta.today_di)
        else:
            self.__meta.today_di = self.__get_di("TODAY", common_utils.equal_or_first_less)
            self.__meta.today_date = self.__meta.date_index[self.__meta.today_di]
            log_info("Auto set today date %s, today di %s", self.__meta.today_date, self.__meta.today_di)

    def __load_instrument_index(self, meta_dir: str, load_begin_di: int, load_end_di: int, simple_index=False):
        """
        param:
            simple_index(bool): 是否考虑标的有效日期
        """
        file_path = os.path.join(meta_dir, "meta", "index", "InstrumentIndex.csv")
        lines = common_utils.load_csv_file(file_path)
        # valid_begin_di = self.__meta.begin_di - self.__meta.max_back_days
        self.__meta.all_instrument_index = [""] * self.__meta.ii_size
        if not simple_index:
            for di in range(load_begin_di, load_end_di + 1):
                self.__meta.instrument_index[di] = ([""] * self.__meta.ii_size).copy()
        else:
            # simple index only supply last
            # 相当于忽略上市日期
            log_info("User set simple index true")
            self.__meta.instrument_index[self.__meta.end_di] = ([""] * self.__meta.ii_size).copy()

        for line in lines:
            ii = int(line[0])           # 行号就是 ii
            instrument: str = line[1]   # 标的代码
            start_date = int(line[2])   # 标的起始日期
            end_date = int(line[3])     # 标的结束日期

            self.__meta.ii_mapping[instrument] = ii
            self.__meta.all_instrument_index[ii] = instrument

            if not simple_index:
                # 标的无有效日期区间
                if end_date <= self.__meta.total_date_index[0] or start_date > self.__meta.total_date_index[-1]:
                    continue

                start_di = self.__meta.total_di_mapping[start_date]

                if start_di < load_begin_di:
                    start_di = load_begin_di

                if end_date > self.__meta.total_date_index[-1]:
                    end_di = self.__meta.total_di_mapping[self.__meta.total_date_index[-1]] - 1
                else:
                    end_di = self.__meta.total_di_mapping[end_date] - 1

                if end_di > load_end_di:
                    end_di = load_end_di

                # 在有效日期中填充标的
                for di in range(start_di, end_di + 1):
                    self.__meta.instrument_index[di][ii] = instrument
            else:
                self.__meta.instrument_index[self.__meta.end_di][ii] = instrument

        self.__meta.last_instrument_index = self.__meta.instrument_index[load_end_di]
        self.__meta.ii_list = list(range(0, self.__meta.ii_size))

        # with open("./test.csv", "w") as writer:
        #     for di in range(len(self.meta.instrument_index)):
        #         for ii in range(len(self.meta.instrument_index[di])):
        #             if self.meta.instrument_index[di][ii] != "":
        #                 writer.write("%s,%s,%s,%s\n" % (di, self.meta.date_index[di], ii, self.meta.instrument_index[di][ii]))
        # log_info("Test csv")

        log_info("Load instrument index finish")

    def __load_time_index(self, meta_dir: str):
        time_index_dir = os.path.join(meta_dir, "meta", "time_index")
        self.__meta.time_index_dict["day"] = [DAY_TIME]
        self.__meta.time_int_index_dict["day"] = [DAY_TIME_INT]
        self.__meta.time_mapping_dict["day"] = {DAY_TIME: 0}
        for file_name in os.listdir(time_index_dir):
            file_path = os.path.join(time_index_dir, file_name)
            lines = common_utils.load_csv_file(file_path)
            interval = os.path.splitext(file_name)[0]
            time_index = self.__meta.time_index_dict.setdefault(interval, [])
            time_int_index = self.__meta.time_int_index_dict.setdefault(interval, [])
            time_mapping = self.__meta.time_mapping_dict.setdefault(interval, SortedDict())
            for i in range(len(lines)):
                line = lines[i]
                ti = int(line[0])
                update_time = line[2]
                if ti != i:
                    abort("Time index file error, di(%s) != i(%s), interval %s", ti, i, interval)
                time_index.append(update_time)
                time_int_index.append(int(update_time.replace(":", "")))
                time_mapping[update_time] = ti
            log_info("Load time index %s finish", interval)

    def __check_time(self, config_dict):
        self.__meta.interval = config_dict.get("interval", self.__meta.interval)
        self.__meta.interval_time_mapping = self.__meta.time_mapping_dict[self.__meta.interval]
        self.__meta.interval_time_index = self.__meta.time_index_dict[self.__meta.interval]
        self.__meta.interval_ti_size = len(self.__meta.interval_time_index)

        for item in itertools.product(self.__meta.offset_date_index, self.__meta.interval_time_index):
            self.__meta.interval_date_time_index.append(datetime.datetime.strptime("{} {}".format(item[0], item[1]), "%Y%m%d %H:%M:%S"))
        for item in itertools.product(self.__meta.offset_date_index, self.__meta.interval_time_mapping.values()):
            self.__meta.interval_date_time_int_index.append(item[0] * 10000 + item[1])

        if self.__meta.interval != "day":
            self.__meta.interval_time_mapping = self.__meta.time_mapping_dict[self.__meta.interval]
            self.__meta.interval_time_index = self.__meta.time_index_dict[self.__meta.interval]
            begin_time = config_dict.get("begin_time", self.__meta.interval_time_index[0])
            end_time = config_dict.get("end_time", self.__meta.interval_time_index[-1])
            self.__meta.begin_ti = self.__meta.interval_time_mapping[begin_time]
            self.__meta.end_ti = self.__meta.interval_time_mapping[end_time]
            log_info("User set begin ti %s(%s), end ti %s(%s)", self.__meta.begin_ti, begin_time, self.__meta.end_ti, end_time)

    def __load_enum(self, meta_dir: str):
        enum_dir = os.path.join(meta_dir, "meta", "enum")
        for file_name in os.listdir(enum_dir):
            if not file_name.startswith("Enum"):
                continue
            file_path = os.path.join(enum_dir, file_name)
            lines = common_utils.load_csv_file(file_path)
            enum_name = os.path.splitext(file_name)[0][len("Enum_"):]
            enum_index = self.__meta.enum_index_dict.setdefault(enum_name, {})
            enum_mapping = self.__meta.enum_mapping_dict.setdefault(enum_name, {})
            for line in lines:
                enum_id = str(line[0]) if not str(line[0]).isdigit() else int(line[0])
                enum_value = str(line[1]) if not str(line[1]).isdigit() else int(line[1])
                enum_index[enum_id] = enum_value
                enum_mapping[enum_value] = enum_id
            log_info("Load enum %s finish", enum_name)

    def __load_calendar(self, meta_dir: str):
        file_path = os.path.join(meta_dir, "meta", "index", "Calendar.csv")
        if not os.path.exists(file_path):
            return
        lines = common_utils.load_csv_file(file_path)
        for line in lines:
            trading_day = int(line[0])
            market = line[1]
            self.__meta.calendar_dict.setdefault(market, SortedList()).add(trading_day)
        log_info("Load calendar finish")


def load_meta(config_dict: dict):
    return MetaLoader(config_dict).run()
