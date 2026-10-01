# Scale comprehension benchmark

Does a model read bpp as well as JSON and GCF when the table has 100, 500 or 1000 rows, and
when it does not, why? Built after blackwell-systems' evaluation
([data and harness](https://github.com/blackwell-systems/gcf/tree/main/eval/bpp-comprehension),
[write-up](https://blog.blackwell-systems.com/posts/bpp-comprehension-tokens-you-cant-read/)) found a
54% mean error rate for bpp against 31% for GCF and 40% for JSON.

| file | what it does |
|---|---|
| `data.py` | the payloads: NetClaw's five network tables (seed 42) and blackwell's nested orders fixture |
| `questions.py` | 15 questions per payload with computed answers: 5 lookups (2+ on values bpp interns), 3 reverse lookups, 3 counts, 2 filtered aggregates, 2 positional lookups deep in the table |
| `taxonomy.py` | classifies every wrong answer: `pointer`, `column_shift`, `row_shift`, `count_off`, `refused_truncated`, `other` |
| `run_scale.py` | runs the benchmark (Ollama or a free OpenAI-compatible API) and writes `bench/results/scale/<model>.{jsonl,md}` |
| `blackwell.py` | ports blackwell's harness (19 questions, one request per question, temperature 0.2), checks our payloads against theirs, classifies the wrong answers in their published logs |
| `common.py` | formats, token counting with the model's own tokenizer, model calls |

```bash
pip install -e ".[dev]" gcf-python tokenizers
python bench/scale/run_scale.py --fetch-tokenizers        # Llama 3 / Qwen3 tokenizers (from npm)
python bench/scale/run_scale.py --dry-run                 # every question and answer, sizes, plan
python bench/scale/run_scale.py --model llama3.2:3b --num-ctx 65536
python bench/scale/run_scale.py --model qwen3:8b --num-ctx 40960
NVIDIA_API_KEY=nvapi-... python bench/scale/run_scale.py --provider nvidia \
    --model openai/gpt-oss-120b --num-ctx 131072

git clone --depth 1 https://github.com/blackwell-systems/gcf ../gcf
python bench/scale/blackwell.py --check ../gcf
python bench/scale/blackwell.py --analyze-logs ../gcf
python bench/scale/blackwell.py --model llama3.2:3b --num-ctx 65536 --orders 500
```

Formats: `json` (indent 2), `gcf` (`gcf-python` `encode_generic`), `bpp` (library default),
`bpp-refs`, `bpp-norefs`, or any encoder options as `bpp:keep_order=1,primer=1`. All bpp
variants are labelled "BPP" in the prompt, with no primer. Every bpp payload must round-trip
(values and types) or the run stops; a changed key order (a text column moved last, SPEC §4.3)
is reported by `--dry-run`.

A prompt that does not fit `--num-ctx` (counted with the model's tokenizer, plus the output
limit) is skipped and listed in the report; nothing is truncated. Ollama loads the model with
that context, so keep it fixed for a whole run. Answers are appended to the `.jsonl` file as they
arrive; the same command resumes after an interruption, and `--report` rebuilds the tables.
