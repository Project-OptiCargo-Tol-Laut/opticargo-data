from opticargo_data.io import load
from opticargo_data.normalize import ROUTE_BUSINESS_KEY, canonicalize_routes, prepare_seed_rows


def test_routes_are_canonical_for_gateway_unique_key():
    source = load("routes")
    canonical, aliases = canonicalize_routes(source)
    keys = [tuple(row[field] for field in ROUTE_BUSINESS_KEY) for row in canonical]
    assert len(keys) == len(set(keys))
    assert len(canonical) < len(source)
    assert sum(src != dst for src, dst in aliases.items()) == len(source) - len(canonical)


def test_voyage_route_ids_are_remapped_to_materialized_routes():
    names = [
        "users", "ports", "commodities", "routes", "ships", "suppliers",
        "voyages", "cargo_capacities", "cargo_listings", "bookings",
    ]
    source = {name: load(name) for name in names}
    prepared, stats = prepare_seed_rows(source)
    route_ids = {row["id"] for row in prepared["routes"]}
    assert all(voyage["route_id"] in route_ids for voyage in prepared["voyages"])
    assert stats["route_aliases"] == len(source["routes"]) - len(prepared["routes"])
