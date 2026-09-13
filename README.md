# İlan Beceri Radarı

Uzaktan çalışma ilanlarından LLM ile yapılandırılmış beceri çıkarımı, ve çıkan
veriden bir analiz panosu.

Serbest formatlı ilan metni giriyor, sabit şemalı JSON çıkıyor: istenen
beceriler, seviye, deneyim yılı, çalışma şekli, rol ailesi. Sonra bu veriden
"hangi beceriler birlikte isteniyor" ve "hangi beceri hangi maaş bandında
geçiyor" sorularına bakılıyor.

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

cp .env.example .env
```

## Çalıştırma

```bash
python src/fetch_jobs.py --limit 300 --tags dev,engineer,python,javascript,data,devops
python src/extract_rules.py --verbose
python src/analyze.py
streamlit run src/app.py
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

Rol sınıflandırması ilanların bir kısmında karar veremiyor ("other"), ve teknik
rol sayılan 89 ilanın 30'unda hiç beceri bulunamıyor. Bunlar genelde kısa
yazılmış ilanlar; kural tabanlı yaklaşımın doğal sınırı.

## Bulgular

300 ilan çekildi, bunların 89'u teknik rol olarak sınıflandı. Sayılar küçük,
dolayısıyla aşağıdakiler bu anlık görüntüye ait gözlemler, piyasa iddiası değil.

- **Python + SQL en sık birlikte istenen çift** (17 ilan). Tek tek de zaten
  ilk sıradalar: Python 24, SQL 20 ilanda geçiyor.

- **Çoklu bulut beklentisi belirgin.** AWS ve Google Cloud 8 ilanda birlikte
  (lift 4.62), Azure ve Google Cloud 7 ilanda (lift 4.72). Tek bulut sağlayıcı
  bilmek yetmiyor gibi görünüyor.

- **En güçlü bağ frontend üçlüsünde:** CSS ve HTML 11 ilanda birlikte, lift
  7.42 ile listenin tepesinde. Buna JavaScript de ekleniyor (HTML+JS 12 ilan).

- **Veri tarafında Snowflake ayrışıyor.** "data engineering" ile Snowflake
  4 ilanda birlikte, lift 7.42. Küçük sayı ama bağ çok güçlü.

- **İlanların çoğu seviye belirtmiyor.** 89 teknik ilanın 61'inde başlıkta veya
  metinde açık bir seviye ifadesi yok. Belirtenlerde lead (11) sayısı senior (7)
  ve junior (7) toplamına yakın.

- **İstenen deneyim medyanı 3 yıl.** Yıl sayısı belirten 31 ilanda dağılım
  3 yıl (10 ilan), 2 yıl (8), 1 yıl (6) şeklinde yoğunlaşıyor.

- **Maaş neredeyse hiç açıklanmıyor.** 89 teknik ilanın sadece 5'inde maaş
  aralığı var, bu yüzden beceri-maaş grafiği anlamlı sonuç üretmiyor.

### Çıkarım sürecinden çıkan iki bulgu

Bunlar veri hakkında değil, veriyle çalışma hakkında:

**Kaynağın etiketleri güvenilmez.** İlk çalıştırmada Go, Python'dan sonra ikinci
sıradaydı. Şüphelenip baktığımda 60 ilanın içinde İK uzmanı, makine operatörü ve
teknisyen ilanları vardı. Sebep: Remote OK ilanlara ilanla alakasız etiketler
ekliyor, bir pazarlama asistanı ilanının etiketleri arasında `golang` geçiyor.
Etiket alanı çıkarımdan tamamen çıkarıldığında Go ilk 10'dan düştü.

**Kısa dil isimleri bağlam ister.** `in go` kalıbı "go-to-market strategy"
ifadesini, bare `rest` kalıbı "the rest of the team" cümlesini, `swift` kalıbı
"swift action" ifadesini yakalıyordu. Üçü de bağlam isteyen kalıplarla
değiştirildi (`STRICT_SKILLS`).

## Kaynak

İlan verisi [Remote OK](https://remoteok.com) açık API'sinden alınmıştır.
Remote OK verinin kullanıldığı yerde kaynağa bağlantı verilmesini şart koşuyor;
bu README ve pano arayüzü bu bağlantıyı içeriyor. Ham ilan metinleri repoda
yeniden yayınlanmıyor, sadece çıkarılmış alanlar ve toplulaştırılmış sonuçlar
paylaşılıyor.

## Lisans

MIT
