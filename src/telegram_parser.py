# -*- coding: utf-8 -*-
import os
import sys
import json
import asyncio
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument
import src.config as config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_target_groups(raw_groups):
    if isinstance(raw_groups, dict):
        return list(raw_groups.items())
    
    if isinstance(raw_groups, str):
        try:
            parsed = json.loads(raw_groups)
            if isinstance(parsed, dict):
                return list(parsed.items())
            if isinstance(parsed, list):
                raw_groups = parsed
        except Exception:
            pass

    groups = []
    if isinstance(raw_groups, list):
        for idx, item in enumerate(raw_groups, 1):
            if isinstance(item, dict):
                groups.extend(item.items())
            elif isinstance(item, str):
                try:
                    parsed_item = json.loads(item)
                    if isinstance(parsed_item, dict):
                        groups.extend(parsed_item.items())
                        continue
                except Exception:
                    pass
                # Очищаем строку от кавычек и скобок
                clean_item = item.strip("{}\"' ")
                if ":" in clean_item:
                    k, v = clean_item.split(":", 1)
                    groups.append((k.strip("\"' "), v.strip("\"' ")))
                else:
                    groups.append((f"GROUP_{idx}", clean_item))
    return groups

async def main():
    session_path = os.path.join("storage", "user_session")
    client = TelegramClient(session_path, config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)
    await client.start()
    logging.info("Telethon авторизован успешно.")

    groups = parse_target_groups(config.TARGET_GROUPS)

    for group_name, group_url in groups:
        logging.info(f"=== Начинаем обработку группы: {group_name} ({group_url}) ===")
        save_dir = os.path.join("storage", "audio", group_name)
        os.makedirs(save_dir, exist_ok=True)

        try:
            entity = await client.get_entity(group_url)
            messages = await client.get_messages(entity, limit=None)
            total = len(messages)
            
            for idx, msg in enumerate(messages, 1):
                if msg.media and (msg.voice or msg.audio or (isinstance(msg.media, MessageMediaDocument) and msg.document.mime_type.startswith('audio/'))):
                    ext = ".ogg" if msg.voice else ".mp3"
                    if hasattr(msg, 'file') and msg.file and msg.file.ext:
                        ext = msg.file.ext
                    
                    filename = f"{group_name}_{msg.id}{ext}"
                    filepath = os.path.join(save_dir, filename)

                    if os.path.exists(filepath):
                        logging.info(f"[{group_name}] [{idx}/{total}] Пропущен (уже существует): {filename}")
                        continue

                    logging.info(f"[{group_name}] [{idx}/{total}] Скачивание: {filename}...")
                    await client.download_media(msg, file=filepath)
        except Exception as e:
            logging.error(f"Ошибка при работе с группой {group_name}: {e}")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
