"""
watson_bridge.py — IBM WatsonX AI Bridge (ibm-watsonx-ai)
Команды: режим ии watsonx | watsonx статус
"""
import os
from src.argos_logger import get_logger
log = get_logger("argos.watsonx")

try:
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
    WATSONX_OK = True
except ImportError:
    WATSONX_OK = False

AVAILABLE_MODELS = [
    "meta-llama/llama-3-1-70b-instruct",
    "meta-llama/llama-3-1-8b-instruct",
    "ibm/granite-13b-chat-v2",
    "ibm/granite-20b-chat-v2",
]


class WatsonXBridge:
    def __init__(self):
        self.api_key    = os.getenv("WATSONX_API_KEY", "")
        self.project_id = os.getenv("WATSONX_PROJECT_ID", "")
        self.url        = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
        self.model_id   = os.getenv("WATSONX_MODEL", "meta-llama/llama-3-1-70b-instruct")
        self._model     = None
        self._init_model()

    def _init_model(self):
        if not (WATSONX_OK and self.api_key and self.project_id):
            return
        try:
            creds  = Credentials(api_key=self.api_key, url=self.url)
            params = {
                GenParams.DECODING_METHOD:   "greedy",
                GenParams.MAX_NEW_TOKENS:    1024,
                GenParams.REPETITION_PENALTY: 1.05,
            }
            self._model = ModelInference(
                model_id=self.model_id,
                params=params,
                credentials=creds,
                project_id=self.project_id,
            )
            log.info("WatsonX: OK (%s)", self.model_id)
        except Exception as e:
            log.warning("WatsonX init: %s", e)

    @property
    def available(self) -> bool:
        return self._model is not None

    def ask(self, system: str, user: str) -> str | None:
        if not self.available: return None
        try:
            prompt = (f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
                      f"{system}\n<|eot_id|>"
                      f"<|start_header_id|>user<|end_header_id|>\n"
                      f"{user}\n<|eot_id|>"
                      f"<|start_header_id|>assistant<|end_header_id|>\n")
            res = self._model.generate_text(prompt=prompt)
            return res.strip() if res else None
        except Exception as e:
            log.error("WatsonX ask: %s", e)
            return None

    def status(self) -> str:
        lines = ["🔷 IBM WatsonX Bridge:"]
        if not WATSONX_OK:
            lines.append("  ❌ Не установлен: pip install ibm-watsonx-ai")
        elif not self.api_key:
            lines.append("  ❌ WATSONX_API_KEY не задан в .env")
        elif not self.project_id:
            lines.append("  ❌ WATSONX_PROJECT_ID не задан в .env")
        elif self.available:
            lines.append(f"  ✅ Подключён: {self.model_id}")
            lines.append(f"  URL: {self.url}")
        else:
            lines.append("  ⚠️ Ошибка инициализации — проверь ключи")
        lines.append(f"  Доступные модели: {', '.join(AVAILABLE_MODELS)}")
        return "\n".join(lines)
