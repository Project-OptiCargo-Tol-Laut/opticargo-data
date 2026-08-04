"""Post-seed verification across PostgreSQL, Neo4j, and Qdrant."""

from __future__ import annotations

from collections import Counter
from typing import Any

from seed.seed_neo4j import get_neo4j_driver
from seed.seed_postgres import get_pg_connection
from seed.seed_qdrant import COLLECTION_NAME, get_qdrant_client
from seed.validate import BASE_DIR, load_json


class SeedVerificationError(RuntimeError):
    """Raised when a seeded datastore does not satisfy its postconditions."""


def _ids(name: str) -> list[str]:
    return [str(item["id"]) for item in load_json(BASE_DIR / name / f"{name}.json")]


def _assert_complete(name: str, expected: set[str], actual: set[str]) -> None:
    missing = sorted(expected - actual)
    if missing:
        preview = ", ".join(missing[:3])
        raise SeedVerificationError(
            f"{name} kehilangan {len(missing)} record seed; contoh: {preview}"
        )


def verify_postgres() -> dict[str, int]:
    """Verify every canonical operational ID and critical invariants in PostgreSQL."""
    expected_by_table = {
        name: set(_ids(name))
        for name in ("ports", "ships", "routes", "voyages", "commodities", "suppliers")
    }
    connection = get_pg_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        for table, expected in expected_by_table.items():
            cursor.execute(
                f"SELECT id::text FROM {table} WHERE id = ANY(%s::uuid[])",
                (sorted(expected),),
            )
            actual = {row[0] for row in cursor.fetchall()}
            _assert_complete(f"PostgreSQL {table}", expected, actual)

        voyage_ids = sorted(expected_by_table["voyages"])
        cursor.execute(
            """
            SELECT count(*)
            FROM voyages
            WHERE id = ANY(%s::uuid[])
              AND used_capacity_ton + remaining_capacity_ton = total_capacity_ton
              AND used_capacity_ton >= 0
              AND remaining_capacity_ton >= 0
            """,
            (voyage_ids,),
        )
        reconciled = int(cursor.fetchone()[0])
        if reconciled != len(voyage_ids):
            raise SeedVerificationError(
                "Rekonsiliasi kapasitas voyage PostgreSQL gagal"
            )

        suppliers = load_json(BASE_DIR / "suppliers" / "suppliers.json")
        seed_user_ids = {str(item["user_id"]) for item in suppliers}
        seed_user_ids.add("87a9b0c1-d2e3-4f56-a7b8-c9d0e1f2a3b4")
        cursor.execute(
            "SELECT count(*) FROM users WHERE id = ANY(%s::uuid[]) AND is_active = false",
            (sorted(seed_user_ids),),
        )
        disabled_users = int(cursor.fetchone()[0])
        if disabled_users != len(seed_user_ids):
            raise SeedVerificationError("Satu atau lebih akun seed masih aktif")
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()
    return {table: len(values) for table, values in expected_by_table.items()}


def _neo4j_ids(session, query: str, identifiers: set[str]) -> set[str]:
    record = session.run(query, ids=sorted(identifiers)).single(strict=True)
    return {str(value) for value in record["ids"]}


def verify_neo4j() -> dict[str, int]:
    """Verify graph nodes plus route, voyage, and supplier connectivity."""
    node_specs = {
        "Port": set(_ids("ports")),
        "Ship": set(_ids("ships")),
        "Commodity": set(_ids("commodities")),
        "Supplier": set(_ids("suppliers")),
    }
    voyages = load_json(BASE_DIR / "voyages" / "voyages.json")
    active_voyages = {
        str(item["id"])
        for item in voyages
        if item["status"] in {"scheduled", "in_transit"}
    }
    routes = set(_ids("routes"))
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            for label, expected in node_specs.items():
                actual = _neo4j_ids(
                    session,
                    f"UNWIND $ids AS id MATCH (n:{label} {{id: id}}) RETURN collect(n.id) AS ids",
                    expected,
                )
                _assert_complete(f"Neo4j {label}", expected, actual)

            route_ids = _neo4j_ids(
                session,
                """
                UNWIND $ids AS id
                MATCH (:Port)-[r:TERHUBUNG_DENGAN {id: id}]->(:Port)
                RETURN collect(r.id) AS ids
                """,
                routes,
            )
            _assert_complete("Neo4j route relationships", routes, route_ids)

            connected_voyages = _neo4j_ids(
                session,
                """
                UNWIND $ids AS id
                MATCH (:Ship)-[:BEROPERASI_DI]->(v:Voyage {id: id})
                MATCH (v)-[:SINGGAH_DI {role: 'origin'}]->(:Port)
                MATCH (v)-[:SINGGAH_DI {role: 'destination'}]->(:Port)
                RETURN collect(DISTINCT v.id) AS ids
                """,
                active_voyages,
            )
            _assert_complete(
                "Neo4j connected voyages", active_voyages, connected_voyages
            )

            supplier_ids = node_specs["Supplier"]
            located_suppliers = _neo4j_ids(
                session,
                """
                UNWIND $ids AS id
                MATCH (s:Supplier {id: id})-[:BERLOKASI_DI]->(:Port)
                MATCH (s)-[:MENYUPLAI]->(:Commodity)
                RETURN collect(DISTINCT s.id) AS ids
                """,
                supplier_ids,
            )
            _assert_complete(
                "Neo4j connected suppliers", supplier_ids, located_suppliers
            )
    finally:
        driver.close()
    return {
        **{label.lower(): len(values) for label, values in node_specs.items()},
        "voyages": len(active_voyages),
        "routes": len(routes),
    }


def _payload_missing_fields(payload: dict[str, Any]) -> list[str]:
    required = (
        "document_id",
        "chunk_id",
        "filename",
        "title",
        "page",
        "checksum",
        "chunk_text",
        "embedding_model",
        "embedding_dimension",
        "metadata",
    )
    return [field for field in required if payload.get(field) in (None, "", [])]


def verify_qdrant() -> dict[str, int]:
    """Verify document coverage, citation payloads, and absence of unknown documents."""
    regulations = load_json(BASE_DIR / "regulations" / "regulations.json")
    expected_filenames = {str(item["filename"]) for item in regulations}
    client = get_qdrant_client()
    counts: Counter[str] = Counter()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            missing = _payload_missing_fields(payload)
            if missing:
                raise SeedVerificationError(
                    f"Qdrant point {point.id} tidak memiliki payload: {', '.join(missing)}"
                )
            filename = str(payload["filename"])
            if filename not in expected_filenames:
                raise SeedVerificationError(
                    f"Qdrant memiliki dokumen asing/stale: {filename}"
                )
            if int(payload["embedding_dimension"]) != 384:
                raise SeedVerificationError(f"Dimensi payload Qdrant salah: {point.id}")
            counts[filename] += 1
        if offset is None:
            break

    missing_documents = sorted(name for name in expected_filenames if counts[name] == 0)
    if missing_documents:
        raise SeedVerificationError(
            f"Dokumen regulasi tanpa chunk Qdrant: {', '.join(missing_documents)}"
        )
    return {"documents": len(counts), "chunks": sum(counts.values())}


def verify_all() -> dict[str, dict[str, int]]:
    """Run all datastore postconditions and return a compact audit summary."""
    summary = {
        "postgres": verify_postgres(),
        "neo4j": verify_neo4j(),
        "qdrant": verify_qdrant(),
    }
    print(
        "[OK] Post-seed verification: "
        f"PostgreSQL {sum(summary['postgres'].values())} record domain, "
        f"Neo4j {summary['neo4j']['routes']} rute/{summary['neo4j']['voyages']} voyage, "
        f"Qdrant {summary['qdrant']['chunks']} chunk/{summary['qdrant']['documents']} dokumen."
    )
    return summary


if __name__ == "__main__":
    verify_all()
