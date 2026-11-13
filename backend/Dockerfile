# Bauplan für das Docker-Image der Flask-App.
FROM python:3.14-slim

# Python soll keine .pyc-Dateien schreiben und Ausgaben sofort anzeigen (wichtig für Logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Erst nur requirements.txt kopieren und installieren. Docker merkt sich diesen Schritt
# (Cache). Ändert sich nur der Code, muss nicht alles neu installiert werden.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Jetzt den restlichen Code kopieren (was ignoriert wird, steht in .dockerignore)
COPY . .

# Aus Sicherheitsgründen nicht als root laufen
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Docker prüft regelmäßig, ob die App noch antwortet
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# gunicorn = Produktions-Webserver. 2 Worker-Prozesse pro Container.
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "wsgi:app"]
