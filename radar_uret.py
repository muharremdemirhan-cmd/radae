import sqlite3, json, subprocess
from datetime import datetime

DB = "/root/kap_bot/radar.db"
OUT = "/root/radae/radar.json"

SORGU = """
WITH veri AS (
  SELECT hisse, yatirimci,
    substr(tarih,7,4)||substr(tarih,4,2)||substr(tarih,1,2) AS d,
    oran,
    ROW_NUMBER() OVER (PARTITION BY hisse,yatirimci ORDER BY substr(tarih,7,4)||substr(tarih,4,2)||substr(tarih,1,2) DESC) AS yeni,
    ROW_NUMBER() OVER (PARTITION BY hisse,yatirimci ORDER BY substr(tarih,7,4)||substr(tarih,4,2)||substr(tarih,1,2) ASC) AS eski
  FROM ortaklik
  WHERE yatirimci!='DİĞER' AND oran IS NOT NULL
    AND substr(tarih,7,4)||substr(tarih,4,2)||substr(tarih,1,2) >= '20250601'
)
SELECT a.hisse, a.yatirimci, b.oran, a.oran, ROUND(a.oran-b.oran,2)
FROM veri a
JOIN veri b ON a.hisse=b.hisse AND a.yatirimci=b.yatirimci
WHERE a.yeni=1 AND b.eski=1 AND a.oran-b.oran>1
ORDER BY (a.oran-b.oran) DESC
LIMIT 50;
"""

con = sqlite3.connect(DB)
rows = con.execute(SORGU).fetchall()
con.close()

data = {
    "guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "baslik": "Son 12 Ayda Pay Artiran Ortaklar",
    "kayitlar": [
        {"hisse": r[0], "ortak": r[1], "ilk_oran": r[2],
         "son_oran": r[3], "artis": r[4]}
        for r in rows
    ]
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"JSON yazildi: {len(data['kayitlar'])} kayit")

# GitHub'a push
subprocess.run(["git", "-C", "/root/radae", "add", "radar.json"])
subprocess.run(["git", "-C", "/root/radae", "commit", "-m", f"radar guncelleme {data['guncelleme']}"])
r = subprocess.run(["git", "-C", "/root/radae", "push"], capture_output=True, text=True)
print("PUSH:", r.returncode)
print(r.stderr[-300:] if r.stderr else "ok")
