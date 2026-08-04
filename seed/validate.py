"""
validate.py - Modul Validasi Dataset OptiCargo

Memastikan seluruh file JSON di folder dataset/ lolos validasi
terhadap skema Pydantic yang didefinisikan di opticargo-shared.
Mengikuti prinsip fail-fast: jika satu record saja tidak valid,
seluruh proses dihentikan sebelum data sempat masuk ke database.

Referensi PRD: Bagian 4.2 (seed/validate.py)
"""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from opticargo_shared.models.commodity import Commodity
from opticargo_shared.models.port import Port
from opticargo_shared.models.route import Route
from opticargo_shared.models.ship import Ship
from opticargo_shared.models.supplier import Supplier
from opticargo_shared.models.voyage import Voyage

from seed.manifest import check_manifest

# Lokasi root folder dataset, relatif terhadap posisi file ini.
# Struktur: opticargo-data/seed/validate.py -> naik 1 level -> opticargo-data/dataset/
BASE_DIR = Path(__file__).parent.parent / "dataset"
DEFAULT_CREATED_AT = datetime(2026, 7, 27, tzinfo=UTC).isoformat()


class DatasetValidationError(ValueError):
    """Raised when a dataset asset or cross-reference is invalid."""


def load_json(filepath: Path) -> list[dict[str, Any]]:
    """
    Membaca file JSON dan mengembalikan isinya sebagai list of dict.

    Args:
        filepath: Path absolut atau relatif menuju file JSON.

    Returns:
        List of dictionary dari isi file JSON.
        Raises DatasetValidationError bila file hilang, kosong, atau bukan list object.
    """
    if not filepath.exists():
        raise DatasetValidationError(f"File dataset tidak ditemukan: {filepath}")
    with filepath.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, list) or not value:
        raise DatasetValidationError(
            f"File dataset harus berupa list non-kosong: {filepath}"
        )
    if not all(isinstance(item, dict) for item in value):
        raise DatasetValidationError(
            f"Semua record dataset harus berupa object: {filepath}"
        )
    return value


def inject_created_at(data_list: list[dict]) -> list[dict]:
    """
    Menyuntikkan field 'created_at' pada record yang belum memilikinya.

    Beberapa file JSON (misalnya routes.json) tidak menyertakan
    field created_at karena field tersebut bersifat metadata database,
    bukan data domain. Fungsi ini menambahkannya secara otomatis
    dengan timestamp UTC saat ini agar lolos validasi Pydantic.

    Args:
        data_list: List of dict hasil pembacaan JSON.

    Returns:
        List of dict yang sama (mutasi in-place), dengan created_at terisi.
    """
    for item in data_list:
        if "created_at" not in item:
            item["created_at"] = DEFAULT_CREATED_AT
    return data_list


def normalize_for_shared(model: type, item: dict[str, Any]) -> dict[str, Any]:
    """Ambil hanya field kontrak shared dan lengkapi timestamp read model."""
    normalized = {key: item[key] for key in model.model_fields if key in item}
    if "created_at" in model.model_fields and "created_at" not in normalized:
        normalized["created_at"] = DEFAULT_CREATED_AT
    if "updated_at" in model.model_fields and "updated_at" not in normalized:
        normalized["updated_at"] = normalized.get("created_at", DEFAULT_CREATED_AT)
    return normalized


def validate_records(model: type, data: list[dict]) -> list:
    """Validasi fail-fast memakai kontrak shared tanpa membuang metadata dataset."""
    return [model.model_validate(normalize_for_shared(model, item)) for item in data]


def _unique_ids(name: str, records: list[dict[str, Any]]) -> set[str]:
    identifiers = [str(item.get("id", "")) for item in records]
    if not all(identifiers) or len(identifiers) != len(set(identifiers)):
        raise DatasetValidationError(f"ID kosong atau duplikat pada dataset {name}")
    return set(identifiers)


def validate_cross_references(
    datasets: dict[str, list[dict[str, Any]]],
    dataset_dir: Path = BASE_DIR,
) -> dict[str, int]:
    """Validate FK, schedule, capacity, and RAG assets before any database mutation."""

    ids = {name: _unique_ids(name, records) for name, records in datasets.items()}
    operational_names = (
        "ports",
        "routes",
        "ships",
        "commodities",
        "suppliers",
        "voyages",
    )
    all_operational = [
        identifier for name in operational_names for identifier in ids[name]
    ]
    if len(all_operational) != len(set(all_operational)):
        raise DatasetValidationError(
            "ID domain bertabrakan antar file dataset operasional"
        )

    routes_by_id = {str(item["id"]): item for item in datasets["routes"]}
    ships_by_id = {str(item["id"]): item for item in datasets["ships"]}
    suppliers_by_port: dict[str, list[dict[str, Any]]] = {}
    for route in datasets["routes"]:
        if str(route["origin_port_id"]) not in ids["ports"]:
            raise DatasetValidationError(
                f"Route {route['id']} memiliki origin_port_id tidak valid"
            )
        if str(route["destination_port_id"]) not in ids["ports"]:
            raise DatasetValidationError(
                f"Route {route['id']} memiliki destination_port_id tidak valid"
            )
        if route["origin_port_id"] == route["destination_port_id"]:
            raise DatasetValidationError(
                f"Route {route['id']} memiliki origin dan destination sama"
            )
        if Decimal(str(route["distance_nm"])) <= 0 or int(route["estimated_days"]) <= 0:
            raise DatasetValidationError(
                f"Route {route['id']} memiliki distance/duration tidak valid"
            )

    for supplier in datasets["suppliers"]:
        if str(supplier["port_id"]) not in ids["ports"]:
            raise DatasetValidationError(
                f"Supplier {supplier['id']} memiliki port_id tidak valid"
            )
        commodity_ids = [str(value) for value in supplier.get("commodity_ids", [])]
        if not commodity_ids or any(
            value not in ids["commodities"] for value in commodity_ids
        ):
            raise DatasetValidationError(
                f"Supplier {supplier['id']} memiliki commodity_ids tidak valid"
            )
        suppliers_by_port.setdefault(str(supplier["port_id"]), []).append(supplier)

    active_voyages = 0
    backhaul_ready = 0
    for voyage in datasets["voyages"]:
        route = routes_by_id.get(str(voyage["route_id"]))
        ship = ships_by_id.get(str(voyage["ship_id"]))
        if route is None or ship is None:
            raise DatasetValidationError(
                f"Voyage {voyage['id']} memiliki FK route/ship tidak valid"
            )
        departure = date.fromisoformat(str(voyage["departure_date"])[:10])
        arrival = date.fromisoformat(str(voyage["arrival_date"])[:10])
        if arrival <= departure:
            raise DatasetValidationError(
                f"Voyage {voyage['id']} memiliki jadwal tidak valid"
            )
        total = Decimal(str(voyage["total_capacity_ton"]))
        used = Decimal(str(voyage["used_capacity_ton"]))
        remaining = Decimal(str(voyage["remaining_capacity_ton"]))
        if total <= 0 or used < 0 or remaining < 0 or used + remaining != total:
            raise DatasetValidationError(
                f"Voyage {voyage['id']} memiliki rekonsiliasi kapasitas tidak valid"
            )
        if voyage["status"] in {"scheduled", "in_transit"}:
            active_voyages += 1
            if not route.get("is_active", False):
                raise DatasetValidationError(
                    f"Voyage aktif {voyage['id']} memakai route nonaktif"
                )
            if ship.get("status") != "active":
                raise DatasetValidationError(
                    f"Voyage aktif {voyage['id']} memakai ship nonaktif"
                )
            if suppliers_by_port.get(str(route["destination_port_id"])):
                backhaul_ready += 1

    filenames: set[str] = set()
    for regulation in datasets["regulations"]:
        filename = str(regulation["filename"])
        if filename in filenames:
            raise DatasetValidationError(f"Filename regulasi duplikat: {filename}")
        filenames.add(filename)
        path = dataset_dir / "regulations" / filename
        if (
            path.suffix.lower() != ".pdf"
            or not path.is_file()
            or path.stat().st_size == 0
        ):
            raise DatasetValidationError(f"PDF regulasi hilang atau kosong: {filename}")
        if not regulation.get("source_url") or not regulation.get("topics"):
            raise DatasetValidationError(
                f"Metadata sumber/topik regulasi tidak lengkap: {filename}"
            )

    if active_voyages == 0 or backhaul_ready == 0:
        raise DatasetValidationError(
            "Dataset tidak memiliki skenario active-voyage backhaul yang valid"
        )
    return {
        "active_voyages": active_voyages,
        "backhaul_ready_voyages": backhaul_ready,
        "regulation_pdfs": len(filenames),
    }


def validate_all() -> dict[str, int]:
    """
    Menjalankan validasi fail-fast terhadap seluruh file dataset.

    Urutan validasi mengikuti dependensi logis:
    Ports -> Ships -> Routes -> Commodities -> Suppliers.

    Raises:
        pydantic.ValidationError: Jika ada record yang tidak sesuai skema.
    """
    print("[INFO] Memulai validasi data JSON...")

    try:
        manifest_problems = check_manifest(BASE_DIR)
        if manifest_problems:
            raise DatasetValidationError("; ".join(manifest_problems))

        ports_data = inject_created_at(load_json(BASE_DIR / "ports" / "ports.json"))
        ports = validate_records(Port, ports_data)
        print(f"[OK] Validasi sukses: {len(ports)} Port")

        ships_data = inject_created_at(load_json(BASE_DIR / "ships" / "ships.json"))
        ships = validate_records(Ship, ships_data)
        print(f"[OK] Validasi sukses: {len(ships)} Ship")

        routes_data = inject_created_at(load_json(BASE_DIR / "routes" / "routes.json"))
        routes = validate_records(Route, routes_data)
        print(f"[OK] Validasi sukses: {len(routes)} Route")

        commodities_data = inject_created_at(
            load_json(BASE_DIR / "commodities" / "commodities.json")
        )
        commodities = validate_records(Commodity, commodities_data)
        print(f"[OK] Validasi sukses: {len(commodities)} Commodity")

        suppliers_data = inject_created_at(
            load_json(BASE_DIR / "suppliers" / "suppliers.json")
        )
        suppliers = validate_records(Supplier, suppliers_data)
        print(f"[OK] Validasi sukses: {len(suppliers)} Supplier")

        voyages_data = inject_created_at(
            load_json(BASE_DIR / "voyages" / "voyages.json")
        )
        voyages = validate_records(Voyage, voyages_data)
        print(f"[OK] Validasi sukses: {len(voyages)} Voyage")

        regulations_data = load_json(BASE_DIR / "regulations" / "regulations.json")
        summary = validate_cross_references(
            {
                "ports": ports_data,
                "routes": routes_data,
                "ships": ships_data,
                "commodities": commodities_data,
                "suppliers": suppliers_data,
                "voyages": voyages_data,
                "regulations": regulations_data,
            }
        )
        print(
            "[OK] Cross-reference valid: "
            f"{summary['active_voyages']} voyage aktif, "
            f"{summary['backhaul_ready_voyages']} siap backhaul, "
            f"{summary['regulation_pdfs']} PDF regulasi."
        )

        print("[INFO] Semua data JSON valid dan siap dimasukkan ke database.")
        return summary

    except Exception as e:
        print(f"[FAIL] Validasi gagal. Data tidak sesuai skema Pydantic:\n{e}")
        raise


if __name__ == "__main__":
    validate_all()
