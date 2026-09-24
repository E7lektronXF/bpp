# .bpp design experiments

Counters: o200k, claude2. Δ% is relative to the first row.

### E1 Tabular data (60 rows x 10 cols): layout

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| JSON pretty | 5545 | 5675 | +0.0 | +0.0 |
| JSON minified | 3564 | 3986 | -35.7 | -29.8 |
| YAML | 4390 | 4075 | -20.8 | -28.2 |
| CSV | 2224 | 2500 | -59.9 | -55.9 |
| TOON comma | 2278 | 2497 | -58.9 | -56.0 |
| TOON tab | 2262 | 2498 | -59.2 | -56.0 |
| proto comma, no row indent | 2172 | 2511 | -60.8 | -55.8 |
| proto comma, row indent | 2232 | 2511 | -59.7 | -55.8 |
| proto tab | 2155 | 2511 | -61.1 | -55.8 |
| proto pipe | 2262 | 2511 | -59.2 | -55.8 |
| proto comma, no [N] | 2169 | 2509 | -60.9 | -55.8 |
| proto comma, null as empty | 2169 | 2505 | -60.9 | -55.9 |
| proto comma, bools as 1/0 | 2232 | 2511 | -59.7 | -55.8 |
| proto comma, bools as T/F | 2172 | 2511 | -60.8 | -55.8 |
| proto comma, header (a,b) | 2171 | 2511 | -60.8 | -55.8 |
| proto comma, header [a,b] | 2168 | 2509 | -60.9 | -55.8 |
| proto comma, quote all strings | 2200 | 2571 | -60.3 | -54.7 |

### E2 Nested config: indentation and key/value separator

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| JSON pretty | 601 | 610 | +0.0 | +0.0 |
| JSON minified | 365 | 393 | -39.3 | -35.6 |
| YAML | 443 | 417 | -26.3 | -31.6 |
| TOON | 399 | 389 | -33.6 | -36.2 |
| proto indent 2sp, ': ' | 391 | 386 | -34.9 | -36.7 |
| proto indent 1sp, ':' | 343 | 380 | -42.9 | -37.7 |
| proto indent 1sp, ': ' | 366 | 386 | -39.1 | -36.7 |
| proto indent tab, ':' | 361 | 426 | -39.9 | -30.2 |
| proto indent 1sp, '=' | 341 | 380 | -43.3 | -37.7 |
| proto indent 1sp, ' ' | 333 | 353 | -44.6 | -42.1 |
| proto dotted keys, ':' | 375 | 464 | -37.6 | -23.9 |
| proto dotted keys, '=' | 373 | 464 | -37.9 | -23.9 |
| proto inline list [a,b] | 338 | 377 | -43.8 | -38.2 |

### E3 Repeated long strings (80 log rows): dictionary

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| proto inline values | 3189 | 3253 | +0.0 | +0.0 |
| TOON | 3349 | 3333 | +5.0 | +2.5 |
| proto + dict (messages+services) | 1945 | 1948 | -39.0 | -40.1 |
| proto + dict (messages only) | 2445 | 2549 | -23.3 | -21.6 |

### E3b Short repeated strings (department/city): dictionary

Short values are usually 1-2 tokens, so a `*n` reference cannot beat them.

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| proto inline values | 2172 | 2511 | +0.0 | +0.0 |
| proto + dict | 2170 | 2468 | -0.1 | -1.7 |

### E4 Plan (6 steps, 21 sub-steps)

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| JSON pretty | 1609 | 1718 | +0.0 | +0.0 |
| JSON minified | 990 | 1078 | -38.5 | -37.3 |
| YAML | 1212 | 1248 | -24.7 | -27.4 |
| Markdown checklist | 828 | 894 | -48.5 | -48.0 |
| TOON (nested) | 1228 | 1257 | -23.7 | -26.8 |
| proto nested tree | 1130 | 1230 | -29.8 | -28.4 |
| flat table + parent col | 774 | 945 | -51.9 | -45.0 |
| flat table, hierarchical id | 722 | 889 | -55.1 | -48.3 |
| positional outline | 576 | 662 | -64.2 | -61.5 |

### E5 Mixed document (API response, 20 orders)

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| JSON pretty | 3524 | 3614 | +0.0 | +0.0 |
| JSON minified | 2231 | 2455 | -36.7 | -32.1 |
| YAML | 2636 | 2526 | -25.2 | -30.1 |
| TOON | 2276 | 2342 | -35.4 | -35.2 |
| proto | 2067 | 2316 | -41.3 | -35.9 |

### E6 Primer cost (absolute tokens)

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| none | 0 | 0 | - | - |
| 1 line | 38 | 39 | - | - |
| 3 lines | 96 | 103 | - | - |
| (ref) 'bpp1' header | 3 | 3 | - | - |

### E7 Unicode handling (Turkish text)

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| raw UTF-8 | 28 | 38 | +0.0 | +0.0 |
| JSON \u escapes | 73 | 85 | +160.7 | +123.7 |
| JSON quoted, raw | 32 | 45 | +14.3 | +18.4 |

### E8 Plan as tree-table (children indented under parent row)

Missing fields are empty cells. The `>steps` suffix names the child key.

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| positional outline (E4 best) | 576 | 662 | +0.0 | +0.0 |
| tree, comma, deps [a b] | 664 | 818 | +15.3 | +23.6 |
| tree, comma, deps [a;b] | 664 | 820 | +15.3 | +23.9 |
| tree, comma, deps a b | 652 | 797 | +13.2 | +20.4 |
| tree, tab, deps [a,b] | 681 | 833 | +18.2 | +25.8 |
| tree, ' | ', deps [a,b] | 796 | 889 | +38.2 | +34.3 |
| tree, '|', deps [a,b] | 729 | 821 | +26.6 | +24.0 |

### E8b Plan rows: positional variants

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| positional outline (sigils < @ #) | 576 | 662 | +0.0 | +0.0 |
| id status pri title k=v... | 605 | 696 | +5.0 | +5.1 |
| id status pri k=v... title | 606 | 696 | +5.2 | +5.1 |
| id status pri "title" k=v... | 654 | 749 | +13.5 | +13.1 |
| comma columns + k=v optional | 653 | 776 | +13.4 | +17.2 |

### E9 Separator `key:value` vs `key value` on other documents

Δ% only meaningful between rows of the same document.

| variant | o200k | claude2 | Δ% o200k | Δ% claude2 |
|---|---:|---:|---:|---:|
| config ':' | 343 | 380 | +0.0 | +0.0 |
| config ' ' | 333 | 353 | -2.9 | -7.1 |
| config ' ' + lists [a,b] | 328 | 350 | -4.4 | -7.9 |
| mixed ':' | 2067 | 2316 | +502.6 | +509.5 |
| mixed ' ' | 1947 | 2194 | +467.6 | +477.4 |
| plan-nested ':' | 1130 | 1230 | +229.4 | +223.7 |
| plan-nested ' ' | 1067 | 1133 | +211.1 | +198.2 |
