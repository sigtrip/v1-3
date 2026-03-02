# P2P Транспорты

## Обзор

Argos поддерживает несколько транспортных протоколов для P2P-коммуникации между нодами.
Все транспорты наследуют `P2PTransportBase` и регистрируются через `TransportRegistry`.

## Встроенные транспорты

| Транспорт    | Описание                          | Вес по умолч. | ENV-переменная         |
|-------------|-----------------------------------|:-------------:|------------------------|
| TCP         | Стандартный TCP JSON               | 0.8           | _(всегда активен)_      |
| WireGuard   | UDP-туннель через WG-интерфейс     | 1.2           | `ARGOS_WG_INTERFACE`    |
| ZeroTier    | Виртуальная L2-сеть               | 1.1           | `ARGOS_ZT_NETWORK`      |
| ZKP+*       | Обёртка с подписью Schnorr NIZK   | 1.5           | `ARGOS_P2P_ZKP=on`      |

## Настройка

### WireGuard

```bash
# Поднимите WireGuard интерфейс
sudo wg-quick up wg0

# В .env:
ARGOS_WG_INTERFACE=wg0
```

### ZeroTier

```bash
# Подключитесь к сети
sudo zerotier-cli join <network_id>

# В .env:
ARGOS_ZT_NETWORK=<network_id>
```

### ZKP Privacy-Routing

```bash
# В .env:
ARGOS_P2P_ZKP=on
```

При активации ZKP все исходящие пакеты подписываются Schnorr NIZK-proof.
Входящие пакеты верифицируются перед обработкой.

## Создание custom-транспорта

```python
from src.connectivity.p2p_transport import P2PTransportBase

class MyTransport(P2PTransportBase):
    name = "my-transport"

    def send(self, peer_id: str, payload: bytes) -> None:
        ...

    def recv(self):
        ...

    def request(self, addr: str, payload: dict, timeout: int = 8) -> dict:
        ...

    def is_available(self) -> bool:
        return True
```

Регистрация в `ArgosCore.start_p2p`:

```python
from src.connectivity.p2p_transport import MyTransport
self.p2p.register_transport("my-transport", MyTransport(), weight=1.0)
```

Или через текстовый интент:

```
p2p вес my-transport 0.9
```

## Управление весами

Вес определяет приоритет транспорта (0.0–2.0). Более высокий вес = предпочтительный транспорт.

```
p2p вес wireguard 1.5
p2p тюнинг
p2p транспорт
```

## Тестирование

```bash
pytest tests/test_p2p.py -k "Transport" -v
```
