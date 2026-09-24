# bpp — LLM'e veri verirken daha az token

`.bpp`, JSON/YAML/CSV verisini ve Markdown planlarını bir LLM'in **daha az token ile** okuyacağı
bir metne çevirir, sonra kayıpsız geri çevirir. Örnek setlerde toplam token sayısı JSON'a göre
**~%59**, TOON'a göre **~%30** daha az ([BENCHMARK.md](BENCHMARK.md)).

## 30 saniyede

```bash
pip install .

bpp data.json          # -> data.bpp      (config.json -> config.bpp (o200k: 601 -> 323 tokens, -46%))
bpp data.bpp -o x.json # -> x.json        (JSON'a geri, kayıpsız)
bpp stats data.json    # JSON / YAML / CSV / TOON / bpp token karşılaştırması
```

Bu kadar. `bpp DOSYA` uzantıya bakar: `.json .yaml .csv .md` → `.bpp` üretir, `.bpp` → JSON'a
çevirir. Diğer biçimler için `--to yaml|csv|md`, ekrana yazdırmak için `-o -` kullanılır.

Python'da `json` modülü gibi:

```python
import bpp

text = bpp.dumps(data)          # Python nesnesi -> .bpp metni
data = bpp.loads(text)          # .bpp metni -> Python nesnesi

data = bpp.load("config.yaml")  # .json .yaml .csv .md .bpp dosyası okur
bpp.dump(data, "config.bpp")    # biçimi uzantıdan seçer
```

## Nasıl görünüyor?

<table>
<tr><th>JSON (601 token)</th><th>.bpp (323 token)</th></tr>
<tr><td>

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "tls": {"enabled": true}
  },
  "replicas": [
    {"host": "db-1.internal", "port": 5432, "weight": 2},
    {"host": "db-2.internal", "port": 5432, "weight": 1}
  ],
  "regions": ["TR", "DE", "NL"]
}
```

</td><td>

```
bpp1
server
 host 0.0.0.0
 port 8080
 tls
  enabled true
replicas[2]{host port weight}
db-1.internal 5432 2
db-2.internal 5432 1
regions [TR,DE,NL]
```

</td></tr>
</table>

(Token sayıları `examples/config.yaml`'ın tamamı içindir. Yukarıdaki parça o dosyanın kısaltılmış
halidir.)

Bir plan (`examples/plan.json`, JSON'da 1609 token, .bpp'de 634):

```
steps[6]{id:str status priority deps:str owner? note? title}>steps
1 done P1 [] owner=Ayşe Gereksinim analizi
 1.1 done P1 [] Paydaş görüşmeleri
 1.2 done P0 [] Regülasyon incelemesi (BDDK, PCI-DSS)
 1.3 done P1 [1.1] Kabul kriterlerinin yazılması
2 done P1 [1] owner=Mehmet Mimari tasarım
```

Kurallar kısaca:

* `anahtar değer` satırları; tek başına `anahtar` iç içe nesne açar (1 boşluk girinti).
* `ad[N]{a b c}` → N satır, değerler sütun sırasıyla boşlukla ayrılmış, **son sütun satırın
  geri kalanı**. `x?` opsiyonel sütun, satırda `x=değer` diye yazılır. `>steps` → girintili
  satırlar üstteki satırın alt adımlarıdır.
* `"..."` → JSON string (yalnızca gerektiğinde tırnak). `[a,b]` → liste.
* `&0 uzun metin` bir kez tanımlanır, sonra `*0` diye kullanılır.

Tam tanım: [SPEC.md](SPEC.md). `examples/` klasöründe her örneğin kaynak dosyası ve `.bpp`
karşılığı yan yana duruyor.

## LLM'e verirken

```bash
bpp data.json -o - --primer | pbcopy    # başına 1 satırlık açıklama ekler (~60 token)
```

Formatı hiç görmemiş bir model için dosyanın başına şu `#` yorum satırı eklenir (decoder yok
sayar):

```
# bpp1: JSON as 'key value' lines, 1-space indent nests. k[N]{a b}: N rows of values in column order, last column = rest of line, x? columns appear as x=v. "..." = JSON string, *n = &n.
```

Küçük belgelerde (birkaç yüz token) primer kazancı silebilir; BENCHMARK §4.2'ye bakın.

## Sonuçlar (özet)

| örnek | JSON | minified JSON | TOON | **.bpp** | .bpp en iyi rakibe göre |
|---|---:|---:|---:|---:|---|
| 60×10 tablo (CSV) | 5538 | 3562 | 2277 | **2042** | −%6 (CSV) |
| iç içe config (YAML) | 601 | 365 | 399 | **323** | −%12 (min. JSON) |
| yapılandırılmış plan (JSON) | 1609 | 990 | 1228 | **634** | −%36 (min. JSON) |
| Markdown plan | 1501 | 1025 | 1093 | 857 | **+%2 (Markdown kaybettirir)** |
| karışık API yanıtı | 3524 | 2231 | 2276 | **1762** | −%21 (min. JSON) |
| tekrarlı loglar | 5629 | 4109 | 3348 | **1857** | −%42 (CSV) |

o200k token'ı. claude2 tokenizer'ı ile sonuçlar aynı yönde. Ayrıntılar, anlama testi ve
kaybedilen durumların analizi için [BENCHMARK.md](BENCHMARK.md). **Not:** anlama/doğruluk testi
yazıldı ama API anahtarı olmadığı için henüz çalıştırılmadı (`python bench/run_qa.py`).

## Kurulum seçenekleri

```bash
pip install .            # yalnızca PyYAML gerekir
pip install ".[stats]"   # + tiktoken: bpp stats token sayar
pip install ".[api]"     # + anthropic: gerçek Claude token sayımı ve anlama testi
pip install -e ".[dev]"  # + pytest, hypothesis
```

Python ≥ 3.9.

## Tüm komutlar

Kısayol (`bpp DOSYA`) çoğu iş için yeterlidir. Ayrıntılı alt komutlar:

```bash
bpp encode data.json -o data.bpp [--primer none|short|long] [--no-refs] [--keep-order]
bpp encode - --from yaml < config.yaml          # stdin
bpp decode data.bpp -o data.yaml                # biçim -o uzantısından
bpp decode data.bpp --to json --indent -1       # minified JSON'a
bpp decode plan.bpp --to md
bpp stats data.json [--markdown]
```

| seçenek | etkisi |
|---|---|
| `--primer` | Başa açıklama satırı ekler (`short` ~60, `long` ~110 token). |
| `--no-refs` | `&n`/`*n` sözlüğünü kapatır. |
| `--keep-order` | Anahtar sırasını hiç değiştirmez. Varsayılanda encoder, `title` gibi bir metin sütununu satır sonuna taşıyabilir (veri aynı, JSON'daki anahtar sırası farklı). CSV'de her zaman açık. |
| `-f/--force` | Kısayol modunda var olan dosyanın üzerine yazar (varsayılan: yazmaz). |

## Kayıpsızlık

* **JSON / YAML:** `loads(dumps(x)) == x`, tipler dahil (`1` ≠ `1.0`, `"42"` ≠ `42`, `null`).
  `--keep-order` ile JSON metni anahtar sırasıyla birlikte birebir geri gelir. YAML yorumları ve
  anchor'ları veri değildir, korunmaz. Tarihler string olarak okunur.
* **CSV:** hücreler ve sütun sırası birebir korunur. Sayıya çevirme yalnızca geri yazınca aynı
  metni veriyorsa yapılır (`007`, `1.50` string kalır). Satırsız, yalnız başlıktan oluşan CSV'de
  başlık kaybolur.
* **Markdown:** yapı korunur, biçim korunmaz. Başlıklar ve iç içe listeler ağaca dönüşür;
  `- [ ]` / `[x]` / `[/]` / `[-]` → `status` todo / done / doing / cancelled; paragraflar ve kod
  blokları `note` olur.

## Token sayımı

`bpp stats` kurulu olan sayaçları kullanır:

* **o200k** (tiktoken). İndirme sunucusuna erişilemezse aynı dosyayı npm'den alır ve SHA-256
  ile doğrular.
* **claude2**: Anthropic'in yayımladığı eski Claude tokenizer'ı.
* **anthropic**: `ANTHROPIC_API_KEY` varsa gerçek `count_tokens`. Varsayılan model
  `claude-opus-5`; `BPP_ANTHROPIC_MODEL` ile değiştirilir.

İlk ikisi güncel Claude için yalnızca vekildir; formatlar arası göreli fark için kullanılır. TOON
satırı için `cd bench/toon && npm install` gerekir.

## Geliştirme

```bash
pip install -e ".[dev]"
pytest -q                      # 205 test: round-trip, uç durumlar, hypothesis, CLI
python bench/run_tokens.py     # token benchmark'ını yeniden üret
python bench/experiments.py    # SPEC'teki tasarım deneyleri
```

```
SPEC.md          format spesifikasyonu ve her kararın ölçümü
BENCHMARK.md     token sonuçları, anlama testi, kayıplar ve revizyon önerileri
src/bpp/         encoder, decoder, dönüştürücüler, CLI
examples/        örnek girdiler ve .bpp karşılıkları
bench/           deneyler, benchmark ve anlama testi betikleri
tests/           pytest + hypothesis
```
