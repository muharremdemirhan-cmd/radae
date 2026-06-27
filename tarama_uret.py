#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3, json, os, urllib.request, csv, io
from datetime import datetime, timedelta

DB = "/root/kap_bot/radar.db"
OUT = "/root/radae/tarama.json"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_PC-k1mRVsBx1JRey7VpHQX0MtGXpgKorG0GXsULqmE/gviz/tq?tqx=out:csv&gid=1580091346"

def d8(t):
    if not t or len(t) < 10: return "00000000"
    return t[6:10] + t[3:5] + t[0:2]

bugun = datetime.now()
def esik(ay):
    return (bugun - timedelta(days=int(ay*30))).strftime("%Y%m%d")

DONEMLER = {"2hafta": 0.5, "1ay": 1, "2ay": 2, "3ay": 3, "4ay": 4, "5ay": 5, "6ay": 6}

def yuzde(s):
    if not s: return None
    s = s.strip().replace("%","").replace(".","").replace(",",".")
    try: return float(s)
    except: return None

# --- Fiyat/getiri (Sheets) ---
fiyat_map = {}
try:
    req = urllib.request.Request(SHEET_URL, headers={"User-Agent":"Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    for r in list(csv.reader(io.StringIO(raw)))[1:]:
        if not r or not r[0]: continue
        kod = r[0].replace("IST:","").strip()
        g = lambda i: r[i] if i < len(r) else ""
        fiyat_map[kod] = {"d1ay": yuzde(g(5)), "d3ay": yuzde(g(7)), "d6ay": yuzde(g(10)), "d12ay": yuzde(g(16))}
    print(f"Fiyat: {len(fiyat_map)} hisse")
except Exception as e:
    print(f"UYARI fiyat: {e}")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# Ortaklik verisi
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
        if all(oranlar[i] >= oranlar[i-1] for i in range(1, len(oranlar))) and oranlar[-1]-oranlar[0] >= 1:
            surekli.append({"hisse": h, "ortak": y, "ilk": oranlar[0], "son": oranlar[-1],
                            "fark": round(oranlar[-1]-oranlar[0], 2), "adim": len(son12)})
surekli.sort(key=lambda x: -x["fark"])
sonuc["surekli_artiran"] = surekli[:100]

# YENI GIREN ORTAK (donem secmeli): ilk kez gorunen + guncel %5+ pay
def d8_to_str(d):
    return d[6:8]+"/"+d[4:6]+"/"+d[0:4]  # YYYYMMDD -> GG/AA/YYYY
YG_DONEM = {"1ay":1, "2ay":2, "3ay":3, "6ay":6}
for dad, ay in YG_DONEM.items():
    es = esik(ay)
    yg = []
    for h in veri:
        for y, kayitlar in veri[h].items():
            ilk_d8 = kayitlar[0][0]
            guncel = kayitlar[-1][1]
            # ilk kaydi bu donem icindeyse = yeni giris
            if ilk_d8 >= es and guncel is not None and guncel >= 5:
                yg.append({"hisse": h, "ortak": y,
                           "giris_orani": kayitlar[0][1], "guncel": guncel,
                           "tarih": d8_to_str(ilk_d8)})
    yg.sort(key=lambda x: -x["guncel"])
    sonuc[f"yeni_giren_{dad}"] = yg[:100]

# Fiili dolasim
fii = {}
for r in con.execute("SELECT hisse, tarih, oran FROM fiili_dolasim WHERE oran IS NOT NULL"):
    fii.setdefault(r["hisse"], []).append((d8(r["tarih"]), r["oran"]))
for h in fii:
    fii[h].sort()

az_dolasim = []
for h, kayitlar in fii.items():
    g = kayitlar[-1][1]
    if g is not None and g <= 30:
        az_dolasim.append({"hisse": h, "dolasim": g})
az_dolasim.sort(key=lambda x: x["dolasim"])
sonuc["az_dolasimli"] = az_dolasim[:150]

# Dolasim degisim yardimci (donem -> fark)
def dolasim_fark(h, ay):
    kayitlar = fii.get(h)
    if not kayitlar: return None
    es = esik(ay)
    donem = [k for k in kayitlar if k[0] >= es]
    if len(donem) >= 2 and donem[0][1] is not None:
        return round(donem[-1][1] - donem[0][1], 2)
    return None

for dad, ay in DONEMLER.items():
    daralan = []
    for h in fii:
        f = dolasim_fark(h, ay)
        if f is not None and f <= -0.5:
            daralan.append({"hisse": h, "ilk": [k for k in fii[h] if k[0]>=esik(ay)][0][1],
                            "son": fii[h][-1][1], "fark": f})
    daralan.sort(key=lambda x: x["fark"])
    sonuc[f"daralan_{dad}"] = daralan[:100]

# Fon: hisseye giren fonlar var mi (fon.json'dan degil, dogrudan DB'den hisse bazli degil)
# Fon verisi fon bazli oldugu icin burada "fon giriyor" sinyalini hisse bazli kuramayiz.
# Onun yerine birlesik sinyalde ortak+dolasim+fiyat kullanacagiz.

# === BIRLESIK SINYAL: sessiz toplama ===
# Kriter: son 3 ayda dolasim daraliyor + ayni donemde ortak pay artiriyor
#         + fiyat henuz cok kosmamis
birlesik = []
for h in fii:
    dol3 = dolasim_fark(h, 3)
    dol1 = dolasim_fark(h, 1)
    if dol3 is None or dol3 > -1: continue  # dolasim en az 1 puan daralmali (3 ay)
    # ortak pay artirmis mi (son 3 ay)
    es3 = esik(3)
    artiran_ortak = None; max_artis = 0
    for y, kayitlar in veri.get(h, {}).items():
        dk = [k for k in kayitlar if k[0] >= es3]
        if len(dk) < 2: continue
        a = dk[-1][1] - dk[0][1]
        if a > max_artis:
            max_artis = a; artiran_ortak = y
    if max_artis < 1: continue  # en az bir ortak 1+ puan artirmali
    fy = fiyat_map.get(h, {})
    f1 = fy.get("d1ay"); f3 = fy.get("d3ay"); f6 = fy.get("d6ay"); f12 = fy.get("d12ay")
    # Fiyat 3 ayda +%50 ustu kosanlari ele (zaten kacmis)
    if f3 is not None and f3 > 30: continue
    # toplama skoru: dolasim daralmasi + ortak artisi
    toplama = abs(dol3) + max_artis
    # sessizlik bonusu: fiyat ne kadar dusukse o kadar iyi
    fiyat_ceza = f3 if f3 is not None else 0
    sessizlik = round(toplama - max(fiyat_ceza, 0) * 0.3, 1)
    birlesik.append({
        "hisse": h, "dolasim_3ay": dol3, "dolasim_1ay": dol1,
        "ortak": artiran_ortak, "ortak_artis": round(max_artis, 2),
        "fiyat_1ay": f1, "fiyat_3ay": f3, "fiyat_6ay": f6, "fiyat_12ay": f12,
        "skor": round(toplama, 1), "sessizlik": sessizlik,
        "dolasim_guncel": fii[h][-1][1]
    })
# Sessiz toplama one cikar: toplama yuksek + fiyat henuz kosmamis
birlesik.sort(key=lambda x: -x["sessizlik"])
sonuc["birlesik"] = birlesik[:80]

con.close()
data = {"guncelleme": bugun.strftime("%Y-%m-%d %H:%M"),
        "donemler": list(DONEMLER.keys()),
        "filtreler": list(sonuc.keys()), "veri": sonuc}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
print(f"Tarama yazildi: {len(sonuc)} filtre")
print(f"  birlesik (sessiz toplama): {len(sonuc['birlesik'])} kayit")
print(f"Dosya boyutu: {os.path.getsize(OUT)/1024:.0f} KB")
