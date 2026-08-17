from static_provider import *
from stocks_common import STOCKS_CC_DIR, STOCKS_UPDATE_DIR
from xqsim.xqsim_run import builder_run

from sortedcollections import SortedDict, SortedList


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.ignore_column_set = {"OBJECT_ID", "OPDATE", "OPMODE", "COPDATE", "MOPDATE",
                                  "ACTUAL_ANN_DT", "ANN_DT", "CRNCY_CODE", "REPORT_PERIOD", "STATEMENT_TYPE",
                                  "S_INFO_WINDCODE", "WIND_CODE", "MEMO", "S_INFO_COMPCODE", "COMP_TYPE_CODE"}.union(self.cfg.get("ignore_columns", set()))
        self.db_name = "wind"
        self.table_name = self.cfg.get("table", self.id)
        self.abbr = self.cfg.get("abbr", self.table_name)
        self.cube_size = self.cfg.get("cube", 8)
        self.back_year = self.cfg.get("year", self.cube_size + 1)
        self.extra = self.cfg.get("extra", set())

        self.ann_dt = self.cfg.get("ann_dt", "ANN_DT")
        self.report_period = self.cfg.get("report_period", "REPORT_PERIOD")
        self.actual_ann_dt = self.cfg.get("actual_ann_dt", None)

        self.comp = self.cfg.get("comp", False)

    def generate(self):
        log_info("Generate: %s.%s which use config %s, abbr %s, cube size %s",
                 self.db_name, self.table_name, self.mysql_config, self.abbr, self.cube_size)
        columns = self.get_column_names(self.db_name, self.table_name, self.ignore_column_set)
        for name in self.extra:
            columns[name.lower()] = "CAST(%s AS SIGNED) AS %s" % (name, name.lower())

        ann_dt_str = self.ann_dt if not self.actual_ann_dt else self.actual_ann_dt
        fin_ann_dt_sql = "LEAST(DATE_FORMAT(OPDATE -INTERVAL 8 HOUR, '%%Y%%m%%d'),%s)" % ann_dt_str

        infos = {ann_dt_str.lower(): "CAST(%s AS SIGNED) AS %s" % (ann_dt_str, ann_dt_str.lower()),
                 self.report_period.lower(): "CAST(%s AS SIGNED) AS %s" % (self.report_period, self.report_period.lower()),
                 "fin_ann_dt": "CAST(%s AS SIGNED) AS fin_ann_dt" % fin_ann_dt_sql}

        if not self.comp:
            sql = """
            SELECT S_INFO_WINDCODE,%s,%s 
            FROM %s.%s 
            WHERE %s is not null and %s is not null
            AND %s BETWEEN DATE_FORMAT('%s' -INTERVAL %s YEAR, '%%Y%%m%%d') AND '%s' 
            """ % (",".join(infos.values()), ",".join(columns.values()), self.db_name, self.table_name,
                   ann_dt_str, self.report_period,
                   fin_ann_dt_sql, self.meta.begin_trading_day, self.back_year, self.meta.date_index[self.meta.end_di + 1])
        else:
            sql = """
            SELECT S_INFO_WINDCODE,%s,%s 
            FROM wind.WINDCODE_TO_COMPCODE A INNER JOIN %s.%s B on A.S_INFO_COMPCODE = B.S_INFO_COMPCODE
            WHERE %s is not null and %s is not null
            AND %s BETWEEN DATE_FORMAT('%s' -INTERVAL %s YEAR, '%%Y%%m%%d') AND '%s' 
            """ % (",".join(infos.values()), ",".join(columns.values()), self.db_name, self.table_name,
                   ann_dt_str, self.report_period,
                   fin_ann_dt_sql, self.meta.begin_trading_day, self.back_year, self.meta.date_index[self.meta.end_di + 1])

        min_date = 299999999
        min_di = min_date
        container = SortedDict()  # dict[di][ii][report period] = row
        for row in self.exec_sql_fetchall(sql):
            if row["S_INFO_WINDCODE"] not in self.meta.ii_mapping:
                continue
            ii = self.meta.ii_mapping[row["S_INFO_WINDCODE"]]
            ann_dt = row["fin_ann_dt"]
            di = common_utils.equal_or_first_less(self.meta.date_index, ann_dt)
            container.setdefault(di, {}).setdefault(ii, SortedDict())[row[self.report_period.lower()]] = row
            if ann_dt < min_date:
                min_date = ann_dt
                min_di = di

        log_info("Min date is %s, min di is %s", min_date, min_di)

        array_dict = {}
        for column in infos.keys():
            array_dict[column] = np.full((self.meta.di_size, self.meta.ii_size, self.cube_size), NAN, np.float64)
        for column in columns.keys():
            array_dict[column] = np.full((self.meta.di_size, self.meta.ii_size, self.cube_size), NAN, np.float64)

        latest_array = []
        for ii in range(self.meta.ii_size):
            latest_array.append(SortedDict())

        for di in range(min_di, self.meta.end_di + 1):
            offset_di = 0
            if di > self.meta.begin_di:
                offset_di = di - self.meta.begin_di
                for array in array_dict.values():
                    array[offset_di] = array[offset_di - 1]  # fill with prev value
            if di in container:
                for ii, sorted_dict in container[di].items():
                    ii_latest_array_dict = latest_array[ii]
                    for report_period, new_row in sorted_dict.items():
                        if report_period not in ii_latest_array_dict:  # find new report period
                            if len(ii_latest_array_dict) < self.cube_size:  # less than cube size, append
                                ii_latest_array_dict[report_period] = new_row

                            elif report_period > ii_latest_array_dict.peekitem()[0]:  # reach cube size already, pop first and append
                                ii_latest_array_dict.popitem(0)
                                ii_latest_array_dict[report_period] = new_row

                            else:
                                # report period already expired, ignore
                                continue

                            # but in array, 0 means largest, so move 0: cube_size -1  to 1: cube_size
                            # then 0 set to new report period
                            for name, array in array_dict.items():
                                array[offset_di][ii][1: self.cube_size] = array[offset_di][ii][0: self.cube_size - 1]
                                array[offset_di][ii][0] = new_row[name]
                        else:
                            current_row = ii_latest_array_dict[report_period]
                            for name, array in array_dict.items():
                                if new_row[name] is not None and current_row[name] != new_row[name]:  # new value not null and value not same with current value
                                    current_row[name] = new_row[name]
                                    array_dict[name][offset_di][ii][self.cube_size - 1 - ii_latest_array_dict.index(report_period)] = new_row[name]
                            ii_latest_array_dict[report_period] = current_row

        for name, array in array_dict.items():
            data_name = self.abbr + "." + name.lower()
            self.write_compress_data(data_name, array)


def main():
    builder_run(meta_dir=STOCKS_CC_DIR, begin_date=20160101, end_date=20170228, output_cache_dir=STOCKS_UPDATE_DIR, table="ASHAREPROFITEXPRESS")


if __name__ == '__main__':
    main()
