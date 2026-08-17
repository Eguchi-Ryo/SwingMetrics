FROM python:3.11-slim

# システムライブラリのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先にCPU版PyTorchのバイナリを明示して高速インストール
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 残りの依存ライブラリをインストール
COPY requirements.txt .
# requirements.txt 内に torch / torchvision の重複行があっても wheel が優先されます
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data/uploads

EXPOSE 5001

CMD ["python", "app.py"]