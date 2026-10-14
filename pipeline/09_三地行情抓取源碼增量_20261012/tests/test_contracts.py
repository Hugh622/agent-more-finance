# -*- coding: utf-8 -*-
"""E-P1-3 数据源契约测试（文件即合约）
=====================================
设计（P0 共识延伸）：契约文件（contracts/contract_*.json）即数据源输出规格的唯一声明，
测试引擎只做"契约→产物"的机械校验，不内嵌任何硬编码期望值：
  ① 契约自检：每份契约可解析、引擎必备字段齐全（防止契约本身腐烂）；
  ② 产物在场：artifact_glob 命中数 >= min_files；命中 0 且 allow_empty=false 必须 FAIL
    （缺失显性化，不许假绿；显式声明 allow_empty=true 才可 skip=not_available）；
  ③ 行级校验：required_columns 齐、column_rules 逐列、file_rules 逐文件（日期唯一/有序、
    OHLC 自洽、series_id 常量、le_column 跨列约束等）。
运行约定：pytest 以管道根为 cwd（conftest 已注入 sys.path）；数据根可用
MARKET_DATA_DIR 覆盖，默认 <管道根>/../market_data。
"""
import csv
import glob
import json
import os
import re

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKET_DATA = os.environ.get("MARKET_DATA_DIR") or os.path.join(
    os.path.dirname(BASE), "market_data")
CONTRACTS = sorted(glob.glob(os.path.join(BASE, "contracts", "contract_*.json")))
ENGINE_MIN_FIELDS = {"contract_id", "kind", "allow_empty", "min_files"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _hit_files(contract):
    globs = contract.get("artifact_globs") or [contract["artifact_glob"]]
    out = []
    for g in globs:
        out.extend(glob.glob(os.path.join(MARKET_DATA, g)))
    return sorted(set(out))


def _float(v):
    return float(str(v).strip())


def _check_cell(contract, col, v):
    """按 column_rules 校验单格；返回 None 或违规说明。"""
    rule = contract["column_rules"].get(col)
    if rule is None or v is None:
        return None
    v = str(v).strip()
    if rule.get("non_empty"):
        if not v:
            return "空值"
        return None
    if rule.get("format_date"):
        if not DATE_RE.fullmatch(v):
            return f"日期格式非 YYYY-MM-DD: {v!r}"
        return None
    if "float_gt" in rule:
        try:
            if not _float(v) > rule["float_gt"]:
                return f"值未 > {rule['float_gt']}: {v!r}"
        except ValueError:
            return f"非数值: {v!r}"
        return None
    if "float_ge" in rule:
        try:
            if not _float(v) >= rule["float_ge"]:
                return f"值未 >= {rule['float_ge']}: {v!r}"
        except ValueError:
            return f"非数值: {v!r}"
        return None
    if "float_parse" in rule:
        try:
            _float(v)
        except ValueError:
            return f"非数值: {v!r}"
        return None
    if "int_ge" in rule:
        try:
            if int(float(v)) < rule["int_ge"]:
                return f"值未 >= {rule['int_ge']}: {v!r}"
        except ValueError:
            return f"非整数: {v!r}"
        return None
    if "enum" in rule:
        if v not in rule["enum"]:
            return f"枚举外值: {v!r}"
        return None
    if "regex" in rule:
        if not re.fullmatch(rule["regex"], v):
            return f"不匹配 {rule['regex']}: {v!r}"
        return None
    if "prefix" in rule:
        if not any(v.lower().startswith(p) for p in rule["prefix"]):
            return f"前缀须在 {rule['prefix']}: {v!r}"
        return None
    if "market_prefix" in rule:
        mp = rule["market_prefix"]  # 需要同行的 market 值，行级处理，此处跳过
        return None
    return None


def _check_file(contract, path):
    """单文件契约校验；返回违规列表 [(文件, 摘要)]。"""
    errs = []
    with open(path, encoding=contract.get("encoding", "utf-8-sig")) as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        missing_cols = [c for c in contract["required_columns"] if c not in header]
        if missing_cols:
            return [(path, f"缺列: {missing_cols}")]
        rows = list(reader)

    mp = contract["column_rules"].get("code", {}).get("market_prefix")
    seen_dates, prev_date = set(), None
    seen_keys = set()
    constants = {c: None for c in contract.get("file_rules", {}).get("constant_per_file", [])}
    for i, row in enumerate(rows, 2):
        for col in contract["required_columns"]:
            rule = contract["column_rules"].get(col, {})
            if "market_prefix" in rule:
                want = mp.get(row.get("market", ""))
                ok = False
                if isinstance(want, list):
                    ok = any(str(row[col]).lower().startswith(p) for p in want)
                elif want:
                    ok = str(row[col]).lower().startswith(want)
                if not ok:
                    errs.append((path, f"行{i}: code/market 不匹配 "
                                       f"({row.get('market')}↔{row[col]})"))
                continue
            e = _check_cell(contract, col, row.get(col))
            if e:
                errs.append((path, f"行{i}[{col}]: {e}"))
        fr = contract.get("file_rules", {})
        if fr.get("date_unique") and "date" in row:
            d = str(row["date"]).strip()
            if d in seen_dates:
                errs.append((path, f"行{i}: date 重复 {d}"))
            seen_dates.add(d)
        if fr.get("date_sorted_asc") and "date" in row:
            d = str(row["date"]).strip()
            if prev_date and d < prev_date:
                errs.append((path, f"行{i}: 日期未升序 {prev_date}→{d}"))
            prev_date = d
        if fr.get("key_unique"):
            kv = tuple(str(row.get(c, "")).strip() for c in fr["key_unique"])
            if kv in seen_keys:
                errs.append((path, f"行{i}: 联合键重复 {dict(zip(fr['key_unique'], kv))}"))
            seen_keys.add(kv)
        if contract.get("file_rules", {}).get("ohlc_sane"):
            try:
                o, h, l, c = (_float(row[k]) for k in ("open", "high", "low", "close"))
                if not (h >= max(o, c) - 1e-9 and l <= min(o, c) + 1e-9 and h >= l):
                    errs.append((path, f"行{i}: OHLC 不自洽 "
                                       f"O{o} H{h} L{l} C{c}"))
            except (ValueError, KeyError):
                pass
        for c in constants:
            val = str(row.get(c, "")).strip()
            if constants[c] is None:
                constants[c] = val
            elif val != constants[c]:
                errs.append((path, f"行{i}: {c} 档内不恒定 "
                                   f"({constants[c]}→{val})"))
        for a, b in contract.get("file_rules", {}).get("le_column", {}).items():
            try:
                if _float(row[a]) > _float(row[b]):
                    errs.append((path, f"行{i}: {a}({row[a]})>{b}({row[b]})"))
            except ValueError:
                errs.append((path, f"行{i}: {a}/{b} 非整数"))
        if len(errs) > 20:  # 失败摘要截断，防报告爆炸
            errs.append((path, "…违规超 20 条，截断"))
            break
    if not rows and contract.get("min_rows", 1) > 0:
        errs.append((path, "零数据行（仅表头）"))
    return errs


# ── ① 契约自检 ─────────────────────────────────────────────
@pytest.mark.parametrize("cpath", CONTRACTS,
                         ids=[os.path.basename(p) for p in CONTRACTS])
def test_contract_self_valid(cpath):
    c = _load(cpath)
    missing = ENGINE_MIN_FIELDS - set(c)
    assert not missing, f"{os.path.basename(cpath)} 缺引擎字段: {missing}"
    assert c["kind"] in ("csv", "json"), f"未知 kind: {c['kind']}"
    assert isinstance(c["min_files"], int) and c["min_files"] >= 0
    globs = c.get("artifact_globs") or [c.get("artifact_glob")]
    assert all(globs), "契约须声明 artifact_glob 或 artifact_globs"
    assert not any(".." in g for g in globs), "契约 glob 禁止路径穿越"
    if c["kind"] == "csv":
        assert c.get("required_columns"), "csv 契约须声明 required_columns"
    else:
        assert c.get("required_keys"), "json 契约须声明 required_keys"


# ── ①b 域覆盖收口：数据域内不允许存在未签约产物 ──────────────
@pytest.mark.parametrize("domain", ["daily", "rates", "fx", "ah"])
def test_domain_fully_contracted(domain):
    """rates 曾暴露三种子格式漏签 —— 本测试保证域内每个文件都被
    至少一份契约 glob 覆盖（新增产物必须先签契约再落盘）。"""
    all_files = set(glob.glob(os.path.join(MARKET_DATA, f"{domain}/*.csv")))
    if not all_files:
        pytest.skip(f"domain_absent(not_available): {domain}")
    covered = set()
    for cpath in CONTRACTS:
        c = _load(cpath)
        covered.update(_hit_files(c))
    uncovered = sorted(f for f in all_files if f not in covered)
    assert not uncovered, f"{domain} 域存在未签约产物: {uncovered}"


# ── ② 产物在场（缺失显性化，不许假绿）──────────────────────
@pytest.mark.parametrize("cpath", CONTRACTS,
                         ids=[os.path.basename(p) for p in CONTRACTS])
def test_artifacts_present(cpath):
    c = _load(cpath)
    assert os.path.isdir(MARKET_DATA), f"数据根不存在: {MARKET_DATA}"
    files = _hit_files(c)
    if not files:
        if c["allow_empty"]:
            pytest.skip(f"artifact_absent(not_available): {c['artifact_glob']}")
        pytest.fail(f"契约 {c['contract_id']} 产物缺席: {c['artifact_glob']}")
    assert len(files) >= c["min_files"], \
        f"{c['contract_id']} 在场文件 {len(files)} < min_files {c['min_files']}"


# ── ③ 行级/结构校验 ────────────────────────────────────────
@pytest.mark.parametrize("cpath", CONTRACTS,
                         ids=[os.path.basename(p) for p in CONTRACTS])
def test_rows_conform(cpath):
    c = _load(cpath)
    files = _hit_files(c)
    assert files, f"{c['contract_id']} 无产物可校验"
    errs = []
    for path in files:
        if c["kind"] == "csv":
            errs.extend(_check_file(c, path))
        else:
            errs.extend(_check_json(c, path))
        if len(errs) > 20:
            break
    assert not errs, f"契约 {c['contract_id']} 违规 {len(errs)} 条: {errs[:8]}"


def _check_json(c, path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    errs = []
    for k in c["required_keys"]:
        if k not in data:
            errs.append((path, f"缺键: {k}"))
    for key, lr in c.get("list_rules", {}).items():
        lst = data.get(key)
        if not isinstance(lst, list) or len(lst) < lr.get("min_len", 0):
            errs.append((path, f"{key} 非列表或长度<{lr.get('min_len')}"))
            continue
        for i, item in enumerate(lst, 1):
            for rk in lr.get("item_required_keys", []):
                if rk not in item:
                    errs.append((path, f"{key}[{i}] 缺键: {rk}"))
            for rk, rules in lr.get("item_rules", {}).items():
                v = str(item.get(rk, "")).strip()
                if rules.get("format_date") and not DATE_RE.fullmatch(v):
                    errs.append((path, f"{key}[{i}].{rk} 日期异常: {v!r}"))
    return errs
