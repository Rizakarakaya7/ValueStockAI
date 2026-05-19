# Kesin sürüm belirterek sürprizleri engelliyoruz
FROM python:3.12.9-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Sistem bağımlılıklarını ve TLS/SSL sertifikalarını yükle
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    ca-certificates \
    gnupg \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Ana klasördeki requirements'ı kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tüm kodları içeri aktar
COPY . .