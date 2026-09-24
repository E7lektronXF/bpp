# bpp — LLM'e veri verirken daha az token

`.bpp`, JSON/YAML/CSV verisini ve Markdown planlarını bir LLM'in **daha az token ile** okuyacağı
bir metne çevirir, sonra kayıpsız geri çevirir. Örnek setlerde toplam token sayısı JSON'a göre
**~%59**, TOON'a göre **~%30** daha az ([BENCHMARK.md](BENCHMARK.md)).

Bir benzetmeyle: bpp, veriyi LLM'e göndermeden önce vakumlu paketlemek gibidir. İçerik aynı
kalır, kapladığı yer (token) küçülür, açınca her şey eskisi gibi çıkar.

## Kurulum (5 dakika)

### 1. Python var mı?

Bir terminal açın:

* **Windows:** Başlat menüsüne `PowerShell` yazıp açın.
* **macOS:** Spotlight'a (⌘ + Boşluk) `Terminal` yazıp açın.
* **Linux:** Terminal uygulamasını açın.

Şunu yazın:

```bash
python --version        # Windows'ta çalışmazsa:  py --version
```

`Python 3.9` veya daha yeni bir sürüm görüyorsanız 2. adıma geçin. Görmüyorsanız
[python.org/downloads](https://www.python.org/downloads/) adresinden Python'u kurun. **Windows'ta
kurulumun ilk ekranında "Add python.exe to PATH" kutusunu işaretleyin.** Sonra terminali kapatıp
yeniden açın.

### 2. bpp'yi kurun (tek komut)

```bash
pip install https://github.com/E7lektronXF/bpp/archive/HEAD.zip
```

Bu komut kodu GitHub'dan indirip kurar; git gerekmez. Windows'ta `pip` bulunamazsa
`py -m pip install ...`, macOS/Linux'ta `python3 -m pip install ...` yazın.

> ⚠️ `pip install bpp` **yazmayın**. PyPI'daki `bpp` adlı paket bu proje değil, başka bir paket.

Kesin token sayımı da görmek isterseniz (isteğe bağlı):

```bash
pip install tiktoken
```

### 3. Çalışıyor mu?

```bash
bpp --version
```

Çıktı `bpp 0.1.0` olmalı. `bpp` komutu bulunamazsa aynı her şeyi `python -m bpp` ile
çalıştırabilirsiniz (örneğin `python -m bpp --version`).

## Kullanım

### Bir dosyayı çevirin

Denemek için hazır bir örnek dosya indirebilirsiniz
([tarayıcıda aç](https://github.com/E7lektronXF/bpp/blob/HEAD/examples/siparisler.json)) ya da
terminalden:

```bash
curl -O https://raw.githubusercontent.com/E7lektronXF/bpp/HEAD/examples/siparisler.json
```

(Windows PowerShell'de `curl.exe -O ...` yazın.)

Terminalde dosyanın bulunduğu klasöre geçin (örneğin `cd Desktop`) ve dosya adını verin:

```console
$ bpp siparisler.json
siparisler.json -> siparisler.bpp (o200k: 149 -> 74 tokens, -50%)
```

Yanına `siparisler.bpp` oluşur. `.json`, `.yaml`, `.csv` ve `.md` dosyalarıyla çalışır.

`siparisler.json`:

```json
{
  "magaza": "Kadıköy Şubesi",
  "siparisler": [
    {"no": 1, "musteri": "Ayşe Yılmaz", "urun": "Kulaklık", "adet": 2, "fiyat": 749.9},
    {"no": 2, "musteri": "Can Demir", "urun": "Klavye", "adet": 1, "fiyat": 1299.0},
    {"no": 3, "musteri": "Şule Öztürk", "urun": "Kulaklık", "adet": 1, "fiyat": 749.9}
  ]
}
```

`siparisler.bpp`:

```
bpp1
magaza Kadıköy Şubesi
siparisler[3]{no urun adet fiyat musteri}
1 Kulaklık 2 749.9 Ayşe Yılmaz
2 Klavye 1 1299.0 Can Demir
3 Kulaklık 1 749.9 Şule Öztürk
```

### LLM'e verin

`siparisler.bpp`'yi bir metin editöründe açın, içeriğini kopyalayıp ChatGPT, Claude vb. sohbet
penceresine yapıştırın ve sorunuzu yazın. Model formatı ilk kez görecekse `--primer` ekleyin;
dosyanın başına formatı anlatan tek bir açıklama satırı (~60 token) eklenir:

```bash
bpp siparisler.json --primer
```

Dosya oluşturmadan doğrudan ekrana yazdırmak için `-o -` kullanın:

```bash
bpp siparisler.json --primer -o -
```

### Geri çevirin

```console
$ bpp siparisler.bpp -o geri.json
```

`geri.json`, orijinal veriyle birebir aynı veriyi içerir. YAML, CSV veya Markdown istiyorsanız
çıktı dosyasının uzantısını değiştirin (`-o geri.yaml`) ya da `--to yaml` yazın. bpp, var olan bir
dosyanın üzerine sormadan yazmaz; üzerine yazmak için `--force` ekleyin.

### Kaç token kazandığınızı görün

```console
$ bpp stats siparisler.json
format           chars  o200k  claude2  vs JSON (o200k)  vs JSON (claude2)
JSON (indent 2)    424    173      186            +0.0%              +0.0%
JSON (minified)    261    109      129           -37.0%             -30.6%
YAML               257    130      130           -24.9%             -30.1%
bpp                159     74       83           -57.2%             -55.4%
bpp + primer       345    134      147           -22.5%             -21.0%
```

`o200k` ve `claude2` sütunları için `pip install tiktoken` gerekir; kurulu değilse kaba bir tahmin
(`chars/4`) gösterilir. Bu kadar küçük bir dosyada primer satırı kazancın çoğunu yer; primer'i
büyük dosyalarda kullanın.

### Python kodundan kullanın

```python
import bpp

metin = bpp.dumps(veri)          # Python nesnesi -> .bpp metni (LLM'e gönderilecek)
veri = bpp.loads(metin)          # .bpp metni -> Python nesnesi

veri = bpp.load("config.yaml")   # .json .yaml .csv .md .bpp dosyası okur
bpp.dump(veri, "config.bpp")     # biçimi uzantıdan seçer
```

### Sık karşılaşılan sorunlar

| sorun | çözüm |
|---|---|
| `bpp: command not found` / `'bpp' is not recognized` | `python -m bpp ...` kullanın ya da terminali yeniden açın. |
| `pip: command not found` | Windows: `py -m pip install ...` · macOS/Linux: `python3 -m pip install ...` |
| `error: externally-managed-environment` (yeni macOS/Linux) | `pipx install https://github.com/E7lektronXF/bpp/archive/HEAD.zip` ya da bir sanal ortam kullanın: `python3 -m venv .venv && . .venv/bin/activate` ve 2. adımı tekrarlayın. |
| `cannot infer format` | Dosya uzantısı `.json .yaml .yml .csv .md .bpp` olmalı. |
| `... exists; use -o ...` | Geri çevirirken orijinal dosyanın üzerine yazılmasın diye durdu. `-o başka_ad.json` verin. |

Kaldırmak için: `pip uninstall bpp`.

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

## Primer satırı

Formatı hiç görmemiş bir model için `--primer` dosyanın başına şu `#` yorum satırını ekler
(decoder yok sayar):

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

## Kurulum seçenekleri (geliştiriciler için)

```bash
git clone https://github.com/E7lektronXF/bpp.git && cd bpp
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
