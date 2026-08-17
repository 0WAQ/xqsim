from DataProviderStatic import *
from DataProviderStocksCommon import STOCKS_CC_DIR, STOCKS_UPDATE_DIR
from xqsim.xqsim_run import builder_run
import xqsim.common_utils as common_utils
import numpy as np

ABBR_DICT = {
    "000300.SH": "hs300",
    "000905.SH": "zz500",
    "000016.SH": "sz50"
}

SQL_INDEX_DICT = {
    "000300.SH": "000300.SH",
    "399300.SZ": "000300.SH",
    "000905.SH": "000905.SH",
    "399905.SZ": "000905.SH",
    "000016.SH": "000016.SH",
    "999987.SH": "000016.SH",
}

MINUTE_DICT = {"minute15": ("m15", "15min"),
               "minute5": ("m5", "5min"),
               "minute1": ("m1", "1min")}


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.intervals = self.cfg.get("intervals", MINUTE_DICT.keys())

    def generate_index(self, interval):
        log_info("generate interval: %s", interval)
        suffix = MINUTE_DICT[interval][0]
        db_name = MINUTE_DICT[interval][1]
        time_mapping = self.meta.time_mapping_dict[interval]
        shape = (self.meta.di_size, len(time_mapping), 1)
        default = nan
        dtype = np.float64
        array_dict = {}

        preclose_data_dict = {}
        for index in ABBR_DICT.keys():
            preclose_data_dict[index] = np.full((self.meta.di_size, 1), default, dtype)

        sql_day = """
                  SELECT TRADE_DT AS TradingDay, S_INFO_WINDCODE AS WindCode, S_DQ_PRECLOSE AS preclose
                  FROM wind.AINDEXEODPRICES
                  WHERE TRADE_DT BETWEEN '%s' AND '%s' AND S_INFO_WINDCODE IN %s
                  """ % (self.meta.begin_trading_day, self.meta.end_trading_day, tuple(ABBR_DICT.keys())[:])

        for row in self.exec_sql_fetchall(sql_day):
            trading_day = int(row["TradingDay"])
            di = self.meta.offset_di_mapping[trading_day]
            ii = 0
            index = row["WindCode"]
            preclose_data_dict[index][di][ii] = row["preclose"]

        name_dict = {"open": "open",
                     "high": "high",
                     "low": "low",
                     "close": "close",
                     "volume": "volume",
                     "value": "value"}
        sql = """
            SELECT `date` AS `TradingDay`, `time`, `sid` AS `WindCode`, %s
            FROM hf_bar.bar_%s 
            WHERE `sid` IN %s AND `date` BETWEEN '%s' AND '%s' 
            ORDER BY `date`, `time`
            """ % (",".join(name_dict.values()), db_name, tuple(SQL_INDEX_DICT.keys())[:], self.meta.begin_trading_day, self.meta.end_trading_day)

        for index in ABBR_DICT:
            for name in name_dict.keys():
                array_dict.setdefault(index, {})[name] = np.full(shape, default, dtype)
            array_dict[index]["preclose"] = np.full(shape, default, dtype)
            array_dict[index]["ret"] = np.full(shape, default, dtype)
            array_dict[index]["vwap"] = np.full(shape, default, dtype)

        for row in self.exec_sql_fetchall(sql):
            index = row["WindCode"]
            trading_day = int(row["TradingDay"].strftime("%Y%m%d"))
            current_time = str(row["time"])
            if len(current_time) < 8:
                current_time = "0" + current_time
            di = self.meta.offset_di_mapping[trading_day]
            ti = time_mapping[current_time]
            ii = 0
            index = SQL_INDEX_DICT[index]
            for name in name_dict.keys():
                array_dict[index][name][di][ti][ii] = row[name]
            if ti == 0:
                array_dict[index]["preclose"][di][ti][ii] = preclose_data_dict[index][di][ii]
            else:
                array_dict[index]["preclose"][di][ti][ii] = array_dict[index]["close"][di][ti - 1][ii]
            array_dict[index]["ret"][di][ti][ii] = array_dict[index]["close"][di][ti][ii] / array_dict[index]["preclose"][di][ti][ii] - 1 \
                if array_dict[index]["preclose"][di][ti][ii] != 0 else 0
            array_dict[index]["vwap"][di][ti][ii] = common_utils.round_right(array_dict[index]["value"][di][ti][ii] / array_dict[index]["volume"][di][ti][ii], 4) \
                if array_dict[index]["volume"][di][ti][ii] != 0 else array_dict[index]["close"][di][ti][ii]

        for index, dic in array_dict.items():
            abbr = "idx.k%s.%s" % (suffix, ABBR_DICT[index])
            for name, array in dic.items():
                data_name = abbr + "." + name.lower()
                self.write_data(data_name, array)

    def generate(self):
        for interval in self.intervals:
            self.generate_index(interval)


def main():
    builder_run(meta_dir=STOCKS_CC_DIR, begin_date=20200827, end_date=20200831, output_cache_dir=STOCKS_UPDATE_DIR)


if __name__ == '__main__':
    main()
