import os
import re
import glob
import sqlite3
import chromadb
from sentence_transformers import SentenceTransformer

STORAGE_DIR = os.path.join("storage", "transcriptions")
DB_DIR = os.path.join("storage", "chroma_db")
CACHE_DB_PATH = os.path.join("storage", "cache.db")
MODEL_NAME = "intfloat/multilingual-e5-small"

CHANNEL_SUNNAH = "https://t.me/alislam_sahih"
CHANNEL_TERMINOLOGY = "https://t.me/Oblique_terminology"

print(f"Загрузка локальной модели эмбеддингов ({MODEL_NAME})...")
embedder = SentenceTransformer(MODEL_NAME)

chroma_client = chromadb.PersistentClient(path=DB_DIR)
collection = chroma_client.get_or_create_collection(
    name="imam_lectures",
    metadata={"hnsw:space": "cosine"}
)

def split_text_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 150):
    paragraphs = text.split("\n")
    chunks = []
    current_chunk = ""

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(current_chunk) + len(p) + 1 <= chunk_size:
            current_chunk += ("\n" + p if current_chunk else p)
        else:
            if current_chunk:
                chunks.append(current_chunk)
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = overlap_text + "\n" + p
            else:
                for i in range(0, len(p), chunk_size - overlap):
                    chunks.append(p[i:i + chunk_size])
                current_chunk = ""

    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def clear_cache():
    if os.path.exists(CACHE_DB_PATH):
        try:
            with sqlite3.connect(CACHE_DB_PATH) as conn:
                conn.execute("DELETE FROM response_cache")
                conn.commit()
            print("• Кэш старых ответов успешно сброшен под новую базу.")
        except Exception as e:
            print(f"• Ошибка очистки кэша: {e}")

def get_tg_link(file_path: str, source_name: str) -> str:
    path_lower = file_path.lower()
    name_lower = source_name.lower()
    
    if "terminology" in path_lower or "термин" in path_lower or "term" in name_lower:
        base_url = CHANNEL_TERMINOLOGY
    else:
        base_url = CHANNEL_SUNNAH

    match = re.search(r"\d+", source_name)
    if match:
        return f"{base_url}/{match.group(0)}"
    return base_url

def index_all():
    files = glob.glob(os.path.join(STORAGE_DIR, "**", "*.txt"), recursive=True)
    if not files:
        print("Текстовые файлы для индексации не найдены.")
        return

    existing_docs = collection.get()
    existing_sources = set()
    if existing_docs and "metadatas" in existing_docs and existing_docs["metadatas"]:
        for meta in existing_docs["metadatas"]:
            if meta and "source" in meta:
                existing_sources.add(meta["source"])

    new_chunks_count = 0

    for file_path in files:
        source_name = os.path.splitext(os.path.basename(file_path))[0]
        if source_name in existing_sources:
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            with open(file_path, "r", encoding="cp1251", errors="ignore") as f:
                text = f.read()

        if not text.strip():
            continue

        chunks = split_text_into_chunks(text, chunk_size=1000, overlap=150)
        if not chunks:
            continue

        tg_link = get_tg_link(file_path, source_name)
        print(f"• Индексация: {source_name} ({len(chunks)} фрагментов) -> {tg_link}")
        
        prefixed_chunks = [f"passage: {c}" for c in chunks]
        embeddings = embedder.encode(prefixed_chunks, show_progress_bar=False).tolist()

        ids = [f"{source_name}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": source_name, "link": tg_link, "chunk_id": i} for i in range(len(chunks))]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        new_chunks_count += len(chunks)

    if new_chunks_count > 0:
        clear_cache()
    
    print(f"\nСинхронизация завершена! Добавлено новых фрагментов: {new_chunks_count}")

if __name__ == "__main__":
    index_all()
