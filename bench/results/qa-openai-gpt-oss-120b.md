# Comprehension benchmark (openai/gpt-oss-120b via groq, temperature 0, reasoning low, 2 repeat(s))

| format | employees | config | plan | project_plan | orders | logs | total | accuracy | mean input tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| JSON (indent 2) | 16/20 | 20/20 | 20/20 | 20/20 | 19/20 | 8/20 | 103/120 | 85.8% | 3372 |
| JSON (minified) | 16/20 | 20/20 | 20/20 | 20/20 | 18/20 | 8/20 | 102/120 | 85.0% | 2355 |
| YAML | 18/20 | 20/20 | 20/20 | 18/20 | 20/20 | 0/20 | 96/120 | 80.0% | 2703 |
| CSV | 18/20 | – | – | – | – | 3/20 | 21/40 | 52.5% | 2970 |
| bpp | 17/20 | 20/20 | 20/20 | 19/20 | 20/20 | 5/20 | 101/120 | 84.2% | 1439 |
| bpp + primer | 16/20 | 20/20 | 20/20 | 17/20 | 20/20 | 0/20 | 93/120 | 77.5% | 1497 |
| Markdown | – | – | – | 18/20 | – | – | 18/20 | 90.0% | 1292 |

Refusals: 0  ·  Cut off by the output limit: 7
