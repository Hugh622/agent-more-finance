#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_fixture_v1102.py — fixture_v110.db 同步升版重建器（方法學線 P1② 收尾，配 gen_seeds_dual.py v1.0.2）
全鏈可復現：DDL → EXP種子預註冊 → 規則收編種子(v1.0.2 SQLite 方言) → 台賬遷移種子 → P2 回寫釘檔 payload（含 created_at 時間線）。
執行【交付的種子文件本身】而非旁路邏輯，程序化三硬斷言；若檢測到舊版 fixture 備份則附加逐表邏輯 diff（預期恰 3 行 supersedes_id 變化）。
工件查找順序＝腳本所在目錄 → shared/方法學線_20261011/，兩處交付一致即可復現。
"""
import json, hashlib, os, re, sqlite3, sys, tempfile

SHARED = "/home/z/my-project/shared/方法學線_20261011"
PRIVATE_ARCHIVE = "/home/z/my-project/agents/6a852d5ae176869046aa8e8d/methodology_1011/archive_v101"
EXPECTED_LINKS = 3

def find(name):
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (here, SHARED):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    sys.exit(f"artifact not found: {name}")

def semver(v):
    return tuple(int(p) for p in v.split("."))

def split_statements(sql):
    buf, out = [], []
    for line in sql.splitlines():
        buf.append(line)
        s = "\n".join(buf)
        if sqlite3.complete_statement(s):
            out.append(s)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        out.append(tail)
    return out

def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def table_rows(cur, t):
    cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})")]
    pk = cols[0]
    cur.execute(f"SELECT {','.join(cols)} FROM {t} ORDER BY {pk}")
    return {tuple(r[:1]): dict(zip(cols, r)) for r in cur.fetchall()}, cols

def logical_diff(old_db, new_db):
    o = sqlite3.connect(old_db); oc = o.cursor()
    n = sqlite3.connect(new_db); nc = n.cursor()
    tabs = [r[0] for r in oc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    ntabs = [r[0] for r in nc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    assert tabs == ntabs, "table sets differ"
    diffs = []
    for t in tabs:
        do, _ = table_rows(oc, t)
        dn, _ = table_rows(nc, t)
        assert set(do) == set(dn), f"{t}: key sets differ"
        for k in sorted(set(do) & set(dn)):
            if do[k] != dn[k]:
                changed = {c: (do[k][c], dn[k][c]) for c in do[k] if do[k][c] != dn[k][c]}
                diffs.append((t, k, changed))
    o.close(); n.close()
    return diffs

def build(out_path):
    con = sqlite3.connect(out_path)
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()
    # ① DDL
    cur.executescript(open(find("SQLite九表測試基座_DDL_20261011.sql"), encoding="utf-8").read())
    # ② EXP 種子預註冊（時序鐵律：先於 rules FK 依賴）
    cur.executescript(open(find("EXP種子預註冊_20261011.sql"), encoding="utf-8").read())
    # ③ 規則收編種子 v1.0.2（逐語句執行以捕獲 rowcount——A3）
    # 注：sqlite3_complete 會把純註釋塊與其後語句合併為同一 buffer——必須剝離整行註釋後執行，
    #     閉鏈 UPDATE 用「內容檢測」捕獲 rowcount（不得錨定語句開頭，否則註釋合併後整段被跳過＝空轉通過）。
    stmts = split_statements(open(find("規則收編種子_20261011.sqlite.sql"), encoding="utf-8").read())
    updates = 0
    for st in stmts:
        body = "\n".join(l for l in st.splitlines() if not l.lstrip().startswith("--")).strip()
        if not body:
            continue
        is_closure = "UPDATE rules SET supersedes_id" in body
        cur.execute(body)
        if is_closure:
            rc = cur.rowcount
            updates += rc
            assert rc == 1, f"A3 FAIL: closure UPDATE rowcount={rc} (expect 1) :: {body[:80]}"
        elif body.upper().startswith("SELECT"):
            for row in cur.fetchall():
                txt = " | ".join(str(c) for c in row)
                if "FAIL" in txt:
                    raise AssertionError(f"seed acceptance FAIL: {txt}")
                if txt.startswith(("OK", "P0.", "active", "frozen", "registered", "rejected", "retired")):
                    print("  seed assert:", txt)
    assert updates == EXPECTED_LINKS, f"A3 FAIL: total closure updates={updates}"
    print(f"A3 PASS: closure UPDATE rowcount 1x{EXPECTED_LINKS}, total=={EXPECTED_LINKS}")
    # ④ 台賬遷移種子（中立方言）
    cur.executescript(open(find("台賬遷移種子_20261011_v101.sql"), encoding="utf-8").read())
    # ⑤ P2 回寫釘檔 payload（歷史事實原樣回放，含 created_at 時間線）
    pin = json.load(open(find("fixture_writeback_20261012.json"), encoding="utf-8"))
    for r in pin["rows"]:
        cur.execute("UPDATE experiment SET status=?, trials_used=?, finished_at=?, result_summary=?, created_at=? WHERE experiment_id=?",
                    (r["status"], r["trials_used"], r["finished_at"], r["result_summary"], r["created_at"], r["experiment_id"]))
        assert cur.rowcount == 1, f"writeback miss: {r['experiment_id']}"
    for k, ts in pin["created_at_pins"]["rules"].items():
        rid, ver = k.rsplit("@", 1)
        cur.execute("UPDATE rules SET created_at=? WHERE rule_id=? AND version=?", (ts, rid, ver))
        assert cur.rowcount == 1, f"rules created_at pin miss: {k}"
    for did, ts in pin["created_at_pins"]["decision"].items():
        cur.execute("UPDATE decision SET created_at=? WHERE decision_id=?", (ts, did))
        assert cur.rowcount == 1, f"decision created_at pin miss: {did}"
    con.commit()

    # ---------- 三硬斷言（DB 權威態層） ----------
    n_rules = cur.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    assert n_rules == 79, f"rules rows={n_rules}"
    n_links = cur.execute("SELECT COUNT(*) FROM rules WHERE supersedes_id IS NOT NULL").fetchone()[0]
    assert n_links == EXPECTED_LINKS, f"A1 FAIL: links={n_links}"
    print("A1 PASS: links closed == 3")
    n_dang = cur.execute("SELECT COUNT(*) FROM rules c WHERE c.supersedes_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM rules p WHERE p.id=c.supersedes_id)").fetchone()[0]
    n_self = cur.execute("SELECT COUNT(*) FROM rules c WHERE c.supersedes_id=c.id").fetchone()[0]
    pairs = cur.execute("SELECT c.rule_id,c.version,p.rule_id,p.version,p.status FROM rules c JOIN rules p ON p.id=c.supersedes_id").fetchall()
    n_semver = sum(1 for _, cv, _, pv, _ in pairs if semver(pv) >= semver(cv))
    assert (n_dang, n_self, n_semver) == (0, 0, 0), f"A2 FAIL: dangling={n_dang} selfref={n_self} semver_violations={n_semver}"
    n_parent_retired = sum(1 for *_, ps in pairs if ps == "retired")
    print(f"A2 PASS: dangling=0, self-ref=0, parent version strictly lower (semver), parents retired x{n_parent_retired}")
    assert n_parent_retired == EXPECTED_LINKS and n_rules == 79
    # 權威態全面對帳
    tally = dict(cur.execute("SELECT status, COUNT(*) FROM rules GROUP BY status"))
    assert tally == {"active": 45, "frozen": 1, "registered": 4, "rejected": 19, "retired": 10}, f"tally={tally}"
    assert cur.execute("SELECT COUNT(*) FROM decision").fetchone()[0] == 17
    exp = cur.execute("SELECT experiment_id, status, result_summary FROM experiment ORDER BY experiment_id").fetchall()
    assert len(exp) == 3 and all(s == "completed" for _, s, _ in exp)
    for eid, _, rs in exp:
        pinned = next(r["result_summary"] for r in pin["rows"] if r["experiment_id"] == eid)
        assert rs == pinned, f"result_summary mismatch: {eid}"
    assert not cur.execute("PRAGMA foreign_key_check").fetchall()
    assert cur.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    print("totals PASS: rules 79 (active45/frozen1/registered4/rejected19/retired10) | decision 17 | experiment 3 completed | FK/integrity OK")
    con.close()

if __name__ == "__main__":
    old_path = os.path.join(PRIVATE_ARCHIVE, "fixture_v110.v101_nulllinks.db")
    h_old = sha256(old_path) if os.path.exists(old_path) else None
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture_v110.db")
    tmp = tempfile.mktemp(suffix=".db", dir=os.path.dirname(out_path))
    build(tmp)
    if h_old:
        diffs = logical_diff(old_path, tmp)
        print(f"-- logical diff old->new: {len(diffs)} row(s) changed")
        for t, k, ch in diffs:
            assert t == "rules" and set(ch) == {"supersedes_id"}, f"UNEXPECTED DIFF: {t} {k} {ch}"
            print(f"   rules[{k}] supersedes_id: {ch['supersedes_id'][0]} -> {ch['supersedes_id'][1]}")
        assert len(diffs) == EXPECTED_LINKS, "diff count != 3"
    else:
        print("-- old fixture backup not found; skip diff (assertions already enforced)")
    os.replace(tmp, out_path)
    h_new = sha256(out_path)
    print(f"fixture_v110.db upgraded at {out_path}")
    print(f"  sha256 old={h_old}")
    print(f"  sha256 new={h_new}")
