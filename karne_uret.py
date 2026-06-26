#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3, json, os
from datetime import datetime

DB = "/root/kap_bot/radar.db"
OUT = "/root/radae/karne.json"

def d8(t):
    if not t or len(t) < 10:
        return "00000000"
    return t[6:10] + t[3:5] + t[0:2]

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

hisseler = [r[0] for r in con.execute(
    "SELECT DISTINCT hisse FROM ortaklik ORDER BY hisse").fetchall()]

karne = {}
for hisse in hisseler:
    ort_rows = con.execute(
        "SELECT tarih, yatirimci, oran, oy_orani FROM ortaklik WHERE hisse=?",
        (hisse,)).fetchall()
    if not ort_rows:
        continue
    son_tarih = max(ort_rows, key=lambda r: d8(r["tarih"]))["tarih"]
    guncel_ortaklik = [
        {"yatirimci": r["yatirimci"], "oran": r["oran"], "oy": r["oy_orani"]}
        for r in ort_rows if r["tarih"] == son_tarih
    ]
    guncel_ortaklik.sort(key=lambda x: (x["oran"] is None, -(x["oran"] or 0)))

    hareketler = []
    yat_map = {}
    for r in ort_rows:
        if r["yatirimci"] == "DİĞER" or r["oran"] is None:
            continue
        yat_map.setdefault(r["yatirimci"], []).append((d8(r["tarih"]), r["oran"]))
    for yat, kayitlar in yat_map.items():
        kayitlar.sort()
        son12 = [k for k in kayitlar if k[0] >= "20250601"]
        if len(son12) >= 2:
            ilk = son12[0][1]; son = son12[-1][1]
            fark = round(son - ilk, 2)
            if abs(fark) >= 1:
                hareketler.append({"yatirimci": yat, "ilk": ilk,
                                   "son": son, "fark": fark})
    hareketler.sort(key=lambda x: -abs(x["fark"]))

    fii_rows = con.execute(
        "SELECT tarih, oran, nominal FROM fiili_dolasim WHERE hisse=?",
        (hisse,)).fetchall()
    fiili = []
    if fii_rows:
        srt = sorted(fii_rows, key=lambda r: d8(r["tarih"]), reverse=True)
        for r in srt[:6]:
            fiili.append({"tarih": r["tarih"], "oran": r["oran"],
                          "nominal": r["nominal"]})

    karne[hisse] = {
        "son_tarih": son_tarih,
        "ortaklik": guncel_ortaklik,
        "hareketler": hareketler[:10],
        "fiili": fiili,
    }
con.close()

data = {
    "guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "hisse_sayisi": len(karne),
    "hisseler": karne,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
print(f"Karne yazildi: {len(karne)} hisse")
print(f"Dosya boyutu: {os.path.getsize(OUT)/1024:.0f} KB")
