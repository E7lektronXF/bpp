# .bpp — Format Specification (version `bpp2`)

> Status: **v2** (`bpp2`; the decoder also reads `bpp1` files, see §11). Every decision was
> measured with `bench/experiments.py`; raw results are in `bench/results/experiments.md`.
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
bpp2                      ← header line (required, version)
# ...                     ← 0+ comment/primer lines (optional)
&0 long repeated value    ← 0+ dictionary definitions (optional)
...body...                ← the root value
```

* UTF-8 encoding, `\n` line endings (`\r\n` is accepted when reading).
* Indentation is **1 space** per level. Tabs are not used for indentation.
* A line starting with `#` (after indentation) is a comment and the decoder ignores it. Keys that
  start with `#` are quoted.
* Blank lines are ignored.

**Measured (E2, nested config):** 1-space indentation is 6.4% cheaper than 2 spaces on o200k and
the same on claude2. Tab indentation costs 12% more on claude2.

## 2. Scalar values

| Type | Written as | Note |
|---|---|---|
| null | `null` | |
| bool | `true` / `false` | `T/F` and `1/0` were measured: no gain (E1) |
| number | JSON number grammar: `42`, `-3.5`, `1.0`, `1e-7` | `1` (int) and `1.0` (float) stay distinct |
| special number | `NaN`, `Infinity`, `-Infinity` | YAML input only |
| string (bare) | `Alice Johnson` | runs to the end of line or delimiter, depending on context |
| string (quoted) | `"line1\nline2"` | JSON string syntax and escapes |
| reference | `*3` | the value of dictionary entry `&3` (see §6) |

### 2.1 Quoting rule (minimal quoting)

A string is written **bare** unless one of the following holds, in which case it is written as a
JSON string:

* it is empty;
* it has leading or trailing whitespace;
* it contains a control character (`\n`, `\r`, `\t`, U+0000–U+001F, U+007F);
* it starts with `"`, `[`, `{`, `*`, `&` or `#`;
* it equals `null`, `true`, `false`, `NaN`, `Infinity` or `-Infinity`;
* it matches the JSON number grammar (`"42"`, `"1.1"`, `"-0"`);
* it contains the delimiter of its context: `,` in a comma table, a space in a row table (and the
  exact value `-` there), `,` or `]` in an inline list;
* it is a list item (`- `) and contains a space (see §5).

Quoted strings use only JSON's mandatory escapes: `\"`, `\\`, `\n`, `\r`, `\t`, `\b`, `\f` and
`\u00XX` for control characters. **Unicode (ç ğ ı İ ö ş ü, emoji, …) is never written as
`\uXXXX`**; it stays raw UTF-8. In bare strings a backslash is a literal backslash; there are no
escapes.

**Measured (E7, Turkish text):** JSON with `\u` escapes costs 161% more tokens than raw UTF-8 on
o200k and 124% more on claude2. Quoting every string costs 1.3% / 2.4% more in a table (E1).

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
  `"[]{}=,:?>`, and does not start with `-#&*`. Otherwise it is quoted as a JSON string
  (`"first name" Alice`). Keys with Unicode letters (`şehir`) stay bare.
* Key order is preserved.

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

### 4.3 Row table: space-delimited rows, sparse and recursive arrays — `key[N]{a b? c?= d}>child`

When the column names in the header are **separated by spaces**, rows are separated by spaces too.
This layout was designed for plans and trees; the measurements showed it is also the cheapest form
for flat tables (see the note in §4.2):

```
steps[2]{id:str status? priority deps:str owner?= note?= title}>steps
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
quoted.

## 5. Parsing ambiguities and how they are resolved

| Case | Resolution |
|---|---|
| Is `- hello world` a string or `{hello: "world"}`? | An object. String items with a space are quoted. |
| `- hello` (no space, no children) | The string `"hello"`. |
| A bare `key` with no children | Invalid; an empty object is `key {}`. |
| Is `42` a string or a number? | A number; the string is `"42"` or lives in a `:str` column. |
| A value starting with `*` or `&` | Quoted; a bare `*n` is a reference. |
| A lone `-` in a row table | The positional optional column is absent; the string is `"-"`. |

## 6. Dictionary / references: `&n` and `*n`

This is YAML's anchor/alias notation, a pattern LLMs already know:

```
bpp2
&0 Connection to upstream payment provider timed out after 30000ms
&1 payments-gateway-eu-west-1
logs[80]{ts level service message latency_ms}
2026-09-24T10:00:00Z ERROR *1 *0 30000
```

* Definitions come after the header and comments, before the body: `&n value` (a §2 scalar).
* `*n` may appear wherever a **string value** can: entry values, cells, list items and `name=`
  values. It is never used for keys.
* **Rule:** the encoder puts a string in the dictionary only if
  `n·t(value) − (t(definition line) + n·t(*i)) > 0`, where t is a deterministic token estimator.
  tiktoken is deliberately not used, so the output does not depend on the environment.
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
steps[N]{id:str status priority deps:str owner?= due?= note?= title}>steps
```

* `id`: hierarchical ID (`1`, `1.2`, `1.2.3`), unquoted thanks to `:str`.
* `status`: `todo | doing | done | blocked | cancelled`.
* `priority`: `P0 | P1 | P2 | P3`.
* `deps`: IDs of the steps this step depends on, as an inline list (`[1.1,2]`).
* Sub-steps are indented rows via `>steps`.

From Markdown, headings (`#`, `##`, …) and nested lists become a tree. `- [ ]` becomes
`status todo`, `- [x]` becomes `status done`, `[/]` becomes `doing` and `[-]` becomes
`cancelled`. Headings and items without a checkbox have no `status`, so the row shows `-`:

```
steps[5]{status? note?= title}>steps
- Discovery and inventory
 done note="Found 312 Airflow DAGs ..." Inventory of existing workflows
 doing Build the dependency graph
```

## 8. Primer (optional)

For an LLM that has never seen the format, a `#` comment line can be prepended to the file
(`bpp encode --primer`). The decoder ignores it.

**1 line (o200k 70 / claude2 73 tokens):**
```
# bpp2: JSON as 'key value' lines, 1-space indent nests. k[N]{a b}: N rows of values in column order, last column = rest of line; x? = optional ('-' if absent), x?= columns appear as x=v. "..." = JSON string, *n = &n.
```

**3 lines (115 / 123 tokens):**
```
# bpp2 = JSON data. Lines are 'key value'; a bare 'key' opens a nested object (1-space indent). [a,b] = list.
# k[N]{a b c}: N rows, values space-separated in column order, last column = rest of line;
# x? = optional, '-' if absent; x?= written as x=v; >kids: indented rows are kids. {a,b}: comma rows. k[N]: N '- ' items. "..." = JSON string. *n = &n value.
```

> History: the Stage 1 primer said "k[N]{a,b} = N CSV rows". Once row tables became the default in
> Stage 2 it was rewritten to describe the actual syntax (38 → 60 tokens). `bpp2` added the `x?` /
> `x?=` distinction (60 → 70 tokens).

The primer is a fixed cost: 2–3% on a 60-row table (~2050 tokens) and 12–35% on a small config
(~330 tokens). It is **off** by default. The comprehension benchmark compares answers with and
without it.

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

## 10. Grammar (summary, EBNF-like)

```
file      = "bpp2" NL {comment} {def} body
comment   = INDENT "#" {any} NL
def       = "&" digits SP scalar NL
body      = object(0) | rootarray | scalar NL
object(d) = {entry(d)}
entry(d)  = I(d) key SP inline NL                          (* scalar / [..] / {} / [] *)
          | I(d) key NL object(d+1)                        (* nested object *)
          | I(d) key "[" N "]" "{" cols(",") "}" NL N×row(d, ",")
          | I(d) key "[" N "]" "{" cols(" ") "}" [">" key] NL rowtree(d)
          | I(d) key "[" N "]" NL N×item(d)
item(d)   = I(d) "- " (inline | entry-tail) NL [object(d+1)]
col       = key ["?" ["="]] [":str"]                       (* ? and ?= only in space headers *)
inline    = scalar | "[" [scalar {"," scalar}] "]" | "{}"
scalar    = "null" | "true" | "false" | number | jsonstring | "*" digits | barestring
I(d)      = d × " "
```

## 11. Version history

* **bpp2** added positional optional columns (`name?`, `-` when absent). bpp1's `name?` (keyed)
  became `name?=`. Reason: on the Markdown checklist plan, .bpp lost to the source Markdown
  because `status`, present in most rows, was repeated as `status=` on every row. Measured on
  `examples/project_plan.md`: 857 → 792 tokens (o200k, −7.6%) and 1083 → 1017 (claude2, −6.1%).
  The source Markdown is 837 / 1078 tokens, so .bpp is now 5.4% / 5.7% smaller than Markdown. The
  cost: in tables with keyed optional columns, the header grows by one character per such column
  (`plan.json`: +2 tokens).
* **bpp1** was the first version. The decoder still reads files with a `bpp1` header; in those
  files `name?` means keyed optional.
