"""
Rasa NLP Adapter для Argos (в разработке)
"""
class RasaAdapter:
    def __init__(self, core, url="http://localhost:5005/model/parse"):
        self.core = core
        self.url = url

    def parse(self, text):
        try:
            import requests
        except ImportError:
            requests = None
        if requests is None:
            return {"error": "requests не установлен"}
        try:
            resp = requests.post(self.url, json={"text": text})
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def handle_message(self, text):
        result = self.parse(text)
        # TODO: интеграция с ядром Argos
        return result
