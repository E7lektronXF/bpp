# .bpp — Format Specification (version `bpp4`)

> Status: **v4** (`bpp4`; the decoder also reads `bpp1`, `bpp2` and `bpp3` files, see §11). Every
> decision was measured with `bench/experiments.py`; raw results are in `bench/results/experiments.md`.
> Benchmark results and proposed revisions (R1–R5): [BENCHMARK.md](BENCHMARK.md) §5.
> Türkçe: [SPEC.tr.md](SPEC.tr.md)

## 0. Goals and principles

`.bpp` writes the JSON data model (object, array, string, number, bool, null) in a form an LLM can
read **with fewer tokens and without losing structure**. Human readability is not a goal. The
format does deliberately reuse patterns that are abundant in LLM training data: YAML/TOML-like
indentation, CSV rows, JSON strings, YAML anchors, and TypeScript's `?` / `:type` notation. It
uses no invented symbols and no binary encoding.

The savings come from four sources:

1. **Removing repetition.** In arrays of objects, keys are written once in a header.
2. **Dropping unnecessary punctuation.** `{}`, `"`, `:` and `,` appear only when needed.
3. **Putting long repeated values in a dictionary**, but only when the net gain is positive.
4. **Keeping structure explicit.** Row counts (`[N]`) and column names give the LLM a frame.

Tokens were counted with two proxies: **o200k** (tiktoken `o200k_base`) and **claude2**
(Anthropic's published legacy Claude tokenizer, `@anthropic-ai/tokenizer`). Neither matches
current Claude models exactly. Anthropic's documentation notes that tiktoken undercounts Claude
tokens by 15–20%, and by more on non-English text. What matters here is the **relative difference
between formats**. When `ANTHROPIC_API_KEY` is set, `bpp stats` also shows real `count_tokens`
results.

---

## 1. File structure

```
bpp4                      ← header line (required, version)
# ...                     ← 0+ comment/primer lines (optional)
&0 long repeated value    ← 0+ dictionary definitions (optional)
...body...                ← the root value
```

* UTF-8 encoding, `\n` line endings (`\r\n` is accepted when reading).
* Indentation is **1 space** per level. Tabs are not used for indentation.
* A line starting with `#` (after indentation) is a comment and the decoder ignores it. Keys that
  start with `#` are quoted.
* Blank lines are ignored.
* Neither rule applies inside a `|N` block string (§2.2): its lines are taken as they are.
* A file whose header is `bpp4 md` holds a Markdown document as its source text (§7.2).

**Measured (E2, nested config):** 1-space indentation is 6.4% cheaper than 2 spaces on o200k and
the same on claude2. Tab indentation costs 12% more on claude2.

## 2. Scalar values

| Type | Written as | Note |
|---|---|---|
| null | `null` | |
| bool | `true` / `false` | `T/F` and `1/0` were measured: no gain (E1) |
| number | JSON number grammar, ASCII digits: `42`, `-3.5`, `1.0`, `1e-7` | `1` (int) and `1.0` (float) stay distinct |
| special number | `NaN`, `Infinity`, `-Infinity` | YAML input only |
| string (bare) | `Alice Johnson` | runs to the end of line or delimiter, depending on context |
| string (quoted) | `"line1\nline2"` | JSON string syntax and escapes |
| string (block) | `\|2` + 2 raw lines | multi-line text, bpp4 (see §2.2) |
| reference | `*3` | the value of dictionary entry `&3` (see §6) |

### 2.1 Quoting rule (minimal quoting)

A string is written **bare** unless one of the following holds, in which case it is written as a
JSON string:

* it is empty;
* it has leading or trailing whitespace;
* it contains a control character (`\n`, `\r`, `\t`, U+0000–U+001F, U+007F);
* it starts with `"`, `[`, `{`, `&` or `#`;
* it is `*` or `|` followed by digits only (`*12`, `|3`): a reference or a block marker;
* it equals `null`, `true`, `false`, `NaN`, `Infinity` or `-Infinity`;
* it matches the JSON number grammar (`"42"`, `"1.1"`, `"-0"`), even with non-ASCII digits
  (`"1٣"`): decoders read only ASCII digits as a number, but bpp 0.4.0 read `1٣` as 13;
* it contains the delimiter of its context: `,` in a comma table, a space in a row table (and the
  exact value `-` there), `,` or `]` in an inline list;
* it is a list item (`- `) and contains a space (see §5).

Quoted strings use only JSON's mandatory escapes: `\"`, `\\`, `\n`, `\r`, `\t`, `\b`, `\f` and
`\u00XX` for control characters. **Unicode (ç ğ ı İ ö ş ü, emoji, …) is never written as
`\uXXXX`**; it stays raw UTF-8. In bare strings a backslash is a literal backslash; there are no
escapes.

**Measured (E7, Turkish text):** JSON with `\u` escapes costs 161% more tokens than raw UTF-8 on
o200k and 124% more on claude2. Quoting every string costs 1.3% / 2.4% more in a table (E1).

**Measured (E13, bpp4):** bpp1–bpp3 quoted every string that starts with `*`, which caught Markdown
bold (`**Note:** …`). Quoting only `*` + digits saves 16 / 8 tokens (o200k / claude2) on the five
Markdown documents of §7.1.

### 2.2 Block strings: `|N` (bpp4)

`|N` in place of a string value means: **the N raw lines after this line are the string.**

```
note |3
First paragraph, with `code` and "quotes".

Second paragraph: \ and \n stay as they are.
```

* The N lines are joined with `\n`. Nothing in them is escaped, quoted or indented, and the
  decoder does not read them as bpp: a block line may be blank, start with spaces, `#`, `|`, `- `
  or look like a `bpp3` header. The count delimits the block, as `[N]` does for table rows.
* `|N` can stand for any string value: `key |N`, a list item `- |N`, a dictionary definition
  `&0 |N`, and every table cell (comma cells, positional cells, keyed `note=|N` and the last
  column). Inside an inline list (`[...]`) it is not a block: `[|3]` is the string `"|3"`.
* Several blocks on one line follow in order, left to right: after `|2 |1 Title` come the 2 lines
  of the first block, then the 1 line of the second.
* In a row table the block lines come right after their row, before its indented child rows.
* A string that ends with `\n` has an empty last line. The string `|3` itself is quoted (§2.1), and
  so is a key that looks like a block marker.
* The encoder uses a block only for a string that contains `\n` and no other control character
  (no `\r`, no `\t`), and only if its estimated gain is not negative (on a tie the block wins; it
  is also easier to read):

  `gain = t(" " + "json string") + m − t(" |N") − t(string + "\n")`

  t is the estimator of §6 and m the number of line breaks that follow ASCII punctuation or
  another line break: a raw newline merges into the token before it (`):\n\n` is one token), an
  escaped `\n` does not, and the estimator alone misses that.

**Measured (E10, the five Markdown documents of §7.1, whole files):**

| multi-line strings | o200k | claude2 |
|---|---:|---:|
| all quoted (bpp3) | 15201 | 15749 |
| all blocks | 14824 | 15508 |
| **block when the gain is ≥ 0** | **14824** | **15513** |

Writing every multi-line string as a block is within 5 tokens of the rule on these documents; the
rule keeps short strings such as `"a\nb"` quoted, where a block costs more.

## 3. Objects: `key value`

```
service
 name order-api
 version 2.4.1
 replicas 3
 debug false
 tls {}
 tags []
```

* `key␠value`: **a single space** between key and scalar.
* A bare `key` line opens a nested object; its children are one level deeper. A bare key without
  children is invalid: write `{}` for an empty object and `[]` for an empty array.
* A key is written bare if it is non-empty, contains no whitespace, control character or any of
  `"[]{}=,:?>`, does not start with `-#&*` and is not a block marker (`|3`). Otherwise it is quoted
  as a JSON string
  (`"first name" Alice`). Keys with Unicode letters (`şehir`) stay bare.
* Key order is preserved.
* A key appears at most once in an object; decoders reject a repeated key.

**Measured (E2, E9):** `key value` is cheaper than `key:value` by 2.9% / 7.1% on the config,
5.8% / 5.3% on the mixed document and 5.6% / 7.9% on the plan (o200k / claude2). The reason: a
space merges into the token of the next word, while `:` is usually a separate token. `key=value`
costs the same as `:`. Dotted path keys (`db.host`) cost 22% more on claude2, so they are not used.

## 4. Arrays

### 4.1 Inline list (scalars only)

```
beta_regions [TR,DE,NL]
sinks [stdout,file]
ports [80,443]
codes ["01","02"]
```

Items are separated by `,` with no spaces. An item containing `,` or `]`, or caught by §2.1, is
quoted. **Measured (E9):** `[a,b]` is 1.5% / 0.9% cheaper than TOON's `k[2]: a,b`.

### 4.2 Comma table: uniform arrays of objects — `key[N]{a,b,c}`

For arrays whose items all have **the same keys in the same order** and only scalar values:

```
employees[3]{id,name,city,salary,active,manager_id}
1,Alice Johnson,London,48500,true,null
2,"Smith, Bob",Berlin,61000,false,1
3,Carol White,Paris,39000,true,1
```

* `[N]` is the row count. Exactly N rows follow **at the same indentation as the header**. They
  need no extra indentation because the count delimits the block.
* Cells are separated by `,` as in CSV; a string containing `,` is quoted.
* **Typed column** `name:str`: bare cells in that column are always strings (never numbers or
  bools). `null`, quoted and `*n` cells keep their special meaning. Number-like IDs and codes
  such as `"1.1"` or `"007"` can therefore be written without quotes. The encoder adds `:str`
  when every non-null value in the column is a string and at least one would otherwise need
  quoting.

**Measured (E1, 60×10 table):** 60.8% / 55.8% smaller than JSON; 39% / 37% smaller than minified
JSON; on par with TOON (−4.7% on o200k, +0.6% on claude2); on par with CSV, which carries no types.
The variants differ little: a tab delimiter is 0.8% cheaper on o200k and equal on claude2; `|`
costs 4% more; indenting rows costs 2.8% more. Dropping `[N]` saves 0.1%, but it is **kept**
because it helps comprehension. Writing null as an empty cell saves 0.1–0.2%, but **`null` is
kept** for clarity.

> **Stage 2 revision:** measured with the real encoder, the same table written as a
> **space-delimited row table** (§4.3) turned out clearly cheaper than the comma table. On the
> 60×10 employee table it went from 2171 to 1910 tokens (o200k, −12%) and from 2511 to 1961
> (claude2, −22%). The reason: `,` is usually its own token and does not merge with the following
> word or number, while a space merges into the next token (the same effect as `key value` in §3).
> The encoder therefore builds every candidate for each array (comma table, row table, `- ` list)
> and picks the cheapest according to a deterministic token estimator; on a tie the
> order-preserving candidate wins. Comma tables still win when most values contain spaces.

### 4.3 Row table: space-delimited rows, sparse, nested and recursive arrays — `key[N]{a b.c? d?= e}>child`

When the column names in the header are **separated by spaces**, rows are separated by spaces too.
This layout was designed for plans and trees; the measurements showed it is also the cheapest form
for flat tables (see the note in §4.2):

```
steps[2]{id:str status? priority deps:str owner?= note?= title}>
1 done P1 [] owner=Alice Requirements analysis
 1.1 done P1 [] Stakeholder interviews
 1.2 - P0 [1.1] Regulatory review (GDPR, PCI-DSS)
2 todo P0 [1] owner="External vendor" note="Runs nightly at 02:00" Security testing
```

* Required columns are positional, separated by a single space. **The last column is the rest of
  the line**: it may contain spaces and needs no quotes.
* Optional columns (TypeScript's `name?:`) come in two forms. An optional column that does not
  appear in a row means the key is **absent** from that object, which is different from `null`:
  * `name?` is **positional optional**: the value sits in place, or a lone `-` when absent. A cell
    whose value is the string `"-"` is quoted.
  * `name?=` is **keyed optional**: written only when present, as `name=value`, after the
    positional columns and before the last column.

  For each optional column the encoder compares `missing·t(" -")` with `present·t(" name=")`.
  A column present in most rows (such as a plan's `status`) becomes positional; a sparse column
  (such as `note` or `owner`) becomes keyed. `:str` combines with both forms (`name?:str`,
  `name?=:str`).
* Positional and `name=` values are quoted if they contain a space. Cells can be scalars or inline
  lists (`[a,b]`, `{}`).
* `>child` names the recursion key. Rows directly below a row and **indented one more space** form
  that item's `child` array. An empty child array is written as `child=[]`; if the key is absent,
  nothing is written. `[N]` counts only top-level rows.
* A bare `>` (bpp4) means the child key is the table's own key: `steps[2]{...}>` is
  `steps[2]{...}>steps`. In a child spec (`orders[2]{...}>items{...}>`) it repeats that child key.
  A keyless table (`[N]{...}`) has no key to repeat and always names it. **Measured (E12):** −16 /
  −8 tokens on the five Markdown documents of §7.1, −2 / −1 on `plan.json` (636 → 634, 728 → 727).
* If the last column's value starts with a `name=` pattern, it is quoted.
* Header order = value order in the row = key order in the decoded object. Header and row order
  never diverge, so the LLM can map columns correctly.
* The encoder tries two variants: (a) order-preserving, where the last column is the original
  last key; (b) moving the text column with the most spaces (such as `title` or `name`) to the
  end, so its values need no quotes but the object's key order changes. It picks (b) only when
  it is cheaper and `keep_order` is off. **For CSV input `keep_order` is always on**, because
  column order is data.

**Measured (E4, E8, E8b; 6 steps + 21 sub-steps):**

| layout | o200k | claude2 |
|---|---:|---:|
| JSON pretty | 1609 | 1718 |
| JSON minified | 990 | 1078 |
| YAML | 1212 | 1248 |
| Markdown checklist | 828 | 894 |
| TOON | 1228 | 1257 |
| comma tree table | 652–664 | 797–820 |
| **row table (keyed `k=v` optionals, title last)** | **606** | **696** |
| outline with symbols (`<dep @owner #note`) | 576 | 662 |

The symbol outline is 5% cheaper, but `< @ #` carry invented meanings, which goes against
principle #1 and risks comprehension. The self-describing `deps=` / `owner=` was chosen instead.

### 4.3.1 Nested objects and child tables (bpp3)

Real API responses nest: an order has a `customer` object and a list of `items`. bpp1/bpp2 could
not put such arrays in a table and fell back to `- ` items (§4.4). bpp3 extends the row table in
two ways:

```
orders[2]{id customer.city status customer.name}>items{sku qty name}
A-1 London paid Ada Lovelace
 K-1 2 Blue pen
 K-2 1 Red pen
A-2 Wilmslow sent Alan Turing
 K-3 5 Notebook
```

* **Column paths.** A column name `a.b.c` means key `c` inside object `b` inside object `a` of the
  row. Nested objects are flattened into such columns (any depth). A key that itself contains `.`
  is quoted in headers (`"a.b"`). Path columns can be required, optional (`?`, `?=`) and `:str`
  like any other column; a keyed optional path is written `a.b=value`. When decoding, an object is
  created only if at least one of its columns is present in the row, so absent and present
  objects round-trip exactly. Flattening is used only when every row agrees: if `k` is an object
  in one row and a plain value in another, the array is not written as a row table. The paths of
  a header are distinct and none is a prefix of another, so every value has one column; decoders
  reject `{a a}` and `{a a.b}`.
* **Child tables.** `>child` alone means the child rows use the same columns (a tree, as in
  plans). `>child{...}` gives the child rows their own columns. Child rows are indented one space
  under their parent row; child tables can have their own children (`>parts{...}>subs{...}`).
  An empty child list is `child=[]`, as before.

For the first child key that can be used, the encoder builds a tree (same columns) and a child
table (the top level gets its own columns); without a child key, a plain row table. The usual
cost comparison (§4.2) then decides between those, a comma table and `- ` items. Key order is
rebuilt in header order; with `keep_order` the encoder only uses a layout whose rebuilt objects
have exactly the original key order.

bpp3 kept the tree whenever it was lossless. bpp4 lets the child table compete, which matters for
Markdown trees: headings (the top level) often carry a long note, list items rarely do. In a child
table the heading's note can be positional (`|7 Title`, `-` when absent) while it stays keyed
below (`note=|7`). **Measured (E14, the five Markdown documents of §7.1):** −14 / −12 tokens.

**Measured (`examples/orders.json`, 20 orders with a customer object and 1–3 items each):**

| | o200k | claude2 |
|---|---:|---:|
| bpp2 (`- ` items) | 1762 | 1839 |
| **bpp3 (paths + child table)** | **1151 (−34.7%)** | **1178 (−35.9%)** |
| minified JSON | 2231 | 2455 |
| TOON | 2276 | 2342 |

### 4.4 Generic list: `key[N]` + `- ` items

For arrays that cannot be a table or row table (mixed types, nested objects):

```
orders[2]
- order_id ORD-1
 customer
  name Alice
 items[1]{sku,qty}
 SKU-1,2
- order_id ORD-2
 status cancelled
mixed[3]
- 1
- "two words"
- [a,b]
```

* Items start with `- ` at the header's indentation; there are N items.
* Object item: its first entry is on the `- ` line and the other entries are **one level
  deeper**. An empty object item is `- {}`.
* Scalar item: `- value`. String items containing a space are quoted, since they would otherwise
  read as a `key value` entry.
* Nested array item: `- [a,b]`, or a keyless header `- [N]{a,b}` / `- [N]`.

### 4.5 Root value

A root object's entries are written at indentation 0. A root array uses a keyless header
(`[60]{id,name}`, `[3]`, `[1,2,3]`). A root scalar is a single line; a root string is always
quoted, unless it is written as a block (`|N` and its lines, §2.2).

## 5. Parsing ambiguities and how they are resolved

| Case | Resolution |
|---|---|
| Is `- hello world` a string or `{hello: "world"}`? | An object. String items with a space are quoted. |
| `- hello` (no space, no children) | The string `"hello"`. |
| A bare `key` with no children | Invalid; an empty object is `key {}`. |
| Is `42` a string or a number? | A number; the string is `"42"` or lives in a `:str` column. |
| A value starting with `*` or `&` | Quoted; a bare `*n` is a reference. |
| A lone `-` in a row table | The positional optional column is absent; the string is `"-"`. |
| Is `a.b` in a header one key or a path? | A path (bpp3). A key containing `.` is quoted: `"a.b"`. |
| Is `\|3` a string or a block? | A block of 3 lines (bpp4). The string is `"\|3"`; inside `[...]` it is the string. |
| `*note*`, `**bold**` | Strings. Only `*` + digits is a reference; the string `"*3"` is quoted. |
| `- \|2` followed by 2 lines | A block string item. A key `\|2` is quoted, so it cannot be an object. |

## 6. Dictionary / references: `&n` and `*n`

This is YAML's anchor/alias notation, a pattern LLMs already know:

```
bpp4
&0 Connection to upstream payment provider timed out after 30000ms
&1 payments-gateway-eu-west-1
logs[80]{ts level service message latency_ms}
2026-09-24T10:00:00Z ERROR *1 *0 30000
```

* Definitions come after the header and comments, before the body: `&n value` (a §2 scalar; a
  multi-line value may be a block, `&0 |3`).
* `*n` may appear wherever a **string value** can: entry values, cells, list items and `name=`
  values. It is never used for keys.
* **Rule:** the encoder puts a string in the dictionary only if
  `n·t(value) − (t(definition line) + n·t(*i)) > 0`, where t is a deterministic token estimator.
  tiktoken is deliberately not used, so the output does not depend on the environment. In bpp4
  the estimator counts a run of newlines (a blank line) as one token and keeps `?=`, `=|` and `"=`
  as two, as both tokenizers do (E14: −3 / −1 tokens on the Markdown documents; no JSON, YAML or
  CSV example changes).
  Candidates are strings of at least 8 characters that occur at least twice; they are numbered
  by gain.

**Measured (E3, 80 log rows):** putting messages and service names in the dictionary saves 39.0% /
40.1%. Short values such as departments or cities (1–2 tokens) gain nothing (−0.1% / −1.7%), and
the threshold rule filters them out. TOON has no dictionary; on this dataset TOON is 5% more
expensive than bpp even without the dictionary.

## 7. Plans

Recommended plan schema. The Markdown converter produces it, and JSON/YAML plans that follow it
are encoded the same way:

```
title <plan title>
goal <optional description>
steps[N]{id:str status priority deps:str owner?= due?= note?= title}>
```

* `id`: hierarchical ID (`1`, `1.2`, `1.2.3`), unquoted thanks to `:str`.
* `status`: `todo | doing | done | blocked | cancelled`.
* `priority`: `P0 | P1 | P2 | P3`.
* `deps`: IDs of the steps this step depends on, as an inline list (`[1.1,2]`).
* Sub-steps are indented rows via `>` (`>steps`).

From Markdown, headings (`#`, `##`, …) and nested lists become a tree. `- [ ]` becomes
`status todo`, `- [x]` becomes `status done`, `[/]` becomes `doing` and `[-]` becomes
`cancelled`. Headings and items without a checkbox have no `status`, so the row shows `-`. Here
the headings have their own columns (a child table, §4.3.1):

```
steps[5]{title}>{status? note?= title}>
Keşif ve envanter
 done Mevcut iş akışlarının envanteri Toplam 312 Airflow DAG'i, 48 Spark işi ve 17 Hive veritabanı tespit edildi.
 done Veri sahipleriyle görüşmeler
  done Pazarlama analitiği
```

### 7.1 Soft line breaks (bpp4)

Markdown keeps its structure, not its formatting (§9), and a soft line break is formatting:
CommonMark renders it as a space. bpp4 joins with a space:

* the wrapped lines of a list item's first paragraph, into its `title`, whether they are indented
  under the item or "lazy" (not indented). Before bpp4 they went to `note`, and since the title is
  the last column, the second half of a sentence was written before its first half
  (`note=virtualenv. Check https://… in a clean`);
* the wrapped lines of plain paragraphs inside a `note`.

Nothing is joined across a hard break (two trailing spaces or `\`) or a blank line, and lines
that start, or may start, a block of their own are never joined: code fences (```` ``` ````,
`~~~`), `$$` math, block quotes (`>`), HTML (`<`, until its end marker or a blank line), table
rows (any line containing `|`), list markers, `#`, thematic breaks and setext underlines (`---`,
`===`, `***`), link reference definitions (`[x]: …`) and YAML front matter. The line after a hard
break starts the item's `note`, so a checklist that wants a note under an item writes a hard break
or a blank line; a plain indented line continues the title, as it does in rendered Markdown.
`tree_to_md` writes a blank line between an item's title and its note, so md → tree → md → tree
is a fixed point. `md_to_tree(text, join=False)` keeps every line break (the bpp3 behaviour).

**Measured (E11):** the corpus for the bpp4 Markdown experiments is `bench/corpus/`: this
repository's README, SPEC, BENCHMARK and RELEASING as of v0.3.0, and `examples/project_plan.md`.

| line breaks | o200k | claude2 |
|---|---:|---:|
| all kept (bpp3) | 15059 | 15737 |
| item titles joined | 14915 | 15627 |
| **item titles and note paragraphs joined** | **14824** | **15513** |

### 7.2 Markdown kept as source: `bpp4 md` (bpp4)

A Markdown document can also be written as its own source text:

```
bpp4 md
# Releasing to PyPI

The package is published as ...
```

* A header line `bpp4 md` (after optional blank or `#` lines) means: everything after that line's
  `\n` is the Markdown source, byte for byte, to the end of the file. No count, no escaping and no
  bpp syntax follow the header.
* Decoding it gives `md_to_tree(source)` (`bpp decode`, `--to json`, `bpp.decode`), and `--to md`
  gives the source back unchanged (`bpp.md_source`). YAML and CSV output use the tree.
* `encode_md` (used by `bpp encode x.md`, `bpp x.md` and `bpp stats x.md`) builds the tree encoding
  and this form, and keeps the one the estimator counts as shorter; a tie keeps the tree. This form
  costs exactly its header line more than the source, 5 tokens on o200k and claude2, so by the
  estimator a Markdown file never grows by more than that. On the five documents the real
  tokenizers agree with every choice (E15).
* No primer is added to this form: it contains no bpp syntax.

**Measured (E15):**

| | o200k | claude2 |
|---|---:|---:|
| Markdown source | 15072 | 15844 |
| `bpp4 md` + source | 15097 | 15869 |
| **bpp4, `encode_md`** | **14824** | **15513** |
| bpp4 + primer, `encode_md` | 15010 | 15757 |

Per document (o200k / claude2): README 3703 / 3894 vs 3722 / 3938 in Markdown, SPEC 6144 / 6330 vs
6269 / 6483, BENCHMARK 3724 / 3756 vs 3747 / 3802, RELEASING 495 / 537 vs 497 / 543, project plan
758 / 996 vs 837 / 1078. With a primer, README, BENCHMARK and RELEASING are kept as source.

## 8. Primer (optional)

For an LLM that has never seen the format, a `#` comment line can be prepended to the file
(`bpp encode --primer`). The decoder ignores it.

**1 line.** Since bpp4 the primer explains only the syntax the output uses: row tables (with the
`b.c` path example only when a path column occurs), comma tables, `x?`, `x?=`, `>k` or a bare `>`,
`"..."`, `|N` and `*n`. With every feature (108 / 114 tokens):

```
# bpp4: JSON as 'key value' lines, 1-space indent nests. k[N]{a b.c}: N rows, values in column order (b.c = key c of b), last one = rest of line; k[N]{a,b}: N comma rows; x? optional (- = absent); x?= as x=v; >k: indented rows are k (bare >: same key). "..." = JSON string, |N = the next N lines, *n = &n.
```

For `examples/quickstart.json` it is 40 / 42 tokens:

```
# bpp4: JSON as 'key value' lines, 1-space indent nests. k[N]{a b}: N rows, values in column order, last one = rest of line.
```

**Markdown primer.** `encode_md` uses a primer written for Markdown trees instead. For
`examples/project_plan.md` (64 / 65 tokens):

```
# bpp4 Markdown: steps[N]{cols} = N headings/list items, cols in order, title = rest of line, indented rows = sub-items (>{...}: own cols); status: todo/done/doing/cancelled (- none); note= its text. "..." = JSON string.
```

With it the project plan takes 822 / 1062 tokens, less than its Markdown source (837 / 1078); with
the bpp3 primer it took 876 / 1106.

**3 lines** (`--primer long`, fixed text, 156 / 166 tokens; for Markdown input `--primer long` gives
the Markdown primer):
```
# bpp4 = JSON data. Lines are 'key value'; a bare 'key' opens a nested object (1-space indent). [a,b] = list.
# k[N]{a b.c d}: N rows, values space-separated in column order, b.c = key c inside object b, last column = rest of line;
# x? = optional, '-' if absent; x?= written as x=v; >kids: indented rows are kids (a bare > keeps the table's key), >kids{...} gives them their own columns. {a,b}: comma rows. k[N]: N '- ' items. "..." = JSON string. |N = the next N lines as a string. *n = &n value.
```

**Measured (E16):**

| primer | o200k | claude2 |
|---|---:|---:|
| bpp3, 1 line | 84 | 88 |
| bpp4, `plan.json` | 64 | 66 |
| bpp4, `examples/quickstart.json` | 40 | 42 |
| bpp4, Markdown, `project_plan.md` | 64 | 65 |

> History: the Stage 1 primer said "k[N]{a,b} = N CSV rows". Once row tables became the default in
> Stage 2 it was rewritten to describe the actual syntax (38 → 60 tokens). `bpp2` added the `x?` /
> `x?=` distinction (60 → 70 tokens); bpp3 added paths and child tables (70 → 84 tokens); bpp4
> made it list only what the output uses.

The primer is a fixed cost. It is **off** by default. The comprehension benchmark compares answers
with and without it.

## 9. Losslessness

`decode(encode(x)) == x` on the JSON data model:

* types are preserved (int/float, string/number, null);
* object key order is preserved, with one exception: §4.3(b), where a text column moves to the
  end of the row. `encode(..., keep_order=True)` / `bpp encode --keep-order` turns that off, and
  the JSON text then comes back identical, key order included;
* YAML: comments, anchors and tags are not part of the data model and are not preserved.
  Date/time values are read as strings (automatic `date` conversion is disabled). Non-string YAML
  keys are converted to strings.
* CSV: cell text is preserved exactly. The encoder turns a cell into a number/bool/null only if
  writing it back produces the same text (`007` and `1.50` stay strings).
* Markdown: the tree keeps the structure (headings, items, checkboxes, notes), not the formatting;
  soft line breaks are joined (§7.1). The normalized Markdown written from it parses back to the
  same tree. A `bpp4 md` file (§7.2) gives the source text back byte for byte.

## 10. Grammar (summary, EBNF-like)

```
file      = "bpp4" NL {comment} {def} body
          | "bpp4 md" NL {any}                             (* Markdown source, §7.2 *)
comment   = INDENT "#" {any} NL
def       = "&" digits SP string NL [blocks]
body      = object(0) | rootarray | scalar NL [blocks]
object(d) = {entry(d)}
entry(d)  = I(d) key SP inline NL [blocks]                 (* scalar / [..] / {} / [] *)
          | I(d) key NL object(d+1)                        (* nested object *)
          | I(d) key "[" N "]" "{" cols(",") "}" NL N×(row(d, ",") [blocks])
          | I(d) key "[" N "]" spec NL rowtree(d, spec)     (* each row followed by its blocks *)
          | I(d) key "[" N "]" NL N×item(d)
item(d)   = I(d) "- " (inline | entry-tail) NL [blocks] [object(d+1)]
spec      = "{" cols(" ") "}" [">" [seg] [spec]]           (* >k or bare > (same key, bpp4) *)
col       = path ["?" ["="]] [":str"]                      (* ? and ?= only in space headers *)
path      = seg {"." seg}                                   (* bpp3; bpp1/2: a single key *)
seg       = key without "."  |  jsonstring
inline    = scalar | "[" [scalar {"," scalar}] "]" | "{}"   (* no blocks inside [..] *)
scalar    = "null" | "true" | "false" | number | jsonstring | "*" digits | "|" digits | barestring
blocks    = the raw lines of the line's "|N" markers, N each, in order        (* bpp4 *)
I(d)      = d × " "
```

## 11. Version history

* **bpp4** is about Markdown, where bpp3 lost to the source on prose (README 3845 vs 3722 tokens on
  o200k): multi-line strings as `|N` blocks (§2.2), joined soft line breaks (§7.1), a bare `>` for
  the table's own child key, child tables competing with trees (§4.3.1), `*` quoted only before
  digits, a `bpp4 md` form that keeps the source (§7.2) and a primer that only explains what is used
  (§8). The five Markdown documents of §7.1 take 15072 tokens as Markdown, 15510 in bpp3 and 14824
  in bpp4 on o200k (15844, 16094 and 15513 on claude2); each one is now smaller than its source. No JSON, YAML or CSV example got bigger: `plan.json` 636 → 634 (o200k), and every
  primer is shorter. The decoder reads bpp1–bpp3 headers with their old rules (`|2` is a string
  there and `>` needs a name).
* **bpp3** added column paths (`customer.name`) and child tables with their own columns
  (`>items{sku qty name}`), so arrays of objects with nested objects and sub-lists fit in a row
  table. Measured on `examples/orders.json`: 1762 → 1151 tokens (o200k, −34.7%) and 1839 → 1178
  (claude2, −35.9%); the other examples are unchanged. Keys containing `.` are quoted in table
  headers. The decoder reads bpp1/bpp2 headers with their old rules (a `.` is part of the key).
* **bpp2** added positional optional columns (`name?`, `-` when absent). bpp1's `name?` (keyed)
  became `name?=`. Reason: on the Markdown checklist plan, .bpp lost to the source Markdown
  because `status`, present in most rows, was repeated as `status=` on every row. Measured on
  `examples/project_plan.md`: 857 → 792 tokens (o200k, −7.6%) and 1083 → 1017 (claude2, −6.1%).
  The source Markdown is 837 / 1078 tokens, so .bpp is now 5.4% / 5.7% smaller than Markdown. The
  cost: in tables with keyed optional columns, the header grows by one character per such column
  (`plan.json`: +2 tokens).
* **bpp1** was the first version. The decoder still reads files with a `bpp1` header; in those
  files `name?` means keyed optional.
