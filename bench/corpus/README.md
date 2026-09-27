# bpp — give LLMs your data in ~63% fewer tokens

**bpp** converts JSON, YAML, CSV and Markdown plans into `.bpp`, a compact text format that
language models read with far fewer tokens. You can convert it back without losing anything.

* **~63% fewer tokens than pretty JSON, ~36% fewer than [TOON](https://github.com/toon-format/toon)**
  across the benchmark set. The format beats minified JSON, YAML, CSV and even raw Markdown on
  every example.
* **Lossless round trip:** `decode(encode(x)) == x` for JSON and YAML, with types preserved.
  CSV cells come back byte for byte. Markdown plans keep their structure.
* **Measured, not invented.** Every syntax choice was benchmarked on two tokenizers. There are no
  made-up symbols or binary tricks, only patterns models already know from YAML, CSV, JSON and
  TypeScript.
* **One command, one dependency.** `pip install`, then `bpp data.json`.

**▶ [Try it in your browser](https://e7lektronxf.github.io/bpp/):** paste your own data and compare
token counts, with no install needed.

🇹🇷 Türkçe: [README.tr.md](https://github.com/E7lektronXF/bpp/blob/main/README.tr.md)

```
JSON, pretty-printed (146 tokens)                  bpp (53 tokens)

{                                                  bpp3
  "store": "Downtown Branch",                      store Downtown Branch
  "orders": [                                      orders[3]{id product qty price customer}
    {"id": 1, "customer": "Alice Johnson",         1 Headphones 2 79.9 Alice Johnson
     "product": "Headphones", "qty": 2,            2 Keyboard 1 129.0 Bob Smith
     "price": 79.9},                               3 Headphones 1 79.9 Carol White
    ...
```

## Results

Token counts per format for six example files (o200k tokenizer; fewer is better):

| data | JSON | minified JSON | YAML | TOON | Markdown | **bpp** | bpp vs best alternative |
|---|---:|---:|---:|---:|---:|---:|---|
| 60×10 table (CSV) | 5538 | 3562 | 4388 | 2277 | – | **2042** | −6% vs CSV |
| nested config (YAML) | 601 | 365 | 443 | 399 | – | **323** | −12% vs minified JSON |
| project plan with deps (JSON) | 1609 | 990 | 1212 | 1228 | – | **636** | −36% vs minified JSON |
| Markdown checklist plan | 1501 | 1025 | 1119 | 1093 | 837 | **792** | −5% vs Markdown |
| API response with nested objects | 3524 | 2231 | 2636 | 2276 | – | **1151** | −48% vs minified JSON |
| repetitive logs | 5629 | 4109 | 4587 | 3348 | – | **1857** | −42% vs CSV |
| **total** | 18402 | 12282 | 14385 | 10621 | | **6801** | **−63% vs JSON, −36% vs TOON** |

Anthropic's published Claude tokenizer (`claude2`) shows the same picture: −62% vs JSON, −36% vs
TOON. The full tables, the method and the cases where bpp wins by less are in
[BENCHMARK.md](https://github.com/E7lektronXF/bpp/blob/main/BENCHMARK.md).

## Quick start

### 1. Install

You need Python 3.9 or newer (check with `python --version`). Then run:

```bash
pip install bpp-format
```

If `pip` isn't found, use `python3 -m pip` on macOS/Linux or `py -m pip` on Windows.

> ⚠️ The package is called **`bpp-format`**; the command and the Python import are `bpp`.
> `pip install bpp` installs an unrelated project.

Optional: `pip install "bpp-format[stats]"` also installs tiktoken, for exact token counts instead
of estimates.

```bash
bpp --version      # bpp 0.3.0
```

### 2. Convert a file

```console
$ bpp quickstart.json
quickstart.json -> quickstart.bpp (o200k: 122 -> 53 tokens, -57%)
```

This works with `.json`, `.yaml`, `.csv` and `.md` files. Want a sample to try?
`curl -O https://raw.githubusercontent.com/E7lektronXF/bpp/HEAD/examples/quickstart.json`

### 3. Give it to your LLM

Open `quickstart.bpp`, then paste it into ChatGPT, Claude or your prompt template. If the model
hasn't seen the format before, add `--primer`. It prepends a one-line explanation (~85 tokens):

```bash
bpp quickstart.json --primer -o -     # print to the terminal instead of writing a file
```

```
bpp3
# bpp3: JSON as 'key value' lines, 1-space indent nests. k[N]{a b}: N rows of values in column order, last column = rest of line; x? = optional ('-' if absent), x?= columns appear as x=v. "..." = JSON string, *n = &n.
store Downtown Branch
...
```

### 4. Convert back

```console
$ bpp quickstart.bpp -o roundtrip.json
```

`roundtrip.json` holds exactly the original data. Use `-o file.yaml`, `-o file.csv` or `--to md`
for other formats. bpp never silently overwrites an existing file; pass `--force` to allow it.

### Compare formats yourself

```console
$ bpp stats quickstart.json
format           chars  o200k  claude2  vs JSON (o200k)  vs JSON (claude2)
JSON (indent 2)    434    146      136            +0.0%              +0.0%
JSON (minified)    271     82       81           -43.8%             -40.4%
YAML               261    102       82           -30.1%             -39.7%
bpp                163     53       48           -63.7%             -64.7%
bpp + primer       402    137      137            -6.2%              +0.7%
```

On a file this small the primer eats most of the savings. Use it on larger inputs.

### From Python

```python
import bpp

text = bpp.dumps(data)          # Python object -> bpp text (send this to the LLM)
data = bpp.loads(text)          # bpp text -> Python object

data = bpp.load("config.yaml")  # reads .json .yaml .csv .md .bpp
bpp.dump(data, "config.bpp")    # format chosen by extension
```

## The format in one minute

```
bpp3
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

* **`key value` lines.** A bare `key` opens a nested object, and nesting is one space of
  indentation. There are no braces, no colons and no quotes unless a value needs them.
* **Tables:** `name[N]{a b c}` is followed by N rows of values in column order. Keys are written
  once instead of on every object. The last column takes the rest of the line, so free text
  needs no quotes.
* **Nested data:** `customer.name` is key `name` inside object `customer`, and `>items{...}`
  means the rows indented under a row are its `items`, with their own columns.
* **Optional columns:** `x?` sits in place, with `-` when absent. `x?=` appears only when present,
  as `x=value`.
* **Trees:** `>steps` means rows indented under a row are its children. This is how plans are
  written.
* **Dictionary:** a long value repeated many times is written once as `&0 value` and referenced
  as `*0`, in YAML anchor style. It is used only when it measurably saves tokens.
* **Strings** are quoted JSON-style only when they would be ambiguous. Unicode stays raw UTF-8.

A plan with dependencies (`examples/plan.json`: 1609 tokens as JSON, 636 as bpp):

```
steps[6]{id:str status priority deps:str owner?= note?= title}>steps
1 done P1 [] owner=Ayşe Gereksinim analizi
 1.1 done P1 [] Paydaş görüşmeleri
 1.2 done P0 [] Regülasyon incelemesi (BDDK, PCI-DSS)
 1.3 done P1 [1.1] Kabul kriterlerinin yazılması
2 done P1 [1] owner=Mehmet Mimari tasarım
```

An API response with nested objects and sub-lists (`examples/orders.json`: 3524 tokens as JSON,
2231 minified, 1151 as bpp). `customer.city` is a key inside the `customer` object, and each order's
`items` are the indented rows under it, with their own columns:

```
orders[20]{order_id customer.city status shipping_method total note customer.name}>items{sku qty unit_price name}
ORD-2026-00001 Ankara paid standard 2897.68 *4 Ayşe Arslan
 SKU-254 3 335.6 *3
 SKU-940 1 1890.88 Laptop Standı
```

A Markdown checklist (`examples/project_plan.md`: 837 tokens as Markdown, 792 as bpp). Headings
and nested lists become a tree; `[ ]` `[x]` `[/]` `[-]` become `todo` `done` `doing` `cancelled`:

```
steps[5]{status? note?= title}>steps
- Keşif ve envanter
 done note="Toplam 312 Airflow DAG'i, 48 Spark işi ve 17 Hive veritabanı tespit edildi." Mevcut iş akışlarının envanteri
 done Veri sahipleriyle görüşmeler
  done Pazarlama analitiği
```

The full grammar and the measurement behind each rule are in [SPEC.md](https://github.com/E7lektronXF/bpp/blob/main/SPEC.md).

## Why it is smaller

LLMs read tokens, and tokenizers are trained on English, code and JSON. Invented symbols or binary
encodings usually cost more tokens and hurt understanding. bpp saves tokens by:

1. **Removing repetition.** Object keys are written once per table, not once per row.
2. **Dropping punctuation the tokenizer charges for.** A space merges into the next token; `:`,
   `,` and `"` usually don't. Switching table rows from commas to spaces alone saved 12–22%.
3. **Referencing long repeated values** through a small dictionary, but only when the estimated
   gain is positive.
4. **Keeping structure explicit:** row counts (`[N]`), column names and indentation give the model
   a frame to read against.

## Guarantees

| input | round trip |
|---|---|
| JSON / YAML | `loads(dumps(x)) == x`, types included (`1` ≠ `1.0`, `"42"` ≠ `42`, `null`). With `--keep-order`, the JSON text comes back identical, key order included. YAML comments and anchors are not data and are not kept. Dates stay strings. |
| CSV | Cells and column order come back byte for byte. Numbers are typed only when writing them back gives the same text (`007` and `1.50` stay strings). |
| Markdown | Structure is kept, formatting is not. Output is normalized Markdown that parses back to the same tree. |

Backed by 217 tests: edge cases (empty containers, 80-level nesting, delimiters inside strings,
multi-line text, Unicode, number-like strings) and hypothesis property tests on random JSON, CSV,
YAML and Markdown trees.

## Honest caveats

* **Understanding is not measured yet.** Token savings are measured. Whether models answer
  questions about bpp as accurately as about JSON is not yet known. A ready-to-run comprehension
  benchmark (10 auto-graded questions per dataset, every format) is included:
  `ANTHROPIC_API_KEY=... python bench/run_qa.py`. The biggest risk is the dictionary: the model
  has to resolve `*3` to its definition.
* **Token counts are proxies.** They come from tiktoken `o200k_base` and Anthropic's older public
  Claude tokenizer. Current Claude models use a different tokenizer. Set `ANTHROPIC_API_KEY` and
  `bpp stats` adds real `count_tokens` numbers.
* **Small gains in some cases:** plain flat tables are only ~6% smaller than CSV on o200k (17% on
  claude2). The primer (~85 tokens) cancels the savings on documents of a few hundred tokens.

## Command reference

`bpp FILE` covers most uses. It encodes, or decodes if FILE ends in `.bpp`. The full subcommands:

```bash
bpp encode data.json -o data.bpp [--primer none|short|long] [--no-refs] [--keep-order]
bpp encode - --from yaml < config.yaml       # read from stdin
bpp decode data.bpp -o data.yaml             # output format from the extension
bpp decode data.bpp --to json --indent -1    # minified JSON
bpp decode plan.bpp --to md
bpp stats data.json [--markdown]
```

| option | effect |
|---|---|
| `--primer` | Prepend a format explanation (`short` ~85, `long` ~135 tokens). |
| `--no-refs` | Disable the `&n`/`*n` dictionary. |
| `--keep-order` | Never reorder keys. By default a table may move a free-text column such as `title` to the end of each row, which changes JSON key order but not the data. Always on for CSV input. |
| `-o -` | Write to stdout. |
| `-f`, `--force` | Allow overwriting an existing file in one-step mode. |

## Troubleshooting

| problem | fix |
|---|---|
| `bpp: command not found` | Use `python -m bpp ...`, or open a new terminal. |
| `pip: command not found` | `python3 -m pip install ...` (macOS/Linux) or `py -m pip install ...` (Windows). |
| `externally-managed-environment` | `pipx install bpp-format`, or install inside a virtualenv (`python3 -m venv .venv && . .venv/bin/activate`). |
| `cannot infer format` | Use one of these extensions: `.json .yaml .yml .csv .md .bpp`. |
| `... exists; use -o ...` | bpp refused to overwrite your original file. Pick another name with `-o`. |

Upgrade with `pip install --upgrade bpp-format`. Uninstall
with `pip uninstall bpp-format`.

## Development

```bash
git clone https://github.com/E7lektronXF/bpp.git && cd bpp
pip install -e ".[dev]"        # + pytest, hypothesis, tiktoken
pytest -q                      # 217 tests
python bench/run_tokens.py     # regenerate the token benchmark
python bench/experiments.py    # the design experiments behind SPEC.md
python bench/run_qa.py         # comprehension benchmark (needs ANTHROPIC_API_KEY)
```

The TOON column needs Node.js and `cd bench/toon && npm install`.

```
SPEC.md        format specification and the measurement behind every rule
js/            JavaScript port (byte-identical output, tested against Python)
site/          browser playground source; `python site/build.py` writes docs/index.html
BENCHMARK.md   token results, comprehension test, losses and proposed revisions
src/bpp/       encoder, decoder, converters, CLI
examples/      sample inputs next to their .bpp output
bench/         experiments, token benchmark, comprehension benchmark
tests/         pytest + hypothesis
```

## License

[MIT](https://github.com/E7lektronXF/bpp/blob/main/LICENSE)
