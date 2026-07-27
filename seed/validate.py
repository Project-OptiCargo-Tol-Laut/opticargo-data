"""
validate.py - Modul Validasi Dataset OptiCargo

Memastikan seluruh file JSON di folder dataset/ lolos validasi
terhadap skema Pydantic yang didefinisikan di opticargo-shared.
Mengikuti prinsip fail-fast: jika satu record saja tidak valid,
seluruh proses dihentikan sebelum data sempat masuk ke database.

Referensi PRD: Bagian 4.2 (seed/validate.py)
"""

import json
from pathlib import Path
from datetime import datetime, timezone

from opticargo_shared.models.port import Port
from opticargo_shared.models.ship import Ship
from opticargo_shared.models.route import Route
from opticargo_shared.models.commodity import Commodity
from opticargo_shared.models.supplier import Supplier
from opticargo_shared.models.voyage import Voyage

# Lokasi root folder dataset, relatif terhadap posisi file ini.
# Struktur: opticargo-data/seed/validate.py -> naik 1 level -> opticargo-data/dataset/
BASE_DIR = Path(__file__).parent.parent / "dataset"


def load_json(filepath: Path) -> list[dict]:
    """
    Membaca file JSON dan mengembalikan isinya sebagai list of dict.

    Args:
        filepath: Path absolut atau relatif menuju file JSON.

    Returns:
        List of dictionary dari isi file JSON.
        Mengembalikan list kosong jika file tidak ditemukan.
    """
    if not filepath.exists():
        print(f"[WARN] File tidak ditemukan: {filepath}")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


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
    now = datetime.now(timezone.utc).isoformat()
    for item in data_list:
        if "created_at" not in item:
            item["created_at"] = now
    return data_list


def validate_all() -> None:
    """
    Menjalankan validasi fail-fast terhadap seluruh file dataset.

    Urutan validasi mengikuti dependensi logis:
    Ports -> Ships -> Routes -> Commodities -> Suppliers.

    Raises:
        pydantic.ValidationError: Jika ada record yang tidak sesuai skema.
    """
    print("[INFO] Memulai validasi data JSON...")

    try:
        ports_data = inject_created_at(load_json(BASE_DIR / "ports" / "ports.json"))
        ports = [Port(**item) for item in ports_data]
        print(f"[OK] Validasi sukses: {len(ports)} Port")

        ships_data = inject_created_at(load_json(BASE_DIR / "ships" / "ships.json"))
        ships = [Ship(**item) for item in ships_data]
        print(f"[OK] Validasi sukses: {len(ships)} Ship")

        routes_data = inject_created_at(load_json(BASE_DIR / "routes" / "routes.json"))
        routes = [Route(**item) for item in routes_data]
        print(f"[OK] Validasi sukses: {len(routes)} Route")

        commodities_data = inject_created_at(load_json(BASE_DIR / "commodities" / "commodities.json"))
        commodities = [Commodity(**item) for item in commodities_data]
        print(f"[OK] Validasi sukses: {len(commodities)} Commodity")

        suppliers_data = inject_created_at(load_json(BASE_DIR / "suppliers" / "suppliers.json"))
        suppliers = [Supplier(**item) for item in suppliers_data]
        print(f"[OK] Validasi sukses: {len(suppliers)} Supplier")

        voyages_data = inject_created_at(load_json(BASE_DIR / "voyages" / "voyages.json"))
        voyages = [Voyage(**item) for item in voyages_data]
        print(f"[OK] Validasi sukses: {len(voyages)} Voyage")

        print("[INFO] Semua data JSON valid dan siap dimasukkan ke database.")

    except Exception as e:
        print(f"[FAIL] Validasi gagal. Data tidak sesuai skema Pydantic:\n{e}")
        raise


if __name__ == "__main__":
    validate_all()