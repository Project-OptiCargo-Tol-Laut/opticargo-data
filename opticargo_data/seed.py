from __future__ import annotations

import argparse
from time import perf_counter

from .config import demo_password, demo_password_source, password_scheme
from .contracts import (
    shared_contract_version,
    validate_all,
    validate_provenance,
)
from .demo_accounts import DEMO_ACCOUNTS
from .db import SchemaMismatch, connect, schema_report, upsert_rows
from .io import load, manifest
from .load_profiles import (
    DEFAULT_ANCHOR_DATE,
    LOAD_PROFILES,
    build_augmented_rows,
    load_plan,
    parse_anchor_date,
)
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


def _base_rows() -> dict[str, list[dict]]:
    return {name: load(name) for name in TABLE_ORDER}


def _prepare_runtime_rows(
    *,
    load_profile: str,
    anchor_date: str | None,
    presentation_scenarios: bool,
):
    source_rows = _base_rows()
    anchor = parse_anchor_date(anchor_date)
    augmented, augmentation_stats = build_augmented_rows(
        source_rows,
        load_profile=load_profile,
        anchor_date=anchor,
        presentation_scenarios=presentation_scenarios,
    )
    rows, normalize_stats = prepare_seed_rows(augmented)

    # Static JSON is already validated by validate_competition(). Runtime-generated
    # rows are validated again as one coherent graph before touching PostgreSQL.
    validate_all(rows)
    validate_provenance(augmented)
    return rows, normalize_stats, augmentation_stats, anchor


def seed(
    profile: str,
    idempotent: bool,
    schema_only: bool = False,
    upload_regulations_flag: bool = False,
    *,
    load_profile: str = "none",
    anchor_date: str | None = None,
    presentation_scenarios: bool = True,
):
    if profile != "competition":
        raise SystemExit(f"Unsupported profile: {profile}. Available: competition")
    validate_competition()
    with connect() as conn:
        if schema_only:
            print(schema_report(conn, TABLE_ORDER))
            return {}, {}, {}, {}, parse_anchor_date(anchor_date)

        rows, normalize_stats, augmentation_stats, anchor = _prepare_runtime_rows(
            load_profile=load_profile,
            anchor_date=anchor_date,
            presentation_scenarios=presentation_scenarios,
        )

        # Password hashes are generated at seed time and never stored in dataset artifacts.
        scheme = password_scheme()
        password = demo_password()
        hashed = hash_password(password, scheme)
        for user in rows["users"]:
            user["password_hash"] = hashed

        seeded = {}
        timings: dict[str, float] = {}
        id_maps: dict[str, dict[str, str]] = {}
        started = perf_counter()
        for table in TABLE_ORDER:
            table_started = perf_counter()
            stats = upsert_rows(
                conn,
                table,
                rows[table],
                idempotent=idempotent,
                id_maps=id_maps,
            )
            timings[table] = perf_counter() - table_started
            seeded[table] = stats
            id_maps[table] = stats.id_map
        conn.commit()
        timings["total"] = perf_counter() - started

    if upload_regulations_flag:
        from .regulations import upload_regulations

        normalize_stats["regulation_files_uploaded"] = upload_regulations()
    return seeded, normalize_stats, augmentation_stats, timings, anchor


def list_demo_accounts(show_password: bool = False) -> int:
    """Print deterministic demo login identities.

    The resolved password is only printed when the caller explicitly passes
    --show-demo-password. This keeps ordinary seed/CI logs free of credentials.
    """
    password = demo_password() if show_password else None
    source = demo_password_source()

    print("OptiCargo deterministic demo accounts")
    print("=" * 37)
    print(f"password_source          {source}")
    if not show_password:
        print("password                 <hidden; pass --show-demo-password to display>")
    for account in DEMO_ACCOUNTS:
        line = (
            f"{account['role']:16s} "
            f"{account['username']:20s} "
            f"{account['email']}"
        )
        if show_password:
            line += f"  password={password}"
        print(line)
    return 0


def print_load_plan(profile: str) -> int:
    plan = load_plan(profile)
    print(f"OptiCargo load profile: {profile}")
    print("=" * 34)
    print(f"additional_users         {plan.users}")
    print(f"additional_suppliers     {plan.suppliers}")
    print(f"additional_voyages       {plan.voyages}")
    print(f"additional_capacities    {plan.voyages}")
    print(f"additional_listings      {plan.cargo_listings}")
    print(f"additional_bookings      {plan.bookings}")
    print("presentation_listings    5 UMKM + 5 Distributor (unless --no-presentation-scenarios)")
    print("distributor_demo         supplier + 5 bookings across lifecycle states")
    return 0


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
    p.add_argument(
        "--load-profile",
        default="none",
        choices=list(LOAD_PROFILES),
        help="Add deterministic relational volume for local API/FE performance testing",
    )
    p.add_argument(
        "--seed-anchor-date",
        default=None,
        help=f"Anchor generated voyage/listing dates at YYYY-MM-DD (default {DEFAULT_ANCHOR_DATE.isoformat()})",
    )
    p.add_argument(
        "--no-presentation-scenarios",
        action="store_true",
        help="Do not add the five guaranteed-match umkm.demo listings",
    )
    p.add_argument(
        "--print-load-plan",
        action="store_true",
        help="Print the selected load profile counts and exit without database access",
    )
    p.add_argument(
        "--list-demo-accounts",
        action="store_true",
        help="List the nine deterministic presentation accounts without printing the password",
    )
    p.add_argument(
        "--show-demo-password",
        action="store_true",
        help="With --list-demo-accounts, explicitly print the resolved local demo password",
    )
    p.add_argument("--schema-only", action="store_true", help="Print live PostgreSQL schema used by the seeder")
    p.add_argument("--verify-demo-auth", action="store_true", help="Verify the resolved demo password against admin.demo without printing the password")
    p.add_argument(
        "--upload-regulations",
        action="store_true",
        help="Stage regulation PDFs in MinIO; indexing remains RAG worker responsibility",
    )
    args = p.parse_args(argv)
    if args.show_demo_password and not args.list_demo_accounts:
        p.error("--show-demo-password requires --list-demo-accounts")
    if args.list_demo_accounts:
        validate_competition()
        return list_demo_accounts(show_password=args.show_demo_password)
    if args.print_load_plan:
        return print_load_plan(args.load_profile)
    if args.verify_demo_auth:
        return verify_demo_auth()

    counts = validate_competition()
    if args.validate_only:
        rows, normalize_stats, augmentation_stats, anchor = _prepare_runtime_rows(
            load_profile=args.load_profile,
            anchor_date=args.seed_anchor_date,
            presentation_scenarios=not args.no_presentation_scenarios,
        )
        print(f"Competition dataset valid against opticargo-shared=={shared_contract_version()}")
        print(f"load_profile             {args.load_profile}")
        print(f"seed_anchor_date         {anchor.isoformat()}")
        for table in TABLE_ORDER:
            print(f"runtime_{table:16s} {len(rows[table])}")
        print(f"presentation_listings    {augmentation_stats['presentation_listings']}")
        print(f"distributor_supplier     {augmentation_stats['distributor_presentation_supplier']}")
        print(f"distributor_listings     {augmentation_stats['distributor_presentation_listings']}")
        print(f"distributor_bookings     {augmentation_stats['distributor_presentation_bookings']}")
        print(f"load_listings            {augmentation_stats['load_listings']}")
        print(f"load_bookings             {augmentation_stats['load_bookings']}")
        print(f"routes_materialized      {normalize_stats['routes_materialized']}")
        return 0

    try:
        seeded, normalization, augmentation, timings, anchor = seed(
            args.profile,
            args.idempotent,
            args.schema_only,
            args.upload_regulations,
            load_profile=args.load_profile,
            anchor_date=args.seed_anchor_date,
            presentation_scenarios=not args.no_presentation_scenarios,
        )
    except (SchemaMismatch, ValueError) as exc:
        print(f"SEED_ERROR: {exc}")
        return 2
    if args.schema_only:
        return 0

    m = manifest()
    print("OptiCargo Competition Seed")
    print("=" * 29)
    for table in TABLE_ORDER:
        stats = seeded[table]
        suffix = f" (aliases={stats.unique_aliases})" if stats.unique_aliases else ""
        seconds = timings.get(table, 0.0)
        rate = (stats.processed / seconds) if seconds > 0 else 0.0
        print(
            f"{table:24s} {stats.materialized_ids}/{stats.processed}{suffix} "
            f"[{seconds:.2f}s, {rate:.0f} rows/s]"
        )
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
    print(f"load_profile             {args.load_profile}")
    print(f"seed_anchor_date         {anchor.isoformat()}")
    print(f"presentation_listings    {augmentation['presentation_listings']}")
    print(f"distributor_supplier     {augmentation['distributor_presentation_supplier']}")
    print(f"distributor_listings     {augmentation['distributor_presentation_listings']}")
    print(f"distributor_bookings     {augmentation['distributor_presentation_bookings']}")
    print(f"load_users               {augmentation['load_users']}")
    print(f"load_suppliers           {augmentation['load_suppliers']}")
    print(f"load_voyages             {augmentation['load_voyages']}")
    print(f"load_listings            {augmentation['load_listings']}")
    print(f"load_bookings            {augmentation['load_bookings']}")
    print(f"seed_seconds_total       {timings.get('total', 0.0):.2f}")
    print(f"shared_contract          {shared_contract_version()}")
    print(f"password_scheme          {password_scheme()}")
    print(f"demo_password_source     {demo_password_source()}")
    print(f"demo_password_length     {len(demo_password())}")
    print(f"demo_accounts            {len(DEMO_ACCOUNTS)} deterministic presentation accounts")
    print("demo_credentials         python -m opticargo_data.seed --list-demo-accounts")
    print("demo_password            from OPTICARGO_DEMO_PASSWORD (default documented for local demo only)")
    print("Seed completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
