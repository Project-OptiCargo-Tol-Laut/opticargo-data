from __future__ import annotations
import json
from pathlib import Path
from .config import dataset_root

FILES = {
    "users": "users/users.json",
    "ports": "ports/ports.json",
    "routes": "routes/routes.json",
    "commodities": "commodities/commodities.json",
    "ships": "ships/ships.json",
    "suppliers": "suppliers/suppliers.json",
    "voyages": "voyages/voyages.json",
    "cargo_capacities": "cargo_capacities/cargo_capacities.json",
    "cargo_listings": "cargo_listings/cargo_listings.json",
    "bookings": "bookings/bookings.json",
    "regulations": "regulations/regulations.json",
}


def load(name: str):
    rel = FILES[name]
    path = dataset_root() / rel
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def manifest():
    path = dataset_root() / "manifest.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
