# 期货日行情 provider, 移植自 ldcta provider/futures_kdata.py。
# 数据源: wind.dbo.CCOMMODITYFUTURESEODPRICES (FS_INFO_TYPE=2 商品期货)
# 语义 (与 ldcta 一致):
#   - preclose = 本合约前一有效报价日的收盘 (跨合约不衔接)
#   - returns: 有 preclose 时 close/preclose-1; 首个有效报价日 close/open-1
#   - 停牌/缺报价日 (在挂牌窗口内且此前有报价) 前填: OHLC=昨收, volume/amount=0,
#     settle/position 沿用昨值, returns=0
#   - amount 除以 100 (ldcta 原样)
#   - 最后按 hot_builder 的主力映射把主力合约数据拷贝进 48 号槽
from mssql_provider import MssqlProvider
from futures_common import convert_to_standard_code, SLOTS_SIZE, HOT_SLOT
from hot_builder import build_hot_map
from xqsim.xqsim_run import builder_run
import xqsim.common_utils as common_utils
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


class KData(object):
    def __init__(self):
        self.open = nan
        self.high = nan
        self.low = nan
        self.close = nan
        self.settle = nan
        self.volume = nan
        self.amount = nan
        self.position = nan

    def is_valid(self):
        return not (np.isnan(self.open) or np.isnan(self.high) or np.isnan(self.low)
                    or np.isnan(self.close) or np.isnan(self.volume) or np.isnan(self.amount))


class Provider(MssqlProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.abbr = "k"

    def generate(self):
        sql = KDATA_SQL % (self.meta.begin_trading_day, self.meta.end_trading_day)

        # code -> {offset_di: KData}; (trading_day, code, oi) 供主力判定
        kdata_dict: dict[str, dict[int, KData]] = {}
        oi_rows = []
        for row in self.exec_sql_fetchall(sql):
            trading_day = int(str(row["TRADE_DT"]).replace("-", ""))
            if trading_day not in self.meta.offset_di_mapping:
                continue
            code = convert_to_standard_code(str(row["S_INFO_WINDCODE"]), str(trading_day))
            if code is None:
                continue
            di = self.meta.offset_di_mapping[trading_day]

            kdata = KData()
            for attr, col in (("open", "S_DQ_OPEN"), ("high", "S_DQ_HIGH"), ("low", "S_DQ_LOW"),
                              ("close", "S_DQ_CLOSE"), ("settle", "S_DQ_SETTLE"),
                              ("volume", "S_DQ_VOLUME"), ("position", "S_DQ_OI")):
                if row[col] is not None:
                    setattr(kdata, attr, float(row[col]))
            if row["S_DQ_AMOUNT"] is not None:
                kdata.amount = float(row["S_DQ_AMOUNT"]) / 100.0
            kdata_dict.setdefault(code, {})[di] = kdata
            oi_rows.append((trading_day, code, kdata.position if not np.isnan(kdata.position) else 0.0))

        shape = (self.meta.di_size, self.meta.ii_size)
        buffer_dict = {name: np.full(shape, nan, np.float64)
                       for name in ("open", "high", "low", "close", "volume",
                                    "amount", "settle", "position", "preclose", "returns")}

        for code, day_map in kdata_dict.items():
            ii = self.get_ii(code)
            if ii is None:
                continue
            prev: KData | None = None
            for di in range(self.meta.di_size):
                # 只填挂牌窗口内的槽 (槽位复用: 同 ii 不同时段是不同合约)
                if self.listed_code(di, ii) != code:
                    continue
                kdata = day_map.get(di)
                if kdata is not None and kdata.is_valid():
                    preclose = prev.close if prev is not None else nan
                    if not np.isnan(preclose) and preclose != 0 and not np.isnan(kdata.close):
                        returns = kdata.close / preclose - 1
                    elif not np.isnan(kdata.open) and kdata.open != 0 and not np.isnan(kdata.close):
                        returns = kdata.close / kdata.open - 1
                    else:
                        returns = 0.0
                    buffer_dict["open"][di][ii] = kdata.open
                    buffer_dict["high"][di][ii] = kdata.high
                    buffer_dict["low"][di][ii] = kdata.low
                    buffer_dict["close"][di][ii] = kdata.close
                    buffer_dict["volume"][di][ii] = kdata.volume
                    buffer_dict["amount"][di][ii] = kdata.amount
                    buffer_dict["settle"][di][ii] = kdata.settle
                    buffer_dict["position"][di][ii] = kdata.position
                    buffer_dict["preclose"][di][ii] = preclose
                    buffer_dict["returns"][di][ii] = returns
                    prev = kdata
                elif prev is not None:
                    # 停牌日前填: OHLC=昨收, 无量, returns=0
                    buffer_dict["open"][di][ii] = prev.close
                    buffer_dict["high"][di][ii] = prev.close
                    buffer_dict["low"][di][ii] = prev.close
                    buffer_dict["close"][di][ii] = prev.close
                    buffer_dict["volume"][di][ii] = 0.0
                    buffer_dict["amount"][di][ii] = 0.0
                    buffer_dict["settle"][di][ii] = prev.settle
                    buffer_dict["position"][di][ii] = prev.position
                    buffer_dict["preclose"][di][ii] = prev.close
                    buffer_dict["returns"][di][ii] = 0.0

        # 主力合约拷贝进 48 号槽
        hot_map = build_hot_map(oi_rows, self.meta)
        for di, product_hot in hot_map.items():
            for pi, (hot_ii, _) in product_hot.items():
                for buffer in buffer_dict.values():
                    buffer[di][pi * SLOTS_SIZE + HOT_SLOT] = buffer[di][hot_ii]

        for name, array in buffer_dict.items():
            self.write_data("%s.%s" % (self.abbr, name), array)


def main():
    builder_run(meta_dir="./data/futures/cc", begin_date="TODAY-5", end_date="TODAY",
                output_cache_dir="./data/futures/cc_update", index_category="FUTURES")


if __name__ == '__main__':
    main()
