import re
import json
import logging
import functools
import pymorphy3
from google import genai
from google.genai import types
from chat import get_current_client
from synonyms import get_synonyms

morph = pymorphy3.MorphAnalyzer()

@functools.lru_cache(maxsize=2048)
def normalize_word(word: str) -> str:
    parsed = morph.parse(word)
    return parsed[0].normal_form if parsed else word

def extract_json(text: str) -> dict:
    """Безопасное извлечение JSON из любого формата ответа модели"""
    text = text.strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {}

EXPAND_PROMPT = """Выдели ключевые исламские термины из запроса и напиши их арабские синонимы, транслитерации и русский перевод.
Верни ТОЛЬКО валидный JSON:
{{"synonyms": ["термин1", "термин2"]}}

Запрос: "{query}"
JSON:"""

def get_smart_query(user_query: str) -> str:
    clean_words = [w.strip(".,!?:;\"'()[]«»") for w in user_query.lower().split() if len(w) > 1]
    
    # 1. Мгновенно собираем леммы и синонимы из детерминированного словаря
    collected_terms = set(clean_words)
    for w in clean_words:
        lemma = normalize_word(w)
        collected_terms.add(lemma)
        collected_terms.update(get_synonyms(w))
        collected_terms.update(get_synonyms(lemma))

    # 2. Если термины уже найдены в локальном словаре — не тратим время на LLM
    if len(collected_terms) > len(clean_words) + 1:
        return " ".join(collected_terms)

    # 3. Если слово редкое/неизвестное — подключаем LLM с безопасным парсером
    try:
        client = get_current_client()
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=EXPAND_PROMPT.format(query=user_query),
            config=types.GenerateContentConfig(
                temperature=0.0
            )
        )
        if response.text:
            data = extract_json(response.text)
            extra = data.get("synonyms", [])
            for item in extra:
                if isinstance(item, str) and len(item) > 1:
                    collected_terms.add(item.lower().strip())
    except Exception as e:
        logging.warning(f"Ошибка фонового вызова LLM: {e}")

    return " ".join(collected_terms)
