# .bpp — Format Spesifikasyonu (sürüm `bpp1`)

> Durum: **taslak v1** (Aşama 1). Her karar `bench/experiments.py` ile ölçüldü; ham sonuçlar
> `bench/results/experiments.md`'de. Aşama 4 benchmark'ı sonrasında revize edilecek.

## 0. Amaç ve ilkeler

`.bpp`, JSON veri modelini (nesne, dizi, string, sayı, bool, null) **LLM'in daha az token ile
ve doğru okuyabileceği** biçimde yazar. İnsan okunabilirliği hedef değildir, ama LLM'in
eğitim verisinde bol bulunan kalıplar (YAML/TOML'a benzer girinti, CSV satırları, JSON
string'leri, YAML anchor'ları, TypeScript `?` / `:tip` gösterimi) bilinçli olarak yeniden
kullanılır; icat edilmiş semboller ve binary encoding kullanılmaz.

Verimlilik dört kaynaktan gelir:

1. **Tekrarı kaldırmak** — nesne dizilerinde anahtarlar başlıkta bir kez yazılır.
2. **Gereksiz noktalamayı atmak** — `{}`, `"`, `:` ve `,` sadece gerektiğinde.
3. **Uzun tekrarlanan değerleri sözlüğe almak** — yalnızca net kazanç pozitifse.
4. **Yapıyı açık tutmak** — satır sayıları (`[N]`) ve sütun adları LLM'e çerçeve verir.

Token ölçümü iki vekil ile yapıldı: **o200k** (tiktoken `o200k_base`) ve **claude2**
(Anthropic'in yayımladığı eski Claude tokenizer'ı, `@anthropic-ai/tokenizer`). İkisi de güncel
Claude modelleri için birebir değildir (Anthropic dokümanı tiktoken'ın Claude'u %15–20, Türkçe'de
daha fazla eksik saydığını belirtir); **formatlar arası göreli fark** esas alınır.
`ANTHROPIC_API_KEY` varsa `bpp stats` gerçek `count_tokens` sonucunu da gösterir.

---

## 1. Dosya yapısı

```
bpp1                      ← başlık satırı (zorunlu, sürüm)
# ...                     ← 0+ yorum/primer satırı (opsiyonel)
&0 uzun tekrarlanan değer ← 0+ sözlük tanımı (opsiyonel)
...gövde...               ← kök değer
```

* Kodlama UTF-8, satır sonu `\n` (okurken `\r\n` de kabul edilir).
* Girinti **1 boşluk** = 1 seviye. Tab girinti kullanılmaz.
* `#` ile başlayan satır (girintiden sonra) yorumdur; decoder yok sayar. Anahtar `#` ile
  başlıyorsa tırnaklanır.
* Boş satırlar yok sayılır.

**Ölçüm (E2, iç içe config):** 1 boşluk girinti 2 boşluğa göre o200k'de −%6.4, claude2'de ±0;
tab girinti claude2'de +%12 kötü.

## 2. Skaler değerler

| Tip | Yazım | Not |
|---|---|---|
| null | `null` | |
| bool | `true` / `false` | `T/F` veya `1/0` ölçüldü: kazanç yok (E1) |
| sayı | JSON sayı grameri: `42`, `-3.5`, `1.0`, `1e-7` | `1` (int) ve `1.0` (float) ayrımı korunur |
| özel sayı | `NaN`, `Infinity`, `-Infinity` | yalnızca YAML girdisi için |
| string (çıplak) | `Ahmet Yılmaz` | bağlama göre satır sonuna/ayraca kadar |
| string (tırnaklı) | `"satır1\nsatır2"` | JSON string sözdizimi ve escape'leri |
| referans | `*3` | sözlükteki `&3` tanımının değeri (bkz. §6) |

### 2.1 Tırnaklama kuralı (minimum tırnak)

Bir string **çıplak** yazılır; aşağıdakilerden biri doğruysa JSON string olarak tırnaklanır:

* boş string;
* baş veya sondaki boşluk;
* herhangi bir kontrol karakteri (`\n`, `\r`, `\t`, U+0000–U+001F, U+007F);
* `"`, `[`, `{`, `*`, `&`, `#` ile başlıyor;
* `null`, `true`, `false`, `NaN`, `Infinity`, `-Infinity` ile birebir aynı;
* JSON sayı gramerine uyuyor (`"42"`, `"1.1"`, `"-0"`);
* bağlamın ayracını içeriyor (tabloda `,`, satır tablosunda boşluk, satır içi listede `,` ve `]`);
* liste öğesi (`- `) içinde ve boşluk içeriyor (bkz. §5).

Tırnaklı string'lerde yalnızca JSON'un zorunlu escape'leri kullanılır: `\"`, `\\`, `\n`, `\r`,
`\t`, `\b`, `\f`, `\u00XX` (kontrol karakterleri). **Unicode (ç ğ ı İ ö ş ü, emoji vb.) asla
`\uXXXX` ile escape edilmez**, ham UTF-8 yazılır. Çıplak string'lerde ters bölü `\` harfiyen
kendisidir (escape yoktur).

**Ölçüm (E7, Türkçe metin):** `\u` escape'li JSON ham UTF-8'e göre o200k'de +%161, claude2'de
+%124 token. Her şeyi tırnaklamak tabloda +%1.3 / +%2.4 (E1).

## 3. Nesneler: `key value`

```
service
 name order-api
 version 2.4.1
 replicas 3
 debug false
 tls {}
 tags []
```

* `anahtar␠değer` — anahtar ile skaler arasında **tek boşluk**.
* Tek başına `anahtar` satırı iç içe nesne açar; çocukları bir seviye derindedir. Çocuksuz
  çıplak anahtar geçersizdir: boş nesne `{}`, boş dizi `[]` yazılır.
* Anahtar çıplak yazılır eğer: boş değilse, boşluk/kontrol karakteri, `"[]{}=,:?>` içermiyorsa
  ve `-#&*` ile başlamıyorsa. Aksi halde JSON string olarak tırnaklanır (`"first name" Ali`).
  Unicode harfli anahtarlar (`şehir`) çıplak yazılır.
* Anahtar sırası korunur.

**Ölçüm (E2, E9):** `key value`, `key:value`'ya göre config'te −%2.9/−%7.1, karma belgede
−%5.8/−%5.3, planda −%5.6/−%7.9 (o200k/claude2). Neden: boşluk bir sonraki kelimenin token'ına
kaynaşır, `:` ise çoğu zaman ayrı token'dır. `key=value` `:` ile aynıdır. Noktalı yol anahtarları
(`db.host`) claude2'de +%22 kötü → kullanılmaz.

## 4. Diziler

### 4.1 Satır içi liste (yalnızca skalerler)

```
beta_regions [TR,DE,NL]
sinks [stdout,file]
ports [80,443]
codes ["01","02"]
```

Öğeler `,` ile ayrılır, boşluk yok. `,` veya `]` içeren ya da §2.1'e takılan öğe tırnaklanır.
**Ölçüm (E9):** `[a,b]`, TOON'un `k[2]: a,b` biçiminden −%1.5/−%0.9 ucuz.

### 4.2 Tablo: tekdüze nesne dizileri — `key[N]{a,b,c}`

Tüm öğeleri **aynı anahtarları aynı sırada** taşıyan ve değerleri skaler olan nesne dizileri:

```
employees[3]{id,name,city,salary,active,manager_id}
1,Ahmet Yılmaz,İstanbul,48500,true,null
2,"Kaya, Ayşe",Ankara,61000,false,1
3,Can Demir,İzmir,39000,true,1
```

* `[N]` satır sayısıdır; tam olarak N satır, **başlıkla aynı girintide** gelir (girinti gerekmez,
  sayı bloğu sınırlar).
* Hücreler CSV benzeri `,` ile ayrılır; `,` içeren string tırnaklanır.
* **Tipli sütun** `ad:str`: sütundaki çıplak hücreler her zaman string'tir (sayıya/bool'a
  çevrilmez). `null`, tırnaklı ve `*n` hücreler yine özel anlam taşır. Böylece `"1.1"`, `"007"`
  gibi sayıya benzeyen kimlik/kod değerleri tırnak maliyeti ödemeden yazılır. Encoder, en az
  bir hücre aksi halde tırnaklanacaksa ve sütundaki tüm null-olmayan değerler string ise
  `:str` ekler.

**Ölçüm (E1, 60×10 tablo):** JSON'a göre −%60.8 / −%55.8; minified JSON'a göre −%39 / −%37;
TOON ile başa baş (o200k'de −%4.7, claude2'de +%0.6), CSV ile başa baş (ama CSV tip
taşımaz). Varyantlar arasındaki farklar küçük: tab ayraç o200k'de −%0.8, claude2'de 0;
`|` +%4; satır girintisi +%2.8; `[N]` kaldırmak −%0.1 (anlamaya yardımı için **korunur**);
null'u boş hücre yazmak −%0.1/−%0.2 (netlik için **`null` korunur**).

### 4.3 Satır tablosu (outline): metin ağırlıklı / seyrek / özyinelemeli diziler —
`key[N]{a b? c}>child`

Başlıktaki sütun adları **boşlukla** ayrılmışsa satırlar boşlukla ayrılır. Planlar, görev
listeleri ve ağaçlar için tasarlandı:

```
steps[2]{id:str status priority deps:str owner? note? title}>steps
1 done P1 [] owner=Ayşe Gereksinim analizi
 1.1 done P1 [] Paydaş görüşmeleri
 1.2 done P0 [1.1] Regülasyon incelemesi (BDDK, PCI-DSS)
2 todo P0 [1] owner="Harici firma" note="Gece 02:00'de çalışır" Güvenlik testi
```

* Zorunlu sütunlar pozisyoneldir (tek boşlukla ayrılır). **Son sütun satırın geri kalanıdır**
  (boşluk içerebilir, tırnak gerekmez).
* `ad?` ile işaretli sütun opsiyoneldir: satırda yoksa o nesnede anahtar yoktur; varsa
  pozisyonel sütunlardan sonra, son sütundan önce `ad=değer` olarak yazılır. (TypeScript'teki
  `ad?:` gösterimi.) `ad?:str` birlikte kullanılabilir.
* Pozisyonel ve `ad=` değerleri boşluk içeriyorsa tırnaklanır. Hücreler skaler veya satır içi
  liste (`[a,b]`, `{}`) olabilir.
* `>child`: özyineleme anahtarı. Bir satırın hemen altındaki **bir boşluk daha girintili**
  satırlar o öğenin `child` dizisidir. Çocuk dizisi boşsa `child=[]` yazılır; anahtar yoksa hiçbir
  şey yazılmaz. `[N]` yalnızca en üst seviyedeki satırları sayar.
* Son sütunun değeri `ad=` kalıbıyla başlıyorsa tırnaklanır.
* Decode edilen nesnede anahtar sırası başlık sırasıdır (encoder başlığı ilk görülen anahtar
  sırasıyla kurar, yalnızca "satır sonu" sütununu sona taşır).

**Ölçüm (E4, E8, E8b; 6 adım + 21 alt adım):**

| gösterim | o200k | claude2 |
|---|---:|---:|
| JSON pretty | 1609 | 1718 |
| JSON minified | 990 | 1078 |
| YAML | 1212 | 1248 |
| Markdown checklist | 828 | 894 |
| TOON | 1228 | 1257 |
| virgüllü ağaç-tablo | 652–664 | 797–820 |
| **satır tablosu (`k=v` opsiyonel, başlık son)** | **606** | **696** |
| sembollü outline (`<dep @owner #note`) | 576 | 662 |

Sembollü outline %5 daha ucuzdur ama `< @ #` icat edilmiş anlamlar taşır (ilke #1'e aykırı,
anlama riski); kendini açıklayan `deps=`/`owner=` tercih edildi.

### 4.4 Genel liste: `key[N]` + `- ` öğeleri

Tablo/satır tablosu olamayan (karışık tipli, iç içe nesneli) diziler:

```
orders[2]
- order_id ORD-1
 customer
  name Ali
 items[1]{sku,qty}
 SKU-1,2
- order_id ORD-2
 status cancelled
mixed[3]
- 1
- "iki kelime"
- [a,b]
```

* Öğeler başlıkla aynı girintide `- ` ile başlar; N öğe vardır.
* Nesne öğesi: ilk girdi `- ` ile aynı satırda, diğer girdileri **bir seviye derinde**.
  Boş nesne öğesi `- {}`.
* Skaler öğe: `- değer`. Boşluk içeren string öğeler tırnaklanır (aksi halde `key value` girdisi
  olarak okunurdu).
* İç içe dizi öğesi: `- [a,b]` veya anahtarsız başlık `- [N]{a,b}` / `- [N]`.

### 4.5 Kök değer

Kök nesne ise girdileri 0 girintide yazılır. Kök dizi anahtarsız başlıkla yazılır
(`[60]{id,name}`, `[3]`, `[1,2,3]`). Kök skaler tek satırdır; kök string her zaman tırnaklanır.

## 5. Ayrıştırma belirsizlikleri ve çözümleri

| Durum | Çözüm |
|---|---|
| `- hello world` string mi, `{hello: "world"}` mu? | Nesne. String öğe boşluk içeriyorsa tırnaklanır. |
| `- hello` (boşluksuz, çocuksuz) | String `"hello"`. |
| `key` tek başına ve çocuksuz | Geçersiz; boş nesne `key {}`. |
| `42` string mi sayı mı? | Sayı; string `"42"` ya da `:str` sütun. |
| Değer `*` veya `&` ile başlıyor | Tırnaklanır; çıplak `*n` referanstır. |

## 6. Sözlük / referanslar: `&n` ve `*n`

YAML anchor/alias gösterimi (LLM'in tanıdığı kalıp):

```
bpp1
&0 Connection to upstream payment provider timed out after 30000ms
&1 payments-gateway-eu-west-1
logs[80]{ts,level,service,message,latency_ms}
2026-09-24T10:00:00Z,ERROR,*1,*0,30000
```

* Tanımlar başlık/yorumlardan sonra, gövdeden önce gelir: `&n değer` (değer §2 skaleri).
* `*n` herhangi bir **string değer** konumunda kullanılabilir (girdi değeri, hücre, liste öğesi,
  `ad=` değeri). Anahtarlarda kullanılmaz.
* **Kullanım kuralı:** encoder bir string'i ancak
  `n·t(değer) − (t(tanım satırı) + n·t(*i)) > 0` ise sözlüğe alır (t = deterministik token
  tahmincisi; ortamdan bağımsız aynı çıktı için tiktoken kullanılmaz). Aday: ≥2 kez geçen ve
  ≥12 karakterlik string'ler; kazanç sırasına göre numaralandırılır.

**Ölçüm (E3, 80 log satırı):** mesajlar+servisler sözlükte: −%39.0 / −%40.1. Kısa değerler
(departman/şehir, 1–2 token) için kazanç yok (−%0.1 / −%1.7) → eşik kuralı bunu eler.
TOON'da sözlük yoktur; bu veri setinde TOON bizim sözlüksüz halimizden bile +%5 pahalı.

## 7. Planlar

Planlar için önerilen şema (Markdown çeviricisi bunu üretir, JSON/YAML planlar da bu şemaya
uyarsa aynı şekilde kodlanır):

```
title <plan başlığı>
goal <opsiyonel açıklama>
steps[N]{id:str status priority deps:str owner? due? note? title}>steps
```

* `id`: hiyerarşik kimlik (`1`, `1.2`, `1.2.3`); `:str` sayesinde tırnaksız.
* `status`: `todo | doing | done | blocked | cancelled`.
* `priority`: `P0 | P1 | P2 | P3`.
* `deps`: bağımlı olunan adım kimlikleri, satır içi liste (`[1.1,2]`).
* Alt adımlar `>steps` ile girintili satırlardır.

Markdown girişinde: başlıklar (`#`, `##`, …) ve iç içe listeler ağaca çevrilir; `- [ ]` →
`status todo`, `- [x]` → `status done`. (Ayrıntı Aşama 2'de README'de.)

## 8. Primer (opsiyonel)

Formatı hiç görmemiş bir LLM için dosyanın başına `#` yorum satırı olarak eklenebilir
(`bpp encode --primer`). Decoder yok sayar.

**1 satır (o200k 38 / claude2 39 token):**
```
# bpp1: JSON as indented 'key value' lines; k[N]{a,b} = N CSV rows; "..." = JSON string; *n = &n.
```

**3 satır (96 / 103 token):**
```
# bpp1 = JSON data. Lines are 'key value'; a bare 'key' opens a nested object (1-space indent).
# k[N]{a,b}: N rows of comma values for a,b. k[N]{a b? c}>kids: space rows, last col = rest of line,
# optional col as a=v, indented rows are kids. '- ' = list item. "..." = JSON string. *n = &n value.
```

Primer sabit maliyettir: 60 satırlık tabloda (~2200 token) %2, küçük bir config'te (~330 token)
%11–29. Varsayılan **kapalı**; Aşama 4'te anlama testinin primer'li/primer'siz karşılaştırması
yapılacak.

## 9. Kayıpsızlık tanımı

`decode(encode(x)) == x`, JSON veri modeli üzerinde:

* tipler korunur (int/float, string/sayı, null);
* nesne anahtar sırası korunur (istisna: satır tablolarında §4.3'teki kanonik sıra);
* YAML: yorumlar, anchor'lar, etiketler veri modeline ait değildir, korunmaz. Tarih/saat
  değerleri string olarak okunur (otomatik `date` dönüşümü kapatılır). String olmayan YAML
  anahtarları string'e çevrilir.
* CSV: hücre metni birebir korunur. Encoder bir hücreyi sayı/bool/null'a yalnızca metne geri
  yazıldığında aynı metni verecekse çevirir (`007` string kalır, `1.50` string kalır).

## 10. Gramer (özet, EBNF benzeri)

```
file      = "bpp1" NL {comment} {def} body
comment   = INDENT "#" {any} NL
def       = "&" digits SP scalar NL
body      = object(0) | rootarray | scalar NL
object(d) = {entry(d)}
entry(d)  = I(d) key SP inline NL                          (* skaler / [..] / {} / [] *)
          | I(d) key NL object(d+1)                        (* iç içe nesne *)
          | I(d) key "[" N "]" "{" cols(",") "}" NL N×row(d, ",")
          | I(d) key "[" N "]" "{" cols(" ") "}" [">" key] NL rowtree(d)
          | I(d) key "[" N "]" NL N×item(d)
item(d)   = I(d) "- " (inline | entry-tail) NL [object(d+1)]
col       = key ["?"] [":str"]                             (* ? yalnızca boşluklu başlıkta *)
inline    = scalar | "[" [scalar {"," scalar}] "]" | "{}"
scalar    = "null" | "true" | "false" | number | jsonstring | "*" digits | barestring
I(d)      = d × " "
```
