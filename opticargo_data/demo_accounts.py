from __future__ import annotations

from typing import Final

# Canonical deterministic presentation accounts.
#
# Passwords are intentionally NOT stored here. The seeder resolves one local-demo
# password from OPTICARGO_DEMO_PASSWORD (default: OptiCargoDemo123!) and hashes it
# at seed time with the same Argon2 contract used by the Gateway.
DEMO_ACCOUNTS: Final[tuple[dict[str, str], ...]] = (
    {
        "role": "admin",
        "username": "admin.demo",
        "email": "admin@demo.opticargo.id",
    },
    {
        "role": "operator_kapal",
        "username": "operator.demo",
        "email": "operator@demo.opticargo.id",
    },
    {
        "role": "distributor",
        "username": "distributor.demo",
        "email": "distributor@demo.opticargo.id",
    },
    {
        "role": "umkm",
        "username": "umkm.demo",
        "email": "umkm@demo.opticargo.id",
    },
    {
        "role": "pengepul",
        "username": "pengepul.demo",
        "email": "pengepul@demo.opticargo.id",
    },
    {
        "role": "koperasi",
        "username": "koperasi.demo",
        "email": "koperasi@demo.opticargo.id",
    },
    {
        "role": "pelabuhan",
        "username": "pelabuhan.demo",
        "email": "pelabuhan@demo.opticargo.id",
    },
    {
        "role": "pemerintah",
        "username": "pemerintah.demo",
        "email": "pemerintah@demo.opticargo.id",
    },
    {
        "role": "eksportir",
        "username": "eksportir.demo",
        "email": "eksportir@demo.opticargo.id",
    },
)


def demo_account_usernames() -> set[str]:
    return {row["username"] for row in DEMO_ACCOUNTS}


def validate_demo_accounts(users: list[dict]) -> None:
    """Raise ValueError if the deterministic presentation-account contract drifts."""
    by_username = {str(row.get("username")): row for row in users}
    problems: list[str] = []

    for expected in DEMO_ACCOUNTS:
        actual = by_username.get(expected["username"])
        if actual is None:
            problems.append(f"missing {expected['username']}")
            continue
        for field in ("role", "email"):
            if str(actual.get(field)) != expected[field]:
                problems.append(
                    f"{expected['username']} {field}={actual.get(field)!r}, "
                    f"expected {expected[field]!r}"
                )
        if str(actual.get("account_status")) != "active":
            problems.append(
                f"{expected['username']} account_status={actual.get('account_status')!r}, "
                "expected 'active'"
            )

    if problems:
        raise ValueError("Demo account contract invalid: " + "; ".join(problems))
