#!/usr/bin/env python3
"""Parra valör tablosu (kullanıcı, 22 Kasım 2026): fon ve borsa işlemlerinde paranın kaç iş günü sonra hesaba geçtiği.

  fon/tr/valor.json
    {"surum":1,"guncelleme":"2026-11-22","kaynak":"TEFAS; Borsa İstanbul",
     "borsa":{"bist":{"alis":0,"satis":2},"yabanci":{"alis":0,"satis":1}},
     "fonlar":{"AFT":[1,2,"2026-11-22"], ...}}      # [alış valörü, satış valörü, son kontrol günü]

Kaynaklar:
  - Fon: TEFAS fon sayfası (https://www.tefas.gov.tr/tr/fon-detayli-analiz/<KOD>), "Fon Alış Valörü" ve
    "Fon Satış Valörü". TEFAS'ın robots.txt'i bu sayfalara izin veriyor (yalnız /api/ yasak). Toplu liste yok; fon
    başına bir sayfa, istekler arasında `--bekle` saniye (varsayılan 2). Her çalıştırma en çok `--sure` dakika
    (varsayılan 45) çalışıp bulduğunu yazar; en eski kontrol edilmiş fon önce. Pazartesi dört kez çalışarak (11, 13,
    15, 17 İstanbul) bütün fonları aynı gün yeniler.
  - BIST: Borsa İstanbul "Takas Esasları" sayfasındaki "Takas günü T+n" cümlesi; okunamazsa önceki değer (yoksa 2).
  - Yabancı hisse: ABD T+1 (28 Mayıs 2024'ten beri); sayfası olmadığından betikte sabit.

Uygulamada alışta para her zaman hemen çıkar (kullanıcı, 22 Kasım 2026); dosyadaki alış valörü bilgi için.
TEFAS'ın uyarısı: valör talimat saatine ve tatillere göre değişir, kurucu değiştirebilir — tablo varsayılan öneri.

Kullanım (site deposunun kökünde; fon/tr/fonlar.json'u fon_guncelle.py yazar):
  python3 valor_guncelle.py
  python3 valor_guncelle.py --en-cok 50        # yalnız en eski kontrol edilmiş 50 fon
  python3 valor_guncelle.py --dene sayfa.html  # yalnız ayrıştırıcıyı dene, ağ yok
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


def yanit(url, deneme=2):
    """(metin, HTTP durumu, yönlendirmeden sonraki adres)."""
    for i in range(deneme):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=BASLIK), timeout=20) as y:
                return y.read().decode("utf-8", errors="replace"), y.status, y.geturl()
        except Exception:
            if i == deneme - 1:
                raise
            time.sleep(5)


def getir(url, deneme=2):
    return yanit(url, deneme)[0]


def teshis(kod, durum, url, sayfa):
    """Valörü okunamayan sayfanın tek satırlık özeti (23 Kasım 2026: GitHub'da 1010 fonun hiçbiri okunamadı, yerelde
    okunuyordu; sunucuya gelen sayfayı görmek için)."""
    m = re.search(r"<title[^>]*>(.*?)</title>", sayfa, re.S | re.I)
    baslik = re.sub(r"\s+", " ", m.group(1)).strip()[:120] if m else "-"
    valor = "var" if "Valör" in sayfa else "yok"
    return f"{kod}: HTTP {durum}, {url}, {len(sayfa)} karakter, başlık: {baslik}, 'Valör' {valor}"


def erken_dur(i, okunan, esik):
    """İlk `esik` fonun hiçbiri okunamadıysa dur (yerelde ilk 30 fonun 20'si okunuyor): süre boşa gitmesin."""
    return esik > 0 and okunan == 0 and i >= esik


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
    ap.add_argument("--en-cok", type=int, default=3000, help="bu çalışmada yenilenecek en çok fon (varsayılan: hepsi)")
    ap.add_argument("--bekle", type=float, default=2.0, help="istekler arası saniye")
    ap.add_argument("--sure", type=float, default=45, help="en çok çalışma süresi (dakika); dolunca bulunanlar yazılır")
    ap.add_argument("--erken-dur", type=int, default=30,
                    help="ilk bu kadar fonun hiçbiri okunamazsa dur (0: kapalı)")
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
    ilk_teshis = None
    baslangic = time.monotonic()
    for i, kod in enumerate(sira):
        # Süre sınırı (22 Kasım 2026): GitHub çalıştırıcısı 2 saati aşan işte koptu; bulunanlar yazılır, kalanı bir
        # sonraki çalıştırmada (en eski kontrol edilmiş önce).
        if time.monotonic() - baslangic > a.sure * 60:
            print(f"süre doldu: {i}/{len(sira)} fon bu çalıştırmada", file=sys.stderr)
            break
        if erken_dur(i, okunan, a.erken_dur):
            print(ilk_teshis or "teşhis yok", file=sys.stderr)
            sys.exit(f"ilk {i} fonun hiçbirinin valörü okunamadı; TEFAS bu sunucuya valörsüz sayfa veriyor olabilir"
                     " — dosya yazılmadı")
        if i and i % 100 == 0:
            print(f"{i}/{len(sira)}", file=sys.stderr)
        if i:
            time.sleep(a.bekle)
        try:
            sayfa, durum, son_url = yanit(TEFAS.format(kod))
            v = fon_valoru(sayfa)
            if not v and ilk_teshis is None:
                ilk_teshis = teshis(kod, durum, son_url, sayfa)
                print(f"teşhis: {ilk_teshis}", file=sys.stderr)
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
