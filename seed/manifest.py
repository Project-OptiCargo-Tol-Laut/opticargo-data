"""Deterministic dataset manifest and checksum verification."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opticargo_shared import __version__ as shared_version
from opticargo_shared.dataset import DatasetManifest

DATASET_DIR = Path(__file__).resolve().parents[1] / "dataset"
MANIFEST_PATH = DATASET_DIR / "manifest.json"
DATASET_VERSION = "opticargo-data-v1"
DATASET_CREATED_AT = datetime(2026, 7, 27, tzinfo=UTC)
JSON_ASSETS = (
    "commodities/commodities.json",
    "ports/ports.json",
    "regulations/regulations.json",
    "routes/routes.json",
    "ships/ships.json",
    "suppliers/suppliers.json",
    "voyages/voyages.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def _asset_profile(
    relative_path: str, regulations: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if relative_path.startswith("regulations/"):
        regulation = regulations.get(Path(relative_path).name)
        return {
            "source_type": "official",
            "source": regulation.get("source_url")
            if regulation
            else "opticargo regulation metadata",
            "is_synthetic": False,
            "generator_seed": None,
        }
    if relative_path == "routes/routes.json":
        return {
            "source_type": "official-derived",
            "source": "PM_29_2018_Tarif_PSO_Angkutan_Barang_Laut.pdf",
            "is_synthetic": False,
            "generator_seed": None,
        }
    if relative_path == "ports/ports.json":
        return {
            "source_type": "curated",
            "source": "OptiCargo Tol Laut port reference",
            "is_synthetic": False,
            "generator_seed": None,
        }
    if relative_path in {
        "ships/ships.json",
        "suppliers/suppliers.json",
        "voyages/voyages.json",
    }:
        return {
            "source_type": "synthetic",
            "source": f"scripts/generators/generate_{Path(relative_path).stem}.py",
            "is_synthetic": True,
            "generator_seed": 42,
        }
    return {
        "source_type": "curated-synthetic",
        "source": "OptiCargo curated commodity baseline",
        "is_synthetic": True,
        "generator_seed": None,
    }


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Dataset asset must be a list of objects: {path}")
    return value


def build_manifest(dataset_dir: Path = DATASET_DIR) -> dict[str, Any]:
    regulations_data = _load_json_list(dataset_dir / "regulations" / "regulations.json")
    regulations = {str(item["filename"]): item for item in regulations_data}
    relative_assets = list(JSON_ASSETS)
    relative_assets.extend(f"regulations/{name}" for name in sorted(regulations))

    assets: list[dict[str, Any]] = []
    combined = hashlib.sha256()
    total_records = 0
    for relative_path in sorted(relative_assets):
        path = dataset_dir / relative_path
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(
                f"Dataset asset is missing or empty: {relative_path}"
            )
        record_count: int | None = None
        if path.suffix.lower() == ".json":
            record_count = len(_load_json_list(path))
            total_records += record_count
        checksum = sha256_file(path)
        combined.update(relative_path.encode("utf-8"))
        combined.update(b"\0")
        combined.update(checksum.encode("ascii"))
        combined.update(b"\0")
        assets.append(
            {
                "path": relative_path,
                "sha256": checksum,
                "size_bytes": path.stat().st_size,
                "record_count": record_count,
                **_asset_profile(relative_path, regulations),
            }
        )

    source_references = sorted(
        {str(item["source_url"]) for item in regulations_data if item.get("source_url")}
    )
    contract = DatasetManifest(
        dataset_name="opticargo-operational-and-regulation-baseline",
        dataset_version=DATASET_VERSION,
        created_at=DATASET_CREATED_AT,
        source_type="mixed-official-curated-synthetic",
        source_references=source_references,
        is_synthetic=True,
        record_count=total_records,
        schema_package_version=shared_version,
        checksum=f"sha256:{combined.hexdigest()}",
    )
    return {
        "manifest_schema_version": 1,
        **contract.model_dump(mode="json"),
        "contains_synthetic_data": True,
        "assets": assets,
    }


def serialized_manifest(dataset_dir: Path = DATASET_DIR) -> str:
    return (
        json.dumps(
            build_manifest(dataset_dir), indent=2, sort_keys=True, ensure_ascii=False
        )
        + "\n"
    )


def check_manifest(
    dataset_dir: Path = DATASET_DIR,
    manifest_path: Path | None = None,
) -> list[str]:
    path = manifest_path or dataset_dir / "manifest.json"
    if not path.is_file():
        return [f"dataset manifest is missing: {path}"]
    expected = serialized_manifest(dataset_dir)
    actual = path.read_text(encoding="utf-8")
    return [] if actual == expected else ["dataset manifest is stale or non-canonical"]


def write_manifest(
    dataset_dir: Path = DATASET_DIR, manifest_path: Path | None = None
) -> Path:
    path = manifest_path or dataset_dir / "manifest.json"
    path.write_text(serialized_manifest(dataset_dir), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        problems = check_manifest()
        if problems:
            for problem in problems:
                print(f"[FAIL] {problem}")
            raise SystemExit(1)
        print("[OK] Dataset manifest is current and checksums match.")
        return
    print(f"[OK] Wrote dataset manifest: {write_manifest()}")


if __name__ == "__main__":
    main()
