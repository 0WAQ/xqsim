# wind 商品库存 provider, 移植自 ldcta provider/futures_wind_commodity_data.py。
# 数据源: wind.dbo.CFUTURESINSTOCK join wind.dbo.CFUTURESCONTPRO (中文名 -> 品种码)
# 产出 (pi 维 di×80 原生存储, 文件名 M80, 见 MssqlProvider.write_pi_data):
#   wc.in_stock / wc.in_stock_total / wc.available_in_stock
# 语义 (与 ldcta 一致): 无逐日前填, null -> NaN。
# 与 ldcta 的差异: **修复三个 save_dat 同写 in_stock_buffer 的 bug**
# (ldcta 生产缓存中三个文件内容完全相同, 已实证); 未收录品种靠 get_pi 自动跳过。
import numpy as np
from numpy import nan

from DataProviderMssql import MssqlProvider
from DataProviderFuturesCommon import FUTURES_CC_DIR, convert_product, SLOTS_SIZE
from xqsim.xqsim_run import builder_run

WIND_COMMODITY_SQL = """\
    SELECT DISTINCT ANN_DATE, FS_INFO_SCNAME, S_INFO_CODE, S_INFO_EXNAME,
        IN_STOCK, IN_STOCK_TOTAL, AVAILABLE_IN_STOCK
    FROM wind.dbo.CFUTURESINSTOCK aa
    LEFT JOIN wind.dbo.CFUTURESCONTPRO bb
        ON aa.FS_INFO_SCNAME = bb.S_INFO_NAME
    WHERE ANN_DATE BETWEEN '%s' AND '%s'
"""

FIELD_TAGS = {
    "IN_STOCK": "wc.in_stock",
    "IN_STOCK_TOTAL": "wc.in_stock_total",
    "AVAILABLE_IN_STOCK": "wc.available_in_stock",
}


class Provider(MssqlProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.dir_name = "WindCommodity"

    def generate(self):
        pi_size = self.meta.ii_size // SLOTS_SIZE
        buffer_dict = {col: np.full((self.meta.di_size, pi_size), nan, np.float64)
                       for col in FIELD_TAGS}

        sql = WIND_COMMODITY_SQL % (self.meta.begin_trading_day, self.meta.end_trading_day)
        for row in self.exec_sql_fetchall(sql):
            trading_day = int(str(row["ANN_DATE"]).replace("-", ""))
            if trading_day not in self.meta.offset_di_mapping:
                continue
            exchange = str(row["S_INFO_EXNAME"])
            old_product = str(row["S_INFO_CODE"])
            if exchange != "CZCE":
                old_product = old_product.lower()
            pi = self.get_pi(convert_product(old_product))
            if pi is None:
                continue
            di = self.meta.offset_di_mapping[trading_day]
            for col in FIELD_TAGS:
                value = row[col]
                if value is not None:
                    buffer_dict[col][di][pi] = float(value)

        for col, tag in FIELD_TAGS.items():
            self.write_pi_data(tag, buffer_dict[col])


def main():
    builder_run(meta_dir=FUTURES_CC_DIR, begin_date="TODAY-5", end_date="TODAY",
                output_cache_dir=FUTURES_CC_DIR, index_category="FUTURES", data_dir="")


if __name__ == '__main__':
    main()
