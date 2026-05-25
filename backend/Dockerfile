FROM python:3.11-slim

WORKDIR /app

# Only backend-specific deps — no GDAL/hdf5 needed
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY .env.example .env.example

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
