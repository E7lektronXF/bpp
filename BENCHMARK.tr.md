# BENCHMARK — .bpp gerçekten işe yarıyor mu?

> English: [BENCHMARK.md](BENCHMARK.md)

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
primer. Markdown örneği, `bpp x.md`'nin yaptığı gibi kaynağından `encode_md` ile kodlanır.

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
| employees | 5538 | 3562 | 4388 | 2165 | – | 2277 | **2042** | 2088 | **-5.7%** (CSV) |
| config | 601 | 365 | 443 | – | – | 399 | **323** | 369 | **-11.5%** (JSON min) |
| plan | 1609 | 990 | 1212 | – | – | 1228 | **634** | 698 | **-36.0%** (JSON min) |
| project_plan | 1445 | 990 | 1083 | – | 837 | 1024 | **758** | 822 | **-9.4%** (Markdown) |
| orders | 3524 | 2231 | 2636 | – | – | 2276 | **1151** | 1221 | **-48.4%** (JSON min) |
| logs | 5629 | 4109 | 4587 | 3185 | – | 3348 | **1857** | 1903 | **-41.7%** (CSV) |
| **toplam** | 18346 | 12247 | 14349 | | | 10552 | **6765** | 7101 | JSON'a göre **-63.1%**, TOON'a göre **-35.9%** |

### claude2

| örnek | JSON | JSON min | YAML | CSV | Markdown | TOON | **bpp** | bpp+primer | bpp vs en iyi rakip |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| employees | 5669 | 3984 | 4072 | 2501 | – | 2496 | **2084** | 2133 | **-16.5%** (TOON) |
| config | 611 | 393 | 417 | – | – | 389 | **332** | 381 | **-14.7%** (TOON) |
| plan | 1719 | 1078 | 1248 | – | – | 1257 | **727** | 794 | **-32.6%** (JSON min) |
| project_plan | 1683 | 1240 | 1259 | – | 1078 | 1215 | **996** | 1062 | **-7.6%** (Markdown) |
| orders | 3615 | 2455 | 2526 | – | – | 2342 | **1178** | 1252 | **-49.7%** (TOON) |
| logs | 5563 | 4199 | 4456 | 3249 | – | 3332 | **1800** | 1849 | **-44.6%** (CSV) |
| **toplam** | 18860 | 13349 | 13978 | | | 11031 | **7117** | 7471 | JSON'a göre **-62.3%**, TOON'a göre **-35.5%** |

Ayrıntılı tablolar (sözlüksüz `--no-refs` varyantı dahil): `bench/results/tokens.md`.

### 2.1 Kazancın kaynakları

| kaynak | nerede | etkisi |
|---|---|---|
| Anahtarların bir kez yazılması (tablolar) | employees, logs, orders kalemleri, replicas | JSON'a göre −%55…−%60; CSV/TOON ile aynı mekanizma |
| Boşlukla ayrılmış satırlar (`,` yerine) | tüm tablolar | virgüllü tabloya göre −%12 (o200k) / −%22 (claude2). Boşluk bir sonraki token'a kaynaşıyor, virgül kaynaşmıyor |
| `key value` (`:` yok), 1 boşluk girinti | config, orders | `key:value`'ya göre −%3…−%8 |
| Sözlük (`&n` / `*n`) | logs, orders | logs'ta sözlüksüz haline göre −%36 / −%39; orders'ta −%10.4 / −%13.5 |
| Ağaç satırları (`>steps`; bpp4'ten beri tek başına `>`) | plan | JSON min'e göre −%36; iç içe nesneler yerine girintili satırlar |
| Pozisyonel opsiyonel sütun (`status?`, eksikse `-`) — bpp2 | project_plan | bpp1'e göre −%7.6 / −%6.1; kaynak Markdown'ı geçmesini sağlayan değişiklik |
| Sütun yolları (`customer.name`) ve alt tablolar (`>items{...}`) — bpp3 | orders | her siparişi `- ` öğesi olarak yazan bpp2'ye göre −%34.7 / −%35.9 |
| Birleştirilen satır sonları, `\|N` blokları, tek başına `>`, başlıklar için alt tablolar — bpp4 | project_plan, Markdown belgeleri | project_plan 792 → 758 / 1017 → 996; §4.4'teki beş Markdown belgesi 15510 → 14824 / 16094 → 15513 |
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

OpenAI-compatible (OpenAI biçimini kullanan) her API de ek paket gerekmeden çalışır. Sonuçlar
`bench/results/qa-<model>.md` dosyasına yazılır:

```bash
export NVIDIA_API_KEY=nvapi-...                    # build.nvidia.com'dan ücretsiz anahtar
python bench/run_qa.py --provider nvidia           # deepseek-ai/deepseek-v4.1-flash, temperature 0
python bench/run_qa.py --provider nvidia --model openai/gpt-oss-20b
python bench/run_qa.py --provider openai --base-url https://.../v1 --model NAME   # OPENAI_API_KEY
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

### 4.1 Markdown checklist planı — `bpp1`'de kaybediyordu, `bpp2`'de çözüldü

**bpp1'deki durum:** kaynak Markdown .bpp'den +%2.4 / +%0.5 daha ucuzdu (837'ye karşı 857 token).

**Neden:** Plan satırlarının çoğunda `status` var ama hepsinde değil (başlıklar ve bazı maddeler
checkbox'sız). Bu yüzden `status` opsiyonel sütundu ve her satıra `status=done ` yazılıyordu
(3–4 token). Markdown'da aynı bilgi `[x]` (1–2 token). İkinci, daha küçük etken: notlar
`note="..."` olarak tırnaklanıp satır sonları `\n` ile escape ediliyor. Markdown'da aynı notlar
girintili düz satırlar.

**Prototip ölçümü** (aynı veri, elle üretilmiş varyantlar):

| varyant | o200k | claude2 |
|---|---:|---:|
| bpp1 (`status=done`, `note="…"`) | 857 | 1083 |
| status pozisyonel, eksik değer `-` | **786** | **1011** |
| status checkbox `[x]` olarak | 827 | 1058 |
| not metin bloğu (girintili satırlar) | 842 | 1064 |
| checkbox + metin bloğu | 817 | 1044 |
| Markdown (kaynak) | 837 | 1078 |

**Çözüm — R1, `bpp2`'de uygulandı:** Çoğu satırda bulunan opsiyonel sütun artık pozisyonel
yazılıyor; eksik değer `-` ile gösteriliyor ve başlıkta `status?` olarak işaretleniyor. Seyrek
sütunlar `note?=` olarak `note=...` biçiminde kalıyor. Encoder seçimi sütun bazında maliyet
karşılaştırmasıyla yapıyor.

```
steps[5]{status? note?= title}>steps
- Keşif ve envanter
 done note="Toplam 312 Airflow DAG'i, …" Mevcut iş akışlarının envanteri
 done Veri sahipleriyle görüşmeler
```

| | o200k | claude2 |
|---|---:|---:|
| bpp1 | 857 | 1083 |
| **bpp2** | **792** (−%7.6) | **1017** (−%6.1) |
| Markdown (kaynak) | 837 | 1078 |
| bpp2, Markdown'a göre | **−%5.4** | **−%5.7** |

Prototipteki 786 ile gerçek encoder'ın 792'si arasındaki fark başlık gösteriminden geliyor
(`status? note?=`). Bedeli: yalnızca anahtarlı opsiyonel sütun içeren tablolarda başlık sütun başına
bir `=` uzuyor (`plan.json`: 634 → 636). Diğer örneklerde değişiklik yok.

**Kalan token'lar nerede:** 792 token'ın 695'i (o200k; claude2'de 1017'nin 943'ü) başlık ve
notların kendisi; bunlar her formatta aynı tutar. Üstündeki yapı .bpp'de 97, Markdown'da 142 token
(−%32; claude2'de 74'e karşı 135, −%45). Hiç yapısı olmayan bir format bile bu dosyada en fazla ~%12
daha kazandırabilirdi.

**Metin blokları yeniden ölçüldü (R2):** notları `note="…"` yerine satırın altında düz girintili
satırlar olarak yazmak bpp2'de 792 yerine 794 token verdi: kazanılan tırnak ve `note=`, yeni satır,
girinti ve önek olarak geri ödeniyor. R2 elendi.

**bpp4'te çözüldü:** primer eklenince .bpp bu örnekte yine Markdown'dan pahalıydı (876'ya karşı
837, claude2'de 1106'ya karşı 1078). bpp4 Markdown'a kendi, daha kısa primer'ını veriyor (84 / 88
yerine 64 / 65 token) ve kaydırılmış madde satırlarını birleştiriyor (§4.4): primer'le plan artık
822 / 1062 token. Markdown'u her LLM zaten tanır; .bpp'nin primer'siz anlaşılıp anlaşılmadığı
anlama testiyle ölçülmeli (§3).

### 4.2 Primer küçük belgelerde kazancı siliyor

bpp3'ün primer'ı 84 / 88 token'dı: bpp2 `x?` / `x?=` ayrımını, bpp3 yolları ve alt tabloları
açıklamaya ekledi. bpp4'ten beri primer yalnızca dosyanın kullandığı sözdizimini anlatıyor: 40–108
token (SPEC.tr §8). config örneğinde primer'li .bpp (369; bpp3: 407) hâlâ minified JSON'dan (365)
pahalı. Büyük örneklerde (employees, logs) %2–3 ekliyor.

### 4.3 CSV'ye karşı fark küçük (o200k)

Düz tabloda .bpp CSV'den o200k'de yalnızca −%5.7 ucuz. claude2'de fark −%16.5. CSV'nin tip
bilgisi yoktur ve iç içe veri taşıyamaz. Yine de tamamen düz tablo için kazanç tokenizer'a bağlı
ve küçüktür.

### 4.4 Düz yazı ağırlıklı Markdown — `bpp3`'te kaybediyordu, `bpp4`'te çözüldü

**bpp3'teki durum:** çoğu paragraftan oluşan belgelerde .bpp, Markdown kaynağından yaklaşık %3
büyüktü: bu deponun README'si bpp3'te 3845, Markdown'da 3722 token (o200k); SPEC 6488'e karşı 6269,
BENCHMARK 3872'ye karşı 3747, RELEASING 513'e karşı 497. Yalnızca checklist planı küçüktü (837'ye
karşı 792).

**Neden:**

1. **Escape edilen çok satırlı notlar.** Bir başlığın metni onun `note`'udur, çok satırlı bir
   string; JSON string olarak yazılıyordu: iki tırnak, her satır sonu ve tırnak escape'li (`\n`,
   `\"`). Escape edilmiş `\n` kendi başına bir token'dır; ham satır sonu ise önündeki token'a
   kaynaşır (`):\n\n` tek token). Her belgede bu maliyet farkın tamamı kadar ya da daha fazlaydı.
2. **Kaydırılmış liste maddeleri.** Maddenin kaydırılmış ikinci satırı `note`'a gidiyordu. Başlık
   son sütun olduğundan satırda cümlenin ikinci yarısı önce görünüyordu
   (`note=virtualenv. Check https://pypi.org/... in a clean`) ve `note=` ile tırnaklar ödeniyordu.

**Çözüm (bpp4, SPEC.tr §2.2, §7.1, §7.2):** çok satırlı string'ler `|N` blokları olarak yazılıyor
(sonraki N satır, ham), kaydırılmış satırlar bir boşlukla birleştiriliyor, tek başına `>` `>steps`
yerine geçiyor, başlıklar kendi sütunlarını alabiliyor, `**kalın**` artık tırnaklanmıyor ve ağaç
yine de kaynaktan uzunsa `bpp4 md` kaynağın kendisini saklıyor. `bench/corpus/` üzerinde ölçüm
(dört belgenin v0.3.0 hali ve örnek plan; `bench/results/experiments.md`, E10–E15):

| belge | Markdown | bpp3 | **bpp4** |
|---|---:|---:|---:|
| README | 3722 / 3938 | 3845 / 4035 | **3703 / 3894** |
| SPEC | 6269 / 6483 | 6488 / 6628 | **6144 / 6330** |
| BENCHMARK | 3747 / 3802 | 3872 / 3861 | **3724 / 3756** |
| RELEASING | 497 / 543 | 513 / 553 | **495 / 537** |
| project_plan | 837 / 1078 | 792 / 1017 | **758 / 996** |
| **toplam** | 15072 / 15844 | 15510 / 16094 | **14824 / 15513** |

(o200k / claude2.) bpp3 sütunu v0.3.0 encoder'ıyla ölçüldü.

**Geriye kalan:** düz yazıda bpp4, Markdown'dan yalnızca %0.4–2 küçük. Metnin kendisi ikisinde de
aynı tutuyor; bpp `#`, `-` ve `1.` işaretlerinden kazanıyor, başlığına, tablo başlığına ve `note=`
işaretlerine ödüyor. RELEASING'de fark 2 token. `bpp4 md` yedeği sayesinde ağacın uzatacağı bir
dosya yalnızca 5 token'lık başlık satırı kadar büyür (encoder'ın tahminine göre; bu dosyalarda
gerçek tokenizer'lar da aynı fikirde).

## 5. SPEC revizyon önerileri

| # | öneri | gerekçe | durum |
|---|---|---|---|
| R1 | **Sık görülen opsiyonel sütun pozisyonel yazılsın**; eksik değer `-` (string `"-"` tırnaklanır). Başlıkta `x?` pozisyonel, `x?=` anahtarlı. Encoder sütun bazında `eksik·t(" -")` ile `mevcut·t(" x=")` maliyetini karşılaştırarak seçer. | §4.1: −%7.6 / −%6.1, Markdown'dan −%5.4 / −%5.7 ucuz | **uygulandı (`bpp2`)** |
| R2 | Çok satırlı metin sütunları için **metin bloğu**: satırın altında, çocuk satırlardan ayırt edilebilir girintili satırlar | §4.1: ek −%1.8 | bpp2'de **elendi** (792 yerine 794 token; §4.1); **bpp4'te** satır sayısıyla sınırlanan, girintisiz `\|N` bloklarıyla **yerine konuldu** (§4.4) |
| R3 | Primer yalnızca belge büyükse eklensin (ör. `--primer auto`: gövde > 1000 token) | §4.2 | önerilir; bpp4 primer'ı zaten kullanılan sözdizimine indirdi (40–108 token); eşik anlama testinden seçilmeli |
| R4 | Sözlük eşiği anlama testine göre ayarlanabilsin (`--refs min-gain=N`); doğruluk düşerse yalnızca çok tekrarlanan uzun değerlerde kullanılsın | §3 risk 1 | anlama testi sonrasına bağlı |
| R5 | Liste öğelerindeki iç içe nesneler (orders'taki `customer`) satır tablosunda noktalı sütunlara (`customer.name`), alt listeler alt tablolara açılsın | orders `- ` öğeleriyle yazılıyordu | **uygulandı (`bpp3`)**: orders −%34.7 / −%35.9 (SPEC §4.3.1) |
| R6 | Markdown: `\|N` blokları, birleştirilen yumuşak satır sonları, Markdown primer'ı ve kaynağa dönen `bpp4 md` yedeği | §4.4: bpp3 düz yazılı Markdown'a ~%3 kaybediyordu | **uygulandı (`bpp4`)**: §4.4'teki her belge kaynağından küçük |

R1 `bpp2`, R5 `bpp3`, R6 `bpp4` olarak uygulandı. Decoder `bpp1`, `bpp2` ve `bpp3` dosyalarını okumaya
devam eder ([SPEC.tr.md](SPEC.tr.md) §11).
