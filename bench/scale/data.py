"""Payloads for the scale benchmark: NetClaw's five network tables and nested orders.

The five network generators are copied unchanged (apart from taking an explicit
`random.Random`) from automateyournetwork/netclaw `benchmarks/gcf_vs_toon_benchmark.py`
(Apache-2.0, commit bcc3134). Every payload is generated with its own
`random.Random(42)`, so one payload never depends on which others were generated.

`orders` is a port of the adversarial fixture of blackwell-systems/gcf
`eval/bpp-comprehension`: each customer, email, SKU and product name repeats about
4 times, so bpp's dictionary interns all of them. `orders(500)` and `orders(1000)` equal
the published `encodings/adv-{500,1000}-json.txt` (checked by `blackwell.py --check`).
"""

from __future__ import annotations

import random
import string

SEED = 42
SIZES = (100, 500, 1000)


def bgp_peers(n: int, rnd: random.Random) -> dict:
    states = ["Established", "Active", "Idle", "Connect", "OpenSent", "OpenConfirm"]
    peers = []
    for i in range(n):
        peers.append({
            "neighbor": f"10.{rnd.randint(0,255)}.{rnd.randint(0,255)}.{rnd.randint(1,254)}",
            "remote_as": rnd.randint(64512, 65534),
            "local_as": 65000,
            "state": rnd.choice(states),
            "uptime_seconds": rnd.randint(0, 864000),
            "prefixes_received": rnd.randint(0, 50000),
            "prefixes_sent": rnd.randint(0, 10000),
            "messages_received": rnd.randint(100, 1000000),
            "messages_sent": rnd.randint(100, 1000000),
            "description": f"Transit-Peer-{i+1}",
            "address_family": "ipv4-unicast",
            "hold_time": 180,
            "keepalive_interval": 60,
        })
    return {"peers": peers, "count": n}


def route_table(n: int, rnd: random.Random) -> dict:
    origins = ["igp", "egp", "incomplete"]
    routes = []
    for i in range(n):
        prefix = f"{rnd.randint(1,223)}.{rnd.randint(0,255)}.{rnd.randint(0,255)}.0/24"
        routes.append({
            "prefix": prefix,
            "next_hop": f"10.{rnd.randint(0,255)}.{rnd.randint(0,255)}.{rnd.randint(1,254)}",
            "as_path": " ".join(str(rnd.randint(1, 65534)) for _ in range(rnd.randint(1, 6))),
            "local_pref": rnd.choice([100, 150, 200]),
            "med": rnd.randint(0, 1000),
            "origin": rnd.choice(origins),
            "communities": f"{rnd.randint(1,65534)}:{rnd.randint(1,65534)}",
            "valid": True,
            "best": rnd.random() > 0.3,
            "weight": rnd.choice([0, 100, 32768]),
        })
    return {"routes": routes, "count": n}


def interfaces(n: int, rnd: random.Random) -> dict:
    types = ["ethernet", "loopback", "vlan", "port-channel", "management"]
    states = ["up", "down", "admin-down"]
    out = []
    for i in range(n):
        itype = rnd.choice(types)
        out.append({
            "hostname": f"switch-{rnd.randint(1,20):02d}",
            "ifname": f"{'Ethernet' if itype == 'ethernet' else itype.capitalize()}{rnd.randint(1,96)}",
            "state": rnd.choice(states),
            "adminState": rnd.choice(["up", "down"]),
            "type": itype,
            "mtu": rnd.choice([1500, 9000, 9214]),
            "speed": rnd.choice([1000, 10000, 25000, 40000, 100000]),
            "ipAddressList": [f"10.{rnd.randint(0,255)}.{rnd.randint(0,255)}.{rnd.randint(1,254)}/30"],
            "macaddr": ":".join(f"{rnd.randint(0,255):02x}" for _ in range(6)),
            "vlan": rnd.randint(1, 4094),
            "master": "",
            "description": f"Link-to-{''.join(rnd.choices(string.ascii_lowercase, k=6))}",
        })
    return {"interfaces": out, "count": n}


def ospf_neighbors(n: int, rnd: random.Random) -> dict:
    states = ["Full", "2-Way", "ExStart", "Exchange", "Loading", "Init", "Down"]
    neighbors = []
    for i in range(n):
        neighbors.append({
            "router_id": f"10.0.{rnd.randint(0,255)}.{rnd.randint(1,254)}",
            "neighbor_address": f"10.{rnd.randint(0,255)}.{rnd.randint(0,255)}.{rnd.randint(1,254)}",
            "state": rnd.choice(states[:3]),
            "area": f"0.0.0.{rnd.choice([0, 1, 2, 10, 20])}",
            "interface": f"Ethernet{rnd.randint(1,48)}",
            "priority": rnd.choice([0, 1, 128]),
            "dead_timer": rnd.randint(30, 40),
            "uptime_seconds": rnd.randint(0, 864000),
            "dr": f"10.0.{rnd.randint(0,255)}.{rnd.randint(1,254)}",
            "bdr": f"10.0.{rnd.randint(0,255)}.{rnd.randint(1,254)}",
            "options": "0x12",
        })
    return {"neighbors": neighbors, "count": n}


def nsg_rules(n: int, rnd: random.Random) -> dict:
    actions = ["Allow", "Deny"]
    directions = ["Inbound", "Outbound"]
    protocols = ["TCP", "UDP", "ICMP", "*"]
    rules = []
    for i in range(n):
        rules.append({
            "name": f"Rule-{i+1:03d}",
            "priority": 100 + i * 10,
            "direction": rnd.choice(directions),
            "access": rnd.choice(actions),
            "protocol": rnd.choice(protocols),
            "source_address_prefix": rnd.choice(["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "*",
                                                 "VirtualNetwork"]),
            "destination_address_prefix": rnd.choice(["10.0.0.0/8", "*", "AzureLoadBalancer", "Internet"]),
            "source_port_range": rnd.choice(["*", "1024-65535", "80", "443"]),
            "destination_port_range": rnd.choice(["80", "443", "22", "3389", "1433", "*"]),
            "description": f"{'Allow' if rnd.random() > 0.3 else 'Deny'} traffic for service-{i+1}",
            "provisioning_state": "Succeeded",
        })
    return {"nsg_name": "prod-web-nsg", "resource_group": "rg-networking", "rules": rules, "count": n}


def _num(x: float):
    """A float the way Go's encoding/json writes it (10.0 -> 10)."""
    x = round(x, 2)
    return int(x) if x == int(x) else x


def orders(n: int, rnd: random.Random | None = None) -> dict:
    """blackwell's adversarial fixture: a pool of n/4 customers and SKUs, keys sorted."""
    pool = max(1, n // 4)
    tiers = ["standard", "premium", "enterprise", "standard", "premium"]
    statuses = ["shipped", "pending", "processing", "delivered", "cancelled"]
    out = []
    for i in range(n):
        c = i % pool
        items, subtotal = [], 0.0
        for j in range(i % 4 + 1):
            k = (i * 3 + j) % pool
            price, qty = round(10 + k + (k * 7 % 100) / 100, 2), j % 3 + 1
            items.append({"name": f"Product Item {k:06d}", "price": _num(price), "quantity": qty,
                          "sku": f"SKU-{k:06d}"})
            subtotal += price * qty
        subtotal = round(subtotal, 2)
        tax = round(subtotal * 0.08, 2)
        out.append({
            "customer": {"email": f"customer.{c:05d}@example.com", "id": c + 1,
                         "name": f"Customer Number {c:05d}", "tier": tiers[c % len(tiers)]},
            "items": items,
            "orderId": f"ORD-{i + 1:04d}",
            "status": statuses[i % len(statuses)],
            "subtotal": _num(subtotal),
            "tax": _num(tax),
            "total": _num(subtotal + tax),
        })
    return {"orders": out}


GENERATORS = {
    "bgp_peers": bgp_peers,
    "route_table": route_table,
    "interfaces": interfaces,
    "ospf_neighbors": ospf_neighbors,
    "nsg_rules": nsg_rules,
    "orders": orders,
}

# The key that holds the rows of each payload.
ROWS_KEY = {"bgp_peers": "peers", "route_table": "routes", "interfaces": "interfaces",
            "ospf_neighbors": "neighbors", "nsg_rules": "rules", "orders": "orders"}


def payload(name: str, n: int) -> dict:
    return GENERATORS[name](n, random.Random(SEED))
