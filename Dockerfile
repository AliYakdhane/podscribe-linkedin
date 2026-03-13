FROM python:3.11-slim

# Install system dependencies (ffmpeg for Whisper, plus basic build tools)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first (better layer cache)
COPY requirements-backend.txt ./requirements-backend.txt

RUN pip install --no-cache-dir -r requirements-backend.txt

# Copy the rest of the application
COPY . .

# Default command: run FastAPI backend
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

