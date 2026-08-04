"""
seed_indexes.py - Membuat index aplikasi di PostgreSQL

Schema Neo4j dimiliki secara tunggal oleh versioned migrations di repository
opticargo-knowledge-graph agar seeder tidak dapat menimbulkan schema drift.
"""

import os

import psycopg2
from dotenv import load_dotenv

from seed.database import normalize_postgres_dsn

load_dotenv()


def run_seed_indexes():
    print("\n" + "=" * 50)
    print("MENGINISIASI PEMBUATAN INDEX")
    print("=" * 50)

    # 1. PostgreSQL Indexes
    print("[INFO] Membuat index di PostgreSQL...")
    pg_url = os.getenv("DATABASE_URL")
    if not pg_url:
        raise ValueError("DATABASE_URL tidak ditemukan; index PostgreSQL wajib dibuat")
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(normalize_postgres_dsn(pg_url))
        cur = conn.cursor()

        pg_queries = [
            "CREATE INDEX IF NOT EXISTS idx_routes_origin ON routes(origin_port_id);",
            "CREATE INDEX IF NOT EXISTS idx_routes_dest ON routes(destination_port_id);",
            "CREATE INDEX IF NOT EXISTS idx_voyages_ship ON voyages(ship_id);",
            "CREATE INDEX IF NOT EXISTS idx_voyages_route ON voyages(route_id);",
            "CREATE INDEX IF NOT EXISTS idx_voyages_status ON voyages(status);",
            "CREATE INDEX IF NOT EXISTS idx_suppliers_port ON suppliers(port_id);",
        ]

        for query in pg_queries:
            cur.execute(query)
        conn.commit()
        print("[OK] Index PostgreSQL berhasil dibuat.")
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

    print(
        "[INFO] Schema/index Neo4j dikelola oleh versioned migrations "
        "opticargo-knowledge-graph."
    )


if __name__ == "__main__":
    run_seed_indexes()
