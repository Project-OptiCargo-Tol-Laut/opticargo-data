"""
generate_routes.py
==================
Script untuk meng-generate routes.json final dengan:
- UUID5 deterministik berbasis origin+destination (sesuai PRD)
- Merujuk port_id dari ports.json yang sudah dibuat
- Field sesuai skema Route model opticargo-shared:
  id, origin_port_id, destination_port_id, distance_nm,
  estimated_days, route_type, is_active
- Data tarif dari PM 29 Tahun 2018 dipertahankan sebagai field tambahan

Jalankan: python -m seed.generate_routes
"""

import json
import uuid
import math
from pathlib import Path

ROUTES_NAMESPACE = uuid.UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901")
PORTS_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def make_port_uuid(name: str) -> str:
    return str(uuid.uuid5(PORTS_NAMESPACE, name.lower().strip()))


def make_route_uuid(origin: str, destination: str, via_ports: list, idx: int = 0) -> str:
    via_str = ",".join(sorted(v.lower().strip() for v in via_ports))
    key = (origin + "|" + destination + "|" + via_str + "|" + str(idx)).lower().strip()
    return str(uuid.uuid5(ROUTES_NAMESPACE, key))


def estimate_days(distance_nm: float) -> int:
    """Estimasi hari perjalanan: kapal kargo Tol Laut ~10-12 knot."""
    if distance_nm <= 0:
        return 1
    hours = distance_nm / 11.0
    days = math.ceil(hours / 24)
    return max(1, days)


def build_route(idx: int, raw: dict) -> dict:
    # Handles both original format (origin_port) and already-enriched format (origin_port_name)
    origin = raw.get("origin_port") or raw.get("origin_port_name", "")
    dest = raw.get("destination_port") or raw.get("destination_port_name", "")
    dist = raw.get("jarak_nm") or raw.get("distance_nm") or 0
    via = raw.get("via_ports", [])
    return {
        "id": make_route_uuid(origin, dest, via, idx),
        "route_id": "route_" + str(idx).zfill(3),
        "origin_port_id": make_port_uuid(origin),
        "origin_port_name": origin,
        "destination_port_id": make_port_uuid(dest),
        "destination_port_name": dest,
        "via_ports": via,
        "distance_nm": dist,
        "estimated_days": estimate_days(dist),
        "route_type": "toll_sea",
        "is_active": True,
        "koefisien_pm29": raw.get("koefisien") or raw.get("koefisien_pm29"),
        "tarif_dry_container_idr": raw.get("tarif_dry_container_idr"),
        "tarif_reefer_container_idr": raw.get("tarif_reefer_container_idr"),
        "tarif_general_cargo_idr": raw.get("tarif_general_cargo_idr"),
        "source": raw.get("source", "Permenhub PM 29 Tahun 2018 - Lampiran Tarif Angkutan Barang PSO"),
    }


if __name__ == "__main__":
    base = Path(__file__).parent.parent
    raw_path = base / "routes" / "routes.json"
    out_path = base / "routes" / "routes.json"

    with open(raw_path, encoding="utf-8") as f:
        raw_routes = json.load(f)

    result = []
    for i, raw in enumerate(raw_routes):
        result.append(build_route(i + 1, raw))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("[OK] Generated " + str(len(result)) + " routes -> " + str(out_path))

    # Verifikasi: cek apakah ada UUID duplikat (seharusnya tidak karena uuid5)
    ids = [r["id"] for r in result]
    dupes = len(ids) - len(set(ids))
    if dupes > 0:
        print("[WARN] " + str(dupes) + " duplicate route UUIDs detected!")
    else:
        print("  Semua UUID unik - OK")

    # Statistik
    unique_origins = set(r["origin_port_name"] for r in result)
    unique_dests = set(r["destination_port_name"] for r in result)
    print("  Unique origins: " + str(len(unique_origins)))
    print("  Unique destinations: " + str(len(unique_dests)))
    avg_dist = sum(r["distance_nm"] for r in result) / len(result)
    print("  Rata-rata jarak: " + str(round(avg_dist, 1)) + " nm")
    print("  Sample route: " + result[0]["origin_port_name"] + " -> " + result[0]["destination_port_name"] + " (" + str(result[0]["distance_nm"]) + " nm, " + str(result[0]["estimated_days"]) + " hari)")
