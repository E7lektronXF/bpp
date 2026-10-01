"""Questions with computed answers for the scale benchmark (15 per payload).

Every question records what it asks about (`row`, `col`) so a wrong answer can be
classified (taxonomy.py): a value from the neighbouring column, from a neighbouring
row, an unresolved dictionary pointer, ...

Mix per payload: 5 direct lookups (at least 2 on a value bpp's dictionary interns, when
the payload has any), 3 reverse lookups, 3 counts, 2 filtered aggregates, 2 positional
lookups deep in the table.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from data import ROWS_KEY

# Questions are about the rows under ROWS_KEY; a path is a tuple into a row,
# e.g. ("customer", "email") or ("items", 0, "sku").
Path = tuple


@dataclass
class Q:
    text: str
    expected: object
    kind: str            # run_qa.grade kind: num | str | list | bool
    qtype: str           # lookup | reverse | count | aggregate | position
    row: int | None = None
    col: Path | None = None
    tags: list = field(default_factory=list)  # e.g. "interned" (bpp default refs this value)


def flat(row: dict, prefix: Path = ()) -> dict:
    """{path: scalar or list of scalars} of one row; lists of objects are indexed."""
    out = {}
    for k, v in row.items():
        p = prefix + (k,)
        if isinstance(v, dict):
            out.update(flat(v, p))
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            for i, x in enumerate(v):
                out.update(flat(x, p + (i,)))
        else:
            out[p] = v
    return out


def ordinal(n: int) -> str:
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _at(n: int, frac: float) -> int:
    return min(n - 1, max(0, round(frac * (n - 1))))


def _unique_near(rows, start, col, step=1):
    """The first row from `start` whose `col` value is unique in the table."""
    cnt = Counter(_hashable(r[col]) for r in rows)
    n = len(rows)
    for d in range(n):
        i = (start + d * step) % n
        if cnt[_hashable(rows[i][col])] == 1:
            return i
    raise ValueError(f"no unique value in column {col}")


def _hashable(v):
    return tuple(v) if isinstance(v, list) else v


def _expect(v):
    """(expected, kind) for a cell value."""
    if isinstance(v, bool):
        return v, "bool"
    if isinstance(v, (int, float)):
        return v, "num"
    if isinstance(v, list):
        return (v[0], "str") if len(v) == 1 else (v, "list")
    return v, "str"


def _name(p: Path) -> str:
    return ".".join(str(x) for x in p)


# --------------------------------------------------------------- flat tables

# noun, key column, lookup columns, categorical columns, numeric columns
TABLES = {
    "bgp_peers": ("peer", "neighbor", ["state", "remote_as", "prefixes_received", "description",
                                       "address_family", "uptime_seconds"],
                  ["state"], ["prefixes_received", "remote_as", "uptime_seconds"]),
    "route_table": ("route", "prefix", ["next_hop", "as_path", "med", "origin", "communities",
                                        "local_pref"],
                    ["origin", "local_pref"], ["med", "weight"]),
    "interfaces": ("interface", "description", ["hostname", "ifname", "mtu", "ipAddressList",
                                                "vlan", "macaddr"],
                   ["state", "type"], ["vlan", "speed"]),
    "ospf_neighbors": ("neighbor", "neighbor_address", ["router_id", "state", "area", "interface",
                                                        "uptime_seconds", "dr"],
                       ["state", "area"], ["uptime_seconds", "dead_timer"]),
    "nsg_rules": ("rule", "name", ["priority", "access", "destination_port_range",
                                   "source_address_prefix", "description", "protocol"],
                  ["access", "protocol"], ["priority"]),
}


def table_questions(name: str, payload: dict, interned: set) -> list[Q]:
    noun, key, look, cats, nums = TABLES[name]
    rows = payload[ROWS_KEY[name]]
    n = len(rows)
    nums = [c for c in nums if c in rows[0]]
    qs: list[Q] = []
    # Lookup columns whose values bpp interns come first, so that (when there are any) at
    # least two lookups test the dictionary.
    ref_cols = [c for c in look if any(isinstance(r[c], str) and r[c] in interned for r in rows)]
    first = (ref_cols * 2)[:2]
    order = first + [c for c in look if c not in first]
    for j, frac in enumerate((0.1, 0.35, 0.6, 0.85, 1.0)):
        col = order[j % len(order)]
        i = _unique_near(rows, _at(n, frac), key, -1 if frac == 1.0 else 1)
        if col in ref_cols:  # land on a row whose value is interned
            i = next((x for x in range(i, i + n) if rows[x % n][col] in interned
                      and Counter(r[key] for r in rows)[rows[x % n][key]] == 1), i) % n
        exp, kind = _expect(rows[i][col])
        qs.append(Q(f"What is the {col} of the {noun} with {key} {rows[i][key]}?", exp, kind,
                    "lookup", i, (col,), ["interned"] if exp in interned else []))
    rev = [c for c in nums if 1 in Counter(r[c] for r in rows).values()]
    for frac, col in zip((0.2, 0.5, 0.95), (rev * 3)[:3]):
        i = _unique_near(rows, _at(n, frac), col)
        qs.append(Q(f"Which {noun} has {col} {rows[i][col]}? Answer with its {key}.", rows[i][key],
                    "str", "reverse", i, (key,), ["interned"] if rows[i][key] in interned else []))
    for j in range(2):
        cat = cats[j % len(cats)]
        vals = Counter(r[cat] for r in rows)
        ranked = sorted(vals, key=lambda x: (vals[x], str(x)))
        v = ranked[(len(ranked) // 2 + j // len(cats)) % len(ranked)]  # a mid-frequency value
        qs.append(Q(f"How many {noun}s have {cat} {v}?", vals[v], "num", "count"))
    col = nums[0]
    t = sorted(r[col] for r in rows)[int(n * 0.9)]
    qs.append(Q(f"How many {noun}s have {col} greater than {t}?", sum(r[col] > t for r in rows),
                "num", "count"))
    # filtered aggregates over a handful of rows
    cat, a = cats[0], nums[0]
    b = max(nums, key=lambda c: (len({r[c] for r in rows}), c != a))
    v = Counter(r[cat] for r in rows).most_common(1)[0][0]
    sel = sorted((r for r in rows if r[cat] == v), key=lambda r: r[b], reverse=True)
    k = min(5, len(sel))
    while k < len(sel) and sel[k][b] == sel[k - 1][b]:
        k += 1
    t = sel[k][b] if k < len(sel) else sel[-1][b] - 1
    qs.append(Q(f"What is the sum of {a} over the {noun}s with {cat} {v} and {b} greater than {t}?",
                sum(r[a] for r in sel[:k]), "num", "aggregate"))
    v2 = Counter(r[cat] for r in rows).most_common()[-1][0]
    qs.append(Q(f"What is the highest {a} among the {noun}s with {cat} {v2}?",
                max(r[a] for r in rows if r[cat] == v2), "num", "aggregate"))
    for frac, col in ((0.52, look[2]), (0.97, look[0])):
        i = _at(n, frac)
        exp, kind = _expect(rows[i][col])
        qs.append(Q(f"What is the {col} of the {ordinal(i + 1)} {noun} in the list?", exp, kind,
                    "position", i, (col,), ["interned"] if exp in interned else []))
    return qs


# -------------------------------------------------------------------- orders

def order_questions(payload: dict, interned: set) -> list[Q]:
    rows = payload["orders"]
    n = len(rows)

    def tag(v):
        return ["interned"] if isinstance(v, str) and v in interned else []

    def lookup(frac, path, text):
        i = _at(n, frac)
        o = rows[i]
        v = flat(o)[path]
        exp, kind = _expect(v)
        return Q(text.format(id=o["orderId"]), exp, kind, "lookup", i, path, tag(v))

    qs = [
        lookup(0.5, ("customer", "email"), "What is the customer email on order {id}?"),
        lookup(0.5, ("items", 0, "sku"), "What is the SKU of the first item in order {id}?"),
        lookup(0.99, ("items", 0, "sku"), "What is the SKU of the first item in order {id}?"),
        lookup(1.0, ("customer", "tier"), "What is the customer tier on order {id}?"),
        lookup(0.35, ("customer", "name"), "What is the customer name on order {id}?"),
    ]
    # Totals repeat (the fixture recycles customers and SKUs), so ask for the first match.
    for frac in (0.2, 0.6, 0.9):
        t = rows[_at(n, frac)]["total"]
        i = next(x for x, o in enumerate(rows) if o["total"] == t)
        qs.append(Q(f"What is the orderId of the first order in the list with a total of {t}?",
                    rows[i]["orderId"], "str", "reverse", i, ("orderId",)))
    qs += [
        Q("How many orders have status shipped?", sum(o["status"] == "shipped" for o in rows),
          "num", "count"),
        Q("How many orders have a customer with tier premium?",
          sum(o["customer"]["tier"] == "premium" for o in rows), "num", "count"),
        Q("How many orders have 3 or more line items?", sum(len(o["items"]) >= 3 for o in rows),
          "num", "count"),
    ]
    email = rows[_at(n, 0.4)]["customer"]["email"]
    mine = [o for o in rows if o["customer"]["email"] == email]
    qs.append(Q(f"What is the sum of the order totals of the customer with email {email}?",
                round(sum(o["total"] for o in mine), 2), "num", "aggregate", tags=tag(email)))
    sku = rows[_at(n, 0.3)]["items"][0]["sku"]
    qs.append(Q(f"What is the total quantity ordered of SKU {sku} across all orders?",
                sum(it["quantity"] for o in rows for it in o["items"] if it["sku"] == sku),
                "num", "aggregate", tags=tag(sku)))
    i = _at(n, 0.52)
    qs.append(Q(f"What is the status of the {ordinal(i + 1)} order in the list?", rows[i]["status"],
                "str", "position", i, ("status",)))
    i = next(x for x in range(_at(n, 0.97), n) if len(rows[x]["items"]) >= 2)
    v = rows[i]["items"][1]["sku"]
    qs.append(Q(f"What is the SKU of the second item of the {ordinal(i + 1)} order in the list?",
                v, "str", "position", i, ("items", 1, "sku"), tag(v)))
    return qs


def questions(name: str, payload: dict, interned: set) -> list[Q]:
    """interned: the strings bpp's default encoding puts in its &n dictionary."""
    if name == "orders":
        return order_questions(payload, interned)
    return table_questions(name, payload, interned)

