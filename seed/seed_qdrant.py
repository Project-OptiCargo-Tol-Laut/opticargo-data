"""
seed_qdrant.py - Seeding Dokumen Regulasi ke Qdrant (Vector Database)

Memproses file PDF regulasi pemerintah menjadi chunk teks,
men-generate embedding vektor menggunakan FastEmbed lokal,
lalu meng-upsert hasilnya ke Qdrant untuk keperluan RAG.

Pipeline:
  1. Baca metadata regulasi dari regulations.json.
  2. Ekstrak teks dari setiap file PDF menggunakan pdfplumber
     (dengan opsi membatasi halaman, untuk melewati lampiran tabel).
  3. Bersihkan teks dari header/footer berulang.
  4. Potong teks menjadi chunk berukuran konsisten (~500 kata).
  5. Generate embedding per chunk menggunakan FastEmbed BAAI/bge-small-en-v1.5.
  6. Hapus chunk lama dokumen tsb (kalau ada), lalu upsert chunk baru
     ke Qdrant collection -- supaya tidak ada chunk basi nyangkut.

Referensi PRD: Bagian 4.5 (seed/seed_qdrant.py)
"""

import os
import re
import uuid
import time
import hashlib

import pdfplumber
from fastembed import TextEmbedding
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

from opticargo_shared.models.rag_chunk import RagChunkMetadata
from seed.validate import load_json, BASE_DIR

load_dotenv()

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------

# Nama collection di Qdrant untuk menyimpan chunk regulasi.
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "opticargo_documents_v1")

# Dimensi vektor output dari model FastEmbed BAAI/bge-small-en-v1.5.
EMBEDDING_DIMENSION = 384
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Jumlah kata per chunk. Disesuaikan agar tidak melebihi batas token model.
CHUNK_SIZE_WORDS = 500

# Jumlah kata yang tumpang tindih antar chunk, agar konteks tidak terpotong.
CHUNK_OVERLAP_WORDS = 50

# Jeda antar request ke Gemini API tidak diperlukan untuk FastEmbed lokal.
API_DELAY_SECONDS = 0

# Jumlah percobaan ulang jika embedding gagal.
MAX_EMBEDDING_RETRIES = 3

# Pola baris yang dianggap noise berulang (header/footer khas dokumen
# Permenhub) dan akan dibuang sebelum chunking, supaya chunk tidak
# dipenuhi teks yang sama berulang-ulang di tiap halaman.
NOISE_PATTERNS = [
    r"^MENTERI PERHUBUNGAN\s*$",
    r"^REPUBLIK INDONESIA\s*$",
    r"^-\s*\d+\s*-\s*$",          # penomoran halaman gaya "- 2 -"
    r"^\d+\s*$",                   # baris cuma berisi angka halaman
    r"^SK\s+No\s+\d+\s+[A-Z]\s*$", # SK No 019623 A
    r"^www\.peraturan\.go\.id\s*$", # footer website
    r"^\d+,\s*No\.\s*\d+\s*-\d+-\s*$", # 2021, No. 778 -6-
    r"^\d+,\s*No\.\s*\d+\s*$",     # 2021, No. 778
]
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)


# ---------------------------------------------------------------------------
# Koneksi
# ---------------------------------------------------------------------------

def get_qdrant_client() -> QdrantClient:
    """Membuat koneksi ke Qdrant menggunakan QDRANT_URL dari .env."""
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    if not url:
        raise ValueError("QDRANT_URL tidak ditemukan di file .env")
    return QdrantClient(url=url, api_key=api_key)


def get_embedding_model() -> TextEmbedding:
    """Meload model FastEmbed (Local)."""
    return TextEmbedding(model_name=EMBEDDING_MODEL_NAME)


def stable_document_uuid(source_id: str) -> str:
    """Membuat UUID deterministik untuk document_id kontrak shared."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"opticargo:document:{source_id}"))


def file_checksum(filepath: str) -> str:
    """Menghitung checksum file untuk provenance dan reindexing."""
    digest = hashlib.sha256()
    with open(filepath, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


# ---------------------------------------------------------------------------
# Ekstraksi Teks dari PDF
# ---------------------------------------------------------------------------

def extract_text_from_pdf(filepath: str, max_pages: int | None = None, is_bilingual: bool = False) -> str:
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
            if is_bilingual:
                width = page.width
                height = page.height
                left_bbox = (0, 0, width / 2, height)
                
                left_text = page.crop(left_bbox).extract_text() or ""
                
                # Mengabaikan kolom kanan (bahasa Inggris)
                text = left_text
            else:
                text = page.extract_text()
                
            if text:
                full_text.append(text)
    return "\n".join(full_text)


def extract_pages_from_pdf(
    filepath: str,
    max_pages: int | None = None,
    is_bilingual: bool = False,
) -> list[tuple[int, str]]:
    """Mengekstrak teks per halaman agar setiap chunk punya citation page-aware."""
    pages_text: list[tuple[int, str]] = []
    with pdfplumber.open(filepath) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
        for page_index, page in enumerate(pages, start=1):
            if is_bilingual:
                width = page.width
                height = page.height
                left_bbox = (0, 0, width / 2, height)
                text = page.crop(left_bbox).extract_text() or ""
            else:
                text = page.extract_text() or ""

            if text.strip():
                pages_text.append((page_index, text))
    return pages_text


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

def semantic_chunking(text: str, max_chunk_words: int = 800) -> list[str]:
    """
    Memotong teks panjang berdasarkan struktur "Pasal".
    Setiap Pasal akan menjadi 1 chunk. Jika Pasal tersebut terlalu panjang
    (> max_chunk_words kata), maka akan dipecah lagi per "Ayat" atau penomoran.
    """
    # 1. Pisahkan teks sebelum kata "Pasal <angka>" (di awal baris)
    parts = re.split(r'\n(?=\s*Pasal\s+\d+)', text, flags=re.IGNORECASE)
    
    chunks = []
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        word_count = len(part.split())
        
        # Jika bagian ini terlalu panjang (mis. Pasal 1 Ketentuan Umum)
        if word_count > max_chunk_words:
            # Cari judul pasal (biasanya di baris pertama)
            lines = part.split("\n", 1)
            pasal_header = lines[0].strip() if re.match(r'^Pasal\s+\d+', lines[0], re.IGNORECASE) else "Lanjutan"
            
            # Pecah berdasarkan penomoran ayat (1), (2), atau 1., 2.
            sub_parts = re.split(r'\n(?=\s*\(\d+\)\s+|\s*\d+\.\s+)', part)
            
            current_sub_chunk = ""
            for sub_part in sub_parts:
                sub_part = sub_part.strip()
                if not sub_part:
                    continue
                    
                # Jika sub_part tidak diawali dengan "Pasal", tambahkan header agar konteks jelas
                prefix = f"[{pasal_header}]\n" if not re.match(r'^Pasal\s+\d+', sub_part, re.IGNORECASE) else ""
                
                # Jika digabung masih muat
                if not current_sub_chunk:
                    current_sub_chunk = f"{prefix}{sub_part}"
                elif len(current_sub_chunk.split()) + len(sub_part.split()) <= max_chunk_words:
                    current_sub_chunk += f"\n\n{sub_part}"
                else:
                    chunks.append(current_sub_chunk)
                    current_sub_chunk = f"[{pasal_header}]\n{sub_part}"
            
            if current_sub_chunk:
                chunks.append(current_sub_chunk)
        else:
            chunks.append(part)

    return chunks


# ---------------------------------------------------------------------------
# Generate Embedding (dengan retry)
# ---------------------------------------------------------------------------

def generate_embedding(embedding_model: TextEmbedding, text: str,
                       max_retries: int = MAX_EMBEDDING_RETRIES) -> list[float]:
    """
    Men-generate embedding vektor dari teks menggunakan FastEmbed secara lokal.
    """
    try:
        embeddings_list = list(embedding_model.embed([text]))
        if not embeddings_list:
            raise RuntimeError("Empty embedding returned")
        return embeddings_list[0].tolist()
    except Exception as e:
        raise RuntimeError(f"Gagal generate embedding lokal: {e}")


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
    embedding_model = get_embedding_model()

    # -- Buat collection jika belum ada --
    existing_names = {c.name for c in qdrant.get_collections().collections}
    if COLLECTION_NAME not in existing_names:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_DIMENSION, distance=Distance.COSINE),
        )
        print(f"[INFO] Collection '{COLLECTION_NAME}' berhasil dibuat di Qdrant.")
    else:
        info = qdrant.get_collection(COLLECTION_NAME)
        actual_dim = info.config.params.vectors.size
        if actual_dim != EMBEDDING_DIMENSION:
            print(f"[WARN] Dimensi lama ({actual_dim}) != baru ({EMBEDDING_DIMENSION}). Recreate...")
            qdrant.delete_collection(COLLECTION_NAME)
            qdrant.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=EMBEDDING_DIMENSION, distance=Distance.COSINE),
            )
        else:
            print(f"[INFO] Collection '{COLLECTION_NAME}' sudah ada, dimensi cocok. Melanjutkan upsert.")

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
        status_text = f"(status: {status}{f', dibatasi {max_pages} halaman' if max_pages else ''})"

        print(f"[INFO] Memproses: {filename} {status_text}")

        # -- Ekstrak dan bersihkan teks per halaman untuk citation --
        is_bilingual = (reg["id"] == "reg_007")
        raw_pages = extract_pages_from_pdf(str(filepath), max_pages=max_pages, is_bilingual=is_bilingual)
        if not raw_pages:
            print(f"[WARN] Tidak ada teks yang bisa diekstrak dari {filename}.")
            continue

        page_chunks = []
        total_words = 0
        for page_number, page_text in raw_pages:
            cleaned_page = clean_text(page_text)
            if not cleaned_page.strip():
                continue
            total_words += len(cleaned_page.split())
            for chunk in semantic_chunking(cleaned_page):
                page_chunks.append({"page": page_number, "text": chunk})

        print(f"  Teks diekstrak: {total_words} kata "
              f"(setelah dibersihkan) -> {len(page_chunks)} chunk")

        # -- Hapus chunk lama dokumen ini dulu --
        delete_existing_chunks(qdrant, filename)

        # -- Generate embedding dan upsert ke Qdrant --
        points = []
        document_id = stable_document_uuid(reg["id"])
        checksum = file_checksum(str(filepath))
        document_version = reg.get("document_number") or str(reg.get("year", ""))
        is_superseded = status.lower() not in {"aktif", "active"}

        for i, page_chunk in enumerate(page_chunks):
            chunk = page_chunk["text"]
            embedding = generate_embedding(embedding_model, chunk)
            if API_DELAY_SECONDS > 0:
                time.sleep(API_DELAY_SECONDS)

            # ID deterministik menggunakan UUID5 dari kombinasi nama file + index.
            # Ini menjamin idempotensi: re-run menghasilkan ID yang sama.
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{filename}::chunk_{i}"))
            metadata = RagChunkMetadata(
                document_version=document_version,
                title=reg.get("title", filename),
                issuer=reg.get("issuer"),
                page=page_chunk["page"],
                effective_date=reg.get("effective_date"),
                source_reference=reg.get("source_url"),
                is_superseded=is_superseded,
                checksum=checksum,
            )

            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "document_id": document_id,
                    "source_document_id": reg["id"],
                    "chunk_id": point_id,
                    "filename": filename,
                    "title": reg.get("title", ""),
                    "full_title": reg.get("full_title", ""),
                    "document_type": reg.get("document_type", ""),
                    "issuer": reg.get("issuer", ""),
                    "year": reg.get("year", 0),
                    "topics": reg.get("topics", []),
                    "rag_priority": reg.get("rag_priority", "low"),
                    "status": status,
                    "document_version": document_version,
                    "source_reference": reg.get("source_url"),
                    "is_superseded": is_superseded,
                    "checksum": checksum,
                    "page": page_chunk["page"],
                    "embedding_model": EMBEDDING_MODEL_NAME,
                    "embedding_dimension": EMBEDDING_DIMENSION,
                    "metadata": metadata.model_dump(mode="json"),
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
