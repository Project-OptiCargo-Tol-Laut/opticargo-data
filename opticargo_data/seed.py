from __future__ import annotations

import argparse

from .config import demo_password, demo_password_source, password_scheme
from .contracts import shared_contract_version
from .db import SchemaMismatch, connect, schema_report, upsert_rows
from .io import load, manifest
from .normalize import prepare_seed_rows
from .security import hash_password, verify_password
from .validate import validate_competition

TABLE_ORDER = [
    "users",
    "ports",
    "commodities",
    "routes",
    "ships",
    "suppliers",
    "voyages",
    "cargo_capacities",
    "cargo_listings",
    "bookings",
]


def seed(
    profile: str,
    idempotent: bool,
    schema_only: bool = False,
    upload_regulations_flag: bool = False,
):
    if profile != "competition":
        raise SystemExit(f"Unsupported profile: {profile}. Available: competition")
    validate_competition()
    with connect() as conn:
        if schema_only:
            print(schema_report(conn, TABLE_ORDER))
            return {}, {}

        source_rows = {name: load(name) for name in TABLE_ORDER}
        rows, normalize_stats = prepare_seed_rows(source_rows)

        # Password hashes are generated at seed time and never stored in dataset artifacts.
        scheme = password_scheme()
        password = demo_password()
        hashed = hash_password(password, scheme)
        for user in rows["users"]:
            user["password_hash"] = hashed

        seeded = {}
        id_maps: dict[str, dict[str, str]] = {}
        for table in TABLE_ORDER:
            stats = upsert_rows(
                conn,
                table,
                rows[table],
                idempotent=idempotent,
                id_maps=id_maps,
            )
            seeded[table] = stats
            id_maps[table] = stats.id_map
        conn.commit()

    if upload_regulations_flag:
        from .regulations import upload_regulations

        normalize_stats["regulation_files_uploaded"] = upload_regulations()
    return seeded, normalize_stats


def verify_demo_auth() -> int:
    """Safely verify the resolved demo password against the seeded admin hash.

    The password itself is never printed.  This command is intended for local/CI
    diagnosis when Gateway login returns Invalid credentials.
    """
    password = demo_password()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, account_status, password_hash FROM users WHERE username=%s",
                ("admin.demo",),
            )
            row = cur.fetchone()
    print(f"demo_password_source      {demo_password_source()}")
    print(f"demo_password_length      {len(password)}")
    print(f"admin_user_found          {bool(row)}")
    if not row:
        print("admin_password_matches    False")
        return 3
    username, status, password_hash = row
    print(f"admin_username            {username}")
    print(f"admin_account_status      {status}")
    print(f"admin_hash_algorithm      {'argon2id' if str(password_hash).startswith('$argon2id$') else 'unknown'}")
    matches = verify_password(str(password_hash), password)
    print(f"admin_password_matches    {matches}")
    return 0 if matches else 4


def main(argv=None):
    p = argparse.ArgumentParser(description="OptiCargo deterministic data seeder")
    p.add_argument("--profile", default="competition", choices=["competition"])
    p.add_argument(
        "--idempotent",
        action="store_true",
        help="Use schema-aware idempotent upsert and resolve business-unique aliases",
    )
    p.add_argument("--validate-only", action="store_true")
    p.add_argument("--schema-only", action="store_true", help="Print live PostgreSQL schema used by the seeder")
    p.add_argument("--verify-demo-auth", action="store_true", help="Verify the resolved demo password against admin.demo without printing the password")
    p.add_argument(
        "--upload-regulations",
        action="store_true",
        help="Stage regulation PDFs in MinIO; indexing remains RAG worker responsibility",
    )
    args = p.parse_args(argv)
    if args.verify_demo_auth:
        return verify_demo_auth()
    counts = validate_competition()
    if args.validate_only:
        print(f"Competition dataset valid against opticargo-shared=={shared_contract_version()}")
        for k, v in counts.items():
            print(f"{k:24s} {v}")
        return 0
    try:
        seeded, normalization = seed(
            args.profile,
            args.idempotent,
            args.schema_only,
            args.upload_regulations,
        )
    except SchemaMismatch as exc:
        print(f"SCHEMA_MISMATCH: {exc}")
        return 2
    if args.schema_only:
        return 0

    m = manifest()
    print("OptiCargo Competition Seed")
    print("=" * 29)
    for table in TABLE_ORDER:
        stats = seeded[table]
        suffix = f" (aliases={stats.unique_aliases})" if stats.unique_aliases else ""
        print(f"{table:24s} {stats.materialized_ids}/{stats.processed}{suffix}")
    print(f"{'routes_source':24s} {normalization['routes_source']}")
    print(f"{'routes_materialized':24s} {normalization['routes_materialized']}")
    print(f"{'route_aliases':24s} {normalization['route_aliases']}")
    print(f"{'voyage_route_remaps':24s} {normalization['voyage_route_remaps']}")
    print(f"{'cargo_listings_enriched':24s} {normalization['cargo_listings_enriched']}")
    print(f"{'bookings_enriched':24s} {normalization['bookings_enriched']}")
    if "regulation_files_uploaded" in normalization:
        print(f"{'regulation_files_uploaded':24s} {normalization['regulation_files_uploaded']}")
    print(f"dataset_version          {m['dataset_version']}")
    print(f"idempotent               {args.idempotent}")
    print(f"shared_contract          {shared_contract_version()}")
    print(f"password_scheme          {password_scheme()}")
    print(f"demo_password_source     {demo_password_source()}")
    print(f"demo_password_length     {len(demo_password())}")
    print("demo_admin               admin.demo / admin@demo.opticargo.id")
    print("demo_operator            operator.demo / operator@demo.opticargo.id")
    print("demo_password            from OPTICARGO_DEMO_PASSWORD (default documented for local demo only)")
    print("Seed completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
