# Token benchmark

Counters: o200k, claude2. Lower is better. Δ columns are relative to pretty-printed JSON.

## employees — `examples/employees.csv`

Düz tablo: 60 çalışan × 10 sütun

| format | o200k | claude2 | Δ o200k | Δ claude2 |
|---|---:|---:|---:|---:|
| JSON (indent 2) | 5538 | 5669 | +0.0% | +0.0% |
| JSON (minified) | 3562 | 3984 | -35.7% | -29.7% |
| YAML | 4388 | 4072 | -20.8% | -28.2% |
| CSV | 2165 | 2501 | -60.9% | -55.9% |
| TOON | 2277 | 2496 | -58.9% | -56.0% |
| bpp | **2042** | **2084** | -63.1% | -63.2% |
| bpp + primer | 2088 | 2133 | -62.3% | -62.4% |
| bpp --no-refs | 2042 | 2084 | -63.1% | -63.2% |

bpp vs best non-bpp format: o200k -5.7%, claude2 -16.5%

## config — `examples/config.yaml`

İç içe servis konfigürasyonu

| format | o200k | claude2 | Δ o200k | Δ claude2 |
|---|---:|---:|---:|---:|
| JSON (indent 2) | 601 | 611 | +0.0% | +0.0% |
| JSON (minified) | 365 | 393 | -39.3% | -35.7% |
| YAML | 443 | 417 | -26.3% | -31.8% |
| TOON | 399 | 389 | -33.6% | -36.3% |
| bpp | **323** | **332** | -46.3% | -45.7% |
| bpp + primer | 369 | 381 | -38.6% | -37.6% |
| bpp --no-refs | 323 | 332 | -46.3% | -45.7% |

bpp vs best non-bpp format: o200k -11.5%, claude2 -14.7%

## plan — `examples/plan.json`

Yapılandırılmış proje planı: 6 adım, 21 alt adım, bağımlılık/durum/öncelik

| format | o200k | claude2 | Δ o200k | Δ claude2 |
|---|---:|---:|---:|---:|
| JSON (indent 2) | 1609 | 1719 | +0.0% | +0.0% |
| JSON (minified) | 990 | 1078 | -38.5% | -37.3% |
| YAML | 1212 | 1248 | -24.7% | -27.4% |
| TOON | 1228 | 1257 | -23.7% | -26.9% |
| bpp | **634** | **727** | -60.6% | -57.7% |
| bpp + primer | 698 | 794 | -56.6% | -53.8% |
| bpp --no-refs | 634 | 727 | -60.6% | -57.7% |

bpp vs best non-bpp format: o200k -36.0%, claude2 -32.6%

## project_plan — `examples/project_plan.md`

Uzun Markdown proje planı: başlıklar, checkbox'lar, notlar

| format | o200k | claude2 | Δ o200k | Δ claude2 |
|---|---:|---:|---:|---:|
| Markdown (source) | 837 | 1078 | -42.1% | -35.9% |
| Markdown (normalized) | 829 | 1073 | -42.6% | -36.2% |
| JSON (indent 2) | 1445 | 1683 | +0.0% | +0.0% |
| JSON (minified) | 990 | 1240 | -31.5% | -26.3% |
| YAML | 1083 | 1259 | -25.1% | -25.2% |
| TOON | 1024 | 1215 | -29.1% | -27.8% |
| bpp | **758** | **996** | -47.5% | -40.8% |
| bpp + primer | 822 | 1062 | -43.1% | -36.9% |
| bpp --no-refs | 758 | 996 | -47.5% | -40.8% |

bpp vs best non-bpp format: o200k -8.6%, claude2 -7.2%

## orders — `examples/orders.json`

Karışık yapı: API yanıtı, 20 sipariş, iç içe nesneler ve serbest metin

| format | o200k | claude2 | Δ o200k | Δ claude2 |
|---|---:|---:|---:|---:|
| JSON (indent 2) | 3524 | 3615 | +0.0% | +0.0% |
| JSON (minified) | 2231 | 2455 | -36.7% | -32.1% |
| YAML | 2636 | 2526 | -25.2% | -30.1% |
| TOON | 2276 | 2342 | -35.4% | -35.2% |
| bpp | **1151** | **1178** | -67.3% | -67.4% |
| bpp + primer | 1221 | 1252 | -65.4% | -65.4% |
| bpp --no-refs | 1285 | 1362 | -63.5% | -62.3% |

bpp vs best non-bpp format: o200k -48.4%, claude2 -49.7%

## logs — `examples/logs.json`

Tekrarlanan uzun değerler: 80 log kaydı

| format | o200k | claude2 | Δ o200k | Δ claude2 |
|---|---:|---:|---:|---:|
| JSON (indent 2) | 5629 | 5563 | +0.0% | +0.0% |
| JSON (minified) | 4109 | 4199 | -27.0% | -24.5% |
| YAML | 4587 | 4456 | -18.5% | -19.9% |
| CSV | 3185 | 3249 | -43.4% | -41.6% |
| TOON | 3348 | 3332 | -40.5% | -40.1% |
| bpp | **1857** | **1800** | -67.0% | -67.6% |
| bpp + primer | 1903 | 1849 | -66.2% | -66.8% |
| bpp --no-refs | 2921 | 2952 | -48.1% | -46.9% |

bpp vs best non-bpp format: o200k -41.7%, claude2 -44.6%

## Summary (sum over all examples)

| format | o200k | claude2 | vs JSON o200k | vs JSON claude2 |
|---|---:|---:|---:|---:|
| JSON (indent 2) | 18346 | 18860 | +0.0% | +0.0% |
| JSON (minified) | 12247 | 13349 | -33.2% | -29.2% |
| YAML | 14349 | 13978 | -21.8% | -25.9% |
| TOON | 10552 | 11031 | -42.5% | -41.5% |
| bpp | 6765 | 7117 | -63.1% | -62.3% |
| bpp + primer | 7101 | 7471 | -61.3% | -60.4% |
