from opticargo_data.contracts import shared_contract_version, validate_all
from opticargo_data.io import load
from opticargo_data.normalize import prepare_seed_rows


def test_shared_version_is_locked():
    assert shared_contract_version() == "1.0.0"


def test_all_seed_rows_satisfy_shared_create_contracts():
    names = [
        "users", "ports", "commodities", "routes", "ships", "suppliers",
        "voyages", "cargo_capacities", "cargo_listings", "bookings",
    ]
    source = {name: load(name) for name in names}
    prepared, _ = prepare_seed_rows(source)
    validate_all(prepared)
