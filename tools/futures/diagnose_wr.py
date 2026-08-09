# 诊断: wr (强麦) 失配的根因。在能连 MSSQL 的机器上跑:
#   uv run python tools/futures/diagnose_wr.py
import json
import os

import pymssql

with open(os.path.join(os.path.dirname(__file__), "../../providers/futures/mssql.json")) as f:
    cfg = json.load(f)
conn = pymssql.connect(server=cfg["host"], user=cfg["user"], password=cfg["password"],
                       port=cfg.get("port", "1433"), as_dict=True)
cur = conn.cursor()

print("== 1. EOD 行情表里强麦的 windcode 形态 (失配的两个交易日)")
for day in ("20180926", "20181206"):
    cur.execute("""
        SELECT S_INFO_WINDCODE, FS_INFO_TYPE, S_DQ_OPEN, S_DQ_CLOSE, S_DQ_VOLUME
        FROM wind.dbo.CCOMMODITYFUTURESEODPRICES
        WHERE (S_INFO_WINDCODE LIKE 'wr%%' OR S_INFO_WINDCODE LIKE 'WR%%')
            AND TRADE_DT = '%s' ORDER BY S_INFO_WINDCODE
    """ % day)
    for r in cur.fetchall():
        print(day, r)

print("== 2. 合约表 (CFUTURESDESCRIPTION) 里 wr/WR 的形态")
cur.execute("""
    SELECT S_INFO_CODE, FS_INFO_SCCODE, S_INFO_LISTDATE, S_INFO_DELISTDATE
    FROM wind.dbo.CFUTURESDESCRIPTION
    WHERE FS_INFO_SCCODE IN ('wr', 'WR') ORDER BY S_INFO_LISTDATE DESC
""")
for r in cur.fetchall()[:10]:
    print(r)

print("== 3. 我的 InstrumentIndex.csv 里 ii=1035/1040 及 wr/WR 相关行")
idx_path = os.path.join(os.path.dirname(__file__), "../../data/futures/cc/meta/index/InstrumentIndex.csv")
with open(idx_path) as f:
    for line in f:
        parts = line.split(",")
        if parts[0] in ("1035", "1040") or "wr" in line or "WR" in line:
            print(line.strip())
