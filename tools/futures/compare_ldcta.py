# 比对 xqsim 期货缓存与 ldcta 原始缓存 (QNCTACC2026MSSQL) 的一致性。
#
# 前提: 已跑过 meta_updater.py + config_production.yml (build), 产出在
#   data/futures/cc_update。两侧日历同源 (CC_Meta_TradingDays_Wind),
#   按交易日对齐行; 列 (ii) 布局因 pi/slot 分配规则一致而天然对齐。
#
# 用法 (repo 根目录):
#   uv run python tools/futures/compare_ldcta.py \
#       --ldcta /path/to/QNCTACC2026MSSQL \
#       --cache data/futures/cc_update \
#       --meta  data/futures/cc \
#       [--calendar /path/to/DateIndex.csv | /path/to/Dates.npy]
#
# 四个路径全部可指定, 适配在数据所在机器上直接跑:
#   --ldcta     旧版 (ldcta) 缓存根目录
#   --cache     新版 (xqsim) 缓存目录
#   --meta      新版 meta_dir (init_dr 加载缓存头需要)
#   --calendar  行对齐用的交易日历, 可选; 默认 <meta>/meta/index/DateIndex.csv,
#               也接受裸 int64 yyyymmdd 二进制 (如 cc_all 的 Dates.npy)
#
# 已知预期差异 (不算 bug):
#   - hot 相关: 窗口首日的主力判定可能与 ldcta 历史 hot 表不同 (播种差异),
#     逐日失配统计里看是否只集中在窗口开头;
#   - k.* 为 float64, ldcta 为 float32, 按 float32 精度比对。
import argparse
import os

import numpy as np

from xqsim.xqsim_run import init_dr

# xqsim tag -> (ldcta 目录, ldcta 文件名)
FIELD_MAP = {
    "k.open": ("KData", "KData.open_price.M.f.dat"),
    "k.high": ("KData", "KData.highest_price.M.f.dat"),
    "k.low": ("KData", "KData.lowest_price.M.f.dat"),
    "k.close": ("KData", "KData.close_price.M.f.dat"),
    "k.volume": ("KData", "KData.volume.M.f.dat"),
    "k.amount": ("KData", "KData.amount.M.f.dat"),
    "k.settle": ("KData", "KData.settlement_price.M.f.dat"),
    "k.position": ("KData", "KData.position.M.f.dat"),
    "k.preclose": ("KData", "KData.preclose.M.f.dat"),
    "k.returns": ("KData", "KData.returns.M.f.dat"),
    "uv.all": ("Universe", "Universe.all.M.b.dat"),
    "static.multiply": ("InstrumentInfo", "InstrumentInfo.multiply.M.f.dat"),
    "static.ticksize": ("InstrumentInfo", "InstrumentInfo.ticksize.M.f.dat"),
}

LDCTA_DTYPES = {"f": np.float32, "i": np.int32, "b": np.bool_}
LDCTA_MAX_INT = 2147483647
SLOTS_SIZE = 50
HOT_SLOT = 48


def load_calendar(path: str) -> np.ndarray:
    """交易日历: DateIndex.csv (第二列 yyyymmdd) 或裸 int64 二进制 (Dates.npy 格式)"""
    if path.endswith(".csv"):
        days = []
        with open(path) as reader:
            for line in reader.readlines()[1:]:
                days.append(int(line.split(",")[1]))
        return np.array(days, dtype=np.int64)
    return np.fromfile(path, dtype=np.int64)


def load_ldcta(file_path: str, calendar: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """返回 (行对应交易日数组, 矩阵)。裸 .dat, 行 = 交易日, 列 = ii (或 pi)。"""
    with open(os.path.join(os.path.dirname(file_path), ".meta")) as reader:
        start_day = int(reader.readline())
    fields = os.path.basename(file_path).split(".")
    dtype = LDCTA_DTYPES[fields[-2]]
    dimen = fields[-3]
    row_len = 4000 if dimen == "M" else int(dimen[1:])
    raw = np.fromfile(file_path, dtype=dtype)
    n_rows = raw.size // row_len
    start_idx = int(np.nonzero(calendar == start_day)[0][0])
    days = calendar[start_idx:start_idx + n_rows]
    return days, raw.reshape(n_rows, row_len)


def load_xqsim(dr, cache_dir: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """扫 xqsim 缓存目录, 返回 {tag: (行对应交易日数组, 矩阵)}"""
    result = {}
    for dir_path, _, file_names in os.walk(cache_dir):
        for file_name in file_names:
            elements = file_name.split(".")
            if len(elements) < 4:
                continue
            tag = ".".join(elements[:-3])
            if tag not in FIELD_MAP and not tag.startswith("hot."):
                continue
            data, header = dr.load_data_header_from_file(os.path.join(dir_path, file_name), total=True)
            begin_di = dr.meta.total_di_mapping[int(header.begin_trading_day)]
            end_di = dr.meta.total_di_mapping[int(header.end_trading_day)]
            days = np.array(dr.meta.total_date_index[begin_di:end_di + 1], dtype=np.int64)
            result[tag] = (days, np.asarray(data))
    return result


def compare_matrix(tag: str, mine: np.ndarray, theirs: np.ndarray) -> str:
    if mine.shape != theirs.shape:
        return "%-16s SHAPE MISMATCH %s vs %s" % (tag, mine.shape, theirs.shape)
    if mine.dtype == np.bool_ or theirs.dtype == np.bool_:
        mismatch = int((mine.astype(bool) != theirs.astype(bool)).sum())
        return "%-16s bool mismatch=%s / %s" % (tag, mismatch, mine.size)
    a = mine.astype(np.float32)
    b = theirs.astype(np.float32)
    both_nan = np.isnan(a) & np.isnan(b)
    same = (a == b) | both_nan
    n_mismatch = int((~same).sum())
    if n_mismatch:
        diff = np.abs(a - b)
        diff[np.isnan(diff)] = 0
        # 失配按行(交易日)统计, 方便识别 hot 窗口边界效应
        bad_rows = int((~same).any(axis=1).sum())
        return "%-16s mismatch=%s (days=%s), max abs diff=%.6g" % (
            tag, n_mismatch, bad_rows, diff.max())
    return "%-16s OK (%s cells)" % (tag, mine.size)


def compare_hot_ii(tag: str, mine: np.ndarray, theirs_m80: np.ndarray) -> str:
    """mine: di×ii (每个挂牌槽填所属品种主力 ii, 默认 -1);
    theirs: di×80 (每品种主力 ii, 空 = max_int)。逐品种比对。"""
    n_mismatch = 0
    n_compared = 0
    for pi in range(theirs_m80.shape[1]):
        their = theirs_m80[:, pi]
        seg = mine[:, pi * SLOTS_SIZE: pi * SLOTS_SIZE + HOT_SLOT]
        for col in range(seg.shape[1]):
            my = seg[:, col]
            mask = my != -1
            if not mask.any():
                continue
            n_compared += int(mask.sum())
            # ldcta 空缺(max_int) 而我方有值, 或值不等, 都算失配
            n_mismatch += int((my[mask] != their[mask]).sum())
    return "%-16s mismatch=%s / %s" % (tag, n_mismatch, n_compared)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ldcta", required=True, help="ldcta 缓存目录 (QNCTACC2026MSSQL)")
    parser.add_argument("--cache", required=True, help="xqsim 输出缓存目录 (cc_update)")
    parser.add_argument("--meta", required=True, help="xqsim futures meta_dir (data/futures/cc)")
    parser.add_argument("--calendar", default=None,
                        help="行对齐日历: DateIndex.csv 或裸 int64 Dates.npy; 默认 <meta>/meta/index/DateIndex.csv")
    args = parser.parse_args()

    calendar_path = args.calendar or os.path.join(args.meta, "meta", "index", "DateIndex.csv")
    calendar = load_calendar(calendar_path)
    dr = init_dr(meta_dir=args.meta, total=True, index_category="FUTURES")
    xqsim_data = load_xqsim(dr, args.cache)
    if not xqsim_data:
        print("no xqsim cache files found in %s" % args.cache)
        return

    for tag, (dir_name, file_name) in sorted(FIELD_MAP.items()):
        if tag not in xqsim_data:
            print("%-16s MISSING in xqsim cache" % tag)
            continue
        ldcta_path = os.path.join(args.ldcta, dir_name, file_name)
        if not os.path.exists(ldcta_path):
            print("%-16s ldcta file missing: %s" % (tag, ldcta_path))
            continue
        my_days, my = xqsim_data[tag]
        their_days, theirs = load_ldcta(ldcta_path, calendar)
        common_days = np.intersect1d(my_days, their_days)
        my_rows = np.searchsorted(my_days, common_days)
        their_rows = np.searchsorted(their_days, common_days)
        print(compare_matrix(tag, my[my_rows], theirs[their_rows]))

    # hot.ii / hot.ii_next 与 ldcta 的 M80 布局单独比对
    for tag, file_name in (("hot.ii", "Hot.hot_ii.M80.i.dat"),
                           ("hot.ii_next", "Hot.hot_ii_next.M80.i.dat")):
        if tag not in xqsim_data:
            print("%-16s MISSING in xqsim cache" % tag)
            continue
        ldcta_path = os.path.join(args.ldcta, "Hot", file_name)
        if not os.path.exists(ldcta_path):
            print("%-16s ldcta file missing: %s" % (tag, ldcta_path))
            continue
        my_days, my = xqsim_data[tag]
        their_days, theirs = load_ldcta(ldcta_path, calendar)
        common_days = np.intersect1d(my_days, their_days)
        my_rows = np.searchsorted(my_days, common_days)
        their_rows = np.searchsorted(their_days, common_days)
        print(compare_hot_ii(tag, my[my_rows], theirs[their_rows]))


if __name__ == '__main__':
    main()
