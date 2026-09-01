import os
import glob
import time
import sys
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | transcriber | %(message)s")

raw_keys = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

if not API_KEYS:
    logging.error("Не заданы API-ключи. Проверьте .env")
    sys.exit(1)

current_key_idx = 0
client = genai.Client(api_key=API_KEYS[current_key_idx])
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

AUDIO_DIR = os.path.join("storage", "audio")
OUTPUT_DIR = os.path.join("storage", "transcriptions")
os.makedirs(OUTPUT_DIR, exist_ok=True)

AUDIO_EXTENSIONS = ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg", "*.oga", "*.opus", "*.webm", "*.flac")

def get_audio_files():
    audio_files = []
    for ext in AUDIO_EXTENSIONS:
        audio_files.extend(glob.glob(os.path.join(AUDIO_DIR, "**", ext), recursive=True))
    return sorted(list(set(audio_files)))

def get_output_path(audio_path: str):
    rel_path = os.path.relpath(audio_path, AUDIO_DIR)
    base_name = os.path.splitext(rel_path)[0]
    return os.path.join(OUTPUT_DIR, f"{base_name}.txt")

def switch_to_next_key():
    global current_key_idx, client
    current_key_idx += 1
    if current_key_idx < len(API_KEYS):
        logging.info(f"🔄 Лимит исчерпан. Переключаемся на ключ #{current_key_idx + 1} из {len(API_KEYS)}...")
        client = genai.Client(api_key=API_KEYS[current_key_idx])
        return True
    else:
        logging.error("🛑 Все доступные API-ключи исчерпали квоту!")
        print("\n" + "="*60)
        print("🛑 ВСЕ КЛЮЧИ ИСЧЕРПАНЫ.")
        print("="*60 + "\n")
        return False

def transcribe_file(file_path: str):
    global client
    out_txt_path = get_output_path(file_path)
    file_name = os.path.basename(file_path)

    if os.path.exists(out_txt_path):
        return True

    os.makedirs(os.path.dirname(out_txt_path), exist_ok=True)
    logging.info(f"→ Обработка: {file_name}")

    while True:
        uploaded_file = None
        try:
            uploaded_file = client.files.upload(file=file_path)
            
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2)
                uploaded_file = client.files.get(name=uploaded_file.name)

            if uploaded_file.state.name == "FAILED":
                logging.error(f"X Ошибка загрузки файла {file_name}")
                return True

            prompt = (
                "Сделай максимально точную, дословную текстовую расшифровку этой аудиозаписи на русском языке "
                "с сохранением исламских терминов и арабских выражений. Без сокращений и комментариев."
            )

            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[uploaded_file, prompt],
                    config=types.GenerateContentConfig(tools=[])
                )
                with open(out_txt_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                logging.info(f"✓ Успешно расшифрован: {file_name}")
                return True
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota exceeded" in err_str:
                    logging.warning(f"Ключ #{current_key_idx + 1} исчерпан.")
                    if switch_to_next_key():
                        continue
                    else:
                        return False
                logging.error(f"X Ошибка генерации {file_name}: {err_str}")
                return True

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota exceeded" in err_str:
                logging.warning(f"Ключ #{current_key_idx + 1} исчерпан при загрузке.")
                if switch_to_next_key():
                    continue
                else:
                    return False
            logging.error(f"X Ошибка обработки {file_name}: {e}")
            return True
        finally:
            if uploaded_file:
                try:
                    client.files.delete(name=uploaded_file.name)
                except Exception:
                    pass

def main():
    audio_files = get_audio_files()
    if not audio_files:
        logging.warning("В папке storage/audio не найдено аудиофайлов.")
        return

    logging.info(f"Всего файлов в очереди: {len(audio_files)}. Ключей в пуле: {len(API_KEYS)}.")
    for f in audio_files:
        success = transcribe_file(f)
        if not success:
            sys.exit(0)
        time.sleep(1)

if __name__ == "__main__":
    main()
