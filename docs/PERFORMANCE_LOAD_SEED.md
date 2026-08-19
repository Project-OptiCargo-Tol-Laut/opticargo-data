# OptiCargo Deterministic Load Seed

`opticargo-data` v3.2.1 menyediakan runtime load profile untuk pengujian pagination,
filter, object-scope, matching voyage, dashboard, dan performa Gateway/Frontend tanpa
mengubah JSON canonical.

## Profile

| Profile | User tambahan | Supplier tambahan | Voyage + capacity | Cargo listing tambahan | Booking tambahan |
|---|---:|---:|---:|---:|---:|
| `none` | 0 | 0 | 0 | 0 | 0 |
| `small` | 250 | 200 | 200 | 2.000 | 5.000 |
| `medium` | 1.000 | 800 | 800 | 8.000 | 25.000 |
| `large` | 3.000 | 2.500 | 2.500 | 25.000 | 100.000 |

Semua row load menggunakan UUIDv5 deterministik dan `is_synthetic=true`, sehingga
profile yang sama dapat di-seed ulang dengan `--idempotent` tanpa menggandakan data.

Selain load profile, default runtime seed menambahkan **5 listing `umkm.demo`** yang
sengaja disejajarkan dengan route, tanggal, kapasitas, dan voyage `scheduled/delayed`
yang ada. Tujuannya agar halaman `Rekomendasi Kapal` selalu memiliki skenario positif.

Pada load profile, sekitar 20% cargo listing tambahan dimiliki supplier `umkm.demo`.
Sekitar 10% listing load tambahan juga dimiliki `distributor.demo`, yang mendapatkan supplier deterministik, lima listing guaranteed-match, dan lima booking lintas status untuk dashboard/tracking demo.
Dengan profile `medium`, akun tersebut mendapat sekitar 1.600 listing load sehingga
pagination/filter/recommendation dapat diuji langsung dari FE. Voyage load memakai kapal
existing milik `operator.demo`, sehingga dashboard operator juga mendapat working set besar.

## Validasi tanpa database

```powershell
python -m opticargo_data.seed `
  --profile competition `
  --load-profile medium `
  --validate-only
```

Atau lihat plan saja:

```powershell
python -m opticargo_data.seed `
  --load-profile medium `
  --print-load-plan
```

## Seed melalui Infra

Karena profile `ai` mengaktifkan `rag-worker` yang bergantung pada Gateway, gunakan
`core + gateway + ai + demo` pada Compose saat ini:

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

`medium` adalah rekomendasi awal untuk laptop development. Gunakan `large` hanya jika
memang ingin stress test karena schema-aware idempotent upsert melakukan preflight/update
secara konservatif dan 100k booking dapat membutuhkan waktu signifikan.

Tanggal synthetic runtime dapat digeser tanpa mengubah identitas record:

```powershell
python -m opticargo_data.seed `
  --profile competition `
  --idempotent `
  --load-profile medium `
  --seed-anchor-date 2026-08-11
```

## Benchmark read-only Gateway

Script berikut login dengan cookie session dan hanya mengirim GET requests. Password
tidak dicetak; jika environment variable tidak diberikan, script meminta password secara
interaktif.

```powershell
python scripts/benchmark_gateway.py `
  --username umkm.demo `
  --requests 100 `
  --concurrency 10
```

Default endpoint benchmark:

- `/dashboard/summary`
- `/ports?page=1&page_size=50`
- `/routes?page=1&page_size=50`
- `/voyages?page=1&page_size=50`
- `/cargo-listings?page=1&page_size=50`
- `/bookings?page=1&page_size=50`

Output menampilkan success count, RPS, average latency, p50, p95, dan p99.

## Boundary

Load seed sengaja tidak membuat row payment, recommendation, review, document, audit,
outbox, atau session secara langsung. Tabel tersebut memiliki lifecycle/side effect yang
dimiliki Gateway/worker. Untuk menguji volume pada domain-domain itu, buat fixture melalui
public/internal application flow yang sesuai, bukan insert DB yang melewati business rule.
