# 期货会员成交/持仓排名 provider (rank cube)。
# 数据源: wind.dbo.CCOMMODITYFUTURESPOSITIONS (交易所盘后公布的会员排名)
#
# 布局: (di, ri, ii) 三维 cube, 骑在缓存格式现成的 ti 轴机制上 (ti_size=20,
# 语义借道: 这里是 rank 不是时间)。ri ∈ [0, 20) 对应 rank 1~20; 只收录
# 2016 年后的 top20 时代数据, 早年深榜 (>20 名) 丢弃。
#
# 产出 (目录 PositionsRank, 每字段 (di, 20, ii)):
#   rk.vol / rk.vol_chg / rk.vol_member        成交量榜: 成交量(手) / 较上日增减 / 会员 enum id
#   rk.long_pos / rk.long_pos_chg / rk.long_pos_member    持买单榜: 持仓(手) / 增减 / 会员 id
#   rk.short_pos / rk.short_pos_chg / rk.short_pos_member 持卖单榜: 同上
# 说明:
#   - 三张榜同名次的会员通常不同, member 字段按榜分开存
#   - 数值 float64 缺名次 NaN; member int64 缺名次 -1 (同 hot.ii 惯例)
#   - 无榜日期保持 NaN/-1, 不前填 (排名只在交易日盘后发布)
#   - 会员身份: compcode 优先, 缺失回退 NAME::会员名 (futures_common.member_key);
#     enum 落 meta/enum/Enum_member.csv, id 只增不改
#   - 末尾按主力映射把主力合约的整条 rank 切片拷进 48 号槽
#   - 非 CZCE/DCE/SHFE 的合约 (如 GFEX) 查不到 ii 自动跳过
from mssql_provider import MssqlProvider
from futures_common import (convert_to_standard_code, member_key,
                            load_or_extend_member_enum, SLOTS_SIZE, HOT_SLOT)
from hot_builder import build_hot_map
from xqsim.xqsim_run import builder_run
import os
import numpy as np
from numpy import nan

RANK_SIZE = 20

POSITIONS_SQL = """\
    SELECT S_INFO_WINDCODE, TRADE_DT, FS_INFO_TYPE, FS_INFO_RANK,
        FS_INFO_MEMBERNAME, S_INFO_COMPCODE,
        FS_INFO_POSITIONSNUM, S_OI_POSITIONSNUMC
    FROM wind.dbo.CCOMMODITYFUTURESPOSITIONS
    WHERE TRADE_DT BETWEEN '%s' AND '%s'
"""

# type -> (数值字段, chg 字段, member 字段)
TYPE_FIELDS = {
    1: ("vol", "vol_chg", "vol_member"),
    2: ("long_pos", "long_pos_chg", "long_pos_member"),
    3: ("short_pos", "short_pos_chg", "short_pos_member"),
}


class Provider(MssqlProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.abbr = "rk"

    def generate(self):
        sql = POSITIONS_SQL % (self.meta.begin_trading_day, self.meta.end_trading_day)

        shape = (self.meta.di_size, RANK_SIZE, self.meta.ii_size)
        num_buffers = {name: np.full(shape, nan, np.float64)
                       for name in ("vol", "vol_chg", "long_pos", "long_pos_chg",
                                    "short_pos", "short_pos_chg")}
        member_buffers = {name: np.full(shape, -1, np.int64)
                          for name in ("vol_member", "long_pos_member", "short_pos_member")}

        enum_path = os.path.join(self.meta.meta_dir, "meta", "enum", "Enum_member.csv")
        member_enum = load_or_extend_member_enum(enum_path, [])

        pending_keys = set()
        rows = []
        for row in self.exec_sql_fetchall(sql):
            rank = int(row["FS_INFO_RANK"])
            if rank < 1 or rank > RANK_SIZE:
                continue  # 早年深榜 (>20 名) 丢弃
            trading_day = int(str(row["TRADE_DT"]).replace("-", ""))
            if trading_day not in self.meta.offset_di_mapping:
                continue
            code = convert_to_standard_code(str(row["S_INFO_WINDCODE"]), str(trading_day))
            if code is None:
                continue
            ii = self.get_ii(code)
            if ii is None:
                continue
            di = self.meta.offset_di_mapping[trading_day]
            # 只填挂牌窗口内的槽 (槽位复用: 同 ii 不同时段是不同合约)
            if self.listed_code(di, ii) != code:
                continue
            key = member_key(row["S_INFO_COMPCODE"], row["FS_INFO_MEMBERNAME"])
            if key is not None and key not in member_enum:
                pending_keys.add(key)
            rows.append((di, rank - 1, ii, int(row["FS_INFO_TYPE"]), key,
                         row["FS_INFO_POSITIONSNUM"], row["S_OI_POSITIONSNUMC"]))

        # 新会员追加进 enum (id 只增不改)
        if pending_keys:
            member_enum = load_or_extend_member_enum(enum_path, pending_keys)

        for di, ri, ii, info_type, key, num, chg in rows:
            num_name, chg_name, member_name = TYPE_FIELDS[info_type]
            if num is not None:
                num_buffers[num_name][di][ri][ii] = float(num)
            if chg is not None:
                num_buffers[chg_name][di][ri][ii] = float(chg)
            if key is not None:
                member_buffers[member_name][di][ri][ii] = member_enum[key]

        buffer_dict = {**num_buffers, **member_buffers}

        # 主力合约拷贝进 48 号槽 (整条 rank 切片)
        hot_map = build_hot_map(self.fetch_oi_rows(), self.meta)
        for di, product_hot in hot_map.items():
            for pi, (hot_ii, _) in product_hot.items():
                for buffer in buffer_dict.values():
                    buffer[di][:, pi * SLOTS_SIZE + HOT_SLOT] = buffer[di][:, hot_ii]

        for name, array in buffer_dict.items():
            self.write_compress_data("%s.%s" % (self.abbr, name), array)


def main():
    builder_run(meta_dir="./data/futures/cc", begin_date="TODAY-5", end_date="TODAY",
                output_cache_dir="./data/futures/cc", index_category="FUTURES", data_dir="")


if __name__ == '__main__':
    main()
