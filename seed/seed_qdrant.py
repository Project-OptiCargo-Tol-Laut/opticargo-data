"""
seed_qdrant.py - Seeding Dokumen Regulasi ke Qdrant (Vector Database)

Memproses file PDF regulasi pemerintah menjadi chunk teks,
men-generate embedding vektor menggunakan Gemini API,
lalu meng-upsert hasilnya ke Qdrant untuk keperluan RAG.

Pipeline:
  1. Baca metadata regulasi dari regulations.json.
  2. Ekstrak teks dari setiap file PDF menggunakan pdfplumber
     (dengan opsi membatasi halaman, untuk melewati lampiran tabel).
  3. Bersihkan teks dari header/footer berulang.
  4. Potong teks menjadi chunk berukuran konsisten (~500 kata).
  5. Generate embedding per chunk menggunakan Gemini text-embedding-004,
     dengan retry otomatis kalau gagal.
  6. Hapus chunk lama dokumen tsb (kalau ada), lalu upsert chunk baru
     ke Qdrant collection -- supaya tidak ada chunk basi nyangkut.

Referensi PRD: Bagian 4.5 (seed/seed_qdrant.py)
"""

import os
import re
import uuid
import time

import pdfplumber
from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    FilterSelector,
    MatchValue,
)
from dotenv import load_dotenv

from seed.validate import load_json, BASE_DIR

load_dotenv()

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------

# Nama collection di Qdrant untuk menyimpan chunk regulasi.
COLLECTION_NAME = "regulations"

# Dimensi vektor output dari model text-embedding-004 Gemini.
EMBEDDING_DIMENSION = 3072

# Jumlah kata per chunk. Disesuaikan agar tidak melebihi batas token model.
CHUNK_SIZE_WORDS = 500

# Jumlah kata yang tumpang tindih antar chunk, agar konteks tidak terpotong.
CHUNK_OVERLAP_WORDS = 50

# Jeda antar request ke Gemini API untuk menghindari rate limit (detik).
API_DELAY_SECONDS = 1.5

# Jumlah percobaan ulang jika embedding gagal (rate limit/timeout/dsb).
MAX_EMBEDDING_RETRIES = 3

# Pola baris yang dianggap noise berulang (header/footer khas dokumen
# Permenhub) dan akan dibuang sebelum chunking, supaya chunk tidak
# dipenuhi teks yang sama berulang-ulang di tiap halaman.
NOISE_PATTERNS = [
    r"^MENTERI PERHUBUNGAN\s*$",
    r"^REPUBLIK INDONESIA\s*$",
    r"^-\s*\d+\s*-\s*$",          # penomoran halaman gaya "- 2 -"
    r"^\d+\s*$",                   # baris cuma berisi angka halaman
]
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)


# ---------------------------------------------------------------------------
# Koneksi
# ---------------------------------------------------------------------------

def get_qdrant_client() -> QdrantClient:
    """Membuat koneksi ke Qdrant menggunakan QDRANT_URL dari .env."""
    url = os.getenv("QDRANT_URL")
    if not url:
        raise ValueError("QDRANT_URL tidak ditemukan di file .env")
    return QdrantClient(url=url)


def get_gemini_client() -> genai.Client:
    """Membuat client Gemini API menggunakan GEMINI_API_KEY dari .env."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY tidak ditemukan di file .env")
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Ekstraksi Teks dari PDF
# ---------------------------------------------------------------------------

def extract_text_from_pdf(filepath: str, max_pages: int | None = None) -> str:
    """
    Mengekstrak teks dari file PDF menggunakan pdfplumber.

    Args:
        filepath: Path absolut menuju file PDF.
        max_pages: Kalau diisi, hanya halaman 1..max_pages yang diproses.
            Dipakai untuk dokumen yang punya lampiran tabel besar (mis.
            PM 29/2018 dengan tabel 445 baris tarif) -- tabel semacam itu
            SEBAIKNYA TIDAK ikut di-chunk sebagai teks bebas, karena hasil
            ekstraksinya jadi deretan angka tanpa konteks kolom yang jelas.
            Data tabel seperti itu sudah lebih baik disimpan terstruktur
            (lihat dataset/routes/routes.json), bukan lewat RAG.

    Returns:
        String berisi teks dari halaman yang diproses.
    """
    full_text = []
    with pdfplumber.open(filepath) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
        for page in pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
    return "\n".join(full_text)


def clean_text(text: str) -> str:
    """
    Membersihkan teks dari baris-baris noise berulang (header/footer
    khas dokumen Permenhub) sebelum di-chunk, supaya setiap chunk lebih
    padat informasi dan tidak dipenuhi teks yang sama berkali-kali.
    """
    cleaned_lines = [
        line for line in text.split("\n")
        if line.strip() and not NOISE_RE.match(line.strip())
    ]
    return "\n".join(cleaned_lines)


# ---------------------------------------------------------------------------
# Chunking Teks
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS,
               overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """
    Memotong teks panjang menjadi potongan-potongan (chunk) berukuran
    konsisten, memakai sliding window berbasis jumlah kata dengan overlap.
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


# ---------------------------------------------------------------------------
# Generate Embedding (dengan retry)
# ---------------------------------------------------------------------------

def generate_embedding(gemini_client: genai.Client, text: str,
                       max_retries: int = MAX_EMBEDDING_RETRIES) -> list[float]:
    """
    Men-generate embedding vektor dari teks menggunakan Gemini API,
    dengan retry otomatis kalau gagal (rate limit/timeout/dsb) -- supaya
    1 chunk yang gagal tidak menghentikan seluruh proses seeding 9 dokumen.
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            result = gemini_client.models.embed_content(
                model="gemini-embedding-2",
                contents=text,
            )
            if not result.embeddings or not result.embeddings[0].values:
                raise RuntimeError("Empty embedding returned")
            return result.embeddings[0].values
        except Exception as e:
            last_error = e
            wait = API_DELAY_SECONDS * (attempt + 2)
            print(f"    [WARN] Embedding gagal (percobaan {attempt + 1}/{max_retries}): {e}"
                  f" -- retry dalam {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError(
        f"Gagal generate embedding setelah {max_retries} percobaan"
    ) from last_error


# ---------------------------------------------------------------------------
# Hapus chunk lama sebelum insert baru (hindari chunk basi nyangkut)
# ---------------------------------------------------------------------------

def delete_existing_chunks(qdrant: QdrantClient, filename: str) -> None:
    """
    Menghapus semua chunk lama milik satu file regulasi dari Qdrant
    sebelum meng-upsert versi baru. Ini penting kalau CHUNK_SIZE_WORDS
    pernah diubah antar-run -- tanpa ini, chunk lama dengan chunk_index
    yang sudah tidak relevan akan tetap nyangkut selamanya di Qdrant.
    """
    qdrant.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="filename",
                        match=MatchValue(value=filename),
                    )
                ]
            )
        ),
    )


# ---------------------------------------------------------------------------
# Orkestrator Utama
# ---------------------------------------------------------------------------

def run_seed() -> None:
    """
    Menjalankan seluruh pipeline seeding Qdrant.

    regulations.json per dokumen boleh punya field opsional:
      - "max_pages": batas halaman yang diproses (skip lampiran tabel)
      - "status": "aktif" / "dicabut" (default "aktif" kalau tidak diisi)
    """
    qdrant = get_qdrant_client()
    gemini = get_gemini_client()

    # -- Buat collection jika belum ada --
    existing = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION_NAME not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        print(f"[INFO] Collection '{COLLECTION_NAME}' berhasil dibuat di Qdrant.")
    else:
        print(f"[INFO] Collection '{COLLECTION_NAME}' sudah ada, melanjutkan upsert.")

    # -- Baca metadata regulasi --
    regulations = load_json(BASE_DIR / "regulations" / "regulations.json")
    print(f"[INFO] Ditemukan {len(regulations)} dokumen regulasi.")

    total_chunks = 0

    for reg in regulations:
        filename = reg["filename"]
        filepath = BASE_DIR / "regulations" / filename

        if not filepath.exists():
            print(f"[WARN] File tidak ditemukan, dilewati: {filename}")
            continue

        status = reg.get("status", "aktif")
        max_pages = reg.get("max_pages")

        print(f"[INFO] Memproses: {filename} (status: {status}"
              f"{f', dibatasi {max_pages} halaman' if max_pages else ''})")

        # -- Ekstrak dan bersihkan teks --
        raw_text = extract_text_from_pdf(str(filepath), max_pages=max_pages)
        if not raw_text.strip():
            print(f"[WARN] Tidak ada teks yang bisa diekstrak dari {filename}.")
            continue

        cleaned = clean_text(raw_text)
        chunks = chunk_text(cleaned)
        print(f"  Teks diekstrak: {len(cleaned.split())} kata "
              f"(setelah dibersihkan) -> {len(chunks)} chunk")

        # -- Hapus chunk lama dokumen ini dulu --
        delete_existing_chunks(qdrant, filename)

        # -- Generate embedding dan upsert ke Qdrant --
        points = []
        for i, chunk in enumerate(chunks):
            embedding = generate_embedding(gemini, chunk)
            time.sleep(API_DELAY_SECONDS)

            # ID deterministik menggunakan UUID5 dari kombinasi nama file + index.
            # Ini menjamin idempotensi: re-run menghasilkan ID yang sama.
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{filename}::chunk_{i}"))

            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "document_id": reg["id"],
                    "filename": filename,
                    "title": reg.get("title", ""),
                    "full_title": reg.get("full_title", ""),
                    "document_type": reg.get("document_type", ""),
                    "issuer": reg.get("issuer", ""),
                    "year": reg.get("year", 0),
                    "topics": reg.get("topics", []),
                    "rag_priority": reg.get("rag_priority", "low"),
                    "status": status,
                    "chunk_index": i,
                    "chunk_text": chunk,
                    "token_count": len(chunk.split()),
                },
            ))

        # -- Upsert batch per dokumen --
        if points:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
            total_chunks += len(points)
            print(f"  [OK] {len(points)} chunk berhasil di-upsert.")

    print(f"[INFO] Seeding Qdrant selesai. Total: {total_chunks} chunk dari "
          f"{len(regulations)} dokumen.")


if __name__ == "__main__":
    run_seed()
