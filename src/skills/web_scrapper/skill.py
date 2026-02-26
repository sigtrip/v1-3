import requests
from bs4 import BeautifulSoup

class ArgosScrapper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def quick_search(self, query):
        """Парсинг поисковой выдачи для получения оперативной информации."""
        try:
            # Используем DuckDuckGo (HTML версия) для анонимности и скорости
            url = f"https://html.duckduckgo.com/html/?q={query}"
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code != 200:
                return "Ошибка доступа к сетевым узлам поиска."

            soup = BeautifulSoup(response.text, 'html.parser')
            # Извлекаем сниппеты (краткие описания) результатов
            snippets = soup.find_all('a', class_='result__snippet')

            if not snippets:
                return "Поиск не дал результатов. Информация в зашифрованных слоях не найдена."

            # Берем первые 3 результата для лаконичности
            results = [s.get_text().strip() for s in snippets[:3]]
            formatted_data = " | ".join(results)

            return f"Данные из глобальной сети: {formatted_data}"

        except Exception as e:
            return f"Сбой сетевого сканирования: {str(e)}"
