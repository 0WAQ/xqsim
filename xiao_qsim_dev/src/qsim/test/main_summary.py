from qsim.utils import *


def main():
    # pd.set_option('precision', 2)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('expand_frame_repr', False)
    pd.set_option('display.unicode.ambiguous_as_wide', True)
    pd.set_option('display.unicode.east_asian_width', True)

    df = pd.read_csv(r"./unknown_id_raw.csv")

    daily_df = get_daily_df(df)
    # print(daily_df)

    result1, result2, result3 = pnl_scale(daily_df, "Y", 1)
    result1.index = [''] * len(result1)
    result2.index = [''] * len(result2)
    result3.index = [''] * len(result3)

    print(result1)


if __name__ == '__main__':
    main()
