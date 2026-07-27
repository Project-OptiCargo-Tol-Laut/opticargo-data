"""
seed_indexes.py - Membuat Index di PostgreSQL dan Neo4j

Menambahkan indeks pada tabel/node yang sering di-query oleh Agen.
Ini akan mempercepat proses Graph Analysis Agent dan Retrieval Agent.
"""

import os
import psycopg2
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

def run_seed_indexes():
    print("\n" + "="*50)
    print("MENGINISIASI PEMBUATAN INDEX")
    print("="*50)

    # 1. PostgreSQL Indexes
    print("[INFO] Membuat index di PostgreSQL...")
    pg_url = os.getenv("DATABASE_URL")
    if pg_url:
        try:
            conn = psycopg2.connect(pg_url)
            cur = conn.cursor()
            
            pg_queries = [
                "CREATE INDEX IF NOT EXISTS idx_routes_origin ON routes(origin_port_id);",
                "CREATE INDEX IF NOT EXISTS idx_routes_dest ON routes(destination_port_id);",
                "CREATE INDEX IF NOT EXISTS idx_voyages_ship ON voyages(ship_id);",
                "CREATE INDEX IF NOT EXISTS idx_voyages_route ON voyages(route_id);",
                "CREATE INDEX IF NOT EXISTS idx_voyages_status ON voyages(status);",
                "CREATE INDEX IF NOT EXISTS idx_suppliers_port ON suppliers(port_id);"
            ]
            
            for query in pg_queries:
                cur.execute(query)
                
            conn.commit()
            cur.close()
            conn.close()
            print("[OK] Index PostgreSQL berhasil dibuat.")
        except Exception as e:
            print(f"[FAIL] Gagal membuat index PostgreSQL: {e}")
    else:
        print("[WARN] DATABASE_URL tidak ditemukan. Skip index PostgreSQL.")

    # 2. Neo4j Indexes
    print("[INFO] Membuat index di Neo4j...")
    uri = os.getenv("NEO4J_URI") or ""
    user = os.getenv("NEO4J_USER") or ""
    password = os.getenv("NEO4J_PASSWORD") or ""

    if all([uri, user, password]):
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                neo4j_queries = [
                    "CREATE INDEX port_id_idx IF NOT EXISTS FOR (p:Port) ON (p.id);",
                    "CREATE INDEX ship_id_idx IF NOT EXISTS FOR (s:Ship) ON (s.id);",
                    "CREATE INDEX supplier_id_idx IF NOT EXISTS FOR (sup:Supplier) ON (sup.id);",
                    "CREATE INDEX commodity_id_idx IF NOT EXISTS FOR (c:Commodity) ON (c.id);",
                    "CREATE INDEX ship_status_idx IF NOT EXISTS FOR (s:Ship) ON (s.status);"
                ]
                for query in neo4j_queries:
                    session.run(query)
            
            driver.close()
            print("[OK] Index Neo4j berhasil dibuat.")
        except Exception as e:
            print(f"[FAIL] Gagal membuat index Neo4j: {e}")
    else:
        print("[WARN] Kredensial Neo4j tidak lengkap. Skip index Neo4j.")

if __name__ == "__main__":
    run_seed_indexes()
