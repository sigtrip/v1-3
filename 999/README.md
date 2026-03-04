# Инструкции по сборке и интеграции ARGOS

## 1. Rust ядро (core-rs)

### Сборка и установка
1. Установите Rust: https://rustup.rs/
2. Перейдите в папку ядра:
   cd 999/core-rs
3. Сборка Python-модуля:
   maturin develop --release
   # или
   pip install maturin
   maturin build --release
4. После сборки появится wheel-файл, который можно установить через pip.

### Зависимости
- pyo3 (FFI для Python)
- serde, serde_json (сериализация)

## 2. Python-логика (ai-py)

1. Создайте виртуальное окружение:
   python3 -m venv .venv
   source .venv/bin/activate
2. Установите зависимости:
   pip install -r requirements.txt
3. Проверьте импорт empathy_engine:
   python ai-py/empathy_test.py

## 3. Go Mesh/P2P (mesh-go)

1. Установите Go: https://go.dev/doc/install
2. Перейдите в папку:
   cd 999/mesh-go
3. Запуск демо-узла:
   go run main.go

## 4. Интеграция
- Rust ядро импортируется в Python через pyo3/maturin.
- Mesh/P2P сервисы общаются с Python через gRPC/WebSocket/REST (пример ниже).

---
# Пример gRPC для Go

// mesh-go/p2p.proto
syntax = "proto3";
package p2p;
service Mesh {
  rpc SendMessage (Message) returns (Ack) {}
}
message Message {
  string from = 1;
  string body = 2;
}
message Ack {
  bool ok = 1;
}

# Генерация gRPC:
protoc --go_out=. --go-grpc_out=. p2p.proto

---
# Пример криптографии в Rust

// core-rs/src/crypto.rs
use pyo3::prelude::*;
use rand::Rng;

#[pyfunction]
pub fn gen_key() -> PyResult<String> {
    let key: [u8; 32] = rand::thread_rng().gen();
    Ok(hex::encode(key))
}

// В lib.rs
mod crypto;
use crypto::gen_key;

#[pymodule]
fn empathy_engine(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<EmpathyEngine>()?;
    m.add_function(wrap_pyfunction!(gen_key, m)?)?;
    Ok(())
}

---
# Пример вызова Rust-криптографии из Python
from empathy_engine import gen_key
print(gen_key())

---
# Пример WebSocket для Go
import (
	"github.com/gorilla/websocket"
)
// ...
conn, _, err := websocket.DefaultDialer.Dial("ws://localhost:8080/ws", nil)
if err != nil { panic(err) }
conn.WriteMessage(websocket.TextMessage, []byte("Hello"))
