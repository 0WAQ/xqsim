# 期货品种/合约代码换算, 移植自 ldcta base.py 的纯函数部分
# (common_cache_mssql_cron_ldcta, ywang)。原始代码中的读侧基类 CommonCacheBase
# 不移植, 其职能由 xqsim 的 Meta/DataRepository 替代。
import re

# 槽位布局常量: ii = pi * 50 + slot
SLOTS_SIZE = 50
HOT_SLOT = 48     # 主力合约拷贝槽
INDEX_SLOT = 49   # 指数槽 (ldcta 从未填数据, 一期不使用)


def convert_windcode(wind_code: str) -> str | None:
    if not wind_code:
        return None
    if "-S" in wind_code:
        return None

    exchange = wind_code[wind_code.index(".") + 1:]
    instrument = wind_code[0:wind_code.index(".")]
    if exchange != 'CZC' and exchange != 'CFE':
        instrument = instrument.lower()
    return instrument


def convert_czc_code(instrument: str | None, trading_day: str) -> str | None:
    """CZCE 三位年份码补全为四位 (按交易日推断年代)"""
    if not instrument:
        return None

    if re.match("[a-zA-Z]+\\d{3}", instrument) is None:
        return None

    if not instrument[-4].isdigit():
        if instrument[-3] >= trading_day[3]:
            return instrument[0:-3] + trading_day[2] + instrument[-3:]
        else:
            return instrument[0:-3] + str((int(trading_day[2]) + 1) % 10) + instrument[-3:]
    return instrument


def convert_product(product: str) -> str:
    """品种改名历史映射"""
    if product == "RO":
        return "OI"
    if product == "ME":
        return "MA"
    if product == "TC":
        return "ZC"
    if product == "ER":
        return "RI"
    if product == "WS":
        return "WH"
    return product


def get_product(instrument: str) -> str:
    return instrument[:-4] if instrument[-4].isdigit() else instrument[:-3]


def convert_to_standard_code(wind_code: str, trading_day: str) -> str | None:
    """wind 代码 -> 标准合约码 (如 RB1810.SHF -> rb1810)"""
    instrument = convert_czc_code(convert_windcode(wind_code), trading_day)
    if instrument is None:
        return None
    product = convert_product(instrument[:-4])
    return product + instrument[-4:]
