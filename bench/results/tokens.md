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
| bpp + primer | 2102 | 2148 | -62.0% | -62.1% |
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
| bpp + primer | 383 | 396 | -36.3% | -35.2% |
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
| bpp | **634** | **726** | -60.6% | -57.8% |
| bpp + primer | 694 | 790 | -56.9% | -54.0% |
| bpp --no-refs | 634 | 726 | -60.6% | -57.8% |

bpp vs best non-bpp format: o200k -36.0%, claude2 -32.7%

## project_plan — `examples/project_plan.md`

Uzun Markdown proje planı: başlıklar, checkbox'lar, notlar

| format | o200k | claude2 | Δ o200k | Δ claude2 |
|---|---:|---:|---:|---:|
| Markdown (source) | 837 | 1078 | -44.2% | -37.9% |
| Markdown (normalized) | 846 | 1083 | -43.6% | -37.7% |
| JSON (indent 2) | 1501 | 1737 | +0.0% | +0.0% |
| JSON (minified) | 1025 | 1265 | -31.7% | -27.2% |
| YAML | 1119 | 1288 | -25.4% | -25.8% |
| TOON | 1093 | 1273 | -27.2% | -26.7% |
| bpp | **857** | **1083** | -42.9% | -37.7% |
| bpp + primer | 917 | 1147 | -38.9% | -34.0% |
| bpp --no-refs | 857 | 1083 | -42.9% | -37.7% |

bpp vs best non-bpp format: o200k +2.4%, claude2 +0.5%

## orders — `examples/orders.json`

Karışık yapı: API yanıtı, 20 sipariş, iç içe nesneler ve serbest metin

| format | o200k | claude2 | Δ o200k | Δ claude2 |
|---|---:|---:|---:|---:|
| JSON (indent 2) | 3524 | 3615 | +0.0% | +0.0% |
| JSON (minified) | 2231 | 2455 | -36.7% | -32.1% |
| YAML | 2636 | 2526 | -25.2% | -30.1% |
| TOON | 2276 | 2342 | -35.4% | -35.2% |
| bpp | **1762** | **1839** | -50.0% | -49.1% |
| bpp + primer | 1822 | 1903 | -48.3% | -47.4% |
| bpp --no-refs | 1845 | 1983 | -47.6% | -45.1% |

bpp vs best non-bpp format: o200k -21.0%, claude2 -21.5%

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
| bpp + primer | 1917 | 1864 | -65.9% | -66.5% |
| bpp --no-refs | 2921 | 2952 | -48.1% | -46.9% |

bpp vs best non-bpp format: o200k -41.7%, claude2 -44.6%

## Summary (sum over all examples)

| format | o200k | claude2 | vs JSON o200k | vs JSON claude2 |
|---|---:|---:|---:|---:|
| JSON (indent 2) | 18402 | 18914 | +0.0% | +0.0% |
| JSON (minified) | 12282 | 13374 | -33.3% | -29.3% |
| YAML | 14385 | 14007 | -21.8% | -25.9% |
| TOON | 10621 | 11089 | -42.3% | -41.4% |
| bpp | 7475 | 7864 | -59.4% | -58.4% |
| bpp + primer | 7835 | 8248 | -57.4% | -56.4% |
