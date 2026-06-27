#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3, json, os
from datetime import datetime, timedelta

DB = "/root/kap_bot/radar.db"
OUT = "/root/radae/fon.json"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

son_tarih = con.execute("SELECT MAX(tarih) FROM fon_dagilim").fetchone()[0]
# ~1 ay onceki tarih (hisse agirligi degisimi icin)
onceki = con.execute(
    "SELECT MAX(tarih) FROM fon_dagilim WHERE tarih <= date(?, '-30 day')",
    (son_tarih,)).fetchone()[0]

# Guncel fon profili
guncel = {}
for r in con.execute("SELECT fon_kod, fon_ad, hisse, yabanci_hisse, portfoy_buyukluk, yatirimci_sayi FROM fon_dagilim WHERE tarih=?", (son_tarih,)):
    guncel[r["fon_kod"]] = {
        "kod": r["fon_kod"], "ad": r["fon_ad"],
        "hisse": r["hisse"], "yabanci": r["yabanci_hisse"],
        "buyukluk": r["portfoy_buyukluk"], "yatirimci": r["yatirimci_sayi"],
    }

# Onceki hisse oranlari (degisim icin)
onceki_hisse = {}
if onceki:
    for r in con.execute("SELECT fon_kod, hisse FROM fon_dagilim WHERE tarih=?", (onceki,)):
        onceki_hisse[r["fon_kod"]] = r["hisse"]

# Tum fonlar listesi (arama icin) - sade
fonlar = []
for kod, f in guncel.items():
    fonlar.append({
        "kod": kod, "ad": f["ad"],
        "hisse": round(f["hisse"], 1) if f["hisse"] is not None else 0,
        "buyukluk": f["buyukluk"], "yatirimci": f["yatirimci"],
    })

# Populer = en buyuk 30 fon
populer = sorted(fonlar, key=lambda x: -(x["buyukluk"] or 0))[:30]

# Hisseye yuklenen / kacan (sadece hisse fonu olanlar, >5% baz)
yuklenen = []; kacan = []
for kod, f in guncel.items():
    if f["hisse"] is None or kod not in onceki_hisse or onceki_hisse[kod] is None:
        continue
    fark = round(f["hisse"] - onceki_hisse[kod], 2)
    if f["hisse"] < 5:  # hisse fonu olmayanlari atla
        continue
    kayit = {"kod": kod, "ad": f["ad"], "onceki": round(onceki_hisse[kod],1),
             "simdi": round(f["hisse"],1), "fark": fark, "buyukluk": f["buyukluk"]}
    if fark >= 2:
        yuklenen.append(kayit)
    elif fark <= -2:
        kacan.append(kayit)
yuklenen.sort(key=lambda x: -x["fark"])
kacan.sort(key=lambda x: x["fark"])

con.close()

data = {
    "guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "veri_tarihi": son_tarih,
    "fon_sayisi": len(fonlar),
    "populer": populer,
    "yuklenen": yuklenen[:50],
    "kacan": kacan[:50],
    "tum_fonlar": fonlar,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
print(f"Fon yazildi: {len(fonlar)} fon")
print(f"  populer: {len(populer)}, yuklenen: {len(yuklenen)}, kacan: {len(kacan)}")
print(f"Dosya boyutu: {os.path.getsize(OUT)/1024:.0f} KB")
