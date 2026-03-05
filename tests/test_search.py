"""
test_search.py — Тесты для локального поиска (mocked)
"""

import pytest
from unittest.mock import MagicMock, patch
from src.skills.web_scrapper.search_engine import LocalSearchEngine


class TestSearchEngine:
    @patch("src.skills.web_scrapper.search_engine.DDGS")
    def test_search_basic(self, mock_ddgs):
        """Проверка базового поиска через DDGS."""
        # Настройка мока
        mock_instance = MagicMock()
        mock_instance.text.return_value = [
            {"title": "Test Title", "href": "http://example.com", "body": "Test Body"}
        ]
        mock_ddgs.return_value = mock_instance

        engine = LocalSearchEngine()
        results = engine.search("test query")

        assert len(results) == 1
        assert results[0]["title"] == "Test Title"
        mock_instance.text.assert_called_with("test query", max_results=3)

    @patch("src.skills.web_scrapper.search_engine.trafilatura.fetch_url")
    @patch("src.skills.web_scrapper.search_engine.trafilatura.extract")
    def test_fetch_content(self, mock_extract, mock_fetch):
        """Проверка скачивания контента."""
        mock_fetch.return_value = "<html><body>Content</body></html>"
        mock_extract.return_value = "Extracted Text"

        engine = LocalSearchEngine()
        content = engine.fetch_page_content("http://example.com")

        assert content == "Extracted Text"
        mock_fetch.assert_called_once()

    @patch("src.skills.web_scrapper.search_engine.DDGS")
    def test_research_integration(self, mock_ddgs):
        """Проверка полного цикла research (mocked)."""
        # Мокаем поиск
        mock_instance = MagicMock()
        mock_instance.text.return_value = [
            {"title": "Result 1", "href": "http://1.com", "body": "Snippet 1"}
        ]
        mock_ddgs.return_value = mock_instance

        # Мокаем trafilatura внутри класса (через patch.object сложнее, используем patch функции выше)
        with patch(
            "src.skills.web_scrapper.search_engine.trafilatura.fetch_url"
        ) as mock_fetch:
            mock_fetch.return_value = (
                None  # Симулируем ошибку сети, должен использоваться сниппет
            )

            engine = LocalSearchEngine()
            report = engine.research("query")

            # В коде используется лупа 🔍, а в тесте была 🔎
            assert "🔍 Поиск: query" in report
            assert "Источник 1: Result 1" in report
            assert "Snippet 1" in report  # Fallback to snippet
