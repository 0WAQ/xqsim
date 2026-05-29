from qsim.alpha_base import *
import pandas as pd

pd.set_option('display.max_rows', None)


def main():
    # dr = init_dr(meta_dir=r"E:\CC", begin_date=20180110, end_date=20201231, back_days=5, data_limit=10000000)
    dr = init_dr(meta_dir=r"/cc", begin_date=20200722, end_date=20200728, back_days=1, data_limit=1, interval="minute1_239",
                 cache_list=["~/test_cc", "/fast/szhong/cc", "/mnt/s"])

    close = dr.get_data_adj("km15.close", 20200715)
    close1 = dr.get_data_adj("km15.close", 20200725)
    close2 = dr.get_data("km15.close")

    print(dr.meta.all_instrument_index[2])

    for di in dr.meta.di_list:
        print(dr.meta.date_index[di])
        print(close[di][0][2])
        print(close1[di][0][2])
        print(close2[di][0][2])

    volume = dr.get_data_adj("k.volume", 20200715, ADJ_VOLUME)
    volume1 = dr.get_data_adj("k.volume", 20200725, ADJ_VOLUME)
    volume2 = dr.get_data("k.volume")
    print(volume.to_df())
    print(volume1.to_df())
    print(volume2.to_df())

    close_d = dr.get_data_adj("k.close", 20200722)
    close_d1 = dr.get_data_adj("k.close", 20200727)
    close_d2 = dr.get_data("k.close")
    print(close_d.to_df())
    print(close_d1.to_df())
    print(close_d2.to_df())

    # close = dr.get_data("close")
    # close1 = dr.get_data_adj("close", 20200722)
    # close2 = dr.get_data_adj("close", 20200727)
    #
    # close3 = dr.get_matrix_data_adj("close")
    # for di in dr.meta.di_list:
    #     print("==", di, dr.meta.date_index[di])
    #     print(close[di][0][2])
    #     print(close1[di][0][2])
    #     print(close2[di][0][2])
    #     print(close.to_df_di(di))
    #     print(close3.to_df())
    #     print(close3.shape)


if __name__ == '__main__':
    main()
