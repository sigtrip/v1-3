# Пример автоматического деплоя (Docker)

# 1. Dockerfile для Rust ядра
FROM rust:1.76 as builder
WORKDIR /app
COPY . .
RUN cd core-rs && cargo build --release

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/core-rs/target/release/libempathy_engine.so /usr/local/lib/
COPY ai-py/ ./ai-py/
RUN pip install maturin && cd ai-py && maturin develop --release
CMD ["python", "ai-py/empathy_test.py"]

# 2. Dockerfile для Go Mesh
FROM golang:1.22 as builder
WORKDIR /mesh
COPY mesh-go/ ./
RUN go build -o mesh-node main.go

FROM debian:bookworm-slim
WORKDIR /mesh
COPY --from=builder /mesh/mesh-node ./
CMD ["./mesh-node"]

# 3. docker-compose.yml
version: '3.9'
services:
  argos-core:
    build:
      context: .
      dockerfile: Dockerfile.rust
    container_name: argos-core
    restart: unless-stopped
  mesh-node:
    build:
      context: .
      dockerfile: Dockerfile.go
    container_name: mesh-node
    restart: unless-stopped
    ports:
      - "9999:9999"
