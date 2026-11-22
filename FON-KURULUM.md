# Fon fiyatları — kurulum (A34, 21 Kasım 2026)

Parra fon fiyatlarını kendi sitesinden okur:
`https://burak-coding.github.io/parra/fon/tr/fiyatlar.json`, `fonlar.json` ve `gecmis/<KOD>/<YIL>.json`.
Bu dosyaları sitenin deposundaki GitHub Actions üretir. Veri fonfiyat.com.tr'nin herkese açık API'sinden gelir
(kaynak TEFAS). API'de anahtar yok ve ticari kullanım serbest. Saatte bir kereden sık çekilmemeli ve kaynak
belirtilmeli; uygulama Hakkında'da "fonfiyat.com.tr / TEFAS" yazıyor.

## Bir kerelik kurulum (senin işin)

1. Sitenin deposuna (`burak-coding/parra`) şu iki dosyayı aynı yollarla kopyala:
   - `scripts/fon_guncelle.py`
   - `.github/workflows/fon-fiyatlari.yml`
2. GitHub'da depo › **Settings › Actions › General** sayfasını aç:
   - "Allow all actions" seçili olsun.
   - "Workflow permissions" altında **Read and write permissions** seçili olsun (Action `fon/` klasörünü depoya yazıyor).
3. **Actions › Fon fiyatları › Run workflow** ile ilk çalıştırmayı elle başlat.
   - İlk çalıştırma bütün fonların son fiyatını yazar.
   - Geçmiş her çalıştırmada 150 fon için doldurulur; bütün fonların geçmişi yaklaşık 8 iş gününde tamamlanır.
4. Sonrasında iş günleri 12:15 ve 18:30'da (İstanbul) kendiliğinden çalışır.

Gizli anahtar gerekmiyor. Cloudflare Pages istersen aynı `fon/` klasörünü oradan da yayınlayabilirsin, ama
uygulamanın adresi GitHub Pages'i gösteriyor; adres değişirse `ParraFundSource.base` (iOS) ve
`ParraFundSource.BASE` (Android) güncellenmeli.

## Elle çalıştırma

```bash
python3 scripts/fon_guncelle.py --cikti fon/tr --doldur 0
```

## Valör tablosu (22 Kasım 2026)

Uygulama satışta paranın hesaba geçeceği günü `fon/tr/valor.json`'dan önerir (BIST takas günü, fon başına satış
valörü). Dosyayı `scripts/valor_guncelle.py` üretir:

- **Fonlar:** TEFAS fon sayfasındaki "Fon Alış Valörü" ve "Fon Satış Valörü". TEFAS'ın robots.txt'i bu sayfalara izin
  veriyor; toplu liste olmadığı için fon başına bir sayfa okunuyor. Valör seyrek değiştiği için her hafta yalnız en
  eski kontrol edilmiş 300 fon, 2 saniye arayla yenileniyor (~10 dakika).
- **BIST:** Borsa İstanbul "Takas Esasları" sayfasındaki "Takas günü T+n".
- **Yabancı hisse:** T+1, betikte sabit.

Kurulum: `scripts/valor_guncelle.py` ile `.github/workflows/valor.yml`'yi de aynı yollarla depoya kopyala. Fon
fiyatları en az bir kez çalışmış olmalı (`fonlar.json` gerekiyor). İlk doldurma için **Actions › Valör tablosu ›
Run workflow** ile "Yenilenecek en çok fon" alanına `3000` yaz (yaklaşık 1–1,5 saat). Sonrasında her pazar
kendiliğinden çalışır.

Dosya yoksa ya da okunamazsa uygulama yerleşik varsayılanlarla (BIST T+2, yabancı T+1, fonda addan tahmin) çalışır.

```bash
python3 scripts/valor_guncelle.py --cikti fon/tr --en-cok 50   # elle, az sayıda fon
```
