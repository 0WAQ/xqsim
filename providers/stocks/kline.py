from static_provider import *
from xqsim.xqsim_run import builder_run
import xqsim.common_utils as common_utils
import numpy as np



class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.abbr = "k"

    def generate(self):
        name_dict = {"open": "OpenPrice",
                     "high": "HighPrice",
                     "low": "LowPrice",
                     "close": "ClosePrice",
                     "volume": "Volume",
                     "value": "Amount",
                     "preclose": "PreClosePrice",
                     "adj": "AccuAdjFactor",
                     "vwap": "AvgPrice",
                     "upper": "UpperLimitPrice",
                     "lower": "LowerLimitPrice",
                     "tstatus": "TStatus",
                     "wind_tstatus": "WindTStatusCode"}

        new_name_dict = name_dict.copy()
        for name in name_dict.keys():
            new_name_dict[name] += " AS " + name
        sql = """
               SELECT TradingDay, WindCode, %s
               FROM meta.KData_wind
               WHERE TradingDay BETWEEN '%s' AND '%s' order by TradingDay
               """ % (",".join(new_name_dict.values()), self.meta.begin_trading_day, self.meta.end_trading_day)
        shape = (self.meta.di_size, self.meta.ii_size)
        default = nan
        dtype = np.float64
        array_dict = {}

        for name in name_dict.keys():
            array_dict[name] = np.full(shape, default, dtype)
        array_dict["ret"] = np.full(shape, default, dtype)

        # current_di = 0

        for row in self.exec_sql_fetchall(sql):
            trading_day = int(row["TradingDay"])
            di = self.meta.offset_di_mapping[trading_day]

            # if di > current_di:
            #     for name in name_dict.keys():
            #         array_dict[name][di] = array_dict[name][current_di]
            #     di = current_di
            code = row["WindCode"]
            if code not in self.meta.ii_mapping:
                continue
            ii = self.meta.ii_mapping[code]
            for name in name_dict.keys():
                array_dict[name][di][ii] = row[name]
            array_dict["ret"][di][ii] = array_dict["close"][di][ii] / array_dict["preclose"][di][ii] - 1 if array_dict["preclose"][di][ii] != 0 else 0

        for name, array in array_dict.items():
            self.write_data("%s.%s" % (self.abbr, name.lower()), array)


def main():
    builder_run(meta_dir="/cc", begin_date="TODAY-5", end_date="TODAY", output_cache_dir="./cc_update")


if __name__ == '__main__':
    main()
