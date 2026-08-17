# 期货主力映射 provider, 移植自 ldcta provider/futures_hot.py。
# 产出 (int64 di×ii, 默认 -1; xqsim 缓存格式只支持 float64/int64/bool):
#   hot.ii       每个挂牌合约槽当天所属品种的主力合约 ii
#   hot.ii_next  次主力合约 ii
# 用法: 判定合约槽 ii 当天是否主力 -> ii == hot.ii[di][ii]
# 与 ldcta 的差异:
#   1. 修复 ldcta 的顺序 bug (set_value 用了上轮循环残留的 hot_ii, hot.M.b 错位);
#   2. 冗余的 hotc/hot 两个 bool 阵不移植 (hot.ii 完全覆盖其语义);
#   3. 主力判定由 hot_builder 内存计算 (持仓量来自 wind 行情表),
#      不再读 MSSQL hot 中间表。
from mssql_provider import MssqlProvider
from futures_common import FUTURES_CC_DIR, SLOTS_SIZE, HOT_SLOT
from hot_builder import build_hot_map
from xqsim.xqsim_run import builder_run
import numpy as np


class Provider(MssqlProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.dir_name = "Hot"
        self.abbr = "hot"

    def generate(self):
        hot_map = build_hot_map(self.fetch_oi_rows(), self.meta)

        hot_ii_buffer = np.full((self.meta.di_size, self.meta.ii_size), -1, np.int64)
        hot_ii_next_buffer = np.full((self.meta.di_size, self.meta.ii_size), -1, np.int64)
        for di in range(self.meta.di_size):
            if di not in hot_map:
                continue
            for ii in range(self.meta.ii_size):
                if ii % SLOTS_SIZE >= HOT_SLOT:
                    continue
                if self.listed_code(di, ii) == "":
                    continue
                hot_ii, hot_ii_next = hot_map[di].get(ii // SLOTS_SIZE, (-1, -1))
                hot_ii_buffer[di][ii] = hot_ii
                hot_ii_next_buffer[di][ii] = hot_ii_next

        self.write_data("%s.ii" % self.abbr, hot_ii_buffer)
        self.write_data("%s.ii_next" % self.abbr, hot_ii_next_buffer)


def main():
    builder_run(meta_dir=FUTURES_CC_DIR, begin_date="TODAY-5", end_date="TODAY",
                output_cache_dir=FUTURES_CC_DIR, index_category="FUTURES", data_dir="")


if __name__ == '__main__':
    main()
