import json
import uuid
import random
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path("D:/PROYEK ML DAN AI/OptiCargo/opticargo-data/dataset")

def generate_voyages():
    # Load ships and routes
    with open(BASE_DIR / "ships" / "ships.json", "r") as f:
        ships = json.load(f)
    with open(BASE_DIR / "routes" / "routes.json", "r") as f:
        routes = json.load(f)

    # Filter active routes
    active_routes = [r for r in routes if r.get("is_active", True)]
    
    voyages = []
    base_date = datetime.utcnow()

    # Provide a fixed seed for reproducible results if needed, or random
    random.seed(42)

    for ship in ships:
        ship_id = ship["id"]
        total_capacity = float(ship["deadweight_tonnage"])
        
        # Select 2 to 4 random routes for this ship
        num_voyages = random.randint(2, 4)
        selected_routes = random.sample(active_routes, num_voyages)
        
        for i, route in enumerate(selected_routes):
            route_id = route["id"]
            estimated_days = route["estimated_days"]
            
            # Stagger departures: e.g. one in transit, others scheduled in future
            days_offset = random.randint(-2, 14)
            departure_date = base_date + timedelta(days=days_offset)
            arrival_date = departure_date + timedelta(days=estimated_days)
            
            status = "in_transit" if departure_date <= base_date <= arrival_date else "scheduled"
            if base_date > arrival_date:
                status = "completed"
            
            # Backhaul signal: used_capacity is between 20% and 80% of total
            used_capacity = total_capacity * random.uniform(0.2, 0.8)
            remaining_capacity = total_capacity - used_capacity
            
            voyages.append({
                "id": str(uuid.uuid4()),
                "ship_id": ship_id,
                "route_id": route_id,
                "departure_date": departure_date.isoformat() + "Z",
                "arrival_date": arrival_date.isoformat() + "Z",
                "total_capacity_ton": round(total_capacity, 2),
                "used_capacity_ton": round(used_capacity, 2),
                "remaining_capacity_ton": round(remaining_capacity, 2),
                "status": status,
                "waypoints": [],
                "created_at": base_date.isoformat() + "Z"
            })

    voyages_dir = BASE_DIR / "voyages"
    voyages_dir.mkdir(exist_ok=True)
    
    out_file = voyages_dir / "voyages.json"
    with open(out_file, "w") as f:
        json.dump(voyages, f, indent=2)

    print(f"Berhasil men-generate {len(voyages)} voyages untuk {len(ships)} kapal.")
    print(f"Disimpan di {out_file}")

if __name__ == "__main__":
    generate_voyages()
