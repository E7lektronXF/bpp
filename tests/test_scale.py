"""The scale benchmark's own logic: payloads, questions, error taxonomy (no model calls)."""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bench" / "scale"))

import blackwell  # noqa: E402
import data  # noqa: E402
from common import render, roundtrips  # noqa: E402
from questions import flat, questions  # noqa: E402
from taxonomy import classify, refs_of  # noqa: E402

from bpp.encoder import _extract_refs  # noqa: E402


def Q(expected, qtype="lookup", row=None, col=None):
    return SimpleNamespace(expected=expected, qtype=qtype, row=row, col=col)


ROWS = [flat(r) for r in [
    {"name": "Rule-001", "access": "Allow", "port": 80, "items": [{"sku": "A"}, {"sku": "B"}]},
    {"name": "Rule-002", "access": "Deny", "port": 443, "items": [{"sku": "C"}]},
    {"name": "Rule-003", "access": "Allow", "port": 22, "items": [{"sku": "D"}]},
]]
REFS = {"VirtualNetwork": 0, "AzureLoadBalancer": 3}


@pytest.mark.parametrize("answer, q, stop, refs, kind", [
    ("*3", Q("AzureLoadBalancer"), "stop", REFS, "pointer"),
    ("*12", Q("Deny", row=1, col=("access",)), "stop", REFS, "pointer"),
    ("3", Q("AzureLoadBalancer"), "stop", REFS, "pointer"),           # its own index
    ("0", Q("AzureLoadBalancer"), "stop", REFS, "pointer"),           # another definition's index
    ("*3", Q("AzureLoadBalancer"), "stop", {}, "other"),              # no dictionary in this format
    ("22", Q(443, row=1, col=("port",)), "stop", {"x" * 9: 22}, "row_shift"),  # numbers: not pointers
    ("*3*", Q("AzureLoadBalancer"), "stop", REFS, "pointer"),         # Markdown bold around it
    ("Allow", Q("Deny", row=1, col=("access",)), "stop", {}, "row_shift"),
    ("Rule-002", Q("Deny", row=1, col=("access",)), "stop", {}, "column_shift"),
    ("B", Q("A", row=0, col=("items", 0, "sku")), "stop", {}, "row_shift"),  # another child row
    ("C", Q("A", row=0, col=("items", 0, "sku")), "stop", {}, "row_shift"),  # next row's child
    ("41", Q(42, "count"), "stop", {}, "count_off"),
    ("I cannot tell", Q(42, "count"), "stop", {}, "refused_truncated"),
    ("Not found in the data", Q("Deny", row=1, col=("access",)), "stop", {}, "refused_truncated"),
    (None, Q("Deny", row=1, col=("access",)), "stop", {}, "refused_truncated"),
    ("Deny", Q("Deny", row=1, col=("access",)), "length", {}, "refused_truncated"),
    ("Maybe", Q("Deny", row=1, col=("access",)), "stop", {}, "other"),
])
def test_taxonomy(answer, q, stop, refs, kind):
    assert classify(answer, q, ROWS, refs, stop)[0] == kind


def test_refs_of_reads_definitions():
    d = {"a": ["customer.00001@example.com"] * 9, "b": ["1024-65535 y"] * 9, "c": ['say "hi"  #2'] * 9}
    assert refs_of(render("bpp-refs", d)) == {"customer.00001@example.com": 0, 'say "hi"  #2': 1,
                                              "1024-65535 y": 2}
    assert refs_of(render("bpp-norefs", d)) == {}


@pytest.mark.parametrize("name", list(data.GENERATORS))
@pytest.mark.parametrize("n", data.SIZES)
def test_payloads_round_trip_and_have_questions(name, n):
    p = data.payload(name, n)
    assert p == data.payload(name, n)  # deterministic
    for fmt in ("bpp", "bpp-refs", "bpp-norefs", "json"):
        assert roundtrips(fmt, render(fmt, p), p), fmt
    interned = set(_extract_refs(p)[1])
    qs = questions(name, p, interned)
    assert len(qs) >= 15
    assert len({q.text for q in qs}) == len(qs)
    assert all(q.expected is not None and q.kind in ("num", "str", "list", "bool") for q in qs)
    assert {q.qtype for q in qs} == {"lookup", "reverse", "count", "aggregate", "position"}
    if interned:
        assert sum("interned" in q.tags for q in qs) >= 2
    rows = p[data.ROWS_KEY[name]]
    for q in qs:
        if q.row is not None and q.qtype in ("lookup", "position"):
            v = flat(rows[q.row])[q.col]
            assert (v[0] if isinstance(v, list) and len(v) == 1 else v) == q.expected


def test_orders_fixture_matches_blackwell():
    # values from blackwell-systems/gcf eval/bpp-comprehension/encodings/adv-500-json.txt
    o = data.orders(500)["orders"]
    assert o[499] == {
        "customer": {"email": "customer.00124@example.com", "id": 125,
                     "name": "Customer Number 00124", "tier": "premium"},
        "items": [{"name": "Product Item 000122", "price": 132.54, "quantity": 1, "sku": "SKU-000122"},
                  {"name": "Product Item 000123", "price": 133.61, "quantity": 2, "sku": "SKU-000123"},
                  {"name": "Product Item 000124", "price": 134.68, "quantity": 3, "sku": "SKU-000124"},
                  {"name": "Product Item 000000", "price": 10, "quantity": 1, "sku": "SKU-000000"}],
        "orderId": "ORD-0500", "status": "cancelled", "subtotal": 813.8, "tax": 65.1, "total": 878.9}
    assert len(_extract_refs({"orders": o})[1]) == 375  # "375 defs at N=500" (their NOTES.md)


def test_blackwell_questions_match_their_logs():
    # expected values as printed in their logs (N=500 and N=1000)
    for n, want in ((500, {"order_count": "500", "count_shipped": "100", "count_premium_customers": "200",
                           "highest_total": "1006.62", "total_revenue_shipped": "32914.90",
                           "count_orders_with_3plus_items": "250", "sku_first_item_order3": "SKU-000006",
                           "email_mid_ORD-0250": "customer.00124@example.com",
                           "sku_deep_ORD-0500": "SKU-000122", "customer_tier_last_order": "premium",
                           "unique_statuses": "cancelled, delivered, pending, processing, shipped"}),
                    (1000, {"sku_mid_ORD-0500": "SKU-000247", "email_deep_ORD-1000": "customer.00249@example.com",
                            "tier_mid_ORD-0500": "premium"})):
        qs = {q.name: q for q in blackwell.build_questions(data.orders(n)["orders"])}
        assert len(qs) == 19
        for name, exp in want.items():
            assert qs[name].expected == exp, name


def test_blackwell_grading():
    assert blackwell.numeric_verify("32914.90", "$32,914.85")
    assert not blackwell.numeric_verify("32914.90", "32914.7")
    assert blackwell.string_verify("SKU-000122", "`sku-000122`")
    assert not blackwell.string_verify("SKU-000122", "*372")
    assert blackwell.statuses_verify("cancelled, delivered", "Cancelled,delivered")


def test_blackwell_log_line():
    line = ('    generic_comprehension_test.go:651:   FAIL sku_mid_ORD-0250          bpp      '
            '[got "*250"] expected="SKU-000122" got="*250"')
    m = blackwell._LOG.search(line)
    assert m.group(1, 2, 3, 5) == ("FAIL", "sku_mid_ORD-0250", "bpp", '"*250"')


def test_dry_run():
    out = subprocess.run([sys.executable, str(ROOT / "bench" / "scale" / "run_scale.py"), "--dry-run",
                          "--datasets", "nsg_rules", "--sizes", "100", "--formats", "json", "bpp-refs",
                          "bpp-norefs"], capture_output=True, text=True, check=True).stdout
    assert "What is the" in out and "requests x 1 repeat(s)" in out
