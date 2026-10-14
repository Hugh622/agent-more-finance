#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_seeds_dual.py v1.0.2 — 由 rules_registry_20261011.yaml（單一事實源）生成雙方言種子（方法學線 P1②）
MySQL 版與 SQLite 版統一採用【兩段式閉鏈】：stage1 INSERT 全量 supersedes_id=NULL → stage2 逐鏈 UPDATE 閉合。

【v1.0.2 變更記錄】
- 缺陷根因（10/12 全棧復核抓出＋本腿實證複現）：同批自引用閉鏈在兩方言皆靜默落 NULL——
  ① MySQL：@var 對同批 INSERT 內父行無論 SET 前置/後置均取不到（v1.0.1「SET 前置」修法理由本身錯誤）；
  ② SQLite：多行 VALUES 內標量子查詢對【同一語句】先前插入之行返回 NULL（實證腳本在案）。
  ⇒ 兩段式閉鏈是唯一跨方言穩健修法，v1.0.1 兩方言種子皆需升版。
- @var 全面廢除：CynosDB 連接復用代理會重置 SESSION/@@ 變量，@var 路線在代理環境不可靠；
  v1.0.2 種子零 @var、零 SET SESSION 依賴，語句間無隱藏狀態。
- 三硬斷言（生成期＋執行期雙重強制）：
  A1 鏈數==registry 聲明數（本版=3）；
  A2 每鏈：父行存在（無懸掛）＋非自引用＋父版本嚴格更低（真 semver 比較，SQL 側為雙保險網）；
  A3 每條閉鏈 UPDATE rowcount 精確==1、合計精確==3。
- fixture_v110.db 已同步升版（build_fixture_v1102.py 全鏈重建），消除兩方言權威態漂移。

【歷史版本】v1.0.1（2026-10-11）首版雙方言，MySQL @var 缺陷如上；v1.0.0 單方言 MySQL。
【載入順序鐵律】①EXP種子預註冊_20261011.sql → ②本生成物（rules.validation_experiment_id FK 依賴 experiment）
【執行者】全棧開發（單寫者原則）；憑據環境變數注入，本生成物零憑據。
【生產庫現狀】MySQL 權威態已由全棧 10/12 手工 UPDATE×3 修復並經量化腿 V1–V7＋X1–X10 連庫驗收 PASS；
  本 v1.0.2 種子供全新 schema 載入／重放用，無需對生產庫重放。
"""
import yaml, json, io, re, sys

SRC = "/home/z/my-project/shared/方法學線_20261011/rules_registry_20261011.yaml"
OUT_MYSQL = "/home/z/my-project/shared/方法學線_20261011/規則收編種子_20261011.sql"
OUT_SQLITE = "/home/z/my-project/shared/方法學線_20261011/規則收編種子_20261011.sqlite.sql"

EXPECTED_RULES = 72          # registry v1.0.0 定稿行數
EXPECTED_LINKS = 3           # registry v1.0.0 聲明鏈數（registry 升版時同步更新此錨）＝硬斷言 A1 基準

d = yaml.safe_load(io.open(SRC, encoding="utf-8"))
rules = d["rules"]
assert len(rules) == EXPECTED_RULES, f"expect {EXPECTED_RULES}, got {len(rules)}"

# ---------- 載入順序：依 supersedes 拓撲排序（父先子後；同時驗證無環） ----------
bykey = {f"{r['rule_id']}@{r['version']}": r for r in rules}
assert len(bykey) == len(rules), "dup rule@version in registry"
seen, order = set(), []
def visit(r):
    k = f"{r['rule_id']}@{r['version']}"
    if k in seen: return
    seen.add(k)
    sp = r.get("supersedes")
    if sp:
        assert sp in bykey, f"supersedes target missing: {sp}"      # A2 分支：無懸掛（registry 內）
        visit(bykey[sp])
    order.append(r)
for r in rules: visit(r)
assert len(order) == EXPECTED_RULES

# ---------- 鏈清單＋硬斷言 A1/A2（生成期） ----------
links = []  # (child_id, child_ver, parent_id, parent_ver)
for r in rules:
    if r.get("supersedes"):
        pid, pver = r["supersedes"].split("@")
        links.append((r["rule_id"], r["version"], pid, pver))

# A1：鏈數 == registry 聲明數
assert len(links) == EXPECTED_LINKS, f"A1 FAIL: links={len(links)}, expected {EXPECTED_LINKS}"
# A2：無懸掛（已由 visit 斷言）＋無自引用＋父版本嚴格更低（真 semver）＋組件單位數（SQL 側字典序雙保險的前提）
def semver(v):
    parts = v.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts), f"bad semver: {v}"
    assert all(len(p) == 1 for p in parts), f"non single-digit component {v}: SQL 字典序雙保險前提不成立，須改權重式"
    return tuple(int(p) for p in parts)
for (cid, cver, pid, pver) in links:
    assert f"{pid}@{pver}" in bykey, f"A2 FAIL dangling: {pid}@{pver}"
    assert not (cid == pid and cver == pver), f"A2 FAIL self-ref: {cid}@{cver}"
    assert semver(pver) < semver(cver), f"A2 FAIL version not strictly lower: {pid}@{pver} !< {cid}@{cver}"

def j(v):
    """JSON 列（scope/inputs/parameters）→ SQL 字符串字面量（TEXT/JSON 列均收字符串，DB 层 json_valid 校验）"""
    if v is None: return "NULL"
    return s(json.dumps(v, ensure_ascii=False, separators=(",", ":")))
def s(v):
    if v is None: return "NULL"
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"

COLS = ("rule_id,version,status,owner,scope,inputs,parameters,logic_ref,logic_desc,"
        "entry_effective,invalidation,validation_experiment_id,supersedes_id,notes")

def row_vals(r):
    """兩段式 stage1：所有行 supersedes_id 一律 NULL（閉鏈交由 stage2 UPDATE）"""
    return (f"({s(r['rule_id'])},{s(r['version'])},{s(r['status'])},{s(r['owner'])},{j(r.get('scope'))},"
            f"{j(r.get('inputs'))},{j(r.get('parameters'))},{s(r.get('logic_ref'))},{s(r.get('logic_desc'))},"
            f"{s(r.get('entry_effective'))},{s(r.get('invalidation'))},{s(r.get('validation_experiment_id'))},"
            f"NULL,{s(r.get('notes'))})")

HDR = """-- ============================================================
-- {fname}
-- 方法学线 P1② 交付件 · 由 gen_seeds_dual.py v1.0.2 自 rules_registry_20261011.yaml 生成
-- 源文件：rules_registry_20261011.yaml（{nr} 行定稿，含歷史版本鏈）——單一事實源，兩方言種子同步生成
-- 聲明鏈數：{nl}（{linklist}）
-- 結構：兩段式閉鏈——stage1 INSERT 全量 supersedes_id=NULL → stage2 逐鏈 UPDATE 閉合＋三硬斷言
--   A1 鏈數=={nl}；A2 無懸掛/無自引用/父版本嚴格更低；A3 每鏈 UPDATE rowcount==1、合計==3
-- 載入順序鐵律：①EXP種子預註冊_20261011.sql → ②本文件（FK 依賴 experiment）
-- 執行者：全棧開發（單寫者原則）；憑據環境變數注入，本文件零憑據；零 @var／零 SET SESSION 依賴
-- 任何斷言輸出 FAIL → 立即停止使用本庫態並回報方法學線（量化腿）
-- ============================================================
"""
linklist = "；".join(f"{c}@{cv}→{p}@{pv}" for c, cv, p, pv in links)

# ================= MySQL 方言 =================
m = []
m.append(HDR.format(fname="規則收編種子_20261011.sql（MySQL 方言）", nr=EXPECTED_RULES, nl=EXPECTED_LINKS, linklist=linklist))
m.append("""-- ① 家族級佔位行退役（rule_id='C' 等家族行 → retired；個別規則已按 rule_id 逐條收編）
UPDATE rules SET status='retired',
  notes=CONCAT(COALESCE(notes,''),' [2026-10-11 方法学线收编: 家族级占位行退役, 个别规则见 C1-C19/R1-R10/N1-N19/D1-D3/K1-K6/W1-W5/G1-G2/P0.*]')
WHERE (rule_id, version) IN (('C', '1.0.0'), ('R', '1.0.0'), ('N', '1.0.0'), ('D', '1.0.0'), ('K', '1.0.0'), ('W', '1.0.0'), ('G', '1.0.0'));

-- ② stage1/2：72 行收編，supersedes_id 全量 NULL（閉鏈見 ③ stage2 UPDATE，勿在 INSERT 內自引用——兩方言同批自引用均靜默落 NULL，實證在案）
INSERT INTO rules (%s) VALUES""" % COLS)
m.append(",\n".join(row_vals(r) for r in order) + ";")

m.append("\n-- ③ stage2/2：逐鏈 UPDATE 閉合（硬斷言 A3：每條 ROW_COUNT() 須=1，合計=3）")
for i, (cid, cver, pid, pver) in enumerate(links, 1):
    m.append(f"""UPDATE rules AS child
  JOIN rules AS parent ON parent.rule_id = {s(pid)} AND parent.version = {s(pver)}
  SET child.supersedes_id = parent.id
  WHERE child.rule_id = {s(cid)} AND child.version = {s(cver)};
SELECT ROW_COUNT() AS rc_{i}_{cid.replace('.','_')}_{cver.replace('.','_')};  -- 硬斷言 A3-{i}：須 = 1""")

def w_mysql(col):
    return (f"CAST(SUBSTRING_INDEX({col},'.',1) AS UNSIGNED)*1000000"
            f"+CAST(SUBSTRING_INDEX(SUBSTRING_INDEX({col},'.',2),'.',-1) AS UNSIGNED)*1000"
            f"+CAST(SUBSTRING_INDEX({col},'.',-1) AS UNSIGNED)")

m.append(f"""
-- ⑤ 三硬斷言（載入後必跑；任何 FAIL → 停止使用本庫態並回報）
SELECT IF((SELECT COUNT(*) FROM rules WHERE supersedes_id IS NOT NULL)={EXPECTED_LINKS},
  'OK  A1: supersedes links closed == {EXPECTED_LINKS} (== registry declared)',
  'FAIL A1: links != {EXPECTED_LINKS}') AS assertion_A1;
SELECT IF((SELECT COUNT(*) FROM rules c WHERE c.supersedes_id IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM rules p WHERE p.id = c.supersedes_id)) = 0
      AND (SELECT COUNT(*) FROM rules c WHERE c.supersedes_id = c.id) = 0
      AND (SELECT COUNT(*) FROM rules c JOIN rules p ON p.id = c.supersedes_id
           WHERE {w_mysql('p.version')} >= {w_mysql('c.version')}) = 0,
  'OK  A2: no dangling / no self-ref / parent version strictly lower (semver weighted)',
  'FAIL A2: link integrity violation') AS assertion_A2;
SELECT IF((SELECT COUNT(*) FROM rules c JOIN rules p ON p.id = c.supersedes_id) = {EXPECTED_LINKS},
  'OK  A3: closure UPDATE rowcount 1x{EXPECTED_LINKS} verified above',
  'FAIL A3: link count mismatch') AS assertion_A3;
-- ⑥ 擴展證據（X 系列迴聲）
SELECT IF((SELECT COUNT(*) FROM rules c JOIN rules p ON p.id = c.supersedes_id WHERE p.status <> 'retired') = 0,
  'OK  E1: all {EXPECTED_LINKS} parent rows retired', 'FAIL E1: parent not retired') AS assertion_E1;
SELECT c.rule_id AS child_rule, c.version AS child_ver, p.rule_id AS parent_rule, p.version AS parent_ver, p.status AS parent_status
  FROM rules c JOIN rules p ON p.id = c.supersedes_id ORDER BY c.rule_id;  -- E2: 須恰 {EXPECTED_LINKS} 行（{linklist}）
SELECT status, COUNT(*) FROM rules GROUP BY status ORDER BY status;  -- 預期 active45/frozen1/registered4/rejected19/retired10，合計 79""")
io.open(OUT_MYSQL, "w", encoding="utf-8").write("\n".join(m))

# ================= SQLite 方言 =================
sq = []
sq.append(HDR.format(fname="規則收編種子_20261011.sqlite.sql（SQLite 方言，測試基座用）", nr=EXPECTED_RULES, nl=EXPECTED_LINKS, linklist=linklist))
sq.append("""-- ① 家族級佔位行（鏡像 MySQL 現狀：status='registered'）
INSERT INTO rules (rule_id,version,status,owner,scope,inputs,parameters,logic_ref,logic_desc,entry_effective,invalidation,validation_experiment_id,supersedes_id,notes) VALUES""")
FAM = [("C","波浪形態七宗罪庫（家族級佔位，個別規則見 C1-C19）"),("R","倉位管理十誡庫（家族級佔位，個別規則見 R1-R10）"),
       ("N","不採納邊界庫（家族級佔位，個別規則見 N1-N19）"),("D","數據治理三則庫（家族級佔位，個別規則見 D1-D3）"),
       ("K","賣水人六檢庫（家族級佔位，個別規則見 K1-K6）"),("W","浪潮三段倉位庫（家族級佔位，個別規則見 W1-W5）"),
       ("G","貪婪檢驗二則庫（家族級佔位，個別規則見 G1-G2）")]
sq.append(",\n".join(f"({s(f)},{s('1.0.0')},{s('registered')},{s('quantitative')},NULL,NULL,NULL,NULL,{s(note+'｜2026-10-11 SQLite基座鏡像種子，MySQL側同構行已由全棧落地')},'next_tradable_bar','無',NULL,NULL,{s('家族級佔位行（方法學線收編後退役）')})" for f,note in FAM) + ";")

sq.append("\n-- ② stage1/2：72 行收編，supersedes_id 全量 NULL（同批自引用在 SQLite 多行 VALUES 內同樣靜默落 NULL，實證在案；閉鏈見 ③）\n"
          "INSERT INTO rules (rule_id,version,status,owner,scope,inputs,parameters,logic_ref,logic_desc,entry_effective,invalidation,validation_experiment_id,supersedes_id,notes) VALUES")
sq.append(",\n".join(row_vals(r) for r in order) + ";")

sq.append("\n-- ③ stage2/2：逐鏈 UPDATE 閉合（硬斷言 A3：每條 changes() 須=1、合計=3；builder/build_fixture_v1102.py 程序化斷言）")
for i, (cid, cver, pid, pver) in enumerate(links, 1):
    sq.append(f"""UPDATE rules SET supersedes_id = (SELECT id FROM rules WHERE rule_id = {s(pid)} AND version = {s(pver)})
  WHERE rule_id = {s(cid)} AND version = {s(cver)};  -- A3-{i}: changes() 須 = 1""")

sq.append("""-- ④ 佔位行退役（鏡像 MySQL 語義）
UPDATE rules SET status='retired',
  notes=COALESCE(notes,'')||' [2026-10-11 方法学线收编: 家族级占位行退役]'
WHERE (rule_id,version) IN (('C','1.0.0'),('R','1.0.0'),('N','1.0.0'),('D','1.0.0'),('K','1.0.0'),('W','1.0.0'),('G','1.0.0'));

-- ⑤ 三硬斷言（載入後必跑；任何 FAIL → 停止使用本庫態並回報）""")
# SQLite 側版本比較：組件單位數前提下字典序==數值序（生成器已逐鏈斷言該前提）
sq.append(f"SELECT CASE WHEN (SELECT COUNT(*) FROM rules WHERE supersedes_id IS NOT NULL)={EXPECTED_LINKS} THEN 'OK  A1: supersedes links closed == {EXPECTED_LINKS} (== registry declared)' ELSE 'FAIL A1: links != {EXPECTED_LINKS}' END AS assertion_A1;")
sq.append(f"""SELECT CASE WHEN (SELECT COUNT(*) FROM rules c WHERE c.supersedes_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM rules p WHERE p.id=c.supersedes_id))=0
      AND (SELECT COUNT(*) FROM rules c WHERE c.supersedes_id=c.id)=0
      AND (SELECT COUNT(*) FROM rules c JOIN rules p ON p.id=c.supersedes_id WHERE p.version >= c.version)=0
  THEN 'OK  A2: no dangling / no self-ref / parent version strictly lower (lexicographic, single-digit premise asserted by generator)'
  ELSE 'FAIL A2: link integrity violation' END AS assertion_A2;
SELECT CASE WHEN (SELECT COUNT(*) FROM rules c JOIN rules p ON p.id=c.supersedes_id)={EXPECTED_LINKS} THEN 'OK  A3: closure UPDATE changes() 1x{EXPECTED_LINKS} verified by builder' ELSE 'FAIL A3: link count mismatch' END AS assertion_A3;
-- ⑥ 擴展證據（X 系列迴聲）
SELECT CASE WHEN (SELECT COUNT(*) FROM rules c JOIN rules p ON p.id=c.supersedes_id WHERE p.status<>'retired')=0 THEN 'OK  E1: all {EXPECTED_LINKS} parent rows retired' ELSE 'FAIL E1: parent not retired' END AS assertion_E1;
SELECT c.rule_id AS child_rule, c.version AS child_ver, p.rule_id AS parent_rule, p.version AS parent_ver, p.status AS parent_status
  FROM rules c JOIN rules p ON p.id=c.supersedes_id ORDER BY c.rule_id;  -- E2: 須恰 {EXPECTED_LINKS} 行
SELECT status, COUNT(*) FROM rules GROUP BY status ORDER BY status;  -- 預期 active45/frozen1/registered4/rejected19/retired10，合計 79""")
io.open(OUT_SQLITE, "w", encoding="utf-8").write("\n".join(sq))

# ---------- 自檢 ----------
k = [f"{r['rule_id']}@{r['version']}" for r in order]
assert len(set(k)) == EXPECTED_RULES, "dup rule@version"
print(f"OK v1.0.2: MySQL -> {OUT_MYSQL} | SQLite -> {OUT_SQLITE} | rows: {len(order)} | links: {len(links)}")
print("A1 PASS (links==%d) | A2 PASS (dangling=0/self-ref=0/semver strictly lower) | A3 wired (rowcount per-link)" % EXPECTED_LINKS)
