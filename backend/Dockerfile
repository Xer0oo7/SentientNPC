FROM python:3.11-slim

WORKDIR /app

# Install build deps and cleanup
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy backend sources
COPY . /app

ENV PYTHONUNBUFFERED=1
ENV OLLAMA_URL=http://host.docker.internal:11434/api/generate

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
