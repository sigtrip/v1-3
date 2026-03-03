#!/usr/bin/env python3
import os
import configparser
from dotenv import dotenv_values

# Путь к .env Argos и config.ini agenticSeek
ARGOS_ENV = os.path.join(os.path.dirname(__file__), '..', '.env')
AGENTICSEEK_CONFIG = os.path.join(os.path.dirname(__file__), '..', 'external', 'agenticseek', 'config.ini')

# Карта провайдеров: env -> config.ini
PROVIDER_MAP = {
    'ollama': {
        'env_model': 'WHISPER_MODEL',
        'env_addr': 'ARGOS_OLLAMA_HEALTH_URL',
        'default_model': 'deepseek-r1:14b',
        'default_addr': '127.0.0.1:11434',
    },
    'openai': {
        'env_model': 'OPENAI_MODEL',
        'env_addr': 'OPENAI_API_URL',
        'default_model': 'gpt-4o-mini',
        'default_addr': 'api.openai.com',
    },
    'google': {
        'env_model': 'YANDEXGPT_MODEL_URI',
        'env_addr': 'GEMINI_API_KEY',
        'default_model': 'gemini-pro',
        'default_addr': '',
    },
    'lm-studio': {
        'env_model': 'LMSTUDIO_MODEL',
        'env_addr': 'LMSTUDIO_BASE_URL',
        'default_model': 'local-model',
        'default_addr': 'http://127.0.0.1:1234/v1/chat/completions',
    },
}

def main():
    env = dotenv_values(ARGOS_ENV)
    config = configparser.ConfigParser()
    config.read(AGENTICSEEK_CONFIG)

    # Выбор провайдера
    provider = env.get('ARGOS_AGENTICSEEK_PROVIDER', '').lower()
    if not provider:
        provider = env.get('ARGOS_AGENT_BACKEND', '').lower()
        if provider not in PROVIDER_MAP:
            provider = 'ollama'  # default
    if provider not in PROVIDER_MAP:
        provider = 'ollama'
    pmap = PROVIDER_MAP[provider]

    # Модель и адрес
    model = env.get(pmap['env_model'], pmap['default_model'])
    addr = env.get(pmap['env_addr'], pmap['default_addr'])
    if not addr:
        addr = pmap['default_addr']

    # Запись в config.ini
    if 'MAIN' not in config:
        config['MAIN'] = {}
    config['MAIN']['provider_name'] = provider
    config['MAIN']['provider_model'] = model
    config['MAIN']['provider_server_address'] = addr

    with open(AGENTICSEEK_CONFIG, 'w') as f:
        config.write(f)
    print(f"[agenticseek] config.ini обновлен: provider={provider}, model={model}, addr={addr}")

if __name__ == '__main__':
    main()
