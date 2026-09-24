// Bridge to the reference TOON implementation (@toon-format/toon).
// Usage: node toon.mjs encode|decode [comma|tab|pipe] < input
import { encode, decode, DELIMITERS } from '@toon-format/toon';

const [mode = 'encode', delim = 'comma'] = process.argv.slice(2);
let input = '';
process.stdin.setEncoding('utf8');
for await (const chunk of process.stdin) input += chunk;
if (mode === 'encode') {
  process.stdout.write(encode(JSON.parse(input), { delimiter: DELIMITERS[delim] }));
} else {
  process.stdout.write(JSON.stringify(decode(input)));
}
