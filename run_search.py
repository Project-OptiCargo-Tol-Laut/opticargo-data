import os
from dotenv import load_dotenv
from google import genai
from qdrant_client import QdrantClient

load_dotenv()

def test_search(query: str, top_k: int = 3):
    print(f"\n[?] Pertanyaan: '{query}'")
    
    # 1. Inisialisasi Klien
    gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    qdrant = QdrantClient(os.getenv("QDRANT_URL"))
    
    # 2. Generate Embedding untuk Pertanyaan
    print("Menerjemahkan pertanyaan menjadi vektor...")
    result = gemini_client.models.embed_content(
        model="gemini-embedding-2",
        contents=query,
    )
    if not result.embeddings or not result.embeddings[0].values:
        raise RuntimeError("Empty embedding returned")
    query_vector = result.embeddings[0].values
    
    # 3. Cari di Qdrant
    print(f"Mencari {top_k} chunk paling relevan di Qdrant...\n")
    search_result = qdrant.query_points(
        collection_name=os.getenv("QDRANT_COLLECTION", "opticargo_documents_v1"),
        query=query_vector,
        limit=top_k,
    )
    
    # 4. Tampilkan Hasil
    print("="*60)
    for i, hit in enumerate(search_result.points, 1):
        score = hit.score
        if not hit.payload:
            continue
        filename = hit.payload.get("filename", "Unknown")
        chunk_text = hit.payload.get("chunk_text", "")
        
        # Tampilkan snippet (maks 250 karakter) agar mudah dibaca
        snippet = chunk_text[:250].replace('\n', ' ') + "..." if len(chunk_text) > 250 else chunk_text.replace('\n', ' ')
        
        print(f"#{i} | Score: {score:.4f} | Dokumen: {filename}")
        print(f"Isi Teks:\n{snippet}")
        print("-" * 60)

if __name__ == "__main__":
    # Kita tes dengan pertanyaan spesifik tentang Tol Laut
    test_search("Berapa tarif muatan kontainer kering untuk program tol laut?")
