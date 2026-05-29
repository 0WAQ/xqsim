import numpy as np
from qsim.alpha_base import *


def main(data):
    dr = init_dr(meta_dir=r"/cc", begin_date='20210415', end_date='20210415', back_days=0, data_limit=0, level=1,
                 cache_list=["/mnt/sdb/zhongshuai/PycharmProjects/data_provider/cc", "cc2"],
                 output_cache_dir="./cc2")

    dr.append_alpha_by_ti("Dir1", "signal", data, dr.meta.begin_di, 0, "minute1_239")

    dr = init_dr(meta_dir=r"/cc", begin_date='20210415', end_date='20210415', back_days=0, data_limit=0, level=1,
                 cache_list=["/mnt/sdb/zhongshuai/PycharmProjects/data_provider/cc", "cc2"],
                 output_cache_dir="./cc2")

    alpha = dr.get_alpha("signal")
    print(alpha.end_ti)
    print(alpha.data[0])

    dr.append_alpha_by_ti("Dir1", "signal", data, dr.meta.begin_di, 2, "minute1_239")

    print(alpha.end_ti)
    print(alpha.data[0])

    dr.refresh()
    print(alpha.end_ti)
    print(alpha.data[0])


def main2(data):
    dr = init_dr(meta_dir=r"/cc", begin_date='20210415', end_date='20210415', back_days=0, data_limit=0, level=1,
                 cache_list=["/mnt/sdb/zhongshuai/PycharmProjects/data_provider/cc", "cc2"],
                 output_cache_dir="./cc2")

    alpha = dr.get_alpha("signal")
    print(alpha.end_ti)
    print(alpha.data[0])
    # print(alpha.data[0][1])
    # print(np.where(data != alpha.data[0][0]))
    # print(np.where(data != alpha.data[0][1]))


if __name__ == '__main__':
    data = np.empty((6000,), np.float64)
    data = np.nan_to_num(data)
    print(data)
    main(data)
