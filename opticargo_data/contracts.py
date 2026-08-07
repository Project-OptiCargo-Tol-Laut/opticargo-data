from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from opticargo_shared.dataset import DatasetManifest, RecordProvenance, ValidationStatus
from opticargo_shared.models import (
    BookingCreate,
    CargoCapacityCreate,
    CargoListingCreate,
    CommodityCreate,
    PortCreate,
    RouteCreate,
    ShipCreate,
    SupplierCreate,
    UserCreate,
    VoyageCreate,
)
from opticargo_shared.version import __version__ as shared_version


class SharedContractError(RuntimeError):
    pass


MODELS: dict[str, type[BaseModel]] = {
    "users": UserCreate,
    "ports": PortCreate,
    "commodities": CommodityCreate,
    "routes": RouteCreate,
    "ships": ShipCreate,
    "suppliers": SupplierCreate,
    "voyages": VoyageCreate,
    "cargo_capacities": CargoCapacityCreate,
    "cargo_listings": CargoListingCreate,
    "bookings": BookingCreate,
}


def _contract_payload(model: type[BaseModel], row: dict[str, Any]) -> dict[str, Any]:
    """Project a seed row to the public shared contract.

    Seed rows intentionally contain persistence/dataset metadata (id, timestamps,
    version, synthetic provenance and a small number of Gateway-only columns).
    The shared Create contracts use ``extra='forbid'``, so validate exactly the
    fields owned by the public contract rather than weakening shared strictness.
    """

    return {name: row[name] for name in model.model_fields if name in row}


def validate_rows(table: str, rows: list[dict[str, Any]]) -> None:
    model = MODELS.get(table)
    if model is None:
        return
    for index, row in enumerate(rows):
        try:
            model.model_validate(_contract_payload(model, row))
        except ValidationError as exc:
            rid = row.get("id", f"index:{index}")
            raise SharedContractError(
                f"{table}[{rid}] does not satisfy opticargo-shared=={shared_version}: {exc}"
            ) from exc


def validate_all(rows: dict[str, list[dict[str, Any]]]) -> None:
    for table, items in rows.items():
        validate_rows(table, items)


def validate_provenance(rows: dict[str, list[dict[str, Any]]], *, fallback_timestamp: str = "2026-07-26T00:00:00Z") -> None:
    """Validate the data-repo provenance convention using the shared schema.

    The Gateway tables do not persist these fields, but PRD data governance still
    requires synthetic/provenance metadata in the source dataset.
    """

    for table, items in rows.items():
        for index, row in enumerate(items):
            if "is_synthetic" not in row and "provenance" not in row:
                continue
            created = row.get("created_at") or row.get("updated_at") or fallback_timestamp
            RecordProvenance.model_validate(
                {
                    "source": str(row.get("provenance") or f"opticargo-data:{table}"),
                    "collected_or_generated_at": created,
                    "transformation_version": "opticargo-data-v3.1.0",
                    "is_synthetic": bool(row.get("is_synthetic", False)),
                    "generator_seed": 20260726 if row.get("is_synthetic") else None,
                    "original_external_identifier": None,
                    "validation_status": ValidationStatus.valid,
                }
            )


def validate_shared_manifest(local_manifest: dict[str, Any], checksum: str) -> DatasetManifest:
    counts = local_manifest.get("counts", {})
    total = sum(int(value) for value in counts.values())
    created_at = local_manifest.get("generated_at") or "2026-07-26T00:00:00Z"
    return DatasetManifest.model_validate(
        {
            "dataset_name": local_manifest.get("dataset_name", "opticargo-competition"),
            "dataset_version": local_manifest.get("dataset_version", "unknown"),
            "created_at": created_at,
            "source_type": "mixed-curated-synthetic",
            "source_references": [
                "opticargo-data:dataset",
                "opticargo-shared==1.0.0",
            ],
            "is_synthetic": True,
            "record_count": total,
            "schema_package_version": shared_version,
            "checksum": checksum,
        }
    )


def shared_contract_version() -> str:
    return shared_version
