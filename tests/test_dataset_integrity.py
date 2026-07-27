import json
import unittest
from pathlib import Path

class TestDatasetIntegrity(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).parent.parent / 'dataset'
        self.ports = json.load(open(base / 'ports' / 'ports.json', encoding='utf-8'))
        self.routes = json.load(open(base / 'routes' / 'routes.json', encoding='utf-8'))
        self.ships = json.load(open(base / 'ships' / 'ships.json', encoding='utf-8'))
        self.commodities = json.load(open(base / 'commodities' / 'commodities.json', encoding='utf-8'))
        self.suppliers = json.load(open(base / 'suppliers' / 'suppliers.json', encoding='utf-8'))
        
        self.port_ids = {p['id'] for p in self.ports}
        self.commodity_ids = {c['id'] for c in self.commodities}

    def test_unique_ids_within_files(self):
        for name, data in [('ports', self.ports), ('routes', self.routes), ('ships', self.ships), ('commodities', self.commodities), ('suppliers', self.suppliers)]:
            ids = [item['id'] for item in data]
            self.assertEqual(len(ids), len(set(ids)), f"Duplicate IDs found in {name}.json")

    def test_unique_ids_across_files(self):
        all_ids = []
        for data in [self.ports, self.routes, self.ships, self.commodities, self.suppliers]:
            all_ids.extend([item['id'] for item in data])
        
        self.assertEqual(len(all_ids), len(set(all_ids)), "Duplicate IDs found across different dataset files")

    def test_supplier_foreign_keys(self):
        for supplier in self.suppliers:
            self.assertIn(supplier['port_id'], self.port_ids, f"Supplier {supplier['business_name']} references invalid port_id")
            for c_id in supplier['commodity_ids']:
                self.assertIn(c_id, self.commodity_ids, f"Supplier {supplier['business_name']} references invalid commodity_id {c_id}")

    def test_route_foreign_keys(self):
        for route in self.routes:
            self.assertIn(route['origin_port_id'], self.port_ids, f"Route {route['route_id']} references invalid origin_port_id")
            self.assertIn(route['destination_port_id'], self.port_ids, f"Route {route['route_id']} references invalid destination_port_id")

if __name__ == '__main__':
    unittest.main()
