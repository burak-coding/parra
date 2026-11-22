#!/usr/bin/env python3
"""Parra fon fiyatları (A34, 21 Kasım 2026): fonfiyat.com.tr'nin herkese açık API'sinden (kaynak TEFAS) üç tür dosya.

  fon/tr/fonlar.json        sabit bilgiler: kod, ad, kurucu, kategori, tip (YAT/EMK)
  fon/tr/fiyatlar.json      bütün fonların son fiyatı, önceki günü ve fiyat tarihi
  fon/tr/gecmis/<KOD>/<YIL>.json
                            fon başına, yıl yıl günlük fiyat geçmişi. Her çalışmada yalnız içinde bulunulan yılın
                            dosyasına bugünkü fiyat eklenir (git geçmişi şişmesin); eksik geçmiş yavaş yavaş
                            history.csv'den doldurulur (gecmis/_tam.json doldurulan fonların listesi).

Kullanım (site deposunun kökünde):
  python3 scripts/fon_guncelle.py                    # fiyatlar + bugünkü geçmiş + en çok 150 fonun geçmiş doldurması
  python3 scripts/fon_guncelle.py --doldur 0         # geçmiş doldurmadan
  python3 scripts/fon_guncelle.py --cikti /yol/fon   # başka klasöre

Kaynağın koşulları (fonfiyat.com.tr/api): anahtar yok, ticari kullanım serbest, saatte birden sık çekilmez, kaynak
belirtilir ("Veri: fonfiyat.com.tr / TEFAS"). Veri iş günlerinde ~11:30'da (İstanbul) güncellenir. Yalnız standart
kütüphane; ağ hatasında var olan dosyalar bozulmaz (yazma atomik).
"""
import argparse
import csv
import datetime
import io
import json
import os
import pathlib
import re
import sys
import time
import urllib.request

TABAN = "https://fonfiyat.com.tr"
KAYNAK = "fonfiyat.com.tr / TEFAS"
BASLIK = {"User-Agent": "Parra-fon-guncelle/1.0 (+https://burak-coding.github.io/parra/)"}
GECMIS_BASLANGIC = "2021-01-01"   # en çok 5 yıl
KOD = re.compile(r"^[A-Z0-9]{2,6}$")


def getir(yol, deneme=3):
    for i in range(deneme):
        try:
            with urllib.request.urlopen(urllib.request.Request(TABAN + yol, headers=BASLIK), timeout=60) as y:
                return y.read().decode("utf-8")
        except Exception:
            if i == deneme - 1:
                raise
            time.sleep(5 * (i + 1))


def yaz(yol: pathlib.Path, veri):
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(yol.suffix + ".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(gecici, yol)


def oku(yol: pathlib.Path):
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fiyat_metni(x):
    """6 ondalık, nokta; gereksiz sıfırlar yok ("1.258829", "12.5")."""
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cikti", default="fon/tr")
    ap.add_argument("--doldur", type=int, default=150, help="bu çalışmada geçmişi doldurulacak en çok fon")
    a = ap.parse_args()
    kok = pathlib.Path(a.cikti)

    fonlar = json.loads(getir("/v1/funds.json?tip=all"))
    if not isinstance(fonlar, list) or len(fonlar) < 100:
        sys.exit(f"Beklenmeyen yanıt: {type(fonlar).__name__} {len(fonlar) if isinstance(fonlar, list) else ''}")
    bugun = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sabit, fiyatlar = [], {}
    for f in fonlar:
        kod = str(f.get("kod") or "").strip().upper()
        fiyat, tarih = f.get("fiyat"), f.get("tarih")
        if not KOD.match(kod) or not isinstance(fiyat, (int, float)) or fiyat <= 0 or not tarih:
            continue
        sabit.append({"kod": kod, "ad": (f.get("ad") or "").strip(), "kurucu": f.get("kurucu_ad") or "",
                      "kategori": f.get("kategori") or "", "tip": f.get("tip") or "YAT"})
        gunluk = f.get("gunluk")
        onceki = fiyat / (1 + gunluk / 100) if isinstance(gunluk, (int, float)) and gunluk > -100 else None
        fiyatlar[kod] = [fiyat_metni(fiyat), fiyat_metni(onceki) if onceki else None, tarih]
    sabit.sort(key=lambda x: x["kod"])
    son_tarih = max(v[2] for v in fiyatlar.values())

    yaz(kok / "fonlar.json", {"surum": 1, "guncelleme": bugun, "kaynak": KAYNAK, "fonlar": sabit})
    yaz(kok / "fiyatlar.json", {"surum": 1, "guncelleme": bugun, "kaynak": KAYNAK, "tarih": son_tarih,
                                "fiyatlar": fiyatlar})

    # Geçmiş: bugünkü fiyat her fonun o yılki dosyasına; eksik geçmiş `--doldur` kadar fon için history.csv'den.
    tam_yol = kok / "gecmis" / "_tam.json"
    tam = set(oku(tam_yol) or [])
    doldurulan = 0

    def yil_yaz(kod, gunler):
        yillar = {}
        for t, p in gunler.items():
            yillar.setdefault(t[:4], {})[t] = p
        for yil, d in yillar.items():
            yol = kok / "gecmis" / kod / f"{yil}.json"
            eski = {t: p for t, p in (oku(yol) or {}).get("fiyatlar", [])}
            birlesik = {**eski, **d}
            if birlesik != eski:
                satirlar = ",\n".join(json.dumps([t, birlesik[t]]) for t in sorted(birlesik))
                yol.parent.mkdir(parents=True, exist_ok=True)
                gecici = yol.with_suffix(".json.tmp")
                gecici.write_text(f'{{"kod":"{kod}","yil":{yil},"fiyatlar":[\n{satirlar}\n]}}\n', encoding="utf-8")
                os.replace(gecici, yol)

    for kod, (fiyat, _, tarih) in sorted(fiyatlar.items()):
        gunler = {tarih: fiyat}
        if kod not in tam and doldurulan < a.doldur:
            try:
                metin = getir(f"/v1/funds/{kod}/history.csv?from={GECMIS_BASLANGIC}&locale=en")
                ayirac = ";" if ";" in metin.split("\n", 1)[0] else ","
                for satir in csv.DictReader(io.StringIO(metin), delimiter=ayirac):
                    t, p = (satir.get("tarih") or "").strip(), (satir.get("fiyat") or "").strip().replace(",", ".")
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", t) and p:
                        gunler.setdefault(t, fiyat_metni(float(p)))
                tam.add(kod)
                doldurulan += 1
                time.sleep(1)
            except Exception as e:
                print(f"{kod}: geçmiş alınamadı ({e})", file=sys.stderr)
        yil_yaz(kod, gunler)
    yaz(tam_yol, sorted(tam))

    print(f"{len(fiyatlar)} fon; son fiyat günü {son_tarih}; {doldurulan} fonun geçmişi dolduruldu")


if __name__ == "__main__":
    main()
