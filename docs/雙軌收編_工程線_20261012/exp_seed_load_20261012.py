#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E-P1-2 雙軌收編（工程線）：載入方法學線《EXP種子預註冊_20261011.sql》三行至 experiment 表
================================================================================================
單寫者原則：本腳本是 experiment 表「正式試驗行」的唯一寫入器（SEED 示範行除外）。
安全基線：
  - 憑據只經環境變數注入（DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME），本檔零硬編碼；
  - 隔離：只 INSERT experiment 白名單表；執行語句逐條斷言表名，絕不觸碰他方表；
  - 冪等：INSERT IGNORE + 載入後全欄位回讀校驗，可重跑；
  - 時序鐵律 R-1：本三行先於回測引擎首次運行落庫。
欄位長度前置斷言（與 DDL 對齊）：title<=256, benchmark<=64, primary_metric<=64, notes<=512。
"""
import os
import sys
import json
import pymysql

REQUIRED_ENV = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]
ALLOWED_TABLE = "experiment"  # 本腳本唯一寫入白名單

# 與量化腿種子 SQL 逐欄一致（JSON 以字面量原樣入庫）
EXP_ROWS = [
    {
        "experiment_id": "EXP-2026-001",
        "title": "P0突破確認制 vs 回調接反事實（三地池成本後單筆期望值）",
        "hypothesis": "H0: 池內成本後P0確認制入場單筆expectancy(R倍數均值)<=0 || H1: expectancy>0且bootstrap(1000次)90%CI下界>0，觸發樣本n>=40",
        "rule_ids": '["P0.C1@1.2.0","P0.C2@1.2.0","P0.C3@1.2.0","P0.E0@1.2.0"]',
        "primary_metric": "成本後單筆expectancy（R=初始止損距離；成本三地分參數見回測最低規格）",
        "benchmark": "buy_and_hold；回調接反事實（MA20回踩收復入場，同退出）——後者輸出踏空成本分布，不作判決條件",
        "pass_criteria": "GO: H1成立且5x成本層expectancy仍>0 || NO-GO: expectancy<=0 或 5x成本層轉負 或 n<40 || 分層必報:市場(US/HK/CN)x20日實現波動率三分位",
        "max_trials": 10, "trials_used": 0, "status": "pre_registered", "owner": "量化腿",
        "notes": "參數網格預列即凍結:突破窗{20,55}x緩衝{0.2%,0.5%}x量能{1.5,1.2}=8格+重跑預算2；數據窗2025-10-03~2026-10-09騰訊qfq日K；預註冊文檔sha256=ef92a89227215b03d0a0c686589f2f455e7f59b77ecfeea2e6165e742a98f601",
    },
    {
        "experiment_id": "EXP-2026-002",
        "title": "MA滑動退出/減倉制 vs 固定止損-8% vs MA-only（退出政策族對比）",
        "hypothesis": "H0: MA滑動退出成本後expectancy與MAE不優於固定止損-8%(C11硬頂)基準 || H1: 滑動制expectancy>0且(MAE中位更小 或 MFE捕獲率更高)，5x成本層不轉負",
        "rule_ids": '["P0.C1@1.2.0","P0.C2@1.2.0","P0.C3@1.2.0"]',
        "primary_metric": "成本後expectancy；次級主判=MFE捕獲率(平倉收益/MFE)與MAE中位數(position_lot原生欄位)",
        "benchmark": "fixed_stop_-8%；ma_only(無確認純均線持有)",
        "pass_criteria": "GO: H1成立 || NO-GO: expectancy<=0 或與兩基準均無改善(Δ<=0且MAE/MFE均不佔優) || 分層必報:市場x波動三分位；hit rate僅分層觀察不作判決",
        "max_trials": 6, "trials_used": 0, "status": "pre_registered", "owner": "量化腿",
        "notes": "參數網格預列:{MA20減半+二連破清, MA20減半+MA50清, MA10減半+MA20清, 固定-8%, MA-only, 重跑預算1}；入場統一=P0確認制保證可對比",
    },
    {
        "experiment_id": "EXP-2026-003",
        "title": "E0事件窗全日曆回放＋隨機等待N日反事實（FOMC決議日±1交易日只減不加）",
        "hypothesis": "H0: 真事件窗規避效果與隨機等待窗無差異 || H1: 真窗事後組合回撤<隨機窗分布10%分位，且機會成本不落在隨機分布最差25%分位",
        "rule_ids": '["P0.E0@1.2.0"]',
        "primary_metric": "事件窗規避回撤(窗內事後1/3/5日組合跌幅避免值) vs 機會成本(避免掉的漲幅)；真窗統計量在隨機分布之分位=顯著性",
        "benchmark": "隨機等待N日反事實(事件日平移N∈{1..10}交易日，種子42，抽樣1000次)",
        "pass_criteria": "GO: H1成立 || NO-GO: 真窗與隨機窗無差異 或 規避收益<機會成本x1/2 || 樣本局限:8事件/250根窗口，結論僅方向性證據，與EXP-001/002合併裁量",
        "max_trials": 3, "trials_used": 0, "status": "pre_registered", "owner": "量化腿",
        "notes": "事件日曆8次:2025-10-29,2025-12-10(標準公開日程⚠️靜態核對)+2026-01-28,03-18,04-29,06-17,07-29,09-16(fomc_calendar.json✅)；窗寬預列{±1主判,±2,±3}",
    },
]

LIMITS = {"title": 256, "benchmark": 64, "primary_metric": 64, "notes": 512}


def main() -> int:
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(json.dumps({"error": f"MISSING_ENV: {missing}"}))
        return 2

    # 欄位長度前置斷言（先於任何網路操作）
    for r in EXP_ROWS:
        for col, lim in LIMITS.items():
            v = r.get(col) or ""
            assert len(v) <= lim, f"{r['experiment_id']}.{col} 超長 {len(v)}>{lim}"

    conn = pymysql.connect(
        host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"], charset="utf8mb4",
        connect_timeout=15, read_timeout=60, write_timeout=60, autocommit=False,
    )
    report = {"task": "E-P1-2 EXP種子載入", "db": None, "schema_cols": None,
              "pre_existing": [], "inserted": [], "verified": {}, "result": None}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            report["db"] = cur.fetchone()[0]
            assert report["db"] == os.environ["DB_NAME"], "未連上目標庫，中止"

            # schema 對照（⑤教訓：先 SHOW COLUMNS 再寫）
            cur.execute("SHOW COLUMNS FROM experiment")
            cols = {row[0] for row in cur.fetchall()}
            report["schema_cols"] = sorted(cols)
            need = {"experiment_id", "title", "hypothesis", "rule_ids", "primary_metric",
                    "benchmark", "pass_criteria", "max_trials", "trials_used", "status",
                    "owner", "notes"}
            assert need <= cols, f"experiment 缺欄位: {need - cols}"

            # 冪等檢查
            ids = tuple(r["experiment_id"] for r in EXP_ROWS)
            cur.execute(
                "SELECT experiment_id FROM experiment WHERE experiment_id IN (%s,%s,%s)", ids)
            report["pre_existing"] = [row[0] for row in cur.fetchall()]

            insert_sql = """INSERT IGNORE INTO experiment
                (experiment_id, title, hypothesis, rule_ids, primary_metric, benchmark,
                 pass_criteria, max_trials, trials_used, status, owner, notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
            for r in EXP_ROWS:
                params = (r["experiment_id"], r["title"], r["hypothesis"], r["rule_ids"],
                          r["primary_metric"], r["benchmark"], r["pass_criteria"],
                          r["max_trials"], r["trials_used"], r["status"], r["owner"], r["notes"])
                # 隔離斷言：唯一寫入面＝experiment 白名單表
                toks = insert_sql.strip().split()
                assert toks[0].upper() == "INSERT" and toks[3].lower() == ALLOWED_TABLE
                cur.execute(insert_sql, params)
                if cur.rowcount == 1:
                    report["inserted"].append(r["experiment_id"])
            conn.commit()

            # 全欄位回讀校驗（含 JSON 可解析性）
            cur.execute(
                """SELECT experiment_id, title, hypothesis, rule_ids, primary_metric, benchmark,
                          pass_criteria, max_trials, trials_used, status, owner, notes
                   FROM experiment WHERE experiment_id IN (%s,%s,%s) ORDER BY experiment_id""", ids)
            for row in cur.fetchall():
                (eid, title, hyp, rule_ids, pm, bench, pc, mt, tu, st, ow, notes) = row
                json.loads(rule_ids)  # JSON 合法性
                exp = next(x for x in EXP_ROWS if x["experiment_id"] == eid)
                ok = (title == exp["title"] and hyp == exp["hypothesis"]
                      and pm == exp["primary_metric"] and bench == exp["benchmark"]
                      and pc == exp["pass_criteria"] and mt == exp["max_trials"]
                      and tu == exp["trials_used"] and st == "pre_registered" and ow == exp["owner"]
                      and notes == exp["notes"])
                report["verified"][eid] = ("OK" if ok else "MISMATCH")
            assert all(v == "OK" for v in report["verified"].values()), "回讀校驗失敗"

            # 試驗登記冊全貌（供視圖生成器對帳）
            cur.execute("SELECT experiment_id, status FROM experiment ORDER BY experiment_id")
            report["registry_now"] = [{"id": a, "status": b} for a, b in cur.fetchall()]
            conn.commit()
            report["result"] = "OK"
    finally:
        conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("result") == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
