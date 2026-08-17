from DataProviderStatic import *
from DataProviderStocksCommon import STOCKS_CC_DIR, STOCKS_UPDATE_DIR
from xqsim.xqsim_run import builder_run
import xqsim.common_utils as common_utils
import numpy as np


ABBR_DICT = {
    "000300.SH": "hs300",
    "000905.SH": "zz500",
    "000016.SH": "sz50",
    "000906.SH": "zz800",
    "000852.SH": "zz1000"
}


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)

    def generate(self):
        name_dict = {
            "preclose": "S_DQ_PRECLOSE",
            "open": "S_DQ_OPEN",
            "high": "S_DQ_HIGH",
            "low": "S_DQ_LOW",
            "close": "S_DQ_CLOSE",
            "value": "S_DQ_AMOUNT",
            "volume": "S_DQ_VOLUME"
        }
        new_name_dict = name_dict.copy()
        for name in name_dict.keys():
            new_name_dict[name] += " AS " + name
        sql = """
           SELECT TRADE_DT AS TradingDay, S_INFO_WINDCODE AS WindCode, %s
           FROM wind.AINDEXEODPRICES
           WHERE TRADE_DT BETWEEN '%s' AND '%s' AND S_INFO_WINDCODE IN %s
           """ % (",".join(new_name_dict.values()), self.meta.begin_trading_day, self.meta.end_trading_day, tuple(ABBR_DICT.keys())[:])
        shape = (self.meta.di_size, 1)
        default = nan
        dtype = np.float64
        array_dict = {}

        for index in ABBR_DICT:
            for name in name_dict.keys():
                array_dict.setdefault(index, {})[name] = np.full(shape, default, dtype)
            array_dict[index]["ret"] = np.full(shape, default, dtype)
            array_dict[index]["vwap"] = np.full(shape, default, dtype)

        for row in self.exec_sql_fetchall(sql):
            trading_day = int(row["TradingDay"])
            di = self.meta.offset_di_mapping[trading_day]
            ii = 0
            index = row["WindCode"]
            for name in name_dict.keys():
                array_dict[index][name][di][ii] = row[name]
            array_dict[index]["ret"][di][ii] = array_dict[index]["close"][di][ii] / array_dict[index]["preclose"][di][ii] - 1 \
                if array_dict[index]["preclose"][di][ii] != 0 else 0
            array_dict[index]["vwap"][di][ii] = common_utils.round_right(array_dict[index]["value"][di][ii] / array_dict[index]["volume"][di][ii], 4) \
                if array_dict[index]["volume"][di][ii] != 0 else array_dict[index]["close"][di][ii]

        for index, dic in array_dict.items():
            abbr = "idx.k.%s" % ABBR_DICT[index]
            for name, array in dic.items():
                data_name = abbr + "." + name.lower()
                self.write_data(data_name, array)


def main():
    builder_run(meta_dir=STOCKS_CC_DIR, begin_date=20200701, end_date=20200731, output_cache_dir=STOCKS_UPDATE_DIR)


if __name__ == '__main__':
    main()
