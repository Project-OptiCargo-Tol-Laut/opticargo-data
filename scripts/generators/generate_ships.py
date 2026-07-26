"""
generate_ships.py
=================
Generate data kapal Tol Laut (KM Logistik Nusantara dll).
UUID5 deterministik berbasis nama kapal.
"""

import json
import uuid
import random
from datetime import datetime, timezone
from pathlib import Path

SHIPS_NAMESPACE = uuid.UUID("d0000000-0000-4000-8000-000000000000")
OPERATOR_ID = "87a9b0c1-d2e3-4f56-a7b8-c9d0e1f2a3b4" # dummy operator id

def make_ship_uuid(name: str) -> str:
    return str(uuid.uuid5(SHIPS_NAMESPACE, name.lower().strip()))

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

SHIP_NAMES = [
    "KM Logistik Nusantara 1",
    "KM Logistik Nusantara 2",
    "KM Logistik Nusantara 3",
    "KM Logistik Nusantara 4",
    "KM Logistik Nusantara 5",
    "KM Logistik Nusantara 6",
    "KM Kendhaga Nusantara 1",
    "KM Kendhaga Nusantara 2",
    "KM Kendhaga Nusantara 5",
    "KM Kendhaga Nusantara 7",
    "KM Kendhaga Nusantara 8",
    "KM Kendhaga Nusantara 11",
    "KM Sabuk Nusantara 39",
    "KM Sabuk Nusantara 68",
    "KM Sabuk Nusantara 105"
]

if __name__ == "__main__":
    random.seed(42) # agar kapasitas selalu sama tiap run
    result = []
    
    for i, name in enumerate(SHIP_NAMES):
        is_lognus = "Logistik" in name
        
        # Logistik Nusantara biasanya lebih besar, Kendhaga/Sabuk lebih kecil
        if is_lognus:
            gt = round(random.uniform(2500, 4500), 1)
            dwt = gt * 1.2
            cap = gt * 1.5
        else:
            gt = round(random.uniform(1000, 2000), 1)
            dwt = gt * 1.1
            cap = gt * 1.3
            
        result.append({
            "id": make_ship_uuid(name),
            "name": name,
            "imo_number": f"IMO{random.randint(9000000, 9999999)}",
            "ship_type": "General Cargo" if is_lognus else "Mixed Cargo",
            "gross_tonnage": gt,
            "deadweight_tonnage": round(dwt, 1),
            "cargo_capacity_m3": round(cap, 1),
            "operator_id": OPERATOR_ID,
            "flag": "Indonesia",
            "certifications": {
                "safety": "SOLAS",
                "pollution": "MARPOL"
            },
            "status": "active",
            "created_at": now
        })

    out = Path(__file__).parent.parent.parent / 'dataset' / "ships" / "ships.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[OK] Generated {len(result)} ships -> {out}")
