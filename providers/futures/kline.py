# 期货日行情 provider, 移植自 ldcta provider/futures_kdata.py。
# 数据源: wind.dbo.CCOMMODITYFUTURESEODPRICES (FS_INFO_TYPE=2 商品期货)
#
# 语义以 ldcta 生产缓存 (QNCTACC2026MSSQL) 为准——它与 ldcta 当前代码已漂移
# (生产数据不是 is_valid 闸门 + OHLC=昨收 那套), 实证规则:
#   - 直通: wind 有行就写原值; open/high/low null -> NaN
#     (无成交日 wind 仍发布 close/settle, OHLC 为空)
#   - volume/amount/position null -> 0.0 (活跃槽内这三个字段从不为 NaN)
#   - amount 除以 100 (ldcta 原样)
#   - 前填: 段内 wind 完全无行的日子整行复制上一日 (含 OHLC, 上日为 NaN
#     则填 NaN), preclose=上一日 close, returns=0; 段首从未有行的日子保持 NaN
#   - preclose = 前一交易日的 close (段首为 NaN)
#   - returns: preclose 有效时 close/preclose-1; 段首 close/open-1;
#     open 也缺则 NaN
#   - 最后按 hot_builder 的主力映射把主力合约数据拷贝进 48 号槽
from mssql_provider import MssqlProvider
from futures_common import FUTURES_CC_DIR, convert_to_standard_code, SLOTS_SIZE, HOT_SLOT
from hot_builder import build_hot_map
from xqsim.xqsim_run import builder_run
import numpy as np
from numpy import nan

KDATA_SQL = """\
    SELECT S_INFO_WINDCODE, TRADE_DT,
        S_DQ_OPEN, S_DQ_HIGH, S_DQ_LOW, S_DQ_CLOSE,
        S_DQ_SETTLE, S_DQ_VOLUME, S_DQ_AMOUNT, S_DQ_OI
    FROM wind.dbo.CCOMMODITYFUTURESEODPRICES
    WHERE FS_INFO_TYPE = 2
        AND TRADE_DT BETWEEN '%s' AND '%s'
    ORDER BY TRADE_DT, S_INFO_WINDCODE
"""

FIELDS = ("open", "high", "low", "close", "volume", "amount",
          "settle", "position", "preclose", "returns")


class Provider(MssqlProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.abbr = "k"

    def generate(self):
        sql = KDATA_SQL % (self.meta.begin_trading_day, self.meta.end_trading_day)

        shape = (self.meta.di_size, self.meta.ii_size)
        buffer_dict = {name: np.full(shape, nan, np.float64) for name in FIELDS}

        # code -> [offset_di, ...] (该合约在窗口内的驻留段), (trading_day, code, oi) 供主力判定
        code_days: dict[str, list[int]] = {}
        oi_rows = []
        for row in self.exec_sql_fetchall(sql):
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

            def f(col, zero_on_null=False):
                v = row[col]
                if v is None:
                    return 0.0 if zero_on_null else nan
                return float(v)

            buffer_dict["open"][di][ii] = f("S_DQ_OPEN")
            buffer_dict["high"][di][ii] = f("S_DQ_HIGH")
            buffer_dict["low"][di][ii] = f("S_DQ_LOW")
            buffer_dict["close"][di][ii] = f("S_DQ_CLOSE")
            buffer_dict["settle"][di][ii] = f("S_DQ_SETTLE")
            buffer_dict["volume"][di][ii] = f("S_DQ_VOLUME", zero_on_null=True)
            buffer_dict["amount"][di][ii] = f("S_DQ_AMOUNT", zero_on_null=True) / 100.0
            buffer_dict["position"][di][ii] = f("S_DQ_OI", zero_on_null=True)
            code_days.setdefault(code, []).append(di)
            oi_rows.append((trading_day, code, buffer_dict["position"][di][ii]))

        # preclose / returns 派生 + 无行前填 (生产语义, 实证自 QNCTACC2026MSSQL):
        # 段内无 wind 行的日子整行复制上一日 (OHLC 也照抄, 上日是 NaN 则填 NaN),
        # preclose=上一日 close, returns=0; 段首 (从未有行) 保持 NaN
        for code, days in code_days.items():
            ii = self.get_ii(code)
            days.sort()
            row_set = set(days)
            prev_close = nan
            di = days[0]
            while di < self.meta.di_size and self.listed_code(di, ii) == code:
                if di in row_set:
                    close = buffer_dict["close"][di][ii]
                    open_ = buffer_dict["open"][di][ii]
                    buffer_dict["preclose"][di][ii] = prev_close
                    if not np.isnan(prev_close) and prev_close != 0 and not np.isnan(close):
                        buffer_dict["returns"][di][ii] = close / prev_close - 1
                    elif not np.isnan(open_) and open_ != 0 and not np.isnan(close):
                        buffer_dict["returns"][di][ii] = close / open_ - 1
                    if not np.isnan(close):
                        prev_close = close
                elif not np.isnan(prev_close):
                    for name in ("open", "high", "low", "close", "volume",
                                 "amount", "settle", "position"):
                        buffer_dict[name][di][ii] = buffer_dict[name][di - 1][ii]
                    buffer_dict["preclose"][di][ii] = prev_close
                    buffer_dict["returns"][di][ii] = 0.0
                di += 1

        # 主力合约拷贝进 48 号槽
        hot_map = build_hot_map(oi_rows, self.meta)
        for di, product_hot in hot_map.items():
            for pi, (hot_ii, _) in product_hot.items():
                for buffer in buffer_dict.values():
                    buffer[di][pi * SLOTS_SIZE + HOT_SLOT] = buffer[di][hot_ii]

        for name, array in buffer_dict.items():
            self.write_data("%s.%s" % (self.abbr, name), array)


def main():
    builder_run(meta_dir=FUTURES_CC_DIR, begin_date="TODAY-5", end_date="TODAY",
                output_cache_dir=FUTURES_CC_DIR, index_category="FUTURES", data_dir="")


if __name__ == '__main__':
    main()
