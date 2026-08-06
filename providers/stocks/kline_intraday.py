from static_provider import *
from xqsim.xqsim_run import builder_run
import xqsim.common_utils as common_utils
import numpy as np


MINUTE_DICT = {"minute15": ("m15", "15min"),
               "minute5": ("m5", "5min"),
               "minute1": ("m1", "1min")}


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.name_dict = {"open": "open",
                          "high": "high",
                          "low": "low",
                          "close": "close",
                          "volume": "volume",
                          "value": "value"}
        self.intervals = self.cfg.get("intervals", MINUTE_DICT.keys())

    def generate_di(self, start_di, end_di, interval):
        log_info("generate di: %s -- %s, interval %s", start_di, end_di, interval)
        begin_trading_day = self.meta.total_date_index[start_di]
        end_trading_day = self.meta.total_date_index[end_di]
        time_mapping = self.meta.time_mapping_dict[interval]
        shape = (end_di - start_di + 1, len(time_mapping), self.meta.ii_size)
        default = nan
        dtype = np.float64
        array_dict = {}

        suffix = MINUTE_DICT[interval][0]
        db_name = MINUTE_DICT[interval][1]

        preclose_data = np.full((end_di - start_di + 1, self.meta.ii_size), default, dtype)

        sql_day = """
              SELECT TRADE_DT AS TradingDay, S_INFO_WINDCODE AS WindCode, S_DQ_PRECLOSE AS preclose
              FROM wind.ASHAREEODPRICES
              WHERE TRADE_DT BETWEEN '%s' AND '%s'
              """ % (begin_trading_day, end_trading_day)

        for row in self.exec_sql_fetchall(sql_day):
            trading_day = int(row["TradingDay"])
            di = self.meta.total_di_mapping[trading_day] - start_di
            code = row["WindCode"]
            if code not in self.meta.ii_mapping:
                continue
            ii = self.meta.ii_mapping[code]
            preclose_data[di][ii] = row["preclose"]

        for name in self.name_dict.keys():
            array_dict[name] = np.full(shape, default, dtype)
        array_dict["preclose"] = np.full(shape, default, dtype)
        array_dict["ret"] = np.full(shape, default, dtype)
        array_dict["vwap"] = np.full(shape, default, dtype)

        sql = """
                SELECT `date` AS `TradingDay`, `time`, `sid` AS `WindCode`, %s
                FROM hf_bar.bar_%s 
                WHERE `date` BETWEEN '%s' AND '%s' 
                ORDER BY `date`, `time`
                """ % (",".join(self.name_dict.values()), db_name, begin_trading_day, end_trading_day)

        for row in self.exec_sql_fetchall(sql):
            code = row["WindCode"]
            trading_day = int(row["TradingDay"].strftime("%Y%m%d"))
            current_time = str(row["time"])
            if len(current_time) < 8:
                current_time = "0" + current_time
            if code not in self.meta.ii_mapping:
                continue
            ii = self.meta.ii_mapping[code]
            di = self.meta.total_di_mapping[trading_day] - start_di
            ti = time_mapping[current_time]
            for name in self.name_dict.keys():
                array_dict[name][di][ti][ii] = row[name]
            if ti == 0:
                array_dict["preclose"][di][ti][ii] = preclose_data[di][ii]
            else:
                array_dict["preclose"][di][ti][ii] = array_dict["close"][di][ti - 1][ii]
            array_dict["ret"][di][ti][ii] = array_dict["close"][di][ti][ii] / array_dict["preclose"][di][ti][ii] - 1 \
                if array_dict["preclose"][di][ti][ii] != 0 else 0
            array_dict["vwap"][di][ti][ii] = common_utils.round_right(array_dict["value"][di][ti][ii] / array_dict["volume"][di][ti][ii], 4) \
                if array_dict["volume"][di][ti][ii] != 0 else array_dict["close"][di][ti][ii]
        if interval == "minute1":
            for name, array in array_dict.items():
                self.write_compress_data("k%s.%s" % (suffix, name), array, begin_trading_day, end_trading_day)
        else:
            for name, array in array_dict.items():
                self.append_data("k%s.%s" % (suffix, name), array, begin_trading_day, end_trading_day)

    def generate(self):
        batch_size = 50
        for interval in self.intervals:
            for di in range(self.meta.begin_di, self.meta.end_di + 1, batch_size):
                start_di = di
                end_di = min(di + batch_size - 1, self.meta.end_di)
                self.generate_di(start_di, end_di, interval)


def main():
    builder_run(meta_dir="/cc", begin_date=20200720, end_date=20200728, output_cache_dir="./cc_update", intervals=["minute15"])


if __name__ == '__main__':
    main()
