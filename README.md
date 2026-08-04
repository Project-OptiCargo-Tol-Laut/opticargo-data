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
3. **Qdrant (Vector Database):** Bertindak sebagai *Semantic Engine*. Menyimpan hasil *vector embedding* berdimensi 384 dari model FastEmbed `BAAI/bge-small-en-v1.5` untuk dokumen regulasi dan SOP pemerintah. Memungkinkan agen AI melakukan pencarian berbasis makna (Semantic Search) dengan citation ke dokumen, chunk, dan halaman sumber.
4. **Redis (In-Memory Database):** Berfungsi sebagai jembatan komunikasi antar-agen dan sistem penyimpanan memori jangka pendek untuk koordinasi *real-time*.

## Rincian Dataset

### 1. Data Operasional Riil
Data ini diekstrak dari dokumen resmi Kementerian Perhubungan dan telah dikalibrasi.
- **69 Pelabuhan Tol Laut:** Diklasifikasikan sebagai pelabuhan *Hub* atau *Feeder*, lengkap dengan titik koordinat *Latitude/Longitude* hasil *geocoding*.
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

## Kontrak Data Final

Kontrak baseline-final lintas repository tersedia di [`docs/DATA_CONTRACT_FINAL.md`](docs/DATA_CONTRACT_FINAL.md).

Dokumen tersebut menjadi acuan untuk integrasi:

- `opticargo-data` sebagai sumber dataset dan seeding.
- `opticargo-knowledge-graph` sebagai proyeksi relasi operasional dari PostgreSQL ke Neo4j.
- `opticargo-rag-pipeline` sebagai indexing dokumen regulasi dari PDF ke Qdrant.
- `opticargo-agents` sebagai orkestrator yang mengonsumsi konteks KG/RAG/ML melalui dependency interface.

Setiap aset JSON/PDF dicatat dalam `dataset/manifest.json` dengan checksum SHA-256,
ukuran, jumlah record, sumber, dan penanda data sintetis. Manifest bersifat
deterministik dan wajib diperbarui secara eksplisit ketika dataset berubah:

```bash
python -m seed.manifest
python -m seed.manifest --check
python -m seed.validate
```

Perintah `--check` dan validasi harus lulus sebelum image `data-seed` dibangun.

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
   *(Sesuaikan port dan kredensial database jika menggunakan konfigurasi kustom. Embedding regulasi memakai FastEmbed lokal, sehingga tidak membutuhkan `GEMINI_API_KEY`).*

2. Pastikan semua kontainer Docker (PostgreSQL, Neo4j, Qdrant) pada repositori infrastruktur sudah berjalan.
3. Jalankan perintah orkestrator berikut dari direktori root `opticargo-data`:

```bash
python -m seed.seed_all
```

Proses ini bersifat *idempotent* dan fail-fast. PostgreSQL memakai advisory lock,
satu transaksi, serta UPSERT penuh untuk merekonsiliasi record seed. Proyeksi
Neo4j dijalankan dalam satu managed write transaction. Qdrant menyiapkan seluruh
embedding terlebih dahulu, menunggu upsert tersimpan, lalu hanya menghapus chunk
lama yang benar-benar stale. Seeder tidak pernah menghapus collection otomatis
jika dimensi embedding tidak cocok; perubahan dimensi harus melalui migrasi
collection/alias yang eksplisit.

Akun operator/supplier yang dibuat oleh seeder selalu nonaktif dan memakai hash
sentinel yang tidak dapat dipakai untuk login. Kredensial pengguna demo/produksi
harus disediakan oleh sistem identity, bukan oleh dataset ini.

## Verifikasi Visual (Untuk Keperluan Penjurian & Audit)

Untuk memudahkan verifikasi dan audit arsitektur database, sistem ini telah menyediakan akses *dashboard* visual secara lokal yang dapat langsung diakses melalui web browser:

1. **Neo4j (Knowledge Graph)**
   - **URL:** Akses melalui browser lokal Anda pada port default Neo4j Browser (biasanya `http://localhost:7474`).
   - **Kredensial:** Gunakan kredensial yang tertera pada file `.env` sistem lokal Anda.
   - **Cara Verifikasi:** Masukkan kueri Cypher `MATCH (n) RETURN n LIMIT 100` untuk melihat visualisasi graf relasi pelabuhan, rute, kapal, dan *supplier* secara interaktif.

2. **Qdrant (Vector Database)**
   - **URL:** Akses dashboard melalui port REST Qdrant (biasanya `http://localhost:16333/dashboard`).
   - **Cara Verifikasi:** Pilih menu **Collections** di panel kiri, kemudian klik pada collection `opticargo_documents_v1` atau nilai `QDRANT_COLLECTION` di environment. Anda akan melihat daftar vektor berdimensi 384 hasil *embedding* dokumen beserta metadatanya: `document_id`, `chunk_id`, `page`, `checksum`, `document_version`, judul dokumen, dan teks chunk.

3. **PostgreSQL (Relational Database)**
   - **Kredensial:** Konfigurasi koneksi (Host, Port, User, Password) merujuk pada isi dari file `.env`.
   - **Cara Verifikasi:** Gunakan aplikasi *Database Client* seperti **DBeaver** atau **pgAdmin**. Buka skema `public` dan Anda dapat memeriksa integritas relasional serta keutuhan data pada tabel-tabel transaksional (seperti rute dan tarif subsidi).
