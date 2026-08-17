from DataProviderStatic import *
from DataProviderStocksCommon import STOCKS_CC_DIR, STOCKS_UPDATE_DIR
from xqsim.xqsim_run import builder_run
import numpy as np



class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)

    def generate(self):
        name_dict = {"level1": "LEVEL1",
                     "level2": "LEVEL2",
                     "level3": "LEVEL3"}

        for industry in ["wind"]:
            self.generate_matrix_with_name_dict(db_name="meta",
                                                table_name="Industry_" + industry,
                                                name_dict=name_dict,
                                                date_name="TradingDay",
                                                date_find=False,
                                                code_name="WindCode",
                                                code_find=True,
                                                abbr="ind." + industry)


def main():
    builder_run(meta_dir=STOCKS_CC_DIR, begin_date=20200701, end_date=20200731, output_cache_dir=STOCKS_UPDATE_DIR)


if __name__ == '__main__':
    main()
