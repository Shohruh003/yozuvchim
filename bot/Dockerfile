FROM python:3.12-slim

# System dependencies for python-docx, pillow, lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev libxslt1-dev \
    libjpeg-dev zlib1g-dev \
    libpq-dev \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Storage location for generated documents (mounted volume in compose)
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data /app/logs

CMD ["python", "main.py"]
