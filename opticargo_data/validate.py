from __future__ import annotations

import hashlib
import json
from collections import Counter

from .config import dataset_root
from .contracts import SharedContractError, validate_all, validate_provenance, validate_shared_manifest
from .io import FILES, load, manifest
from .normalize import prepare_seed_rows


class DatasetValidationError(RuntimeError):
    pass


def _unique(rows, field, label):
    c = Counter(str(r.get(field)) for r in rows)
    dup = [key for key, value in c.items() if value > 1]
    if dup:
        raise DatasetValidationError(f"{label}: duplicate {field}: {dup[:5]}")


def dataset_checksum() -> str:
    """Stable checksum over the canonical JSON dataset artifacts."""

    digest = hashlib.sha256()
    root = dataset_root()
    for name, rel in sorted(FILES.items()):
        path = root / rel
        if not path.exists():
            continue
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def validate_competition() -> dict[str, int]:
    names = [
        "users",
        "ports",
        "routes",
        "commodities",
        "ships",
        "suppliers",
        "voyages",
        "cargo_capacities",
        "cargo_listings",
        "bookings",
    ]
    data = {name: load(name) for name in names}
    for name, rows in data.items():
        if not isinstance(rows, list) or not rows:
            raise DatasetValidationError(f"{name}: dataset empty or invalid")
        _unique(rows, "id", name)

    _unique(data["users"], "username", "users")
    _unique(data["users"], "email", "users")

    port_ids = {r["id"] for r in data["ports"]}
    route_ids = {r["id"] for r in data["routes"]}
    user_ids = {r["id"] for r in data["users"]}
    ship_ids = {r["id"] for r in data["ships"]}
    commodity_ids = {r["id"] for r in data["commodities"]}
    supplier_ids = {r["id"] for r in data["suppliers"]}
    voyage_ids = {r["id"] for r in data["voyages"]}
    listing_ids = {r["id"] for r in data["cargo_listings"]}

    for row in data["routes"]:
        if row["origin_port_id"] not in port_ids or row["destination_port_id"] not in port_ids:
            raise DatasetValidationError(f"route {row['id']} references missing port")
    for row in data["ships"]:
        if row.get("operator_id") and row["operator_id"] not in user_ids:
            raise DatasetValidationError(f"ship {row['id']} references missing operator user")
    for row in data["suppliers"]:
        if row["user_id"] not in user_ids or row["port_id"] not in port_ids:
            raise DatasetValidationError(f"supplier {row['id']} invalid user/port FK")
        if any(cid not in commodity_ids for cid in row.get("commodity_ids", [])):
            raise DatasetValidationError(f"supplier {row['id']} invalid commodity FK")
    for row in data["voyages"]:
        if row["ship_id"] not in ship_ids or row["route_id"] not in route_ids:
            raise DatasetValidationError(f"voyage {row['id']} invalid ship/route FK")
        if float(row["remaining_capacity_ton"]) < 0:
            raise DatasetValidationError(f"voyage {row['id']} negative remaining capacity")
    for row in data["cargo_capacities"]:
        if row["voyage_id"] not in voyage_ids:
            raise DatasetValidationError(f"capacity {row['id']} invalid voyage FK")
    for row in data["cargo_listings"]:
        if row["supplier_id"] not in supplier_ids or row["commodity_id"] not in commodity_ids:
            raise DatasetValidationError(f"listing {row['id']} invalid supplier/commodity FK")
        if row["origin_port_id"] not in port_ids or row["destination_port_id"] not in port_ids:
            raise DatasetValidationError(f"listing {row['id']} invalid port FK")
    for row in data["bookings"]:
        if row["voyage_id"] not in voyage_ids or row["cargo_listing_id"] not in listing_ids:
            raise DatasetValidationError(f"booking {row['id']} invalid voyage/listing FK")
        if not row.get("is_synthetic"):
            raise DatasetValidationError(f"booking {row['id']} must be synthetic")

    if len(data["ships"]) < 10 or len(data["suppliers"]) < 30 or len(data["bookings"]) < 500:
        raise DatasetValidationError("Competition minimum counts are not satisfied")
    if len(data["commodities"]) < 3 or len(data["routes"]) < 3:
        raise DatasetValidationError("Competition scenario diversity minimum is not satisfied")

    regulations = load("regulations")
    if len(regulations) < 9:
        raise DatasetValidationError("Expected at least 9 regulation metadata rows")
    root = dataset_root() / "regulations"
    for row in regulations:
        if not (root / row["filename"]).exists():
            raise DatasetValidationError(f"Missing regulation PDF: {row['filename']}")

    expected = manifest().get("counts", {})
    counts = {key: len(value) for key, value in data.items()}
    counts["regulations"] = len(regulations)
    for key, value in expected.items():
        if key in counts and counts[key] != value:
            raise DatasetValidationError(f"manifest count mismatch for {key}: {counts[key]} != {value}")

    # Shared is the public domain-contract source of truth. Validate the normalized
    # seed view because it contains required booking fields that are deterministically
    # derived from existing source relationships.
    prepared, _stats = prepare_seed_rows(data)
    try:
        validate_all(prepared)
        validate_provenance(data)
        validate_shared_manifest(manifest(), dataset_checksum())
    except SharedContractError as exc:
        raise DatasetValidationError(str(exc)) from exc
    except Exception as exc:
        raise DatasetValidationError(f"opticargo-shared validation failed: {exc}") from exc

    return counts


def main():
    counts = validate_competition()
    print("Dataset valid against opticargo-shared==1.0.0")
    print(f"dataset_checksum     {dataset_checksum()}")
    for key, value in counts.items():
        print(f"{key:20s} {value}")


if __name__ == "__main__":
    main()
