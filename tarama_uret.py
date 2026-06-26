#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3, json, os
from datetime import datetime, timedelta

DB = "/root/kap_bot/radar.db"
OUT = "/root/radae/tarama.json"

def d8(t):
    if not t or len(t) < 10:
        return "00000000"
    return t[6:10] + t[3:5] + t[0:2]

bugun = datetime.now()
def esik(ay):
    return (bugun - timedelta(days=ay*30)).strftime("%Y%m%d")

DONEMLER = {"1ay": 1, "3ay": 3, "6ay": 6, "9ay": 9, "12ay": 12}

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

veri = {}
for r in con.execute("SELECT hisse, yatirimci, tarih, oran FROM ortaklik WHERE yatirimci!='DİĞER' AND oran IS NOT NULL"):
    veri.setdefault(r["hisse"], {}).setdefault(r["yatirimci"], []).append((d8(r["tarih"]), r["oran"]))
for h in veri:
    for y in veri[h]:
        veri[h][y].sort()

sonuc = {}
for dad, ay in DONEMLER.items():
    es = esik(ay)
    artiran = []; azaltan = []
    for h in veri:
        for y, kayitlar in veri[h].items():
            dk = [k for k in kayitlar if k[0] >= es]
            if len(dk) < 2: continue
            ilk = dk[0][1]; son = dk[-1][1]; fark = round(son - ilk, 2)
            if fark >= 1:
                artiran.append({"hisse": h, "ortak": y, "ilk": ilk, "son": son, "fark": fark})
            elif fark <= -1:
                azaltan.append({"hisse": h, "ortak": y, "ilk": ilk, "son": son, "fark": fark})
    artiran.sort(key=lambda x: -x["fark"])
    azaltan.sort(key=lambda x: x["fark"])
    sonuc[f"artiran_{dad}"] = artiran[:100]
    sonuc[f"azaltan_{dad}"] = azaltan[:100]

surekli = []
for h in veri:
    for y, kayitlar in veri[h].items():
        son12 = [k for k in kayitlar if k[0] >= esik(12)]
        if len(son12) < 3: continue
        oranlar = [k[1] for k in son12]
        artislar = all(oranlar[i] >= oranlar[i-1] for i in range(1, len(oranlar)))
        ga = oranlar[-1] - oranlar[0]
        if artislar and ga >= 1:
            surekli.append({"hisse": h, "ortak": y, "ilk": oranlar[0],
                            "son": oranlar[-1], "fark": round(ga, 2), "adim": len(son12)})
surekli.sort(key=lambda x: -x["fark"])
sonuc["surekli_artiran"] = surekli[:100]

az_dolasim = []; fii = {}
for r in con.execute("SELECT hisse, tarih, oran FROM fiili_dolasim WHERE oran IS NOT NULL"):
    fii.setdefault(r["hisse"], []).append((d8(r["tarih"]), r["oran"]))
for h, kayitlar in fii.items():
    kayitlar.sort()
    guncel = kayitlar[-1][1]
    if guncel is not None and guncel <= 30:
        az_dolasim.append({"hisse": h, "dolasim": guncel})
az_dolasim.sort(key=lambda x: x["dolasim"])
sonuc["az_dolasimli"] = az_dolasim[:150]

con.close()
data = {
    "guncelleme": bugun.strftime("%Y-%m-%d %H:%M"),
    "donemler": list(DONEMLER.keys()),
    "filtreler": list(sonuc.keys()),
    "veri": sonuc,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
print(f"Tarama yazildi: {len(sonuc)} filtre")
for k in sonuc:
    print(f"  {k}: {len(sonuc[k])} kayit")
print(f"Dosya boyutu: {os.path.getsize(OUT)/1024:.0f} KB")
