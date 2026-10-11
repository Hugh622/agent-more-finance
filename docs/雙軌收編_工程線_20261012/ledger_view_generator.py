#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E-P1-2 雙軌收編（工程線）：紙面執行台賬 → 資料庫生成的閱讀視圖
================================================================
定案：warren_learning_db（MySQL 九表）＝唯一事實主檔；本生成器只讀，
將試驗登記冊／規則註冊冊／標的主檔／凍結快照渲染為 Markdown 閱讀視圖。
憑據只經環境變數注入（DB_*），本檔零硬編碼，可直接入倉（守則 SOP）。
每次周檢/收編後重跑刷新；輸出固定路徑由第一參數指定。
"""
import os
import sys
import json
import hashlib
import pymysql

REQUIRED_ENV = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]


def esc(v):
    if v is None:
        return "—"
    s = str(v).replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= 120 else s[:117] + "…"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: ledger_view_generator.py <output.md>")
        return 2
    out_path = sys.argv[1]
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(json.dumps({"error": f"MISSING_ENV: {missing}"}))
        return 2
    conn = pymysql.connect(
        host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"], charset="utf8mb4",
        connect_timeout=15, read_timeout=60, write_timeout=60,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            assert cur.fetchone()[0] == os.environ["DB_NAME"], "未連上目標庫"

            cur.execute("""SELECT experiment_id, title, hypothesis, rule_ids, primary_metric,
                                  benchmark, pass_criteria, max_trials, trials_used, status,
                                  owner, notes FROM experiment ORDER BY experiment_id""")
            experiments = cur.fetchall()

            cur.execute("""SELECT rule_id, version, status, owner, scope, logic_ref, logic_desc,
                                  invalidation, notes FROM rules ORDER BY rule_id, version""")
            rules = cur.fetchall()

            cur.execute("""SELECT instrument_id, symbol_current, name, market, currency,
                                  status, notes FROM instrument_master
                           ORDER BY market, symbol_current""")
            instruments = cur.fetchall()

            cur.execute("""SELECT snapshot_id, instrument_id, as_of_time, as_of_tz, source,
                                  adjustment_flag, quality_status, missing_status, run_id, notes
                           FROM market_snapshot ORDER BY snapshot_id""")
            snapshots = cur.fetchall()
    finally:
        conn.close()

    L = []
    L.append("# 纸面执行台账 · DB 阅读视图（机器生成）")
    L.append("")
    L.append("> **性质**：本文件由 `ledger_view_generator.py`（只读）从唯一事实主档 **warren_learning_db**（MySQL 九表）实时渲染，"
             "属 E-P1-2 双轨收编产物；人工请勿直接编辑本文件。")
    L.append(f"> **生成时刻**：{__import__('datetime').datetime.now(__import__('datetime').timezone.utc):%Y-%m-%d %H:%M:%S} UTC ｜ **主档**：{os.environ['DB_NAME']}@{os.environ['DB_HOST']}")
    L.append(f"> **内容摘要指纹**：sha256(experiment×{len(experiments)}, rules×{len(rules)}, "
             f"instrument×{len(instruments)}, snapshot×{len(snapshots)}) = "
             f"{hashlib.sha256(json.dumps([len(experiments), len(rules), len(instruments), len(snapshots)]).encode()).hexdigest()[:16]}")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §A 试验登记册 experiment（预注册先行 · DSR/PBO 试验次数底册）")
    L.append("")
    L.append("| ID | 状态 | 拥有腿 | 标题 | 预算(用/额) | rule_ids |")
    L.append("|---|---|---|---|---|---|")
    for (eid, title, _h, rule_ids, _pm, _b, _p, mt, tu, st, ow, _n) in experiments:
        seed_tag = "（SEED 示范）" if "SEED" in eid else ""
        L.append(f"| {eid}{seed_tag} | {st} | {esc(ow)} | {esc(title)} | {tu}/{mt} | {esc(rule_ids)} |")
    L.append("")
    for (eid, title, hyp, _r, pm, bench, pc, _m, _t, _s, _o, notes) in experiments:
        if "SEED" in eid:
            continue
        L.append(f"### {eid} · {title}")
        L.append(f"- **假设**：{hyp}")
        L.append(f"- **主指标**：{pm}")
        L.append(f"- **基准**：{bench}")
        L.append(f"- **GO/NO-GO**：{pc}")
        L.append(f"- **备注**：{notes}")
        L.append("")
    L.append("## §B 规则注册册 rules（混合模式：YAML 元数据 + Python 主体）")
    L.append("")
    L.append("| rule_id | 版本 | 状态 | 拥有腿 | scope | logic_ref | 摘要 |")
    L.append("|---|---|---|---|---|---|---|")
    for (rid, ver, st, ow, scope, lref, ldesc, _inv, _n) in rules:
        L.append(f"| {rid} | {ver} | {st} | {esc(ow)} | {esc(scope)} | {esc(lref)} | {esc(ldesc)} |")
    L.append("")
    L.append("## §C 标的主档 instrument_master")
    L.append("")
    L.append("| instrument_id | 现用代码 | 名称 | 市场 | 币种 | 池内状态 | 备注 |")
    L.append("|---|---|---|---|---|---|---|")
    for (iid, sym, name, mk, cur_, st, notes) in instruments:
        L.append(f"| {iid} | {sym} | {esc(name)} | {mk} | {cur_} | {st} | {esc(notes)} |")
    L.append("")
    L.append("## §D 数据冻结层 market_snapshot（可重放最小集）")
    L.append("")
    L.append("| snapshot_id | 标的 | as_of(UTC) | 原时区 | 来源 | 复权 | 质量 | 缺失态 | run_id |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for (sid, iid, t, tz, src, adj, q, ms, run, _n) in snapshots:
        L.append(f"| {sid} | {iid} | {t} | {tz} | {esc(src)} | {adj} | {q} | {esc(ms)} | {run} |")
    L.append("")
    L.append("## §E 过渡区（phase-2 迁移前人读条目）")
    L.append("")
    L.append("纸面令 P-001~P-013、终审执行计划总表、判例增补等**人读条目**在 10/16 台账 v2 正式收编前，")
    L.append("仍以《纸面执行台账_v1.1_20261010.md》为过渡阅读层（该册自 2026-10-12 起同为视图性质）；")
    L.append("增量记账一律**先入 DB 后刷视图**，phase-2 收编后订单五表（signal/decision/paper_order/paper_fill/position_lot）"
             "入册，本区缩为纯指针。")
    L.append("")
    L.append("---")
    L.append("")
    L.append("*本视图为模型打磨阶段的纸面记录体系之一部分，全部条目无真实成交，不构成投资建议。*")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(json.dumps({"result": "OK", "out": out_path,
                      "counts": {"experiment": len(experiments), "rules": len(rules),
                                 "instrument": len(instruments), "snapshot": len(snapshots)}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
