# OptiCargo Demo Accounts

Akun berikut adalah **presentation accounts deterministik untuk development/competition**.
Mereka bukan credential production.

| Role | Username | Email | Default local password |
|---|---|---|---|
| admin | `admin.demo` | `admin@demo.opticargo.id` | `OptiCargoDemo123!` |
| operator_kapal | `operator.demo` | `operator@demo.opticargo.id` | `OptiCargoDemo123!` |
| distributor | `distributor.demo` | `distributor@demo.opticargo.id` | `OptiCargoDemo123!` |
| umkm | `umkm.demo` | `umkm@demo.opticargo.id` | `OptiCargoDemo123!` |
| pengepul | `pengepul.demo` | `pengepul@demo.opticargo.id` | `OptiCargoDemo123!` |
| koperasi | `koperasi.demo` | `koperasi@demo.opticargo.id` | `OptiCargoDemo123!` |
| pelabuhan | `pelabuhan.demo` | `pelabuhan@demo.opticargo.id` | `OptiCargoDemo123!` |
| pemerintah | `pemerintah.demo` | `pemerintah@demo.opticargo.id` | `OptiCargoDemo123!` |
| eksportir | `eksportir.demo` | `eksportir@demo.opticargo.id` | `OptiCargoDemo123!` |

## Password contract

Semua presentation account memakai **satu resolved demo password**:

```text
OPTICARGO_DEMO_PASSWORD
```

Default lokal:

```text
OptiCargoDemo123!
```

Jika environment mengoverride `OPTICARGO_DEMO_PASSWORD`, password aktual seluruh
akun di atas ikut berubah saat seeder dijalankan ulang. Plaintext password tidak
disimpan di `users.json`; seeder menyimpan hash Argon2 ke PostgreSQL.

Lihat akun tanpa password:

```powershell
python -m opticargo_data.seed --list-demo-accounts
```

Lihat credential aktual secara eksplisit pada terminal lokal:

```powershell
python -m opticargo_data.seed --list-demo-accounts --show-demo-password
```

Jangan gunakan `--show-demo-password` pada CI, log publik, atau screenshot.

## UMKM presentation account

`umkm.demo` mempertahankan UUID milik seed `umkm.utara.samudera.01`, sehingga
supplier, cargo listings, dan bookings yang sudah mengacu ke UUID tersebut tetap
terhubung. Ini membuat dashboard UMKM langsung memiliki data demo tanpa duplikasi
supplier/listing/booking.
