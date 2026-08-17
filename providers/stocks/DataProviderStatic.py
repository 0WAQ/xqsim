import json
import pymysql
from xqsim.common_module import *
from xqsim.base.provider_base import ProviderBase
import numpy as np



class StaticProvider(ProviderBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.mysql_config_dir = self.cfg.get("mysql_config_dir", os.path.abspath(os.path.dirname(__file__)))
        self.mysql_config = self.cfg.get("mysql_config", "mysql.json")

    @staticmethod
    def fillna_with_prev(data: np.ndarray):
        for i in range(1, data.shape[0]):
            index = np.isnan(data[i])
            data[i][index] = data[i - 1][index]

    def exec_sql_fetchall(self, sql: str, json_file=None, limit=None):
        # limit is tuple(str, int), limit[0] is primary key, limit[1] is limit count
        if json_file is None:
            json_file = self.mysql_config
        json_file = os.path.join(self.mysql_config_dir, json_file)
        with open(json_file, "r") as reader:
            config_dict = json.load(reader)
            log_info("Connect to mysql %s with user %s", config_dict["host"], config_dict["user"])
            conn = pymysql.connect(**config_dict, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
            cursor = conn.cursor()
            if limit is None:
                log_info("Exec sql and fetchall: %s", sql)
                cursor.execute(sql)
                rows = cursor.fetchall()
            else:
                rows = []
                limit_sql = sql
                if "order by" not in sql.lower():
                    limit_sql += " ORDER BY " + limit[0]
                offset = 0
                limit_count = limit[1]
                log_info("Sql add limit: %s, limit count %s", limit_sql, limit_count)
                while True:
                    current_sql = "%s limit %s, %s" % (limit_sql, offset, limit_count)
                    cursor.execute(current_sql)
                    # print(current_sql)
                    current_rows = cursor.fetchall()
                    rows += current_rows
                    if len(current_rows) < limit_count:
                        break
                    offset += limit_count
                    log_info("Current offset: %s", offset)
            log_info("Exec finish, rows count %s", len(rows))
            cursor.close()
            conn.close()
            return rows

    def generate_matrix_from_sql(self,
                                 sql,
                                 name_dict,
                                 date_find,
                                 code_find,
                                 abbr):

        shape = (self.meta.di_size, self.meta.ii_size)
        default = nan
        dtype = np.float64
        array_dict = {}

        for name in name_dict.keys():
            array_dict[name] = np.full(shape, default, dtype)

        for row in self.exec_sql_fetchall(sql):
            trading_day = int(row["TradingDay"])
            code = row["WindCode"]
            if date_find and trading_day not in self.meta.offset_di_mapping:
                continue
            if code_find and code not in self.meta.ii_mapping:
                continue
            di = self.meta.offset_di_mapping[trading_day]
            ii = self.meta.ii_mapping[code]
            for name in name_dict.keys():
                array_dict[name][di][ii] = row[name]

        for name, array in array_dict.items():
            data_name = abbr + "." + name.lower()
            self.write_data(data_name, array)

    def get_column_names(self, db_name, table_name, ignore_columns):
        sql = """
                      SELECT column_name AS column_name, column_type AS column_type
                      FROM information_schema.columns
                      WHERE table_schema='%s' AND table_name = '%s' 
                      """ % (db_name, table_name)

        name_dict = {}
        for row in self.exec_sql_fetchall(sql):
            if ignore_columns is not None and row["column_name"] in ignore_columns:
                continue
            if "datetime" in row["column_type"]:
                continue
            if "decimal" not in row["column_type"]:
                continue
                # abort("Find invalid type: %s", row)
            name_dict[row["column_name"].lower()] = row["column_name"] + " AS " + row["column_name"].lower()
        log_info("Column name dict: %s", name_dict)
        return name_dict

    def generate_matrix_from_table(self,
                                   db_name,
                                   table_name,
                                   date_name,
                                   date_find,
                                   code_name,
                                   code_find,
                                   abbr,
                                   ignore_columns=None):
        log_info("Generate table as matrix: %s.%s which use config %s, abbr %s, date name %s, code name %s, ignore columns %s",
                 db_name, table_name, self.mysql_config, abbr, date_name, code_name, ignore_columns)

        append_ignore_column_set = {date_name, code_name}
        if ignore_columns is None:
            ignore_columns = append_ignore_column_set
        else:
            ignore_columns = ignore_columns.union(append_ignore_column_set)

        name_dict = self.get_column_names(db_name, table_name, ignore_columns)

        sql = """
            SELECT %s AS TradingDay,%s AS WindCode,%s 
            FROM %s.%s
            WHERE %s BETWEEN '%s' AND '%s'
            """ % (date_name, code_name, ",".join(name_dict.values()), db_name, table_name, date_name, self.meta.begin_trading_day, self.meta.end_trading_day)

        self.generate_matrix_from_sql(sql, name_dict, date_find, code_find, abbr)

    def generate_matrix_with_name_dict(self,
                                       db_name,
                                       table_name,
                                       name_dict,
                                       date_name,
                                       date_find,
                                       code_name,
                                       code_find,
                                       abbr):

        new_name_dict = name_dict.copy()
        for name in name_dict.keys():
            new_name_dict[name] += " AS " + name

        sql = """
            SELECT %s AS TradingDay,%s AS WindCode,%s 
            FROM %s.%s 
            WHERE %s BETWEEN '%s' AND '%s'
            """ % (date_name, code_name, ",".join(new_name_dict.values()), db_name, table_name, date_name, self.meta.begin_trading_day, self.meta.end_trading_day)

        self.generate_matrix_from_sql(sql, new_name_dict, date_find, code_find, abbr)
