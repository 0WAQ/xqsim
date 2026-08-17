from static_provider import *
from stocks_common import STOCKS_CC_DIR, STOCKS_UPDATE_DIR
from xqsim.xqsim_run import builder_run


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.ignore_column_set = {"OBJECT_ID", "OPDATE", "OPMODE", "COPDATE", "MOPDATE"}.union(self.cfg.get("ignore_columns", set()))
        self.db_name = "wind"

        self.table_name = self.cfg.get("table", self.id)
        self.abbr = self.cfg.get("abbr", self.table_name)
        self.date_find = self.cfg.get("date_find", True)
        self.code_find = self.cfg.get("code_find", True)
        log_info("Wind common: mysql config %s, table %s, abbr %s, date find %s, code find %s",
                 self.mysql_config, self.table_name, self.abbr, self.date_find, self.code_find)

    def generate(self):
        self.generate_matrix_from_table(db_name=self.db_name,
                                        table_name=self.id,
                                        date_name="TRADE_DT",
                                        date_find=self.date_find,
                                        code_name="S_INFO_WINDCODE",
                                        code_find=self.code_find,
                                        abbr=self.abbr,
                                        ignore_columns=self.ignore_column_set)


def main():
    builder_run(meta_dir=STOCKS_CC_DIR, begin_date=20180102, end_date=20180131, output_cache_dir=STOCKS_UPDATE_DIR)


if __name__ == '__main__':
    main()
