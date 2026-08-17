# 期货合约信息 provider, 移植自 ldcta provider/futures_instrument_info.py。
# 数据源: wind.dbo.CFUTURESCONTPRO (合约乘数 / 最小跳动)
# 产出 (float64 di×ii):
#   static.multiply   合约乘数
#   static.ticksize   最小变动价位
# 说明:
#   - ldcta 按 di×ii 逐日重复存储, 移植保留该形态 (xqsim 缓存以 di 为主轴,
#     静态压缩是格式层议题, 不在本次拆分范围);
#   - CZCE 三位年份码的换算依赖交易日, 与 ldcta 一致按 di 逐日换算;
#   - 末尾按主力映射把主力合约的乘数/跳动拷贝进 48 号槽 (与 ldcta 一致)。
import re

import numpy as np
from numpy import nan

from DataProviderMssql import MssqlProvider
from DataProviderFuturesCommon import FUTURES_CC_DIR, convert_to_standard_code, SLOTS_SIZE, HOT_SLOT
from DataProviderHotBuilder import build_hot_map
from xqsim.xqsim_run import builder_run

CONTPRO_SQL = "SELECT S_INFO_WINDCODE, S_INFO_PUNIT, S_INFO_MFPRICE FROM wind.dbo.CFUTURESCONTPRO"


class Provider(MssqlProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.dir_name = "InstrumentInfo"
        self.abbr = "static"

    def generate(self):
        windcode_dict: dict[str, tuple[float, float]] = {}
        for row in self.exec_sql_fetchall(CONTPRO_SQL):
            if row["S_INFO_PUNIT"] is None or row["S_INFO_MFPRICE"] is None:
                continue
            multiply = float(row["S_INFO_PUNIT"])
            match = re.findall(r"\d+\.?\d*", str(row["S_INFO_MFPRICE"]))
            if not match:
                continue
            windcode_dict[str(row["S_INFO_WINDCODE"])] = (multiply, float(match[0]))

        shape = (self.meta.di_size, self.meta.ii_size)
        multiply_buffer = np.full(shape, nan, np.float64)
        ticksize_buffer = np.full(shape, nan, np.float64)

        for di in range(self.meta.di_size):
            trading_day = str(self.meta.date_index[self.meta.begin_di + di])
            for windcode, (multiply, ticksize) in windcode_dict.items():
                code = convert_to_standard_code(windcode, trading_day)
                if code is None:
                    continue
                ii = self.get_ii(code)
                if ii is None or self.listed_code(di, ii) != code:
                    continue
                multiply_buffer[di][ii] = multiply
                ticksize_buffer[di][ii] = ticksize

        # 主力合约拷贝进 48 号槽
        hot_map = build_hot_map(self.fetch_oi_rows(), self.meta)
        for di, product_hot in hot_map.items():
            for pi, (hot_ii, _) in product_hot.items():
                multiply_buffer[di][pi * SLOTS_SIZE + HOT_SLOT] = multiply_buffer[di][hot_ii]
                ticksize_buffer[di][pi * SLOTS_SIZE + HOT_SLOT] = ticksize_buffer[di][hot_ii]

        self.write_data("%s.multiply" % self.abbr, multiply_buffer)
        self.write_data("%s.ticksize" % self.abbr, ticksize_buffer)


def main():
    builder_run(meta_dir=FUTURES_CC_DIR, begin_date="TODAY-5", end_date="TODAY",
                output_cache_dir=FUTURES_CC_DIR, index_category="FUTURES", data_dir="")


if __name__ == '__main__':
    main()
