# cython: language_level=3
from static_provider import *


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.dir_name = "Universe"
        self.abbr = "uv"
        self.buffer_dict = {}

    def generate_universe(self, universe, check_count=0):
        if check_count == 0:
            for di in self.meta.di_list:
                check_count += len([code for code in self.meta.instrument_index[di] if code != ""])
        elif check_count > 0:
            check_count *= self.meta.di_size
        else:
            check_count = None

        if universe == "hs300":
            # just 298 stocks of hs300 in these days
            if self.meta.begin_trading_day <= 20091231:
                check_count -= 2
            if self.meta.begin_trading_day <= 20091230:
                check_count -= 2
            if self.meta.begin_trading_day <= 20091229:
                check_count -= 2
        if universe == "zz1000":
            # begin from 20141017
            if self.meta.begin_trading_day < 20141017:
                check_count -= 1000 * (self.meta.di_mapping[20141017] - self.meta.begin_di)
        if check_count and check_count < 0:
            check_count = 0

        log_info("generate universe %s, count should be %s", universe, check_count)
        buffer = np.full((self.meta.di_size, self.meta.ii_size), False, np.bool_)
        sql = """
                SELECT TradingDay, WindCode 
                FROM meta.Universe_%s 
                WHERE TradingDay BETWEEN '%s' AND '%s'
                """ % (universe, self.meta.begin_trading_day, self.meta.end_trading_day)

        rows = self.exec_sql_fetchall(sql)
        if check_count is not None and check_count != len(rows):
            abort("rows not match, check count(%s) != len(rows)(%s)", check_count, len(rows))
        for row in rows:
            di = self.meta.offset_di_mapping[int(row["TradingDay"])]
            if row["WindCode"] not in self.meta.ii_mapping:
                continue
            ii = self.meta.ii_mapping[row["WindCode"]]
            buffer[di][ii] = True
        self.write_data("%s.%s" % (self.abbr, universe), buffer)
        self.buffer_dict[universe] = buffer

    def generate_qsim_uv(self):
        all_buffer = self.buffer_dict["all"]
        st_buffer = self.buffer_dict["st"]
        ipo_buffer = self.buffer_dict["ipo_120day"]

        sql = """
                SELECT TradingDay, WindCode 
                FROM meta.KData_wind 
                WHERE TStatus = 10 AND TradingDay BETWEEN '%s' AND '%s' 
                ORDER BY TradingDay
                """ % (self.meta.begin_trading_day, self.meta.end_trading_day)
        rows = self.exec_sql_fetchall(sql)
        new_buffer = np.full((self.meta.di_size + 10, self.meta.ii_size), 0, np.int32)
        for row in rows:
            di = self.meta.offset_di_mapping[int(row["TradingDay"])]
            if row["WindCode"] not in self.meta.ii_mapping:
                continue
            ii = self.meta.ii_mapping[row["WindCode"]]
            new_buffer[di: di + 10, ii] += 1
        new_buffer = new_buffer[: -10, :]
        new_buffer_bool = np.full((self.meta.di_size, self.meta.ii_size), False, np.bool_)
        index = new_buffer > 2
        # print(np.where(index))
        new_buffer_bool[index] = True
        buffer = all_buffer & ~st_buffer & ~ipo_buffer & ~new_buffer_bool

        self.write_data("%s.%s" % (self.abbr, "qsim_all"), buffer)

    def generate(self):
        self.generate_universe("all", 0)
        self.generate_universe("sz50", 50)
        self.generate_universe("hs300", 300)
        self.generate_universe("zz500", 500)
        self.generate_universe("zz800", 800)
        self.generate_universe("zz1000", 1000)
        self.generate_universe("ipo_120day", -1)
        self.generate_universe("st", -1)
        self.generate_qsim_uv()


def main():
    builder_run(meta_dir="./cc", begin_date=20130104, end_date="TODAY-1", output_cache_dir="./cc_update")


if __name__ == '__main__':
    main()
