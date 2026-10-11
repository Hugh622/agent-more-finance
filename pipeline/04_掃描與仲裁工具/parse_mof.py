import csv, datetime

def rows(path):
    out = []
    with open(path, encoding='utf-8', errors='ignore') as f:
        r = csv.reader(f)
        for row in r:
            if not row or not row[0].strip() or '/' not in row[0]:
                continue
            try:
                d = datetime.date(*map(int, row[0].strip().split('/')))
            except Exception:
                continue
            vals = []
            for x in row[1:]:
                x = x.strip()
                try:
                    vals.append(float(x))
                except Exception:
                    vals.append(None)
            out.append((d, vals))
    return out

cols = [0, 4, 9, 11, 12, 13, 14]  # 1Y,5Y,10Y,20Y,25Y,30Y,40Y
names = ['1Y', '5Y', '10Y', '20Y', '25Y', '30Y', '40Y']

allrows = rows('jgbcme_all.csv')
cur = rows('jgbcme_cur.csv')

print("== curmonth (latest rows) ==")
for d, v in cur[-8:]:
    print(d, [v[i] for i in cols])

print("== key historical (1Y/5Y/10Y/20Y/25Y/30Y/40Y) ==")
want = ['2025-09-30', '2025-12-30', '2026-01-05', '2026-03-31', '2026-04-30',
        '2026-06-30', '2026-07-31', '2026-08-31']
idx = {d.isoformat(): v for d, v in allrows}
for w in sorted(want):
    if w in idx:
        print(w, [idx[w][i] for i in cols])
    else:
        print(w, 'MISSING')

print("== 2026 YTD extremes ==")
y26 = [(d, v) for d, v in allrows if d.year == 2026]
for name, i in [('10Y', 9), ('25Y', 12), ('30Y', 13), ('40Y', 14)]:
    vals = [(v[i], d) for d, v in y26 if v[i] is not None]
    if vals:
        mx = max(vals)
        print(f"2026 max {name}: {mx[0]} @ {mx[1]}")

print("== 2025 extremes (10Y/30Y) ==")
y25 = [(d, v) for d, v in allrows if d.year == 2025]
for name, i in [('10Y', 9), ('30Y', 13)]:
    vals = [(v[i], d) for d, v in y25 if v[i] is not None]
    if vals:
        mx = max(vals)
        print(f"2025 max {name}: {mx[0]} @ {mx[1]}")

print("== all.csv last row ==")
d, v = allrows[-1]
print(d, [v[i] for i in cols])
print("allrows total:", len(allrows))
