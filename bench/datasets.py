"""Deterministic sample datasets used by the design experiments and benchmarks."""

from __future__ import annotations

import random

FIRST = ["Ahmet", "Ayşe", "Mehmet", "Zeynep", "Mustafa", "Elif", "Can", "Şule",
         "İsmail", "Gül", "Oğuz", "Çiğdem", "Emre", "Özlem", "Burak", "Ümran",
         "John", "Maria", "Wei", "Priya"]
LAST = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Öztürk", "Aydın",
        "Arslan", "Doğan", "Smith", "Garcia", "Chen", "Patel"]
DEPTS = ["Engineering", "Sales", "Marketing", "Finance", "Human Resources", "Operations"]
CITIES = ["İstanbul", "Ankara", "İzmir", "Bursa", "Eskişehir", "Berlin", "London"]


def _ascii(s: str) -> str:
    return s.translate(str.maketrans("çğıİöşüÇĞÖŞÜ", "cgiIosuCGOSU")).lower()


def employees(n: int = 60, seed: int = 1) -> list[dict]:
    r = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        f, l = r.choice(FIRST), r.choice(LAST)
        rows.append({
            "id": i,
            "name": f"{f} {l}",
            "email": f"{_ascii(f)}.{_ascii(l)}@example.com",
            "department": r.choice(DEPTS),
            "city": r.choice(CITIES),
            "salary": r.randrange(30000, 150000, 500),
            "rating": round(r.uniform(1, 5), 1),
            "active": r.random() > 0.2,
            "manager_id": None if i <= 3 else r.randint(1, 3),
            "start_date": f"20{r.randint(10, 25)}-{r.randint(1, 12):02d}-{r.randint(1, 28):02d}",
        })
    return rows


def config() -> dict:
    return {
        "service": {"name": "order-api", "version": "2.4.1", "environment": "production",
                    "debug": False, "replicas": 3},
        "server": {"host": "0.0.0.0", "port": 8080, "timeouts": {"read_ms": 5000, "write_ms": 10000,
                   "idle_ms": 60000}, "tls": {"enabled": True, "cert_path": "/etc/ssl/certs/order-api.pem",
                   "key_path": "/etc/ssl/private/order-api.key", "min_version": "1.2"}},
        "database": {"primary": {"host": "db-primary.internal", "port": 5432, "name": "orders",
                     "user": "order_svc", "pool": {"min": 5, "max": 50, "idle_timeout_s": 300}},
                     "replicas": [{"host": "db-replica-1.internal", "port": 5432, "weight": 2},
                                  {"host": "db-replica-2.internal", "port": 5432, "weight": 1}]},
        "cache": {"backend": "redis", "url": "redis://cache.internal:6379/0", "ttl_s": 900,
                  "key_prefix": "order-api:"},
        "logging": {"level": "info", "format": "json", "sinks": ["stdout", "file"],
                    "file": {"path": "/var/log/order-api/app.log", "rotate_mb": 100, "keep": 7}},
        "features": {"new_checkout": True, "fraud_scoring": True, "gift_cards": False,
                     "beta_regions": ["TR", "DE", "NL"]},
        "rate_limits": [{"route": "/v1/orders", "method": "POST", "per_minute": 600},
                        {"route": "/v1/orders", "method": "GET", "per_minute": 3000},
                        {"route": "/v1/orders/{id}/cancel", "method": "POST", "per_minute": 60}],
        "owners": ["platform-team@example.com", "oncall-orders@example.com"],
    }


def plan() -> dict:
    """A project plan as a tree: steps with sub-steps, deps, status, priority."""
    def s(id, title, status="todo", pri="P2", deps=None, owner=None, steps=None, note=None):
        d = {"id": id, "title": title, "status": status, "priority": pri, "deps": deps or []}
        if owner:
            d["owner"] = owner
        if note:
            d["note"] = note
        if steps:
            d["steps"] = steps
        return d

    return {
        "title": "Mobil ödeme özelliğinin yayına alınması",
        "goal": "Q3 sonuna kadar iOS ve Android uygulamalarında kartla ve cüzdanla ödeme.",
        "steps": [
            s("1", "Gereksinim analizi", "done", "P1", owner="Ayşe", steps=[
                s("1.1", "Paydaş görüşmeleri", "done", "P1"),
                s("1.2", "Regülasyon incelemesi (BDDK, PCI-DSS)", "done", "P0"),
                s("1.3", "Kabul kriterlerinin yazılması", "done", "P1", ["1.1"]),
            ]),
            s("2", "Mimari tasarım", "done", "P1", ["1"], owner="Mehmet", steps=[
                s("2.1", "Ödeme sağlayıcısı seçimi", "done", "P0", note="Sağlayıcı A seçildi: komisyon %1.4"),
                s("2.2", "Tokenizasyon akışının tasarımı", "done", "P0", ["2.1"]),
                s("2.3", "Hata ve iade senaryoları", "done", "P1", ["2.2"]),
            ]),
            s("3", "Backend geliştirme", "in_progress", "P0", ["2"], owner="Can", steps=[
                s("3.1", "Ödeme servisi API'si", "done", "P0"),
                s("3.2", "Webhook işleyicisi", "in_progress", "P0", ["3.1"]),
                s("3.3", "İade (refund) uç noktası", "todo", "P1", ["3.1"]),
                s("3.4", "Mutabakat (reconciliation) işi", "todo", "P1", ["3.2"],
                  note="Gece 02:00'de çalışır; farklar Slack #odeme-alarm kanalına"),
            ]),
            s("4", "Mobil istemci", "in_progress", "P0", ["2"], owner="Zeynep", steps=[
                s("4.1", "iOS: Apple Pay entegrasyonu", "in_progress", "P0", ["3.1"]),
                s("4.2", "Android: Google Pay entegrasyonu", "todo", "P0", ["3.1"]),
                s("4.3", "Kart formu ve 3-D Secure ekranı", "in_progress", "P0", ["3.1"]),
                s("4.4", "Hata mesajlarının yerelleştirilmesi (tr, en, de)", "todo", "P2", ["4.3"]),
            ]),
            s("5", "Test", "todo", "P0", ["3", "4"], owner="Elif", steps=[
                s("5.1", "Birim testleri (%80 kapsama)", "in_progress", "P1"),
                s("5.2", "Sağlayıcı sandbox ile uçtan uca test", "todo", "P0", ["3.2", "4.3"]),
                s("5.3", "Yük testi: 200 işlem/sn", "todo", "P1", ["3.4"]),
                s("5.4", "Güvenlik testi (pentest)", "todo", "P0", ["5.2"], owner="Harici firma"),
            ]),
            s("6", "Yayın", "todo", "P0", ["5"], owner="Oğuz", steps=[
                s("6.1", "Kademeli açılış: %5 → %25 → %100", "todo", "P0", ["5.4"]),
                s("6.2", "İzleme panoları ve alarmlar", "todo", "P1", ["3.4"]),
                s("6.3", "Destek ekibi eğitimi", "todo", "P2"),
            ]),
        ],
    }


def mixed() -> dict:
    """An API-response-like document: metadata, nested objects, a table, prose."""
    r = random.Random(7)
    products = ["Kablosuz Kulaklık", "USB-C Şarj Aleti", "Mekanik Klavye", "27\" Monitör",
                "Laptop Standı", "Webcam 1080p"]
    orders = []
    for i in range(1, 21):
        items = [{"sku": f"SKU-{r.randint(100, 999)}", "name": r.choice(products),
                  "qty": r.randint(1, 3), "unit_price": round(r.uniform(99, 4999), 2)}
                 for _ in range(r.randint(1, 3))]
        orders.append({
            "order_id": f"ORD-2026-{i:05d}",
            "customer": {"name": f"{r.choice(FIRST)} {r.choice(LAST)}", "city": r.choice(CITIES)},
            "status": r.choice(["paid", "shipped", "delivered", "cancelled"]),
            "shipping_method": r.choice(["standard", "express"]),
            "items": items,
            "total": round(sum(x["qty"] * x["unit_price"] for x in items), 2),
            "note": r.choice([None, None, "Kapıya bırakın, zili çalmayın.",
                              "Fatura: şirket adına, \"ACME Ltd. Şti.\"",
                              "Line one\nLine two"]),
        })
    return {
        "request_id": "req_8f3a2c",
        "generated_at": "2026-09-24T10:15:00Z",
        "page": {"number": 1, "size": 20, "total_pages": 7},
        "summary": "Son 30 günün siparişleri. İptal oranı %4.2; en çok satan ürün kulaklık.",
        "orders": orders,
    }


def repetitive_logs(n: int = 80, seed: int = 3) -> list[dict]:
    """Rows with long, repeated string values - the case a dictionary helps."""
    r = random.Random(seed)
    msgs = [
        "Connection to upstream payment provider timed out after 30000ms",
        "User session expired; redirecting to the login page",
        "Rate limit exceeded for API key; request rejected with 429",
        "Database replica lag above threshold, falling back to primary",
    ]
    services = ["payments-gateway-eu-west-1", "auth-service-eu-west-1", "orders-api-eu-central-1"]
    return [{"ts": f"2026-09-24T10:{i // 60:02d}:{i % 60:02d}Z",
             "level": r.choice(["WARN", "ERROR", "INFO"]),
             "service": r.choice(services),
             "message": r.choice(msgs),
             "latency_ms": r.randint(5, 30000)} for i in range(n)]


ALL = {
    "employees": employees,
    "config": config,
    "plan": plan,
    "mixed": mixed,
    "logs": repetitive_logs,
}
