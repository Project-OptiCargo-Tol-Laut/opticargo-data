import json
import uuid
from datetime import datetime, timezone
import os
from pathlib import Path

PORTS_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def make_uuid(name):
    return str(uuid.uuid5(PORTS_NAMESPACE, name.lower().strip()))


now = os.getenv("OPTICARGO_DATASET_TIMESTAMP", "2026-07-26T00:00:00Z")

PORTS = [
    # HUB UTAMA
    {"name": "Tanjung Perak", "city": "Kota Surabaya", "province": "Jawa Timur", "latitude": -7.1967, "longitude": 112.7328, "port_type": "hub", "max_vessel_tonnage": 75000, "tol_laut_role": "Pelabuhan Pangkal Hub Utama - Jawa Timur"},
    {"name": "Tanjung Priok", "city": "Kota Jakarta Utara", "province": "DKI Jakarta", "latitude": -6.1015, "longitude": 106.8860, "port_type": "hub", "max_vessel_tonnage": 100000, "tol_laut_role": "Pelabuhan Pangkal Hub Nasional"},
    {"name": "Makassar", "city": "Kota Makassar", "province": "Sulawesi Selatan", "latitude": -5.1206, "longitude": 119.4072, "port_type": "hub", "max_vessel_tonnage": 60000, "tol_laut_role": "Pelabuhan Pangkal Hub - Kawasan Timur Indonesia"},
    {"name": "Belang Belang", "city": "Kabupaten Mamuju", "province": "Sulawesi Barat", "latitude": -2.4631, "longitude": 118.9723, "port_type": "hub", "max_vessel_tonnage": 30000, "tol_laut_role": "Pelabuhan Pangkal Hub - Kalimantan dan Sulawesi Barat"},
    {"name": "Teluk Bayur", "city": "Kota Padang", "province": "Sumatera Barat", "latitude": -1.0011, "longitude": 100.3500, "port_type": "hub", "max_vessel_tonnage": 50000, "tol_laut_role": "Pelabuhan Pangkal Hub - Sumatera Barat"},
    {"name": "Bengkulu", "city": "Kota Bengkulu", "province": "Bengkulu", "latitude": -3.9017, "longitude": 102.3022, "port_type": "hub", "max_vessel_tonnage": 30000, "tol_laut_role": "Pelabuhan Pangkal Hub - Bengkulu"},
    {"name": "Pangkal Balam", "city": "Kota Pangkalpinang", "province": "Kepulauan Bangka Belitung", "latitude": -2.0994, "longitude": 106.1300, "port_type": "hub", "max_vessel_tonnage": 20000, "tol_laut_role": "Pelabuhan Pangkal Hub - Bangka Belitung"},
    {"name": "Natuna", "city": "Kabupaten Natuna", "province": "Kepulauan Riau", "latitude": 3.9231, "longitude": 108.1871, "port_type": "hub", "max_vessel_tonnage": 20000, "tol_laut_role": "Pelabuhan Pangkal Hub - Kepulauan Natuna (3T)"},
    # FEEDER - Sumatera
    {"name": "Mentawai", "city": "Kabupaten Kepulauan Mentawai", "province": "Sumatera Barat", "latitude": -2.0308, "longitude": 99.5867, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Kepulauan Mentawai (3T)"},
    {"name": "Enggano", "city": "Kabupaten Bengkulu Utara", "province": "Bengkulu", "latitude": -5.3833, "longitude": 102.4000, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Pulau Enggano (3T Terluar)"},
    {"name": "Nias", "city": "Kota Gunungsitoli", "province": "Sumatera Utara", "latitude": 1.3047, "longitude": 97.6102, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Kepulauan Nias"},
    # FEEDER - Kepulauan Riau
    {"name": "Tarempa", "city": "Kabupaten Kepulauan Anambas", "province": "Kepulauan Riau", "latitude": 3.2200, "longitude": 106.2200, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Kepulauan Anambas (3T)"},
    {"name": "Tanjung Batu", "city": "Kabupaten Karimun", "province": "Kepulauan Riau", "latitude": 0.6635, "longitude": 103.4611, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Karimun"},
    {"name": "Serasan", "city": "Kabupaten Natuna", "province": "Kepulauan Riau", "latitude": 2.5144, "longitude": 109.0447, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Serasan (3T Terluar)"},
    {"name": "Midai", "city": "Kabupaten Natuna", "province": "Kepulauan Riau", "latitude": 2.9833, "longitude": 107.7667, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Pulau Midai (3T)"},
    # FEEDER - Bangka Belitung
    {"name": "Blinyu", "city": "Kabupaten Bangka", "province": "Kepulauan Bangka Belitung", "latitude": -1.6375, "longitude": 105.7720, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Blinyu/Bangka"},
    {"name": "Tanjung Pandan", "city": "Kabupaten Belitung", "province": "Kepulauan Bangka Belitung", "latitude": -2.7462, "longitude": 107.6286, "port_type": "feeder", "max_vessel_tonnage": 10000, "tol_laut_role": "Pelabuhan Singgah - Belitung"},
    # FEEDER - Kalimantan
    {"name": "Nunukan", "city": "Kabupaten Nunukan", "province": "Kalimantan Utara", "latitude": 4.1502, "longitude": 117.6578, "port_type": "feeder", "max_vessel_tonnage": 10000, "tol_laut_role": "Pelabuhan Singgah - Nunukan (Perbatasan Malaysia)"},
    {"name": "P. Sebatik", "city": "Kabupaten Nunukan", "province": "Kalimantan Utara", "latitude": 4.1289, "longitude": 117.8828, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - P. Sebatik (3T Perbatasan)"},
    {"name": "Sangatta", "city": "Kabupaten Kutai Timur", "province": "Kalimantan Timur", "latitude": 0.5203, "longitude": 117.6033, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Sangatta"},
    # FEEDER - Sulawesi Utara
    {"name": "Amurang", "city": "Kabupaten Minahasa Selatan", "province": "Sulawesi Utara", "latitude": 1.1895, "longitude": 124.5714, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Amurang"},
    {"name": "Biaro", "city": "Kabupaten Kepulauan Siau Tagulandang Biaro", "province": "Sulawesi Utara", "latitude": 2.1158, "longitude": 125.3725, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Pulau Biaro (3T)"},
    {"name": "Buhias", "city": "Kabupaten Kepulauan Siau Tagulandang Biaro", "province": "Sulawesi Utara", "latitude": 2.7094, "longitude": 125.4089, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Pulau Buhias (3T)"},
    {"name": "Kahakitang", "city": "Kabupaten Kepulauan Sangihe", "province": "Sulawesi Utara", "latitude": 3.1729, "longitude": 125.5180, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Kahakitang (3T)"},
    {"name": "Kakorotan", "city": "Kabupaten Kepulauan Talaud", "province": "Sulawesi Utara", "latitude": 4.6308, "longitude": 127.1594, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Kakorotan (3T Terluar)"},
    {"name": "Lirung", "city": "Kabupaten Kepulauan Talaud", "province": "Sulawesi Utara", "latitude": 3.9328, "longitude": 126.6905, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Lirung/Talaud (3T)"},
    {"name": "Marore", "city": "Kabupaten Kepulauan Sangihe", "province": "Sulawesi Utara", "latitude": 4.7372, "longitude": 125.4783, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Pulau Marore (3T Terluar)"},
    {"name": "Melangoane", "city": "Kabupaten Kepulauan Talaud", "province": "Sulawesi Utara", "latitude": 4.0069, "longitude": 126.6728, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Melangoane (3T)"},
    {"name": "Miangas", "city": "Kabupaten Kepulauan Talaud", "province": "Sulawesi Utara", "latitude": 5.5525, "longitude": 126.5806, "port_type": "feeder", "max_vessel_tonnage": 2000, "tol_laut_role": "Pelabuhan Singgah - Miangas (3T Terluar Perbatasan Filipina)"},
    {"name": "Tagulandang", "city": "Kabupaten Kepulauan Siau Tagulandang Biaro", "province": "Sulawesi Utara", "latitude": 2.3453, "longitude": 125.3806, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Tagulandang"},
    {"name": "Tahuna", "city": "Kabupaten Kepulauan Sangihe", "province": "Sulawesi Utara", "latitude": 3.6364, "longitude": 125.4636, "port_type": "feeder", "max_vessel_tonnage": 10000, "tol_laut_role": "Pelabuhan Singgah - Tahuna/Sangihe"},
    # FEEDER - Sulawesi Selatan & Tenggara
    {"name": "Sanni", "city": "Kabupaten Kepulauan Selayar", "province": "Sulawesi Selatan", "latitude": -5.7333, "longitude": 120.4500, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Sanni/Selayar"},
    {"name": "Bau Bau", "city": "Kota Baubau", "province": "Sulawesi Tenggara", "latitude": -5.4636, "longitude": 122.5972, "port_type": "feeder", "max_vessel_tonnage": 10000, "tol_laut_role": "Pelabuhan Singgah - Bau-Bau"},
    {"name": "Wanci", "city": "Kabupaten Wakatobi", "province": "Sulawesi Tenggara", "latitude": -5.3177, "longitude": 123.5409, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Wanci/Wakatobi"},
    # FEEDER - Maluku Utara
    {"name": "Maba", "city": "Kabupaten Halmahera Timur", "province": "Maluku Utara", "latitude": 0.6250, "longitude": 128.1750, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Maba/Halmahera Timur"},
    {"name": "Morotai", "city": "Kabupaten Pulau Morotai", "province": "Maluku Utara", "latitude": 2.0550, "longitude": 128.2950, "port_type": "feeder", "max_vessel_tonnage": 10000, "tol_laut_role": "Pelabuhan Singgah - Morotai (3T)"},
    {"name": "Obi", "city": "Kabupaten Halmahera Selatan", "province": "Maluku Utara", "latitude": -1.5000, "longitude": 127.7500, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Pulau Obi"},
    {"name": "Pulau Gebe", "city": "Kabupaten Halmahera Tengah", "province": "Maluku Utara", "latitude": -0.0758, "longitude": 129.4486, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Pulau Gebe (3T)"},
    {"name": "Sanana", "city": "Kabupaten Kepulauan Sula", "province": "Maluku Utara", "latitude": -2.0544, "longitude": 125.9753, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Sanana/Kepulauan Sula"},
    {"name": "Tidore", "city": "Kota Tidore Kepulauan", "province": "Maluku Utara", "latitude": 0.6850, "longitude": 127.4385, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Tidore"},
    {"name": "Tobelo", "city": "Kabupaten Halmahera Utara", "province": "Maluku Utara", "latitude": 1.7678, "longitude": 127.9833, "port_type": "feeder", "max_vessel_tonnage": 10000, "tol_laut_role": "Pelabuhan Singgah - Tobelo/Halmahera Utara"},
    # FEEDER - Maluku
    {"name": "Dobo", "city": "Kabupaten Kepulauan Aru", "province": "Maluku", "latitude": -6.2000, "longitude": 134.5000, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Dobo/Kepulauan Aru (3T)"},
    {"name": "Kisar (Wonreli)", "city": "Kabupaten Maluku Barat Daya", "province": "Maluku", "latitude": -8.0594, "longitude": 127.1733, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Pulau Kisar (3T Terluar)"},
    {"name": "Moa", "city": "Kabupaten Maluku Barat Daya", "province": "Maluku", "latitude": -8.1830, "longitude": 127.9444, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Pulau Moa (3T)"},
    {"name": "Namlea", "city": "Kabupaten Buru", "province": "Maluku", "latitude": -3.2715, "longitude": 127.0842, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Namlea/Pulau Buru"},
    {"name": "Namrole", "city": "Kabupaten Buru Selatan", "province": "Maluku", "latitude": -3.5136, "longitude": 126.8272, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Namrole/Buru Selatan"},
    {"name": "Saumlaki", "city": "Kabupaten Kepulauan Tanimbar", "province": "Maluku", "latitude": -7.9167, "longitude": 131.3333, "port_type": "feeder", "max_vessel_tonnage": 10000, "tol_laut_role": "Pelabuhan Singgah - Saumlaki/Tanimbar (3T)"},
    # FEEDER - NTT
    {"name": "Adonara (Terong)", "city": "Kabupaten Flores Timur", "province": "Nusa Tenggara Timur", "latitude": -8.3903, "longitude": 123.1311, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Pulau Adonara (3T)"},
    {"name": "Kalabahi", "city": "Kabupaten Alor", "province": "Nusa Tenggara Timur", "latitude": -8.2197, "longitude": 124.5164, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Kalabahi/Alor"},
    {"name": "Larantuka", "city": "Kabupaten Flores Timur", "province": "Nusa Tenggara Timur", "latitude": -8.3500, "longitude": 122.9800, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Larantuka"},
    {"name": "Lewoleba", "city": "Kabupaten Lembata", "province": "Nusa Tenggara Timur", "latitude": -8.3699, "longitude": 123.4056, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Lewoleba/Lembata"},
    {"name": "Maumere", "city": "Kabupaten Sikka", "province": "Nusa Tenggara Timur", "latitude": -8.6147, "longitude": 122.2144, "port_type": "feeder", "max_vessel_tonnage": 10000, "tol_laut_role": "Pelabuhan Singgah - Maumere"},
    {"name": "Rote", "city": "Kabupaten Rote Ndao", "province": "Nusa Tenggara Timur", "latitude": -10.8333, "longitude": 123.0000, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Pulau Rote (3T Terluar)"},
    {"name": "Sabu", "city": "Kabupaten Sabu Raijua", "province": "Nusa Tenggara Timur", "latitude": -10.4908, "longitude": 121.8389, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Pulau Sabu (3T)"},
    {"name": "Waingapu", "city": "Kabupaten Sumba Timur", "province": "Nusa Tenggara Timur", "latitude": -9.6522, "longitude": 120.2637, "port_type": "feeder", "max_vessel_tonnage": 10000, "tol_laut_role": "Pelabuhan Singgah - Waingapu/Sumba Timur"},
    # FEEDER - NTB
    {"name": "Calabai (Dompu)", "city": "Kabupaten Dompu", "province": "Nusa Tenggara Barat", "latitude": -8.2142, "longitude": 117.7093, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Calabai/Dompu"},
    # FEEDER - Papua Barat
    {"name": "Fakfak", "city": "Kabupaten Fakfak", "province": "Papua Barat", "latitude": -2.9325, "longitude": 132.3097, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Fakfak"},
    {"name": "Kaimana", "city": "Kabupaten Kaimana", "province": "Papua Barat", "latitude": -3.6609, "longitude": 133.7745, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Kaimana"},
    {"name": "Manokwari", "city": "Kabupaten Manokwari", "province": "Papua Barat", "latitude": -0.8667, "longitude": 134.0833, "port_type": "feeder", "max_vessel_tonnage": 20000, "tol_laut_role": "Pelabuhan Singgah - Manokwari (Ibu Kota Papua Barat)"},
    {"name": "Oransbari", "city": "Kabupaten Manokwari Selatan", "province": "Papua Barat", "latitude": -1.3400, "longitude": 134.2528, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Oransbari"},
    {"name": "Wasior", "city": "Kabupaten Teluk Wondama", "province": "Papua Barat", "latitude": -2.7167, "longitude": 134.5000, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Wasior"},
    # FEEDER - Papua
    {"name": "Agats", "city": "Kabupaten Asmat", "province": "Papua Selatan", "latitude": -5.5381, "longitude": 138.1370, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Agats/Asmat (3T)"},
    {"name": "Biak", "city": "Kabupaten Biak Numfor", "province": "Papua", "latitude": -1.1764, "longitude": 136.0827, "port_type": "feeder", "max_vessel_tonnage": 20000, "tol_laut_role": "Pelabuhan Singgah - Biak"},
    {"name": "Merauke", "city": "Kabupaten Merauke", "province": "Papua Selatan", "latitude": -8.4778, "longitude": 140.3900, "port_type": "feeder", "max_vessel_tonnage": 20000, "tol_laut_role": "Pelabuhan Singgah - Merauke"},
    {"name": "Nabire", "city": "Kabupaten Nabire", "province": "Papua Tengah", "latitude": -3.2300, "longitude": 135.5800, "port_type": "feeder", "max_vessel_tonnage": 5000, "tol_laut_role": "Pelabuhan Singgah - Nabire"},
    {"name": "Sarmi", "city": "Kabupaten Sarmi", "province": "Papua", "latitude": -2.4167, "longitude": 139.0833, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Sarmi (3T)"},
    {"name": "Serui", "city": "Kabupaten Kepulauan Yapen", "province": "Papua", "latitude": -1.8833, "longitude": 136.2333, "port_type": "feeder", "max_vessel_tonnage": 10000, "tol_laut_role": "Pelabuhan Singgah - Serui/Yapen"},
    {"name": "Teba", "city": "Kabupaten Mamberamo Raya", "province": "Papua", "latitude": -1.4839, "longitude": 137.8836, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Teba"},
    {"name": "Timika", "city": "Kabupaten Mimika", "province": "Papua Tengah", "latitude": -4.7500, "longitude": 137.0000, "port_type": "feeder", "max_vessel_tonnage": 20000, "tol_laut_role": "Pelabuhan Singgah - Timika"},
    {"name": "Waren", "city": "Kabupaten Waropen", "province": "Papua", "latitude": -2.2860, "longitude": 137.0184, "port_type": "feeder", "max_vessel_tonnage": 3000, "tol_laut_role": "Pelabuhan Singgah - Waren (3T)"},
]


def build_facilities(port_type):
    return {
        "has_crane": port_type == "hub",
        "has_cold_storage": port_type == "hub",
        "has_container_yard": port_type == "hub",
        "fuel_available": True,
    }


result = []
for i, p in enumerate(PORTS):
    record = {
        "id": make_uuid(p["name"]),
        "port_id": "port_" + str(i + 1).zfill(3),
        "name": p["name"],
        "city": p["city"],
        "province": p["province"],
        "latitude": p["latitude"],
        "longitude": p["longitude"],
        "port_type": p["port_type"],
        "tol_laut_role": p["tol_laut_role"],
        "max_vessel_tonnage": p["max_vessel_tonnage"],
        "facilities": build_facilities(p["port_type"]),
        "operating_hours": {"weekday": "07:00-17:00", "weekend": "07:00-14:00"},
        "source": "SK Jaringan Trayek Tol Laut 2022 / Permenhub PM 29 Tahun 2018",
        "created_at": now,
        "is_synthetic": False,
        "provenance": "opticargo-data:curated:ports",
    }
    result.append(record)

out = Path(__file__).parent.parent.parent / 'dataset' / "ports" / "ports.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

hubs = [p for p in result if p["port_type"] == "hub"]
feeders = [p for p in result if p["port_type"] == "feeder"]
print("[OK] Generated " + str(len(result)) + " ports -> " + str(out))
print("  Hub: " + str(len(hubs)) + " | Feeder: " + str(len(feeders)))

# Verifikasi nama unik
names = [p["name"] for p in result]
dupes = [n for n in names if names.count(n) > 1]
if dupes:
    print("[WARN] Duplikat ditemukan: " + str(set(dupes)))
else:
    print("  Semua nama pelabuhan unik - OK")
