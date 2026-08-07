from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


ROUTE_BUSINESS_KEY = ("origin_port_id", "destination_port_id", "route_type")
FOOD_CATEGORIES = {
    "kebutuhan pokok",
    "hasil laut",
    "hasil perkebunan",
    "rempah",
    "pertanian",
    "hasil pertanian",
}


def _route_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    """Choose one deterministic route for the Gateway's unique business key."""

    distance = row.get("distance_nm")
    days = row.get("estimated_days")
    return (
        float(distance) if distance is not None else float("inf"),
        float(days) if days is not None else float("inf"),
        str(row.get("route_id") or ""),
        str(row.get("id") or ""),
    )


def canonicalize_routes(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(row.get(field) for field in ROUTE_BUSINESS_KEY)
        grouped[key].append(row)

    canonical: list[dict[str, Any]] = []
    aliases: dict[str, str] = {}
    for variants in grouped.values():
        winner = min(variants, key=_route_rank)
        canonical.append(deepcopy(winner))
        winner_id = str(winner["id"])
        for variant in variants:
            aliases[str(variant["id"])] = winner_id

    canonical.sort(key=lambda row: str(row.get("id") or ""))
    return canonical, aliases


def commodity_cargo_type(commodity: dict[str, Any]) -> str:
    requirements = commodity.get("special_requirements") or {}
    if commodity.get("is_perishable") or requirements.get("temperature_control"):
        return "frozen"
    category = str(commodity.get("category") or "").strip().casefold()
    if category in FOOD_CATEGORIES:
        return "dry_food"
    return "general"


def _enrich_cargo_listings(prepared: dict[str, list[dict[str, Any]]]) -> int:
    commodities = {str(row["id"]): row for row in prepared.get("commodities", [])}
    enriched = 0
    for listing in prepared.get("cargo_listings", []):
        commodity = commodities.get(str(listing.get("commodity_id")))
        if commodity is None:
            continue
        # Gateway persistence currently requires certifications although the
        # opticargo-shared CargoListingCreate v1.0.0 does not expose that field.
        # A demo listing claims the same certifications required by its commodity,
        # which makes matching constraints meaningful rather than filling an
        # arbitrary empty JSON value.
        listing.setdefault("certifications", list(commodity.get("certifications_required") or []))
        listing.setdefault("cargo_type", commodity_cargo_type(commodity))
        enriched += 1
    return enriched


def _booking_ref(booking_id: str) -> str:
    compact = booking_id.replace("-", "").upper()
    return f"OCG-DEMO-{compact[:16]}"


def _enrich_bookings(prepared: dict[str, list[dict[str, Any]]]) -> int:
    suppliers = {str(row["id"]): row for row in prepared.get("suppliers", [])}
    listings = {str(row["id"]): row for row in prepared.get("cargo_listings", [])}
    enriched = 0
    for booking in prepared.get("bookings", []):
        listing = listings.get(str(booking.get("cargo_listing_id")))
        supplier = suppliers.get(str(listing.get("supplier_id"))) if listing else None
        if supplier:
            booking.setdefault("created_by", supplier.get("user_id"))
        booking.setdefault("booking_ref", _booking_ref(str(booking["id"])))
        booking.setdefault("booking_date", booking.get("created_at") or "2026-01-01T00:00:00Z")
        enriched += 1
    return enriched


def prepare_seed_rows(
    rows: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    """Build a shared-valid and Gateway-persistable seed view.

    Source artifacts stay immutable. Public domain semantics are validated against
    opticargo-shared; Gateway-only persistence fields are derived deterministically
    here from existing domain data.
    """

    prepared = {name: deepcopy(items) for name, items in rows.items()}
    routes, route_aliases = canonicalize_routes(prepared["routes"])
    prepared["routes"] = routes

    remapped = 0
    for voyage in prepared.get("voyages", []):
        source_id = str(voyage.get("route_id"))
        target_id = route_aliases.get(source_id, source_id)
        if target_id != source_id:
            voyage["route_id"] = target_id
            remapped += 1

    listings_enriched = _enrich_cargo_listings(prepared)
    bookings_enriched = _enrich_bookings(prepared)

    stats = {
        "routes_source": len(rows["routes"]),
        "routes_materialized": len(routes),
        "route_aliases": sum(1 for src, dst in route_aliases.items() if src != dst),
        "voyage_route_remaps": remapped,
        "cargo_listings_enriched": listings_enriched,
        "bookings_enriched": bookings_enriched,
    }
    return prepared, stats
