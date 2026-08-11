from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid5


LOAD_NAMESPACE = UUID("6f95cfb1-ec3b-4ffd-8c66-0ec6ca6e566d")
DEFAULT_ANCHOR_DATE = date(2026, 8, 11)


@dataclass(frozen=True)
class LoadProfile:
    users: int
    suppliers: int
    voyages: int
    cargo_listings: int
    bookings: int


LOAD_PROFILES: dict[str, LoadProfile] = {
    "none": LoadProfile(0, 0, 0, 0, 0),
    # Enough to exercise pagination/filtering without making a laptop seed excessively slow.
    "small": LoadProfile(250, 200, 200, 2_000, 5_000),
    # Recommended local performance profile. Roughly 35k additional transaction/domain rows.
    "medium": LoadProfile(1_000, 800, 800, 8_000, 25_000),
    # Stress profile. The schema-aware idempotent upsert is intentionally conservative,
    # so this profile can take significant time on a laptop/PostgreSQL Docker volume.
    "large": LoadProfile(3_000, 2_500, 2_500, 25_000, 100_000),
}


ROLE_CYCLE = (
    "distributor",
    "pengepul",
    "koperasi",
    "pelabuhan",
    "pemerintah",
    "eksportir",
    "operator_kapal",
    "umkm",
)


def _uuid(kind: str, index: int | str) -> str:
    return str(uuid5(LOAD_NAMESPACE, f"{kind}:{index}"))


def parse_anchor_date(value: str | date | None) -> date:
    if value is None:
        return DEFAULT_ANCHOR_DATE
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"Invalid seed anchor date {value!r}; expected YYYY-MM-DD") from exc


def load_plan(profile: str) -> LoadProfile:
    try:
        return LOAD_PROFILES[profile]
    except KeyError as exc:
        raise ValueError(
            f"Unknown load profile {profile!r}; choose one of {', '.join(LOAD_PROFILES)}"
        ) from exc


def _created_at(anchor: date) -> str:
    return datetime.combine(anchor, time.min, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def add_presentation_scenarios(
    source_rows: dict[str, list[dict[str, Any]]],
    *,
    anchor_date: date,
    listing_count: int = 5,
) -> dict[str, int]:
    """Add deterministic, guaranteed-match UMKM listings for FE/E2E demos.

    Existing source JSON remains unchanged. Runtime rows are added in memory and use
    existing scheduled/delayed voyages so `/matching/voyage-options` has meaningful
    candidates instead of relying on a coincidental synthetic route/date overlap.
    """

    if listing_count <= 0:
        return {"presentation_listings": 0}

    users = {row["username"]: row for row in source_rows["users"]}
    umkm_user = users.get("umkm.demo")
    if umkm_user is None:
        raise ValueError("presentation scenario requires deterministic user umkm.demo")

    supplier = next(
        (row for row in source_rows["suppliers"] if row.get("user_id") == umkm_user["id"]),
        None,
    )
    if supplier is None:
        raise ValueError("presentation scenario requires supplier owned by umkm.demo")

    routes = {str(row["id"]): row for row in source_rows["routes"]}
    candidates: list[tuple[datetime, dict[str, Any], dict[str, Any]]] = []
    anchor_dt = datetime.combine(anchor_date, time.min, tzinfo=timezone.utc)
    for voyage in source_rows["voyages"]:
        if voyage.get("status") not in {"scheduled", "delayed"}:
            continue
        route = routes.get(str(voyage.get("route_id")))
        if not route or not route.get("is_active", True):
            continue
        departure = datetime.fromisoformat(str(voyage["departure_date"]).replace("Z", "+00:00"))
        if departure < anchor_dt:
            continue
        if Decimal(str(voyage.get("remaining_capacity_ton", "0"))) <= 5:
            continue
        candidates.append((departure, voyage, route))

    candidates.sort(key=lambda item: (item[0], str(item[1]["id"])))
    if not candidates:
        raise ValueError("presentation scenario requires at least one future scheduled/delayed voyage")

    commodity_ids = list(supplier.get("commodity_ids") or [])
    if not commodity_ids:
        commodity_ids = [row["id"] for row in source_rows["commodities"]]
    if not commodity_ids:
        raise ValueError("presentation scenario requires at least one commodity")

    existing_ids = {str(row["id"]) for row in source_rows["cargo_listings"]}
    added = 0
    for index in range(listing_count):
        departure, voyage, route = candidates[index % len(candidates)]
        listing_id = _uuid("presentation-umkm-listing", index)
        if listing_id in existing_ids:
            continue
        remaining = Decimal(str(voyage["remaining_capacity_ton"]))
        volume = min(Decimal("5") + Decimal(index * 3), max(Decimal("1"), remaining * Decimal("0.08")))
        row = {
            "id": listing_id,
            "supplier_id": supplier["id"],
            "commodity_id": commodity_ids[index % len(commodity_ids)],
            "volume_ton": str(volume.quantize(Decimal("0.1"))),
            "available_from": (departure.date() - timedelta(days=2)).isoformat(),
            "available_until": (departure.date() + timedelta(days=1)).isoformat(),
            "origin_port_id": route["origin_port_id"],
            "destination_port_id": route["destination_port_id"],
            "asking_price_per_ton": str(2_100_000 + index * 175_000),
            "status": "open",
            "is_synthetic": True,
            "provenance": "opticargo-data:presentation:guaranteed-voyage-match-v1",
            "created_at": _created_at(anchor_date),
            "updated_at": _created_at(anchor_date),
        }
        source_rows["cargo_listings"].append(row)
        existing_ids.add(listing_id)
        added += 1

    return {"presentation_listings": added}


def apply_load_profile(
    source_rows: dict[str, list[dict[str, Any]]],
    *,
    profile: str,
    anchor_date: date,
) -> dict[str, int]:
    """Expand the competition seed deterministically for local load/performance testing.

    The generator deliberately reuses curated ports/routes/commodities and existing
    operator-owned ships. This gives realistic relational density while keeping the
    canonical geographic/regulatory datasets unchanged.
    """

    plan = load_plan(profile)
    if profile == "none":
        return {
            "load_users": 0,
            "load_suppliers": 0,
            "load_voyages": 0,
            "load_capacities": 0,
            "load_listings": 0,
            "load_bookings": 0,
        }

    if plan.suppliers > plan.users:
        raise ValueError("load profile suppliers cannot exceed users")

    created = _created_at(anchor_date)
    ports = source_rows["ports"]
    commodities = source_rows["commodities"]
    routes = [row for row in source_rows["routes"] if row.get("is_active", True)]
    ships = [row for row in source_rows["ships"] if row.get("status") == "active"]
    if not ports or not commodities or not routes or not ships:
        raise ValueError("load profile requires non-empty ports, commodities, active routes and ships")

    demo_umkm = next(row for row in source_rows["users"] if row.get("username") == "umkm.demo")
    demo_supplier = next(
        row for row in source_rows["suppliers"] if row.get("user_id") == demo_umkm["id"]
    )

    # Users backing generated suppliers are always UMKM. Remaining users cycle through
    # other roles so Admin user-management pagination/filtering has realistic diversity.
    generated_user_ids: list[str] = []
    for index in range(plan.users):
        user_id = _uuid("load-user", index)
        generated_user_ids.append(user_id)
        if index < plan.suppliers:
            role = "umkm"
            username = f"load.umkm.{index + 1:05d}"
            company = f"UMKM Load Nusantara {index + 1:05d}"
        else:
            role = ROLE_CYCLE[(index - plan.suppliers) % len(ROLE_CYCLE)]
            username = f"load.{role}.{index + 1:05d}"
            company = f"OptiCargo Load {role.replace('_', ' ').title()} {index + 1:05d}"
        source_rows["users"].append(
            {
                "id": user_id,
                "username": username,
                "email": f"{username}@load.opticargo.id",
                "role": role,
                "account_status": "active",
                "company_name": company,
                "phone": f"+62877{index + 1:07d}",
                "is_synthetic": True,
                "provenance": f"opticargo-data:load:{profile}:user-v1",
                "created_at": created,
                "updated_at": created,
            }
        )

    generated_suppliers: list[dict[str, Any]] = []
    for index in range(plan.suppliers):
        port = ports[index % len(ports)]
        commodity_a = commodities[index % len(commodities)]
        commodity_b = commodities[(index * 7 + 3) % len(commodities)]
        supplier = {
            "id": _uuid("load-supplier", index),
            "user_id": generated_user_ids[index],
            "business_name": f"Supplier Load Nusantara {index + 1:05d}",
            "port_id": port["id"],
            "commodity_ids": list(dict.fromkeys([commodity_a["id"], commodity_b["id"]])),
            "avg_monthly_volume_ton": str(50 + (index % 450)),
            "rating": round(3.0 + ((index % 20) / 10), 1),
            "verified": index % 4 != 0,
            "address": f"Kawasan Logistik Load {port['name']} Blok {index % 100 + 1}",
            "is_synthetic": True,
            "provenance": f"opticargo-data:load:{profile}:supplier-v1",
            "created_at": created,
            "updated_at": created,
        }
        source_rows["suppliers"].append(supplier)
        generated_suppliers.append(supplier)

    generated_voyages: list[dict[str, Any]] = []
    generated_capacities: list[dict[str, Any]] = []
    route_by_voyage: dict[str, dict[str, Any]] = {}
    for index in range(plan.voyages):
        route = routes[(index * 17 + index // max(1, len(routes))) % len(routes)]
        ship = ships[index % len(ships)]
        departure = datetime.combine(anchor_date, time(2, 0), tzinfo=timezone.utc) + timedelta(
            days=2 + (index % 180), hours=(index % 4) * 3
        )
        travel_days = max(1, int(route.get("estimated_days") or 1))
        arrival = departure + timedelta(days=travel_days, hours=index % 8)
        status_slot = index % 20
        if status_slot == 0:
            status = "delayed"
        elif status_slot == 1:
            status = "completed"
        elif status_slot == 2:
            status = "in_transit"
        else:
            status = "scheduled"
        total = Decimal(900 + (index % 18) * 100)
        used_ratio = Decimal(5 + (index % 30)) / Decimal(100)
        used = (total * used_ratio).quantize(Decimal("0.1"))
        remaining = total - used
        voyage_id = _uuid("load-voyage", index)
        voyage = {
            "id": voyage_id,
            "ship_id": ship["id"],
            "route_id": route["id"],
            "departure_date": departure.isoformat().replace("+00:00", "Z"),
            "arrival_date": arrival.isoformat().replace("+00:00", "Z"),
            "total_capacity_ton": str(total),
            "used_capacity_ton": str(used),
            "remaining_capacity_ton": str(remaining),
            "status": status,
            "waypoints": [],
            "is_synthetic": True,
            "provenance": f"opticargo-data:load:{profile}:voyage-v1",
            "created_at": created,
            "updated_at": created,
        }
        source_rows["voyages"].append(voyage)
        generated_voyages.append(voyage)
        route_by_voyage[voyage_id] = route

        cargo_types = ["general", "dry_food"]
        if index % 3 == 0:
            cargo_types.append("frozen")
        capacity = {
            "id": _uuid("load-capacity", index),
            "voyage_id": voyage_id,
            "available_weight_ton": str(remaining),
            "available_volume_m3": str((remaining * Decimal("9.5")).quantize(Decimal("0.1"))),
            "cargo_type_allowed": cargo_types,
            "temperature_range": {"min_celsius": "-20" if "frozen" in cargo_types else "5", "max_celsius": "25"},
            "is_synthetic": True,
            "provenance": f"opticargo-data:load:{profile}:capacity-v1",
            "created_at": created,
            "updated_at": created,
        }
        source_rows["cargo_capacities"].append(capacity)
        generated_capacities.append(capacity)

    bookable_voyages = [v for v in generated_voyages if v["status"] in {"scheduled", "delayed"}]
    if not bookable_voyages:
        raise ValueError("load profile failed to generate bookable voyages")

    listing_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for index in range(plan.cargo_listings):
        voyage = bookable_voyages[index % len(bookable_voyages)]
        route = route_by_voyage[voyage["id"]]
        departure = datetime.fromisoformat(voyage["departure_date"].replace("Z", "+00:00"))
        # 20% of load listings belong to umkm.demo so the role can exercise
        # pagination/filtering/recommendation performance directly from the FE.
        if index % 5 == 0:
            supplier = demo_supplier
        else:
            supplier = generated_suppliers[index % len(generated_suppliers)]
        commodity = commodities[(index * 11 + 5) % len(commodities)]
        volume = Decimal(2 + (index % 60)) + Decimal((index % 4) * 25) / Decimal(100)
        status_slot = index % 20
        if status_slot < 12:
            status = "open"
        elif status_slot < 16:
            status = "matched"
        elif status_slot < 18:
            status = "closed"
        else:
            status = "expired"
        listing = {
            "id": _uuid("load-listing", index),
            "supplier_id": supplier["id"],
            "commodity_id": commodity["id"],
            "volume_ton": str(volume),
            "available_from": (departure.date() - timedelta(days=3)).isoformat(),
            "available_until": (departure.date() + timedelta(days=2)).isoformat(),
            "origin_port_id": route["origin_port_id"],
            "destination_port_id": route["destination_port_id"],
            "asking_price_per_ton": str(1_500_000 + (index % 18) * 125_000),
            "status": status,
            "is_synthetic": True,
            "provenance": f"opticargo-data:load:{profile}:listing-v1",
            "created_at": created,
            "updated_at": created,
        }
        source_rows["cargo_listings"].append(listing)
        listing_pairs.append((listing, voyage))

    booking_statuses = ("pending", "confirmed", "in_progress", "completed", "cancelled")
    for index in range(plan.bookings):
        listing, voyage = listing_pairs[index % len(listing_pairs)]
        repetition = index // len(listing_pairs)
        fraction = (Decimal("0.15"), Decimal("0.20"), Decimal("0.25"))[repetition % 3]
        booked = (Decimal(str(listing["volume_ton"])) * fraction).quantize(Decimal("0.1"))
        booked = max(booked, Decimal("0.1"))
        booking_date = datetime.combine(anchor_date, time.min, tzinfo=timezone.utc) - timedelta(
            days=index % 180, hours=index % 24
        )
        status = booking_statuses[index % len(booking_statuses)]
        confirmation_date = None
        if status in {"confirmed", "in_progress", "completed"}:
            confirmation_date = (booking_date + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        booking = {
            "id": _uuid("load-booking", index),
            "voyage_id": voyage["id"],
            "cargo_listing_id": listing["id"],
            "recommendation_id": None,
            "booked_volume_ton": str(booked),
            "agreed_price_per_ton": listing["asking_price_per_ton"],
            "status": status,
            "booking_date": booking_date.isoformat().replace("+00:00", "Z"),
            "confirmation_date": confirmation_date,
            "is_synthetic": True,
            "provenance": f"opticargo-data:load:{profile}:booking-v1",
            "created_at": booking_date.isoformat().replace("+00:00", "Z"),
            "updated_at": (booking_date + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        }
        source_rows["bookings"].append(booking)

    return {
        "load_users": plan.users,
        "load_suppliers": plan.suppliers,
        "load_voyages": plan.voyages,
        "load_capacities": plan.voyages,
        "load_listings": plan.cargo_listings,
        "load_bookings": plan.bookings,
    }


def build_augmented_rows(
    base_rows: dict[str, list[dict[str, Any]]],
    *,
    load_profile: str = "none",
    anchor_date: date = DEFAULT_ANCHOR_DATE,
    presentation_scenarios: bool = True,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    rows = {name: deepcopy(items) for name, items in base_rows.items()}
    stats: dict[str, int] = {}
    if presentation_scenarios:
        stats.update(add_presentation_scenarios(rows, anchor_date=anchor_date))
    else:
        stats["presentation_listings"] = 0
    stats.update(apply_load_profile(rows, profile=load_profile, anchor_date=anchor_date))
    return rows, stats
