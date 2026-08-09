# 诊断 pi 维字段的失配列: 打出失配集中在哪个 pi、该品种在我方 meta 里的
# 代码、以及两侧采样值。
# 用法: uv run python tools/futures/diagnose_pi.py --tag wh.deliverable \
#       --ldcta /production/qsim/LDCTA/QNCTACC2026MSSQL/ \
#       --cache data/futures/cc_update/ --meta data/futures/cc
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_ldcta import (FIELD_MAP, PI_FIELD_MAP, load_calendar, load_ldcta,
                           load_xqsim, HOT_SLOT, SLOTS_SIZE)
from xqsim.xqsim_run import init_dr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--ldcta", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--meta", required=True)
    parser.add_argument("--calendar", default=None)
    args = parser.parse_args()

    calendar = load_calendar(args.calendar or os.path.join(args.meta, "meta", "index", "DateIndex.csv"))
    sys.argv = sys.argv[:1]
    dr = init_dr(meta_dir=args.meta, total=True, index_category="FUTURES")
    xqsim_data = load_xqsim(dr, args.cache)

    dir_name, file_name = PI_FIELD_MAP[args.tag]
    my_days, my = xqsim_data[args.tag]
    their_days, theirs = load_ldcta(os.path.join(args.ldcta, dir_name, file_name), calendar)
    common_days = np.intersect1d(my_days, their_days)
    my_rows = np.searchsorted(my_days, common_days)
    their_rows = np.searchsorted(their_days, common_days)
    mine = my[my_rows].astype(np.float32)
    their = theirs[their_rows].astype(np.float32)

    same = (mine == their) | (np.isnan(mine) & np.isnan(their))
    bad_pi = np.nonzero((~same).any(axis=0))[0]
    print("mismatch pi columns:", bad_pi.tolist())
    for pi in bad_pi:
        col_bad = np.nonzero(~same[:, pi])[0]
        first, last = col_bad[0], col_bad[-1]
        day = int(common_days[first])
        abs_di = dr.meta.total_di_mapping[day]
        hot_ii = pi * SLOTS_SIZE + HOT_SLOT
        code = dr.meta.instrument_index[abs_di][hot_ii] if abs_di in dr.meta.instrument_index else "?"
        print("pi=%s code=%s mismatch_days=%s (%s ~ %s)" % (
            pi, code, len(col_bad), common_days[first], common_days[last]))
        for r in col_bad[:3].tolist() + col_bad[-3:].tolist():
            print("   %s mine=%s theirs=%s" % (common_days[r], mine[r, pi], their[r, pi]))


if __name__ == '__main__':
    main()
