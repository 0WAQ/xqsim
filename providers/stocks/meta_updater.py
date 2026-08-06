import os
import pymysql
import pandas as pd
from xqsim import common_utils
import json


STATIC_SQL = "SELECT ID, StaticValue, Comment FROM meta.StaticConfig ORDER BY ID"
DATE_SQL = "SELECT ID, TradingDay FROM meta.DateIndex ORDER BY ID"
INSTRUMENT_SQL = "SELECT ID, WindCode, StartDate, EndDate FROM meta.InstrumentIndex ORDER BY ID"
TIME_SQL = "SELECT ID, TimeInterval, CONVERT(UpdateTime, CHAR) AS UpdateTime FROM meta.TimeIndex ORDER BY TimeInterval, ID"


class MetaUpdater(object):
    def __init__(self, meta_dir, mysql_config):
        self.meta_dir = meta_dir
        json_file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), mysql_config)
        db_info = json.load(open(json_file_path))
        self.conn = pymysql.connect(**db_info, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
        print(json_file_path)

    def update(self, sql, file_name):
        df = pd.read_sql_query(sql, self.conn)
        file_path = os.path.join(self.meta_dir, "meta", "index", file_name)
        common_utils.ensure_dir(file_path)
        df.to_csv(file_path, index=False)
        print("update %s finish" % file_name)

    def update_static_config(self):
        self.update(STATIC_SQL, "StaticIndexSize.csv")

    def update_date_index(self):
        self.update(DATE_SQL, "DateIndex.csv")

    def update_instrument_index(self):
        self.update(INSTRUMENT_SQL, "InstrumentIndex.csv")

    def time_index_to_csv(self, x: pd.DataFrame):
        file_name = "%s.csv" % (x.iloc[0][1])
        file_path = os.path.join(self.meta_dir, "meta", "time_index", file_name)
        common_utils.ensure_dir(file_path)
        x.to_csv(file_path, index=False)
        print("update %s finish" % file_name)

    def update_time_index(self):
        df = pd.read_sql_query(TIME_SQL, self.conn)
        df.groupby("TimeInterval").apply(self.time_index_to_csv)

    def update_enum(self):
        cursor = self.conn.cursor()
        cursor.execute("use meta")
        cursor.execute("show tables")
        for row in cursor.fetchall():
            table = str(row["Tables_in_meta"])
            if table.startswith("Enum"):
                df = pd.read_sql_query("SELECT EnumID, EnumValue FROM %s" % table, self.conn)
                file_path = os.path.join(self.meta_dir, "meta", "enum", table + ".csv")
                common_utils.ensure_dir(file_path)
                df.to_csv(file_path, index=False)
                print("update enum %s finish" % table)

    def update_calendar(self):
        self.update("SELECT TradingDay, Market FROM meta.Calendar", "Calendar.csv")

    def run(self):
        self.update_static_config()
        self.update_date_index()
        self.update_instrument_index()
        self.update_time_index()
        self.update_enum()
        # self.update_calendar()


class EnumUpdater(MetaUpdater):
    def __init__(self, meta_dir, mysql_config):
        super().__init__(meta_dir, mysql_config)

    def run(self):
        self.update_enum()


def diff(sql, conn1, conn2):
    df1 = pd.read_sql_query(sql, conn1)
    df2 = pd.read_sql_query(sql, conn2)
    ans = pd.merge(left=df1, right=df2, how='left', indicator=True, on=None)
    ans = ans.loc[ans._merge == 'left_only', :].drop(columns='_merge')
    if ans.empty is False:
        raise Exception("Find diff for sql %s: %s" % (sql, ans))
    else:
        print("sql %s result: same" % sql)


def run(meta_dir):
    MetaUpdater(meta_dir, "mysql.json").run()
    EnumUpdater(meta_dir, "mysql.json").run()


def main():
    meta_dir = "./cc"
    run(meta_dir)


if __name__ == '__main__':
    main()
