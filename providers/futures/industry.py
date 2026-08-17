# 期货品种行业分类 provider, 不连 MSSQL: 读 providers/futures/industries.csv
# (code, industry_l1, sector; 由 AlphaJrx 包 meta/51_industries.csv +
#  operators/neutralize.py 的 DEFAULT_CTA_SECTOR_MAP 合并而来, 2026-08-15)
# 产出 (int64 di×ii 逐日平铺, 形态同 static.pi):
#   ind.l1      细行业 (industry_l1) enum id, 未收录品种 -1
#   ind.sector  粗行业 (CTA sector) enum id, 未收录品种 -1
# enum 落 meta/enum/Enum_industry_l1.csv / Enum_sector.csv (id 只增不改)
# 注意: 静态表, 生产 do_generate 目录存在即跳过; 表变更或缓存延伸后需
#   清理 $XQSIM_DATA_HOME/futures/cc/Industry 后重跑本文件重建
import os

import numpy as np
import pandas as pd

from mssql_provider import MssqlProvider
from futures_common import FUTURES_CC_DIR, SLOTS_SIZE, load_or_extend_member_enum
from xqsim.xqsim_run import builder_run

INDUSTRY_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "industries.csv")


class Provider(MssqlProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.dir_name = "Industry"
        self.abbr = "ind"

    def generate(self):
        table = pd.read_csv(self.cfg.get("industry_csv", INDUSTRY_CSV), dtype=str)
        enum_dir = os.path.join(self.meta.meta_dir, "meta", "enum")
        l1_map = load_or_extend_member_enum(
            os.path.join(enum_dir, "Enum_industry_l1.csv"), table["industry_l1"].dropna().tolist())
        sector_map = load_or_extend_member_enum(
            os.path.join(enum_dir, "Enum_sector.csv"), table["sector"].dropna().tolist())

        l1_buffer = np.full((self.meta.di_size, self.meta.ii_size), -1, np.int64)
        sector_buffer = np.full((self.meta.di_size, self.meta.ii_size), -1, np.int64)
        for _, row in table.iterrows():
            pi = self.get_pi(str(row["code"]))
            if pi is None:
                continue
            slots = slice(pi * SLOTS_SIZE, (pi + 1) * SLOTS_SIZE)
            l1_buffer[:, slots] = l1_map[str(row["industry_l1"])]
            sector_buffer[:, slots] = sector_map[str(row["sector"])]

        self.write_data("%s.l1" % self.abbr, l1_buffer)
        self.write_data("%s.sector" % self.abbr, sector_buffer)


def main():
    builder_run(meta_dir=FUTURES_CC_DIR, begin_date="20160104", end_date="TODAY",
                output_cache_dir=FUTURES_CC_DIR, index_category="FUTURES", data_dir="")


if __name__ == '__main__':
    main()
