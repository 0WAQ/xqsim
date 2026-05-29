from qsim.alpha_base import *
import pandas as pd
import itertools
import datetime


def normalize(alpha, pct=0.003, mode=0):
    alpha = 1.0 * alpha
    index = np.isfinite(alpha)
    valid_alpha = alpha[index]
    if len(valid_alpha) > 0:
        pct2 = min(0.5, 1.0 * pct * len(alpha) / len(valid_alpha))
        l, r = np.quantile(valid_alpha, [pct2, 1.0 - pct2])
        valid_alpha[valid_alpha < l] = l
        valid_alpha[valid_alpha > r] = r
        if mode == 0:
            valid_alpha = valid_alpha - np.mean(valid_alpha)
        elif mode == 1:
            valid_alpha = valid_alpha / max(valid_alpha.std(), 1e-8)
    alpha[index] = valid_alpha
    alpha[~index] = 0.0
    return alpha


def scale_book_size(alpha, book_size, mode):
    if mode == 0:
        value = np.nan_to_num(alpha)
        lv = np.sum(value[value > 0])
        sv = np.sum(value[value < 0])

        if lv != 0.0:
            multiplier_lv = book_size / 2.0 / lv
            value[value > 0] *= multiplier_lv

        if sv != 0.0:
            multiplier_sv = book_size / 2.0 / abs(sv)
            value[value < 0] *= multiplier_sv
        return value
    elif mode == 1:
        value = np.nan_to_num(alpha)
        tv = np.sum(np.abs(value))
        if tv != 0.0:
            multiplier = book_size / tv
            value *= multiplier
        return value
    elif mode == -1:
        value = np.nan_to_num(alpha)
        return value


def calc_cor(array: np.ndarray, ret: np.ndarray):
    index = np.isfinite(array) & np.isfinite(ret)
    if np.sum(index) <= 1:
        return NAN
    array = array[index]
    if np.std(array) == 0:
        return NAN
    ret = ret[index]
    return np.corrcoef(array, ret)[0][1]


def load_dat_to_df(meta_dir, file_path):
    header = DataManager.load_header(file_path)
    dr = init_dr(meta_dir=meta_dir, begin_date=int(header.begin_trading_day), end_date=int(header.end_trading_day))
    data = DataManager(dr.meta).load_data_from_file(file_path)
    if len(data.shape) == 3:
        data.shape = (data.shape[0] * data.shape[1], data.shape[2])
        index = None
        for time_index in dr.meta.time_index_dict.values():
            if len(time_index) == int(header.ti_size):
                index = []
                for item in itertools.product(dr.meta.offset_date_index, time_index):
                    index.append(datetime.datetime.strptime("{} {}".format(item[0], item[1]), "%Y%m%d %H:%M:%S"))
                break
        if index is None:
            raise Exception("time index not found")
    else:
        index = [datetime.datetime.strptime(str(item), "%Y%m%d") for item in dr.meta.offset_date_index]
    df = pd.DataFrame(data, index=index, columns=dr.meta.all_instrument_index)
    return df


DAYS_YEAR = 250.0
DAYS_MONTH = 21.0
DAYS_WEEK = 5.0


def pnl_ana(df, days_multiply):
    dates = df['Date'].min().strftime('%Y%m%d') + '-' + df['Date'].max().strftime('%Y%m%d')
    lv = df['LongValue'].mean() / 1000000.0
    sv = df['ShortValue'].mean() / 1000000.0
    pnl = df['Pnl'].sum() / 1000000.0

    ret = 100.0 * df['Return'].sum()
    days = df['Return'].count()
    # if days_multiply == DAYS_YEAR and (df['Date'].iloc[0].strftime('%m%d') > '0105' or df['Date'].iloc[-1].strftime('%m%d') < '1228'):
    #     ret = ret / days * days_multiply

    tvr = 100.0 * df['TradeValue'].sum() / df['BookSize'].sum()

    if len(df) > 1 and df['Return'].std(ddof=0) != 0.0:
        sharpe = df['Return'].mean() / df['Return'].std(ddof=0) * (DAYS_YEAR ** 0.5)
    else:
        sharpe = np.Inf

    mdd_idx = df['_drawdown'].idxmax()
    mdd = 100.0 * df['_drawdown'].loc[mdd_idx]
    mdd_date = df['Date'].loc[mdd_idx].strftime('%Y%m%d')
    mdd_start_idx = df[df.index <= mdd_idx]['_cumret'].idxmax()
    mdd_dur = mdd_idx - mdd_start_idx

    win = 100.0 * len(df[df['Return'] > 0.0]) / days
    ln = int(df['LongNum'].mean())
    sn = int(df['ShortNum'].mean())
    ic = df['IC'].mean()

    calmar = ret / mdd if mdd != 0.0 else np.Inf

    df_down = df[df['Return'] < 0.0]
    if len(df_down) > 1 and df_down['Return'].std(ddof=0) != 0.0:
        sortino = df['Return'].mean() / df_down['Return'].std(ddof=0) * (DAYS_YEAR ** 0.5)
    else:
        sortino = np.Inf

    trade_total = df['TradeValue'].sum() / 1000000.0
    bpmargin = 10000. * pnl / trade_total if trade_total != 0 else np.Inf
    # csmargin = 100000. * (df['Ret'] / df['LongNum']).mean()
    fitness = sharpe * (abs(ret / tvr) ** 0.5) * 1.0 if tvr > 0 else -1.0

    return pd.DataFrame([[dates, lv, sv, pnl, ret, tvr, mdd, calmar, sharpe, sortino, win, mdd_date, mdd_dur, ln, sn, bpmargin, fitness, ic]],
                        columns=['Dates', 'Long(M)', 'Short(M)', 'PnL(M)', 'Ret(%)', 'TVR(%)', 'MDD(%)', 'Calmar',
                                 'Sharpe', 'Sortino', 'Win(%)', 'MDD_Date', 'MDD_Dur', 'LongNum', 'ShortNum', 'BPMargin',
                                 'Fitness', "IC"])


def pnl_scale(df, scale, recent):
    df = df.reset_index(drop=True)
    df.loc[:, '_cumret'] = df['Return'].cumsum()
    df.loc[:, '_lastmax'] = df['_cumret'].cummax()
    df.loc[:, '_drawdown'] = df['_lastmax'] - df['_cumret']
    # print(df)
    df.loc[:, 'Date'] = [pd.Timestamp(str(x)) for x in df.loc[:, "Date"]]
    if 'M' == scale[0]:
        df.loc[:, '_scale'] = [(x.year * 100 + x.month) for x in df.Date]
        days_multiply = DAYS_MONTH
    elif 'W' == scale[0]:
        df.loc[:, '_scale'] = [(x.year * 100 + x.weekofyear) for x in df.Date]
        days_multiply = DAYS_WEEK
    else:
        df.loc[:, '_scale'] = [x.year for x in df.Date]
        days_multiply = DAYS_YEAR
    df.loc[:, '_year'] = [x.year for x in df.Date]
    df_grouped_scale = df.groupby('_scale', group_keys=False)
    df_grouped_year = df.groupby('_year')

    date_recent_end = df['Date'].iloc[-1]
    date_recent_start = pd.Timestamp(date_recent_end.year - recent, date_recent_end.month, date_recent_end.day)
    df_recent = df[df["Date"] > date_recent_start]

    df_result1 = df_grouped_scale.apply(pnl_ana, days_multiply=days_multiply)

    df_result2 = pnl_ana(df, DAYS_YEAR)

    df_result3 = pnl_ana(df_recent, DAYS_YEAR)

    days_year = df_grouped_year['Return'].count()
    year_num = len(days_year)
    # if df['Date'].iloc[0].strftime('%m%d') > '0105':
    #     year_num += (days_year.iloc[0] / DAYS_YEAR - 1)
    # if df['Date'].iloc[-1].strftime('%m%d') < '1228':
    #     year_num += (days_year.iloc[-1] / DAYS_YEAR - 1)

    ret_all = 100.0 * df['Return'].sum() / year_num
    ret_recent = 100.0 * df_recent['Return'].sum() / recent

    df_result2.loc[0, 'Ret(%)'] = ret_all
    df_result3.loc[0, 'Ret(%)'] = ret_recent
    df_result2.loc[0, 'Ret/MDD'] = ret_all / df_result2.loc[0, 'MDD(%)'] if df_result2.loc[0, 'MDD(%)'] != 0.0 else np.Inf
    df_result3.loc[0, 'Ret/MDD'] = ret_recent / df_result3.loc[0, 'MDD(%)'] if df_result3.loc[0, 'MDD(%)'] != 0.0 else np.Inf

    return df_result1.round(4), df_result2.round(4), df_result3.round(4)


def get_daily_df(df) -> pd.DataFrame:
    df = df.groupby("Date").agg(Date=("Date", "last"),
                                RawPnl=("RawPnl", "sum"),
                                LongValue=("LongValue", "mean"),
                                ShortValue=("ShortValue", "mean"),
                                RawReturn=("RawReturn", "sum"),
                                BookSize=("BookSize", "mean"),
                                TradeValue=("TradeValue", "sum"),
                                LongNum=("LongNum", "mean"),
                                ShortNum=("ShortNum", "mean"),
                                IC=("IC", "mean"), )
    return df
