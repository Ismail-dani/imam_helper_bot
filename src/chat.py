import os
import re
import logging
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

raw_keys = os.getenv("GEMINI_API_KEYS", "")
single_key = os.getenv("GEMINI_API_KEY", "")

all_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
if single_key and single_key not in all_keys:
    all_keys.insert(0, single_key)

if not all_keys:
    raise ValueError("API ключи Gemini не найдены в .env файле!")

current_key_idx = 0

def get_current_client():
    global current_key_idx
    return genai.Client(api_key=all_keys[current_key_idx])

def switch_key():
    global current_key_idx
    current_key_idx = (current_key_idx + 1) % len(all_keys)
    logging.info(f"🔄 Смена API ключа на #{current_key_idx + 1} из {len(all_keys)}")

def generate_with_retry(prompt: str) -> str:
    attempts = 0
    max_attempts = len(all_keys) * 2

    while attempts < max_attempts:
        client = get_current_client()
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[],
                    temperature=0.0
                )
            )
            if response.text:
                return response.text
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "Quota exceeded" in err:
                logging.warning(f"Ключ #{current_key_idx + 1} исчерпан, переключаем...")
                switch_key()
                time.sleep(1)
                attempts += 1
                continue
            logging.error(f"Ошибка генерации: {err}")
            switch_key()
            attempts += 1
            time.sleep(1)

    raise RuntimeError("Все API-ключи исчерпали квоту. Попробуйте позже.")

DISCLAIMER = "\n\n────────────────\n⚠️ *Примечание:* Ответ сгенерирован ИИ исключительно на основе аудиозаписей уроков. Для принятия религиозных решений обращайтесь к обладающим знанием."

def ask_bot(user_query: str, search_context: str = "") -> str:
    if not search_context or not search_context.strip():
        return "В доступных уроках имама нет информации по этому вопросу."

    prompt = f"""Ты — интеллектуальный ассистент по архиву исламских уроков конкретного преподавателя.
Твоя задача — предоставить структурированный, визуально эстетичный и точный ответ строго по приведенным фрагментам.

ПРАВИЛА ОФОРМЛЕНИЯ И ТИПОГРАФИКИ:
1. ВИЗУАЛЬНАЯ СТРУКТУРА:
   - Каждый пункт начинай с аккуратного эмодзи-маркера (🔹, 📌, ⚖️).
   - Выделяй ключевой тезис в начале пункта **жирным шрифтом**.
   - Религиозные термины пиши *курсивом* (например: *саляф салих*, *харам*, *батыль*, *му'минун*).
2. ССЫЛКИ НА ИСТОЧНИК:
   - В конце пункта ставь кликабельную ссылку строго в формате: [📖 Источник](ССЫЛКА_НА_УРОК)
   - Если источников несколько, пиши: [📖 Источник 1](ССЫЛКА_1), [📖 Источник 2](ССЫЛКА_2)
   - Не вставляй сырые URL-адреса.
3. ТОЧНОСТЬ АДРЕСАТА:
   - Если хукм касается женщин (или мужчин), прямо укажи это.
4. ТРЁХУРОВНЕВЫЙ ОТВЕТ:
   - Прямой ответ: начни со вступительного вывода, затем разложи по пунктам.
   - Смежная тема: начни с фразы «Прямого ответа на этот конкретный вопрос в уроках нет, однако по смежным темам разъясняется следующее:» и структурируй пункты.
   - Нет данных: «В доступных уроках имама нет информации по этому вопросу.»

ФРАГМЕНТЫ ИЗ УРОКОВ:
{search_context}

ВОПРОС:
{user_query}

ОТВЕТ:"""

    answer = generate_with_retry(prompt)
    if "нет информации по этому вопросу" not in answer.lower():
        answer += DISCLAIMER
    return answer
