# BENCHMARK — .bpp gerçekten işe yarıyor mu?

Kısa cevap: **token tarafında evet, ölçüldü. Anlama tarafında henüz bilinmiyor**, çünkü bu
ortamda `ANTHROPIC_API_KEY` yoktu. Anlama testi yazıldı ve çalışmaya hazır (§3). Aşağıdaki her
sayı depodaki betiklerle yeniden üretilebilir:

```bash
python bench/make_examples.py   # examples/ klasörünü üretir
python bench/run_tokens.py      # -> bench/results/tokens.md, tokens.json
python bench/run_qa.py          # -> bench/results/qa.md (API anahtarı gerekir)
```

## 1. Yöntem

**Veriler** (`examples/`):

| örnek | dosya | içerik |
|---|---|---|
| employees | `employees.csv` | Düz tablo: 60 çalışan × 10 sütun, Türkçe isim/şehirler |
| config | `config.yaml` | İç içe servis konfigürasyonu (4 seviye, küçük tablolar, listeler) |
| plan | `plan.json` | Yapılandırılmış plan: 6 adım + 21 alt adım; `id`, `status`, `priority`, `deps`, `owner`, `note` |
| project_plan | `project_plan.md` | Uzun Markdown plan: başlıklar, iç içe checkbox listeleri, notlar, kod bloğu |
| orders | `orders.json` | Karışık yapı: API yanıtı, 20 sipariş, iç içe müşteri nesnesi, kalem tabloları, serbest metin |
| logs | `logs.json` | 80 log kaydı; uzun değerler (mesaj, servis adı) çok tekrarlı |

**Formatlar:** JSON (2 boşluk girinti), minified JSON, YAML (PyYAML, `allow_unicode`), CSV
(yalnızca düz tablolarda), Markdown (yalnızca md örneğinde, kaynak dosya), TOON (referans
`@toon-format/toon` 4.1.1, varsayılan ayarlar), `.bpp` (varsayılan ayarlar) ve `.bpp` + 1 satır
primer.

**Token sayaçları:**

* **o200k** — tiktoken `o200k_base`.
* **claude2** — Anthropic'in yayımladığı eski Claude tokenizer'ı (`@anthropic-ai/tokenizer`).

İkisi de güncel Claude modellerinin tokenizer'ı **değildir**. Anthropic dokümanına göre
tiktoken, Claude token'larını tipik metinde %15–20, Türkçe gibi İngilizce dışı metinde daha fazla
eksik sayar. Mutlak sayılar bu yüzden temsili değildir; güvenilen şey formatlar arasındaki
göreli farktır. İki bağımsız tokenizer'ın aynı yönde sonuç vermesi bu farkların tokenizer'a özgü
olmadığına işaret eder. `ANTHROPIC_API_KEY` tanımlıysa `run_tokens.py` ve `bpp stats` gerçek
`count_tokens` sonucunu üçüncü sütun olarak ekler.

## 2. Token sonuçları

### o200k

| örnek | JSON | JSON min | YAML | CSV | Markdown | TOON | **bpp** | bpp+primer | bpp vs en iyi rakip |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| employees | 5538 | 3562 | 4388 | 2165 | – | 2277 | **2042** | 2102 | **−5.7%** (CSV) |
| config | 601 | 365 | 443 | – | – | 399 | **323** | 383 | **−11.5%** (JSON min) |
| plan | 1609 | 990 | 1212 | – | – | 1228 | **634** | 694 | **−36.0%** (JSON min) |
| project_plan | 1501 | 1025 | 1119 | – | 837 | 1093 | 857 | 917 | **+2.4%** (Markdown) ❌ |
| orders | 3524 | 2231 | 2636 | – | – | 2276 | **1762** | 1822 | **−21.0%** (JSON min) |
| logs | 5629 | 4109 | 4587 | 3185 | – | 3348 | **1857** | 1917 | **−41.7%** (CSV) |
| **toplam** | 18402 | 12282 | 14385 | | | 10621 | **7475** | 7835 | JSON'a göre **−59.4%**, TOON'a göre **−29.6%** |

### claude2

| örnek | JSON | JSON min | YAML | CSV | Markdown | TOON | **bpp** | bpp+primer | bpp vs en iyi rakip |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| employees | 5669 | 3984 | 4072 | 2501 | – | 2496 | **2084** | 2148 | **−16.5%** (TOON) |
| config | 611 | 393 | 417 | – | – | 389 | **332** | 396 | **−14.7%** (TOON) |
| plan | 1719 | 1078 | 1248 | – | – | 1257 | **726** | 790 | **−32.7%** (JSON min) |
| project_plan | 1737 | 1265 | 1288 | – | 1078 | 1273 | 1083 | 1147 | **+0.5%** (Markdown) ❌ |
| orders | 3615 | 2455 | 2526 | – | – | 2342 | **1839** | 1903 | **−21.5%** (TOON) |
| logs | 5563 | 4199 | 4456 | 3249 | – | 3332 | **1800** | 1864 | **−44.6%** (CSV) |
| **toplam** | 18914 | 13374 | 14007 | | | 11089 | **7864** | 8248 | JSON'a göre **−58.4%**, TOON'a göre **−29.1%** |

Ayrıntılı tablolar (sözlüksüz `--no-refs` varyantı dahil): `bench/results/tokens.md`.

### 2.1 Kazancın kaynakları

| kaynak | nerede | etkisi |
|---|---|---|
| Anahtarların bir kez yazılması (tablolar) | employees, logs, orders kalemleri, replicas | JSON'a göre −%55…−%60; CSV/TOON ile aynı mekanizma |
| Boşlukla ayrılmış satırlar (`,` yerine) | tüm tablolar | virgüllü tabloya göre −%12 (o200k) / −%22 (claude2). Boşluk bir sonraki token'a kaynaşıyor, virgül kaynaşmıyor |
| `key value` (`:` yok), 1 boşluk girinti | config, orders | `key:value`'ya göre −%3…−%8 |
| Sözlük (`&n` / `*n`) | logs, orders | logs'ta sözlüksüz haline göre −%36 / −%39; orders'ta −%4.5 / −%7.3 |
| Ağaç satırları (`>steps`) | plan | JSON min'e göre −%36; iç içe nesneler yerine girintili satırlar |
| Minimum tırnak + ham UTF-8 | her yerde | `\u` escape'i Türkçe metinde +%124…+%161 token olurdu |

**Sözlüğün payı:** logs örneğindeki büyük farkın çoğu sözlükten geliyor. Sözlük kapatıldığında
(`--no-refs`) .bpp logs'ta 2921 / 2952 token, yani CSV'den yalnızca −%8 / −%9 ucuz. TOON'da sözlük
mekanizması yoktur.

## 3. Anlama testi (çalıştırılmadı)

`bench/run_qa.py` her örnek için veriden hesaplanan cevaplarıyla **10 soru** üretir:

* doğrudan erişim ("id 17'nin adı"),
* iç içe erişim ("ikinci replika host'u"),
* sayma ("kaç sipariş iptal edilmiş"),
* bağımlılık ve ebeveyn ilişkisi ("5.2 hangi adımlara bağlı"),
* sözlük referansı çözme (logs'taki mesajlar).

Aynı sorular her formattaki veriyle birlikte tek istekte Claude'a sorulur. Cevaplar otomatik
notlanır: sayısal karşılaştırma, liste için küme eşitliği, metin için normalize eşitlik.
`--dry-run` tüm soruları ve beklenen cevapları gösterir; notlama mantığı `tests/test_bench.py`
ile test edilir.

```bash
pip install ".[api]"
export ANTHROPIC_API_KEY=...
python bench/run_qa.py --dry-run                   # soruları ve beklenen cevapları gör
python bench/run_qa.py                             # claude-opus-5, effort low, 1 tekrar
python bench/run_qa.py --repeats 3 --effort high   # daha sağlam ölçüm
python bench/run_qa.py --model claude-sonnet-5 --examples plan logs
```

Varsayılan çalıştırma 39 istek ve ~60 bin giriş token'ıdır. Refusal fallback bilerek **kapalıdır**:
bir fallback başka bir modelle cevap verip karşılaştırmayı bozardı. Refusal'lar yanlış sayılır ve
raporlanır.

**Anlama tarafındaki riskler (hipotezler, ölçülmedi):**

1. **Sözlük dolaylılığı.** Model `*3`'ü `&3` tanımına çözmek zorunda. Logs'taki "şu mesaja sahip
   kaç kayıt var" sorusu tam bunu ölçer. En büyük kazanç (logs −%42) en büyük anlama riskini
   de taşıyor.
2. **Başlık–sütun eşleme.** 10 sütunlu boşluklu satırlarda modelin değerleri doğru sütuna
   eşlemesi gerekir. Değerler sıralı ve başlık bir kez yazılı. CSV/TOON ile aynı zorluk, ama
   ayraç olarak virgül yerine boşluk var.
3. **İki nokta üst üste olmayan `key value`.** YAML/TOML'a göre daha az sinyal taşıyor.
4. **Primer'siz okuma.** `x?` ve `>steps` gibi gösterimler primer olmadan tahmin edilebilir mi?
   Bu yüzden testte primer'li ve primer'siz .bpp ayrı satırlar olarak yer alıyor.

## 4. Kaybedilen kategoriler ve nedenleri

### 4.1 Markdown checklist planı: Markdown +%2.4 / +%0.5 daha ucuz

**Neden:** Plan satırlarının çoğunda `status` var ama hepsinde değil (başlıklar ve bazı maddeler
checkbox'sız). Bu yüzden encoder `status`'u **opsiyonel** sütun yapıyor ve her satıra
`status=done ` yazıyor (3–4 token). Markdown'da aynı bilgi `[x]` (1–2 token). İkinci, daha küçük
etken: notlar `note="..."` olarak tırnaklanıp satır sonları `\n` ile escape ediliyor. Markdown'da
aynı notlar girintili düz satırlar.

**Prototip ölçümü** (aynı veri, elle üretilmiş varyantlar):

| varyant | o200k | claude2 |
|---|---:|---:|
| mevcut `.bpp` (`status=done`, `note="…"`) | 857 | 1083 |
| status pozisyonel, eksik değer `-` | **786** | **1011** |
| status checkbox `[x]` olarak | 827 | 1058 |
| not metin bloğu (girintili satırlar) | 842 | 1064 |
| checkbox + metin bloğu | 817 | 1044 |
| Markdown (kaynak) | 837 | 1078 |

### 4.2 Primer küçük belgelerde kazancı siliyor

1 satırlık primer 60–63 token. config örneğinde primer'li .bpp (383) minified JSON'dan (365) daha
pahalı. Büyük belgelerde etkisi %2–3.

### 4.3 CSV'ye karşı fark küçük (o200k)

Düz tabloda .bpp CSV'den o200k'de yalnızca −%5.7 ucuz. claude2'de fark −%16.5. CSV'nin tip
bilgisi yoktur ve iç içe veri taşıyamaz. Yine de tamamen düz tablo için kazanç tokenizer'a bağlı
ve küçüktür.

## 5. SPEC revizyon önerileri

| # | öneri | gerekçe | durum |
|---|---|---|---|
| R1 | **Sık görülen opsiyonel sütun pozisyonel yazılsın**; eksik değer için ayrılmış bir işaret (`-`, string `"-"` tırnaklanır). Başlıkta ayrı bir gösterim gerekir (ör. `status?-`). Encoder sütun bazında `eksik·t("-")` ile `mevcut·t("status=")` maliyetini karşılaştırarak seçer. | §4.1: −%8.3 / −%6.6, Markdown'ı ~%6 geçiyor | ölçüldü, uygulanmadı |
| R2 | Çok satırlı metin sütunları için **metin bloğu**: satırın altında, çocuk satırlardan ayırt edilebilir girintili satırlar | §4.1: ek −%1.8 | ölçüldü, uygulanmadı; çocuk satırlarla belirsizlik tasarımı gerekiyor |
| R3 | Primer yalnızca belge büyükse eklensin (ör. `--primer auto`: gövde > 1000 token) | §4.2 | önerilir; anlama testi primer'in katkısını gösterirse eşik oradan seçilmeli |
| R4 | Sözlük eşiği anlama testine göre ayarlanabilsin (`--refs min-gain=N`); doğruluk düşerse yalnızca çok tekrarlanan uzun değerlerde kullanılsın | §3 risk 1 | anlama testi sonrasına bağlı |
| R5 | Liste öğelerindeki iç içe nesneler (orders'taki `customer`) satır tablosunda noktalı sütun (`customer.name`) olarak düzleştirilsin | orders hâlâ `- ` öğeleriyle yazılıyor | **ölçülmedi**; E2'de noktalı anahtarlar config için kötüydü (claude2 +%22), tablolarda ayrıca ölçülmeli |

R1 ve R2, SPEC'in `bpp2` sürümü için adaylardır. `bpp1` decoder'ı bu gösterimleri
tanımayacağından başlık satırındaki sürüm değişmelidir.
