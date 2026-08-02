"""
seed_postgres.py - Seeding Data Transaksional ke PostgreSQL

Memasukkan data dari file JSON (dataset/) ke tabel-tabel PostgreSQL
dengan menjaga urutan Foreign Key dan prinsip idempotensi.

Urutan insert (sesuai PRD Bagian 4.3):
  users -> ports -> ships -> routes -> commodities -> suppliers

Idempotensi dijamin oleh klausa ON CONFLICT (id) DO NOTHING pada
setiap query, sehingga skrip ini aman dijalankan berulang kali
tanpa menghasilkan data duplikat.

Referensi PRD: Bagian 4.3 (seed/seed_postgres.py)
"""

import os
import json

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

from seed.validate import load_json, inject_created_at, BASE_DIR

# Memuat variabel environment dari file .env di root opticargo-data.
# Nilai koneksi (DATABASE_URL, dll.) mengikuti konfigurasi opticargo-infra.
load_dotenv()


# ---------------------------------------------------------------------------
# Koneksi Database
# ---------------------------------------------------------------------------

def get_pg_connection():
    """
    Membuat koneksi ke PostgreSQL menggunakan DATABASE_URL dari environment.

    Returns:
        psycopg2.connection: Objek koneksi yang siap digunakan.

    Raises:
        ValueError: Jika DATABASE_URL tidak ditemukan di environment.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL tidak ditemukan. "
            "Pastikan file .env sudah dikonfigurasi sesuai opticargo-infra."
        )
    db_url = db_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return psycopg2.connect(db_url)


def ensure_schema(cur) -> None:
    """Membuat schema minimum yang dibutuhkan seed lokal bila migration belum tersedia."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS ports (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT,
            province TEXT,
            latitude NUMERIC,
            longitude NUMERIC,
            facilities JSONB NOT NULL DEFAULT '{}'::jsonb,
            max_vessel_tonnage NUMERIC,
            operating_hours JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS ships (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            imo_number TEXT,
            ship_type TEXT,
            gross_tonnage NUMERIC,
            deadweight_tonnage NUMERIC,
            cargo_capacity_m3 NUMERIC,
            operator_id UUID REFERENCES users(id),
            flag TEXT,
            certifications JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS routes (
            id UUID PRIMARY KEY,
            origin_port_id UUID NOT NULL REFERENCES ports(id),
            destination_port_id UUID NOT NULL REFERENCES ports(id),
            distance_nm NUMERIC,
            estimated_days INTEGER,
            route_type TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            tarif_dry_container_idr NUMERIC,
            tarif_reefer_container_idr NUMERIC,
            tarif_general_cargo_idr NUMERIC,
            koefisien_pm29 NUMERIC,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS commodities (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            hs_code TEXT,
            special_requirements JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_perishable BOOLEAN NOT NULL DEFAULT false,
            max_stack_height INTEGER,
            certifications_required TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS voyages (
            id UUID PRIMARY KEY,
            ship_id UUID NOT NULL REFERENCES ships(id),
            route_id UUID NOT NULL REFERENCES routes(id),
            departure_date DATE,
            arrival_date DATE,
            total_capacity_ton NUMERIC,
            used_capacity_ton NUMERIC,
            remaining_capacity_ton NUMERIC,
            status TEXT,
            waypoints JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            business_name TEXT NOT NULL,
            port_id UUID NOT NULL REFERENCES ports(id),
            commodity_ids UUID[] NOT NULL DEFAULT ARRAY[]::UUID[],
            avg_monthly_volume_ton NUMERIC,
            rating NUMERIC,
            verified BOOLEAN NOT NULL DEFAULT false,
            address TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


# ---------------------------------------------------------------------------
# Fungsi Seeding per Tabel
# ---------------------------------------------------------------------------

def seed_users(cur) -> None:
    """
    Memasukkan user dummy yang dibutuhkan sebagai Foreign Key oleh tabel
    ships (operator_id) dan suppliers (user_id).

    Strategi:
    - 1 user operator: ID-nya diambil langsung dari ships.json agar FK cocok.
    - N user supplier: ID-nya diekstrak dari seluruh user_id unik di suppliers.json.

    Email dibuat unik per-user menggunakan 8 karakter pertama UUID,
    untuk menghindari konflik dengan data user yang sudah ada di database
    (misalnya admin bawaan dari opticargo-infra).
    """
    print("[INFO] Seeding Users (Operator & Suppliers)...")

    # -- Operator Kapal --
    # ID ini harus sama persis dengan nilai operator_id di ships.json
    operator_id = "87a9b0c1-d2e3-4f56-a7b8-c9d0e1f2a3b4"

    operator_query = """
        INSERT INTO users (id, username, email, password_hash, role, is_active, created_at)
        VALUES (%s, 'operator_kapal', 'operator_seed@opticargo.id', 'hash', 'operator', true, NOW())
        ON CONFLICT (id) DO NOTHING;
    """
    cur.execute(operator_query, (operator_id,))

    # -- User Supplier --
    # Membaca suppliers.json untuk mengekstrak seluruh user_id unik.
    # Menggunakan set comprehension agar tidak ada ID duplikat.
    suppliers_data = load_json(BASE_DIR / "suppliers" / "suppliers.json")
    unique_supplier_ids = {s["user_id"] for s in suppliers_data}

    supplier_query = """
        INSERT INTO users (id, username, email, password_hash, role, is_active, created_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING;
    """

    # Menyiapkan tuple values untuk bulk insert.
    # Email di-generate unik dari potongan UUID agar tidak bentrok.
    supplier_values = [
        (
            uid,
            f"supplier_{str(uid)[:8]}",
            f"supplier_{str(uid)[:8]}@opticargo.id",
            "hash",
            "supplier",
            True,
            "2026-07-27T00:00:00Z",
        )
        for uid in unique_supplier_ids
    ]

    if supplier_values:
        execute_values(cur, supplier_query, supplier_values)

    print(f"[OK] Seeding selesai: 1 Operator + {len(unique_supplier_ids)} Supplier Users.")


def seed_ports(cur) -> None:
    """
    Memasukkan data pelabuhan dari ports.json ke tabel ports.

    Field yang di-insert disesuaikan dengan kolom tabel PostgreSQL.
    Field tambahan di JSON (port_id, port_type, tol_laut_role, dll.)
    sengaja tidak dimasukkan karena belum ada kolom padanannya di tabel.
    Data tersebut tetap tersimpan di file JSON untuk keperluan lain
    (misalnya Knowledge Graph di Neo4j).
    """
    print("[INFO] Seeding Ports...")
    ports_data = inject_created_at(load_json(BASE_DIR / "ports" / "ports.json"))

    if not ports_data:
        print("[WARN] Tidak ada data ports untuk di-seed.")
        return

    query = """
        INSERT INTO ports (id, name, city, province, latitude, longitude,
                           facilities, max_vessel_tonnage, operating_hours, created_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING;
    """

    values = [
        (
            p["id"],
            p["name"],
            p.get("city", ""),
            p.get("province", ""),
            p.get("latitude", 0),
            p.get("longitude", 0),
            json.dumps(p.get("facilities", {})),
            p.get("max_vessel_tonnage", 0),
            json.dumps(p.get("operating_hours", {})),
            p["created_at"],
        )
        for p in ports_data
    ]

    execute_values(cur, query, values)
    print(f"[OK] Seeding selesai: {len(values)} pelabuhan.")


def seed_ships(cur) -> None:
    """
    Memasukkan data kapal dari ships.json ke tabel ships.

    Field certifications bertipe JSONB di PostgreSQL, sehingga perlu
    di-serialize ke string JSON terlebih dahulu menggunakan json.dumps().
    """
    print("[INFO] Seeding Ships...")
    ships_data = inject_created_at(load_json(BASE_DIR / "ships" / "ships.json"))

    if not ships_data:
        print("[WARN] Tidak ada data ships untuk di-seed.")
        return

    query = """
        INSERT INTO ships (id, name, imo_number, ship_type, gross_tonnage,
                           deadweight_tonnage, cargo_capacity_m3, operator_id,
                           flag, certifications, status, created_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING;
    """

    values = [
        (
            s["id"],
            s["name"],
            s["imo_number"],
            s["ship_type"],
            s["gross_tonnage"],
            s["deadweight_tonnage"],
            s["cargo_capacity_m3"],
            s["operator_id"],
            s.get("flag", ""),
            json.dumps(s.get("certifications", {})),
            s["status"],
            s["created_at"],
        )
        for s in ships_data
    ]

    execute_values(cur, query, values)
    print(f"[OK] Seeding selesai: {len(values)} kapal.")


def seed_routes(cur) -> None:
    """
    Memasukkan data rute pelayaran dari routes.json ke tabel routes.

    Termasuk kolom data tarif (PM 29/2018) untuk mendukung fungsi 
    perhitungan biaya oleh Optimization Agent.
    """
    print("[INFO] Seeding Routes...")
    routes_data = inject_created_at(load_json(BASE_DIR / "routes" / "routes.json"))

    if not routes_data:
        print("[WARN] Tidak ada data routes untuk di-seed.")
        return

    query = """
        INSERT INTO routes (id, origin_port_id, destination_port_id, distance_nm,
                            estimated_days, route_type, is_active,
                            tarif_dry_container_idr, tarif_reefer_container_idr,
                            tarif_general_cargo_idr, koefisien_pm29, created_at)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            tarif_dry_container_idr = EXCLUDED.tarif_dry_container_idr,
            tarif_reefer_container_idr = EXCLUDED.tarif_reefer_container_idr,
            tarif_general_cargo_idr = EXCLUDED.tarif_general_cargo_idr,
            koefisien_pm29 = EXCLUDED.koefisien_pm29;
    """

    values = [
        (
            r["id"],
            r["origin_port_id"],
            r["destination_port_id"],
            r["distance_nm"],
            r["estimated_days"],
            r["route_type"],
            r.get("is_active", True),
            r.get("tarif_dry_container_idr"),
            r.get("tarif_reefer_container_idr"),
            r.get("tarif_general_cargo_idr"),
            r.get("koefisien_pm29"),
            r["created_at"]
        )
        for r in routes_data
    ]

    execute_values(cur, query, values)
    print(f"[OK] Seeding selesai: {len(values)} rute (termasuk data tarif).")


def seed_commodities(cur) -> None:
    """
    Memasukkan data komoditas dari commodities.json ke tabel commodities.

    Field special_requirements bertipe JSONB, sehingga di-serialize.
    Field certifications_required bertipe TEXT[] (array) di PostgreSQL.
    """
    print("[INFO] Seeding Commodities...")
    commodities_data = inject_created_at(
        load_json(BASE_DIR / "commodities" / "commodities.json")
    )

    if not commodities_data:
        print("[WARN] Tidak ada data commodities untuk di-seed.")
        return

    query = """
        INSERT INTO commodities (id, name, category, hs_code, special_requirements,
                                 is_perishable, max_stack_height,
                                 certifications_required, created_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING;
    """

    values = [
        (
            c["id"],
            c["name"],
            c["category"],
            c["hs_code"],
            json.dumps(c.get("special_requirements", {})),
            c.get("is_perishable", False),
            c.get("max_stack_height", 0),
            c.get("certifications_required", []),
            c["created_at"],
        )
        for c in commodities_data
    ]

    execute_values(cur, query, values)
    print(f"[OK] Seeding selesai: {len(values)} komoditas.")


def seed_suppliers(cur) -> None:
    """
    Memasukkan data supplier dari suppliers.json ke tabel suppliers.

    Prasyarat: seed_users() dan seed_ports() harus sudah dijalankan
    terlebih dahulu, karena tabel ini memiliki Foreign Key ke
    tabel users (user_id) dan ports (port_id).
    """
    print("[INFO] Seeding Suppliers...")
    suppliers_data = inject_created_at(
        load_json(BASE_DIR / "suppliers" / "suppliers.json")
    )

    if not suppliers_data:
        print("[WARN] Tidak ada data suppliers untuk di-seed.")
        return

    # Template khusus untuk execute_values: %s di-expand menjadi satu baris,
    # dan di dalamnya kita meng-cast kolom ke-5 (commodity_ids) ke uuid[]
    # agar PostgreSQL tidak menolaknya sebagai text[].
    query = """
        INSERT INTO suppliers (id, user_id, business_name, port_id, commodity_ids,
                               avg_monthly_volume_ton, rating, verified,
                               address, created_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING;
    """
    row_template = "(%s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s, %s)"

    values = [
        (
            s["id"],
            s["user_id"],
            s["business_name"],
            s["port_id"],
            s.get("commodity_ids", []),
            s["avg_monthly_volume_ton"],
            s.get("rating", 0),
            s.get("verified", False),
            s.get("address", ""),
            s["created_at"],
        )
        for s in suppliers_data
    ]

    execute_values(cur, query, values, template=row_template)
    print(f"[OK] Seeding selesai: {len(values)} supplier.")


def seed_voyages(cur) -> None:
    """
    Memasukkan data voyage sintetis dari voyages.json ke tabel voyages.

    Prasyarat: ships dan routes harus sudah di-seed.
    """
    print("[INFO] Seeding Voyages...")
    voyages_data = inject_created_at(
        load_json(BASE_DIR / "voyages" / "voyages.json")
    )

    if not voyages_data:
        print("[WARN] Tidak ada data voyages untuk di-seed.")
        return

    query = """
        INSERT INTO voyages (id, ship_id, route_id, departure_date, arrival_date,
                             total_capacity_ton, used_capacity_ton,
                             remaining_capacity_ton, status, waypoints, created_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING;
    """

    values = [
        (
            v["id"],
            v["ship_id"],
            v["route_id"],
            v["departure_date"],
            v["arrival_date"],
            v["total_capacity_ton"],
            v["used_capacity_ton"],
            v["remaining_capacity_ton"],
            v["status"],
            json.dumps(v.get("waypoints", [])),
            v["created_at"],
        )
        for v in voyages_data
    ]

    execute_values(cur, query, values)
    print(f"[OK] Seeding selesai: {len(values)} voyage.")



# ---------------------------------------------------------------------------
# Orkestrator Utama
# ---------------------------------------------------------------------------

def run_seed() -> None:
    """
    Menjalankan seluruh proses seeding PostgreSQL dalam satu transaksi.

    Urutan pemanggilan sangat penting karena tabel-tabel memiliki
    hubungan Foreign Key satu sama lain:
      users (tidak punya FK)
        -> ports (tidak punya FK)
          -> ships (FK: operator_id -> users)
            -> routes (FK: origin_port_id, destination_port_id -> ports)
              -> commodities (tidak punya FK)
                -> suppliers (FK: user_id -> users, port_id -> ports)

    Jika terjadi error di langkah manapun, seluruh transaksi di-rollback
    sehingga database tidak berada dalam kondisi setengah terisi.
    """
    conn = get_pg_connection()
    cur = conn.cursor()

    try:
        ensure_schema(cur)
        seed_users(cur)
        seed_ports(cur)
        seed_ships(cur)
        seed_routes(cur)
        seed_voyages(cur)
        seed_commodities(cur)
        seed_suppliers(cur)

        conn.commit()
        print("[INFO] Seeding PostgreSQL selesai. Seluruh data berhasil di-commit.")

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Seeding gagal, seluruh transaksi di-rollback: {e}")
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run_seed()
