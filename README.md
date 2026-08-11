<div align="center">
  <h1>🚢 OptiCargo Data Factory</h1>
  <p><em>Pusat Dataset dan Generator Deterministik untuk Ekosistem AI OptiCargo</em></p>
</div>

---

## 📌 Latar Belakang
Repositori `opticargo-data` adalah komponen fundamental (blok fondasi) bagi ekosistem AI OptiCargo. Kami menyadari bahwa model AI tingkat lanjut (*Cargo Matching, GraphRAG, Route Optimization*) membutuhkan asupan data yang tidak hanya masif, tetapi juga **konsisten, realistis, dan relasional**.

Repo ini bertugas memproduksi, memvalidasi, dan menyediakan dataset (baik riil maupun sintetis yang logis) untuk di-seed ke dalam tiga database utama kami: **PostgreSQL** (Transaksional), **Neo4j** (Knowledge Graph), dan **Qdrant** (Vector Search).

## 🌟 Keunggulan Arsitektur Data

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

---

## ✅ Runtime Seed v3.0 (PRD-aligned)

Repo ini sekarang juga menyediakan **one-off Docker seed job** yang sesuai dengan kontrak `opticargo-infra`:

```text
python -m opticargo_data.seed --profile competition --idempotent
```

Tambahan utama tanpa membuang dataset lama:

- `Dockerfile` + `pyproject.toml` agar image dapat dibangun lokal/CI;
- package `opticargo_data` untuk validation, schema-aware PostgreSQL seed, hashing akun demo, dan optional staging regulasi ke MinIO;
- dataset user 9 role, voyage, cargo capacity, cargo listing, serta **500 synthetic bookings**;
- perbaikan duplicate UUID supplier dan generator timestamp agar deterministic;
- test integritas FK/UUID/count;
- `docs/PRD_TRACEABILITY.md` untuk batas tanggung jawab dan gap yang memang milik Gateway/RAG.

### Build image lokal

```powershell
docker build `
  --progress=plain `
  -t opticargo-data:local `
  .
```

Lalu pada `opticargo-infra/.env`:

```env
DATA_IMAGE=opticargo-data:local
```

Validasi image tanpa database:

```powershell
docker run --rm opticargo-data:local `
  python -m opticargo_data.seed --profile competition --validate-only
```

### Jalankan melalui Infra

```powershell
docker compose `
  -p opticargo `
  --env-file .env `
  -f docker-compose.yml `
  --profile core `
  --profile ai `
  --profile demo `
  run --rm data-seed
```

`data-seed` dari Infra sudah memanggil `python -m opticargo_data.seed --profile competition --idempotent`, sehingga Compose tidak perlu diubah setelah `DATA_IMAGE=opticargo-data:local` diset.

### Akun demo lokal

Seeder menyediakan **sembilan akun presentation deterministik**, satu untuk setiap role.
Akun `umkm.demo` memakai user ID supplier-backed yang sebelumnya bernama
`umkm.utara.samudera.01`, sehingga relasi supplier, cargo listing, dan booking seed
tetap hidup dan dashboard UMKM langsung memiliki data saat demo.

| Role | Username | Email | Password default lokal |
|---|---|---|---|
| Admin | `admin.demo` | `admin@demo.opticargo.id` | `OptiCargoDemo123!` |
| Operator Kapal | `operator.demo` | `operator@demo.opticargo.id` | `OptiCargoDemo123!` |
| Distributor | `distributor.demo` | `distributor@demo.opticargo.id` | `OptiCargoDemo123!` |
| UMKM | `umkm.demo` | `umkm@demo.opticargo.id` | `OptiCargoDemo123!` |
| Pengepul | `pengepul.demo` | `pengepul@demo.opticargo.id` | `OptiCargoDemo123!` |
| Koperasi | `koperasi.demo` | `koperasi@demo.opticargo.id` | `OptiCargoDemo123!` |
| Pelabuhan | `pelabuhan.demo` | `pelabuhan@demo.opticargo.id` | `OptiCargoDemo123!` |
| Pemerintah | `pemerintah.demo` | `pemerintah@demo.opticargo.id` | `OptiCargoDemo123!` |
| Eksportir | `eksportir.demo` | `eksportir@demo.opticargo.id` | `OptiCargoDemo123!` |

Password di tabel adalah **default development lokal**, bukan credential production.
Seeder tidak menyimpan plaintext password pada `dataset/users/users.json`; seluruh akun
menerima hash Argon2 yang dibuat saat seed dari:

```env
OPTICARGO_DEMO_PASSWORD=OptiCargoDemo123!
OPTICARGO_PASSWORD_SCHEME=argon2
```

Jika `OPTICARGO_DEMO_PASSWORD` dioverride di `.env`/Compose, seluruh akun demo memakai
nilai override tersebut. Untuk melihat daftar akun tanpa password:

```powershell
python -m opticargo_data.seed --list-demo-accounts
```

Untuk secara eksplisit menampilkan password lokal yang **sedang ter-resolve**:

```powershell
python -m opticargo_data.seed --list-demo-accounts --show-demo-password
```

Jangan menjalankan opsi `--show-demo-password` pada CI/log publik atau screenshot
presentasi. Gateway 1.0.0 menggunakan Argon2; `OPTICARGO_PASSWORD_SCHEME` selain
`argon2` sengaja ditolak agar hash seeder selalu kompatibel dengan login Gateway.


### Kompatibilitas kolom persistence Gateway

Seeder mengisi metadata persistence yang aman dari schema live: kolom integer `version`
(required optimistic-lock counter) dimulai dari `1`, dan timestamp audit required tanpa
default menggunakan timestamp seed UTC yang tetap. Field bisnis lain tidak pernah ditebak;
ketidakcocokan tetap dihentikan sebagai `SCHEMA_MISMATCH`.

### Cek kompatibilitas schema Gateway

OpenAPI/migration Gateway tetap sumber kebenaran. Sebelum seed pertama setelah perubahan migration:

```powershell
docker compose `
  -p opticargo `
  --env-file .env `
  -f docker-compose.yml `
  --profile core `
  --profile ai `
  --profile demo `
  run --rm data-seed `
  python -m opticargo_data.seed --profile competition --schema-only
```

Seeder menggunakan introspection schema PostgreSQL. Jika ada kolom NOT NULL baru yang tidak dapat dipetakan, seed berhenti dengan `SCHEMA_MISMATCH` daripada menulis data yang salah.

### Regulasi

Sembilan PDF regulasi existing selalu divalidasi. Untuk hanya men-stage PDF ke bucket dokumen MinIO:

```powershell
docker compose `
  -p opticargo `
  --env-file .env `
  -f docker-compose.yml `
  --profile core `
  --profile ai `
  --profile demo `
  run --rm data-seed `
  python -m opticargo_data.seed --profile competition --idempotent --upload-regulations
```

Indexing Qdrant/RAG **tidak dipalsukan oleh data repo**; indexing tetap tanggung jawab pipeline RAG berdasarkan flow aplikasi.

### Test lokal Python

```powershell
python -m pip install -e ".[test]"
python -m pytest
python -m opticargo_data.seed --profile competition --validate-only
```

## Gateway business-unique normalization

The curated route source can contain multiple route variants with the same
`origin_port_id + destination_port_id + route_type` (for example different via
ports).  The current Gateway PostgreSQL schema has a UNIQUE key for that business
identity.  The one-off seed therefore builds a DB-compatible view without changing
the source JSON:

- one deterministic canonical route is materialized per Gateway business key;
- non-canonical source route IDs are treated as aliases;
- `voyages.route_id` is remapped to the canonical DB route ID;
- live UNIQUE constraints are also introspected during idempotent upsert, and
  downstream single-column foreign keys are remapped through any resolved ID alias.

This prevents `UniqueViolation` on route business keys while preserving the curated
source dataset as the reproducible input artifact.

## Contract integration v3.1.0

`opticargo-data` pins and vendors the official `opticargo-shared==1.0.0` wheel. The
competition seed is validated against the shared Create contracts before PostgreSQL
is modified. The seed then performs a separate Gateway persistence projection for
columns that are intentionally not part of the public shared contract.

Current Gateway-only deterministic projections:

- `cargo_listings.certifications`: copied from the linked commodity's
  `certifications_required` so certification matching remains meaningful.
- `cargo_listings.cargo_type`: derived as `frozen`, `dry_food`, or `general` from
  commodity perishability/category, matching the competition capacity vocabulary.
- `bookings.created_by`: resolved from booking -> listing -> supplier -> user.
- `bookings.booking_ref`: deterministic `OCG-DEMO-...` reference.
- `bookings.booking_date`: uses the synthetic booking `created_at` timestamp.
- integer optimistic-lock `version`: initialized to `1` when the live Gateway table
  requires it without a database default.

The public shared model remains strict; Gateway-only columns are never added to the
shared Pydantic payload merely to make validation pass.


## Gateway 1.0.0 auth compatibility

Demo-user password hashing is intentionally aligned to `opticargo-gateway-api` 1.0.0:
`argon2-cffi>=23.1,<24` and `argon2.PasswordHasher()` defaults. The resolved
`OPTICARGO_DEMO_PASSWORD` is trimmed because Gateway `LoginRequest` uses
`str_strip_whitespace=True`. The password itself is never printed by the seeder.

Safe verification against an already-seeded database:

```bash
python -m opticargo_data.seed --verify-demo-auth
```

Expected result includes `admin_user_found True` and
`admin_password_matches True`.

## Load/performance seed v3.2.0

Untuk menguji Frontend/Gateway dengan working set besar tanpa mengganti dataset JSON
canonical, seeder menyediakan runtime augmentation deterministik:

| `--load-profile` | User tambahan | Supplier tambahan | Voyage + capacity | Cargo listing tambahan | Booking tambahan |
|---|---:|---:|---:|---:|---:|
| `none` | 0 | 0 | 0 | 0 | 0 |
| `small` | 250 | 200 | 200 | 2.000 | 5.000 |
| `medium` | 1.000 | 800 | 800 | 8.000 | 25.000 |
| `large` | 3.000 | 2.500 | 2.500 | 25.000 | 100.000 |

Default runtime seed juga menambahkan lima listing `umkm.demo` yang route, availability
window, volume, dan voyage-nya sengaja dibuat kompatibel. Ini memberi positive scenario
untuk halaman **Rekomendasi Kapal**. Pada profile load, sekitar 20% listing tambahan
juga dimiliki `umkm.demo`, sedangkan voyage load memakai armada existing yang dimiliki
`operator.demo`; karena itu kedua role dapat langsung menguji pagination/filter/matching
dengan volume besar.

Validasi profile `medium` tanpa PostgreSQL:

```powershell
python -m opticargo_data.seed `
  --profile competition `
  --load-profile medium `
  --validate-only
```

Seed profile `medium` melalui Infra saat ini:

```powershell
docker compose `
  -p opticargo `
  --env-file .env `
  -f docker-compose.yml `
  -f docker-compose.local.yml `
  --profile core `
  --profile gateway `
  --profile ai `
  --profile demo `
  run --rm data-seed `
  python -m opticargo_data.seed `
  --profile competition `
  --idempotent `
  --load-profile medium
```

Seeder mencetak durasi dan throughput per tabel (`rows/s`) agar waktu materialisasi DB
juga terlihat. Untuk benchmark read-only HTTP sesudah seed:

```powershell
python scripts/benchmark_gateway.py `
  --username umkm.demo `
  --requests 100 `
  --concurrency 10
```

Script meminta password secara interaktif jika `OPTICARGO_BENCHMARK_PASSWORD` tidak
diset, dan melaporkan RPS, average latency, p50, p95, serta p99. Dokumentasi lengkap:
`docs/PERFORMANCE_LOAD_SEED.md`.

Payment, recommendation, review, document, audit, outbox, dan session tidak diinsert
langsung oleh load seed karena lifecycle/side-effect tabel tersebut dimiliki Gateway dan
worker. Volume untuk domain tersebut harus dibuat melalui application flow yang sesuai.
