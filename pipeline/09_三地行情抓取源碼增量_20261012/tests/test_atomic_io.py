# -*- coding: utf-8 -*-
"""atomic_io 单元测试 (E-P0-3 CI 修复: 真 pytest 收集, 断言数>0)。"""
import json
import os


from market_fetcher import atomic_io


def test_atomic_write_json_roundtrip(tmp_path):
    p = str(tmp_path / "a" / "b.json")
    obj = {"k": [1, 2, 3], "s": "中文"}
    atomic_io.atomic_write_json(obj, p)
    with open(p, encoding="utf-8") as f:
        assert json.load(f) == obj


def test_atomic_write_creates_dirs(tmp_path):
    p = str(tmp_path / "x" / "y" / "z.txt")
    atomic_io.atomic_write_text(p, "hi")
    assert open(p, encoding="utf-8").read() == "hi"


def test_no_tmp_leftover(tmp_path):
    d = str(tmp_path / "d")
    for i in range(3):
        atomic_io.atomic_write_text(os.path.join(d, "f.txt"), f"v{i}")
    leftovers = [n for n in os.listdir(d) if n.startswith(atomic_io.TMP_PREFIX)]
    assert leftovers == []


def test_overwrite_keeps_last_complete_value(tmp_path):
    p = str(tmp_path / "o.txt")
    for i in range(5):
        atomic_io.atomic_write_text(p, str(i))
    assert open(p, encoding="utf-8").read() == "4"


def test_sha256_file_and_bytes_match(tmp_path):
    p = str(tmp_path / "bin.dat")
    data = b"\x00binary-data-\xff" * 17
    atomic_io.atomic_write_bytes(p, data)
    assert atomic_io.sha256_file(p) == atomic_io.sha256_bytes(data)


def test_batch_success_and_verify_complete(tmp_path):
    d = str(tmp_path / "batch")
    f1 = atomic_io.atomic_write_text(os.path.join(d, "1.csv"), "one")
    f2 = atomic_io.atomic_write_text(os.path.join(d, "2.csv"), "two")
    atomic_io.write_batch_success(d, [f1, f2], run_id="r1")
    v = atomic_io.verify_batch(d)
    assert v["complete"] is True and v["in_progress"] is False
    assert v["corrupted"] is False and v["files"] == 2


def test_verify_batch_detects_missing(tmp_path):
    d = str(tmp_path / "batch2")
    f1 = atomic_io.atomic_write_text(os.path.join(d, "1.csv"), "one")
    f2 = atomic_io.atomic_write_text(os.path.join(d, "2.csv"), "two")
    atomic_io.write_batch_success(d, [f1, f2])
    os.unlink(f1)
    v = atomic_io.verify_batch(d)
    assert v["complete"] is False
    assert any(m["reason"] == "missing" for m in v["mismatches"])


def test_verify_batch_detects_corruption(tmp_path):
    d = str(tmp_path / "batch3")
    f1 = atomic_io.atomic_write_text(os.path.join(d, "1.csv"), "one")
    atomic_io.write_batch_success(d, [f1])
    with open(f1, "w", encoding="utf-8") as f:
        f.write("tampered")  # 篡改内容(会刷新mtime), 再回拨模拟"标记后被改而未更新标记"
    old = os.path.getmtime(os.path.join(d, atomic_io.SUCCESS_NAME)) - 10
    os.utime(f1, (old, old))
    v = atomic_io.verify_batch(d)
    assert v["complete"] is False
    assert any(m["reason"] == "sha256_mismatch" for m in v["mismatches"])


def test_cleanup_stale_tmp(tmp_path):
    d = str(tmp_path / "c")
    os.makedirs(d)
    stale = os.path.join(d, ".tmp_stale_x")
    fresh = os.path.join(d, ".tmp_fresh_y")
    open(stale, "w").close()
    open(fresh, "w").close()
    old = os.path.getmtime(stale) - 25 * 3600
    os.utime(stale, (old, old))
    n = atomic_io.cleanup_stale_tmp(d, max_age_hours=24)
    assert n == 1
    assert os.path.exists(fresh) and not os.path.exists(stale)
