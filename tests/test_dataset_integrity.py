import json
import unittest
from pathlib import Path

class TestDatasetIntegrity(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).parent.parent / 'dataset'
        self.dataset_dir = base
        self.ports = self._load_json(base / 'ports' / 'ports.json')
        self.routes = self._load_json(base / 'routes' / 'routes.json')
        self.ships = self._load_json(base / 'ships' / 'ships.json')
        self.commodities = self._load_json(base / 'commodities' / 'commodities.json')
        self.suppliers = self._load_json(base / 'suppliers' / 'suppliers.json')
        self.voyages = self._load_json(base / 'voyages' / 'voyages.json')
        self.regulations = self._load_json(base / 'regulations' / 'regulations.json')
        
        self.port_ids = {p['id'] for p in self.ports}
        self.route_ids = {r['id'] for r in self.routes}
        self.ship_ids = {s['id'] for s in self.ships}
        self.commodity_ids = {c['id'] for c in self.commodities}

    def _load_json(self, path):
        with open(path, encoding='utf-8') as file:
            return json.load(file)

    def test_unique_ids_within_files(self):
        for name, data in [
            ('ports', self.ports),
            ('routes', self.routes),
            ('ships', self.ships),
            ('commodities', self.commodities),
            ('suppliers', self.suppliers),
            ('voyages', self.voyages),
            ('regulations', self.regulations),
        ]:
            ids = [item['id'] for item in data]
            self.assertEqual(len(ids), len(set(ids)), f"Duplicate IDs found in {name}.json")

    def test_unique_ids_across_files(self):
        all_ids = []
        for data in [self.ports, self.routes, self.ships, self.commodities, self.suppliers, self.voyages]:
            all_ids.extend([item['id'] for item in data])
        
        self.assertEqual(len(all_ids), len(set(all_ids)), "Duplicate IDs found across different dataset files")

    def test_required_fields_for_final_integration(self):
        required_fields = {
            'ports': ('id', 'name', 'city', 'province', 'latitude', 'longitude', 'max_vessel_tonnage'),
            'routes': ('id', 'origin_port_id', 'destination_port_id', 'distance_nm', 'estimated_days', 'route_type', 'is_active'),
            'ships': ('id', 'name', 'ship_type', 'status', 'deadweight_tonnage', 'cargo_capacity_m3'),
            'commodities': ('id', 'name', 'category', 'hs_code', 'special_requirements'),
            'suppliers': ('id', 'business_name', 'port_id', 'commodity_ids', 'avg_monthly_volume_ton', 'rating', 'verified'),
            'voyages': ('id', 'ship_id', 'route_id', 'departure_date', 'arrival_date', 'status', 'total_capacity_ton', 'used_capacity_ton', 'remaining_capacity_ton'),
            'regulations': ('id', 'filename', 'title', 'full_title', 'document_type', 'issuer', 'year', 'topics', 'rag_priority', 'status'),
        }

        dataset_map = {
            'ports': self.ports,
            'routes': self.routes,
            'ships': self.ships,
            'commodities': self.commodities,
            'suppliers': self.suppliers,
            'voyages': self.voyages,
            'regulations': self.regulations,
        }

        for name, fields in required_fields.items():
            for item in dataset_map[name]:
                for field in fields:
                    self.assertIn(field, item, f"{name} item {item.get('id')} missing required field: {field}")

    def test_supplier_foreign_keys(self):
        for supplier in self.suppliers:
            self.assertIn(supplier['port_id'], self.port_ids, f"Supplier {supplier['business_name']} references invalid port_id")
            for c_id in supplier['commodity_ids']:
                self.assertIn(c_id, self.commodity_ids, f"Supplier {supplier['business_name']} references invalid commodity_id {c_id}")

    def test_route_foreign_keys(self):
        for route in self.routes:
            self.assertIn(route['origin_port_id'], self.port_ids, f"Route {route['route_id']} references invalid origin_port_id")
            self.assertIn(route['destination_port_id'], self.port_ids, f"Route {route['route_id']} references invalid destination_port_id")

    def test_voyage_foreign_keys_and_capacity(self):
        for voyage in self.voyages:
            self.assertIn(voyage['ship_id'], self.ship_ids, f"Voyage {voyage['id']} references invalid ship_id")
            self.assertIn(voyage['route_id'], self.route_ids, f"Voyage {voyage['id']} references invalid route_id")
            self.assertGreater(voyage['total_capacity_ton'], 0, f"Voyage {voyage['id']} total_capacity_ton must be positive")
            self.assertGreaterEqual(voyage['used_capacity_ton'], 0, f"Voyage {voyage['id']} used_capacity_ton must be non-negative")
            self.assertGreaterEqual(voyage['remaining_capacity_ton'], 0, f"Voyage {voyage['id']} remaining_capacity_ton must be non-negative")
            self.assertLessEqual(voyage['used_capacity_ton'], voyage['total_capacity_ton'], f"Voyage {voyage['id']} used_capacity_ton exceeds total capacity")
            self.assertLessEqual(voyage['remaining_capacity_ton'], voyage['total_capacity_ton'], f"Voyage {voyage['id']} remaining_capacity_ton exceeds total capacity")

    def test_supplier_quality_fields(self):
        for supplier in self.suppliers:
            self.assertGreater(supplier['avg_monthly_volume_ton'], 0, f"Supplier {supplier['business_name']} must have positive monthly volume")
            self.assertGreaterEqual(supplier['rating'], 0, f"Supplier {supplier['business_name']} rating must be at least 0")
            self.assertLessEqual(supplier['rating'], 5, f"Supplier {supplier['business_name']} rating must be at most 5")
            self.assertIsInstance(supplier['verified'], bool, f"Supplier {supplier['business_name']} verified must be boolean")
            self.assertGreater(len(supplier['commodity_ids']), 0, f"Supplier {supplier['business_name']} must supply at least one commodity")

    def test_regulation_documents_ready_for_rag(self):
        filenames = [regulation['filename'] for regulation in self.regulations]
        self.assertEqual(len(filenames), len(set(filenames)), "Duplicate regulation filenames found")

        for regulation in self.regulations:
            pdf_path = self.dataset_dir / 'regulations' / regulation['filename']
            self.assertTrue(pdf_path.exists(), f"Regulation PDF is missing: {regulation['filename']}")
            self.assertGreater(pdf_path.stat().st_size, 0, f"Regulation PDF is empty: {regulation['filename']}")
            self.assertIsInstance(regulation['topics'], list, f"Regulation {regulation['id']} topics must be a list")
            self.assertGreater(len(regulation['topics']), 0, f"Regulation {regulation['id']} must have at least one topic")

    def test_data_supports_backhaul_candidate_flow(self):
        suppliers_by_port = {}
        for supplier in self.suppliers:
            suppliers_by_port.setdefault(supplier['port_id'], []).append(supplier)

        voyages_with_destination_supplier = 0
        for voyage in self.voyages:
            route = next((item for item in self.routes if item['id'] == voyage['route_id']), None)
            self.assertIsNotNone(route, f"Voyage {voyage['id']} cannot resolve route")
            if route and suppliers_by_port.get(route['destination_port_id']):
                voyages_with_destination_supplier += 1

        self.assertGreater(
            voyages_with_destination_supplier,
            0,
            "Dataset must contain at least one voyage with suppliers at destination port for backhaul matching",
        )

if __name__ == '__main__':
    unittest.main()
