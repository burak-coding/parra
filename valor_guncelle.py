#!/usr/bin/env python3
"""Parra valör tablosu (kullanıcı, 22 Kasım 2026): fon ve borsa işlemlerinde paranın kaç iş günü sonra hesaba geçtiği.

  fon/tr/valor.json
    {"surum":1,"guncelleme":"2026-11-22","kaynak":"TEFAS; Borsa İstanbul",
     "borsa":{"bist":{"alis":0,"satis":2},"yabanci":{"alis":0,"satis":1}},
     "fonlar":{"AFT":[1,2,"2026-11-22"], ...}}      # [alış valörü, satış valörü, son kontrol günü]

Kaynaklar:
  - Fon: TEFAS fon sayfası (https://www.tefas.gov.tr/tr/fon-detayli-analiz/<KOD>), "Fon Alış Valörü" ve
    "Fon Satış Valörü". TEFAS'ın robots.txt'i bu sayfalara izin veriyor (yalnız /api/ yasak). Toplu liste yok; fon
    başına bir sayfa. Valör nadiren değişiyor: her çalışmada en eski kontrol edilmiş `--en-cok` fon (varsayılan 300)
    yenilenir, istekler arasında `--bekle` saniye (varsayılan 2). İlk doldurma için `--en-cok 3000`.
  - BIST: Borsa İstanbul "Takas Esasları" sayfasındaki "Takas günü T+n" cümlesi; okunamazsa önceki değer (yoksa 2).
  - Yabancı hisse: ABD T+1 (28 Mayıs 2024'ten beri); sayfası olmadığından betikte sabit.

Uygulamada alışta para her zaman hemen çıkar (kullanıcı, 22 Kasım 2026); dosyadaki alış valörü bilgi için.
TEFAS'ın uyarısı: valör talimat saatine ve tatillere göre değişir, kurucu değiştirebilir — tablo varsayılan öneri.

Kullanım (site deposunun kökünde; fon/tr/fonlar.json'u fon_guncelle.py yazar):
  python3 scripts/valor_guncelle.py
  python3 scripts/valor_guncelle.py --en-cok 3000      # ilk doldurma
  python3 scripts/valor_guncelle.py --dene sayfa.html  # yalnız ayrıştırıcıyı dene, ağ yok
Yalnız standart kütüphane; ağ hatasında var olan dosya bozulmaz (yazma atomik), okunamayan fonun eski değeri kalır.
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import sys
import time
import urllib.request

BASLIK = {"User-Agent": "Parra-valor-guncelle/1.0 (+https://burak-coding.github.io/parra/)"}
TEFAS = "https://www.tefas.gov.tr/tr/fon-detayli-analiz/{}"
BIST = "https://www.borsaistanbul.com/piyasalar/pay-piyasasi/takas-esaslari"
YABANCI_SATIS = 1
KOD = re.compile(r"^[A-Z0-9]{2,6}$")
ALIS = re.compile(r">\s*Fon Alış Valörü\s*</p>\s*<p[^>]*>\s*(\d{1,2})\s*</p>")
SATIS = re.compile(r">\s*Fon Satış Valörü\s*</p>\s*<p[^>]*>\s*(\d{1,2})\s*</p>")
TAKAS = re.compile(r"Takas günü\s*T\s*\+\s*(\d)")


def getir(url, deneme=3):
    for i in range(deneme):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=BASLIK), timeout=60) as y:
                return y.read().decode("utf-8", errors="replace")
        except Exception:
            if i == deneme - 1:
                raise
            time.sleep(10 * (i + 1))


def fon_valoru(sayfa):
    """(alış, satış) ya da None."""
    a, s = ALIS.search(sayfa), SATIS.search(sayfa)
    if not a or not s:
        return None
    alis, satis = int(a.group(1)), int(s.group(1))
    return (alis, satis) if 0 <= alis <= 15 and 0 <= satis <= 15 else None


def bist_takasi(sayfa):
    m = TAKAS.search(sayfa)
    return int(m.group(1)) if m and 0 <= int(m.group(1)) <= 5 else None


def oku(yol):
    try:
        return json.loads(pathlib.Path(yol).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def yaz(yol, veri):
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(yol.suffix + ".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    os.replace(gecici, yol)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cikti", default="fon/tr")
    ap.add_argument("--en-cok", type=int, default=300, help="bu çalışmada yenilenecek en çok fon")
    ap.add_argument("--bekle", type=float, default=2.0, help="istekler arası saniye")
    ap.add_argument("--dene", help="yalnız bu HTML dosyasını ayrıştır")
    a = ap.parse_args()

    if a.dene:
        sayfa = pathlib.Path(a.dene).read_text(encoding="utf-8", errors="replace")
        print({"fon": fon_valoru(sayfa), "bist": bist_takasi(sayfa)})
        return

    kok = pathlib.Path(a.cikti)
    yol = kok / "valor.json"
    eski = oku(yol) or {}
    fonlar = dict(eski.get("fonlar") or {})
    bugun = datetime.date.today().isoformat()

    # BIST takas günü.
    borsa = eski.get("borsa") or {"bist": {"alis": 0, "satis": 2}, "yabanci": {"alis": 0, "satis": YABANCI_SATIS}}
    try:
        n = bist_takasi(getir(BIST))
        if n is not None:
            borsa["bist"] = {"alis": 0, "satis": n}
        else:
            print("uyarı: BIST takas günü okunamadı; önceki değer", file=sys.stderr)
    except Exception as e:
        print(f"uyarı: Borsa İstanbul sayfası alınamadı ({e}); önceki değer", file=sys.stderr)
    borsa["yabanci"] = {"alis": 0, "satis": YABANCI_SATIS}

    # Fonlar: yalnız yatırım fonları (TEFAS'ta alınıp satılanlar); en eski kontrol edilmiş önce.
    liste = (oku(kok / "fonlar.json") or {}).get("fonlar") or []
    kodlar = sorted({f["kod"] for f in liste if KOD.match(f.get("kod", "")) and f.get("tip", "YAT") == "YAT"})
    if not kodlar:
        sys.exit("fon/tr/fonlar.json yok ya da boş: önce fon_guncelle.py")
    sira = sorted(kodlar, key=lambda k: (fonlar.get(k, [None, None, ""])[2], k))[: max(a.en_cok, 0)]
    okunan = okunamayan = 0
    for i, kod in enumerate(sira):
        if i:
            time.sleep(a.bekle)
        try:
            v = fon_valoru(getir(TEFAS.format(kod)))
        except Exception as e:
            v = None
            print(f"uyarı: {kod} alınamadı ({e})", file=sys.stderr)
        if v:
            fonlar[kod] = [v[0], v[1], bugun]
            okunan += 1
        else:
            okunamayan += 1
            # Sayfası valör göstermeyen fon (TEFAS'ta işlem görmüyor): sırada sona kalsın, eski değeri kalsın.
            if kod in fonlar:
                fonlar[kod] = fonlar[kod][:2] + [bugun]
            else:
                fonlar[kod] = [None, None, bugun]
    # Art arda hepsi okunamıyorsa sayfa biçimi değişmiş olabilir: dosyayı bozma.
    if sira and okunan == 0:
        sys.exit(f"hiçbir fonun valörü okunamadı ({okunamayan}); sayfa biçimi değişmiş olabilir — dosya yazılmadı")
    fonlar = {k: v for k, v in fonlar.items() if k in set(kodlar)}
    yaz(yol, {"surum": 1, "guncelleme": bugun, "kaynak": "TEFAS; Borsa İstanbul", "borsa": borsa, "fonlar": fonlar})
    print(f"valör: {okunan} okundu, {okunamayan} okunamadı; tabloda {sum(1 for v in fonlar.values() if v[0] is not None)} fon")


if __name__ == "__main__":
    main()
