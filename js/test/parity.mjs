// Checks js/bpp.js against outputs produced by the Python package.
// Usage: node js/test/parity.mjs corpus.json   (corpus written by tests/test_js_parity.py)
import { readFileSync } from 'node:fs';
import { encode, encodeMD, decode, parseJSON, stringifyJSON, loadCSV } from '../bpp.js';

const corpus = JSON.parse(readFileSync(process.argv[2], 'utf8'));
let failures = 0;
const fail = (i, what, got, want) => {
  if (failures++ < 5) console.error(`case ${i} ${what}\n--- js:\n${got}\n--- python:\n${want}`);
};
corpus.forEach((c, i) => {
  try {
    let out;
    if ('md' in c) out = encodeMD(c.md, c.opts);
    else out = encode('json' in c ? parseJSON(c.json) : loadCSV(c.csv), c.opts);
    if (out !== c.bpp) fail(i, 'encode differs', out, c.bpp);
    const back = stringifyJSON(decode(c.bpp), null);
    if (back !== c.back) fail(i, 'decode differs', back, c.back);
  } catch (e) {
    fail(i, `threw ${e.stack}`, '', c.bpp);
  }
});
console.log(`${corpus.length - failures}/${corpus.length} cases identical`);
process.exit(failures ? 1 : 0);
