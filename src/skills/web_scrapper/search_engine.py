"""
search_engine.py — Локальный модуль поиска и суммаризации
Использует duckduckgo-search и trafilatura для сбора информации без API-ключей.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import trafilatura
from duckduckgo_search import DDGS

log = logging.getLogger("argos.search")


class LocalSearchEngine:
    """
    Поисковый движок:
    1. Ищет в DuckDuckGo
    2. Скачивает контент страниц (trafilatura)
    3. Возвращает суммаризированный текст
    """

    def __init__(self, max_results: int = 3):
        self.max_results = max_results
        self.ddgs = DDGS()

    def search(self, query: str) -> List[Dict[str, str]]:
        """Возвращает список результатов [{title, href, body}, ...]"""
        try:
            results = list(self.ddgs.text(query, max_results=self.max_results))
            return results
        except Exception as e:
            log.error(f"DDG Search error: {e}")
            return []

    def fetch_page_content(self, url: str) -> str:
        """Скачивает и очищает текст страницы."""
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(
                    downloaded, include_comments=False, include_tables=False
                )
                if text:
                    return text
        except Exception as e:
            log.warning(f"Error fetching {url}: {e}")
        return ""

    def research(self, query: str, depth: int = 3) -> str:
        """Полный цикл: поиск -> скачивание -> объединение."""
        log.info(f"Researching: {query}")
        results = self.search(query)
        if not results:
            return "Ничего не найдено."

        full_text = [f"🔍 Поиск: {query}\n"]

        # Параллельное скачивание
        with ThreadPoolExecutor(max_workers=3) as executor:
            urls = [r["href"] for r in results[:depth]]
            contents = list(executor.map(self.fetch_page_content, urls))

        for i, res in enumerate(results[:depth]):
            title = res.get("title", "No title")
            link = res.get("href", "")
            snippet = res.get("body", "")
            content = contents[i]

            # Если контент слишком короткий, используем сниппет
            if len(content) < 100:
                content = snippet

            # Обрезаем слишком длинный контент
            content = content[:1500] + "..." if len(content) > 1500 else content

            full_text.append(f"\nИсточник {i + 1}: {title}")
            full_text.append(f"Ссылка: {link}")
            full_text.append(f"Контент:\n{content}\n")
            full_text.append("-" * 40)

        return "\n".join(full_text)


# Синглтон
_engine = None


def get_search_engine():
    global _engine
    if _engine is None:
        _engine = LocalSearchEngine()
    return _engine
