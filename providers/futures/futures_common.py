# 期货品种/合约代码换算, 移植自 ldcta base.py 的纯函数部分
# (common_cache_mssql_cron_ldcta, ywang)。原始代码中的读侧基类 CommonCacheBase
# 不移植, 其职能由 xqsim 的 Meta/DataRepository 替代。
import os
import re

XQSIM_DATA_HOME = os.path.realpath(
    os.environ.get("XQSIM_DATA_HOME", "/usr/local/xqsim/data")
)
FUTURES_CC_DIR = os.path.join(XQSIM_DATA_HOME, "futures", "cc")

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


ENUM_HEADER = "ID,Member"


def member_key(compcode, membername) -> str | None:
    """会员身份字符串: compcode (稳定公司代码) 优先, 缺失回退 NAME::会员名
    (与示例因子 normalized_member_id 规则一致; compcode 稳定而会员名有变体)"""
    compcode = str(compcode).strip() if compcode is not None else ""
    if compcode:
        return compcode
    membername = str(membername).strip() if membername is not None else ""
    if membername:
        return "NAME::" + membername
    return None


def load_or_extend_member_enum(enum_path: str, strings) -> dict[str, int]:
    """会员 enum (Enum_member.csv) 读取 + 追加, 供 positions_rank / meta_updater 共用。
    纪律: id 只增不改——新字符串按当前最大 id 顺延追加写回, 已有条目 id 永不动
    (缓存里存的是 id, 重编会使历史数据错位)。
    返回完整的 字符串 -> id 映射 (键均为 str)。"""
    mapping: dict[str, int] = {}
    if os.path.exists(enum_path):
        with open(enum_path, "r", encoding="utf-8") as reader:
            for line in reader.readlines()[1:]:
                words = [word.strip() for word in line.split(",")]
                if len(words) < 2 or not words[0] or not words[1]:
                    continue
                mapping[words[1]] = int(words[0])

    new_strings = sorted(s for s in set(strings) if s and s not in mapping)
    if new_strings:
        next_id = max(mapping.values(), default=-1) + 1
        # 文件不存在时先补表头 (load_csv_file 固定跳过首行)
        if not os.path.exists(enum_path) or os.path.getsize(enum_path) == 0:
            with open(enum_path, "w", encoding="utf-8") as writer:
                writer.write(ENUM_HEADER + "\n")
        with open(enum_path, "a", encoding="utf-8") as writer:
            for s in new_strings:
                writer.write("%d,%s\n" % (next_id, s))
                mapping[s] = next_id
                next_id += 1
    elif not os.path.exists(enum_path):
        with open(enum_path, "w", encoding="utf-8") as writer:
            writer.write(ENUM_HEADER + "\n")
    return mapping
