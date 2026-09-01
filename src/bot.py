import os
import re
import time
import asyncio
import logging
import chromadb
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

class FastONNXEmbedder:
    def __init__(self, model_id: str):
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        # Скачивание готового ONNX файла модели напрямую из HF
        self.session = ort.InferenceSession(
            f"https://huggingface.co/{model_id}/resolve/main/model.onnx",
            providers=["CPUExecutionProvider"]
        )

    def encode(self, texts, show_progress_bar=False):
        inputs = self.tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="np")
        ort_inputs = {
            "input_ids": inputs["input_ids"],
            "attention_mask": inputs["attention_mask"]
        }
        if "token_type_ids" in inputs and "token_type_ids" in [i.name for i in self.session.get_inputs()]:
            ort_inputs["token_type_ids"] = inputs["token_type_ids"]

        outputs = self.session.run(None, ort_inputs)
        token_embeddings = outputs[0]
        input_mask = np.expand_dims(inputs["attention_mask"], axis=-1)
        sum_embeddings = np.sum(token_embeddings * input_mask, axis=1)
        sum_mask = np.clip(np.sum(input_mask, axis=1), a_min=1e-9, a_max=None)
        embeddings = sum_embeddings / sum_mask
        norm = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return (embeddings / np.clip(norm, a_min=1e-12, a_max=None)).tolist()
from aiogram import Bot, Dispatcher, types, BaseMiddleware
from aiogram.filters import CommandStart
from aiogram.enums import ChatAction
from dotenv import load_dotenv

from chat import ask_bot
from query_expander import get_smart_query

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле!")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

DB_DIR = os.path.join("storage", "chroma_db")
MODEL_NAME = "intfloat/multilingual-e5-small"

print(f"Загрузка локальной модели поиска ({MODEL_NAME})...")
embedder = FastONNXEmbedder(MODEL_NAME)
chroma_client = chromadb.PersistentClient(path=DB_DIR)
collection = chroma_client.get_or_create_collection(
    name="imam_lectures",
    metadata={"hnsw:space": "cosine"}
)

def search_lectures(query: str, top_k: int = 6):
    smart_query = get_smart_query(query)
    logging.info(f"🔍 Поисковый профиль запроса: '{smart_query}'")
    
    query_text = f"query: {smart_query}"
    query_embedding = embedder.encode([query_text], show_progress_bar=False).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k
    )

    if not results or not results.get("documents") or not results["documents"][0]:
        return ""

    docs = results["documents"][0]
    metas = results["metadatas"][0]

    context_parts = []
    for doc, meta in zip(docs, metas):
        src_name = meta.get("source", "Урок")
        link = meta.get("link", "")
        context_parts.append(f"### Урок: {src_name}\nССЫЛКА_НА_УРОК: {link}\nТекст фрагмента:\n{doc}")

    return "\n\n".join(context_parts)

class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limit_seconds: int = 3):
        self.limit = limit_seconds
        self.last_user_time = {}

    async def __call__(self, handler, event: types.Message, data: dict):
        if not isinstance(event, types.Message):
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.time()
        last_time = self.last_user_time.get(user_id, 0)

        if now - last_time < self.limit:
            await event.answer("⏳ Пожалуйста, подождите пару секунд перед следующим вопросом.")
            return

        self.last_user_time[user_id] = now
        return await handler(event, data)

dp.message.middleware(RateLimitMiddleware(limit_seconds=3))

def split_message(text: str, max_length: int = 3800):
    if len(text) <= max_length:
        return [text]

    parts = []
    while len(text) > max_length:
        split_idx = text.rfind("\n\n", 0, max_length)
        if split_idx == -1:
            split_idx = text.rfind("\n", 0, max_length)
        if split_idx == -1:
            split_idx = text.rfind(" ", 0, max_length)
        if split_idx == -1:
            split_idx = max_length

        parts.append(text[:split_idx].strip())
        text = text[split_idx:].strip()

    if text:
        parts.append(text)
    return parts

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    welcome_text = (
        "✨ *Ассаляму алейкум ва рахматуллахи ва баракатух!*\n\n"
        "Я — интеллектуальный ассистент по архиву уроков и лекций.\n\n"
        "Задайте интересующий вас вопрос, и я приведу подробное разъяснение из уроков со ссылками на первоисточники."
    )
    await message.answer(welcome_text, parse_mode="Markdown")

@dp.message()
async def handle_message(message: types.Message):
    user_query = message.text.strip() if message.text else ""
    if not user_query:
        return

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    try:
        loop = asyncio.get_running_loop()
        context = await loop.run_in_executor(None, search_lectures, user_query)
        response = await loop.run_in_executor(None, ask_bot, user_query, context)

        for part in split_message(response):
            try:
                # Отправляем с базовым Markdown и выключенным превью ссылки
                await message.answer(part, parse_mode="Markdown", disable_web_page_preview=True)
            except Exception as e:
                logging.warning(f"Ошибка Markdown: {e}")
                # Если упало из-за спецсимволов — отправляем как чистый текст
                await message.answer(part, parse_mode=None, disable_web_page_preview=True)

    except Exception as e:
        logging.exception(f"Ошибка при обработке запроса: {e}")
        await message.answer("Произошла ошибка при обработке запроса. Пожалуйста, попробуйте чуть позже.")

async def main():
    print("=== Telegram-бот перезапущен с аккуратными ссылками ===")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
