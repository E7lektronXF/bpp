# BENCHMARK — does .bpp actually work?

> Türkçe: [BENCHMARK.tr.md](BENCHMARK.tr.md)

Short answer: **on tokens, yes, and it is measured. On comprehension, not yet known**: no
`ANTHROPIC_API_KEY` was available when these results were produced. The comprehension benchmark
is written and ready to run (§3). Every number below can be reproduced with the scripts in the
repository:

```bash
python bench/make_examples.py   # generates the examples/ folder
python bench/run_tokens.py      # -> bench/results/tokens.md, tokens.json
python bench/run_qa.py          # -> bench/results/qa.md (needs an API key)
```

## 1. Method

**Data** (`examples/`):

| example | file | contents |
|---|---|---|
| employees | `employees.csv` | Flat table: 60 employees × 10 columns, Turkish names and cities |
| config | `config.yaml` | Nested service configuration (4 levels, small tables, lists) |
| plan | `plan.json` | Structured plan: 6 steps + 21 sub-steps with `id`, `status`, `priority`, `deps`, `owner`, `note` |
| project_plan | `project_plan.md` | Long Markdown plan: headings, nested checkbox lists, notes, a code block |
| orders | `orders.json` | Mixed structure: an API response with 20 orders, nested customer objects, line-item tables and free text |
| logs | `logs.json` | 80 log entries; long values (message, service name) repeat a lot |

**Formats:** JSON (2-space indent), minified JSON, YAML (PyYAML, `allow_unicode`), CSV (flat tables
only), Markdown (the md example only, source file), TOON (reference `@toon-format/toon` 4.1.1,
default settings), `.bpp` (default settings) and `.bpp` with the 1-line primer. The Markdown
example is encoded from its source with `encode_md`, as `bpp x.md` does.

**Token counters:**

* **o200k**: tiktoken `o200k_base`.
* **claude2**: Anthropic's published legacy Claude tokenizer (`@anthropic-ai/tokenizer`).

Neither is the tokenizer of current Claude models. According to Anthropic's documentation,
tiktoken undercounts Claude tokens by 15–20% on typical text and by more on non-English text such
as Turkish. The absolute numbers are therefore not representative; what we rely on is the
relative difference between formats. Two independent tokenizers pointing the same way suggests
the differences are not an artifact of one tokenizer. With `ANTHROPIC_API_KEY` set, `run_tokens.py`
and `bpp stats` add real `count_tokens` results as a third column.

## 2. Token results

### o200k

| example | JSON | JSON min | YAML | CSV | Markdown | TOON | **bpp** | bpp+primer | bpp vs best alternative |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| employees | 5538 | 3562 | 4388 | 2165 | – | 2277 | **2042** | 2088 | **-5.7%** (CSV) |
| config | 601 | 365 | 443 | – | – | 399 | **323** | 369 | **-11.5%** (JSON min) |
| plan | 1609 | 990 | 1212 | – | – | 1228 | **634** | 698 | **-36.0%** (JSON min) |
| project_plan | 1445 | 990 | 1083 | – | 837 | 1024 | **758** | 822 | **-9.4%** (Markdown) |
| orders | 3524 | 2231 | 2636 | – | – | 2276 | **1151** | 1221 | **-48.4%** (JSON min) |
| logs | 5629 | 4109 | 4587 | 3185 | – | 3348 | **1857** | 1903 | **-41.7%** (CSV) |
| **total** | 18346 | 12247 | 14349 | | | 10552 | **6765** | 7101 | **-63.1%** vs JSON, **-35.9%** vs TOON |

### claude2

| example | JSON | JSON min | YAML | CSV | Markdown | TOON | **bpp** | bpp+primer | bpp vs best alternative |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| employees | 5669 | 3984 | 4072 | 2501 | – | 2496 | **2084** | 2133 | **-16.5%** (TOON) |
| config | 611 | 393 | 417 | – | – | 389 | **332** | 381 | **-14.7%** (TOON) |
| plan | 1719 | 1078 | 1248 | – | – | 1257 | **727** | 794 | **-32.6%** (JSON min) |
| project_plan | 1683 | 1240 | 1259 | – | 1078 | 1215 | **996** | 1062 | **-7.6%** (Markdown) |
| orders | 3615 | 2455 | 2526 | – | – | 2342 | **1178** | 1252 | **-49.7%** (TOON) |
| logs | 5563 | 4199 | 4456 | 3249 | – | 3332 | **1800** | 1849 | **-44.6%** (CSV) |
| **total** | 18860 | 13349 | 13978 | | | 11031 | **7117** | 7471 | **-62.3%** vs JSON, **-35.5%** vs TOON |

Detailed tables, including the dictionary-free `--no-refs` variant: `bench/results/tokens.md`.

### 2.1 Where the savings come from

| source | where | effect |
|---|---|---|
| Keys written once (tables) | employees, logs, order line items, replicas | 55–60% smaller than JSON; the same mechanism as CSV/TOON |
| Space-delimited rows (instead of `,`) | every table | 12% (o200k) / 22% (claude2) smaller than comma tables. A space merges into the next token; a comma does not |
| `key value` (no `:`), 1-space indent | config, orders | 3–8% smaller than `key:value` |
| Dictionary (`&n` / `*n`) | logs, orders | logs: 36% / 39% smaller than without it; orders: 10.4% / 13.5% |
| Tree rows (`>steps`; a bare `>` since bpp4) | plan | 36% smaller than minified JSON; indented rows instead of nested objects |
| Positional optional column (`status?`, `-` when absent), bpp2 | project_plan | 7.6% / 6.1% smaller than bpp1; the change that made it beat the source Markdown |
| Column paths (`customer.name`) and child tables (`>items{...}`), bpp3 | orders | 34.7% / 35.9% smaller than bpp2, which wrote each order as a `- ` item |
| Joined line breaks, `\|N` blocks, bare `>`, child tables for headings, bpp4 | project_plan, Markdown documents | project_plan 792 → 758 / 1017 → 996; the five Markdown documents of §4.4: 15510 → 14824 / 16094 → 15513 |
| Minimal quoting + raw UTF-8 | everywhere | `\u` escapes would cost 124–161% more tokens on Turkish text |

**How much comes from the dictionary:** most of the big gap on the logs example comes from the
dictionary. With it disabled (`--no-refs`), .bpp takes 2921 / 2952 tokens on logs, only 8% / 9%
less than CSV. TOON has no dictionary mechanism.

## 3. Comprehension benchmark (not yet run)

For each example, `bench/run_qa.py` generates **10 questions** whose answers are computed from
the data:

* direct lookup ("name of id 17"),
* nested lookup ("host of the second replica"),
* counting ("how many orders are cancelled"),
* dependencies and parents ("which steps does 5.2 depend on"),
* resolving dictionary references (the log messages).

The same questions are sent to Claude together with the data in each format, one request per
format. Answers are graded automatically: numeric comparison for numbers, set equality for lists
and normalized equality for text. `--dry-run` prints all questions and expected answers, and the
grading logic is covered by `tests/test_bench.py`.

```bash
pip install ".[api]"
export ANTHROPIC_API_KEY=...
python bench/run_qa.py --dry-run                   # see questions and expected answers
python bench/run_qa.py                             # claude-opus-5, effort low, 1 repeat
python bench/run_qa.py --repeats 3 --effort high   # a more robust measurement
python bench/run_qa.py --model claude-sonnet-5 --examples plan logs
```

Any OpenAI-compatible API works too, with no extra package. Results go to
`bench/results/qa-<model>.md`:

```bash
export NVIDIA_API_KEY=nvapi-...                    # free key from build.nvidia.com
python bench/run_qa.py --provider nvidia           # deepseek-ai/deepseek-v4.1-flash, temperature 0
python bench/run_qa.py --provider nvidia --model openai/gpt-oss-20b
python bench/run_qa.py --provider openai --base-url https://.../v1 --model NAME   # OPENAI_API_KEY
```

The default run is 39 requests and about 60k input tokens. Refusal fallback is deliberately
**off**: a fallback would answer with a different model and spoil the comparison. Refusals count
as wrong answers and are reported.

**Comprehension risks (hypotheses, not measured):**

1. **Dictionary indirection.** The model has to resolve `*3` to the `&3` definition. The logs
   question "how many entries have this message" measures exactly this. The biggest saving
   (logs −42%) also carries the biggest comprehension risk.
2. **Header-to-column mapping.** In space-delimited rows with 10 columns, the model has to map
   each value to the right column. Values are in order and the header is written once. This is
   the same challenge as CSV/TOON, with spaces instead of commas as the delimiter.
3. **`key value` without a colon** carries less signal than YAML/TOML.
4. **Reading without the primer.** Can notations like `x?` and `>steps` be guessed without a
   primer? That is why the benchmark lists .bpp with and without the primer as separate rows.

## 4. Losing categories and why

### 4.1 Markdown checklist plan: lost in `bpp1`, fixed in `bpp2`

**In bpp1:** the source Markdown was 2.4% / 0.5% cheaper than .bpp (837 vs 857 tokens).

**Why:** most plan rows have a `status`, but not all of them (headings and some items have no
checkbox). So `status` was an optional column, and every row carried `status=done ` (3–4 tokens).
Markdown says the same with `[x]` (1–2 tokens). A second, smaller factor: notes are quoted as
`note="..."` with line breaks escaped as `\n`, whereas in Markdown the same notes are plain
indented lines.

**Prototype measurement** (same data, hand-built variants):

| variant | o200k | claude2 |
|---|---:|---:|
| bpp1 (`status=done`, `note="…"`) | 857 | 1083 |
| status positional, `-` when missing | **786** | **1011** |
| status as a checkbox `[x]` | 827 | 1058 |
| note as a text block (indented lines) | 842 | 1064 |
| checkbox + text block | 817 | 1044 |
| Markdown (source) | 837 | 1078 |

**Fix: R1, implemented in `bpp2`.** An optional column present in most rows is now written
positionally, shown as `-` when missing and marked `status?` in the header. Sparse columns stay
keyed as `note?=` and are written `note=...`. The encoder chooses per column by comparing costs.

```
steps[5]{status? note?= title}>steps
- Keşif ve envanter
 done note="Toplam 312 Airflow DAG'i, …" Mevcut iş akışlarının envanteri
 done Veri sahipleriyle görüşmeler
```

| | o200k | claude2 |
|---|---:|---:|
| bpp1 | 857 | 1083 |
| **bpp2** | **792** (−7.6%) | **1017** (−6.1%) |
| Markdown (source) | 837 | 1078 |
| bpp2 vs Markdown | **−5.4%** | **−5.7%** |

The difference between the prototype (786) and the real encoder (792) comes from the header
notation (`status? note?=`). The cost: in tables with keyed optional columns, the header grows by
one `=` per such column (`plan.json`: 634 → 636). The other examples are unchanged.

**Where the remaining tokens are:** 695 of the 792 tokens (o200k; 943 of 1017 on claude2) are
the titles and notes themselves, which cost the same in any format. The structure on top of that
costs 97 tokens in bpp versus 142 in Markdown (−32%; 74 versus 135, −45%, on claude2). Even a
format with no structure at all could save at most another ~12% on this file.

**Text blocks re-measured (R2):** writing notes as plain indented lines under their row instead
of `note="…"` gave 794 tokens instead of 792 in bpp2: the saved quotes and `note=` are paid back
as newline, indentation and a marker. R2 was dropped.

**Fixed in bpp4:** with the primer, .bpp was again more expensive than Markdown on this example
(876 vs 837; 1106 vs 1078 on claude2). bpp4 gives Markdown its own, shorter primer (64 / 65
tokens instead of 84 / 88) and joins the wrapped item lines (§4.4): with the primer the plan now
takes 822 / 1062 tokens. Every LLM already knows Markdown; whether .bpp is understood without the
primer has to be measured by the comprehension benchmark (§3).

### 4.2 The primer cancels the savings on small documents

The bpp3 primer was 84 / 88 tokens: bpp2 added `x?` / `x?=` and bpp3 added paths and child tables
to its explanation. Since bpp4 the primer explains only the syntax the file uses, 40–108 tokens
(SPEC §8). On the config example, .bpp with the primer (369; bpp3: 407) still costs more than
minified JSON (365). On the large examples (employees, logs) it adds 2–3%.

### 4.3 Small margin over CSV (o200k)

On a flat table .bpp is only 5.7% smaller than CSV on o200k; on claude2 the margin is 16.5%. CSV
has no types and cannot hold nested data, but for purely flat tables the gain is small and
depends on the tokenizer.

### 4.4 Prose-heavy Markdown: lost in `bpp3`, fixed in `bpp4`

**In bpp3:** on documents that are mostly paragraphs, .bpp was about 3% bigger than the Markdown
source: this repository's README took 3845 tokens in bpp3 against 3722 in Markdown (o200k), SPEC
6488 vs 6269, BENCHMARK 3872 vs 3747, RELEASING 513 vs 497. Only the checklist plan was smaller
(792 vs 837).

**Why:**

1. **Escaped multi-line notes.** A heading's text is its `note`, a multi-line string, written as
   a JSON string: two quotes, and every line break and quote escaped (`\n`, `\"`). An escaped
   `\n` is a token of its own, while a raw line break merges into the token before it (`):\n\n`
   is one token). On each document this cost as much as the whole difference, or more.
2. **Wrapped list items.** The wrapped second line of an item went to its `note`. The title is
   the last column, so the row showed the second half of the sentence first
   (`note=virtualenv. Check https://pypi.org/... in a clean`), and paid for `note=` and quotes.

**Fix (bpp4, SPEC §2.2, §7.1, §7.2):** multi-line strings are written as `|N` blocks (the next N
lines, raw), wrapped lines are joined with a space, a bare `>` stands for `>steps`, headings can
get their own columns, `**bold**` is no longer quoted, and when the tree is still longer than the
source, `bpp4 md` keeps the source itself. Measured on `bench/corpus/` (the four documents as of
v0.3.0 and the example plan; `bench/results/experiments.md`, E10–E15):

| document | Markdown | bpp3 | **bpp4** |
|---|---:|---:|---:|
| README | 3722 / 3938 | 3845 / 4035 | **3703 / 3894** |
| SPEC | 6269 / 6483 | 6488 / 6628 | **6144 / 6330** |
| BENCHMARK | 3747 / 3802 | 3872 / 3861 | **3724 / 3756** |
| RELEASING | 497 / 543 | 513 / 553 | **495 / 537** |
| project_plan | 837 / 1078 | 792 / 1017 | **758 / 996** |
| **total** | 15072 / 15844 | 15510 / 16094 | **14824 / 15513** |

(o200k / claude2.) The bpp3 column was measured with the v0.3.0 encoder.

**What is left:** on prose, bpp4 is only 0.4–2% smaller than Markdown. The text itself costs the
same in both; bpp saves the `#`, `-` and `1.` markers and pays for its header, table header and
`note=` markers. On RELEASING the margin is 2 tokens. The `bpp4 md` fallback means a file that the
tree would make longer grows by only its 5-token header line (by the encoder's estimate; on these
files the real tokenizers agree).

## 5. Proposed SPEC revisions

| # | proposal | reason | status |
|---|---|---|---|
| R1 | **Write frequently present optional columns positionally**, with `-` when missing (the string `"-"` is quoted). Header: `x?` positional, `x?=` keyed. The encoder picks per column by comparing `missing·t(" -")` with `present·t(" x=")`. | §4.1: −7.6% / −6.1%; 5.4% / 5.7% smaller than Markdown | **implemented (`bpp2`)** |
| R2 | A **text block** for multi-line text columns: indented lines under the row that can be told apart from child rows | §4.1: a further −1.8% | **dropped** in bpp2 (794 vs 792 tokens; §4.1); **replaced in bpp4** by count-delimited, unindented `\|N` blocks (§4.4) |
| R3 | Add the primer only to large documents (e.g. `--primer auto` when the body exceeds 1000 tokens) | §4.2 | recommended; bpp4 already shortened the primer to the syntax used (40–108 tokens); pick a threshold from the comprehension results |
| R4 | Make the dictionary threshold tunable after the comprehension benchmark (`--refs min-gain=N`); if accuracy drops, use it only for long values that repeat a lot | §3 risk 1 | depends on the comprehension results |
| R5 | Flatten nested objects inside list items (`customer` in orders) into dotted columns (`customer.name`) in a row table, with child tables for sub-lists | orders was written as `- ` items | **implemented (`bpp3`)**: orders −34.7% / −35.9% (SPEC §4.3.1) |
| R6 | Markdown: `\|N` blocks, joined soft line breaks, a Markdown primer and a `bpp4 md` fallback to the source | §4.4: bpp3 lost to prose Markdown by ~3% | **implemented (`bpp4`)**: every document of §4.4 is smaller than its source |

R1 shipped as `bpp2`, R5 as `bpp3` and R6 as `bpp4`. The decoder still reads `bpp1`, `bpp2` and
`bpp3` files (SPEC §11).
