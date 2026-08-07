"""
generate_suppliers.py
=====================
Generate data supplier fiktif untuk demo OptiCargo.
- Membaca ports.json untuk foreign key pelabuhan yang valid
- Membaca commodities.json untuk foreign key komoditas yang valid
- Mendistribusikan supplier sesuai logika (Hub = barang pabrikan/kebutuhan pokok, Feeder = komoditas mentah/hasil alam)
"""

import json
import uuid
import random
from datetime import datetime, timezone
import os
from pathlib import Path

SUPPLIERS_NAMESPACE = uuid.UUID("8d4d9f20-c2e4-4b6e-9b3b-e6ad93f1ed51")

def make_supplier_uuid(name: str, port_id: str, sequence: int) -> str:
    stable_key = f"{name}|{port_id}|{sequence:03d}"
    return str(uuid.uuid5(SUPPLIERS_NAMESPACE, f"supplier:{stable_key}"))

def make_user_uuid(name: str, port_id: str, sequence: int) -> str:
    stable_key = f"{name}|{port_id}|{sequence:03d}"
    return str(uuid.uuid5(SUPPLIERS_NAMESPACE, f"user:supplier|{stable_key}"))

now = os.getenv("OPTICARGO_DATASET_TIMESTAMP", "2026-07-26T00:00:00Z")

PREFIXES = ["PT.", "CV.", "UD."]
HUB_NAMES = ["Sejahtera", "Makmur", "Logistik", "Pangan", "Sentosa", "Bina", "Jaya", "Maju", "Agro", "Industri"]
FEEDER_NAMES = ["Hasil Bumi", "Nelayan", "Laut", "Tani", "Samudera", "Nusantara", "Timur", "Papua", "Maluku", "Berkah"]

if __name__ == "__main__":
    random.seed(42)
    base = Path(__file__).parent.parent.parent / 'dataset'
    
    ports_path = base / "ports" / "ports.json"
    comms_path = base / "commodities" / "commodities.json"
    
    ports = json.load(open(ports_path, encoding="utf-8"))
    comms = json.load(open(comms_path, encoding="utf-8"))
    
    # Kelompokkan komoditas
    hub_comms = [c["id"] for c in comms if c["category"] in ["Kebutuhan Pokok", "Material Bangunan", "Barang Konsumsi", "Pertanian"]]
    feeder_comms = [c["id"] for c in comms if c["category"] in ["Hasil Perkebunan", "Rempah", "Hasil Laut", "Ternak", "Kehutanan", "Hasil Pertanian"]]
    
    result = []
    
    # Generate 50 suppliers
    for i in range(1, 51):
        # 30% di Hub, 70% di Feeder
        is_hub = random.random() < 0.3
        
        target_ports = [p for p in ports if p["port_type"] == ("hub" if is_hub else "feeder")]
        port = random.choice(target_ports)
        
        prefix = random.choice(PREFIXES)
        suffix = random.choice(HUB_NAMES if is_hub else FEEDER_NAMES)
        business_name = f"{prefix} {port['city'].split()[-1]} {suffix}"
        
        target_comms = hub_comms if is_hub else feeder_comms
        # Pilih 1-3 komoditas acak
        num_comms = random.randint(1, min(3, len(target_comms)))
        assigned_comms = random.sample(target_comms, num_comms)
        
        result.append({
            "id": make_supplier_uuid(business_name, port["id"], i),
            "user_id": make_user_uuid(business_name, port["id"], i),
            "business_name": business_name,
            "port_id": port["id"],
            "commodity_ids": assigned_comms,
            "avg_monthly_volume_ton": round(random.uniform(50, 500) if is_hub else random.uniform(10, 100), 1),
            "rating": round(random.uniform(3.5, 5.0), 1),
            "verified": random.random() < 0.8,
            "address": f"Jl. Pelabuhan {port['name']} No. {random.randint(1, 100)}, {port['city']}",
            "created_at": now,
            "is_synthetic": True,
            "provenance": "opticargo-data:competition:supplier-generator-v2"
        })
        
    out = base / "suppliers" / "suppliers.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        
    print(f"[OK] Generated {len(result)} suppliers -> {out}")
