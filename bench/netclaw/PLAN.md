# NetClaw comprehension test: pre-registered plan

Status: **draft, open for input until 2026-10-04.** After that date this file is frozen (the
commit hash is posted in automateyournetwork/netclaw#274) and no result exists before the freeze.

## Question

Do models, especially small ones, read NetClaw's flat tool results less accurately when they are
encoded with bpp instead of the GCF generic profile?

This is the risk raised in netclaw#274: whitespace-delimited rows may be misread by smaller models.
The test is designed to find that failure if it exists, not to show a token saving.

## Decision rule (fixed before any run)

For each small model, compare bpp with GCF generic on the same questions (paired).

* If on **any** small model bpp scores **3 or more percentage points lower** than GCF generic
  **and** the difference is significant (exact McNemar test, p < 0.05), I close netclaw#278.
* Otherwise #278 is marked ready for review, with the full results linked.
* Results are published in both cases, including every per-dataset table.

## What is encoded

The exact output NetClaw would send, produced by NetClaw's own serializer at commit `988894b`
plus the #278 branch:

| Format | How it is produced |
|---|---|
| GCF generic | `serialize_response()` with `NETCLAW_GCF_MODE=generic`, `gcf-python==2.2.1` (NetClaw's pin) |
| bpp | same function with `NETCLAW_TABULAR_FORMAT=bpp`, `bpp-format==0.4.0` |
| JSON | NetClaw's JSON fallback (`json.dumps(data, indent=2)`), reference only |

The prompt labels the data as "Tool result" and does not name or explain the format, matching
how NetClaw passes tool output to a model. No primer is used for any format.

## Payloads

* Generators: the five in `benchmarks/gcf_vs_toon_benchmark.py` (BGP peers, route table,
  interfaces, OSPF neighbors, NSG rules), `random.seed(42)`.
* Sizes: 30 and 60 rows.
* Two variants of every payload:
  * **clean**: generator output unchanged;
  * **stress**: in 20% of rows, one string field is replaced with a value chosen to break
    whitespace-delimited parsing: multi-word text in a non-final column, an empty string,
    type-lookalikes (`"true"`, `"null"`, `"80"`, `"1e3"`), and text containing quotes or `#`.
    The replacement is seeded, so every format encodes identical data. Every encoding must
    round-trip to the source data or the payload is excluded for all formats.

5 datasets × 2 sizes × 2 variants = **20 payloads per format**.

## Questions

15 per payload, generated from the data with computed answers (300 per format per model):

| Type | Count | Example |
|---|---:|---|
| Direct lookup | 5 | "What is the `next_hop` of prefix 203.44.12.0/24?" |
| Reverse lookup | 3 | "Which rule has priority 370?" |
| Count | 3 | "How many peers are in state Established?" |
| Filtered aggregate | 2 | "Sum of `prefixes_received` over peers with remote_as 64600" |
| Position | 2 | "What is the `mtu` of the 52nd interface?" |

In stress payloads, at least 5 of the 15 questions target a stressed cell or a row next to one.
Grading reuses `bench/run_qa.py`: numeric comparison for numbers, set equality for lists,
normalized equality for text. `--dry-run` publishes every question and expected answer.

## Models

| Tier | Model | Where |
|---|---|---|
| Small | `llama3.2:3b` | local, Ollama, RTX 3070 8 GB |
| Small | `qwen3:8b`, thinking off | local, Ollama, RTX 3070 8 GB |
| Large | openai/gpt-oss-120b, reasoning low | free-tier API |

Temperature 0, context window 16k tokens (a prompt that would not fit is reported, never
silently truncated), one request per payload per format containing all 15 questions. Answers cut off
by the output limit count as wrong and are reported per format. Suggestions for more models or
stress cases are welcome in netclaw#274 until the freeze date.

## Out of scope

Token counts (already published), GCF's graph profile, session dedup and delta. #278 does not
touch them.
