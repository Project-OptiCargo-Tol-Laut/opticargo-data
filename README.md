<div align="center">
  <h1>🚢 OptiCargo Data Factory</h1>
  <p><em>Pusat Dataset dan Generator Deterministik untuk Ekosistem AI OptiCargo</em></p>
</div>

---

## 📌 Latar Belakang
Repositori `opticargo-data` adalah komponen fundamental (blok fondasi) bagi ekosistem AI OptiCargo. Kami menyadari bahwa model AI tingkat lanjut (*Cargo Matching, GraphRAG, Route Optimization*) membutuhkan asupan data yang tidak hanya masif, tetapi juga **konsisten, realistis, dan relasional**.

Repo ini bertugas memproduksi, memvalidasi, dan menyediakan dataset (baik riil maupun sintetis yang logis) untuk di-seed ke dalam tiga database utama kami: **PostgreSQL** (Transaksional), **Neo4j** (Knowledge Graph), dan **Qdrant** (Vector Search).

## 🌟 Keunggulan Arsitektur Data (Jury Highlight)

1. **Deterministic UUID5 Generation:** 
   Kami tidak menggunakan ID acak (UUIDv4) atau angka *auto-increment*. Seluruh *Primary Key* digenerate menggunakan algoritma *hash* **UUIDv5** berbasis nama entitas (misal: "Tanjung Perak"). Pendekatan *software engineering* tingkat lanjut ini menjamin **Idempotency** dan **Reproducibility**—artinya *database* tidak akan pernah mengalami duplikasi data meskipun proses *seeding* dijalankan ribuan kali.

2. **Real-World Geographic Logic:** 
   Data sintetis kami tidak di-generate secara asal. *Supplier* yang diletakkan di pelabuhan **Hub** (seperti Surabaya/Makassar) secara otomatis dikonfigurasi untuk menyuplai barang pabrikan (Semen, Beras). Sebaliknya, *supplier* di pelabuhan **Feeder** (seperti Maluku/Papua) menyuplai hasil bumi/laut (Kopra, Ikan Beku). Logika ini sangat krusial agar *engine* AI kami bisa didemokan untuk menyelesaikan masalah *Empty Backhaul* (muatan balik kosong) secara logis dan realistis.

3. **Hybrid Data Sourcing:**
   Menggabungkan 100% data riil regulasi pemerintah (untuk presisi RAG) dengan data operasional sintetis yang dikalibrasi sesuai kondisi empiris di lapangan.

---

## 📊 Rincian Dataset

### 1. Data Operasional Riil (Diekstrak dari Dokumen Kemenhub)
- **⚓ 70 Pelabuhan Tol Laut:** Lengkap dengan klasifikasi *Hub/Feeder* dan titik koordinat *Latitude/Longitude* presisi (hasil riset *geocoding*). *(Sumber Acuan: SK Trayek Tol Laut 2022)*
- **🗺️ 445 Rute Pelayaran:** Pasangan pelabuhan asal-tujuan lengkap dengan jarak tempuh (*Nautical Miles*) dan besaran tarif kontainer *Dry/Reefer* bersubsidi. *(Sumber Acuan: Lampiran PM 29 Tahun 2018)*

### 2. Data Dokumen RAG (Knowledge Base)
Terdapat **9 Dokumen PDF Resmi Pemerintah** yang telah di-standarisasi (*clean naming convention*) beserta *metadata*-nya di `regulations.json`. Dokumen ini mencakup:
- Aturan Jaringan Trayek & Kewajiban Pelayanan Publik (PSO)
- Tarif Kepelabuhanan & Jasa Bongkar Muat
- Standar Operasional Prosedur (SOP) Operasional Pelabuhan (Stuffing/Stripping)
- Undang-Undang Karantina Hewan, Ikan, & Tumbuhan

### 3. Data Transaksional Sintetis (Logically Generated)
Dihasilkan secara deterministik melalui *Python script*:
- **📦 19 Komoditas Unggulan:** Terbagi dalam Kebutuhan Pokok, Material Bangunan, Hasil Laut, dan Rempah. Dilengkapi standar `hs_code` dan syarat penanganan khusus (*cold-storage*).
- **🛳️ 15 Kapal Pelayaran:** Menggunakan penamaan armada asli (KM Logistik Nusantara, KM Sabuk Nusantara) dengan rentang *Gross Tonnage* (GT) yang dikalibrasi dengan skala pelabuhan.
- **🏢 50 Supplier Terdistribusi:** Tersebar secara acak namun proporsional di seluruh nusantara. *Foreign key* dijamin 100% terintegrasi dengan tabel pelabuhan dan komoditas.

---

## 📂 Struktur Direktori

Sesuai prinsip *Separation of Concerns*, kami memisahkan data pasif dengan logika pembuat (kode aktif):

```text
opticargo-data/
├── dataset/                  # Murni menampung artefak data pasif (JSON & PDF siap pakai)
│   ├── commodities/          # -> commodities.json
│   ├── ports/                # -> ports.json
│   ├── regulations/          # -> 9 PDF Resmi + regulations.json
│   ├── routes/               # -> routes.json
│   ├── ships/                # -> ships.json
│   └── suppliers/            # -> suppliers.json
├── scripts/
│   └── generators/           # Murni menampung kode Python pembuat data sintetis deterministik
│       ├── generate_commodities.py
│       ├── generate_ports.py
│       ├── generate_routes.py
│       ├── generate_ships.py
│       └── generate_suppliers.py
└── README.md
```

## 🚀 Cara Reproduksi Data (Generation)

Jika Anda ingin memperbesar skala dataset (misal: dari 50 *supplier* menjadi 5.000 *supplier* untuk keperluan *Load Testing* arsitektur), Anda cukup mengubah satu angka pada *script* dan menjalankannya:

```bash
# Contoh untuk me-regenerate data komoditas, kapal, dan supplier
python scripts/generators/generate_commodities.py
python scripts/generators/generate_ships.py
python scripts/generators/generate_suppliers.py
```
> **Catatan:** Seluruh skrip secara otomatis membaca dependensi dari dataset utama (seperti `ports.json`) untuk menjamin integritas relasional (*Foreign Key Constraint*) agar selalu *valid* sebelum masuk ke tahap *database seeding*.
