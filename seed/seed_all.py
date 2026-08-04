"""
seed_all.py - Orkestrator Seeding OptiCargo

Skrip ini menjalankan seluruh tahapan seeding secara berurutan:
1. Validasi Pydantic (validate.py)
2. Seeding PostgreSQL (seed_postgres.py)
3. Seeding Neo4j (seed_neo4j.py)
4. Seeding Qdrant (seed_qdrant.py)
5. Membuat Indexes (seed_indexes.py)
"""

import sys

from seed.seed_indexes import run_seed_indexes
from seed.seed_neo4j import run_seed as run_seed_neo4j
from seed.seed_postgres import run_seed as run_seed_postgres
from seed.seed_qdrant import run_seed as run_seed_qdrant
from seed.validate import validate_all
from seed.verify_seed import verify_all


def main():
    print("=" * 50)
    print("Memulai OptiCargo Seeding Pipeline")
    print("=" * 50)

    try:
        print("\n[1/6] Menjalankan Validasi Data (Pydantic)...")
        validate_all()

        print("\n[2/6] Menjalankan Seeding PostgreSQL...")
        run_seed_postgres()

        print("\n[3/6] Menjalankan Seeding Neo4j...")
        run_seed_neo4j()

        print("\n[4/6] Menjalankan Seeding Qdrant...")
        run_seed_qdrant()

        print("\n[5/6] Membuat Index Database (PostgreSQL & Neo4j)...")
        run_seed_indexes()

        print("\n[6/6] Memverifikasi hasil seed lintas database...")
        verify_all()

        print("\n" + "=" * 50)
        print("[SUCCESS] SEEDING PIPELINE SELESAI.")
        print("=" * 50)

    except Exception as e:  # noqa: BLE001 - pipeline boundary reports every fatal error
        print("\n" + "=" * 50)
        print(f"[FAIL] SEEDING PIPELINE GAGAL: {e}")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
