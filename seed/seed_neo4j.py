"""
seed_neo4j.py - Membangun Knowledge Graph di Neo4j

Membaca data yang sudah ada di PostgreSQL (source of truth),
lalu membangun node dan relationship di Neo4j untuk keperluan
Graph Analysis Agent dan Retrieval Agent.

Prinsip arsitektur (PRD Bagian 4.4):
  - Data DIBACA dari PostgreSQL, BUKAN dari file JSON.
  - Menggunakan MERGE (bukan CREATE) agar idempoten.
  - Neo4j adalah representasi graph dari data transaksional yang sama.

Node yang dibangun:
  Port, Ship, Commodity, Supplier, Voyage

Relationship yang dibangun:
  (Port)-[:TERHUBUNG_DENGAN]->(Port)       -- dari tabel routes
  (Ship)-[:BEROPERASI_DI]->(Voyage)         -- kapal menjalankan voyage aktif
  (Voyage)-[:SINGGAH_DI]->(Port)            -- origin/destination voyage
  (Supplier)-[:BERLOKASI_DI]->(Port)        -- dari FK port_id
  (Supplier)-[:MENYUPLAI]->(Commodity)      -- dari kolom commodity_ids
"""

import os

import psycopg2
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Koneksi Database
# ---------------------------------------------------------------------------

def get_pg_connection():
    """Membuat koneksi ke PostgreSQL."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL tidak ditemukan di file .env")
    return psycopg2.connect(db_url)


def get_neo4j_driver():
    """
    Membuat driver koneksi ke Neo4j.

    Menggunakan NEO4J_URI, NEO4J_USER, dan NEO4J_PASSWORD
    dari environment variable yang sudah dikonfigurasi di .env.
    """
    uri = os.getenv("NEO4J_URI") or ""
    user = os.getenv("NEO4J_USER") or ""
    password = os.getenv("NEO4J_PASSWORD") or ""

    if not all([uri, user, password]):
        raise ValueError(
            "NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD tidak lengkap di .env"
        )

    return GraphDatabase.driver(uri, auth=(user, password))


# ---------------------------------------------------------------------------
# Pembacaan Data dari PostgreSQL
# ---------------------------------------------------------------------------

def fetch_ports(pg_cur) -> list[dict]:
    """Mengambil seluruh data pelabuhan dari PostgreSQL."""
    pg_cur.execute("""
        SELECT id, name, city, province,
               CAST(latitude AS float), CAST(longitude AS float),
               max_vessel_tonnage
        FROM ports
    """)
    columns = ["id", "name", "city", "province", "latitude", "longitude",
               "max_vessel_tonnage"]
    return [dict(zip(columns, row)) for row in pg_cur.fetchall()]


def fetch_ships(pg_cur) -> list[dict]:
    """Mengambil seluruh data kapal dari PostgreSQL."""
    pg_cur.execute("""
        SELECT id, name, imo_number, ship_type,
               CAST(gross_tonnage AS float),
               CAST(deadweight_tonnage AS float),
               CAST(cargo_capacity_m3 AS float),
               flag, status
        FROM ships
    """)
    columns = ["id", "name", "imo_number", "ship_type", "gross_tonnage",
               "deadweight_tonnage", "cargo_capacity_m3", "flag", "status"]
    return [dict(zip(columns, row)) for row in pg_cur.fetchall()]


def fetch_commodities(pg_cur) -> list[dict]:
    """Mengambil seluruh data komoditas dari PostgreSQL."""
    pg_cur.execute("""
        SELECT id, name, category, hs_code, is_perishable
        FROM commodities
    """)
    columns = ["id", "name", "category", "hs_code", "is_perishable"]
    return [dict(zip(columns, row)) for row in pg_cur.fetchall()]


def fetch_routes(pg_cur) -> list[dict]:
    """Mengambil seluruh data rute beserta nama pelabuhan asal/tujuan dan data tarif."""
    pg_cur.execute("""
        SELECT r.id, r.origin_port_id, r.destination_port_id,
               CAST(r.distance_nm AS float), r.estimated_days,
               r.route_type, r.is_active,
               CAST(r.tarif_dry_container_idr AS float),
               CAST(r.tarif_reefer_container_idr AS float),
               CAST(r.tarif_general_cargo_idr AS float),
               CAST(r.koefisien_pm29 AS float)
        FROM routes r
        WHERE r.is_active = true
    """)
    columns = ["id", "origin_port_id", "destination_port_id",
               "distance_nm", "estimated_days", "route_type", "is_active",
               "tarif_dry_container_idr", "tarif_reefer_container_idr",
               "tarif_general_cargo_idr", "koefisien_pm29"]
    return [dict(zip(columns, row)) for row in pg_cur.fetchall()]


def fetch_voyages(pg_cur) -> list[dict]:
    """Mengambil data voyage yang aktif/scheduled untuk graph."""
    pg_cur.execute("""
        SELECT id, ship_id, route_id,
               departure_date, arrival_date,
               CAST(total_capacity_ton AS float),
               CAST(used_capacity_ton AS float),
               CAST(remaining_capacity_ton AS float)
        FROM voyages
        WHERE status IN ('scheduled', 'in_transit')
    """)
    columns = [
        "id", "ship_id", "route_id",
        "departure_date", "arrival_date",
        "total_capacity_ton", "used_capacity_ton", "remaining_capacity_ton",
    ]
    return [dict(zip(columns, row)) for row in pg_cur.fetchall()]


def fetch_suppliers(pg_cur) -> list[dict]:
    """Mengambil seluruh data supplier beserta daftar commodity_ids."""
    pg_cur.execute("""
        SELECT id, business_name, port_id, commodity_ids,
               CAST(avg_monthly_volume_ton AS float),
               CAST(rating AS float), verified, address
        FROM suppliers
    """)
    columns = ["id", "business_name", "port_id", "commodity_ids",
               "avg_monthly_volume_ton", "rating", "verified", "address"]
    
    rows = []
    for row in pg_cur.fetchall():
        row_dict = dict(zip(columns, row))
        
        # Parse commodity_ids from "{uuid1, uuid2}" to list of strings if necessary
        c_ids = row_dict["commodity_ids"]
        if isinstance(c_ids, str) and c_ids.startswith("{") and c_ids.endswith("}"):
            c_ids = [x.strip() for x in c_ids[1:-1].split(",") if x.strip()]
            row_dict["commodity_ids"] = c_ids
            
        rows.append(row_dict)
        
    return rows


# ---------------------------------------------------------------------------
# Pembuatan Node di Neo4j
# ---------------------------------------------------------------------------

def create_port_nodes(neo4j_session, ports: list[dict]) -> None:
    """
    Membuat node Port di Neo4j.

    Menggunakan MERGE berdasarkan UUID agar idempoten.
    UNWIND digunakan untuk memproses seluruh list dalam satu transaksi
    (lebih efisien daripada satu MERGE per record).
    """
    query = """
        UNWIND $ports AS p
        MERGE (port:Port {id: p.id})
        SET port.name             = p.name,
            port.city             = p.city,
            port.province         = p.province,
            port.latitude         = p.latitude,
            port.longitude        = p.longitude,
            port.max_vessel_tonnage = p.max_vessel_tonnage
    """
    neo4j_session.run(query, ports=ports)


def create_ship_nodes(neo4j_session, ships: list[dict]) -> None:
    """Membuat node Ship di Neo4j."""
    query = """
        UNWIND $ships AS s
        MERGE (ship:Ship {id: s.id})
        SET ship.name               = s.name,
            ship.imo_number         = s.imo_number,
            ship.ship_type          = s.ship_type,
            ship.gross_tonnage      = s.gross_tonnage,
            ship.deadweight_tonnage = s.deadweight_tonnage,
            ship.cargo_capacity_m3  = s.cargo_capacity_m3,
            ship.flag               = s.flag,
            ship.status             = s.status
    """
    neo4j_session.run(query, ships=ships)


def create_commodity_nodes(neo4j_session, commodities: list[dict]) -> None:
    """Membuat node Commodity di Neo4j."""
    query = """
        UNWIND $commodities AS c
        MERGE (com:Commodity {id: c.id})
        SET com.name          = c.name,
            com.category      = c.category,
            com.hs_code       = c.hs_code,
            com.is_perishable = c.is_perishable
    """
    neo4j_session.run(query, commodities=commodities)


def create_supplier_nodes(neo4j_session, suppliers: list[dict]) -> None:
    """Membuat node Supplier di Neo4j."""
    query = """
        UNWIND $suppliers AS s
        MERGE (sup:Supplier {id: s.id})
        SET sup.business_name          = s.business_name,
            sup.avg_monthly_volume_ton = s.avg_monthly_volume_ton,
            sup.rating                 = s.rating,
            sup.verified               = s.verified,
            sup.address                = s.address
    """
    neo4j_session.run(query, suppliers=suppliers)


def create_voyage_nodes(neo4j_session, voyages: list[dict]) -> None:
    """Membuat node Voyage agar query Graph Analysis dapat memakai voyage_id."""
    query = """
        UNWIND $voyages AS v
        MERGE (voyage:Voyage {id: v.id})
        SET voyage.ship_id = v.ship_id,
            voyage.route_id = v.route_id,
            voyage.departure_date = toString(v.departure_date),
            voyage.arrival_date = toString(v.arrival_date),
            voyage.total_capacity_ton = toFloat(v.total_capacity_ton),
            voyage.used_capacity_ton = toFloat(v.used_capacity_ton),
            voyage.remaining_capacity = toFloat(v.remaining_capacity_ton),
            voyage.remaining_capacity_ton = toFloat(v.remaining_capacity_ton)
    """
    neo4j_session.run(query, voyages=voyages)


# ---------------------------------------------------------------------------
# Pembuatan Relationship di Neo4j
# ---------------------------------------------------------------------------

def create_route_relationships(neo4j_session, routes: list[dict]) -> None:
    """
    Membuat relationship TERHUBUNG_DENGAN antar-node Port.

    Setiap rute pelayaran menjadi edge berarah dari pelabuhan asal
    ke pelabuhan tujuan, dengan properti jarak, estimasi hari, dan tarif (jika ada).
    """
    query = """
        UNWIND $routes AS r
        MATCH (origin:Port {id: r.origin_port_id})
        MATCH (dest:Port {id: r.destination_port_id})
        MERGE (origin)-[rel:TERHUBUNG_DENGAN {id: r.id}]->(dest)
        SET rel.distance_nm                = r.distance_nm,
            rel.estimated_days             = r.estimated_days,
            rel.route_type                 = r.route_type,
            rel.tarif_dry_container_idr    = r.tarif_dry_container_idr,
            rel.tarif_reefer_container_idr = r.tarif_reefer_container_idr,
            rel.tarif_general_cargo_idr    = r.tarif_general_cargo_idr,
            rel.koefisien_pm29             = r.koefisien_pm29
    """
    neo4j_session.run(query, routes=routes)


def create_ship_voyage_relationships(neo4j_session, voyages: list[dict]) -> None:
    """
    Membuat relationship Ship -> Voyage -> Port.

    Relasi MELAYANI lama tetap dibuat untuk kompatibilitas agents lama.
    """
    query = """
        UNWIND $voyages AS v
        MATCH (ship:Ship {id: v.ship_id})
        MATCH (voyage:Voyage {id: v.id})
        MATCH (origin:Port)-[r:TERHUBUNG_DENGAN {id: v.route_id}]->(dest:Port)
        MERGE (ship)-[:BEROPERASI_DI]->(voyage)
        MERGE (voyage)-[origin_stop:SINGGAH_DI {role: 'origin'}]->(origin)
        SET origin_stop.sequence = 1
        MERGE (voyage)-[dest_stop:SINGGAH_DI {role: 'destination'}]->(dest)
        SET dest_stop.sequence = 2
        MERGE (ship)-[m:MELAYANI {voyage_id: v.id}]->(origin)
        SET m.route_id = v.route_id,
            m.destination_port_id = dest.id,
            m.remaining_capacity_ton = toFloat(v.remaining_capacity_ton)
    """
    neo4j_session.run(query, voyages=voyages)


def create_supplier_relationships(neo4j_session, suppliers: list[dict]) -> None:
    """
    Membuat dua jenis relationship dari Supplier:

    1. BERLOKASI_DI: Supplier -> Port (berdasarkan port_id)
    2. MENYUPLAI: Supplier -> Commodity (berdasarkan commodity_ids)

    Kedua relationship ini adalah fondasi utama bagi Graph Analysis Agent
    untuk menemukan supplier yang bisa mengisi muatan balik (backhaul).
    """
    # -- Supplier BERLOKASI_DI Port --
    location_query = """
        UNWIND $suppliers AS s
        MATCH (sup:Supplier {id: s.id})
        MATCH (port:Port {id: s.port_id})
        MERGE (sup)-[:BERLOKASI_DI]->(port)
    """
    neo4j_session.run(location_query, suppliers=suppliers)

    # -- Supplier MENYUPLAI Commodity --
    # Perlu flatten: setiap elemen dalam commodity_ids menjadi 1 relationship.
    supply_query = """
        UNWIND $suppliers AS s
        MATCH (sup:Supplier {id: s.id})
        UNWIND s.commodity_ids AS cid
        MATCH (com:Commodity {id: cid})
        MERGE (sup)-[:MENYUPLAI]->(com)
    """
    neo4j_session.run(supply_query, suppliers=suppliers)


# ---------------------------------------------------------------------------
# Orkestrator Utama
# ---------------------------------------------------------------------------

def run_seed() -> None:
    """
    Menjalankan seluruh proses seeding Neo4j.

    Alur kerja:
    1. Baca data dari PostgreSQL (source of truth).
    2. Konversi UUID ke string (Neo4j tidak mengenal tipe UUID Python).
    3. Buat seluruh node terlebih dahulu.
    4. Buat seluruh relationship setelah node tersedia.
    """
    # -- Tahap 1: Baca data dari PostgreSQL --
    print("[INFO] Membaca data dari PostgreSQL...")
    pg_conn = get_pg_connection()
    pg_cur = pg_conn.cursor()

    ports = fetch_ports(pg_cur)
    ships = fetch_ships(pg_cur)
    commodities = fetch_commodities(pg_cur)
    routes = fetch_routes(pg_cur)
    voyages = fetch_voyages(pg_cur)
    suppliers = fetch_suppliers(pg_cur)

    pg_cur.close()
    pg_conn.close()

    print(f"[INFO] Data terbaca: {len(ports)} ports, {len(ships)} ships, "
          f"{len(commodities)} commodities, {len(routes)} routes, "
          f"{len(voyages)} voyages, {len(suppliers)} suppliers.")

    # -- Tahap 2: Konversi UUID ke string --
    # Neo4j driver Python tidak bisa serialize objek UUID secara langsung.
    # Kita perlu mengonversinya ke string agar bisa dikirim sebagai parameter.
    from decimal import Decimal

    for record_list in [ports, ships, commodities, routes, voyages, suppliers]:
        for record in record_list:
            for key, value in record.items():
                if hasattr(value, "hex"):  # UUID tunggal
                    record[key] = str(value)
                elif isinstance(value, list): # List UUID
                    record[key] = [str(v) if hasattr(v, "hex") else v for v in value]
                elif isinstance(value, Decimal):  # Decimal dari psycopg2
                    record[key] = float(value)
                elif isinstance(value, list):
                    record[key] = [
                        str(v) if hasattr(v, "hex")
                        else float(v) if isinstance(v, Decimal)
                        else v
                        for v in value
                    ]

    # -- Tahap 3: Buat node --
    neo4j_driver = get_neo4j_driver()

    with neo4j_driver.session() as session:
        print("[INFO] Membuat node Port...")
        create_port_nodes(session, ports)
        print(f"[OK] {len(ports)} node Port.")

        print("[INFO] Membuat node Ship...")
        create_ship_nodes(session, ships)
        print(f"[OK] {len(ships)} node Ship.")

        print("[INFO] Membuat node Commodity...")
        create_commodity_nodes(session, commodities)
        print(f"[OK] {len(commodities)} node Commodity.")

        print("[INFO] Membuat node Supplier...")
        create_supplier_nodes(session, suppliers)
        print(f"[OK] {len(suppliers)} node Supplier.")

        print("[INFO] Membuat node Voyage...")
        create_voyage_nodes(session, voyages)
        print(f"[OK] {len(voyages)} node Voyage.")

        # -- Tahap 4: Buat relationship --
        print("[INFO] Membuat relationship TERHUBUNG_DENGAN (rute)...")
        create_route_relationships(session, routes)
        print(f"[OK] {len(routes)} relationship rute.")

        print("[INFO] Membuat relationship MELAYANI (kapal-voyage-pelabuhan)...")
        create_ship_voyage_relationships(session, voyages)
        print("[OK] Relationship kapal-pelabuhan selesai.")

        print("[INFO] Membuat relationship BERLOKASI_DI dan MENYUPLAI...")
        create_supplier_relationships(session, suppliers)
        print("[OK] Relationship supplier selesai.")

    neo4j_driver.close()
    print("[INFO] Seeding Neo4j selesai. Knowledge Graph berhasil dibangun.")


if __name__ == "__main__":
    run_seed()
