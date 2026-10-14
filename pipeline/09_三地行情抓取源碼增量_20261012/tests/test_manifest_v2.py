# -*- coding: utf-8 -*-
"""Manifest v2 契约测试 (E-P1-1: 新增产出 100% v2 字段)。"""
import json
import os

from market_fetcher import manifest_v2, runner


def _fake_manifest_with_files(tmp_root):
    """构造带两个数据文件的 v1 形态 manifest, 再过 build_v2。"""
    import pandas as pd
    from market_fetcher import storage
    df = pd.DataFrame({"date": ["2026-10-10"], "close": [1.0]})
    p1 = storage.save_csv(df, os.path.join(tmp_root, "daily", "usT.A.csv"),
                          "2026-10-10T10:00:00", "src")
    p2 = storage.save_json({"v": 1}, os.path.join(tmp_root, "latest.csv"))
    m = {"type": "kline_batch", "run_ts": "x",
         "kline": {"results": [{"code": "usT", "status": "ok", "rows": 1,
                                "last_date": "2026-10-10", "path": p1},
                               {"code": "usB", "status": "fail", "rows": 0,
                                "last_date": None}]},
         "extra": {"path": p2, "status": "ok"}}
    return m, p1, p2


def test_build_v2_core_fields(tmp_path):
    root = str(tmp_path / "data")
    os.makedirs(root)
    m, _, _ = _fake_manifest_with_files(root)
    m2 = manifest_v2.build_v2(m, root, str(tmp_path), run_id="run_x_kline_batch")
    assert m2["schema_version"] == 2
    assert m2["run_id"] == "run_x_kline_batch"
    assert m2["ts_utc"].endswith("+00:00")
    assert m2["ts_hkt"].endswith("+08:00")
    assert m2["quality_status"] in ("good", "warn", "bad")
    assert isinstance(m2["code_fingerprint"], str) and len(m2["code_fingerprint"]) == 64


def test_build_v2_data_files_sha256(tmp_path):
    import hashlib
    root = str(tmp_path / "data")
    os.makedirs(root)
    m, p1, p2 = _fake_manifest_with_files(root)
    m2 = manifest_v2.build_v2(m, root, str(tmp_path))
    by_path = {f["path"]: f for f in m2["data_files"]}
    # data_files["path"] 为相对 data_root 的相对路径(v2 契约)
    assert "daily/usT.A.csv" in by_path and "latest.csv" in by_path
    for p, f in by_path.items():
        h = hashlib.sha256(open(os.path.join(root, p), "rb").read()).hexdigest()
        assert f["sha256"] == h


def test_build_v2_quality_from_statuses(tmp_path):
    root = str(tmp_path / "data")
    os.makedirs(root)
    m, _, _ = _fake_manifest_with_files(root)  # 1 ok + 1 fail -> bad
    m2 = manifest_v2.build_v2(m, root, str(tmp_path))
    assert m2["quality_status"] == "bad"


def test_build_v2_mutable_pointer_flag(tmp_path):
    root = str(tmp_path / "data")
    os.makedirs(root)
    m, _, p2 = _fake_manifest_with_files(root)
    m2 = manifest_v2.build_v2(m, root, str(tmp_path))
    f = {x["path"]: x for x in m2["data_files"]}["latest.csv"]  # F-4 可变指针
    assert f["mutable_pointer"] is True


def test_archive_run_writes_success_and_prunes(tmp_path):
    root = str(tmp_path / "data")
    os.makedirs(root)
    m, _, _ = _fake_manifest_with_files(root)
    m2 = manifest_v2.build_v2(m, root, str(tmp_path), run_id="run_arc_test")
    arc = manifest_v2.archive_run(m2, root)
    assert os.path.isdir(arc)
    assert os.path.exists(os.path.join(arc, "_SUCCESS"))
    # _SUCCESS 可解析且引用 run_id
    with open(os.path.join(arc, "_SUCCESS"), encoding="utf-8") as f:
        assert json.load(f)["run_id"] == "run_arc_test"


def test_save_manifest_end_to_end(tmp_path, monkeypatch):
    """端到端: save_manifest 产出的文件必须含 v2 全字段(验收: 新增产出 100% v2)。"""
    root = str(tmp_path / "data")
    os.makedirs(root)
    monkeypatch.setattr(runner, "DATA_ROOT", root)
    m, _, _ = _fake_manifest_with_files(root)
    p = runner.save_manifest(m, data_root=root)
    with open(p, encoding="utf-8") as f:
        saved = json.load(f)
    for k in ("schema_version", "run_id", "ts_utc", "ts_hkt", "code_commit",
              "code_fingerprint", "quality_status", "data_files"):
        assert k in saved, f"缺 v2 字段: {k}"
    assert saved["run_id"] == os.path.basename(p)[:-5]
