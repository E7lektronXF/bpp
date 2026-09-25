// bpp.js: JavaScript port of the bpp encoder/decoder (format bpp2).
//
// Output is byte-identical to the Python package (checked by
// js/test/parity.mjs). Objects are Maps so key order survives integer-like
// keys, and numbers keep their JSON text in `Num` so 1 and 1.0 stay
// distinct and big integers stay exact. `parseJSON` / `stringifyJSON` read
// and write that model; plain JS objects and numbers are accepted by
// `encode` too.

export class Num {
  constructor(text) { this.text = text; }
  toString() { return this.text; }
  valueOf() { return Number(this.text); }
}

export class BppError extends Error {
  constructor(msg, line) {
    super(line ? `line ${line}: ${msg}` : msg);
    this.name = 'BppError';
    this.line = line ?? null;
  }
}

class Ref { constructor(idx) { this.idx = idx; } }

export const HEADER = 'bpp3';
export const PRIMER = "# bpp3: JSON as 'key value' lines, 1-space indent nests. k[N]{a b.c}: N rows, values " +
  "in column order (b.c = key c of b), last one = rest of line; x? optional (- = absent), " +
  'x?= as x=v; >k: indented rows are k. "..." = JSON string, *n = &n.';
export const PRIMER_LONG =
  "# bpp3 = JSON data. Lines are 'key value'; a bare 'key' opens a nested object (1-space indent). [a,b] = list.\n" +
  '# k[N]{a b.c d}: N rows, values space-separated in column order, b.c = key c inside object b, ' +
  'last column = rest of line;\n' +
  "# x? = optional, '-' if absent; x?= written as x=v; >kids: indented rows are kids, >kids{...} gives " +
  "them their own columns. {a,b}: comma rows. k[N]: N '- ' items. \"...\" = JSON string. *n = &n value.";
const CHILD_KEYS = ['steps', 'children', 'subtasks', 'tasks', 'items', 'nodes'];
const MIN_REF_LEN = 8;

// ------------------------------------------------------------ text helpers
// Python's notion of whitespace (str.isspace / re \s), which differs from JS.
const PYWS = '\\t\\n\\x0b\\x0c\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const STRIP_RE = new RegExp(`^[${PYWS}]+|[${PYWS}]+$`, 'gu');
const pyStrip = (s) => s.replace(STRIP_RE, '');
const CTRL = /[\x00-\x1f\x7f]/;
const NUM_RE = /^-?(?:0|[1-9]\p{Nd}*)(?:\.\p{Nd}+)?(?:[eE][+-]?\p{Nd}+)?$/u;
const BARE_KEY_RE = new RegExp(`[^${PYWS}"\\[\\]{}=,:?>\\x00-\\x1f\\x7f]+`, 'uy');
const BARE_SEG_RE = new RegExp(`[^${PYWS}"\\[\\]{}=,:?>.\\x00-\\x1f\\x7f]+`, 'uy');
const BARE_SEG_FULL = new RegExp(`^[^${PYWS}"\\[\\]{}=,:?>.\\x00-\\x1f\\x7f]+$`, 'u');
const BARE_KEY_FULL = new RegExp(`^[^${PYWS}"\\[\\]{}=,:?>\\x00-\\x1f\\x7f]+$`, 'u');
const KV_START = new RegExp(`^(?:[^${PYWS}"\\[\\]{}=,:?>]+|"(?:[^"\\\\]|\\\\[^\\n])*")=`, 'u');
const cpLen = (s) => { let n = 0; for (const _ of s) n++; return n; };
const SPECIAL = new Map([['null', null], ['true', true], ['false', false],
  ['NaN', new Num('NaN')], ['Infinity', new Num('Infinity')], ['-Infinity', new Num('-Infinity')]]);

/** Python's repr() of a float. */
export function pyFloatRepr(x) {
  if (Number.isNaN(x)) return 'NaN';
  if (x === Infinity) return 'Infinity';
  if (x === -Infinity) return '-Infinity';
  if (x === 0) return Object.is(x, -0) ? '-0.0' : '0.0';
  const [mant, expS] = x.toExponential().split('e');  // shortest round-trip digits
  const exp = parseInt(expS, 10);
  const neg = mant[0] === '-';
  const digits = mant.replace('-', '').replace('.', '');
  let out;
  if (exp < -4 || exp >= 16) {
    const ae = Math.abs(exp);
    out = digits[0] + (digits.length > 1 ? '.' + digits.slice(1) : '') +
      'e' + (exp < 0 ? '-' : '+') + (ae < 10 ? '0' + ae : String(ae));
  } else if (exp >= 0) {
    out = digits.length <= exp + 1
      ? digits + '0'.repeat(exp + 1 - digits.length) + '.0'
      : digits.slice(0, exp + 1) + '.' + digits.slice(exp + 1);
  } else {
    out = '0.' + '0'.repeat(-exp - 1) + digits;
  }
  return (neg ? '-' : '') + out;
}

/** A number token (JSON grammar) as Python would read and re-print it. */
export function numFromText(tok) {
  if (/[.eE]/.test(tok)) return new Num(pyFloatRepr(parseFloat(tok)));
  return new Num(BigInt(tok).toString());
}

function fmtNumber(v) {
  if (v instanceof Num) return v.text;
  if (typeof v === 'bigint') return v.toString();
  if (Number.isSafeInteger(v) && !Object.is(v, -0)) return String(v);
  return pyFloatRepr(v);
}

const isNumber = (v) => v instanceof Num || typeof v === 'number' || typeof v === 'bigint';
const isScalar = (v) => v === null || typeof v === 'string' || typeof v === 'boolean' ||
  isNumber(v) || v instanceof Ref;
const jstr = (s) => JSON.stringify(s);

function pyTruthy(v) {
  if (v === undefined || v === null || v === false) return false;
  if (v === true || v instanceof Ref) return true;
  if (typeof v === 'string' || Array.isArray(v)) return v.length > 0;
  if (v instanceof Map) return v.size > 0;
  if (v instanceof Num) return !['0', '0.0', '-0.0'].includes(v.text);
  if (typeof v === 'number') return v !== 0;
  if (typeof v === 'bigint') return v !== 0n;
  return true;
}

function needsQuote(s, ctx = 'value', strmode = false) {
  if (!s || pyStrip(s) !== s || CTRL.test(s) || '"[{*&#'.includes(s[0]) || SPECIAL.has(s)) return true;
  if (!strmode && NUM_RE.test(s)) return true;
  switch (ctx) {
    case 'cell': return s.includes(',');
    case 'list': return s.includes(',') || s.includes(']');
    case 'pos': return s.includes(' ') || s === '-';
    case 'item': return s.includes(' ') || s.includes('[') || s.includes('{');
    case 'last': return KV_START.test(s);
    default: return false;
  }
}

function fmtScalar(v, ctx = 'value', strmode = false) {
  if (v instanceof Ref) return `*${v.idx}`;
  if (v === null) return 'null';
  if (v === true) return 'true';
  if (v === false) return 'false';
  if (isNumber(v)) return fmtNumber(v);
  return needsQuote(v, ctx, strmode) ? jstr(v) : v;
}

function fmtKey(k) {
  return BARE_KEY_FULL.test(k) && !'-#&*'.includes(k[0]) ? k : jstr(k);
}

/** A key inside a table header, where '.' separates path segments. */
function fmtSeg(k) {
  return BARE_SEG_FULL.test(k) && !'-#&*'.includes(k[0]) ? k : jstr(k);
}

function fmtInline(v, ctx = 'value', strmode = false) {
  if (isScalar(v)) return fmtScalar(v, ctx, strmode);
  if (v instanceof Map) return v.size ? null : '{}';
  if (Array.isArray(v)) {
    if (v.every(isScalar)) return '[' + v.map((x) => fmtScalar(x, 'list', strmode)).join(',') + ']';
    return null;
  }
  throw new TypeError(`unsupported value ${v}`);
}

// --------------------------------------------------------------- estimator
const PIECE = new RegExp(
  ' ?[A-Za-z]+| ?(?:(?![A-Za-z])[\\p{L}\\p{Nl}\\p{No}])+| ?\\p{Nd}{1,3}|\\n| +' +
  `|[^\\p{L}\\p{N}_${PYWS}]{1,2}|[^\\n]`, 'gu');
const IS_ALPHA = /^\p{L}$/u;

/** Deterministic token estimate, identical to bpp/estimate.py. */
export function estTokens(text) {
  let n = 0;
  for (const m of text.matchAll(PIECE)) {
    const p = m[0];
    const ps = pyStrip(p);
    const chars = [...ps];
    const L = chars.length;
    const last = [...p].pop() || '';
    if (IS_ALPHA.test(last) && /^[\x00-\x7f]*$/.test(ps)) n += 1 + Math.floor(Math.max(0, L - 1) / 7);
    else if (L && IS_ALPHA.test(chars[0])) n += 1 + Math.floor(Math.max(0, L - 1) / 3);
    else n += 1;
  }
  return n;
}

// ----------------------------------------------------------------- encoder
function cmpCodepoints(a, b) {
  const A = [...a], B = [...b];
  for (let i = 0; i < Math.min(A.length, B.length); i++) {
    const d = A[i].codePointAt(0) - B[i].codePointAt(0);
    if (d) return d;
  }
  return A.length - B.length;
}

function walkStrings(v, cnt) {
  if (typeof v === 'string') cnt.set(v, (cnt.get(v) || 0) + 1);
  else if (v instanceof Map) for (const x of v.values()) walkStrings(x, cnt);
  else if (Array.isArray(v)) for (const x of v) walkStrings(x, cnt);
}

function extractRefs(data) {
  if (typeof data === 'string') return [data, []];
  const cnt = new Map();
  walkStrings(data, cnt);
  const cands = [];
  for (const [s, n] of cnt) {
    if (n < 2 || cpLen(s) < MIN_REF_LEN) continue;
    const cost = estTokens(' ' + fmtScalar(s));
    const gain = n * cost - estTokens(`&10 ${fmtScalar(s)}\n`) - n * estTokens(' *10');
    if (gain > 0) cands.push([gain, s]);
  }
  if (!cands.length) return [data, []];
  cands.sort((a, b) => (b[0] - a[0]) || cmpCodepoints(a[1], b[1]));
  const table = new Map(cands.map(([, s], i) => [s, new Ref(i)]));
  const sub = (v) => {
    if (typeof v === 'string') return table.get(v) ?? v;
    if (v instanceof Map) return new Map([...v].map(([k, x]) => [k, sub(x)]));
    if (Array.isArray(v)) return v.map(sub);
    return v;
  };
  return [sub(data), cands.map(([, s]) => s)];
}

function strCol(values) {
  const flat = [];
  for (const v of values) Array.isArray(v) ? flat.push(...v) : flat.push(v);
  const strs = flat.filter((v) => v !== null && !(v instanceof Ref));
  return strs.length > 0 && strs.every((v) => typeof v === 'string') && strs.some((v) => NUM_RE.test(v));
}

function treeNodes(arr, child) {
  const nodes = [];
  const stack = [...arr].reverse();
  while (stack.length) {
    const x = stack.pop();
    if (!(x instanceof Map) || !x.size) return null;
    nodes.push(x);
    if (x.has(child)) {
      const kids = x.get(child);
      if (!Array.isArray(kids)) return null;
      for (let i = kids.length - 1; i >= 0; i--) stack.push(kids[i]);
    }
  }
  return nodes;
}

// ------------------------------------------------------------ row tables
// Mirrors encoder._Spec / _plan in Python: columns are paths into the row
// (customer.name), and one child key may hold indented rows, with the same
// spec (a tree, >steps) or their own (>items{...}).
const pathKey = (p) => JSON.stringify(p);
const fmtPath = (p) => p.map(fmtSeg).join('.');
const cellable = (v) => isScalar(v) || (v instanceof Map && !v.size) || (Array.isArray(v) && v.every(isScalar));
const isRows = (v) => Array.isArray(v) && v.every((y) => y instanceof Map && y.size);

class Spec {
  constructor(order, required, keyed, smode, child, sub) {
    Object.assign(this, { order, required, keyed, smode, child, sub });
  }
  header() {
    const cols = this.order.map((p) => {
      const k = pathKey(p);
      return fmtPath(p) + (this.keyed.has(k) ? '?=' : this.required.has(k) ? '' : '?') +
        (this.smode.get(k) ? ':str' : '');
    }).join(' ');
    let out = '{' + cols + '}';
    if (this.child !== null) out += '>' + fmtSeg(this.child) + (this.sub ? this.sub.header() : '');
    return out;
  }
}

function flatNode(x, skip) {
  const out = [];
  const go = (path, v) => {
    if (v instanceof Map && v.size) {
      for (const [k, y] of v) if (!go([...path, k], y)) return false;
      return true;
    }
    if (!cellable(v)) return false;
    out.push([path, v]);
    return true;
  };
  for (const [k, v] of x) if (k !== skip && !go([k], v)) return null;
  return out;
}

function plan(arr, keepOrder) {
  if (!arr.length || !arr.every((x) => x instanceof Map && x.size)) return null;
  const seen = new Set();
  for (const ck of [...CHILD_KEYS, ...arr.flatMap((x) => [...x.keys()])]) {
    if (seen.has(ck)) continue;
    seen.add(ck);
    if (!arr.some((x) => pyTruthy(x.get(ck))) || !arr.every((x) => !x.has(ck) || isRows(x.get(ck)))) continue;
    const nodes = treeNodes(arr, ck);
    if (nodes !== null) {
      const spec = planCols(arr, nodes, ck, null, keepOrder);
      if (spec !== null) return spec;
    }
    const sub = plan(arr.flatMap((x) => (pyTruthy(x.get(ck)) ? x.get(ck) : [])), keepOrder);
    if (sub !== null) {
      const spec = planCols(arr, arr, ck, sub, keepOrder);
      if (spec !== null) return spec;
    }
  }
  return planCols(arr, arr, null, null, keepOrder);
}

function planCols(arr, nodes, child, sub, keepOrder) {
  const flats = [];
  for (const x of nodes) {
    const f = flatNode(x, child);
    if (f === null) return null;
    flats.push(new Map(f.map(([p, v]) => [pathKey(p), v])));
  }
  const cols = [];
  const seen = new Set();
  for (const x of nodes) {
    for (const [p] of flatNode(x, child)) {
      const k = pathKey(p);
      if (!seen.has(k)) { seen.add(k); cols.push(p); }
    }
  }
  for (const p of cols) {
    for (let i = 1; i < p.length; i++) if (seen.has(pathKey(p.slice(0, i)))) return null;
  }
  const required = cols.filter((p) => flats.every((f) => f.has(pathKey(p))));
  if (!required.length || (cols.length === 1 && child === null)) return null;
  const textScore = (p) => {
    const vals = flats.map((f) => f.get(pathKey(p)));
    if (!vals.every((v) => typeof v === 'string' || v instanceof Ref)) return [0, 0];
    return [1, vals.reduce((a, v) => a + (typeof v === 'string' ? v.split(' ').length : 1), 0)];
  };
  let rest;
  const lastCol = cols[cols.length - 1];
  if (keepOrder) {
    if (!required.includes(lastCol)) return null;
    rest = lastCol;
  } else {
    let best = null;
    for (const p of required) {
      const sc = textScore(p);
      if (best === null || sc[0] > best[0] || (sc[0] === best[0] && sc[1] > best[1])) { rest = p; best = sc; }
    }
  }
  const order = [...cols.filter((p) => p !== rest), rest];
  const smode = new Map(order.map((p) => {
    const k = pathKey(p);
    return [k, strCol(flats.filter((f) => f.has(k)).map((f) => f.get(k)))];
  }));
  const requiredSet = new Set(required.map(pathKey));
  const keyed = new Set();
  for (const p of order) {
    const k = pathKey(p);
    if (requiredSet.has(k)) continue;
    const present = flats.filter((f) => f.has(k)).length;
    if ((flats.length - present) * estTokens(' -') >= present * estTokens(` ${fmtPath(p)}=`)) keyed.add(k);
  }
  const spec = new Spec(order, requiredSet, keyed, smode, child, sub);
  if (keepOrder && !arr.every((x) => orderedEq(rebuild(x, spec), x))) return null;
  return spec;
}

function rebuild(x, spec) {
  const flat = new Map(flatNode(x, spec.child).map(([p, v]) => [pathKey(p), v]));
  const out = new Map();
  for (const p of spec.order) {
    const k = pathKey(p);
    if (!flat.has(k)) continue;
    let o = out;
    for (const seg of p.slice(0, -1)) {
      if (!o.has(seg)) o.set(seg, new Map());
      o = o.get(seg);
    }
    o.set(p[p.length - 1], flat.get(k));
  }
  if (spec.child !== null && x.has(spec.child)) {
    out.set(spec.child, x.get(spec.child).map((y) => rebuild(y, spec.sub || spec)));
  }
  return out;
}

function orderedEq(a, b) {
  if (a instanceof Map) {
    if (!(b instanceof Map) || a.size !== b.size) return false;
    const ka = [...a.keys()], kb = [...b.keys()];
    return ka.every((k, i) => k === kb[i]) && ka.every((k) => orderedEq(a.get(k), b.get(k)));
  }
  if (Array.isArray(a)) return Array.isArray(b) && a.length === b.length && a.every((y, i) => orderedEq(y, b[i]));
  return a === b;
}

function renderRows(arr, spec, depth, lines) {
  const last = spec.order[spec.order.length - 1];
  for (const x of arr) {
    const flat = new Map(flatNode(x, spec.child).map(([p, v]) => [pathKey(p), v]));
    const parts = [];
    for (const p of spec.order.slice(0, -1)) {
      const k = pathKey(p);
      if (!spec.keyed.has(k)) parts.push(flat.has(k) ? cell(flat.get(k), 'pos', spec.smode.get(k)) : '-');
    }
    for (const p of spec.order.slice(0, -1)) {
      const k = pathKey(p);
      if (spec.keyed.has(k) && flat.has(k)) parts.push(`${fmtPath(p)}=${cell(flat.get(k), 'pos', spec.smode.get(k))}`);
    }
    const kids = spec.child !== null ? x.get(spec.child) : undefined;
    if (spec.child !== null && x.has(spec.child) && !pyTruthy(kids)) parts.push(`${fmtSeg(spec.child)}=[]`);
    parts.push(cell(flat.get(pathKey(last)), 'last', spec.smode.get(pathKey(last))));
    lines.push(' '.repeat(depth) + parts.join(' '));
    if (pyTruthy(kids)) renderRows(kids, spec.sub || spec, depth + 1, lines);
  }
}

function cell(v, ctx, strmode) {
  if (Array.isArray(v)) return '[' + v.map((y) => fmtScalar(y, 'list', strmode)).join(',') + ']';
  if (v instanceof Map && !v.size) return '{}';
  return fmtScalar(v, ctx, strmode);
}

class Enc {
  constructor(keepOrder) { this.keepOrder = keepOrder; }

  root(v) {
    if (typeof v === 'string') return [jstr(v)];
    if (v instanceof Map && v.size) {
      const lines = [];
      for (const [k, x] of v) this.entry(fmtKey(k), x, 0, lines);
      return lines;
    }
    const inl = fmtInline(v);
    if (inl !== null) return [inl];
    return this.array('', v, 0);
  }

  entry(key, v, d, out) {
    const pad = ' '.repeat(d);
    const inl = fmtInline(v);
    if (inl !== null) out.push(`${pad}${key} ${inl}`);
    else if (v instanceof Map) {
      out.push(pad + key);
      for (const [k, x] of v) this.entry(fmtKey(k), x, d + 1, out);
    } else out.push(...this.array(key, v, d));
  }

  array(key, arr, d) {
    const cands = [];
    for (const c of [this.table(key, arr, d), this.outline(key, arr, d, true),
      this.keepOrder ? null : this.outline(key, arr, d, false)]) {
      if (c && !cands.some((x) => x.join('\n') === c.join('\n'))) cands.push(c);
    }
    if (!cands.length || arr.length <= 2) cands.push(this.items(key, arr, d));
    if (cands.length === 1) return cands[0];
    let best = cands[0], bestCost = estTokens(best.join('\n'));
    for (const c of cands.slice(1)) {
      const cost = estTokens(c.join('\n'));
      if (cost < bestCost) { best = c; bestCost = cost; }
    }
    return best;
  }

  table(key, arr, d) {
    if (!arr.every((x) => x instanceof Map && x.size)) return null;
    const cols = [...arr[0].keys()];
    for (const x of arr) {
      const ks = [...x.keys()];
      if (ks.length !== cols.length || ks.some((k, i) => k !== cols[i])) return null;
      if (![...x.values()].every(isScalar)) return null;
    }
    const smode = cols.map((c) => strCol(arr.map((x) => x.get(c))));
    const head = cols.map((c, i) => fmtSeg(c) + (smode[i] ? ':str' : '')).join(',');
    const pad = ' '.repeat(d);
    const lines = [`${pad}${key}[${arr.length}]{${head}}`];
    for (const x of arr) lines.push(pad + cols.map((c, i) => fmtScalar(x.get(c), 'cell', smode[i])).join(','));
    return lines;
  }

  outline(key, arr, d, keepOrder = false) {
    const spec = plan(arr, keepOrder);
    if (spec === null) return null;
    const lines = [`${' '.repeat(d)}${key}[${arr.length}]${spec.header()}`];
    renderRows(arr, spec, d, lines);
    return lines;
  }

  items(key, arr, d) {
    const pad = ' '.repeat(d);
    const lines = [`${pad}${key}[${arr.length}]`];
    for (const x of arr) {
      const inl = fmtInline(x, 'item');
      if (inl !== null) { lines.push(`${pad}- ${inl}`); continue; }
      let sub;
      if (x instanceof Map) {
        sub = [];
        let first = true;
        for (const [k, v] of x) {
          this.entry(fmtKey(k), v, d + 1, sub);
          if (first) { sub[0] = `${pad}- ` + sub[0].slice(d + 1); first = false; }
        }
      } else {
        sub = this.array('', x, d + 1);
        sub[0] = `${pad}- ` + sub[0].slice(d + 1);
      }
      lines.push(...sub);
    }
    return lines;
  }
}

/** Plain JS objects -> Maps (numbers stay numbers). Maps/Num pass through. */
export function toModel(v) {
  if (v === undefined) throw new TypeError('undefined is not JSON');
  if (v instanceof Map) return new Map([...v].map(([k, x]) => [String(k), toModel(x)]));
  if (Array.isArray(v)) return v.map(toModel);
  if (v !== null && typeof v === 'object' && !(v instanceof Num)) {
    return new Map(Object.entries(v).map(([k, x]) => [k, toModel(x)]));
  }
  return v;
}

/**
 * Encode a JSON-compatible value as .bpp text.
 * options: primer (false | true | 'long'), refs (default true), keepOrder.
 */
export function encode(data, { primer = false, refs = true, keepOrder = false } = {}) {
  let model = toModel(data);
  const out = [HEADER];
  if (primer) out.push(primer === 'long' ? PRIMER_LONG : PRIMER);
  let defs = [];
  if (refs) [model, defs] = extractRefs(model);
  defs.forEach((s, i) => out.push(`&${i} ${fmtScalar(s)}`));
  out.push(...new Enc(keepOrder).root(model));
  return out.join('\n') + '\n';
}

// ----------------------------------------------------------------- decoder
function parseBare(tok, strmode) {
  if (strmode) return tok === 'null' ? null : tok;
  if (SPECIAL.has(tok)) return SPECIAL.get(tok);
  if (NUM_RE.test(tok)) {
    try { return numFromText(tok); } catch { return tok; }
  }
  return tok;
}

class Cursor {
  constructor(text, refs, line) { this.s = text; this.i = 0; this.refs = refs; this.line = line; }
  err(msg) { throw new BppError(msg, this.line); }
  eof() { return this.i >= this.s.length; }
  peek() { return this.i < this.s.length ? this.s[this.i] : ''; }
  expect(ch) {
    if (this.peek() !== ch) this.err(`expected '${ch}' at column ${this.i + 1}`);
    this.i++;
  }
  jstring() {
    let j = this.i + 1;
    while (j < this.s.length && this.s[j] !== '"') j += this.s[j] === '\\' ? 2 : 1;
    if (j >= this.s.length) this.err('bad quoted string: Unterminated string');
    let v;
    try { v = JSON.parse(this.s.slice(this.i, j + 1)); } catch (e) { this.err(`bad quoted string: ${e.message}`); }
    this.i = j + 1;
    return v;
  }
  segment() {
    if (this.peek() === '"') return this.jstring();
    BARE_SEG_RE.lastIndex = this.i;
    const m = BARE_SEG_RE.exec(this.s);
    if (!m || '-#&*'.includes(this.s[this.i])) this.err('expected key');
    this.i += m[0].length;
    return m[0];
  }
  path(dotted) {
    if (!dotted) return [this.key()];
    const out = [this.segment()];
    while (this.peek() === '.') { this.i++; out.push(this.segment()); }
    return out;
  }
  key() {
    if (this.peek() === '"') return this.jstring();
    BARE_KEY_RE.lastIndex = this.i;
    const m = BARE_KEY_RE.exec(this.s);
    if (!m || '-#&*'.includes(this.s[this.i])) this.err('expected key');
    this.i += m[0].length;
    return m[0];
  }
  resolve(tok, strmode) {
    if (/^\*[0-9]+$/.test(tok)) {
      const idx = parseInt(tok.slice(1), 10);
      if (idx >= this.refs.length) this.err(`undefined reference ${tok}`);
      return this.refs[idx];
    }
    return parseBare(tok, strmode);
  }
  token(stops, strmode = false) {
    if (this.peek() === '"') return this.jstring();
    let j = this.i;
    while (j < this.s.length && !stops.includes(this.s[j])) j++;
    const tok = this.s.slice(this.i, j);
    if (!tok) this.err(`empty value at column ${this.i + 1}`);
    this.i = j;
    return this.resolve(tok, strmode);
  }
  inlineList(strmode = false) {
    this.expect('[');
    const out = [];
    if (this.peek() === ']') { this.i++; return out; }
    for (;;) {
      out.push(this.token(',]', strmode));
      const c = this.peek();
      this.i++;
      if (c === ']') return out;
      if (c !== ',') this.err('unterminated inline list');
    }
  }
  value(stops = '', strmode = false) {
    const c = this.peek();
    if (c === '[') return this.inlineList(strmode);
    if (this.s.startsWith('{}', this.i)) { this.i += 2; return new Map(); }
    if (!stops) {
      if (c === '"') return this.jstring();
      const tok = this.s.slice(this.i);
      if (!tok) this.err('missing value');
      this.i = this.s.length;
      return this.resolve(tok, strmode);
    }
    return this.token(stops, strmode);
  }
}

function header(text) {
  const m = /^\[([0-9]+)\]/.exec(text);
  if (!m || (m[0].length < text.length && text[m[0].length] !== '{')) return null;
  return [parseInt(m[1], 10), text.slice(m[0].length)];
}

function setPath(obj, path, v, line) {
  for (const k of path.slice(0, -1)) {
    if (!obj.has(k)) obj.set(k, new Map());
    const nxt = obj.get(k);
    if (!(nxt instanceof Map)) throw new BppError(`column '${path.join('.')}' conflicts with '${k}'`, line);
    obj = nxt;
  }
  obj.set(path[path.length - 1], v);
}

class DSpec {
  constructor(cols, delim, child, sub) {
    Object.assign(this, { cols, delim, child, sub });
    this.order = cols.map((c) => c.path);
    this.smode = new Map(cols.map((c) => [pathKey(c.path), c.smode]));
    this.optional = new Set(cols.filter((c) => c.opt).map((c) => pathKey(c.path)));
    this.keyed = new Set(cols.filter((c) => c.keyed).map((c) => pathKey(c.path)));
    this.positional = this.order.slice(0, -1).filter((p) => !this.keyed.has(pathKey(p)));
  }
}
const NO = Symbol('no');

class Dec {
  constructor(lines, version) { this.L = lines; this.version = version; this.i = 0; this.refs = []; }
  cur(ln, start = 0) { const c = new Cursor(ln.text, this.refs, ln.no); c.i = start; return c; }
  depthAt(i) { return i < this.L.length ? this.L[i].depth : -1; }

  document() {
    while (this.i < this.L.length && this.L[this.i].text.startsWith('&')) {
      const ln = this.L[this.i];
      const m = /^&([0-9]+) /.exec(ln.text);
      if (!m || ln.depth || parseInt(m[1], 10) !== this.refs.length) throw new BppError('bad dictionary definition', ln.no);
      const c = this.cur(ln, m[0].length);
      const v = c.value();
      if (typeof v !== 'string' || !c.eof()) throw new BppError('dictionary value must be a string', ln.no);
      this.refs.push(v);
      this.i++;
    }
    if (this.i >= this.L.length) throw new BppError('empty document');
    const first = this.L[this.i];
    if (first.depth) throw new BppError('unexpected indentation', first.no);
    if (this.i === this.L.length - 1) {
      const v = this.rootInline(first);
      if (v !== NO) { this.i++; return v; }
    }
    const v = first.text.startsWith('[') ? this.keyless(first, 0) : this.object(0);
    if (this.i < this.L.length) throw new BppError('unexpected content', this.L[this.i].no);
    return v;
  }

  rootInline(ln) {
    const c = this.cur(ln);
    const ch = c.peek();
    let v;
    try {
      if (ch === '"') v = c.jstring();
      else if ('[{*'.includes(ch) && ch) v = c.value(' ');
      else {
        v = c.token(' ');
        if (typeof v === 'string') return NO;
      }
    } catch (e) {
      if (e instanceof BppError) return NO;
      throw e;
    }
    return c.eof() ? v : NO;
  }

  object(d) {
    const obj = new Map();
    while (this.i < this.L.length) {
      const ln = this.L[this.i];
      if (ln.depth < d) break;
      if (ln.depth > d) throw new BppError('unexpected indentation', ln.no);
      if (ln.text.startsWith('- ') || ln.text === '-') throw new BppError('list item outside a list', ln.no);
      this.i++;
      const [k, v] = this.entry(ln, 0, d);
      obj.set(k, v);
    }
    return obj;
  }

  entry(ln, start, d) {
    const c = this.cur(ln, start);
    const key = c.key();
    const rest = ln.text.slice(c.i);
    if (rest === '') {
      if (this.depthAt(this.i) !== d + 1) throw new BppError(`key '${key}' has no value`, ln.no);
      return [key, this.object(d + 1)];
    }
    if (rest[0] === ' ') {
      c.i++;
      const v = c.value();
      if (!c.eof()) throw new BppError('trailing characters', ln.no);
      return [key, v];
    }
    if (rest[0] === '[') return [key, this.block(rest, ln, d)];
    throw new BppError(`expected space after key '${key}'`, ln.no);
  }

  keyless(ln, d) {
    const h = header(ln.text);
    if (h && (h[1] || this.itemsFollow(d))) { this.i++; return this.block(ln.text, ln, d); }
    const c = this.cur(ln);
    const v = c.inlineList();
    if (!c.eof()) throw new BppError('trailing characters', ln.no);
    this.i++;
    return v;
  }

  itemsFollow(d) {
    const j = this.i + 1;
    return j < this.L.length && this.L[j].depth === d && (this.L[j].text.startsWith('- ') || this.L[j].text === '-');
  }

  block(head, ln, d) {
    const h = header(head);
    if (!h) throw new BppError('bad array header', ln.no);
    const [n, rest] = h;
    if (!rest) return this.items(n, d, ln);
    const c = this.cur({ text: rest, no: ln.no });
    const spec = this.spec(c);
    if (!c.eof()) throw new BppError('bad array header', ln.no);
    if (spec.child === null && !spec.optional.size && (spec.cols.length === 1 || spec.delim === ',')) {
      return this.table(n, spec, d, ln);
    }
    return this.outline(n, spec, d, ln);
  }

  spec(c) {
    const dotted = this.version >= 3;
    c.expect('{');
    const cols = [];
    let delim = null;
    for (;;) {
      const path = c.path(dotted);
      let opt = false, keyed = false;
      if (c.peek() === '?') {
        opt = true;
        c.i++;
        if (this.version === 1) keyed = true;
        else if (c.peek() === '=') { keyed = true; c.i++; }
      }
      let smode = false;
      if (c.s.startsWith(':str', c.i)) { smode = true; c.i += 4; }
      cols.push({ path, opt, keyed, smode });
      const sep = c.peek();
      if (sep === '}') { c.i++; break; }
      if (delim === null) delim = sep;
      if (sep !== delim || !', '.includes(sep) || !sep) c.err('bad column list');
      c.i++;
    }
    let child = null, sub = null;
    if (c.peek() === '>') {
      c.i++;
      child = dotted ? c.segment() : c.key();
      if (dotted && c.peek() === '{') sub = this.spec(c);
    }
    return new DSpec(cols, delim || ',', child, sub);
  }

  table(n, spec, d, ln) {
    const rows = [];
    for (let r = 0; r < n; r++) {
      if (this.i >= this.L.length || this.L[this.i].depth !== d) throw new BppError(`expected ${n} table rows`, ln.no);
      const row = this.L[this.i++];
      const c = this.cur(row);
      const obj = new Map();
      spec.order.forEach((p, j) => {
        setPath(obj, p, c.token(',', spec.smode.get(pathKey(p))), row.no);
        if (j < spec.order.length - 1) c.expect(',');
      });
      if (!c.eof()) throw new BppError('too many cells', row.no);
      rows.push(obj);
    }
    return rows;
  }

  outline(n, spec, d, ln) {
    const dotted = this.version >= 3;
    const check = (sp) => {
      if (sp.optional.has(pathKey(sp.order[sp.order.length - 1]))) throw new BppError('last column must be required', ln.no);
      if (sp.sub) check(sp.sub);
    };
    check(spec);
    const cellOf = (c, sm) => (c.peek() === '[' ? c.inlineList(sm) : c.value(' ', sm));

    const row = (r, sp) => {
      const c = this.cur(r);
      const got = new Map();
      let childEmpty = false;
      for (const p of sp.positional) {
        const k = pathKey(p);
        if (sp.optional.has(k) && c.s.startsWith('- ', c.i)) { c.i += 2; continue; }
        got.set(k, cellOf(c, sp.smode.get(k)));
        c.expect(' ');
      }
      for (;;) {
        const save = c.i;
        if (c.peek() === '"' || !'[{*'.includes(c.peek())) {
          let p;
          try { p = c.path(dotted); } catch (e) {
            if (!(e instanceof BppError)) throw e;
            c.i = save;
            break;
          }
          if (c.peek() === '=') {
            const k = pathKey(p);
            if (sp.child !== null && k === pathKey([sp.child]) && !childEmpty) {
              c.i++;
              const v = c.value(' ');
              if (!Array.isArray(v) || v.length) throw new BppError('child key may only be [] inline', r.no);
              childEmpty = true;
              c.expect(' ');
              continue;
            }
            if (sp.keyed.has(k) && !got.has(k)) {
              c.i++;
              got.set(k, cellOf(c, sp.smode.get(k)));
              c.expect(' ');
              continue;
            }
          }
        }
        c.i = save;
        break;
      }
      const last = sp.order[sp.order.length - 1];
      got.set(pathKey(last), c.value('', sp.smode.get(pathKey(last))));
      if (!c.eof()) throw new BppError('trailing characters', r.no);
      const obj = new Map();
      for (const p of sp.order) {
        const k = pathKey(p);
        if (got.has(k)) setPath(obj, p, got.get(k), r.no);
      }
      if (childEmpty) obj.set(sp.child, []);
      return obj;
    };

    const rowsAt = (depth, count, sp) => {
      const out = [];
      while (this.i < this.L.length && (count === null || out.length < count)) {
        const r = this.L[this.i];
        if (r.depth < depth) break;
        if (r.depth > depth) throw new BppError('unexpected indentation', r.no);
        this.i++;
        const obj = row(r, sp);
        if (sp.child !== null && this.depthAt(this.i) === depth + 1) {
          if (obj.has(sp.child)) throw new BppError('child rows after child=[]', r.no);
          obj.set(sp.child, rowsAt(depth + 1, null, sp.sub || sp));
        }
        out.push(obj);
      }
      if (count !== null && out.length !== count) throw new BppError(`expected ${count} rows`, ln.no);
      return out;
    };
    return rowsAt(d, n, spec);
  }

  items(n, d, ln) {
    const out = [];
    for (let k = 0; k < n; k++) {
      if (this.i >= this.L.length || this.L[this.i].depth !== d) throw new BppError(`expected ${n} list items`, ln.no);
      const it = this.L[this.i];
      if (!it.text.startsWith('- ')) throw new BppError("expected '- ' list item", it.no);
      this.i++;
      out.push(this.item(it, d));
    }
    return out;
  }

  item(it, d) {
    const body = it.text.slice(2);
    const sub = { depth: d + 1, text: body, no: it.no };
    if (body.startsWith('[')) {
      const h = header(body);
      if (h && (h[1] || (this.i < this.L.length && this.L[this.i].depth === d + 1 &&
          this.L[this.i].text.startsWith('- ')))) return this.block(body, sub, d + 1);
      const c = this.cur(sub);
      const v = c.inlineList();
      if (!c.eof()) throw new BppError('trailing characters', it.no);
      return v;
    }
    if (body === '{}') return new Map();
    let key = null, rest = null;
    try {
      const c = this.cur(sub);
      key = c.key();
      rest = body.slice(c.i);
    } catch (e) {
      if (!(e instanceof BppError)) throw e;
    }
    if (key !== null) {
      const isEntry = rest.startsWith(' ') || rest.startsWith('[') ||
        (rest === '' && this.depthAt(this.i) === d + 2);
      if (isEntry) {
        const [k, v] = this.entry(sub, 0, d + 1);
        const obj = new Map([[k, v]]);
        for (const [kk, vv] of this.object(d + 1)) {
          if (obj.has(kk)) throw new BppError(`duplicate key '${kk}'`, it.no);
          obj.set(kk, vv);
        }
        return obj;
      }
    }
    const c = this.cur(sub);
    const v = c.peek() === '"' ? c.jstring() : c.value();
    if (!c.eof()) throw new BppError('trailing characters', it.no);
    return v;
  }
}

/** Decode .bpp text. Objects come back as Maps and numbers as Num. */
export function decode(text) {
  const lines = [];
  let version = 0;
  text.split('\n').forEach((raw, idx) => {
    let ln = raw.endsWith('\r') ? raw.slice(0, -1) : raw;
    const stripped = ln.replace(/^ +/, '');
    if (!stripped || stripped.startsWith('#')) return;
    if (!version) {
      if (!['bpp1', 'bpp2', 'bpp3'].includes(stripped)) throw new BppError("missing 'bpp3' header", idx + 1);
      version = Number(stripped[3]);
      return;
    }
    lines.push({ depth: ln.length - stripped.length, text: stripped, no: idx + 1 });
  });
  if (!version) throw new BppError("missing 'bpp3' header");
  return new Dec(lines, version).document();
}

// ---------------------------------------------------------------- JSON I/O
/** Strict JSON parser (plus NaN/Infinity, like Python) that keeps key order and number text. */
export function parseJSON(text) {
  let i = 0;
  const ws = () => { while (i < text.length && ' \t\n\r'.includes(text[i])) i++; };
  const fail = (msg) => { throw new SyntaxError(`${msg} at position ${i}`); };
  const value = () => {
    ws();
    const c = text[i];
    if (c === '{') {
      i++;
      const m = new Map();
      ws();
      if (text[i] === '}') { i++; return m; }
      for (;;) {
        ws();
        if (text[i] !== '"') fail('expected string key');
        const k = str();
        ws();
        if (text[i] !== ':') fail("expected ':'");
        i++;
        m.set(k, value());
        ws();
        if (text[i] === ',') { i++; continue; }
        if (text[i] === '}') { i++; return m; }
        fail("expected ',' or '}'");
      }
    }
    if (c === '[') {
      i++;
      const a = [];
      ws();
      if (text[i] === ']') { i++; return a; }
      for (;;) {
        a.push(value());
        ws();
        if (text[i] === ',') { i++; continue; }
        if (text[i] === ']') { i++; return a; }
        fail("expected ',' or ']'");
      }
    }
    if (c === '"') return str();
    for (const [lit, v] of [['true', true], ['false', false], ['null', null], ['NaN', new Num('NaN')],
      ['Infinity', new Num('Infinity')], ['-Infinity', new Num('-Infinity')]]) {
      if (text.startsWith(lit, i)) { i += lit.length; return v; }
    }
    const m = /-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/y;
    m.lastIndex = i;
    const r = m.exec(text);
    if (!r) fail('unexpected character');
    i += r[0].length;
    return numFromText(r[0]);
  };
  const str = () => {
    let j = i + 1;
    while (j < text.length && text[j] !== '"') j += text[j] === '\\' ? 2 : 1;
    if (j >= text.length) fail('unterminated string');
    const s = JSON.parse(text.slice(i, j + 1));
    i = j + 1;
    return s;
  };
  const v = value();
  ws();
  if (i < text.length) fail('extra data');
  return v;
}

/** JSON text in Python's json.dumps(ensure_ascii=False) layout (indent=2, or null = minified). */
export function stringifyJSON(v, indent = 2) {
  const nl = indent === null ? '' : '\n';
  const sepItem = ',';
  const sepKey = indent === null ? ':' : ': ';
  const go = (x, depth) => {
    if (x === null) return 'null';
    if (x === true) return 'true';
    if (x === false) return 'false';
    if (isNumber(x)) return fmtNumber(x);
    if (typeof x === 'string') return jstr(x);
    const pad = indent === null ? '' : ' '.repeat(indent * (depth + 1));
    const end = indent === null ? '' : ' '.repeat(indent * depth);
    if (Array.isArray(x)) {
      if (!x.length) return '[]';
      return '[' + nl + x.map((y) => pad + go(y, depth + 1)).join(sepItem + nl) + nl + end + ']';
    }
    const m = x instanceof Map ? x : toModel(x);
    if (!m.size) return '{}';
    return '{' + nl + [...m].map(([k, y]) => pad + jstr(k) + sepKey + go(y, depth + 1)).join(sepItem + nl) + nl + end + '}';
  };
  return go(v, 0);
}

/** Maps/Num -> plain JS values (for libraries such as js-yaml or TOON). */
export function toPlain(v) {
  if (v instanceof Num) return Number(v.text);
  if (v instanceof Map) return Object.fromEntries([...v].map(([k, x]) => [k, toPlain(x)]));
  if (Array.isArray(v)) return v.map(toPlain);
  return v;
}

// ------------------------------------------------------------------- CSV
function csvInfer(cell) {
  if (cell === '') return null;
  if (cell === 'true' || cell === 'false') return cell === 'true';
  if (NUM_RE.test(cell) && /^-?[0-9.eE+]+$/.test(cell)) {
    if (/^-?(?:0|[1-9][0-9]*)$/.test(cell)) return cell === '-0' ? cell : new Num(BigInt(cell).toString());
    const f = parseFloat(cell);
    if (Number.isFinite(f) && pyFloatRepr(f) === cell) return new Num(cell);
  }
  return cell;
}

function csvRows(text) {
  const rows = [];
  let row = [], field = '', i = 0, quoted = false, started = false, fieldQuoted = false;
  const endField = () => { row.push(field); field = ''; fieldQuoted = false; };
  const endRow = () => { if (started || row.length || field) { endField(); rows.push(row); } else rows.push([]); row = []; started = false; };
  while (i < text.length) {
    const c = text[i];
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i += 2; continue; }
        quoted = false; i++; continue;
      }
      field += c; i++; continue;
    }
    if (c === '"' && field === '' && !fieldQuoted) { quoted = true; fieldQuoted = true; started = true; i++; continue; }
    if (c === ',') { endField(); started = true; i++; continue; }
    if (c === '\r' || c === '\n') {
      endRow();
      i += c === '\r' && text[i + 1] === '\n' ? 2 : 1;
      continue;
    }
    field += c; started = true; i++;
  }
  if (quoted || started || row.length || field) endRow();
  return rows;
}

/** CSV text -> array of Maps, typing cells only when that is lossless. */
export function loadCSV(text) {
  if (text.includes('\x00')) throw new Error('CSV cells cannot contain NUL (\\x00) characters');
  const rows = csvRows(text);
  if (!rows.length) return [];
  const header = rows[0];
  if (new Set(header).size !== header.length) throw new Error('CSV header has duplicate column names');
  return rows.slice(1).map((r, k) => {
    if (r.length !== header.length) throw new Error(`CSV row ${k + 2} has ${r.length} cells, header has ${header.length}`);
    return new Map(header.map((h, j) => [h, csvInfer(r[j])]));
  });
}

/** Array of flat objects -> CSV text, or null if the data is not a flat table. */
export function dumpCSV(data) {
  if (!Array.isArray(data) || !data.every((r) => r instanceof Map)) return null;
  const cols = [];
  for (const r of data) for (const k of r.keys()) if (!cols.includes(k)) cols.push(k);
  const text = (v) => {
    if (v === undefined || v === null) return '';
    if (v === true) return 'true';
    if (v === false) return 'false';
    if (isNumber(v)) return fmtNumber(v);
    if (typeof v === 'string') return v;
    return null;
  };
  const q = (s) => (/[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s);
  const line = (cells) => (cells.length === 1 && cells[0] === '' ? '""' : cells.map(q).join(','));
  const out = [line(cols)];
  for (const r of data) {
    const cells = cols.map((c) => text(r.get(c)));
    if (cells.includes(null)) return null;
    out.push(line(cells));
  }
  return out.join('\n') + '\n';
}

// -------------------------------------------------------------- Markdown
const HEADING = new RegExp(`^(#{1,6})[${PYWS}]+([^\\n]*?)[${PYWS}]*#*[${PYWS}]*$`, 'u');
const ITEM = /^( *)([-*+]|\p{Nd}{1,9}[.)])(?: +([^\n]*))?$/u;
const BOX = /^\[([ xX/-])\] +/;
const FENCE = /^(```|~~~)/;
const STATUS = { ' ': 'todo', x: 'done', X: 'done', '/': 'doing', '-': 'cancelled' };

function expandTabs(s, size = 4) {
  let out = '', col = 0;
  for (const ch of s) {
    if (ch === '\t') { const n = size - (col % size); out += ' '.repeat(n); col += n; } else { out += ch; col++; }
  }
  return out;
}

function mdNode(text) {
  const m = BOX.exec(text);
  const node = new Map([['title', pyStrip(m ? text.slice(m[0].length) : text)]]);
  if (m) node.set('status', STATUS[m[1]]);
  return node;
}

/** Markdown plan -> tree {title?, note?, steps: [...]}, same as bpp.markdown.md_to_tree. */
export function mdToTree(text) {
  const notes = new Map();  // node -> lines
  const addNote = (node, line) => { if (!notes.has(node)) notes.set(node, []); notes.get(node).push(line); };
  const addStep = (parent, node) => { if (!parent.has('steps')) parent.set('steps', []); parent.get('steps').push(node); };
  const root = new Map([['steps', []]]);
  const headings = [[0, root]];
  let items = [];
  let fence = null;
  const h1Nodes = [];
  for (const raw of text.replace(/\r\n/g, '\n').split('\n')) {
    const line = expandTabs(raw);
    const stripped = line.replace(/^ +/, '');
    const indent = line.length - stripped.length;
    if (fence) {
      const [marker, node, col] = fence;
      addNote(node, stripped ? line.slice(Math.min(col, indent)) : '');
      if (stripped.startsWith(marker)) fence = null;
      continue;
    }
    if (!stripped) {
      const target = items.length ? items[items.length - 1][2] : headings[headings.length - 1][1];
      const nl = notes.get(target);
      if (nl && nl.length && nl[nl.length - 1] !== '') addNote(target, '');
      continue;
    }
    let m = indent < 4 ? HEADING.exec(stripped) : null;
    if (m) {
      const level = m[1].length;
      const node = mdNode(m[2]);
      if (level === 1) h1Nodes.push(node);
      while (headings[headings.length - 1][0] >= level) headings.pop();
      addStep(headings[headings.length - 1][1], node);
      headings.push([level, node]);
      items = [];
      continue;
    }
    m = ITEM.exec(line);
    if (m) {
      while (items.length && items[items.length - 1][0] >= indent) items.pop();
      const node = mdNode(m[3] ?? '');
      const parent = items.length ? items[items.length - 1][2] : headings[headings.length - 1][1];
      addStep(parent, node);
      items.push([indent, indent + m[2].length + 1, node]);
      continue;
    }
    while (items.length && indent < items[items.length - 1][1] && indent <= items[items.length - 1][0]) items.pop();
    const [node, col] = items.length ? [items[items.length - 1][2], items[items.length - 1][1]]
      : [headings[headings.length - 1][1], 0];
    const f = FENCE.exec(stripped);
    if (f) fence = [f[1], node, col];
    addNote(node, line.slice(Math.min(col, indent)));
  }
  const finish = (node) => {
    const note = notes.get(node);
    if (note) {
      while (note.length && note[note.length - 1] === '') note.pop();
      if (note.length) node.set('note', note.join('\n'));
    }
    for (const c of node.get('steps') || []) finish(c);
  };
  finish(root);
  const top = root.get('steps') || [];
  const doc = new Map();
  if (h1Nodes.length === 1 && !h1Nodes[0].has('status')) {
    const t = h1Nodes[0];
    doc.set('title', t.get('title'));
    const ns = [root.get('note'), t.get('note')].filter(Boolean);
    if (ns.length) doc.set('note', ns.join('\n\n'));
    doc.set('steps', [...top.filter((n) => n !== t), ...(t.get('steps') || [])]);
    return doc;
  }
  if (root.get('note')) doc.set('note', root.get('note'));
  doc.set('steps', top);
  return doc;
}
