# 期货 meta CSV 生成器, 移植自 ldcta builder/futures_ii.py。
# 与 ldcta 的差异:
#   1. 砍掉 MSSQL 中间表 (CC_Meta_InstrumentIndex_Future), 直接落 xqsim meta CSV;
#   2. EndDate 排他转换: xqsim meta_loader 按 [StartDate, EndDate) 填充,
#      而 wind 的摘牌日 (S_INFO_DELISTDATE) 是最后交易日 (含当天),
#      所以 EndDate 写摘牌日的**下一个交易日**; 超出日历末尾写 20891231;
#   3. 每品种追加一行 8888 主力拷贝槽 (slot 48); 49 指数槽 ldcta 从未填数据, 不生成;
#   4. StartDate 早于日历首日时收敛到首日 (等价于 ldcta 的 find_dict_ge  clamp)。
#
# 产出 (meta_dir 下):
#   meta/index/DateIndex.csv        di,TradingDay
#   meta/index/InstrumentIndex.csv  ii,Code,StartDate,EndDate
#   meta/index/StaticIndexSize.csv  含 FUTURES/4000 行
#   meta/time_index/ meta/enum/     空目录 (loader 要求存在)
#
# 用法: python meta_updater.py [meta_dir]   (默认 ./data/futures/cc, 需先配好 mssql.json)
import bisect
import json
import os
import sys

import pymssql

from futures_common import SLOTS_SIZE, HOT_SLOT, convert_product

II_SIZE = 4000
FAR_END_DATE = "20891231"

PRODUCT_SQL = """\
    SELECT IIF(S_INFO_EXCHMARKET!='CZCE' AND S_INFO_EXCHMARKET!='CFFEX', lower(FS_INFO_SCCODE), FS_INFO_SCCODE)
        AS SCCODE,
        S_INFO_EXCHMARKET,
        min(S_INFO_LISTDATE)
    FROM wind.dbo.CFUTURESDESCRIPTION
    WHERE FS_INFO_TYPE = 1
        AND (FS_INFO_SCCODE = 'IM' OR S_INFO_NAME NOT LIKE N'%%仿真%%')
        AND S_INFO_EXCHMARKET IN ('CZCE','DCE','SHFE')
    GROUP BY FS_INFO_SCCODE,
        S_INFO_EXCHMARKET
    ORDER BY min(S_INFO_LISTDATE),
        min(FS_INFO_SCCODE)
"""

CONTRACT_SQL = """\
    SELECT  IIF(S_INFO_EXCHMARKET!='CZCE' AND S_INFO_EXCHMARKET!='CFFEX',
                LOWER(S_INFO_CODE),
                IIF(S_INFO_EXCHMARKET!='CZCE',
                    S_INFO_CODE,
                    concat(FS_INFO_SCCODE, substring(S_INFO_DELISTDATE, 3, 4))
                )
            ) AS S_INFO_CODE,
            IIF(S_INFO_EXCHMARKET!='CZCE' AND S_INFO_EXCHMARKET!='CFFEX',
                LOWER(FS_INFO_SCCODE),
                FS_INFO_SCCODE
            ) AS FS_INFO_SCCODE,
            S_INFO_EXCHMARKET,
            S_INFO_LISTDATE,
            S_INFO_DELISTDATE
    FROM wind.dbo.CFUTURESDESCRIPTION
    WHERE FS_INFO_TYPE = 1
"""

CALENDAR_SQL = "SELECT TradingDay FROM CommonCache.dbo.CC_Meta_TradingDays_Wind ORDER BY TradingDay ASC"


def norm_date(date_str: str) -> str:
    """wind 日期统一为 yyyymmdd"""
    return str(date_str).replace("-", "")


class MetaUpdater(object):
    def __init__(self, meta_dir: str, mssql_config: str = "mssql.json"):
        self.meta_dir = meta_dir
        json_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), mssql_config)
        with open(json_file) as reader:
            config_dict = json.load(reader)
        connect_kwargs = dict(server=config_dict["host"],
                              user=config_dict["user"],
                              password=config_dict["password"],
                              port=config_dict.get("port", "1433"))
        if "database" in config_dict:
            connect_kwargs["database"] = config_dict["database"]
        self.conn = pymssql.connect(**connect_kwargs)

    def query(self, sql: str) -> list:
        cursor = self.conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def load_calendar(self) -> list[str]:
        return [norm_date(row[0]) for row in self.query(CALENDAR_SQL)]

    def update_date_index(self, calendar: list[str]):
        file_path = os.path.join(self.meta_dir, "meta", "index", "DateIndex.csv")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as writer:
            writer.write("ID,TradingDay\n")
            for di, day in enumerate(calendar):
                writer.write("%s,%s\n" % (di, day))
        print("update DateIndex.csv finish, %s days" % len(calendar))

    def update_instrument_index(self, calendar: list[str]):
        # 品种按最早上市日排序分配 pi (与 ldcta 一致, 保证 ii 布局兼容)
        product_dict: dict[str, tuple[int, str]] = {}  # product -> (pi, listed_date)
        for row in self.query(PRODUCT_SQL):
            product = convert_product(str(row[0]))
            if product in product_dict:
                continue
            product_dict[product] = (len(product_dict), norm_date(row[2]))

        # 合约 -> (ii, code, listed, delisted); slot = year%4*12 + month-1
        symbol_list: list[tuple[int, str, str, str]] = []
        for row in self.query(CONTRACT_SQL):
            old_symbol = str(row[0])
            old_product = str(row[1])
            listed_date = norm_date(row[3])
            delist_date = norm_date(row[4])

            product = convert_product(old_product)
            symbol = old_symbol.replace(old_product, product)
            if product not in product_dict:
                continue
            try:
                symbol_month = int(symbol[-2:])
                symbol_year = int(symbol[-4:-2])
            except (ValueError, IndexError):
                continue

            pi = product_dict[product][0]
            ii = pi * SLOTS_SIZE + symbol_year % 4 * 12 + symbol_month - 1
            symbol_list.append((ii, symbol, listed_date, delist_date))

        # 每品种追加主力拷贝槽 (8888)
        for product, (pi, listed_date) in product_dict.items():
            symbol_list.append((pi * SLOTS_SIZE + HOT_SLOT, product + "8888", listed_date, FAR_END_DATE))

        print("find %s instrument records, %s products" % (len(symbol_list), len(product_dict)))

        file_path = os.path.join(self.meta_dir, "meta", "index", "InstrumentIndex.csv")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as writer:
            writer.write("ID,WindCode,StartDate,EndDate\n")
            for ii, code, listed_date, delist_date in symbol_list:
                if delist_date < calendar[0]:
                    continue
                if listed_date > calendar[-1]:
                    continue
                # xqsim 排他 EndDate = 摘牌日下一交易日; 仍在市的写 20891231
                next_idx = bisect.bisect_right(calendar, delist_date)
                end_date = calendar[next_idx] if next_idx < len(calendar) else FAR_END_DATE
                # wind 上市日不一定是交易日 (可能落在假日/日历空洞),
                # 吸附到第一个 >= 上市日的交易日 (ldcta find_dict_ge 同语义)
                start_idx = bisect.bisect_left(calendar, listed_date)
                if start_idx >= len(calendar):
                    continue
                start_date = calendar[start_idx]
                if start_date >= end_date:
                    continue
                writer.write("%s,%s,%s,%s\n" % (ii, code, start_date, end_date))
        print("update InstrumentIndex.csv finish")

    def update_static_size(self):
        file_path = os.path.join(self.meta_dir, "meta", "index", "StaticIndexSize.csv")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as writer:
            writer.write("ID,StaticValue,Comment\n")
            writer.write("0,%s,FUTURES\n" % II_SIZE)
        print("update StaticIndexSize.csv finish")

    def run(self):
        calendar = self.load_calendar()
        print("calendar: %s ~ %s, %s days" % (calendar[0], calendar[-1], len(calendar)))
        self.update_date_index(calendar)
        self.update_instrument_index(calendar)
        self.update_static_size()
        # loader 对 time_index / enum 目录直接 listdir, 必须存在
        os.makedirs(os.path.join(self.meta_dir, "meta", "time_index"), exist_ok=True)
        os.makedirs(os.path.join(self.meta_dir, "meta", "enum"), exist_ok=True)


def main():
    meta_dir = sys.argv[1] if len(sys.argv) >= 2 else "./data/futures/cc"
    MetaUpdater(meta_dir).run()


if __name__ == '__main__':
    main()
