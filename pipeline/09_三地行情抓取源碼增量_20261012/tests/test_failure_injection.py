# -*- coding: utf-8 -*-
"""P2-2 测试金字塔 · 批次1: 故障注入测试 (failure injection)
=========================================================
定位: 金字塔下层单元测试之上的"恶意层" —— 主动注入崩溃/腐化,
验证 P0-1 原子写入语义与 P0-4 缺失显性化语义在坏情况下仍成立:
  ① os.replace 中途失败 → 目标档不出现、无 .tmp_ 残留;
  ② writer 中途抛错 → 同上;
  ③ _SUCCESS 侧车被写坏 → 读者显性报告损坏, 不静默当作有效批次;
  ④ 批内文件事后被篡改 → verify_batch 报 corrupted。
"""
import json
import os

import pytest

from market_fetcher import atomic_io


@pytest.fixture()
def batch_dir(tmp_path):
    d = tmp_path / "batch"
    d.mkdir()
    return str(d)


# ── ① os.replace 失败注入 ──────────────────────────────────
def test_replace_failure_leaves_no_target_and_no_tmp(batch_dir, monkeypatch):
    target = os.path.join(batch_dir, "out.csv")

    def boom(src, dst):
        raise OSError("ENOSPC: 注入磁盘满")

    monkeypatch.setattr(atomic_io.os, "replace", boom)
    with pytest.raises(OSError):
        atomic_io.atomic_write_text(target, "data")
    assert not os.path.exists(target), "目标档不应存在"
    residue = [n for n in os.listdir(batch_dir) if n.startswith(atomic_io.TMP_PREFIX)]
    assert not residue, f"临时档残留: {residue}"


# ── ② writer 中途抛错注入 ──────────────────────────────────
def test_writer_failure_cleans_tmp(batch_dir, monkeypatch):
    target = os.path.join(batch_dir, "out.json")

    def half_writer(f):
        f.write(b'{"partial":')
        raise RuntimeError("注入: 写入中途崩溃")

    with pytest.raises(RuntimeError):
        atomic_io.atomic_write(target, half_writer, mode="wb")
    assert not os.path.exists(target)
    residue = [n for n in os.listdir(batch_dir) if n.startswith(atomic_io.TMP_PREFIX)]
    assert not residue, f"临时档残留: {residue}"


# ── ③ _SUCCESS 腐化注入: 显性损坏, 不静默 ───────────────────
def test_corrupt_success_sidecar_is_explicit(batch_dir):
    f1 = os.path.join(batch_dir, "a.csv")
    atomic_io.atomic_write_text(f1, "x\n")
    atomic_io.write_batch_success(batch_dir, [f1], kind="test")
    assert atomic_io.verify_batch(batch_dir)["complete"] is True
    # 写坏侧车
    sc = os.path.join(batch_dir, atomic_io.SUCCESS_NAME)
    atomic_io.atomic_write_text(sc, "{corrupt!! 半截 JSON")
    assert atomic_io.read_batch_success(batch_dir) is None, \
        "腐化侧车不得被静默读作有效清单"
    rep = atomic_io.verify_batch(batch_dir)
    assert rep["batch_present"] is False or rep["complete"] is False, \
        "腐化侧车必须显性报告不完整"


# ── ④ 批内文件事后篡改注入: sha 校验必须报红 ─────────────────
def test_verify_batch_detects_tampered_file(batch_dir, monkeypatch):
    f1 = os.path.join(batch_dir, "a.csv")
    atomic_io.atomic_write_text(f1, "v1\n")
    # API 约定: files 收绝对路径(见 write_batch_success 的 abspath)
    atomic_io.write_batch_success(batch_dir, [f1], kind="test")
    # 绕过原子写直接篡改(模拟入侵/半写), 并把 mtime 拉回旧值防 fresh 判定
    with open(f1, "a", encoding="utf-8") as f:
        f.write("tampered\n")
    old = os.path.getmtime(os.path.join(batch_dir, atomic_io.SUCCESS_NAME))
    os.utime(f1, (old - 10, old - 10))
    rep = atomic_io.verify_batch(batch_dir)
    assert rep["complete"] is False and rep["corrupted"], \
        f"篡改未被检出: {rep}"


# ── ⑤ 缺失显性化: 引用文件缺席必须报 absent, 不许绿 ─────────
def test_verify_batch_reports_missing_file(batch_dir):
    f1 = os.path.join(batch_dir, "a.csv")
    fg = os.path.join(batch_dir, "ghost.csv")
    atomic_io.atomic_write_text(f1, "x\n")
    atomic_io.atomic_write_text(fg, "g\n")
    atomic_io.write_batch_success(batch_dir, [f1, fg], kind="test")
    os.utime(f1, (0, 0))  # 置旧, 只观察缺席维度
    os.remove(fg)         # 批内文件事后消失
    rep = atomic_io.verify_batch(batch_dir)
    assert rep["complete"] is False, f"缺席文件未被显性化: {rep}"
    assert any(m.get("reason") == "missing" for m in rep["mismatches"]), \
        f"缺席文件应列名报告: {rep['mismatches']}"
