"""Write the example inputs in examples/ (deterministic) and their .bpp encodings.

    python bench/make_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bench"))

import datasets as ds  # noqa: E402
from bpp.encoder import encode_md  # noqa: E402
from bpp.formats import detect, dump_csv, dump_yaml, dumps, loads  # noqa: E402

EX = ROOT / "examples"

# name -> (file, description)
EXAMPLES = {
    "employees": ("employees.csv", "Düz tablo: 60 çalışan × 10 sütun"),
    "config": ("config.yaml", "İç içe servis konfigürasyonu"),
    "plan": ("plan.json", "Yapılandırılmış proje planı: 6 adım, 21 alt adım, bağımlılık/durum/öncelik"),
    "project_plan": ("project_plan.md", "Uzun Markdown proje planı: başlıklar, checkbox'lar, notlar"),
    "orders": ("orders.json", "Karışık yapı: API yanıtı, 20 sipariş, iç içe nesneler ve serbest metin"),
    "logs": ("logs.json", "Tekrarlanan uzun değerler: 80 log kaydı"),
}

HAND_WRITTEN = ("quickstart.json", "siparisler.json")  # inputs kept as they are


def write_inputs():
    (EX / "employees.csv").write_text(dump_csv(ds.employees()), encoding="utf-8")
    (EX / "config.yaml").write_text(dump_yaml(ds.config()), encoding="utf-8")
    (EX / "plan.json").write_text(json.dumps(ds.plan(), ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
    (EX / "orders.json").write_text(json.dumps(ds.mixed(), ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
    (EX / "logs.json").write_text(json.dumps(ds.repetitive_logs(), ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")


def load(name):
    path = EX / EXAMPLES[name][0]
    fmt = detect(path)
    return loads(path.read_text(encoding="utf-8"), fmt), fmt


def main():
    write_inputs()
    for name, (fname, _) in EXAMPLES.items():
        data, fmt = load(name)
        text = (encode_md((EX / fname).read_text(encoding="utf-8")) if fmt == "md"
                else dumps(data, "bpp", keep_order=fmt == "csv"))
        (EX / (Path(fname).stem + ".bpp")).write_text(text, encoding="utf-8")
    for fname in HAND_WRITTEN:  # the READMEs' quick-start samples
        data = loads((EX / fname).read_text(encoding="utf-8"), detect(fname))
        (EX / (Path(fname).stem + ".bpp")).write_text(dumps(data, "bpp"), encoding="utf-8")
    print("wrote", ", ".join(sorted(p.name for p in EX.iterdir())))


if __name__ == "__main__":
    main()
