# -*- coding: utf-8 -*-
"""后缀正名(量化约定 .OQ=NASDAQ/.N=NYSE/.AM=Arca+AMEX) + 17只单行日K历史重拉(单写者串行)"""
import sys, os, json, shutil, time, random
TOOL="/home/z/my-project/shared/全栈工具v1_三地行情抓取"; sys.path.insert(0, TOOL)
from market_fetcher import us_symbols, runner, tencent_api
FIX={'NOW':'N','NRG':'N','HPE':'N','ZETA':'N','UNH':'N','PFE':'N','SNOW':'N','ESTC':'N',
     'KKR':'N','QS':'N','OKLO':'N','SMR':'N','BMNR':'AM','XBI':'AM','CPER':'AM','GLDM':'AM','GDX':'AM'}
mapping=us_symbols.load_mapping()
patched=[]
for m in mapping:
    s=m['symbol']
    if s in FIX:
        old=m['kline_code']; new=f"us{s}.{FIX[s]}"
        # 备份并移除旧文件
        oldf="/home/z/my-project/shared/market_data/daily/"+old.lower().replace('.','_')+'.csv'
        if os.path.exists(oldf): shutil.move(oldf, "/tmp/kline_backup_20261010/"+os.path.basename(oldf))
        m.update(kline_code=new, suffix=FIX[s],
                 exchange={'N':'NYSE','AM':'NYSE Arca/AMEX','OQ':'NASDAQ'}[FIX[s]],
                 note="后缀按官方交易所正名(2026-10-10,原.OQ误锁)", last_verified="2026-10-10 14:3x",
                 verified=False)  # 先置False,探测通过再True
        patched.append((s,new,m['name_cn']))
with open(us_symbols.US_SYMBOLS_JSON,'w',encoding='utf-8') as f:
    json.dump(mapping,f,ensure_ascii=False,indent=1)
print("patched:",[p[0] for p in patched],flush=True)
# 逐只探测(回退链 .N→.OQ→.AM / .AM→.OQ→.N)
final={}
for s,new,name in patched:
    sfx=FIX[s]; order=[sfx]+[x for x in ('OQ','N','AM') if x!=sfx]
    ok_code=None
    for cand in order:
        code=f"us{s}.{cand}"
        try:
            df=tencent_api.fetch_kline(code,count=5)
            if df is not None and len(df)>=3: ok_code=(code,cand,len(df)); break
        except Exception: pass
        time.sleep(0.4+random.random()*0.3)
    m2=[m for m in mapping if m['symbol']==s][0]
    if ok_code:
        m2.update(kline_code=ok_code[0], suffix=ok_code[1], verified=True,
                  note=f"后缀正名+回验{ok_code[2]}根(2026-10-10)")
        final[s]=ok_code[0]
    else:
        m2.update(verified=False, note="后缀正名后全链探测失败,待人工(2026-10-10)")
    time.sleep(0.5)
with open(us_symbols.US_SYMBOLS_JSON,'w',encoding='utf-8') as f:
    json.dump(mapping,f,ensure_ascii=False,indent=1)
print("verified:",{k:v for k,v in final.items()},flush=True)
# 250根重拉(单批串行,含已通过者; 名称取mapping)
mapping=us_symbols.load_mapping()
pool=[]
for m in mapping:
    if m['symbol'] in FIX and m['verified']:
        pool.append((m['kline_code'], m['name_cn']))
m1=runner.run_kline_batch({"后缀正名重拉":pool}, count=250, sleep=1.0)
runner.save_manifest(m1)
print(f"K线: ok={m1['ok']} thin={m1['thin']} fail={m1['fail']}",flush=True)
print("DONE",flush=True)
