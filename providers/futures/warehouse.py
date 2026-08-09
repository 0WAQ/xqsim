# 期货仓单 provider, 移植自 ldcta provider/futures_warehouse.py。
# 数据源: wind.dbo.CFUTURESWAREHOUSESTOCKS (WAREHOUSE_NAME=N'总计', 品种级日度仓单)
# 产出 (pi 维 di×80 原生存储, 文件名 M80, 见 MssqlProvider.write_pi_data):
#   wh.deliverable / wh.on_warrant / wh.available_warehouse /
#   wh.in / wh.out / wh.cancelled_warrants / wh.effective_forecast
# 语义 (与 ldcta 一致): 有行的日子字段为 null 时取上一日值; 无行的日子保持 NaN。
# 与 ldcta 的差异: 未收录品种靠 get_pi 查不到自动跳过,
# 不再硬编码 LR/SC/NR/LU/BC 剔除名单。
import numpy as np
from numpy import nan

from mssql_provider import MssqlProvider
from futures_common import convert_product, SLOTS_SIZE
from xqsim.xqsim_run import builder_run

WAREHOUSE_SQL = """\
    SELECT S_INFO_CODE, ANN_DATE, DELIVERABLE_W, ON_WARRANT_W, AVAILABLE_WAREHOUSE_W,
        WAREHOUSE_IN, WAREHOUSE_OUT, CANCELLED_WARRANTS, EFFECTIVE_FORECAST
    FROM wind.dbo.CFUTURESWAREHOUSESTOCKS
    WHERE WAREHOUSE_NAME = N'总计' AND ANN_DATE BETWEEN '%s' AND '%s'
    ORDER BY ANN_DATE, S_INFO_CODE
"""

FIELD_TAGS = {
    "DELIVERABLE_W": "wh.deliverable",
    "ON_WARRANT_W": "wh.on_warrant",
    "AVAILABLE_WAREHOUSE_W": "wh.available_warehouse",
    "WAREHOUSE_IN": "wh.in",
    "WAREHOUSE_OUT": "wh.out",
    "CANCELLED_WARRANTS": "wh.cancelled_warrants",
    "EFFECTIVE_FORECAST": "wh.effective_forecast",
}


class Provider(MssqlProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.dir_name = "Warehouse"

    def generate(self):
        pi_size = self.meta.ii_size // SLOTS_SIZE
        buffer_dict = {col: np.full((self.meta.di_size, pi_size), nan, np.float64)
                       for col in FIELD_TAGS}

        sql = WAREHOUSE_SQL % (self.meta.begin_trading_day, self.meta.end_trading_day)
        for row in self.exec_sql_fetchall(sql):
            trading_day = int(str(row["ANN_DATE"]).replace("-", ""))
            if trading_day not in self.meta.offset_di_mapping:
                continue
            pi = self.get_pi(convert_product(str(row["S_INFO_CODE"])))
            if pi is None:
                continue
            di = self.meta.offset_di_mapping[trading_day]
            for col in FIELD_TAGS:
                value = row[col]
                if value is not None:
                    buffer_dict[col][di][pi] = float(value)
                elif di > 0:
                    # null 沿用上一天 (ldcta 同语义)
                    buffer_dict[col][di][pi] = buffer_dict[col][di - 1][pi]

        for col, tag in FIELD_TAGS.items():
            self.write_pi_data(tag, buffer_dict[col])


def main():
    builder_run(meta_dir="./data/futures/cc", begin_date="TODAY-5", end_date="TODAY",
                output_cache_dir="./data/futures/cc_update", index_category="FUTURES")


if __name__ == '__main__':
    main()
