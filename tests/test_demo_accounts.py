from opticargo_data.demo_accounts import DEMO_ACCOUNTS
from opticargo_data.io import load


EXPECTED = {
    "admin": ("admin.demo", "admin@demo.opticargo.id"),
    "operator_kapal": ("operator.demo", "operator@demo.opticargo.id"),
    "distributor": ("distributor.demo", "distributor@demo.opticargo.id"),
    "umkm": ("umkm.demo", "umkm@demo.opticargo.id"),
    "pengepul": ("pengepul.demo", "pengepul@demo.opticargo.id"),
    "koperasi": ("koperasi.demo", "koperasi@demo.opticargo.id"),
    "pelabuhan": ("pelabuhan.demo", "pelabuhan@demo.opticargo.id"),
    "pemerintah": ("pemerintah.demo", "pemerintah@demo.opticargo.id"),
    "eksportir": ("eksportir.demo", "eksportir@demo.opticargo.id"),
}


def test_exactly_one_deterministic_demo_account_per_role():
    assert len(DEMO_ACCOUNTS) == 9
    assert {row["role"] for row in DEMO_ACCOUNTS} == set(EXPECTED)

    users = load("users")
    by_username = {row["username"]: row for row in users}

    for role, (username, email) in EXPECTED.items():
        row = by_username[username]
        assert row["role"] == role
        assert row["email"] == email
        assert row["account_status"] == "active"


def test_umkm_demo_keeps_supplier_listing_and_booking_relations():
    users = load("users")
    suppliers = load("suppliers")
    listings = load("cargo_listings")
    bookings = load("bookings")

    umkm = next(row for row in users if row["username"] == "umkm.demo")
    supplier = next(row for row in suppliers if row["user_id"] == umkm["id"])

    supplier_listing_ids = {
        row["id"] for row in listings if row["supplier_id"] == supplier["id"]
    }

    assert supplier_listing_ids
    assert any(
        row["cargo_listing_id"] in supplier_listing_ids
        for row in bookings
    )
