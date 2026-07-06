FROM python:3.11-slim

# system deps: graphviz for static graph rendering (optional at runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Ingest sample docs happens automatically on first startup if the index is empty.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
