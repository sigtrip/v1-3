FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p logs backups archives

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run genesis on first start if config doesn't exist
RUN python genesis.py || true

# Default command
CMD ["python", "main.py"]
