# 主力合约判定, 移植自 ldcta builder/futures_hot.py。
# 差异: 砍掉 MSSQL hot 表往返 (builder 写表 -> provider 读表), 改为内存计算,
# 结果直接供 kline.py (主力槽拷贝) 和 hot.py (hot.ii 标签) 使用。
#
# 判定规则 (与 ldcta 一致):
#   - 每日候选 = 当日有持仓报价的合约 + 昨日主力/次主力 (权重 0, 仅兜底)
#   - 主力不回退: 合约码小于昨日主力者不得成为主力
#   - 滞回: 现任主力持仓按 1.1 倍计 (新合约持仓须超旧主力 10% 才切换)
#   - 排序: 持仓量降序, 同量按合约码升序; 次主力 = 第二名 (只有一个合约时 = 主力)
# 已知差异: ldcta 用 MSSQL 历史 hot 表给窗口首日播种, 本实现从窗口首日开始
# 递推, 窗口边界一天的主力判定可能与 ldcta 不同 (日更场景建议带几天回看窗口)。
from futures_common import get_product, SLOTS_SIZE

# 晚籼稻, ldcta 中剔除, 保留
SKIP_PRODUCTS = {"LR"}


def build_hot_map(oi_rows, meta) -> dict[int, dict[int, tuple[int, int]]]:
    """
    oi_rows: [(trading_day:int, code:str, oi:float)], code 为标准合约码
    return: {offset_di: {pi: (hot_ii, next_hot_ii)}}
    """
    # day -> product -> [(oi, code)]
    day_product_quotes: dict[int, dict[str, list[tuple[float, str]]]] = {}
    for trading_day, code, oi in oi_rows:
        if trading_day not in meta.offset_di_mapping:
            continue
        product = get_product(code)
        if product in SKIP_PRODUCTS:
            continue
        di = meta.offset_di_mapping[trading_day]
        day_product_quotes.setdefault(di, {}).setdefault(product, []).append((oi, code))

    hot_map: dict[int, dict[int, tuple[int, int]]] = {}
    # product -> (prev_hot_code, prev_next_code)
    product_prev: dict[str, tuple[str | None, str | None]] = {}

    for di in sorted(day_product_quotes.keys()):
        abs_di = meta.begin_di + di
        for product, quotes in sorted(day_product_quotes[di].items()):
            prev_hot, prev_next = product_prev.get(product, (None, None))

            candidates: list[tuple[float, str]] = []
            for seed in (prev_hot, prev_next):
                if seed is not None:
                    candidates.append((0.0, seed))
            for oi, code in quotes:
                # 主力不回退
                if prev_hot is not None and code < prev_hot:
                    continue
                # 滞回: 现任主力持仓 1.1 倍计
                candidates.append((oi * 1.1 if code == prev_hot else oi, code))

            # 持仓量降序, 同量合约码升序
            candidates.sort(key=lambda x: (-x[0], x[1]))
            # 清理: 合约码小于当期主力的全部移除
            hot_code = candidates[0][1]
            candidates = [c for c in candidates if c[1] >= hot_code]
            next_code = candidates[1][1] if len(candidates) > 1 else hot_code
            product_prev[product] = (hot_code, next_code)

            hot_ii = meta.ii_mapping.get(hot_code)
            next_ii = meta.ii_mapping.get(next_code)
            if hot_ii is None or next_ii is None:
                continue
            # 报价落在合约挂牌窗口之外时该槽当天驻留的不是此合约, 丢弃
            if meta.instrument_index[abs_di][hot_ii] != hot_code:
                continue
            if meta.instrument_index[abs_di][next_ii] != next_code:
                next_ii = hot_ii
            hot_map.setdefault(di, {})[hot_ii // SLOTS_SIZE] = (hot_ii, next_ii)

    return hot_map
