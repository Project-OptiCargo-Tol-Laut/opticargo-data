# OptiCargo Data Factory

**Pusat Dataset dan Orkestrasi Seeding untuk Ekosistem AI OptiCargo**

---

## Latar Belakang

Repositori `opticargo-data` merupakan fondasi dari arsitektur ekosistem AI OptiCargo. Mengingat model AI tingkat lanjut (seperti *Cargo Matching, GraphRAG, dan Route Optimization*) membutuhkan asupan data yang masif, konsisten, realistis, dan terstruktur dengan baik, repositori ini bertanggung jawab atas seluruh siklus hidup data. 

Tugas utama dari repositori ini adalah memproduksi, memvalidasi, dan menyediakan dataset (baik data riil maupun sintetis yang deterministik) untuk dimasukkan (di-seed) secara sistematis ke dalam arsitektur *Polyglot Persistence* OptiCargo.

## Arsitektur Polyglot Persistence

OptiCargo menggunakan empat jenis database yang saling melengkapi untuk melayani fungsionalitas Multi-Agent:

1. **PostgreSQL (Relational Database):** Bertindak sebagai *Source of Truth*. Menyimpan data terstruktur yang bersifat final dan transaksional seperti profil user, pelabuhan, daftar kapal, rute pelayaran, data tarif, dan status pemesanan.
2. **Neo4j (Graph Database):** Bertindak sebagai *Knowledge Graph*. Menyimpan relasi antar entitas (Rute, Posisi Kapal, Supplier) untuk mendukung pencarian topologi graf dan analisis peluang *Empty Backhaul* yang tidak dapat diselesaikan dengan kueri relasional biasa.
3. **Qdrant (Vector Database):** Bertindak sebagai *Semantic Engine*. Menyimpan hasil *vector embedding* (berdimensi 3072) dari puluhan dokumen regulasi dan SOP pemerintah. Memungkinkan agen AI melakukan pencarian berbasis makna (Semantic Search) dengan akurasi tinggi.
4. **Redis (In-Memory Database):** Berfungsi sebagai jembatan komunikasi antar-agen dan sistem penyimpanan memori jangka pendek untuk koordinasi *real-time*.

## Rincian Dataset

### 1. Data Operasional Riil
Data ini diekstrak dari dokumen resmi Kementerian Perhubungan dan telah dikalibrasi.
- **70 Pelabuhan Tol Laut:** Diklasifikasikan sebagai pelabuhan *Hub* atau *Feeder*, lengkap dengan titik koordinat *Latitude/Longitude* hasil *geocoding*.
- **445 Rute Pelayaran:** Pasangan pelabuhan asal-tujuan yang dilengkapi dengan jarak tempuh (*Nautical Miles*) serta besaran tarif bersubsidi sesuai ketetapan PM 29 Tahun 2018.

### 2. Data Dokumen RAG (Knowledge Base)
Terdiri dari 9 Dokumen PDF Resmi Pemerintah yang telah distandardisasi. Termasuk di dalamnya:
- Aturan Jaringan Trayek & Kewajiban Pelayanan Publik (PSO).
- Tarif Kepelabuhanan & Jasa Bongkar Muat.
- Standar Operasional Prosedur (SOP) Bongkar Muat.
- Undang-Undang terkait logistik dan karantina.

### 3. Data Transaksional Sintetis
Dibuat secara deterministik untuk simulasi yang realistis:
- **19 Komoditas:** Memuat kode HS dan klasifikasi penanganan khusus.
- **15 Kapal Pelayaran:** Memiliki spesifikasi *Gross Tonnage* (GT) yang terkalibrasi.
- **41 Pelayaran (Voyages):** Jadwal pelayaran kapal yang tersebar ke berbagai rute secara acak namun spesifik, lengkap dengan simulasi sisa kapasitas muatan (*remaining capacity*).
- **50 Supplier:** Didistribusikan ke pelabuhan berdasarkan logika empiris (Supplier di *Hub* menyediakan barang pabrikan; Supplier di *Feeder* menyediakan hasil bumi).

## Struktur Direktori

```text
opticargo-data/
├── dataset/                  # Artefak data JSON & PDF
│   ├── commodities/          # commodities.json
│   ├── ports/                # ports.json
│   ├── regulations/          # Dokumen PDF & regulations.json
│   ├── routes/               # routes.json
│   ├── ships/                # ships.json
│   ├── suppliers/            # suppliers.json
│   └── voyages/              # voyages.json
├── scripts/
│   └── generators/           # Skrip generator data sintetis (generate_voyages.py)
├── seed/                     # Kumpulan skrip seeding & validasi
│   ├── validate.py           # Validasi skema Pydantic
│   ├── seed_postgres.py      # Seeding tabel ke PostgreSQL
│   ├── seed_neo4j.py         # Membangun Knowledge Graph di Neo4j
│   ├── seed_qdrant.py        # Ekstraksi PDF dan Embedding ke Qdrant
│   ├── seed_indexes.py       # Pembuatan index performa untuk DB
│   └── seed_all.py           # Orkestrator eksekusi semua skrip di atas
└── README.md
```

## Panduan Penggunaan (Seeding Pipeline)

1. Pastikan Anda telah menyalin file konfigurasi environment. Sangat disarankan untuk mengubah kredensial default untuk keperluan produksi.
   ```bash
   cp .env.example .env
   ```
   *(Isi `GEMINI_API_KEY` dengan API Key milik Anda. Sesuaikan port dan kredensial database jika menggunakan konfigurasi kustom).*

2. Pastikan semua kontainer Docker (PostgreSQL, Neo4j, Qdrant) pada repositori infrastruktur sudah berjalan.
3. Jalankan perintah orkestrator berikut dari direktori root `opticargo-data`:

```bash
python -m seed.seed_all
```

Proses ini bersifat *idempotent*. Anda dapat menjalankannya berulang kali tanpa khawatir menduplikasi data, berkat penggunaan UUID5 (deterministik) pada PostgreSQL dan operasi `MERGE` pada Neo4j. Skrip juga telah dibekali penanganan konflik pembaruan harga (*Upsert*).

## Verifikasi Visual (Untuk Keperluan Penjurian & Audit)

Untuk memudahkan verifikasi dan audit arsitektur database, sistem ini telah menyediakan akses *dashboard* visual secara lokal yang dapat langsung diakses melalui web browser:

1. **Neo4j (Knowledge Graph)**
   - **URL:** Akses melalui browser lokal Anda pada port default Neo4j Browser (biasanya `http://localhost:7474`).
   - **Kredensial:** Gunakan kredensial yang tertera pada file `.env` sistem lokal Anda.
   - **Cara Verifikasi:** Masukkan kueri Cypher `MATCH (n) RETURN n LIMIT 100` untuk melihat visualisasi graf relasi pelabuhan, rute, kapal, dan *supplier* secara interaktif.

2. **Qdrant (Vector Database)**
   - **URL:** Akses dashboard melalui port REST Qdrant (biasanya `http://localhost:16333/dashboard`).
   - **Cara Verifikasi:** Pilih menu **Collections** di panel kiri, kemudian klik pada collection `regulations`. Anda akan melihat daftar vektor berdimensi 3072 hasil *embedding* dokumen beserta dengan metadatanya (judul dokumen, nomor halaman, dan teks aslinya).

3. **PostgreSQL (Relational Database)**
   - **Kredensial:** Konfigurasi koneksi (Host, Port, User, Password) merujuk pada isi dari file `.env`.
   - **Cara Verifikasi:** Gunakan aplikasi *Database Client* seperti **DBeaver** atau **pgAdmin**. Buka skema `public` dan Anda dapat memeriksa integritas relasional serta keutuhan data pada tabel-tabel transaksional (seperti rute dan tarif subsidi).
