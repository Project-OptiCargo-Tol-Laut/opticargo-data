from __future__ import annotations

from datetime import date

from opticargo_data.contracts import validate_all, validate_provenance
from opticargo_data.io import load
from opticargo_data.load_profiles import LOAD_PROFILES, build_augmented_rows
from opticargo_data.normalize import prepare_seed_rows


TABLES = [
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


def _base():
    return {name: load(name) for name in TABLES}


def test_small_load_profile_is_deterministic_and_shared_valid():
    base = _base()
    first, stats_first = build_augmented_rows(
        base, load_profile="small", anchor_date=date(2026, 8, 11)
    )
    second, stats_second = build_augmented_rows(
        base, load_profile="small", anchor_date=date(2026, 8, 11)
    )

    assert stats_first == stats_second
    assert first["users"][-1]["id"] == second["users"][-1]["id"]
    assert first["bookings"][-1]["id"] == second["bookings"][-1]["id"]

    plan = LOAD_PROFILES["small"]
    assert len(first["users"]) == len(base["users"]) + plan.users
    assert len(first["suppliers"]) == len(base["suppliers"]) + plan.suppliers
    assert len(first["voyages"]) == len(base["voyages"]) + plan.voyages
    assert len(first["cargo_capacities"]) == len(base["cargo_capacities"]) + plan.voyages
    assert len(first["cargo_listings"]) == len(base["cargo_listings"]) + 5 + plan.cargo_listings
    assert len(first["bookings"]) == len(base["bookings"]) + plan.bookings

    prepared, _ = prepare_seed_rows(first)
    validate_all(prepared)
    validate_provenance(first)


def test_umkm_demo_gets_guaranteed_open_matching_listings():
    base = _base()
    augmented, stats = build_augmented_rows(
        base, load_profile="none", anchor_date=date(2026, 8, 11)
    )
    assert stats["presentation_listings"] == 5

    umkm = next(row for row in augmented["users"] if row["username"] == "umkm.demo")
    supplier = next(row for row in augmented["suppliers"] if row["user_id"] == umkm["id"])
    route_by_id = {row["id"]: row for row in augmented["routes"]}
    voyage_routes = {
        (route_by_id[v["route_id"]]["origin_port_id"], route_by_id[v["route_id"]]["destination_port_id"])
        for v in augmented["voyages"]
        if v["status"] in {"scheduled", "delayed"}
    }
    presentation = [
        row
        for row in augmented["cargo_listings"]
        if row["supplier_id"] == supplier["id"]
        and row.get("provenance") == "opticargo-data:presentation:guaranteed-voyage-match-v1"
    ]
    assert len(presentation) == 5
    assert all(row["status"] == "open" for row in presentation)
    assert all((row["origin_port_id"], row["destination_port_id"]) in voyage_routes for row in presentation)


def test_medium_profile_has_large_demo_owned_working_set():
    base = _base()
    augmented, _ = build_augmented_rows(
        base, load_profile="medium", anchor_date=date(2026, 8, 11)
    )
    umkm = next(row for row in augmented["users"] if row["username"] == "umkm.demo")
    supplier = next(row for row in augmented["suppliers"] if row["user_id"] == umkm["id"])
    own = [row for row in augmented["cargo_listings"] if row["supplier_id"] == supplier["id"]]
    # 20% of 8k load listings + base/presentation rows.
    assert len(own) >= 1_600
    assert sum(row["status"] == "open" for row in own) >= 900
