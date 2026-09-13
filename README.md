# İlan Beceri Radarı

Uzaktan çalışma ilanlarından LLM ile yapılandırılmış beceri çıkarımı, ve çıkan
veriden bir analiz panosu.

Serbest formatlı ilan metni giriyor, sabit şemalı JSON çıkıyor: istenen
beceriler, seviye, deneyim yılı, çalışma şekli, rol ailesi. Sonra bu veriden
"hangi beceriler birlikte isteniyor" ve "hangi beceri hangi maaş bandında
geçiyor" sorularına bakılıyor.

<!-- Panoyu çalıştırıp ekran görüntüsü al, docs/screenshot.png olarak kaydet
     ve şu satırın yorumunu kaldır. README'nin en çok fark yaratan kısmı bu. -->
<!-- ![Pano](docs/screenshot.png) -->

## Nasıl çalışır

```
fetch_jobs.py       ──▶  data/raw_jobs.json    Remote OK açık API'si
extract_rules.py    ──▶  data/extracted.json   sözlük + regex ile çıkarım  (varsayılan, ücretsiz)
extract.py          ──▶  data/extracted.json   Claude + tool use ile çıkarım (opsiyonel, API anahtarı ister)
analyze.py          ──▶  data/analysis.json    frekans, birlikte geçiş, maaş kırılımı
app.py                                         Streamlit panosu
```

İki çıkarım yolu aynı şemayı üretiyor, yani `analyze.py` ve `app.py` hangisini
kullandığından bağımsız çalışıyor. Varsayılan yol kural tabanlı olan — hiçbir
ücret çıkarmıyor ve repoyu klonlayan herkes tam pipeline'ı çalıştırabiliyor.

## Kurulum

```bash
git clone https://github.com/<kullanici>/ilan-skill-radar
cd ilan-skill-radar
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env    # ANTHROPIC_API_KEY'i içine yaz
```

## Çalıştırma

```bash
python src/fetch_jobs.py --limit 300 --tags dev,engineer,python,javascript,data,devops
python src/extract_rules.py --verbose    # kural tabanlı çıkarım, ücretsiz
python src/analyze.py                    # istatistikleri üret
streamlit run src/app.py                 # panoyu aç
```

LLM yolunu denemek istersen (`.env` içine `ANTHROPIC_API_KEY` gerekiyor):

```bash
python src/extract.py --limit 20 --out extracted_llm.json
```

`data/extracted.json` repoda olduğu için, API anahtarı olmayan biri de doğrudan
`analyze.py` ve `app.py` adımlarını çalıştırıp sonucu görebilir.

## Yöntem notları

**Beceri sözlüğü.** `extract_rules.py` içindeki `SKILLS` tablosu, her becerinin
metinde geçebilecek yazımlarını tutuyor: `postgres` ve `postgresql`, `k8s` ve
`kubernetes` aynı isimde toplanıyor. Eşleştirme kelime sınırına duyarlı, yoksa
`java` araması `javascript` ilanlarını da yakalıyor.

**Kısa isim tuzağı.** `go`, `r`, `c` gibi isimler normal eşleştirmeyle
çalışmıyor — "go to the office" cümlesi Go diline sayılıyor. Bunlar için
`STRICT_SKILLS` içinde bağlam isteyen ayrı kalıplar var (`golang`, `go
developer`, `in go`).

**Neden tool use.** Modelden "sadece JSON dön" diye rica etmek yerine
`extract_job` adında bir araç tanımlıyoruz. Cevap aracın `input_schema`'sına
uymak zorunda, yani `seniority` alanı her zaman tanımlı beş değerden biri
oluyor. Markdown bloğu ayıklamak, bozuk JSON kurtarmaya çalışmak gerekmiyor.

**Prompt ayrı dosyada.** `prompts/extraction.md` içinde. Prompt'u değiştirdiğinde
çıktının nasıl kaydığını görmek bu projenin asıl öğretici kısmı, o yüzden kod
içine gömülü değil, git geçmişinde takip edilebilir halde.

**Kırpma.** İlan metinleri 6000 karaktere kırpılıyor. Uzun ilanların sonunda
genelde şirket kültürü ve yan haklar var, beceri bilgisi başta geçiyor.

**Maliyet.** `extract.py` sonunda token sayısı ve tahmini maliyet raporluyor.
300 ilanlık tam çalıştırma Sonnet ile birkaç dolar, Haiku ile bunun beşte biri:
`--model claude-haiku-4-5-20251001`.

## Bilinen sınırlar

Çıkarım doğruluğu sistematik olarak ölçülmedi. Elle etiketlenmiş bir test seti
yok, dolayısıyla buradaki sayılar "kuralların yakaladığı beceriler", "ilanlarda
gerçekten geçen beceriler" değil.

Kural tabanlı yaklaşımın bilinen zayıflığı: sözlükte olmayan bir beceri hiç
görünmez, ve "no experience with Kubernetes needed" gibi olumsuz cümleleri
ayırt edemez. LLM yolu bu ikisinde daha iyi olmalı, ama ölçmeden bilinmez.

Ölçmek isteyen için yol: 100-150 ilanı elle etiketle, iki çıkarım yolunu aynı
ilanlarda karşılaştır, alan bazında precision/recall raporla.

Veri kaynağı uzaktan çalışma ilanlarına özel bir platform, dolayısıyla
`work_mode` dağılımı genel iş piyasasını temsil etmiyor.

Veri Remote OK'in o anki feed'inden geliyor, yani belirli bir günün anlık
görüntüsü. Zaman içindeki değişimi göstermiyor.

## Bulgular

<!-- Kendi verinle çalıştırdıktan sonra buraya 3-5 madde yaz. Somut sayı ver.
     Repoyu veri deposu olmaktan çıkarıp bir şey söyleyen projeye çeviren kısım
     burası — README'yi okuyan çoğu kişi sadece bunu okuyacak. -->

- ...
- ...

## Kaynak

İlan verisi [Remote OK](https://remoteok.com) açık API'sinden alınmıştır.
Remote OK verinin kullanıldığı yerde kaynağa bağlantı verilmesini şart koşuyor;
bu README ve pano arayüzü bu bağlantıyı içeriyor. Ham ilan metinleri repoda
yeniden yayınlanmıyor, sadece çıkarılmış alanlar ve toplulaştırılmış sonuçlar
paylaşılıyor.

## Lisans

MIT
