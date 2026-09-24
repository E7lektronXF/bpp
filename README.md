# bpp — LLM'ler için token-verimli veri formatı

`.bpp`, JSON veri modelini (nesne, dizi, string, sayı, bool, null) bir LLM'in **daha az token
harcayarak** ve yapıyı kaybetmeden okuyabileceği bir metin biçiminde yazar. İnsan
okunabilirliği hedef değildir; her tasarım kararı token ölçümüyle verilmiştir
(bkz. [SPEC.md](SPEC.md), [bench/results/experiments.md](bench/results/experiments.md)).

Bu depo iki şey içerir:

* **Format spesifikasyonu** — [SPEC.md](SPEC.md)
* **Çift yönlü çevirici** — `bpp` Python paketi ve CLI (JSON / YAML / CSV / Markdown ↔ .bpp)

## Kısa örnek

```json
{"service": {"name": "order-api", "port": 8080, "debug": false},
 "replicas": [{"host": "db-1.internal", "port": 5432, "weight": 2},
              {"host": "db-2.internal", "port": 5432, "weight": 1}],
 "regions": ["TR", "DE", "NL"]}
```

```
bpp1
service
 name order-api
 port 8080
 debug false
replicas[2]{host port weight}
db-1.internal 5432 2
db-2.internal 5432 1
regions [TR,DE,NL]
```

* `anahtar değer` satırları; tek başına `anahtar` iç içe nesne açar (1 boşluk girinti).
* Nesne dizileri bir kez yazılan başlık + satırlar olarak: `ad[N]{sütunlar}`.
* Tekrarlanan uzun string'ler bir sözlüğe alınır: `&0 uzun değer` … `*0`.
* Planlar/ağaçlar girintili satırlarla: `steps[6]{id:str status priority deps:str owner? title}>steps`.

## Kurulum

```bash
pip install .            # yalnızca PyYAML gerekir
pip install ".[stats]"   # + tiktoken (bpp stats için token sayımı)
pip install ".[api]"     # + anthropic (gerçek Claude token sayımı / anlama testi)
pip install -e ".[dev]"  # + pytest, hypothesis (geliştirme)
```

Python ≥ 3.9.

## Kullanım

```bash
# JSON / YAML / CSV / Markdown -> .bpp
bpp encode data.json -o data.bpp
bpp encode config.yaml -o config.bpp
bpp encode table.csv -o table.bpp
bpp encode plan.md -o plan.bpp
bpp encode data.json --primer short     # formatı bilmeyen LLM için 1 satırlık açıklama
cat data.json | bpp encode - --from json # stdin

# .bpp -> JSON / YAML / CSV / Markdown
bpp decode data.bpp -o data.json          # biçim -o uzantısından
bpp decode data.bpp --to yaml
bpp decode data.bpp --to json --indent -1 # minified
bpp decode plan.bpp --to md

# Token karşılaştırması: JSON, minified JSON, YAML, CSV, TOON, .bpp
bpp stats data.json
bpp stats plan.md --markdown
```

`bpp encode` seçenekleri:

| seçenek | etkisi |
|---|---|
| `--primer none\|short\|long` | Başa 0 / 1 / 3 satırlık `#` açıklama ekler (~38 / ~100 token). |
| `--no-refs` | `&n`/`*n` sözlüğünü kapatır. |
| `--keep-order` | Anahtar sırasını hiçbir koşulda değiştirmez (bkz. SPEC §4.3). CSV girdisinde her zaman açık. |

Python'dan:

```python
import bpp

text = bpp.encode({"users": [{"id": 1, "name": "Ayşe"}, {"id": 2, "name": "Can"}]})
assert bpp.decode(text) == {"users": [{"id": 1, "name": "Ayşe"}, {"id": 2, "name": "Can"}]}
```

## Kayıpsızlık

* **JSON / YAML:** `decode(encode(x)) == x` (tipler dahil: `1` ≠ `1.0`, `"42"` ≠ `42`, `null`).
  Anahtar sırası korunur; tek istisna, encoder'ın bir metin sütununu satır sonuna taşıdığı satır
  tablolarıdır (`--keep-order` bunu kapatır). YAML'da yorumlar/anchor'lar/etiketler veri modeline
  ait olmadığı için korunmaz; tarih değerleri string olarak okunur.
* **CSV:** hücre metinleri ve sütun sırası birebir korunur (`bpp decode --to csv` aynı hücreleri
  üretir). Sayı/bool dönüşümü yalnızca metne geri yazıldığında aynı metni veriyorsa yapılır
  (`007`, `1.50` string kalır); boş hücre `null` olur ve boş hücreye geri döner. Yalnız başlıktan
  oluşan (satırsız) CSV'de başlık korunmaz.
* **Markdown:** yapı korunur, biçim korunmaz. Başlıklar ve iç içe listeler ağaca çevrilir;
  `- [ ]` / `- [x]` / `- [/]` / `- [-]` → `status` todo / done / doing / cancelled; paragraflar ve
  kod blokları `note` olur. `decode --to md` normalize edilmiş bir Markdown yazar ve bu tekrar
  okunduğunda aynı ağacı verir.

## Token sayımı hakkında

`bpp stats` şu sayaçları kullanır (kurulu olanlar):

* **o200k** — tiktoken `o200k_base`. İndirme sunucusuna erişilemiyorsa aynı dosya npm'deki
  `js-tiktoken` paketinden alınır ve tiktoken'ın yayımladığı SHA-256 ile doğrulanır.
* **claude2** — Anthropic'in npm'de yayımladığı eski Claude tokenizer'ı
  (`@anthropic-ai/tokenizer`); `~/.cache/bpp/` altına indirilir.
* **anthropic** — `ANTHROPIC_API_KEY` tanımlı ve `anthropic` paketi kuruluysa gerçek
  `messages.count_tokens` sonucu (varsayılan model `claude-opus-5`, `BPP_ANTHROPIC_MODEL` ile
  değiştirilebilir).

o200k ve claude2 güncel Claude modelleri için yalnızca vekildir; formatlar arasındaki **göreli**
fark için kullanılır. TOON karşılaştırması için `bench/toon/` içinde `npm install` çalıştırılmış
olmalıdır (referans `@toon-format/toon` uygulaması Node ile çağrılır).

## Depo yapısı

```
SPEC.md               format spesifikasyonu ve ölçüm gerekçeleri
src/bpp/              encoder, decoder, format dönüştürücüler, CLI, token sayaçları
bench/experiments.py  tasarım deneyleri -> bench/results/experiments.md
bench/datasets.py     deterministik örnek veriler
bench/toon/           referans TOON uygulamasına köprü (yalnızca karşılaştırma için)
```
