// Checks js/bpp.js against outputs produced by the Python package.
// Usage: node js/test/parity.mjs corpus.json   (corpus written by tests/test_js_parity.py)
// A case without json/md/csv is hand-written .bpp: only decoding is compared, and
// `back: null` means Python rejects it, so the JS decoder must throw a BppError too.
import { readFileSync } from 'node:fs';
import { encode, encodeMD, decode, parseJSON, stringifyJSON, loadCSV, BppError } from '../bpp.js';

const corpus = JSON.parse(readFileSync(process.argv[2], 'utf8'));
let failures = 0;
const fail = (i, what, got, want) => {
  if (failures++ < 5) console.error(`case ${i} ${what}\n--- js:\n${got}\n--- python:\n${want}`);
};
corpus.forEach((c, i) => {
  try {
    if ('md' in c || 'json' in c || 'csv' in c) {
      let out;
      if ('md' in c) out = encodeMD(c.md, c.opts);
      else out = encode('json' in c ? parseJSON(c.json) : loadCSV(c.csv), c.opts);
      if (out !== c.bpp) fail(i, 'encode differs', out, c.bpp);
    }
    if (c.back === null) {
      let back;
      try {
        back = stringifyJSON(decode(c.bpp), null);
      } catch (e) {
        if (e instanceof BppError) return;
        throw e;
      }
      fail(i, 'decode should fail', back, `BppError for:\n${c.bpp}`);
      return;
    }
    const back = stringifyJSON(decode(c.bpp), null);
    if (back !== c.back) fail(i, 'decode differs', back, c.back);
  } catch (e) {
    fail(i, `threw ${e.stack}`, '', c.bpp);
  }
});
console.log(`${corpus.length - failures}/${corpus.length} cases identical`);
process.exit(failures ? 1 : 0);
