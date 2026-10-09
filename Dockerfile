FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY orbitra ./orbitra
COPY web ./web
# utilisateur sans privilèges (on ne fait jamais tourner un service web en root)
RUN useradd --create-home orbitra && chown -R orbitra /app
USER orbitra
EXPOSE 8000
CMD ["sh", "-c", "uvicorn orbitra.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
