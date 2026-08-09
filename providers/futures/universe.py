# 期货 universe provider, 移植自 ldcta provider/futures_universe.py (裁剪版)。
# 不连 MSSQL: 活跃标记直接由 meta.instrument_index (挂牌窗口) 推导。
# 产出:
#   uv.all     bool di×ii, 当天挂牌的真实合约槽 (不含 48 主力拷贝槽 / 49 指数槽)
#   static.pi  int32 di×ii, 槽位所属品种 id (= ii // 50), 全槽填充
# 裁剪: ldcta 的 universe.index/commodity/product 三个标签从未被使用
#   (index 槽十年无数据, commodity 恒 true), 不移植。
from mssql_provider import MssqlProvider
from futures_common import SLOTS_SIZE, HOT_SLOT
from xqsim.xqsim_run import builder_run
import numpy as np


class Provider(MssqlProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.dir_name = "Universe"
        self.abbr = "uv"

    def generate(self):
        all_buffer = np.full((self.meta.di_size, self.meta.ii_size), False, np.bool_)
        for di in range(self.meta.di_size):
            for ii in range(self.meta.ii_size):
                if ii % SLOTS_SIZE >= HOT_SLOT:
                    continue
                if self.listed_code(di, ii) != "":
                    all_buffer[di][ii] = True
        self.write_data("%s.all" % self.abbr, all_buffer)

        pi_buffer = np.tile(np.arange(self.meta.ii_size, dtype=np.int32) // SLOTS_SIZE,
                            (self.meta.di_size, 1))
        self.write_data("static.pi", pi_buffer)


def main():
    builder_run(meta_dir="./data/futures/cc", begin_date="TODAY-5", end_date="TODAY",
                output_cache_dir="./data/futures/cc_update", index_category="FUTURES")


if __name__ == '__main__':
    main()
