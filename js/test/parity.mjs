// Checks js/bpp.js against outputs produced by the Python package.
// Usage: node js/test/parity.mjs corpus.json   (corpus written by tests/test_js_parity.py)
import { readFileSync } from 'node:fs';
import { encode, decode, parseJSON, stringifyJSON, mdToTree, loadCSV } from '../bpp.js';

const corpus = JSON.parse(readFileSync(process.argv[2], 'utf8'));
let failures = 0;
const fail = (i, what, got, want) => {
  if (failures++ < 5) console.error(`case ${i} ${what}\n--- js:\n${got}\n--- python:\n${want}`);
};
corpus.forEach((c, i) => {
  try {
    let data;
    if ('json' in c) data = parseJSON(c.json);
    else if ('md' in c) data = mdToTree(c.md);
    else data = loadCSV(c.csv);
    const out = encode(data, c.opts);
    if (out !== c.bpp) fail(i, 'encode differs', out, c.bpp);
    const back = stringifyJSON(decode(c.bpp), null);
    if (back !== c.back) fail(i, 'decode differs', back, c.back);
  } catch (e) {
    fail(i, `threw ${e.stack}`, '', c.bpp);
  }
});
console.log(`${corpus.length - failures}/${corpus.length} cases identical`);
process.exit(failures ? 1 : 0);
