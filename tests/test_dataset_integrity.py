from opticargo_data.validate import validate_competition
from opticargo_data.io import load

def test_competition_dataset_integrity():
    counts=validate_competition()
    assert counts["bookings"] >= 500
    assert counts["ships"] >= 10
    assert counts["suppliers"] >= 30
    assert counts["routes"] >= 3
    assert counts["commodities"] >= 3

def test_required_demo_roles_exist():
    roles={u["role"] for u in load("users")}
    assert {"admin","operator_kapal","umkm"}.issubset(roles)
    assert {"admin","operator_kapal","distributor","umkm","pengepul","koperasi","pelabuhan","pemerintah","eksportir"}.issubset(roles)

def test_supplier_ids_and_user_ids_are_unique():
    rows=load("suppliers")
    assert len({r["id"] for r in rows}) == len(rows)
    assert len({r["user_id"] for r in rows}) == len(rows)
