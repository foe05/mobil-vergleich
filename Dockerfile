FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# nicht als root laufen
# /app/daten vorab anlegen: ein frisches Named Volume übernimmt Besitzer vom Image-Pfad
ENV MOBIL_DB=/app/daten/mobil.db
RUN useradd -m appuser && mkdir -p /app/daten && chown -R appuser /app
USER appuser

EXPOSE 8501
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "app.py"]
