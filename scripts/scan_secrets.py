#!/usr/bin/env python3
"""scan_secrets.py — 推送前密鑰掃描（淨版 v2 規則）
用法: python3 scan_secrets.py <目錄或.zip>
規則: (api_key|token|secret|password|authorization)[=:] 後接 20+ 位裸值；
      REDACTED_* 佔位值視為淨；命中退出碼 1（阻止推送）。
每次 commit/push 前必跑；.git/hooks/pre-commit 已掛同款關卡。
"""
import re, zipfile, os, sys

PATTERNS = [
    re.compile(rb'(api[_-]?key|token|secret|password|authorization)\s*[=:]\s*["\']?([A-Za-z0-9_\-]{20,})', re.IGNORECASE),
]

def scan_bytes(name, data, hits):
    for pat in PATTERNS:
        for m in pat.finditer(data):
            val = m.group(2).decode('utf-8', 'replace')
            if 'REDACTED' in val.upper():
                continue
            s = m.group(0).decode('utf-8', 'replace')
            hits.append((name, (s[:8] + '***' + s[-4:]) if len(s) > 14 else s[:3] + '***'))

def main(target):
    hits, n = [], 0
    if target.endswith('.zip') and os.path.isfile(target):
        with zipfile.ZipFile(target) as z:
            for info in z.infolist():
                if not info.is_dir():
                    n += 1
                    scan_bytes(info.filename, z.read(info.filename), hits)
    else:
        for root, _, files in os.walk(target):
            for f in files:
                p = os.path.join(root, f)
                n += 1
                try:
                    scan_bytes(os.path.relpath(p, target), open(p, 'rb').read(), hits)
                except Exception:
                    pass
    if hits:
        print(f"[FAIL] {n} 檔案掃描, {len(hits)} 命中，禁止推送：")
        for fn, ex in hits:
            print(f"    {fn}  {ex}")
        sys.exit(1)
    print(f"[OK] {n} 檔案掃描, 0 命中 ✓ 可推送")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("用法: python3 scan_secrets.py <目錄或.zip>")
        sys.exit(2)
    main(sys.argv[1])
