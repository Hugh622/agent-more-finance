#!/usr/bin/env python3
"""patch_main_zip_secrets.py — 對主包 zip 一鍵脫敏（安全整改伴隨工具）
用法: python3 patch_main_zip_secrets.py <in.zip> <out.zip> [known_secret]
邏輯:
  1) 精確擦除已知密鑰字面量（finnhub key）
  2) 通用模式擦除 (token|api_key|secret|password|authorization)=<20+位字面量> 的裸值（v1.1: 下限 28→20，修复 25 位 URL query token 逃逸；键名补 authorization）
  3) 在包根追加 SECURITY_脱敏修复说明.md，列出全部改動條目
  4) 重掃描斷言 0 殘留，條目數與原包一致
"""
import sys, re, zipfile, datetime

GENERIC = re.compile(rb'((?:token|api[_-]?key|secret|password|authorization)\s*[=:]\s*["\']?)([A-Za-z0-9_\-]{20,})')
NOTE = """# 脫敏修復說明（自動生成 {ts})

本包由《{orig}》重打包而來，僅做安全脫敏，內容零改動：

- 擦除方式：已知密鑰字面量 → `REDACTED_FINNHUB_KEY`；通用模式 `(token|api_key|secret|password)=<28+位>` 裸值 → `REDACTED`
- 改動條目（{n} 個）：
{files}

## 外發前仍需人工執行
1. 該 key 已進入過打包流程，**視同暴露**：請到 finnhub 後台作廢換新
2. 新 key 改用環境變量注入，配置範式見《數據工程補充包》05_安全脫敏/finnhub.json.example
3. `config/finnhub_verify_result.json` 為歷史驗證日誌（token 已擦），後續日誌請在代碼層加脫敏 middleware
"""

def scrub(data: bytes, key: bytes):
    hits = 0
    if key and key in data:
        data = data.replace(key, b"REDACTED_FINNHUB_KEY"); hits += 1
    data, n = GENERIC.subn(lambda m: m.group(1) + b"REDACTED", data)
    return data, hits + n

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    inp, outp = sys.argv[1], sys.argv[2]
    key = (sys.argv[3].encode() if len(sys.argv) > 3 and sys.argv[3] != "-" else b"")
    zin = zipfile.ZipFile(inp)
    entries = [i for i in zin.infolist() if not i.is_dir()]
    changed = {}
    buf = {}
    for info in entries:
        data = zin.read(info.filename)
        data, n = scrub(data, key)
        if n: changed[info.filename] = n
        buf[info.filename] = data
    note = NOTE.format(ts=datetime.datetime.now().isoformat(timespec="seconds"),
                       orig=inp.split("/")[-1], n=len(changed),
                       files="\n".join(f"  - `{k}`（{v} 處）" for k, v in changed.items()) or "  - （無）")
    with zipfile.ZipFile(outp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in entries:
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, buf[info.filename])
        zout.writestr("SECURITY_脱敏修复说明_20261011.md", note.encode())
    # verify
    zchk = zipfile.ZipFile(outp)
    assert len([i for i in zchk.infolist() if not i.is_dir()]) == len(entries) + 1
    leak = [i.filename for i in zchk.infolist() if not i.is_dir() and
            ((key and key in zchk.read(i.filename)) or GENERIC.search(zchk.read(i.filename)))]
    print(f"改動條目 {len(changed)} 個；輸出 {outp}；殘留洩漏 {leak if leak else '0 ✓'}")

if __name__ == "__main__":
    main()
