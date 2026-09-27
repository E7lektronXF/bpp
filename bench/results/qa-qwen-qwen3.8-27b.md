# Comprehension benchmark (qwen/qwen3.8-27b via groq, temperature 0, reasoning none, 1 repeat(s))

| format | employees | config | plan | project_plan | orders | logs | total | accuracy | mean input tokens | cut off |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| JSON (indent 2) | 7/10 | 10/10 | 9/10 | 9/10 | 9/10 | 0/10 | 44/60 | 73.3% | 3360 | 1 |
| JSON (minified) | 7/10 | 10/10 | 9/10 | 9/10 | 9/10 | 4/10 | 48/60 | 80.0% | 2618 | 0 |
| YAML | 7/10 | 10/10 | 10/10 | 9/10 | 9/10 | 4/10 | 49/60 | 81.7% | 3028 | 0 |
| CSV | 7/10 | – | – | – | – | 4/10 | 11/20 | 55.0% | 3637 | 0 |
| bpp | 7/10 | 10/10 | 10/10 | 8/10 | 9/10 | 4/10 | 48/60 | 80.0% | 1694 | 0 |
| bpp + primer | 7/10 | 10/10 | 10/10 | 9/10 | 9/10 | 4/10 | 49/60 | 81.7% | 1752 | 0 |
| Markdown | – | – | – | 9/10 | – | – | 9/10 | 90.0% | 1285 | 0 |

Refusals: 0  ·  Cut off or rejected as too large: 1 requests (their unanswered questions count as wrong; 'cut off' is per format)
