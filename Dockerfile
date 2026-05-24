FROM python:3.11-slim

WORKDIR /app

# System deps for h5py, psycopg2, and rasterio (GDAL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libhdf5-dev libgomp1 libgdal-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/
COPY .env.example .env.example

ENV PYTHONPATH=/app

ENTRYPOINT ["bash", "scripts/entrypoint.sh"]
