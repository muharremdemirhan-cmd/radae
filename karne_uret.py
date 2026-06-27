#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3, json, os
from datetime import datetime, timedelta

DB = "/root/kap_bot/radar.db"
OUT = "/root/radae/karne.json"

def d8(t):
    if not t or len(t) < 10: return "00000000"
    return t[6:10] + t[3:5] + t[0:2]

def tarih_obj(dd):
    try: return datetime.strptime(dd, "%Y%m%d")
    except: return None

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
hisseler = [r[0] for r in con.execute("SELECT DISTINCT hisse FROM ortaklik ORDER BY hisse").fetchall()]

karne = {}
for hisse in hisseler:
    ort_rows = con.execute("SELECT tarih, yatirimci, oran, oy_orani FROM ortaklik WHERE hisse=?", (hisse,)).fetchall()
    if not ort_rows: continue

    yat_son = {}; yat_tum = {}
    for r in ort_rows:
        if r["oran"] is None: continue
        dd = d8(r["tarih"]); y = r["yatirimci"]
        if y not in yat_son or dd > yat_son[y][0]:
            yat_son[y] = (dd, r["tarih"], r["oran"], r["oy_orani"])
        if y != "DİĞER":
            yat_tum.setdefault(y, []).append((dd, r["tarih"], r["oran"]))

    # Genel en yeni tarih
    genel_son_d8 = max(yat_son.values(), key=lambda x: x[0])[0]
    genel_son_obj = tarih_obj(genel_son_d8)
    # 90 gun esik
    esik_obj = genel_son_obj - timedelta(days=90) if genel_son_obj else None
    son_tarih = max(yat_son.values(), key=lambda x: x[0])[1]

    # Guncel ortaklik: sadece son 90 gun icinde teyit edilmis ortaklar
    guncel_ortaklik = []
    for y, (dd, ham, oran, oy) in yat_son.items():
        ob = tarih_obj(dd)
        if esik_obj and ob and ob < esik_obj:
            continue  # cok eski kayit -> artik ortak degil, atla
        guncel_ortaklik.append({"yatirimci": y, "oran": oran, "oy": oy, "tarih": ham})
    guncel_ortaklik.sort(key=lambda x: -(x["oran"] or 0))

    zaman = []
    for y, kayitlar in yat_tum.items():
        kayitlar.sort()
        son12 = [k for k in kayitlar if k[0] >= "20250601"]
        if not son12: continue
        adimlar = []; onceki = None
        for dd, ham, oran in son12:
            degisim = None if onceki is None else round(oran - onceki, 2)
            adimlar.append({"tarih": ham, "oran": oran, "degisim": degisim})
            onceki = oran
        toplam = round(son12[-1][2] - son12[0][2], 2)
        if abs(toplam) >= 0.5 or len(adimlar) >= 2:
            zaman.append({"yatirimci": y, "ilk": son12[0][2], "son": son12[-1][2],
                          "toplam": toplam, "adim_sayi": len(adimlar), "adimlar": adimlar})
    zaman.sort(key=lambda x: -abs(x["toplam"]))

    fii_rows = con.execute("SELECT tarih, oran, nominal FROM fiili_dolasim WHERE hisse=?", (hisse,)).fetchall()
    fiili = []
    if fii_rows:
        srt = sorted(fii_rows, key=lambda r: d8(r["tarih"]), reverse=True)
        for r in srt[:8]:
            fiili.append({"tarih": r["tarih"], "oran": r["oran"], "nominal": r["nominal"]})

    karne[hisse] = {"son_tarih": son_tarih, "ortaklik": guncel_ortaklik,
                    "hareketler": zaman[:12], "fiili": fiili}
con.close()

data = {"guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "hisse_sayisi": len(karne), "hisseler": karne}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
print(f"Karne yazildi: {len(karne)} hisse")
print(f"Dosya boyutu: {os.path.getsize(OUT)/1024:.0f} KB")
