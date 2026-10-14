# -*- coding: utf-8 -*-
"""E-P2-2 测试金字塔批次2 · E2E replay: 分层管道端到端重放与断链检测。
以子进程跑 scripts/data_layering.py(固定 runner, 无自订绕过), 沙箱内全流程:
  晋升(fx/klines 两域) → gold 视图 → 血统绿灯 → 篡改 bronze 报红 → 还原复绿 → 幂等重放。
"""
import json
import os
import subprocess
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(BASE, "scripts", "data_layering.py")

FX_WIDE = (
    "date,dxy,usdcny,hkdcny,fetched_at,source,source_level\n"
    "2026-10-08,99.10,6.70,7.84,ts,腾讯,官方直连\n"
    "2026-10-09,99.40,6.69,7.85,ts,腾讯,官方直连\n"
    "2026-10-10,99.64,6.6925,7.8473,ts,腾讯,官方直连\n"
)
KL = (
    "date,open,high,low,close,volume,code,name,fetched_at,source,source_level,grade\n"
    "2026-10-08,10.0,10.5,9.8,10.2,1000,usXXX.OQ,样例,ts,腾讯,第三方可靠来源,行情商\n"
    "2026-10-09,10.2,10.6,10.1,10.5,1200,usXXX.OQ,样例,ts,腾讯,第三方可靠来源,行情商\n"
)


def _run(args, cwd):
    return subprocess.run([sys.executable, SCRIPT] + args, cwd=cwd,
                          capture_output=True, text=True, timeout=120)


def _layer(src, root, domain, cwd):
    return _run(["--src", src, "--root", root, "--domain", domain], cwd)


def _verify(root, cwd):
    return _run(["--verify", "--src", root, "--root", root, "--domain", "x"], cwd)


@pytest.fixture()
def sandbox(tmp_path):
    (tmp_path / "src_fx").mkdir()
    (tmp_path / "src_fx" / "fx_matrix.csv").write_text(FX_WIDE, encoding="utf-8")
    (tmp_path / "src_kl").mkdir()
    (tmp_path / "src_kl" / "k1.csv").write_text(KL, encoding="utf-8")
    (tmp_path / "root").mkdir()
    return tmp_path


def test_e2e_replay_full_cycle(sandbox):
    cwd = str(sandbox)
    root = str(sandbox / "root")

    # 1) 两域晋升 → 退出码 0 且 gold 落地
    for src, dom in (("src_fx", "fx"), ("src_kl", "klines")):
        r = _layer(str(sandbox / src), root, dom, cwd)
        assert r.returncode == 0, r.stdout + r.stderr
        out = json.loads(r.stdout[r.stdout.index("{"):])
        assert out["result"] == "OK", r.stdout
    assert os.path.exists(sandbox / "root" / "gold" / "fx" / "latest_view_fx.csv")
    assert os.path.exists(sandbox / "root" / "gold" / "klines" / "latest_view_klines.csv")

    # 2) 全链血统绿灯
    v = _verify(root, cwd)
    assert v.returncode == 0, v.stdout
    assert json.loads(v.stdout[v.stdout.index("{"):])["ok"] is True

    # 3) 幂等重放: 源未变 → bronze unchanged
    r = _layer(str(sandbox / "src_fx"), root, "fx", cwd)
    out = json.loads(r.stdout[r.stdout.index("{"):])
    assert all(a["state"] == "unchanged" for a in out["actions"]["bronze"])

    # 4) 篡改 bronze 字节 → 断链报红(退出码非 0)
    bronze = sandbox / "root" / "bronze" / "fx" / "fx_matrix.csv"
    bronze.write_text(bronze.read_text(encoding="utf-8") + "2026-10-11,99.99,6.70,7.85,ts,x,x\n",
                      encoding="utf-8")
    v = _verify(root, cwd)
    assert v.returncode != 0, "篡改 bronze 后 verify 必须报红"
    rep = json.loads(v.stdout[v.stdout.index("{"):])
    assert rep["ok"] is False and rep["layers"]["bronze"]["broken"]

    # 5) 还原 → 复绿
    bronze.write_text(FX_WIDE, encoding="utf-8")
    v = _verify(root, cwd)
    assert v.returncode == 0 and json.loads(v.stdout[v.stdout.index("{"):])["ok"] is True
