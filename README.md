# opticargo-data

Dataset sample/dummy dan script seeding untuk kebutuhan MVP dan pengembangan
lokal, mengikuti kebutuhan dataset di Bagian 16 dokumen desain.

## Isi Dataset
- 5-10 kapal fiktif dengan jadwal voyage sample.
- 10-15 pelabuhan dari jaringan Tol Laut (data publik Kemenhub/Pelindo).
- 20-30 supplier komoditas fiktif berbagai daerah.
- 5-10 dokumen regulasi nyata (Kemenhub, KSOP) untuk RAG.
- Data harga & produksi komoditas (referensi format BPS/Kemendag).

## Struktur Direktori
    /ships
    /ports
    /commodities
    /suppliers
    /regulations        → PDF regulasi
    /seed                → script insert ke PostgreSQL + trigger sync ke Neo4j/Qdrant

## Dependensi Repo Lain
- Dikonsumsi oleh `opticargo-knowledge-graph` (seed graph) dan
  `opticargo-rag-pipeline` (index dokumen regulasi).
- Skema data mengikuti definisi di `opticargo-shared`.

## Catatan
Data di repo ini adalah data sample/dummy untuk MVP, bukan data produksi.
Sumber data resmi untuk fase produksi tercantum di Bagian 16 dokumen desain
(Ditjen Hubla, Inaportnet, BPS, Panel Harga Pangan Kemendag, dll).