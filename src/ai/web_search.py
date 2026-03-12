import requests
from duckduckgo_search import DDGS

class WebIntelligence:
    def __init__(self):
        self.ddgs = DDGS()

    def search(self, query):
        """Поиск в интернете без ключей API"""
        try:
            results = self.ddgs.text(query, max_results=3)
            summary = "\n".join([f"🌐 {r['title']}: {r['body']}" for r in results])
            return summary if summary else "🔍 Ничего не найдено в открытых источниках."
        except Exception as e:
            return f"❌ Ошибка сетевого уровня: {e}"