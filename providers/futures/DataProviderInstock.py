# 期货交割库库存 provider, 移植自 ldcta provider/futures_instock.py。
# 数据源: wind.dbo.CFUTURESINSTOCK join Meta.dbo.CTAMap (中文名 -> 品种码)
# 产出 (pi 维 di×80 原生存储, 文件名 M80, 见 MssqlProvider.write_pi_data):
#   istk.instock        IN_STOCK
#   istk.avail_instock  AVAILABLE_IN_STOCK
# 语义 (与 ldcta 一致): 有行的日子字段为 null 时取上一日值; 无行的日子保持 NaN。
# 注意: 与 DataProviderWindCommodity.py 同源不同 join (CTAMap), 覆盖率低于后者, 两者都保留。
import numpy as np
from numpy import nan

from DataProviderMssql import MssqlProvider
from DataProviderFuturesCommon import FUTURES_CC_DIR, convert_product, SLOTS_SIZE
from xqsim.xqsim_run import builder_run

INSTOCK_SQL = """\
    SELECT b.ENAME, a.ANN_DATE, a.IN_STOCK, a.AVAILABLE_IN_STOCK
    FROM wind.dbo.CFUTURESINSTOCK a
    LEFT JOIN Meta.dbo.CTAMap b
        ON a.FS_INFO_SCNAME collate Chinese_PRC_CI_AS = b.CNAME collate Chinese_PRC_CI_AS
    WHERE a.ANN_DATE BETWEEN '%s' AND '%s'
    ORDER BY a.ANN_DATE
"""

FIELD_TAGS = {
    "IN_STOCK": "istk.instock",
    "AVAILABLE_IN_STOCK": "istk.avail_instock",
}


class Provider(MssqlProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.dir_name = "InStock"

    def generate(self):
        pi_size = self.meta.ii_size // SLOTS_SIZE
        buffer_dict = {col: np.full((self.meta.di_size, pi_size), nan, np.float64)
                       for col in FIELD_TAGS}

        sql = INSTOCK_SQL % (self.meta.begin_trading_day, self.meta.end_trading_day)
        for row in self.exec_sql_fetchall(sql):
            if row["ENAME"] is None:
                continue
            trading_day = int(str(row["ANN_DATE"]).replace("-", ""))
            if trading_day not in self.meta.offset_di_mapping:
                continue
            pi = self.get_pi(convert_product(str(row["ENAME"])))
            if pi is None:
                continue
            di = self.meta.offset_di_mapping[trading_day]
            for col in FIELD_TAGS:
                value = row[col]
                if value is not None:
                    buffer_dict[col][di][pi] = float(value)
                elif di > 0:
                    buffer_dict[col][di][pi] = buffer_dict[col][di - 1][pi]

        for col, tag in FIELD_TAGS.items():
            self.write_pi_data(tag, buffer_dict[col])


def main():
    builder_run(meta_dir=FUTURES_CC_DIR, begin_date="TODAY-5", end_date="TODAY",
                output_cache_dir=FUTURES_CC_DIR, index_category="FUTURES", data_dir="")


if __name__ == '__main__':
    main()
