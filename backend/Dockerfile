# Cloud Run-ready image for the Physical IDE agent backend.
FROM python:3.11-slim

WORKDIR /app

# Install deps first so layer caching survives source edits.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run sets PORT; default 8080 to match the contract and deploy.sh.
ENV PORT=8080
ENV MOCK_MODE=true
EXPOSE 8080

# Use the shell form so $PORT is expanded at runtime by Cloud Run.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
