from static_provider import *
from xqsim.xqsim_run import builder_run
import xqsim.common_utils as common_utils
import numpy as np


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)

        self.code_dict = {}
        self.level_dict = {}

    def load_citics_industry(self):
        sql = """
            SELECT DISTINCT S_INFO_WINDCODE FROM wind.AINDEXINDUSTRIESEODCITICS order by S_INFO_WINDCODE
            """
        for row in self.exec_sql_fetchall(sql):
            code = int(row["S_INFO_WINDCODE"][2:-3])
            if code < 5100:
                level = "level1"
            elif 5100 < code < 5200 or 5800 <= code < 5900:
                level = "level2"
            elif 5200 < code < 5800:
                level = "level3"
            elif 5900 < code:
                level = "level1derived"
            else:
                continue
            self.level_dict.setdefault(level, []).append(row["S_INFO_WINDCODE"])
        for level, code_list in self.level_dict.items():
            for i in range(len(code_list)):
                self.code_dict[code_list[i]] = (level, i)

    def generate_index(self):
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
           FROM wind.AINDEXINDUSTRIESEODCITICS
           WHERE TRADE_DT BETWEEN '%s' AND '%s'
           """ % (",".join(new_name_dict.values()), self.meta.begin_trading_day, self.meta.end_trading_day)
        default = np.nan
        dtype = np.float64
        array_dict = {}

        for level, code_list in self.level_dict.items():
            shape = (self.meta.di_size, len(code_list))
            for name in name_dict.keys():
                array_dict.setdefault(level, {})[name] = np.full(shape, default, dtype)
            array_dict[level]["ret"] = np.full(shape, default, dtype)
            array_dict[level]["vwap"] = np.full(shape, default, dtype)

        for row in self.exec_sql_fetchall(sql):
            trading_day = int(row["TradingDay"])
            di = self.meta.offset_di_mapping[trading_day]
            code = row["WindCode"]
            if code not in self.code_dict:
                if code.startswith("CI0059"):
                    continue
            level, ii = self.code_dict[code]
            for name in name_dict.keys():
                array_dict[level][name][di][ii] = row[name]
            array_dict[level]["ret"][di][ii] = array_dict[level]["close"][di][ii] / array_dict[level]["preclose"][di][ii] - 1 \
                if array_dict[level]["preclose"][di][ii] != 0 else 0
            array_dict[level]["vwap"][di][ii] = common_utils.round_right(array_dict[level]["value"][di][ii] / array_dict[level]["volume"][di][ii], 4) \
                if array_dict[level]["volume"][di][ii] != 0 else array_dict[level]["close"][di][ii]

        for level, dic in array_dict.items():
            abbr = "ciidx.%s" % level
            for name, array in dic.items():
                data_name = abbr + "." + name.lower()
                self.write_data(data_name, array)

    def generate(self):
        self.load_citics_industry()
        self.generate_index()


def main():
    builder_run(meta_dir="/cc", begin_date=20200701, end_date=20200731, output_cache_dir="./cc_update")


if __name__ == '__main__':
    main()
