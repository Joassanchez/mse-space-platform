FROM python:3.11-slim

WORKDIR /app

# System deps for h5py and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libhdf5-dev libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY .env.example .env.example

ENV PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "src.jobs.run_smap_ingestion"]
