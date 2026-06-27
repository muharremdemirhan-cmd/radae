#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3, json, os
from datetime import datetime

DB = "/root/kap_bot/radar.db"
OUT = "/root/radae/karne.json"

def d8(t):
    if not t or len(t) < 10: return "00000000"
    return t[6:10] + t[3:5] + t[0:2]

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
hisseler = [r[0] for r in con.execute("SELECT DISTINCT hisse FROM ortaklik ORDER BY hisse").fetchall()]

karne = {}
for hisse in hisseler:
    ort_rows = con.execute("SELECT tarih, yatirimci, oran, oy_orani FROM ortaklik WHERE hisse=?", (hisse,)).fetchall()
    if not ort_rows: continue
    son_tarih = max(ort_rows, key=lambda r: d8(r["tarih"]))["tarih"]
    guncel_ortaklik = [
        {"yatirimci": r["yatirimci"], "oran": r["oran"], "oy": r["oy_orani"]}
        for r in ort_rows if r["tarih"] == son_tarih]
    guncel_ortaklik.sort(key=lambda x: (x["oran"] is None, -(x["oran"] or 0)))

    # HER ORTAGIN TAM ZAMAN CIZELGESI (almis-satmis gecmisi)
    yat_map = {}
    for r in ort_rows:
        if r["yatirimci"] == "DİĞER" or r["oran"] is None: continue
        yat_map.setdefault(r["yatirimci"], []).append((d8(r["tarih"]), r["tarih"], r["oran"]))

    zaman_cizelgesi = []
    for yat, kayitlar in yat_map.items():
        kayitlar.sort()
        # son 12 ay icinde en az 1 hareketi olanlari al
        son12 = [k for k in kayitlar if k[0] >= "20250601"]
        if not son12: continue
        # ilk kaydi referans, sonra her degisim
        adimlar = []
        onceki_oran = None
        for d, ham, oran in son12:
            degisim = None if onceki_oran is None else round(oran - onceki_oran, 2)
            adimlar.append({"tarih": ham, "oran": oran, "degisim": degisim})
            onceki_oran = oran
        toplam = round(son12[-1][2] - son12[0][2], 2)
        if abs(toplam) >= 0.5 or len(adimlar) >= 2:
            zaman_cizelgesi.append({
                "yatirimci": yat,
                "ilk": son12[0][2], "son": son12[-1][2],
                "toplam": toplam, "adim_sayi": len(adimlar),
                "adimlar": adimlar,
            })
    zaman_cizelgesi.sort(key=lambda x: -abs(x["toplam"]))

    fii_rows = con.execute("SELECT tarih, oran, nominal FROM fiili_dolasim WHERE hisse=?", (hisse,)).fetchall()
    fiili = []
    if fii_rows:
        srt = sorted(fii_rows, key=lambda r: d8(r["tarih"]), reverse=True)
        for r in srt[:8]:
            fiili.append({"tarih": r["tarih"], "oran": r["oran"], "nominal": r["nominal"]})

    karne[hisse] = {
        "son_tarih": son_tarih,
        "ortaklik": guncel_ortaklik,
        "hareketler": zaman_cizelgesi[:12],
        "fiili": fiili,
    }
con.close()

data = {"guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "hisse_sayisi": len(karne), "hisseler": karne}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
print(f"Karne yazildi: {len(karne)} hisse")
print(f"Dosya boyutu: {os.path.getsize(OUT)/1024:.0f} KB")
