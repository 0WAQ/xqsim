# MSSQL 读取基类, 仿 providers/stocks/static_provider.py (StaticProvider)。
# 替代 ldcta 的 data_provider_base.py / builder_base.py 的连接职能;
# 凭证外置 mssql.json (ldcta 为明文硬编码, 不沿袭)。
import json
import pymssql
from xqsim.common_module import *
from xqsim.base.provider_base import ProviderBase
from futures_common import convert_to_standard_code, SLOTS_SIZE, HOT_SLOT

OI_SQL = """\
    SELECT S_INFO_WINDCODE, TRADE_DT, S_DQ_OI
    FROM wind.dbo.CCOMMODITYFUTURESEODPRICES
    WHERE FS_INFO_TYPE = 2
        AND TRADE_DT BETWEEN '%s' AND '%s'
    ORDER BY TRADE_DT, S_INFO_WINDCODE
"""


class MssqlProvider(ProviderBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.mssql_config_dir = self.cfg.get("mssql_config_dir", os.path.abspath(os.path.dirname(__file__)))
        self.mssql_config = self.cfg.get("mssql_config", "mssql.json")

    def exec_sql_fetchall(self, sql: str, json_file=None) -> list:
        if json_file is None:
            json_file = self.mssql_config
        json_file = os.path.join(self.mssql_config_dir, json_file)
        with open(json_file, "r") as reader:
            config_dict = json.load(reader)
        log_info("Connect to mssql %s with user %s", config_dict["host"], config_dict["user"])
        connect_kwargs = dict(server=config_dict["host"],
                              user=config_dict["user"],
                              password=config_dict["password"],
                              port=config_dict.get("port", "1433"),
                              as_dict=True)
        if "database" in config_dict:
            connect_kwargs["database"] = config_dict["database"]
        conn = pymssql.connect(**connect_kwargs)
        cursor = conn.cursor()
        log_info("Exec sql and fetchall: %s", sql)
        cursor.execute(sql)
        rows = cursor.fetchall()
        log_info("Exec finish, rows count %s", len(rows))
        cursor.close()
        conn.close()
        return rows

    def get_ii(self, code: str) -> int | None:
        return self.meta.ii_mapping.get(code)

    def listed_code(self, di: int, ii: int) -> str:
        """offset di 上槽位 ii 驻留的合约码, 空槽返回 ""
        注意 instrument_index 的键是绝对 di (begin_di + offset)"""
        return self.meta.instrument_index[self.meta.begin_di + di][ii]

    def get_pi(self, product: str) -> int | None:
        """品种码 -> pi (经 8888 主力槽行反查 ii_mapping), 兼容大小写变体;
        未收录品种 (非 CZCE/DCE/SHFE) 返回 None"""
        for variant in (product, product.lower(), product.upper()):
            ii = self.meta.ii_mapping.get(variant + "8888")
            if ii is not None:
                return ii // SLOTS_SIZE
        return None

    def write_pi_data(self, tag: str, pi_values: np.ndarray):
        """pi 维 (di, pi_size) 数据写进 ii 空间: 值放在该品种 48 号主力槽列,
        其余列 NaN。消费方按 ii = pi*50+48 列读取"""
        data = np.full((self.meta.di_size, self.meta.ii_size), nan, np.float64)
        pi_size = self.meta.ii_size // SLOTS_SIZE
        data[:, HOT_SLOT::SLOTS_SIZE] = pi_values[:, :pi_size]
        self.write_data(tag, data)

    def fetch_oi_rows(self) -> list:
        """拉取持仓量序列供主力判定: [(trading_day:int, code:str, oi:float)]"""
        sql = OI_SQL % (self.meta.begin_trading_day, self.meta.end_trading_day)
        oi_rows = []
        for row in self.exec_sql_fetchall(sql):
            trading_day = int(str(row["TRADE_DT"]).replace("-", ""))
            code = convert_to_standard_code(str(row["S_INFO_WINDCODE"]), str(trading_day))
            if code is None:
                continue
            oi = float(row["S_DQ_OI"]) if row["S_DQ_OI"] is not None else 0.0
            oi_rows.append((trading_day, code, oi))
        return oi_rows
