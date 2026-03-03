"""
Rasa NLP Adapter для Argos (в разработке)
"""
class RasaAdapter:
    def __init__(self, core, url="http://localhost:5005/model/parse"):
        self.core = core
        self.url = url

    def parse(self, text):
        import requests
        resp = requests.post(self.url, json={"text": text})
        return resp.json()

    def handle_message(self, text):
        result = self.parse(text)
        # TODO: интеграция с ядром Argos
        return result
