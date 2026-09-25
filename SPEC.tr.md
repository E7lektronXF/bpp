# .bpp — Format Spesifikasyonu (sürüm `bpp4`)

> Durum: **v4** (`bpp4`; decoder `bpp1`, `bpp2` ve `bpp3` dosyalarını da okur, bkz. §11). Her karar `bench/experiments.py` ile ölçüldü; ham sonuçlar
> `bench/results/experiments.md`'de. Benchmark sonuçları ve revizyon önerileri (R1–R5):
> [BENCHMARK.tr.md](BENCHMARK.tr.md) §5.
> English: [SPEC.md](SPEC.md)

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
bpp4                      ← başlık satırı (zorunlu, sürüm)
# ...                     ← 0+ yorum/primer satırı (opsiyonel)
&0 uzun tekrarlanan değer ← 0+ sözlük tanımı (opsiyonel)
...gövde...               ← kök değer
```

* Kodlama UTF-8, satır sonu `\n` (okurken `\r\n` de kabul edilir).
* Girinti **1 boşluk** = 1 seviye. Tab girinti kullanılmaz.
* `#` ile başlayan satır (girintiden sonra) yorumdur; decoder yok sayar. Anahtar `#` ile
  başlıyorsa tırnaklanır.
* Boş satırlar yok sayılır.
* Bu iki kural `|N` blok string'lerinin (§2.2) içinde geçerli değildir: blok satırları olduğu gibi
  alınır.
* Başlığı `bpp4 md` olan dosya, bir Markdown belgesini kaynak metin olarak taşır (§7.2).

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
| string (blok) | `\|2` + 2 ham satır | çok satırlı metin, bpp4 (bkz. §2.2) |
| referans | `*3` | sözlükteki `&3` tanımının değeri (bkz. §6) |

### 2.1 Tırnaklama kuralı (minimum tırnak)

Bir string **çıplak** yazılır; aşağıdakilerden biri doğruysa JSON string olarak tırnaklanır:

* boş string;
* baş veya sondaki boşluk;
* herhangi bir kontrol karakteri (`\n`, `\r`, `\t`, U+0000–U+001F, U+007F);
* `"`, `[`, `{`, `&`, `#` ile başlıyor;
* `*` ya da `|` ve ardından yalnızca rakamlardan oluşuyor (`*12`, `|3`): referans ya da blok
  işareti;
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

**Ölçüm (E13, bpp4):** bpp1–bpp3 `*` ile başlayan her string'i tırnaklıyordu; bu, Markdown'daki
kalın yazıya (`**Not:** …`) da denk geliyordu. Yalnızca `*` + rakamları tırnaklamak §7.1'deki beş
Markdown belgesinde 16 / 8 token kazandırıyor (o200k / claude2).

### 2.2 Blok string'ler: `|N` (bpp4)

Bir string değerin yerine yazılan `|N`: **bu satırdan sonraki N ham satır string'in kendisidir.**

```
note |3
Birinci paragraf, `kod` ve "tırnak" içerir.

İkinci paragraf: \ ve \n olduğu gibi kalır.
```

* N satır `\n` ile birleştirilir. İçlerinde hiçbir şey escape edilmez, tırnaklanmaz ya da
  girintilenmez; decoder bu satırları bpp olarak okumaz: blok satırı boş olabilir, boşlukla, `#`,
  `|`, `- ` ile başlayabilir ya da `bpp3` başlığına benzeyebilir. Bloğu, tablolardaki `[N]` gibi,
  satır sayısı sınırlar.
* `|N` her string değerin yerine geçebilir: `key |N`, `- |N` liste öğesi, `&0 |N` sözlük tanımı ve
  tüm tablo hücreleri (virgüllü hücreler, pozisyonel hücreler, anahtarlı `note=|N` ve son sütun).
  Satır içi listede (`[...]`) blok değildir: `[|3]` `"|3"` string'idir.
* Bir satırda birden fazla blok varsa soldan sağa sırayla gelir: `|2 |1 Başlık` satırından sonra
  önce birinci bloğun 2 satırı, sonra ikincinin 1 satırı gelir.
* Satır tablosunda blok satırları kendi satırının hemen ardından, girintili çocuk satırlardan önce
  gelir.
* `\n` ile biten string'in son satırı boştur. `|3` string'inin kendisi tırnaklanır (§2.1); blok
  işaretine benzeyen anahtarlar da öyle.
* Encoder bloğu yalnızca `\n` içeren ve başka kontrol karakteri içermeyen (`\r` yok, `\t` yok)
  string'ler için ve tahmini kazanç negatif değilse kullanır (eşitlikte blok seçilir; okuması da
  daha kolaydır):

  `kazanç = t(" " + "json string") + m − t(" |N") − t(string + "\n")`

  t §6'daki tahminci, m ise ASCII noktalama işaretinden ya da başka bir satır sonundan sonra
  gelen satır sonlarının sayısıdır: ham satır sonu önündeki token'a kaynaşır (`):\n\n` tek
  token), escape edilmiş `\n` kaynaşmaz ve tahminci tek başına bunu kaçırır.

**Ölçüm (E10, §7.1'deki beş Markdown belgesi, dosyanın tamamı):**

| çok satırlı string'ler | o200k | claude2 |
|---|---:|---:|
| hepsi tırnaklı (bpp3) | 15201 | 15749 |
| hepsi blok | 14824 | 15508 |
| **kazanç ≥ 0 ise blok** | **14824** | **15513** |

Bu belgelerde her çok satırlı string'i blok yazmak kuraldan en fazla 5 token farklı; kural ise
`"a\nb"` gibi kısa string'leri, bloğun daha pahalı olduğu yerde, tırnaklı bırakır.

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
* Anahtar çıplak yazılır eğer: boş değilse, boşluk/kontrol karakteri, `"[]{}=,:?>` içermiyorsa,
  `-#&*` ile başlamıyorsa ve blok işareti (`|3`) değilse. Aksi halde JSON string olarak tırnaklanır (`"first name" Ali`).
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

### 4.2 Virgüllü tablo: tekdüze nesne dizileri — `key[N]{a,b,c}`

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

> **Aşama 2 revizyonu:** gerçek encoder ile yapılan ölçümde aynı tablo §4.3'teki **boşluklu
> satır tablosu** olarak yazıldığında virgüllü tablodan belirgin ucuz çıktı: 60×10 çalışan
> tablosunda 2171→1910 (o200k, −%12) ve 2511→1961 (claude2, −%22). Neden: `,` çoğu zaman ayrı
> token'dır ve arkasındaki kelime/sayıyla kaynaşmaz; boşluk ise bir sonraki token'ın içine girer
> (§3'teki `key value` bulgusunun aynısı). Bu yüzden encoder her dizi için adayları (virgüllü
> tablo, satır tablosu, `- ` listesi) üretir ve deterministik token tahmincisine göre en ucuzunu
> seçer; eşitlikte sırayı koruyan aday kazanır. Virgüllü tablo; değerlerin çoğunda boşluk olduğu
> durumlar için geçerli kalır.

### 4.3 Satır tablosu: boşlukla ayrılmış satırlar, seyrek ve özyinelemeli diziler —
`key[N]{a b? c?= d}>child`

Başlıktaki sütun adları **boşlukla** ayrılmışsa satırlar boşlukla ayrılır. Önce planlar ve
ağaçlar için tasarlandı; ölçümler düz tablolarda da en ucuz form olduğunu gösterdi (§4.2 notu):

```
steps[2]{id:str status? priority deps:str owner?= note?= title}>
1 done P1 [] owner=Ayşe Gereksinim analizi
 1.1 done P1 [] Paydaş görüşmeleri
 1.2 - P0 [1.1] Regülasyon incelemesi (BDDK, PCI-DSS)
2 todo P0 [1] owner="Harici firma" note="Gece 02:00'de çalışır" Güvenlik testi
```

* Zorunlu sütunlar pozisyoneldir (tek boşlukla ayrılır). **Son sütun satırın geri kalanıdır**
  (boşluk içerebilir, tırnak gerekmez).
* Opsiyonel sütunlar (TypeScript'teki `ad?:` gösterimi) iki biçimde yazılır. Satırda
  olmayan bir opsiyonel sütun, o nesnede anahtarın **olmadığı** anlamına gelir (`null` değil):
  * `ad?` — **pozisyonel opsiyonel**: yerinde değer ya da yoksa tek başına `-` yazılır. Değeri
    string `"-"` olan hücre tırnaklanır.
  * `ad?=` — **anahtarlı opsiyonel**: yalnızca varsa, pozisyonel sütunlardan sonra ve son
    sütundan önce `ad=değer` olarak yazılır.

  Encoder her opsiyonel sütun için `eksik·t(" -")` ile `mevcut·t(" ad=")` maliyetini
  karşılaştırır: çoğu satırda bulunan sütun (ör. plan `status`'u) pozisyonel, seyrek sütun (ör.
  `note`, `owner`) anahtarlı olur. `:str` her iki biçimle birlikte kullanılabilir
  (`ad?:str`, `ad?=:str`).
* Pozisyonel ve `ad=` değerleri boşluk içeriyorsa tırnaklanır. Hücreler skaler veya satır içi
  liste (`[a,b]`, `{}`) olabilir.
* `>child`: özyineleme anahtarı. Bir satırın hemen altındaki **bir boşluk daha girintili**
  satırlar o öğenin `child` dizisidir. Çocuk dizisi boşsa `child=[]` yazılır; anahtar yoksa hiçbir
  şey yazılmaz. `[N]` yalnızca en üst seviyedeki satırları sayar.
* Tek başına `>` (bpp4), çocuk anahtarının tablonun kendi anahtarı olduğunu söyler:
  `steps[2]{...}>` = `steps[2]{...}>steps`. Alt şemada (`orders[2]{...}>items{...}>`) o alt anahtarı
  tekrarlar. Anahtarsız tablonun (`[N]{...}`) tekrarlanacak anahtarı yoktur; orada ad hep yazılır.
  **Ölçüm (E12):** §7.1'deki beş Markdown belgesinde −16 / −8 token, `plan.json`'da −2 / −1
  (636 → 634, 728 → 727).
* Son sütunun değeri `ad=` kalıbıyla başlıyorsa tırnaklanır.
* Başlık sırası = satırdaki değer sırası = decode edilen nesnedeki anahtar sırası. (LLM'in
  sütunları doğru eşlemesi için başlık ile satır sırası asla ayrışmaz.)
* Encoder iki varyant dener: (a) sırayı koruyan — son sütun orijinal son anahtar; (b) en çok
  boşluk içeren metin sütununu (ör. `title`, `name`) sona taşıyan — bu durumda o sütundaki
  değerler tırnaksız yazılır ama nesnenin anahtar sırası değişir. (b) yalnızca daha ucuzsa ve
  `keep_order` kapalıysa seçilir. **CSV girdisinde `keep_order` her zaman açıktır** (sütun sırası
  veridir).

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

### 4.3.1 İç içe nesneler ve alt tablolar (bpp3)

Gerçek API yanıtları iç içedir: bir siparişin `customer` nesnesi ve `items` listesi vardır.
bpp1/bpp2 bu dizileri tabloya koyamıyor, `- ` öğelerine (§4.4) düşüyordu. bpp3 satır tablosunu iki
yönde genişletir:

```
orders[2]{id customer.city status customer.name}>items{sku qty name}
A-1 London paid Ada Lovelace
 K-1 2 Blue pen
 K-2 1 Red pen
A-2 Wilmslow sent Alan Turing
 K-3 5 Notebook
```

* **Sütun yolları.** `a.b.c` sütunu, satırdaki `a` nesnesinin içindeki `b` nesnesinin `c`
  anahtarıdır. İç içe nesneler (her derinlikte) bu sütunlara açılır. Kendisi `.` içeren bir anahtar
  başlıkta tırnaklanır (`"a.b"`). Yol sütunları diğer sütunlar gibi zorunlu, opsiyonel (`?`, `?=`)
  ve `:str` olabilir; anahtarlı opsiyonel yol `a.b=değer` diye yazılır. Decode sırasında bir nesne,
  sütunlarından en az biri satırda varsa oluşturulur; böylece var olan ve olmayan nesneler birebir
  geri gelir. Düzleştirme yalnızca tüm satırlar uyuşuyorsa kullanılır: `k` bir satırda nesne,
  başka satırda düz değerse dizi satır tablosu olarak yazılmaz.
* **Alt tablolar.** Tek başına `>child`, alt satırların aynı sütunları kullandığı anlamına gelir
  (planlardaki gibi ağaç). `>child{...}` alt satırlara kendi sütunlarını verir. Alt satırlar üst
  satırın altında bir boşluk girintiyle yazılır; alt tabloların da kendi alt tabloları olabilir
  (`>parts{...}>subs{...}`). Boş alt liste eskisi gibi `child=[]`.

Kullanılabilen ilk çocuk anahtarı için encoder hem ağacı (aynı sütunlar) hem alt tabloyu (üst
seviyeye kendi sütunları) kurar; çocuk anahtarı yoksa düz satır tablosunu. Ardından olağan maliyet
karşılaştırması (§4.2) bunlar, virgüllü tablo ve `- ` öğeleri arasında seçim yapar. Anahtar sırası
başlık sırasıyla yeniden kurulur; `keep_order` açıkken encoder yalnızca yeniden kurulan nesnelerin
anahtar sırası orijinalle birebir aynı olan düzeni kullanır.

bpp3 kayıpsız olduğu sürece hep ağacı seçiyordu. bpp4'te alt tablo da yarışır; bu Markdown
ağaçlarında önemlidir: başlıklar (üst seviye) çoğu zaman uzun bir not taşır, liste maddeleri
nadiren. Alt tabloda başlığın notu pozisyonel olabilir (`|7 Başlık`, yoksa `-`), alt seviyelerde
anahtarlı kalır (`note=|7`). **Ölçüm (E14, §7.1'deki beş Markdown belgesi):** −14 / −12 token.

**Ölçüm (`examples/orders.json`, her biri müşteri nesnesi ve 1–3 kalem içeren 20 sipariş):**

| | o200k | claude2 |
|---|---:|---:|
| bpp2 (`- ` öğeleri) | 1762 | 1839 |
| **bpp3 (yollar + alt tablo)** | **1151 (−%34.7)** | **1178 (−%35.9)** |
| minified JSON | 2231 | 2455 |
| TOON | 2276 | 2342 |

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
(`[60]{id,name}`, `[3]`, `[1,2,3]`). Kök skaler tek satırdır; kök string, blok olarak yazılmadıkça (`|N` ve satırları, §2.2) her
zaman tırnaklanır.

## 5. Ayrıştırma belirsizlikleri ve çözümleri

| Durum | Çözüm |
|---|---|
| `- hello world` string mi, `{hello: "world"}` mu? | Nesne. String öğe boşluk içeriyorsa tırnaklanır. |
| `- hello` (boşluksuz, çocuksuz) | String `"hello"`. |
| `key` tek başına ve çocuksuz | Geçersiz; boş nesne `key {}`. |
| `42` string mi sayı mı? | Sayı; string `"42"` ya da `:str` sütun. |
| Değer `*` veya `&` ile başlıyor | `&` ile başlayan tırnaklanır. `*` + rakamlar referanstır (string `"*3"` tırnaklanır); `*not*`, `**kalın**` string'dir. |
| `\|3` string mi, blok mu? | 3 satırlık blok (bpp4). String `"\|3"` diye yazılır; `[...]` içinde string'dir. |
| `- \|2` ve ardından 2 satır | Blok string öğesi. `\|2` anahtarı tırnaklanır, dolayısıyla nesne olamaz. |

## 6. Sözlük / referanslar: `&n` ve `*n`

YAML anchor/alias gösterimi (LLM'in tanıdığı kalıp):

```
bpp4
&0 Connection to upstream payment provider timed out after 30000ms
&1 payments-gateway-eu-west-1
logs[80]{ts,level,service,message,latency_ms}
2026-09-24T10:00:00Z,ERROR,*1,*0,30000
```

* Tanımlar başlık/yorumlardan sonra, gövdeden önce gelir: `&n değer` (değer §2 skaleri; çok
  satırlı değer blok olabilir: `&0 |3`).
* `*n` herhangi bir **string değer** konumunda kullanılabilir (girdi değeri, hücre, liste öğesi,
  `ad=` değeri). Anahtarlarda kullanılmaz.
* **Kullanım kuralı:** encoder bir string'i ancak
  `n·t(değer) − (t(tanım satırı) + n·t(*i)) > 0` ise sözlüğe alır (t = deterministik token
  tahmincisi; ortamdan bağımsız aynı çıktı için tiktoken kullanılmaz). Aday: ≥2 kez geçen ve
  ≥8 karakterlik string'ler; kazanç sırasına göre numaralandırılır. bpp4'te tahminci ardışık satır
  sonlarını (boş satır) tek token sayar, `?=`, `=|` ve `"=` çiftlerini ise iki token; iki tokenizer
  da böyle yapıyor (E14: Markdown belgelerinde −3 / −1 token; hiçbir JSON, YAML, CSV örneği
  değişmedi).

**Ölçüm (E3, 80 log satırı):** mesajlar+servisler sözlükte: −%39.0 / −%40.1. Kısa değerler
(departman/şehir, 1–2 token) için kazanç yok (−%0.1 / −%1.7) → eşik kuralı bunu eler.
TOON'da sözlük yoktur; bu veri setinde TOON bizim sözlüksüz halimizden bile +%5 pahalı.

## 7. Planlar

Planlar için önerilen şema (Markdown çeviricisi bunu üretir, JSON/YAML planlar da bu şemaya
uyarsa aynı şekilde kodlanır):

```
title <plan başlığı>
goal <opsiyonel açıklama>
steps[N]{id:str status priority deps:str owner?= due?= note?= title}>
```

* `id`: hiyerarşik kimlik (`1`, `1.2`, `1.2.3`); `:str` sayesinde tırnaksız.
* `status`: `todo | doing | done | blocked | cancelled`.
* `priority`: `P0 | P1 | P2 | P3`.
* `deps`: bağımlı olunan adım kimlikleri, satır içi liste (`[1.1,2]`).
* Alt adımlar `>` (`>steps`) ile girintili satırlardır.

Markdown girişinde: başlıklar (`#`, `##`, …) ve iç içe listeler ağaca çevrilir; `- [ ]` →
`status todo`, `- [x]` → `status done`, `[/]` → `doing`, `[-]` → `cancelled`. Checkbox'sız
başlık ve maddelerde `status` yoktur; satırda `-` görünür. Burada başlıkların kendi sütunları var
(alt tablo, §4.3.1):

```
steps[5]{title}>{status? note?= title}>
Keşif ve envanter
 done Mevcut iş akışlarının envanteri Toplam 312 Airflow DAG'i, 48 Spark işi ve 17 Hive veritabanı tespit edildi.
 done Veri sahipleriyle görüşmeler
  done Pazarlama analitiği
```

### 7.1 Yumuşak satır sonları (bpp4)

Markdown'da yapı korunur, biçim korunmaz (§9); yumuşak satır sonu da biçimdir: CommonMark onu
boşluk olarak gösterir. bpp4 şunları bir boşlukla birleştirir:

* bir liste maddesinin ilk paragrafının kaydırılmış satırlarını, maddenin altına girintili ya da
  "lazy" (girintisiz) olsun, `title`'a. bpp4'ten önce bunlar `note`'a gidiyordu; başlık son sütun
  olduğu için cümlenin ikinci yarısı ilk yarısından önce yazılıyordu
  (`note=virtualenv. Check https://… in a clean`);
* `note` içindeki düz paragrafların kaydırılmış satırlarını.

Hard break (satır sonunda iki boşluk ya da `\`) veya boş satırın ötesine birleştirme yapılmaz;
kendi bloğunu başlatan ya da başlatabilecek satırlar da hiç birleştirilmez: code fence
(```` ``` ````, `~~~`), `$$` matematik, blockquote (`>`), HTML (`<`, bitiş işaretine ya da boş satıra
kadar), tablo satırları (`|` içeren her satır), liste işaretleri, `#`, yatay çizgi ve setext alt
çizgileri (`---`, `===`, `***`), bağlantı tanımları (`[x]: …`) ve YAML front matter. Hard break'ten
sonraki satır maddenin `note`'unu başlatır; yani maddesinin altına not yazmak isteyen bir checklist
hard break ya da boş satır kullanır, düz girintili satır ise (işlenmiş Markdown'da olduğu gibi)
başlığı sürdürür. `tree_to_md` maddenin başlığı ile notu arasına boş satır koyar, böylece
md → tree → md → tree sabit kalır. `md_to_tree(text, join=False)` her satır sonunu korur (bpp3
davranışı).

**Ölçüm (E11):** bpp4 Markdown deneylerinin derlemi `bench/corpus/`: bu deponun v0.3.0'daki
README, SPEC, BENCHMARK ve RELEASING dosyaları ile `examples/project_plan.md`.

| satır sonları | o200k | claude2 |
|---|---:|---:|
| hepsi korunur (bpp3) | 15059 | 15737 |
| madde başlıkları birleşir | 14915 | 15627 |
| **madde başlıkları ve not paragrafları birleşir** | **14824** | **15513** |

### 7.2 Kaynağıyla saklanan Markdown: `bpp4 md` (bpp4)

Bir Markdown belgesi kendi kaynak metni olarak da yazılabilir:

```
bpp4 md
# Releasing to PyPI

The package is published as ...
```

* `bpp4 md` başlık satırı (öncesinde isteğe bağlı boş ya da `#` satırları olabilir) şu anlama
  gelir: o satırın `\n`'inden sonraki her şey, dosyanın sonuna kadar, bayt bayt Markdown
  kaynağıdır. Başlıktan sonra sayı, escape ya da bpp sözdizimi yoktur.
* Decode sonucu `md_to_tree(kaynak)`'tır (`bpp decode`, `--to json`, `bpp.decode`); `--to md` ise
  kaynağı değiştirmeden geri verir (`bpp.md_source`). YAML ve CSV çıktısı ağacı kullanır.
* `encode_md` (`bpp encode x.md`, `bpp x.md` ve `bpp stats x.md` bunu kullanır) hem ağaç kodlamasını
  hem bu biçimi kurar ve tahmincinin daha kısa saydığını seçer; eşitlikte ağaç kalır. Bu biçim
  kaynaktan tam olarak başlık satırı kadar uzundur (o200k ve claude2'de 5 token); yani tahminciye
  göre bir Markdown dosyası bundan fazla büyümez. Beş belgede gerçek tokenizer'lar her seçimle
  aynı fikirde (E15).
* Bu biçime primer eklenmez: içinde bpp sözdizimi yoktur.

**Ölçüm (E15):**

| | o200k | claude2 |
|---|---:|---:|
| Markdown kaynağı | 15072 | 15844 |
| `bpp4 md` + kaynak | 15097 | 15869 |
| **bpp4, `encode_md`** | **14824** | **15513** |
| bpp4 + primer, `encode_md` | 15010 | 15757 |

Belge başına (o200k / claude2): README 3703 / 3894, Markdown'da 3722 / 3938; SPEC 6144 / 6330'a
karşı 6269 / 6483; BENCHMARK 3724 / 3756'ya karşı 3747 / 3802; RELEASING 495 / 537'ye karşı
497 / 543; proje planı 758 / 996'ya karşı 837 / 1078. Primer'le README, BENCHMARK ve RELEASING
kaynak olarak saklanır.

## 8. Primer (opsiyonel)

Formatı hiç görmemiş bir LLM için dosyanın başına `#` yorum satırı olarak eklenebilir
(`bpp encode --primer`). Decoder yok sayar.

**1 satır.** bpp4'ten beri primer yalnızca çıktının kullandığı sözdizimini anlatır: satır
tabloları (`b.c` yol örneği yalnızca yol sütunu varsa), virgüllü tablolar, `x?`, `x?=`, `>k` ya da
tek başına `>`, `"..."`, `|N` ve `*n`. Tüm özelliklerle (108 / 114 token):

```
# bpp4: JSON as 'key value' lines, 1-space indent nests. k[N]{a b.c}: N rows, values in column order (b.c = key c of b), last one = rest of line; k[N]{a,b}: N comma rows; x? optional (- = absent); x?= as x=v; >k: indented rows are k (bare >: same key). "..." = JSON string, |N = the next N lines, *n = &n.
```

`examples/quickstart.json` için 40 / 42 token:

```
# bpp4: JSON as 'key value' lines, 1-space indent nests. k[N]{a b}: N rows, values in column order, last one = rest of line.
```

**Markdown primer'ı.** `encode_md`, Markdown ağaçları için yazılmış ayrı bir primer kullanır.
`examples/project_plan.md` için (64 / 65 token):

```
# bpp4 Markdown: steps[N]{cols} = N headings/list items, cols in order, title = rest of line, indented rows = sub-items (>{...}: own cols); status: todo/done/doing/cancelled (- none); note= its text. "..." = JSON string.
```

Bununla proje planı 822 / 1062 token tutuyor, Markdown kaynağından (837 / 1078) az; bpp3 primer'iyle
876 / 1106 tutuyordu.

**3 satır** (`--primer long`, sabit metin, 156 / 166 token; Markdown girdisinde `--primer long`
Markdown primer'ını verir):
```
# bpp4 = JSON data. Lines are 'key value'; a bare 'key' opens a nested object (1-space indent). [a,b] = list.
# k[N]{a b.c d}: N rows, values space-separated in column order, b.c = key c inside object b, last column = rest of line;
# x? = optional, '-' if absent; x?= written as x=v; >kids: indented rows are kids (a bare > keeps the table's key), >kids{...} gives them their own columns. {a,b}: comma rows. k[N]: N '- ' items. "..." = JSON string. |N = the next N lines as a string. *n = &n value.
```

**Ölçüm (E16):**

| primer | o200k | claude2 |
|---|---:|---:|
| bpp3, 1 satır | 84 | 88 |
| bpp4, `plan.json` | 64 | 66 |
| bpp4, `examples/quickstart.json` | 40 | 42 |
| bpp4, Markdown, `project_plan.md` | 64 | 65 |

> Geçmiş: Aşama 1'deki primer "k[N]{a,b} = N CSV rows" diyordu; Aşama 2'de satır tablosu varsayılan
> olunca primer gerçek sözdizimini anlatacak şekilde yeniden yazıldı (38 → 60 token). `bpp2` ile
> `x?` / `x?=` ayrımı eklendi (60 → 70 token); bpp3 yolları ve alt tabloları ekledi (70 → 84 token);
> bpp4'te yalnızca kullanılanı anlatır oldu.

Primer sabit maliyettir. Varsayılan **kapalı**; anlama testi primer'li ve primer'siz cevapları
karşılaştırır.

## 9. Kayıpsızlık tanımı

`decode(encode(x)) == x`, JSON veri modeli üzerinde:

* tipler korunur (int/float, string/sayı, null);
* nesne anahtar sırası korunur; tek istisna §4.3(b) (bir metin sütunu satır sonuna taşınır).
  `encode(..., keep_order=True)` / `bpp encode --keep-order` bunu da kapatır ve JSON metni
  anahtar sırasıyla birlikte birebir geri gelir;
* YAML: yorumlar, anchor'lar, etiketler veri modeline ait değildir, korunmaz. Tarih/saat
  değerleri string olarak okunur (otomatik `date` dönüşümü kapatılır). String olmayan YAML
  anahtarları string'e çevrilir.
* CSV: hücre metni birebir korunur. Encoder bir hücreyi sayı/bool/null'a yalnızca metne geri
  yazıldığında aynı metni verecekse çevirir (`007` string kalır, `1.50` string kalır).
* Markdown: ağaç yapıyı korur (başlıklar, maddeler, checkbox'lar, notlar), biçimi korumaz;
  yumuşak satır sonları birleştirilir (§7.1). Ağaçtan yazılan normalize Markdown aynı ağaca geri
  okunur. `bpp4 md` dosyası (§7.2) kaynak metni bayt bayt geri verir.

## 10. Gramer (özet, EBNF benzeri)

```
file      = "bpp4" NL {comment} {def} body
          | "bpp4 md" NL {any}                             (* Markdown kaynağı, §7.2 *)
comment   = INDENT "#" {any} NL
def       = "&" digits SP string NL [blocks]
body      = object(0) | rootarray | scalar NL [blocks]
object(d) = {entry(d)}
entry(d)  = I(d) key SP inline NL [blocks]                 (* skaler / [..] / {} / [] *)
          | I(d) key NL object(d+1)                        (* iç içe nesne *)
          | I(d) key "[" N "]" "{" cols(",") "}" NL N×(row(d, ",") [blocks])
          | I(d) key "[" N "]" spec NL rowtree(d, spec)     (* her satırın ardından blokları *)
          | I(d) key "[" N "]" NL N×item(d)
item(d)   = I(d) "- " (inline | entry-tail) NL [blocks] [object(d+1)]
spec      = "{" cols(" ") "}" [">" [seg] [spec]]           (* >k ya da tek başına > (aynı anahtar, bpp4) *)
col       = path ["?" ["="]] [":str"]                      (* ? ve ?= yalnızca boşluklu başlıkta *)
path      = seg {"." seg}                                   (* bpp3; bpp1/2: tek anahtar *)
seg       = "." içermeyen anahtar  |  jsonstring
inline    = scalar | "[" [scalar {"," scalar}] "]" | "{}"   (* [..] içinde blok yok *)
scalar    = "null" | "true" | "false" | number | jsonstring | "*" digits | "|" digits | barestring
blocks    = satırdaki "|N" işaretlerinin ham satırları, her biri N satır, sırayla   (* bpp4 *)
I(d)      = d × " "
```

## 11. Sürüm geçmişi

* **bpp4** — Konu Markdown: bpp3 düz yazıda kaynağa kaybediyordu (README o200k'de 3845'e karşı
  3722 token). Eklenenler: çok satırlı string'ler için `|N` blokları (§2.2), birleştirilen yumuşak
  satır sonları (§7.1), tablonun kendi çocuk anahtarı için tek başına `>`, ağaçla yarışan alt
  tablolar (§4.3.1), yalnızca rakamdan önce tırnaklanan `*`, kaynağı saklayan `bpp4 md` biçimi
  (§7.2) ve yalnızca kullanılanı anlatan primer (§8). §7.1'deki beş Markdown belgesi o200k'de
  Markdown olarak 15072, bpp3'te 15510, bpp4'te 14824 token (claude2'de 15844, 16094 ve 15513);
  her biri artık kaynağından küçük. Hiçbir JSON, YAML, CSV örneği büyümedi: `plan.json` 636 → 634
  (o200k) ve her primer kısaldı. Decoder bpp1–bpp3 başlıklarını eski kurallarıyla okur (orada `|2`
  bir string'dir ve `>` ad ister).
* **bpp3** — Sütun yolları (`customer.name`) ve kendi sütunları olan alt tablolar
  (`>items{sku qty name}`) eklendi; iç içe nesne ve alt liste içeren nesne dizileri artık satır
  tablosuna sığıyor. Ölçüm (`examples/orders.json`): 1762 → 1151 token (o200k, −%34.7), 1839 → 1178
  (claude2, −%35.9); diğer örnekler değişmedi. `.` içeren anahtarlar tablo başlıklarında
  tırnaklanır. Decoder bpp1/bpp2 başlıklarını eski kurallarıyla okur (`.` anahtarın parçasıdır).
* **bpp2** — Pozisyonel opsiyonel sütun (`ad?`, eksikse `-`) eklendi; bpp1'deki `ad?` (anahtarlı)
  gösterimi `ad?=` oldu. Gerekçe: Markdown checklist planında .bpp kaynak Markdown'a kaybediyordu,
  çünkü çoğu satırda bulunan `status` her satırda `status=` diye tekrar ediliyordu. Ölçüm
  (`examples/project_plan.md`): 857 → 792 token (o200k, −%7.6), 1083 → 1017 (claude2, −%6.1);
  kaynak Markdown 837 / 1078 token, yani .bpp artık Markdown'dan −%5.4 / −%5.7 ucuz. Bedeli: yalnızca
  anahtarlı opsiyonel sütun içeren tablolarda başlık sütun başına 1 karakter uzar (`plan.json`:
  +2 token).
* **bpp1** — İlk sürüm. Decoder `bpp1` başlıklı dosyaları okumaya devam eder; bu dosyalarda `ad?`
  anahtarlı opsiyonel anlamına gelir.

