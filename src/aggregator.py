import os
import glob
from typing import List, Dict, Any

class DataAggregator:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def clean_text(self, text: str) -> str:
        """Очистка текста от мусорных пробелов и пустых строк."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def chunk_text(self, text: str, source_name: str) -> List[Dict[str, Any]]:
        """Разбиение текста на чанки с нахлестом (overlap) и сохранением метаданных."""
        cleaned_text = self.clean_text(text)
        chunks = []
        start = 0
        text_length = len(cleaned_text)
        chunk_id = 0

        while start < text_length:
            end = start + self.chunk_size
            chunk_str = cleaned_text[start:end]
            
            chunks.append({
                "chunk_id": f"{source_name}_chunk_{chunk_id}",
                "text": chunk_str,
                "metadata": {
                    "source": source_name,
                    "chunk_index": chunk_id,
                    "char_start": start,
                    "char_end": min(end, text_length)
                }
            })
            
            chunk_id += 1
            # Сдвигаем окно с учетом overlap
            start += (self.chunk_size - self.chunk_overlap)

        return chunks

    def process_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """Загрузка всех .txt файлов из указанной папки."""
        all_chunks = []
        txt_files = glob.glob(os.path.join(dir_path, "*.txt"))

        print(f"[Aggregator] Найдено файлов .txt: {len(txt_files)} в {dir_path}")

        for file_path in txt_files:
            file_name = os.path.basename(file_path)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                file_chunks = self.chunk_text(content, source_name=file_name)
                all_chunks.extend(file_chunks)
                print(f" -> Обработан файл {file_name}: сгенерировано {len(file_chunks)} чанков")
            except Exception as e:
                print(f"[Ошибка] Не удалось прочитать {file_name}: {e}")

        return all_chunks

if __name__ == "__main__":
    # Локальная проверка работы модуля
    aggregator = DataAggregator(chunk_size=1000, chunk_overlap=150)
    
    # Проверяем папку с транскриптами
    transcripts_dir = os.path.join("storage", "transcripts")
    if os.path.exists(transcripts_dir):
        results = aggregator.process_directory(transcripts_dir)
        print(f"\n[Успех] Всего сгенерировано чанков для RAG: {len(results)}")
    else:
        print(f"\n[!] Папка {transcripts_dir} пока не существует. Создайте её для проверки.")