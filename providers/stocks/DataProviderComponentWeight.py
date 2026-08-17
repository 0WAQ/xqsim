from DataProviderStatic import *
from DataProviderStocksCommon import STOCKS_CC_DIR, STOCKS_UPDATE_DIR
from sortedcollections import SortedDict
from xqsim.xqsim_run import builder_run
import numpy as np

ABBR_DICT = {
    "000016.SH": "sz50",
    "000905.SH": "zz500",
    "000906.SH": "zz800",
    "000852.SH": "zz1000",
    "399317.SZ": "mkt",
    "399005.SZ": "zxbz",
    "399006.SZ": "cybz",
    "000300.SH": "hs300"
}


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.abbr = "cw"
        self.ret_array_dict = {}
        self.generate_hs300_flag = self.cfg.get("hs300", True)
        self.generate_zz500_flag = self.cfg.get("zz500", True)

    def generate_wind(self, data_name, sql):
        weight_array = np.full((self.meta.di_size, self.meta.ii_size), 0.0, np.float64)
        for row in self.exec_sql_fetchall(sql):
            trading_day = int(row["TradingDay"])
            di = self.meta.offset_di_mapping[trading_day]
            ii = self.meta.ii_mapping[row["WindCode"]]
            weight = row["weight"]
            weight_array[di][ii] = weight

        self.write_data(self.abbr + "." + data_name, weight_array)

    def generate_hs300(self):
        sql = """
            SELECT S_CON_WINDCODE AS WindCode, TRADE_DT AS TradingDay, I_WEIGHT / 100 AS weight
            FROM wind.AINDEXHS300CLOSEWEIGHT
            WHERE TRADE_DT BETWEEN '%s' AND '%s'
            """ % (self.meta.begin_trading_day, self.meta.end_trading_day)
        self.generate_wind("hs300_wind", sql)

    def generate_zz500(self):
        sql = """
            SELECT S_CON_WINDCODE AS WindCode, TRADE_DT AS TradingDay, I_WEIGHT / 100 AS weight
            FROM wind.AINDEXCSI500CLOSEWEIGHT
            WHERE TRADE_DT BETWEEN '%s' AND '%s'
            """ % (self.meta.begin_trading_day, self.meta.end_trading_day)
        self.generate_wind("zz500_csi", sql)

        sql = """
            SELECT S_CON_WINDCODE AS WindCode, TRADE_DT AS TradingDay, WEIGHT / 100 AS weight
            FROM wind.AINDEXCSI500WEIGHT
            WHERE TRADE_DT BETWEEN '%s' AND '%s'
            """ % (self.meta.begin_trading_day, self.meta.end_trading_day)
        self.generate_wind("zz500_next_csi", sql)

    def get_ret(self):
        # ret need more days than weight
        sql = """
            SELECT TradingDay AS TradingDay, WindCode AS WindCode, ClosePrice AS `close`, PreClosePrice AS preclose
            FROM meta.KData_wind
            WHERE TradingDay BETWEEN DATE_FORMAT(('%s' + INTERVAL -3 MONTH), '%%Y%%m%%d') AND '%s'
            """ % (self.meta.begin_trading_day, self.meta.end_trading_day)
        for row in self.exec_sql_fetchall(sql):
            trading_day = int(row["TradingDay"])
            di = self.meta.total_di_mapping[trading_day]
            if row["WindCode"] not in self.meta.ii_mapping:
                continue
            ii = self.meta.ii_mapping[row["WindCode"]]
            self.ret_array_dict.setdefault(di, np.full(self.meta.ii_size, nan, np.float64))[ii] = row["close"] / row["preclose"] - 1 if row["preclose"] != 0 else 0

    def generate_by_calculate(self, index):
        log_info("Generate component weight of %s", index)
        index_weight_array = np.full((self.meta.di_size, self.meta.ii_size), nan, np.float64)
        weight_month_dict = SortedDict()

        sql = """
            SELECT S_CON_WINDCODE AS WindCode, TRADE_DT AS TradingDay, I_WEIGHT / 100 AS weight
            FROM wind.AINDEXHS300FREEWEIGHT
            WHERE S_INFO_WINDCODE = '%s' AND TRADE_DT BETWEEN DATE_FORMAT(('%s' + INTERVAL -3 MONTH), '%%Y%%m%%d') AND '%s'
            ORDER BY TRADE_DT
            """ % (index, self.meta.begin_trading_day, self.meta.end_trading_day)
        for row in self.exec_sql_fetchall(sql):
            trading_day = int(row["TradingDay"])
            di = self.meta.total_di_mapping[trading_day]
            code = row["WindCode"]
            if index.startswith("399"):
                # check for wind code for 399XXX, wind make mistakes for QLE
                code = code[0:6]
                if code[0] == "6":
                    code += ".SH"
                else:
                    code += ".SZ"
            ii = self.meta.ii_mapping[code]
            weight_month_dict.setdefault(di, np.full(self.meta.ii_size, nan, np.float64))[ii] = row["weight"]

        # print(weight_month_dict)
        begin_index = weight_month_dict.bisect_right(self.meta.total_di_mapping[self.meta.begin_trading_day]) - 1
        if begin_index < 0:
            begin_index = 0
        keys = list(weight_month_dict.islice(begin_index))
        total_begin_di = keys[0]
        total_end_di = self.meta.total_di_mapping[self.meta.end_trading_day]
        # print(total_begin_di, total_end_di)
        for di in range(total_begin_di, total_end_di + 1):
            if di not in weight_month_dict:
                if di in self.ret_array_dict:
                    last_weight_array = np.nan_to_num(weight_month_dict[di - 1])
                    ret_array = np.nan_to_num(self.ret_array_dict[di])
                    weight_month_dict[di] = last_weight_array * (1 + ret_array) / np.sum(last_weight_array * (1 + ret_array))
                else:
                    # maybe T day
                    weight_month_dict[di] = np.full(self.meta.ii_size, nan, np.float64)
            if self.meta.total_date_index[di] >= self.meta.begin_trading_day:
                index_weight_array[self.meta.offset_di_mapping[self.meta.total_date_index[di]]] = np.nan_to_num(weight_month_dict[di])
        self.write_data(self.abbr + "." + ABBR_DICT[index], index_weight_array)

    def generate(self):
        if self.generate_hs300_flag:
            self.generate_hs300()
        if self.generate_zz500_flag:
            self.generate_zz500()

        self.get_ret()
        for index, name in ABBR_DICT.items():
            self.generate_by_calculate(index)


def main():
    builder_run(meta_dir=STOCKS_CC_DIR, begin_date=20130101, end_date="TODAY-1", output_cache_dir=STOCKS_UPDATE_DIR)


if __name__ == '__main__':
    main()
