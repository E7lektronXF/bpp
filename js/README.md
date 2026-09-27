# bpp (JavaScript)

Dependency-free ES module port of the [bpp](https://github.com/E7lektronXF/bpp) encoder and
decoder. Its output is byte-identical to the Python package: `tests/test_js_parity.py` runs
thousands of generated documents through both and compares them.

```js
import { encode, decode, parseJSON, stringifyJSON } from './bpp.js';

const text = encode({ users: [{ id: 1, name: 'Ada' }, { id: 2, name: 'Linus' }] });
// bpp4
// users[2]{id name}
// 1 Ada
// 2 Linus

const data = decode(text);            // Maps and Num values (exact key order and numbers)
console.log(stringifyJSON(data));     // back to JSON text
```

* `encode(value, { primer, refs, keepOrder })` accepts plain objects or the exact model below.
* `decode(text)` returns `Map` objects and `Num` numbers, so key order (including keys such as
  `"10"`) and the difference between `1` and `1.0` survive. `toPlain(value)` converts to plain
  JS objects and numbers.
* `parseJSON(text)` / `stringifyJSON(value, indent)` read and write JSON in that exact model.
* `encodeMD(markdown, options)` encodes a Markdown document like `bpp.encode_md`: its tree, or
  `bpp4 md` followed by the source when that is shorter. `mdSource(text)` returns that source.
* `mdToTree(markdown)`, `loadCSV(text)`, `dumpCSV(rows)` and `estTokens(text)` match the Python
  functions of the same purpose.

This port powers the [browser playground](https://e7lektronxf.github.io/bpp/).
