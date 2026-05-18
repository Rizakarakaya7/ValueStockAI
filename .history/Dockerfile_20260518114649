# Kesin sürüm belirterek sürprizleri engelliyoruz
FROM python:3.12.9-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Sistem bağımlılıklarını yükle
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Ana klasördeki requirements'ı kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tüm kodları içeri aktar
COPY . .