from qsim.alpha_base import *


def main():
    # dr = init_dr(meta_dir=r"E:\CC", begin_date=20180110, end_date=20201231, back_days=5, data_limit=10000000)
    dr = init_dr(meta_dir=r"/cc", begin_date=20200104, end_date=20200131, back_days=1, data_limit=0, level=4)

    # dr.calendar.valid_date("20200102")
    log_info("%s", dr.calendar.get_latest_trade_date(20200101))
    log_info("%s", dr.calendar.get_latest_trade_date(20200102))
    log_info("%s", dr.calendar.get_latest_trade_date(20200103))
    print(dr.meta.enum_index_dict["ciidx_level1"])
    # print(dr.meta.date_index[common_utils.equal_or_first_less(dr.meta.date_index, 20200103)])
    # print(dr.meta.date_index[common_utils.equal_or_first_greater(dr.meta.date_index, 20200103)])


if __name__ == '__main__':
    main()
