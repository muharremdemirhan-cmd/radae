#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3, json, os, urllib.request, csv, io
from datetime import datetime, timedelta

DB = "/root/kap_bot/radar.db"
OUT = "/root/radae/karne.json"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_PC-k1mRVsBx1JRey7VpHQX0MtGXpgKorG0GXsULqmE/gviz/tq?tqx=out:csv&gid=1580091346"

bugun = datetime.now()
DOLASIM_DONEM = {"2hafta": 0.5, "1ay": 1, "2ay": 2, "3ay": 3, "6ay": 6}
def esik(ay):
    return (bugun - timedelta(days=int(ay*30))).strftime("%Y%m%d")

def d8(t):
    if not t or len(t) < 10: return "00000000"
    return t[6:10] + t[3:5] + t[0:2]

def yuzde(s):
    if not s: return None
    s = s.strip().replace("%","").replace(".","").replace(",",".")
    try: return float(s)
    except: return None

def sayi(s):
    if not s: return None
    s = s.strip().replace(".","").replace(",",".")
    try: return float(s)
    except: return None

# --- Google Sheets'ten fiyat/getiri cek ---
fiyat_map = {}
try:
    req = urllib.request.Request(SHEET_URL, headers={"User-Agent":"Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(raw)))
    for r in rows[1:]:
        if not r or not r[0]: continue
        kod = r[0].replace("IST:","").strip()
        g = lambda i: r[i] if i < len(r) else ""
        fiyat_map[kod] = {"fiyat": sayi(g(1)), "d1ay": yuzde(g(5)),
            "d3ay": yuzde(g(7)), "d6ay": yuzde(g(10)),
            "d9ay": yuzde(g(13)), "d12ay": yuzde(g(16))}
    print(f"Fiyat verisi: {len(fiyat_map)} hisse cekildi")
except Exception as e:
    print(f"UYARI fiyat cekilemedi: {e}")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
hisseler = [r[0] for r in con.execute("SELECT DISTINCT hisse FROM ortaklik ORDER BY hisse").fetchall()]

# Fiili dolasim verisini hafizaya al (donem degisimi icin)
fii_all = {}
for r in con.execute("SELECT hisse, tarih, oran FROM fiili_dolasim WHERE oran IS NOT NULL"):
    fii_all.setdefault(r["hisse"], []).append((d8(r["tarih"]), r["oran"]))
for h in fii_all:
    fii_all[h].sort()

def dolasim_degisim(hisse):
    kayitlar = fii_all.get(hisse)
    if not kayitlar: return None
    guncel = kayitlar[-1][1]
    sonuc = {"guncel": guncel}
    for dad, ay in DOLASIM_DONEM.items():
        es = esik(ay)
        donem = [k for k in kayitlar if k[0] >= es]
        if len(donem) >= 2 and donem[0][1] is not None:
            sonuc[dad] = {"fark": round(donem[-1][1] - donem[0][1], 2),
                          "ilk": donem[0][1], "son": donem[-1][1]}
        else:
            sonuc[dad] = None
    return sonuc

karne = {}
for hisse in hisseler:
    ort_rows = con.execute("SELECT tarih, yatirimci, oran, oy_orani FROM ortaklik WHERE hisse=?", (hisse,)).fetchall()
    if not ort_rows: continue

    son_d8 = max(d8(r["tarih"]) for r in ort_rows)
    son_tarih = next(r["tarih"] for r in ort_rows if d8(r["tarih"]) == son_d8)
    guncel_ortaklik = [
        {"yatirimci": r["yatirimci"], "oran": r["oran"], "oy": r["oy_orani"]}
        for r in ort_rows if d8(r["tarih"]) == son_d8 and r["oran"] is not None]
    guncel_ortaklik.sort(key=lambda x: -(x["oran"] or 0))
    iceride = set(o["yatirimci"] for o in guncel_ortaklik)

    yat_tum = {}
    for r in ort_rows:
        if r["yatirimci"] == "DİĞER" or r["oran"] is None: continue
        yat_tum.setdefault(r["yatirimci"], []).append((d8(r["tarih"]), r["tarih"], r["oran"]))

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
        cikti = (y not in iceride)
        son_oran_gercek = son12[-1][2]
        if cikti:
            adimlar.append({"tarih": son_tarih, "oran": 0,
                            "degisim": round(0 - son12[-1][2], 2), "cikis": True})
            son_oran_gercek = 0
        toplam = round(son_oran_gercek - son12[0][2], 2)
        zirve = max(k[2] for k in son12)
        if abs(toplam) >= 0.5 or len(adimlar) >= 2 or cikti:
            zaman.append({"yatirimci": y, "ilk": son12[0][2], "son": son_oran_gercek,
                          "zirve": zirve, "toplam": toplam, "adim_sayi": len(adimlar),
                          "iceride": not cikti, "adimlar": adimlar})
    zaman.sort(key=lambda x: -abs(x["toplam"]))

    fii_rows = con.execute("SELECT tarih, oran, nominal FROM fiili_dolasim WHERE hisse=?", (hisse,)).fetchall()
    fiili = []
    if fii_rows:
        srt = sorted(fii_rows, key=lambda r: d8(r["tarih"]), reverse=True)
        for r in srt[:8]:
            fiili.append({"tarih": r["tarih"], "oran": r["oran"], "nominal": r["nominal"]})

    karne[hisse] = {"son_tarih": son_tarih, "ortaklik": guncel_ortaklik,
                    "hareketler": zaman[:12], "fiili": fiili,
                    "fiyat": fiyat_map.get(hisse),
                    "dolasim_trend": dolasim_degisim(hisse)}
con.close()

data = {"guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "hisse_sayisi": len(karne), "hisseler": karne}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
print(f"Karne yazildi: {len(karne)} hisse")
print(f"Dosya boyutu: {os.path.getsize(OUT)/1024:.0f} KB")
