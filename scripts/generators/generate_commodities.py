"""
generate_commodities.py
=======================
Generate data komoditas Tol Laut yang realistis (muatan berangkat vs muatan balik).
Menggunakan UUID5 deterministik berbasis nama komoditas.
"""

import json
import uuid
from datetime import datetime, timezone
import os
from pathlib import Path

COMMODITIES_NAMESPACE = uuid.UUID("c0000000-0000-4000-8000-000000000000")

def make_commodity_uuid(name: str) -> str:
    return str(uuid.uuid5(COMMODITIES_NAMESPACE, name.lower().strip()))

now = os.getenv("OPTICARGO_DATASET_TIMESTAMP", "2026-07-26T00:00:00Z")

RAW_COMMODITIES = [
    # MUATAN BERANGKAT (Dari Hub ke Feeder)
    {"name": "Beras Medium", "category": "Kebutuhan Pokok", "hs_code": "1006.30.99", "perishable": False, "moisture": True, "certs": ["SNI", "Karantina Pertanian"]},
    {"name": "Minyak Goreng Kemasan", "category": "Kebutuhan Pokok", "hs_code": "1511.90.20", "perishable": False, "moisture": False, "certs": ["SNI", "BPOM"]},
    {"name": "Gula Pasir", "category": "Kebutuhan Pokok", "hs_code": "1701.99.10", "perishable": False, "moisture": True, "certs": ["SNI"]},
    {"name": "Tepung Terigu", "category": "Kebutuhan Pokok", "hs_code": "1101.00.10", "perishable": False, "moisture": True, "certs": ["SNI", "BPOM"]},
    {"name": "Semen Portland", "category": "Material Bangunan", "hs_code": "2523.29.90", "perishable": False, "moisture": True, "certs": ["SNI"]},
    {"name": "Besi Baja Beton", "category": "Material Bangunan", "hs_code": "7214.20.00", "perishable": False, "moisture": False, "certs": ["SNI"]},
    {"name": "Pupuk Urea", "category": "Pertanian", "hs_code": "3102.10.00", "perishable": False, "moisture": True, "certs": ["SNI"]},
    {"name": "Barang Elektronik", "category": "Barang Konsumsi", "hs_code": "8543.70.90", "perishable": False, "moisture": True, "certs": ["SNI"]},
    {"name": "Air Minum Dalam Kemasan", "category": "Kebutuhan Pokok", "hs_code": "2201.10.00", "perishable": False, "moisture": False, "certs": ["SNI", "BPOM"]},

    # MUATAN BALIK (Dari Feeder ke Hub)
    {"name": "Kopra", "category": "Hasil Perkebunan", "hs_code": "1203.00.00", "perishable": False, "moisture": True, "certs": ["Karantina Pertanian"]},
    {"name": "Cengkeh", "category": "Rempah", "hs_code": "0907.10.00", "perishable": False, "moisture": True, "certs": ["Karantina Pertanian"]},
    {"name": "Pala (Biji)", "category": "Rempah", "hs_code": "0908.11.00", "perishable": False, "moisture": True, "certs": ["Karantina Pertanian"]},
    {"name": "Rumput Laut Kering", "category": "Hasil Laut", "hs_code": "1212.21.00", "perishable": False, "moisture": True, "certs": ["Karantina Ikan"]},
    {"name": "Ikan Pelagis Beku", "category": "Hasil Laut", "hs_code": "0303.89.00", "perishable": True, "moisture": False, "certs": ["Karantina Ikan", "Sertifikat Kelayakan Pengolahan"]},
    {"name": "Tuna Beku", "category": "Hasil Laut", "hs_code": "0303.49.00", "perishable": True, "moisture": False, "certs": ["Karantina Ikan", "Catch Certificate"]},
    {"name": "Sapi Hidup", "category": "Ternak", "hs_code": "0102.29.10", "perishable": False, "moisture": False, "certs": ["Karantina Hewan", "Surat Keterangan Kesehatan Hewan"]},
    {"name": "Jagung Pipilan Kering", "category": "Hasil Pertanian", "hs_code": "1005.90.90", "perishable": False, "moisture": True, "certs": ["Karantina Pertanian"]},
    {"name": "Kayu Olahan", "category": "Kehutanan", "hs_code": "4407.29.90", "perishable": False, "moisture": False, "certs": ["SVLK", "Karantina Pertanian"]},
    {"name": "Kakao Biji", "category": "Hasil Perkebunan", "hs_code": "1801.00.00", "perishable": False, "moisture": True, "certs": ["Karantina Pertanian"]},
]

if __name__ == "__main__":
    result = []
    for c in RAW_COMMODITIES:
        result.append({
            "id": make_commodity_uuid(c["name"]),
            "name": c["name"],
            "category": c["category"],
            "hs_code": c["hs_code"],
            "special_requirements": {
                "moisture_control": c["moisture"],
                "temperature_control": c["perishable"]
            },
            "is_perishable": c["perishable"],
            "max_stack_height": 4 if c["perishable"] else 10,
            "certifications_required": c["certs"],
            "created_at": now,
            "is_synthetic": True,
            "provenance": "opticargo-data:synthetic:commodities"
        })

    out = Path(__file__).parent.parent.parent / 'dataset' / "commodities" / "commodities.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[OK] Generated {len(result)} commodities -> {out}")
