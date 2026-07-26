import pdfplumber, json
from pathlib import Path
import re

reg_dir = Path('d:/PROYEK ML DAN AI/OptiCargo/opticargo-data/dataset/regulations')

# 1. Cek SK Trayek
sk_path = reg_dir / 'SK_Jaringan_Trayek_Tol_Laut_2022.pdf'
sk_text = ''
with pdfplumber.open(sk_path) as pdf:
    for page in pdf.pages:
        sk_text += (page.extract_text() or '') + '\n'

# 2. Cek PM 29
pm_path = reg_dir / 'PM_29_2018_Tarif_PSO_Angkutan_Barang_Laut.pdf'
pm_text = ''
with pdfplumber.open(pm_path) as pdf:
    for page in pdf.pages:
        pm_text += (page.extract_text() or '') + '\n'

ports = json.load(open('d:/PROYEK ML DAN AI/OptiCargo/opticargo-data/dataset/ports/ports.json', encoding='utf-8'))
routes = json.load(open('d:/PROYEK ML DAN AI/OptiCargo/opticargo-data/dataset/routes/routes.json', encoding='utf-8'))

missing_ports = []
for p in ports:
    name = p['name']
    # Cari di SK Trayek atau PM 29
    if name.lower() not in sk_text.lower() and name.lower() not in pm_text.lower():
        # Coba split nama jika ada kurung
        base_name = name.split('(')[0].strip()
        if base_name.lower() not in sk_text.lower() and base_name.lower() not in pm_text.lower():
            missing_ports.append(name)

print(f'Total ports in JSON: {len(ports)}')
if missing_ports:
    print(f'WARNING: {len(missing_ports)} ports not found in PDFs: {missing_ports}')
else:
    print('[OK] Semua pelabuhan di ports.json TERVERIFIKASI ada di dalam dokumen SK Trayek / PM 29.')

# Sample cek rute (cek tarifnya ada di teks PM 29 nggak)
sample_route = routes[0]
print(f'\nSample Route: {sample_route["origin_port_name"]} -> {sample_route["destination_port_name"]}')
print(f'Tarif Dry: {sample_route["tarif_dry_container_idr"]}')

# Tarif format text
tarif_str = f'{sample_route["tarif_dry_container_idr"]:,}'.replace(',', '.')
print(f'Mencari tarif {tarif_str} di PM 29...')
if tarif_str in pm_text:
    print('[OK] Tarif ditemukan di PM 29')
else:
    print('[FAIL] Tarif TIDAK ditemukan dalam bentuk string persis di PM 29, tapi mungkin formatnya beda di tabel PDF.')
